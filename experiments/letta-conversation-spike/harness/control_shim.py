#!/usr/bin/env python3
"""Loopback HTTP shim over the existing Personal Agent binding (unchanged).

The Letta-side controller is Node; Blaine's accepted Task controls are Python
(`runtime.personal_agent.PersonalAgent` + `RestateBinding`). This shim exposes
exactly those controls, building TaskRequests with the existing D2 helpers.

  POST /create_decision   {request_id, question}
  POST /create_summarize  {request_id, text}
  POST /inspect           {task_id}
  POST /decision_view     {task_id}   pending HumanDecisionRequest + kernel request_digest
  POST /artifact          {task_id, name}   bounded deliverable content (existing control)
  POST /respond           {task_id, request_id, request_revision, request_digest, response_id, value}
  POST /cancel            {task_id}

`respond` forwards the revision/digest the human was shown; it never recomputes
them from current state, so Blaine's stale/digest checks stay meaningful.
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from runtime.kernel.contracts import message
from runtime.kernel.human import request_digest
from runtime.personal_agent import ControlRejected, PersonalAgent, RestateBinding, decision_request, small_request


class JsonlEvents:
    def __init__(self, path):
        self.path = path

    def publish(self, event):
        with open(self.path, 'a') as out:
            out.write(json.dumps(event) + '\n')


def build(agent):
    def operation(name, body):
        if name == 'create_decision':
            return agent.execute({'operation': 'create', 'request_id': body['request_id'],
                                  'task_request': decision_request(body['request_id'], body['question'])})
        if name == 'create_summarize':
            return agent.execute({'operation': 'create', 'request_id': body['request_id'],
                                  'task_request': small_request(body['text'])})
        if name == 'decision_view':
            # The digest the human is shown is computed by the kernel's own function.
            view = agent.execute({'operation': 'inspect', 'task_id': body['task_id']})
            pending = view.get('pending_human_decision')
            return {'task_id': view['task_id'], 'lifecycle': view['lifecycle'], 'pending': pending,
                    'digest': request_digest(pending) if pending else None}
        if name == 'artifact':
            return agent.execute({'operation': 'artifact', 'task_id': body['task_id'], 'name': body['name']})
        if name in ('inspect', 'cancel'):
            return agent.execute({'operation': name, 'task_id': body['task_id']})
        if name == 'respond':
            response = message('HumanDecisionResponse', {k: body[k] for k in (
                'task_id', 'request_id', 'request_revision', 'request_digest', 'response_id', 'value')})
            return agent.execute({'operation': 'respond', 'task_id': body['task_id'], 'response': response})
        raise ValueError('unknown operation')
    return operation


def main():
    port = int(os.environ.get('SPIKE_SHIM_PORT', '59090'))
    ingress = os.environ.get('SPIKE_INGRESS', 'http://127.0.0.1:58080')
    events = JsonlEvents(os.environ['SPIKE_SHIM_EVENTS'])
    calls = os.environ['SPIKE_SHIM_CALLS']
    operation = build(PersonalAgent(RestateBinding(ingress), events))

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            name = self.path.strip('/')
            size = int(self.headers.get('Content-Length') or 0)
            started = time.time()
            try:
                body = json.loads(self.rfile.read(size) or b'{}')
                result, status = operation(name, body), 200
            except (ValueError, KeyError, TypeError, ControlRejected) as error:
                result, status = {'error': str(error), 'kind': type(error).__name__}, 400
            except OSError as error:
                result, status = {'error': 'Blaine control transport unavailable', 'kind': type(error).__name__}, 502
            with open(calls, 'a') as out:
                out.write(json.dumps({'ts': round(started, 3), 'op': name, 'status': status,
                                      'task_id': (result or {}).get('task_id') if isinstance(result, dict) else None,
                                      'submission': result.get('submission') if isinstance(result, dict) else None,
                                      'ms': round((time.time() - started) * 1000)}) + '\n')
            data = json.dumps(result).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_):
            pass

    print(f'control shim on 127.0.0.1:{port} -> {ingress}', file=sys.stderr, flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Handler).serve_forever()


if __name__ == '__main__':
    main()
