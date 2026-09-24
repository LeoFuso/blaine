#!/usr/bin/env python3
"""One bounded CP.1 native Restate + local Goose smoke. Owns only fixture processes."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode


def http(port, path, data=None, timeout=5):
    request = urllib.request.Request(f'http://127.0.0.1:{port}' + path,
        data=None if data is None else encode(data), headers={'Content-Type': 'application/json'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout) as response:
        return json.load(response)


def ready(fn, seconds=30):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = fn()
            if value: return value
        except (OSError, ValueError):
            pass
        time.sleep(.1)
    raise RuntimeError('Bounded fixture readiness deadline exceeded')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--restate-server', type=Path, required=True)
    parser.add_argument('--goose', type=Path, required=True)
    parser.add_argument('--model', required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'runtime').mkdir()
    ports = []
    sockets = []
    for _ in range(4):
        sock = socket.socket()
        sock.bind(('127.0.0.1', 0))
        ports.append(sock.getsockname()[1])
        sockets.append(sock)
    ingress, admin, endpoint, internal = ports
    (out / 'config.json').write_bytes(encode({'goose': str(args.goose), 'model': args.model,
                                            'endpoint_port': endpoint}))
    (out / 'restate.toml').write_text(f'''cluster-name = "blaine-cp1-probe"
node-name = "cp1-probe"
base-dir = "{out / 'restate-data'}"
bind-ip = "127.0.0.1"
bind-port = {internal}
advertised-host = "127.0.0.1"
listen-mode = "tcp"
auto-provision = true
[admin]
bind-address = "127.0.0.1:{admin}"
[ingress]
bind-address = "127.0.0.1:{ingress}"
''')
    env = {k: v for k, v in os.environ.items() if not k.startswith('RESTATE_')}
    env.update(CP1_PROBE_DIR=str(out), PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1',
               XDG_STATE_HOME=str(out / 'state'))
    versions = {'server': subprocess.check_output([str(args.restate_server), '--version'], text=True).strip(),
        'sdk': importlib.metadata.version('restate-sdk'),
        'goose': subprocess.check_output([str(args.goose), '--version'], env=env, text=True).strip(),
        'model': args.model}
    for sock in sockets: sock.close()
    processes, logs = [], []
    try:
        for name, command in [('server', [str(args.restate_server), '--config-file', str(out / 'restate.toml')]),
                              ('app', [sys.executable, str(ROOT / 'experiments/context-plane-cp1/probe_app.py')])]:
            log = (out / (name + '.log')).open('wb')
            logs.append(log)
            processes.append(subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT))
        ready(lambda: http(admin, '/deployments') is not None)
        def app_ready():
            with socket.create_connection(('127.0.0.1', endpoint), timeout=1): return True
        ready(app_ready)
        deployment = http(admin, '/deployments', {'uri': f'http://127.0.0.1:{endpoint}'})
        (out / 'deployment.json').write_bytes(encode(deployment))
        spec = json.loads((out / 'spec.json').read_text())
        # Exactly one Task, at most two worker dispatches; Goose itself caps each at 60s.
        result = http(ingress, '/CognitiveTaskV1/control/run', spec, timeout=155)
        (out / 'result.json').write_bytes(encode(result))
        def rows(name):
            return [json.loads(line) for line in (out / (name + '.jsonl')).read_text().splitlines()]
        workers, cognition, capabilities = rows('workers'), rows('cognition'), rows('capabilities')
        store = ArtifactStore(out / 'runtime' / 'artifacts')
        verification = store.read_json('control', result['payload']['completion_ref'])
        contract_ref = verification['payload']['contract_ref']
        contract = store.read_json('control', contract_ref)
        (out / 'contract.json').write_bytes(encode(contract))
        projections = [json.loads(w['packet']['payload']['context'][0]['content']) for w in workers]
        delta_ref = capabilities[1]['payload']['output']['delta_ref']
        delta = store.read_json('control', delta_ref)
        (out / 'delta.json').write_bytes(encode(delta))
        (out / 'verification.json').write_bytes(encode(verification))
        checks = {
            'completed': result['payload']['outcome'] == 'COMPLETED',
            'two_worker_dispatches': len(workers) == 2,
            'recorded_coordinator_three_turns': len(cognition) == 3,
            'one_delta': sum(c['payload']['output'].get('delta_ref') is not None for c in capabilities) == 1,
            'initial_exact_source': 'DRAFT' in encode(workers[0]['packet']).decode(),
            'fresh_active_source': 'GOOD' in encode(workers[1]['packet']).decode() and 'DRAFT' not in encode(workers[1]['packet']).decode(),
            'initial_observation': store.read('control', result['payload']['artifacts']['draft']) == b'DRAFT',
            'independent_exact_evidence': verification['payload']['outcome'] == 'satisfied' and store.read('control', result['payload']['artifacts']['answer']) == b'GOOD',
            'current_contract_projection': all(p['contract_ref'] == contract_ref and p['completion'] == {
                'revision': contract['payload']['revision'], 'criteria': contract['payload']['criteria']}
                for p in projections),
            'completion_legality': verification['version'] == 2 and verification['payload']['legality']['legal'],
            'worker_budget': all(w['packet_bytes'] <= 4096 for w in workers),
            'cognition_budget': all(c['packet_bytes'] <= 16384 for c in cognition),
            'delta_budget': len(encode(delta)) <= 4096,
            'capability_budget': all(len(encode(c)) <= 4096 for c in capabilities),
        }
        forbidden = ('SIBLING_SECRET', 'DESCENDANT_SECRET', 'UNRELATED_SECRET', 'FOREIGN_SECRET', 'POLICY_SECRET', 'security_domains')
        public = b''.join((out / name).read_bytes() for name in (
            'workers.jsonl', 'cognition.jsonl', 'capabilities.jsonl', 'verifier.jsonl', 'result.json', 'app.log'))
        checks['negative_scan'] = not any(value.encode() in public for value in forbidden)
        summary = {'status': 'PASS' if all(checks.values()) else 'FAIL', 'checks': checks, 'versions': versions,
            'worker_bytes': [w['packet_bytes'] for w in workers], 'delta_bytes': len(encode(delta)),
            'cognition_bytes': [c['packet_bytes'] for c in cognition],
            'capability_bytes': [len(encode(c)) for c in capabilities],
            'contract_revisions': [p['completion']['revision'] for p in projections],
            'cognition': 'recorded decisions; not a live cognition/utility claim',
            'memory': 'qualified in-process fixture; live MIRIX remains disabled',
            'recovery': 'native completion only; kill/resume and concurrent revocation remain CP.8'}
        summary['source_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in [*sorted((ROOT / 'runtime/kernel').glob('*.py')),
                      ROOT / 'experiments/context-plane-cp1/probe_app.py',
                      ROOT / 'tests/test_kernel_context_plane.py', Path(__file__).resolve()]}
        (out / 'summary.json').write_bytes(encode(summary) + b'\n')
        print(json.dumps({k: v for k, v in summary.items() if k != 'source_sha256'}, indent=2))
        if not all(checks.values()): raise SystemExit(1)
    finally:
        for process in reversed(processes):
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for log in logs: log.close()


if __name__ == '__main__': main()
