"""Loopback HTTP transport for the Personal Agent services (thin by design).

Handlers only parse, bound and route. Conversation semantics live in
``personal_conversation``, Execution Briefs in ``personal_brief``, TaskResult
delivery in ``personal_delivery``, Task controls in ``personal_agent`` and
durable encrypted history in ``kernel.conversation``. This process hosts those
services and runs the delivery loop; it owns no lifecycle, authority, routing,
scheduling, memory or Task execution.

Task controls:
    POST /create    {"request_id", "text"}                (deterministic text.stats)
    POST /inspect   {"task_id"}
    POST /artifact  {"task_id", "name"}
    POST /respond   {"task_id", "value", "request_id"?}   (envelope built from inspect)
    POST /cancel    {"task_id"}
    GET  /task/<id>/events?after=<seq>
    GET  /health

Conversation (encrypted, durable):
    POST /conversation/create                        {"conversation_id"}
    GET  /conversation/<id>
    GET  /conversation/<id>/messages?after=<seq>
    GET  /conversation/<id>/tasks
    GET  /conversation/<id>/projection?after=<cursor>   (the presentation contract)
    POST /conversation/<id>/converse                 {"message_id", "text"}
    POST /conversation/<id>/brief/propose            {}
    GET  /conversation/<id>/brief/<brief_id>
    POST /conversation/<id>/brief/<brief_id>/confirm {}
    POST /conversation/<id>/brief/<brief_id>/reject  {}

Result delivery is not an endpoint: the hosted ResultDelivery loop appends each
delegated Task's verified outcome to its Conversation.
"""
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from runtime.kernel.contracts import MAX_PACKET, identifier, text as bounded_text
from runtime.personal_agent import human_response, small_request
from runtime.personal_services import Services

INGRESS = os.environ.get('BLAINE_D2_INGRESS', 'http://127.0.0.1:48080')
HOST = '127.0.0.1'
PORT = int(os.environ.get('BLAINE_PERSONAL_HTTP_PORT', '48090'))
# Retained ExecutionEvent log written by the D2 kernel journal (read-only here).
EVENTS_FILE = os.environ.get('BLAINE_D2_EVENTS_FILE', '')
CONVERSATION_ID = re.compile(r'[A-Za-z0-9_-]{1,64}')
# The desktop app's own origins (production webview and the dev server). Only
# they may read responses cross-origin; every POST must be JSON, which a page
# from any other origin cannot send without a preflight this bridge refuses.
APP_ORIGINS = frozenset(os.environ.get(
    'BLAINE_BRIDGE_ORIGINS', 'tauri://localhost,http://tauri.localhost,http://localhost:1420').split(','))


