#!/usr/bin/env python3
"""Scripted "hostile model": an OpenAI-compatible chat endpoint on a Unix socket.

  hostile_model.py --unix STATE/sock/hostile.sock --queue Q.jsonl --log L.jsonl

Each /v1/chat/completions request consumes the next line of the queue file:
  {"tool_call": {"name": "...", "arguments": {...}}}   -> one tool call
  {"text": "..."}                                        -> plain assistant text
  optional "delay_ms" on any item delays the response (to kill mid-call)
Empty queue -> "Acknowledged." Every request is logged with the offered tool
names and message roles, so tests can prove what the harness exposed and what
the "model" did. Used to make tool-surface and authority tests deterministic.
"""
import argparse
import json
import os
import socketserver
import threading
import time
from http.server import BaseHTTPRequestHandler

LOCK = threading.Lock()


class UnixHTTPServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--unix', required=True)
    parser.add_argument('--queue', required=True)
    parser.add_argument('--log', required=True)
    parser.add_argument('--dump-dir', default=None, help='save full bodies of requests offering host tools')
    args = parser.parse_args()
    cursor_path = args.queue + '.cursor'
    counter = [0]

    def next_item():
        with LOCK:
            lines = open(args.queue).read().splitlines() if os.path.exists(args.queue) else []
            cursor = int(open(cursor_path).read()) if os.path.exists(cursor_path) else 0
            if cursor >= len(lines):
                return None
            with open(cursor_path, 'w') as out:
                out.write(str(cursor + 1))
            return json.loads(lines[cursor])

    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'

        def address_string(self):
            return 'unix'

        def log_message(self, *_):
            pass

        def send_json(self, value, status=200):
            data = json.dumps(value).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path.rstrip('/').endswith('/models'):
                self.send_json({'object': 'list', 'data': [{'id': 'scripted', 'object': 'model', 'owned_by': 'spike'}]})
            else:
                self.send_json({'error': 'not found'}, 404)

        def do_POST(self):
            size = int(self.headers.get('Content-Length') or 0)
            body = json.loads(self.rfile.read(size) or b'{}')
            counter[0] += 1
            n = counter[0]
            item = next_item()
            tools = [t.get('function', {}).get('name') for t in body.get('tools') or []]
            messages = body.get('messages') or []
            last_user = next((m for m in reversed(messages) if m.get('role') == 'user'), None)
            if args.dump_dir and any(t in ('Bash', 'Edit', 'Read', 'Write') for t in tools):
                with open(os.path.join(args.dump_dir, f'request-{n}.json'), 'w') as dump:
                    json.dump(body, dump)
            with open(args.log, 'a') as out:
                out.write(json.dumps({'ts': round(time.time(), 3), 'n': n, 'tools_offered': tools,
                    'roles': [m.get('role') for m in messages], 'stream': body.get('stream'),
                    'last_user_head': json.dumps(last_user.get('content'))[:200] if last_user else None,
                    'scripted': item}) + '\n')
            if item and item.get('delay_ms'):
                time.sleep(item['delay_ms'] / 1000)
            created = int(time.time())
            cid = f'chatcmpl-hostile-{n}'
            if item and 'tool_call' in item:
                call = item['tool_call']
                delta = {'role': 'assistant', 'content': None, 'tool_calls': [{'index': 0, 'id': f'call_hostile_{n}',
                         'type': 'function', 'function': {'name': call['name'], 'arguments': json.dumps(call.get('arguments', {}))}}]}
                finish = 'tool_calls'
                message = {'role': 'assistant', 'content': None, 'tool_calls': delta['tool_calls']}
            else:
                text = (item or {}).get('text', 'Acknowledged.')
                delta = {'role': 'assistant', 'content': text}
                finish = 'stop'
                message = {'role': 'assistant', 'content': text}
            usage = {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}
            if not body.get('stream'):
                self.send_json({'id': cid, 'object': 'chat.completion', 'created': created, 'model': 'scripted',
                                'choices': [{'index': 0, 'message': message, 'finish_reason': finish}], 'usage': usage})
                return
            chunks = [
                {'id': cid, 'object': 'chat.completion.chunk', 'created': created, 'model': 'scripted',
                 'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]},
                {'id': cid, 'object': 'chat.completion.chunk', 'created': created, 'model': 'scripted',
                 'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish}]},
                {'id': cid, 'object': 'chat.completion.chunk', 'created': created, 'model': 'scripted',
                 'choices': [], 'usage': usage},
            ]
            payload = b''.join(b'data: ' + json.dumps(c).encode() + b'\n\n' for c in chunks) + b'data: [DONE]\n\n'
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    os.chdir(os.path.dirname(os.path.abspath(args.unix)))
    name = os.path.basename(args.unix)
    if os.path.exists(name):
        os.unlink(name)
    server = UnixHTTPServer(name, Handler)
    os.chmod(name, 0o600)
    server.serve_forever()


if __name__ == '__main__':
    main()
