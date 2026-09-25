#!/usr/bin/env python3
"""In-sandbox HTTP sink for LETTA_BASE_URL: records any Letta API call attempt.

Returns 503 to everything so the caller cannot mistake it for a real server.
Only method, path, a header-name list and body size are recorded.
"""
import argparse
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    class Sink(BaseHTTPRequestHandler):
        def handle_any(self):
            size = int(self.headers.get('Content-Length') or 0)
            body = self.rfile.read(size) if size else b''
            with open(args.out, 'a') as out:
                out.write(json.dumps({'ts': round(time.time(), 3), 'method': self.command,
                    'path': self.path, 'headers': sorted(self.headers.keys()),
                    'body_bytes': len(body)}) + '\n')
            self.send_response(503)
            self.send_header('Content-Length', '0')
            self.end_headers()

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = handle_any

        def log_message(self, *_):
            pass

    ThreadingHTTPServer(('127.0.0.1', args.port), Sink).serve_forever()


if __name__ == '__main__':
    main()
