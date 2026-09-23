"""Minimal HTTP bridge for the existing Personal Agent control surface.

Translates JSON-over-HTTP to PersonalAgent.execute(). No lifecycle, authority,
routing, scheduling, memory, or Task-execution logic lives here. The bridge
exists so a local UI can reach the D2 Personal Agent without an ACP client.

Endpoints:
    POST /create    {"request_id": "...", "text": "objective",
                    "mode": "deterministic" | "local-summary", ...}
                    mode deterministic (default): small deterministic Task (text.stats)
                    mode local-summary: real local-cognition summary Task (PoC)
                       → optional "marker" and "words" shape the bounded objective
    POST /inspect   {"task_id": "..."}
                    → returns current Task state
    POST /artifact  {"task_id": "...", "name": "answer"}
                    → returns artifact content
    POST /respond   {"task_id": "...", "response": "YES"}
                    → submits a human decision response
    GET  /task/<id>/events?after=<seq>
                    → read-only projection of the deployment's retained
                      ExecutionEvent log (events.jsonl, written by the kernel
                      journal, never by this bridge) filtered to the Task.
                      The cursor is the 0-based line index; "after" is
                      exclusive. The bridge owns no state: it only tails an
                      existing append-only log.
    GET  /health    → {"status": "ok"}

Transport only. The PersonalAgent + Restate remain authoritative.
"""
import json
import os
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit

from runtime.personal_agent import (
    PersonalAgent, RestateBinding, small_request, local_summary_request, task_identity,
)
from runtime.kernel.contracts import identifier, text as bounded_text, MAX_PACKET

INGRESS = os.environ.get('BLAINE_D2_INGRESS', 'http://127.0.0.1:48080')
HOST = '127.0.0.1'
PORT = int(os.environ.get('BLAINE_PERSONAL_HTTP_PORT', '48090'))
# Retained ExecutionEvent log written by the D2 kernel journal
# (personal_runtime.py wires JsonlEventPublisher). Read-only projection source
# for /task/<id>/events; the bridge never writes, orders, or owns these.
EVENTS_FILE = os.environ.get('BLAINE_D2_EVENTS_FILE', '')


def read_task_events(task_id: str, after: int) -> dict:
    """Read-only tail of the retained event log, filtered to one Task.

    The log is an append-only JSONL written by the kernel journal; line
    position is a stable cursor for this deployment's single log. A missing
    log yields an empty projection (the endpoint degrades, it does not fail).
    SENSITIVE records are never projected: only closed NORMAL metadata is
    surfaced, so no prompt/response/model-content ever leaves the deployment.
    """
    identifier(task_id)
    if type(after) is not int or after < 0:
        raise ValueError('after must be a non-negative integer line cursor')
    if not EVENTS_FILE or not os.path.exists(EVENTS_FILE):
        return {'task_id': task_id, 'after': after, 'next': 0, 'events': []}
    events = []
    seq = 0
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
                continue  # Trailing partial write; the cursor keeps advancing
            if record.get('task_id') == task_id and record.get('sensitivity') == 'NORMAL':
                events.append({
                    'seq': seq,
                    'event_type': record.get('event_type'),
                    'step_id': record.get('step_id'),
                    'outcome': record.get('outcome'),
                    'iteration': (record.get('payload') or {}).get('iteration'),
                    'occurred_at': record.get('occurred_at'),
                    'producer': record.get('producer', {}).get('component'),
                })
    return {'task_id': task_id, 'after': after, 'next': seq, 'events': events}

# Singleton — created once, shared across handler threads.
_control: PersonalAgent | None = None
_lock = threading.Lock()


def get_control() -> PersonalAgent:
    global _control
    if _control is None:
        with _lock:
            if _control is None:
                _control = PersonalAgent(RestateBinding(INGRESS))
    return _control


