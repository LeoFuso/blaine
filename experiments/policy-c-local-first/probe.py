#!/usr/bin/env python3
"""Live Policy C probe: real Restate, real local Qwen, one bounded Task.

Deterministic fixtures already prove the mechanics. This exists only to show the
evidence path holding against the actual runtime: a Task starts locally under an
external grant, its routing record survives in authoritative storage, and the
deterministic report reads it back. It owns its own ports, state and processes,
and never touches the adopted services. No paid provider is involved.
"""
import argparse, json, os, runpy, socket, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import message
from runtime.kernel.routing import LOCAL_BINDING, POLICY

BASE = runpy.run_path(str(ROOT / 'scripts/verify-kernel.py'))
http, until = BASE['http'], BASE['until']
INGRESS, ADMIN, ENDPOINT = 'http://127.0.0.1:41180', 'http://127.0.0.1:41170', 'http://127.0.0.1:41190'
PORTS = (41180, 41170, 41190, 41222)
MODEL = 'nvidia/Qwen3.8-27B-NVFP4'
ANSWER = 'POLICY-C-LOCAL\n'
TASK = 'policy-c-local-001'


def task_request():
    import hashlib
    spec = message('TaskSpec', {
        'objective': f'Write artifact "answer" containing exactly {ANSWER!r}. '
                     'Preserve the trailing newline and add nothing else.',
        'completion': [{'criterion': 'Exact artifact',
                        'evidence': {'artifact': 'answer',
                                     'sha256': hashlib.sha256(ANSWER.encode()).hexdigest()}}],
        'capabilities': ['artifact.write'], 'autonomy': {'allowed': ['artifact.write']}})
    # The grant is envelope data supplied by trusted code, never by the Task.
    return message('TaskRequest', {'task_spec': spec, 'grant': {
        'capabilities': ['artifact.write'], 'escalation_binding': None},
        'initial_action': {'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write',
                           'input': {'name': 'answer', 'content': ANSWER}}})


def application(out):
    import asyncio, restate
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    from runtime.kernel.event_sinks import JsonlEventPublisher
    from runtime.kernel.execution import Capabilities
    from runtime.kernel.model import LocalModelCognition
    from runtime.kernel.workflow import create_workflow
    store = ArtifactStore(out / 'artifacts')
    service = create_workflow(store, LocalModelCognition(endpoint='http://127.0.0.1:8000/v1', model=MODEL),
                              Capabilities(store, out / 'effects.sqlite'),
                              event_publisher=JsonlEventPublisher(out / 'events.jsonl'))
    config = Config(); config.bind = ['127.0.0.1:41190']
    asyncio.run(serve(restate.app([service]), config))


def start(out, name, command, environment, processes, port):
    with (out / (name + '.log')).open('wb') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
    processes.append(process)

    def ready():
        if process.poll() is not None:
            raise RuntimeError(name + ' exited')
        if port is None:
            return http(ADMIN, '/deployments') is not None
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=1):
                return True
        except OSError:
            return False
    until(ready, name + ' ready', 60)
    return process


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--restate-server', type=Path,
                        default=Path.home() / '.local/share/blaine/runtime/bin/restate-server')
    parser.add_argument('--serve', action='store_true')
    arguments = parser.parse_args()
    out = arguments.output.resolve()
    if arguments.serve:
        return application(out)
    if out.exists():
        raise SystemExit('A fresh output directory is required')
    for port in PORTS:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('127.0.0.1', port))
    out.mkdir(parents=True)
    evidence = out / 'evidence'; evidence.mkdir()
    (out / 'restate.toml').write_text(f'''cluster-name = "blaine-policy-c"
node-name = "policy-c"
base-dir = "{out / 'restate-data'}"
bind-ip = "127.0.0.1"
bind-port = 41222
advertised-host = "127.0.0.1"
listen-mode = "tcp"
auto-provision = true
default-journal-retention = "1 days"
[admin]
bind-address = "127.0.0.1:41170"
[ingress]
bind-address = "127.0.0.1:41180"
''')
    environment = {k: v for k, v in os.environ.items() if not k.startswith(('RESTATE_', 'OTEL_'))}
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    processes, summary = [], {'status': 'UNVERIFIED'}
    try:
        start(out, 'restate', [str(arguments.restate_server), '--config-file', str(out / 'restate.toml')],
              environment, processes, None)
        start(out, 'runtime', [sys.executable, str(Path(__file__).resolve()), '--serve', '--output', str(out)],
              environment, processes, 41190)
        http(ADMIN, '/deployments', {'uri': ENDPOINT})
        began = time.monotonic()
        http(INGRESS, f'/CognitiveTaskV1/{TASK}/run/send', task_request())

        def settled():
            state = http(INGRESS, f'/CognitiveTaskV1/{TASK}/status', method='POST')['payload']
            return state if state.get('result_ref') else None
        state = until(settled, 'task settled', 300)
        store = ArtifactStore(out / 'artifacts')
        record = store.read_json(TASK, state['routing_ref'])['payload']
        events = [json.loads(line) for line in (out / 'events.jsonl').read_text().splitlines()]
        summary = {
            'status': 'EXECUTED', 'task_id': TASK, 'model': MODEL,
            'runtime_s': round(time.monotonic() - began, 1),
            'lifecycle': state['lifecycle'], 'routing_record': record,
            'routing_events': [e['event_type'] for e in events
                               if e['producer']['component'] == 'blaine.kernel.routing'],
            'paid_provider_calls': 0,
        }
        summary['checks'] = {
            'policy_recorded': record['policy'] == POLICY,
            'started_local': record['started_local'] and record['initial_binding'] == LOCAL_BINDING,
            'externally_bounded': record['externally_bounded'],
            'effective_capabilities': record['effective_capabilities'] == ['artifact.write'],
            'never_escalated': not record['escalated'],
            'final_binding_local': record['final_binding'] == LOCAL_BINDING,
            'evidence_discoverable_from_events': 'artifact.produced' in summary['routing_events'],
        }
        summary['outcome'] = 'PASS' if all(summary['checks'].values()) and state['lifecycle'] == 'COMPLETED' else 'FAIL'
    except Exception as error:
        summary = {'status': 'FAILED', 'error_type': type(error).__name__, 'error': str(error)[:200]}
        raise
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
        (evidence / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
        for name in ('events.jsonl',):
            if (out / name).exists():
                (evidence / name).write_text((out / name).read_text())
        print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
