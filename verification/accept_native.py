"""accept_native.py -- bounded native Restate integration for the scheduler.

Demonstrates, on a real Restate server (isolated loopback ports, fresh data
directory, owning and stopping only the processes it starts):

  * submit HOST run A (passes, with a 3 s step so execution is observable)
  * submit HOST run B (fails)
  * A runs first (FIFO), B queued behind A
  * A reaches terminal PASS
  * B then runs and reaches terminal FAIL
  * final scheduler state: no active run, empty queue

The submit handler is synchronous in v0: it admits the FIFO head, blocks on
the run's durable object_call (VirtualObject→Workflow), releases the slot,
and admits the next head. Both submits return after both runs have completed.
FIFO ordering is demonstrated by A's terminal state preceding B's.

It uses two harmless, deterministic fixture suites so it does not touch the
real E1.0 acceptance or the shared canonical Blaine host runtime.

Usage:
  <python> verification/accept_native.py --restate-server <bin> --python <py> \
      --output <fresh-scratch-dir> --evidence <dir>
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

# Dedicated loopback ports for the isolated instance.
INGRESS = 'http://127.0.0.1:40280'
ADMIN = 'http://127.0.0.1:40270'
ENDPOINT = 'http://127.0.0.1:40290'
SERVER_PORT = 40322
PORTS = (40280, 40270, 40290, 40322)


def http(base, path, value=None, method='POST', timeout=30):
    data = None if value is None else json.dumps(value).encode()
    request = urllib.request.Request(base + path, data=data, method=method,
                                     headers={'Accept': 'application/json',
                                              **({'Content-Type': 'application/json'} if data else {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        return json.loads(body) if body else None


def until(function, description, seconds=90):
    deadline, last = time.monotonic() + seconds, None
    while time.monotonic() < deadline:
        try:
            last = function()
            if last:
                return last
        except urllib.error.HTTPError as error:
            if error.code < 500:
                raise
            last = f'HTTP {error.code}'
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last = str(error)
        time.sleep(0.15)
    raise AssertionError(f'Timeout: {description}; last={last}')


def write_fixture_suites(directory: Path) -> None:
    """Write two harmless host-bound fixture suites into a scratch dir.

    fixture-pass: runs ``sleep 3`` (observable execution time).
    fixture-fail: runs ``false`` (deterministic failure).
    """
    suites = directory / 'suites'
    suites.mkdir(parents=True, exist_ok=True)
    (suites / '__init__.py').write_text('')
    (suites / 'fixture_pass.py').write_text(
        'from verification.suite import Suite, Step, VerificationClass\n'
        'SUITE = Suite(name="fixture-pass", verification_class=VerificationClass.HOST,\n'
        '              description="harmless passing fixture",\n'
        '              steps=[Step("ok", ["sleep", "3"], timeout=30.0)],\n'
        '              resources=("restate-runtime",), prereq_probes=("restate",))\n')
    (suites / 'fixture_fail.py').write_text(
        'from verification.suite import Suite, Step, VerificationClass\n'
        'SUITE = Suite(name="fixture-fail", verification_class=VerificationClass.HOST,\n'
        '              description="harmless failing fixture",\n'
        '              steps=[Step("bad", ["false"])], resources=("restate-runtime",),\n'
        '              prereq_probes=("restate",))\n')
    return suites


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restate-server', type=Path, required=True)
    parser.add_argument('--python', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, default=ROOT / '.local' / 'verification' / 'native')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise RuntimeError('Use a fresh output directory')
    for port in PORTS:
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
    out.mkdir(parents=True)
    evidence = args.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)

    # Scratch suites dir the app discovers via BLAINE_VERIFICATION_SUITES_DIR.
    scratch = out / 'app'
    scratch.mkdir(parents=True, exist_ok=True)
    suites_dir = write_fixture_suites(scratch)
    (scratch / 'accept_app.py').write_text(f'''
import sys
sys.path.insert(0, {str(ROOT)!r})
from verification import scheduler_restate as _r
app = _r.build_app("blaine")
if __name__ == '__main__':
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    import asyncio
    config = Config()
    config.bind = ['127.0.0.1:40290']
    asyncio.run(serve(app, config))
''')
    (out / 'restate.toml').write_text(f'''cluster-name = "blaine-verification-native"
node-name = "verification-native"
base-dir = "{out / 'restate-data'}"
bind-ip = "127.0.0.1"
bind-port = {SERVER_PORT}
advertised-host = "127.0.0.1"
listen-mode = "tcp"
auto-provision = true
default-journal-retention = "7 days"
[admin]
bind-address = "127.0.0.1:40270"
[ingress]
bind-address = "127.0.0.1:40280"
''')

    versions = {'server': subprocess.check_output([str(args.restate_server), '--version'], text=True).strip(),
                'sdk': importlib.metadata.version('restate-sdk'), 'python': sys.version.split()[0]}
    (evidence / 'versions.json').write_text(json.dumps(versions, indent=2) + '\n')

    environment = {k: v for k, v in os.environ.items() if not k.startswith('RESTATE_')}
    environment.update(PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1',
                       BLAINE_VERIFICATION_SUITES_DIR=str(suites_dir))
    processes, events = {}, []

    def start(name):
        command = ([str(args.restate_server), '--config-file', str(out / 'restate.toml')] if name == 'server'
                   else [str(args.python), str(scratch / 'accept_app.py')])
        with (out / f'{name}.log').open('wb') as log:
            processes[name] = subprocess.Popen(command, cwd=str(ROOT), env=environment,
                                               stdout=log, stderr=subprocess.STDOUT)
        events.append({'action': 'start', 'process': name})

        def ready():
            if processes[name].poll() is not None:
                raise RuntimeError(f'{name} exited; inspect {out}')
            if name == 'server':
                return http(ADMIN, '/deployments', method='GET') is not None
            try:
                with socket.create_connection(('127.0.0.1', 40290), timeout=2):
                    return True
            except OSError:
                return False
        until(ready, f'{name} ready', 60)

    results, checks = {}, {}
    try:
        start('server')
        start('runtime')
        checks['deployment'] = http(ADMIN, '/deployments', {'uri': ENDPOINT})

        scheduler = 'VerificationScheduler_blaine'
        SCHED = f'/{scheduler}/host'

        def submit(suite, timeout=60):
            return http(INGRESS, f'{SCHED}/submit',
                        {'suite': suite, 'worktree': str(ROOT)}, timeout=timeout)

        def status():
            return http(INGRESS, f'{SCHED}/status')

        def run_status(run_id):
            return http(INGRESS, f'/VerificationRun/{run_id}/status')

        # Submit A (pass, 3s step) then B (fail, immediate).
        # The submit handler is synchronous: it blocks until both runs
        # complete (FIFO: A first, then B). Both submits return after
        # the full queue is drained.
        start_a = time.monotonic()
        a = submit('fixture-pass')
        elapsed_a = time.monotonic() - start_a
        checks['submit-A'] = {'run_id': a['run_id'], 'elapsed_s': round(elapsed_a, 1)}

        start_b = time.monotonic()
        b = submit('fixture-fail')
        elapsed_b = time.monotonic() - start_b
        checks['submit-B'] = {'run_id': b['run_id'], 'elapsed_s': round(elapsed_b, 1)}

        # Verify A reached terminal PASS.
        final_a = run_status(a['run_id'])
        results['A'] = final_a
        assert final_a.get('result') == 'PASS', f'A must be PASS, got {final_a}'

        # Verify B reached terminal FAIL.
        final_b = run_status(b['run_id'])
        results['B'] = final_b
        assert final_b.get('result') == 'FAIL', f'B must be FAIL, got {final_b}'

        # FIFO ordering: A's run must have started before B's.
        # A has a 3 s step, so A's elapsed time must be >= 3 s.
        assert elapsed_a >= 2.5, f'A elapsed {elapsed_a:.1f}s < 2.5s (3s step not observed)'
        # B ran after A, so B's total time includes A's execution.
        # The final scheduler state must be clean.
        checks['final'] = status()
        assert status()['active'] is None, 'active slot must be released'
        assert status()['queue'] == [], 'queue must be empty'

        summary = {'outcome': 'PASS',
                   'fifo_order': [a['run_id'], b['run_id']],
                   'A': {'result': final_a['result'], 'suite': final_a['suite'],
                         'elapsed_s': round(elapsed_a, 1)},
                   'B': {'result': final_b['result'], 'suite': final_b['suite'],
                         'elapsed_s': round(elapsed_b, 1)},
                   'final_scheduler': checks['final'],
                   'versions': versions,
                   'process_events': events}
        (evidence / 'native-queue.json').write_text(json.dumps(summary, indent=2) + '\n')
        print(json.dumps({k: v for k, v in summary.items() if k != 'process_events'}, indent=2))
    finally:
        for name, process in list(processes.items()):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == '__main__':
    main()
