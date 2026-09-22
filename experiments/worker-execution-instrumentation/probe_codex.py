#!/usr/bin/env python3
"""Live Codex app-server boundary probe, served by local inference only.

The installed Codex CLI drives its own agent loop against the adopted loopback
Qwen deployment through a custom OpenAI-compatible provider, so this probe makes
no paid cloud inference call and consumes no frontier dispatch grant. It records
the stdio protocol conversation, normalizes it through the observation adapter,
and retains bounded metadata only: no command text, model text or reasoning.
"""
import argparse, json, os, queue, subprocess, sys, threading, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from codex_appserver import CAPABILITIES, observe  # noqa: E402

ENDPOINT = 'http://127.0.0.1:8000/v1'
MODEL = 'nvidia/Qwen3.8-27B-NVFP4'
MARKERS = {'alpha.txt': 'marker-one\n', 'beta.txt': 'marker-two\n'}


def overrides():
    # A fixed local provider. Nothing here is selected by a model or a Task.
    return ['-c', 'model_providers.blainelocal.name="Blaine local serving"',
            '-c', f'model_providers.blainelocal.base_url="{ENDPOINT}"',
            '-c', 'model_providers.blainelocal.wire_api="responses"',
            '-c', 'model_providers.blainelocal.env_key="BLAINE_LOCAL_KEY"',
            '-c', 'model_provider="blainelocal"', '-c', f'model="{MODEL}"',
            '-c', 'model_reasoning_effort="low"']


class AppServer:
    """Minimal stdio JSON-RPC client. Blaine does not own the Codex lifecycle."""

    def __init__(self, home, log):
        self.log = log.open('w')
        self.process = subprocess.Popen(['codex', 'app-server', *overrides()],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
            env={'PATH': os.environ['PATH'], 'HOME': os.environ['HOME'], 'LANG': 'C.UTF-8',
                 'CODEX_HOME': str(home), 'BLAINE_LOCAL_KEY': 'EMPTY'})
        self.inbox, self.records, self.next, self.t0 = queue.Queue(), [], 1, time.monotonic()
        self.on_request = None
        for stream, tag in ((self.process.stdout, 'in'), (self.process.stderr, 'err')):
            threading.Thread(target=self._pump, args=(stream, tag), daemon=True).start()

    def _pump(self, stream, tag):
        for line in stream:
            if tag == 'err':
                self.log.write('STDERR ' + line)
                continue
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                self.log.write('UNPARSED\n')
                continue
            message['_t_ms'] = round((time.monotonic() - self.t0) * 1000, 1)
            message['_dir'] = 'in'
            self.records.append(message)
            self.inbox.put(message)

    def send(self, message):
        message['_t_ms'] = round((time.monotonic() - self.t0) * 1000, 1)
        message['_dir'] = 'out'
        self.records.append(dict(message))
        self.process.stdin.write(json.dumps({k: v for k, v in message.items()
                                             if k not in ('_t_ms', '_dir')}) + '\n')
        self.process.stdin.flush()

    def call(self, method, params, timeout=180):
        identity = self.next
        self.next += 1
        self.send({'jsonrpc': '2.0', 'id': identity, 'method': method, 'params': params})
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                message = self.inbox.get(timeout=1)
            except queue.Empty:
                continue
            if message.get('id') == identity and ('result' in message or 'error' in message):
                return message
            self._dispatch(message)
        raise TimeoutError(method)

    def start(self, method, params):
        identity = self.next
        self.next += 1
        self.send({'jsonrpc': '2.0', 'id': identity, 'method': method, 'params': params})
        return identity

    def notify(self, method, params):
        self.send({'jsonrpc': '2.0', 'method': method, 'params': params})

    def _dispatch(self, message):
        if 'method' in message and 'id' in message and self.on_request:
            self.on_request(self, message)

    def until(self, predicate, timeout=240, observer=None):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                message = self.inbox.get(timeout=1)
            except queue.Empty:
                continue
            self._dispatch(message)
            if observer:
                observer(message)
            if predicate(message):
                return message
        raise TimeoutError('stream')

    def stop(self):
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
        self.log.close()


def session(out, name, *, approval='never', delay=None):
    server = AppServer(out / 'codex-home', out / (name + '.log'))
    timings = []

    def answer(srv, message):
        timings.append({'received_at_ms': message['_t_ms'], 'method': message.get('method')})
        if delay:
            time.sleep(delay)
        srv.send({'jsonrpc': '2.0', 'id': message['id'], 'result': {'decision': 'accept'}})
        timings[-1]['answered_after_ms'] = round(delay * 1000) if delay else 0
    server.on_request = answer
    server.call('initialize', {'clientInfo': {'name': 'blaine-boundary-probe', 'version': '1'}})
    server.notify('initialized', {})
    started = server.call('thread/start', {'cwd': str(out / 'work'), 'sandbox': 'read-only',
                                           'approvalPolicy': approval, 'ephemeral': True})
    return server, started['result']['thread']['id'], timings