class BridgeHandler(BaseHTTPRequestHandler):
    """Stateless JSON translation. No Task state, no session."""

    def log_message(self, format, *args):
        pass  # Suppress default stderr logging; keep quiet.

    def _json(self, status: int, data: dict):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/health':
            self._json(200, {'status': 'ok'})
        elif self.path.startswith('/task/') and '/events' in self.path:
            self._task_events()
        else:
            self._json(404, {'error': 'Not found'})

    def _task_events(self):
        parts = urlsplit(self.path)
        segments = [p for p in parts.path.split('/') if p]
        # Expected shape: task, <task_id>, events
        if len(segments) != 3 or segments[0] != 'task' or segments[2] != 'events':
            self._json(400, {'error': 'Expected /task/<id>/events'})
            return
        try:
            after = 0
            if parts.query:
                for pair in parts.query.split('&'):
                    key, _, value = pair.partition('=')
                    if key == 'after':
                        after = int(value)
            self._json(200, read_task_events(segments[1], after))
        except ValueError as error:
            self._json(400, {'error': str(error)})
        except OSError:
            self._json(503, {'error': 'Event log unavailable'})

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            self._json(400, {'error': 'Empty body'})
            return
        try:
            body = json.loads(self.rfile.read(length))
        except json.JSONDecodeError:
            self._json(400, {'error': 'Invalid JSON'})
            return

        path = urlsplit(self.path).path
        try:
            if path == '/create':
                result = self._create(body)
            elif path == '/inspect':
                result = self._inspect(body)
            elif path == '/artifact':
                result = self._artifact(body)
            elif path == '/respond':
                result = self._respond(body)
            elif path == '/cancel':
                result = self._cancel(body)
            else:
                self._json(404, {'error': f'Unknown endpoint: {path}'})
                return
            self._json(200, result)
        except ValueError as e:
            self._json(400, {'error': str(e)})
        except Exception as e:
            self._json(500, {'error': f'Transport error: {type(e).__name__}'})

    def _create(self, body: dict) -> dict:
        request_id = body.get('request_id', '')
        objective = body.get('text', '')
        if not request_id or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', request_id):
            raise ValueError('request_id must be 1-80 chars: [A-Za-z0-9_-]')
        if not objective:
            raise ValueError('text is required')
        bounded_text(objective, MAX_PACKET)
        mode = body.get('mode', 'deterministic')
        if mode == 'deterministic':
            task_request = small_request(objective)
        elif mode == 'local-summary':
            task_request = local_summary_request(objective, body.get('marker', 'BLAINE_OK'),
                                                int(body.get('words', 40)))
        else:
            raise ValueError('Unknown create mode')
        return get_control().execute({
            'operation': 'create',
            'request_id': request_id,
            'task_request': task_request,
        })

    def _inspect(self, body: dict) -> dict:
        task_id = body.get('task_id', '')
        identifier(task_id)
        return get_control().execute({'operation': 'inspect', 'task_id': task_id})

    def _artifact(self, body: dict) -> dict:
        task_id = body.get('task_id', '')
        name = body.get('name', '')
        identifier(task_id)
        identifier(name)
        return get_control().execute({
            'operation': 'artifact', 'task_id': task_id, 'name': name,
        })

    def _respond(self, body: dict) -> dict:
        task_id = body.get('task_id', '')
        response = body.get('response', '')
        identifier(task_id)
        bounded_text(response, 512)
        return get_control().execute({
            'operation': 'respond', 'task_id': task_id, 'response': response,
        })

    def _cancel(self, body: dict) -> dict:
        task_id = body.get('task_id', '')
        identifier(task_id)
        return get_control().execute({'operation': 'cancel', 'task_id': task_id})


def run():
    server = HTTPServer((HOST, PORT), BridgeHandler)
    print(f'Blaine Personal HTTP bridge: http://{HOST}:{PORT} → Restate at {INGRESS}')
    server.serve_forever()


if __name__ == '__main__':
    run()
