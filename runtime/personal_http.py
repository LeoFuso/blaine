"""Minimal HTTP bridge for the existing Personal Agent control surface.

Translates JSON-over-HTTP to PersonalAgent.execute(). No lifecycle, authority,
routing, scheduling, memory, or Task-execution logic lives here. The bridge
exists so a local UI can reach the D2 Personal Agent without an ACP client.

Endpoints:
    POST /create    {"request_id": "...", "text": "objective"}
                    → creates a small deterministic Task (text.stats)
    POST /inspect   {"task_id": "..."}
                    → returns current Task state
    POST /artifact  {"task_id": "...", "name": "answer"}
                    → returns artifact content
    POST /respond   {"task_id": "...", "response": "YES"}
                    → submits a human decision response
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
    PersonalAgent, RestateBinding, small_request, task_identity,
)
from runtime.kernel.contracts import identifier, text as bounded_text, MAX_PACKET

INGRESS = os.environ.get('BLAINE_D2_INGRESS', 'http://127.0.0.1:48080')
HOST = '127.0.0.1'
PORT = int(os.environ.get('BLAINE_PERSONAL_HTTP_PORT', '48090'))

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
        else:
            self._json(404, {'error': 'Not found'})

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
        return get_control().execute({
            'operation': 'create',
            'request_id': request_id,
            'task_request': small_request(objective),
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