def case_boundaries(out):
    """Two tool calls, so several model continuations occur inside one turn."""
    server, thread, _ = session(out, 'boundaries')
    server.start('turn/start', {'threadId': thread, 'input': [{'type': 'text', 'text':
        'Use the shell tool. Run: cat alpha.txt . Then in a separate command run: cat beta.txt . '
        'Then reply with both file contents separated by a comma and nothing else.'}]})
    server.until(lambda m: m.get('method') == 'turn/completed')
    records = list(server.records)
    server.stop()
    return records, {}


def case_steer(out):
    """Steer while a tool runs, then observe which continuation consumes it."""
    server, thread, _ = session(out, 'steer')
    state = {'turn': None, 'sent': False}
    server.start('turn/start', {'threadId': thread, 'input': [{'type': 'text', 'text':
        'Use the shell tool exactly once to run: sleep 6; cat alpha.txt . '
        'Then reply with the file contents and nothing else.'}]})

    def watch(message):
        if message.get('method') == 'turn/started':
            state['turn'] = (message['params'].get('turn') or {}).get('id')
        item = (message.get('params') or {}).get('item') or {}
        if (message.get('method') == 'item/started' and item.get('type') == 'commandExecution'
                and not state['sent']):
            state['sent'] = True
            threading.Thread(target=lambda: server.call('turn/steer', {
                'threadId': thread, 'expectedTurnId': state['turn'],
                'input': [{'type': 'text', 'text': 'Additional instruction: append the word ADDENDUM.'}]},
                timeout=60), daemon=True).start()
    server.until(lambda m: m.get('method') == 'turn/completed', observer=watch)
    time.sleep(0.5)
    records = list(server.records)
    server.stop()
    return records, {}


def case_interrupt(out):
    """Interrupt active execution and observe the unterminated tool item."""
    server, thread, _ = session(out, 'interrupt')
    state = {'turn': None, 'sent': False}
    server.start('turn/start', {'threadId': thread, 'input': [{'type': 'text', 'text':
        'Use the shell tool exactly once to run: sleep 30; cat alpha.txt . Then reply with the contents.'}]})

    def watch(message):
        if message.get('method') == 'turn/started':
            state['turn'] = (message['params'].get('turn') or {}).get('id')
        item = (message.get('params') or {}).get('item') or {}
        if (message.get('method') == 'item/started' and item.get('type') == 'commandExecution'
                and not state['sent']):
            state['sent'] = True
            threading.Thread(target=lambda: (time.sleep(1.5), server.call('turn/interrupt', {
                'threadId': thread, 'turnId': state['turn']}, timeout=60)), daemon=True).start()
    server.until(lambda m: m.get('method') == 'turn/completed', observer=watch)
    time.sleep(0.5)
    records = list(server.records)
    server.stop()
    return records, {}


def case_approval(out):
    """Hold the blocking approval callback and measure that Codex waits."""
    server, thread, timings = session(out, 'approval', approval='untrusted', delay=3.0)
    server.start('turn/start', {'threadId': thread, 'input': [{'type': 'text', 'text':
        'Use the shell tool exactly once to run: cat alpha.txt . Then reply with the contents.'}]})
    server.until(lambda m: m.get('method') == 'turn/completed')
    records = list(server.records)
    server.stop()
    return records, {'client_callback_timings': timings}


CASES = {'boundaries': case_boundaries, 'steer': case_steer,
         'interrupt': case_interrupt, 'approval': case_approval}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', choices=sorted(CASES))
    arguments = parser.parse_args()
    out = arguments.output.resolve()
    (out / 'work').mkdir(parents=True, exist_ok=True)
    (out / 'codex-home').mkdir(parents=True, exist_ok=True)
    for name, content in MARKERS.items():
        (out / 'work' / name).write_text(content)
    evidence = out / 'evidence'
    evidence.mkdir(exist_ok=True)
    summary = {'version': 1, 'protocol': CAPABILITIES.worker_family, 'adapter_id': CAPABILITIES.adapter_id,
               'inference': 'local loopback serving only; zero paid cloud inference',
               'model': MODEL, 'endpoint': ENDPOINT, 'evidence_class': 'live', 'cases': {}}
    for name in (arguments.case or sorted(CASES)):
        began = time.time()
        try:
            records, extra = CASES[name](out)
            observation = observe(records).summary()
            summary['cases'][name] = {'outcome': 'OBSERVED', 'runtime_s': round(time.time() - began, 1),
                                      'record_count': len(records), **extra,
                                      'boundaries': len(observation['boundaries']),
                                      'model_invocations': len(observation['model_invocations']),
                                      'tool_invocations': len(observation['tool_invocations']),
                                      'turn_status': observation['turn_status']}
            (evidence / (name + '-observation.json')).write_text(json.dumps(observation, indent=1) + '\n')
        except Exception as error:  # a failed case is recorded, never hidden
            summary['cases'][name] = {'outcome': 'FAILED', 'error_type': type(error).__name__,
                                      'runtime_s': round(time.time() - began, 1)}
        print(name, json.dumps(summary['cases'][name])[:400], flush=True)
    (evidence / 'capabilities.json').write_text(json.dumps(CAPABILITIES.summary(), indent=1) + '\n')
    (evidence / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
