#!/usr/bin/env python3
"""Run the complete local acceptance test in one process namespace."""
import json
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import dev

EVIDENCE = ROOT / '.local/evidence'


def run(script, output, *args):
    with (EVIDENCE / output).open('w') as log:
        subprocess.run([sys.executable, str(ROOT / script), *args], cwd=ROOT,
                       stdout=log, stderr=subprocess.STDOUT, check=True, timeout=120)


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    # Do not tear down a user's existing dev environment.
    if any(dev.owned(name) for name in ('runtime', 'restate')):
        raise RuntimeError('Run dev-down first; this acceptance harness needs to own its startup')
    try:
        run('scripts/dev.py', '002-dev-up.json', 'up')
        run('scripts/dev.py', '002-dev-up-again.json', 'up')
        run('scripts/smoke-acp.py', '002-smoke.log')
        summary = json.loads((EVIDENCE / '002-acp/summary.json').read_text())
        run('scripts/dev.py', '002-dev-down.log', 'down')
        for port in dev.PORTS:
            with socket.socket() as sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('127.0.0.1', port))
        # Reuse persisted data/deployment and retrieve the completed task.
        run('scripts/dev.py', '002-restart.json', 'up')
        from runtime.acp_agent import request
        result = request('/TaskWorkflow/' + summary['task_id'] + '/status')
        assert result == summary['result'], result
        (EVIDENCE / '002-after-service-restart.json').write_text(json.dumps(result, indent=2))
        run('scripts/dev.py', '002-doctor.json', 'doctor')
    finally:
        run('scripts/dev.py', '002-final-down.log', 'down')
    for port in dev.PORTS:
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
    (EVIDENCE / '002-lifecycle.json').write_text(json.dumps({
        'startup': 'PASS', 'idempotent_up': 'PASS', 'service_restart_result': 'PASS',
        'owned_listener_cleanup': 'PASS'}, indent=2))
    print('PASS: ACP session independence, human signal, completion, restart retrieval and cleanup')


if __name__ == '__main__':
    sys.path.insert(0, str(ROOT))
    main()