def read_task_events(task_id: str, after: int) -> dict:
    """Read-only tail of the retained event log, filtered to one Task.

    SENSITIVE records are never projected: only closed NORMAL metadata leaves.
    """
    identifier(task_id)
    if type(after) is not int or after < 0:
        raise ValueError('after must be a non-negative integer line cursor')
    if not EVENTS_FILE or not os.path.exists(EVENTS_FILE):
        return {'task_id': task_id, 'after': after, 'next': 0, 'events': []}
    events, seq = [], 0
    with open(EVENTS_FILE, 'r', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            seq += 1
            if seq <= after:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue  # trailing partial write; the cursor keeps advancing
            if record.get('task_id') == task_id and record.get('sensitivity') == 'NORMAL':
                events.append({'seq': seq, 'event_type': record.get('event_type'), 'step_id': record.get('step_id'),
                               'outcome': record.get('outcome'),
                               'iteration': (record.get('payload') or {}).get('iteration'),
                               'occurred_at': record.get('occurred_at'),
                               'producer': record.get('producer', {}).get('component')})
    return {'task_id': task_id, 'after': after, 'next': seq, 'events': events}


services = Services()  # composition root shared with personal_acp


def conversation_id(value: object) -> str:
    if not isinstance(value, str) or not CONVERSATION_ID.fullmatch(value):
        raise ValueError('conversation_id must be 1-64 chars: [A-Za-z0-9_-]')
    return value


class BridgeHandler(BaseHTTPRequestHandler):
    """Parse, bound, route. No Task state, no Conversation semantics."""

    def log_message(self, format, *args):
        pass

    def _cors(self):
        origin = self.headers.get('Origin')
        if origin in APP_ORIGINS:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')

    def _json(self, status: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        if self.headers.get('Origin') not in APP_ORIGINS:
            return self._json(403, {'error': 'Origin not allowed'})
        self.send_response(204)
        self._cors()
        self.send_header('Access-Control-Allow-Methods', 'GET, POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Max-Age', '600')
        self.end_headers()

    def _dispatch(self, route):
        try:
            result = route()
            if result is None:
                self._json(404, {'error': 'Not found'})
            else:
                self._json(200, result)
        except ValueError as error:
            self._json(400, {'error': str(error)[:512]})
        except KeyError as error:
            self._json(503, {'error': f'Unavailable: {str(error)[:256]}'})
        except Exception as error:  # transport boundary: never leak internals
            self._json(500, {'error': f'Transport error: {type(error).__name__}'})

    def do_GET(self):
        url = urlsplit(self.path)
        segments = [p for p in url.path.split('/') if p]
        query = parse_qs(url.query)
        if url.path == '/health':
            return self._json(200, {'status': 'ok'})
        if len(segments) == 3 and segments[0] == 'task' and segments[2] == 'events':
            return self._dispatch(lambda: read_task_events(segments[1], int(query.get('after', ['0'])[0])))
        if len(segments) >= 2 and segments[0] == 'conversation':
            cid, tail = segments[1], segments[2:]
            if not tail:
                return self._dispatch(lambda: services.store.get_conversation(conversation_id(cid)))
            if tail == ['messages']:
                after = int(query.get('after', ['0'])[0])
                return self._dispatch(lambda: {'conversation_id': cid, 'messages':
                                               services.store.list_messages(conversation_id(cid), limit=500, after=after)})
            if tail == ['projection']:
                # The presentation contract (docs/contracts/conversation-projection.md).
                after = int(query.get('after', ['0'])[0])
                return self._dispatch(lambda: services.projection.read(conversation_id(cid), after))
            if tail == ['tasks']:
                return self._dispatch(lambda: {'conversation_id': cid,
                                               'tasks': services.store.list_task_links(conversation_id(cid))})
            if len(tail) == 2 and tail[0] == 'brief':
                return self._dispatch(lambda: services.store.get_brief(conversation_id(cid), identifier(tail[1])))
        self._json(404, {'error': 'Not found'})

    def do_POST(self):
        if (self.headers.get('Content-Type') or '').split(';')[0].strip() != 'application/json':
            return self._json(415, {'error': 'POST bodies must be application/json'})
        length = int(self.headers.get('Content-Length', 0))
        try:
            body = json.loads(self.rfile.read(length)) if length else {}
        except json.JSONDecodeError:
            return self._json(400, {'error': 'Invalid JSON'})
        if not isinstance(body, dict):
            return self._json(400, {'error': 'Expected a JSON object'})
        path = urlsplit(self.path).path
        segments = [p for p in path.split('/') if p]
        agent = services.agent.execute if path in ('/create', '/inspect', '/artifact', '/cancel') else None
        routes = {
            '/create': lambda: agent({'operation': 'create', 'request_id': identifier(body.get('request_id')),
                                      'task_request': small_request(bounded_text(body.get('text'), MAX_PACKET))}),
            '/inspect': lambda: agent({'operation': 'inspect', 'task_id': identifier(body.get('task_id'))}),
            '/artifact': lambda: agent({'operation': 'artifact', 'task_id': identifier(body.get('task_id')),
                                        'name': identifier(body.get('name'))}),
            '/respond': lambda: self._respond(body),
            '/cancel': lambda: agent({'operation': 'cancel', 'task_id': identifier(body.get('task_id'))}),
            '/conversation/create': lambda: services.store.create_conversation(
                conversation_id(body.get('conversation_id'))),
        }
        if path in routes:
            return self._dispatch(routes[path])
        if len(segments) >= 3 and segments[0] == 'conversation':
            cid, tail = segments[1], segments[2:]
            if tail == ['converse']:
                return self._dispatch(lambda: services.conversation.converse(
                    conversation_id(cid), identifier(body.get('message_id')), body.get('text')))
            if tail == ['brief', 'propose']:
                return self._dispatch(lambda: services.briefs.propose(conversation_id(cid)))
            if len(tail) == 3 and tail[0] == 'brief' and tail[2] in ('confirm', 'reject'):
                action = services.briefs.confirm if tail[2] == 'confirm' else services.briefs.reject
                return self._dispatch(lambda: action(conversation_id(cid), identifier(tail[1])))
        self._json(404, {'error': f'Unknown endpoint: {path}'})

    def _respond(self, body):
        task_id = identifier(body.get('task_id'))
        value = bounded_text(body.get('value'), 80)
        request_id = body.get('request_id')
        state = services.agent.execute({'operation': 'inspect', 'task_id': task_id})
        envelope = human_response(state, task_id, value, identifier(request_id) if request_id else None)
        return services.agent.execute({'operation': 'respond', 'task_id': task_id, 'response': envelope})


def run():
    if services.deployment.get('cognition'):
        services.delivery().start()
    server = ThreadingHTTPServer((HOST, PORT), BridgeHandler)
    print(f'Blaine Personal Agent bridge: http://{HOST}:{PORT} -> Restate at {INGRESS}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    run()
