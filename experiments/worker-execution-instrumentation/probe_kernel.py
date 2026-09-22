#!/usr/bin/env python3
"""Live continuation-boundary probe on the Blaine-owned durable loop.

An isolated Restate server, the adopted loopback Qwen deployment and a real OTLP
exporter are used. Nothing here touches the adopted long-lived services: the
probe owns its own ports, state directory and processes.

It establishes four things:

1. Every model continuation is preceded by a synchronous boundary admission.
2. Model and tool telemetry correlate to the Task, run and continuation index.
3. Telemetry leaves through OTLP without the Task depending on the Collector.
4. After SIGKILL, recovery replays an already-admitted boundary decision instead
   of consulting the observer again for that historical boundary.
"""
import argparse, asyncio, hashlib, json, os, runpy, shutil, signal, socket, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode, message
from runtime.kernel.event_sinks import JsonlEventPublisher
from runtime.kernel.execution import Capabilities
from runtime.kernel.instrument import ControlPath, Instrumentation, safe
from runtime.kernel.adapter_profiles import BLAINE_KERNEL_LOOP
from runtime.kernel.workflow import create_workflow

BASE = runpy.run_path(str(ROOT / 'scripts/verify-kernel.py'))
http, until = BASE['http'], BASE['until']
INGRESS, ADMIN, ENDPOINT = 'http://127.0.0.1:41080', 'http://127.0.0.1:41070', 'http://127.0.0.1:41090'
PORTS = (41080, 41070, 41090, 41122)
TASK = 'boundary-live-001'
FIRST, SECOND = 'BOUNDARY-ONE\n', 'BOUNDARY-TWO\n'
MODEL = 'nvidia/Qwen3.8-27B-NVFP4'
COLLECTOR = 'http://127.0.0.1:4318'


def task_spec():
    return message('TaskSpec', {
        'objective': ('Produce two deliverables with exact bytes. Write artifact "first" containing '
                      f'{FIRST!r} and artifact "second" containing {SECOND!r}. Preserve the trailing newline '
                      'and add nothing else.'),
        'completion': [
            {'criterion': 'First exact artifact',
             'evidence': {'artifact': 'first', 'sha256': hashlib.sha256(FIRST.encode()).hexdigest()}},
            {'criterion': 'Second exact artifact',
             'evidence': {'artifact': 'second', 'sha256': hashlib.sha256(SECOND.encode()).hexdigest()}}],
        'capabilities': ['artifact.write'], 'autonomy': {'allowed': ['artifact.write']}})


class RecordingObserver:
    """Deterministic synchronous participant. It never authorizes Worker action.

    Each consultation appends one line to a shared file, so a replayed boundary
    can be distinguished from a recomputed one across process restarts.
    """
    observer_id = 'deterministic-boundary-observer'

    def __init__(self, path):
        self.path = path

    def inspect(self, boundary):
        record = {'pid': os.getpid(), 'index': boundary.index, 'reason': boundary.reason,
                  'tool_invocations': boundary.tool_invocations,
                  'evidence_digest': boundary.evidence_digest, 'at_unix': time.time()}
        with self.path.open('ab', buffering=0) as stream:
            stream.write(encode(record) + b'\n')
            os.fsync(stream.fileno())
        # A cheap deterministic trigger: dense observation stays free of semantics.
        return {'outcome': 'PROCEED', 'label': 'nominal' if boundary.tool_invocations else 'no_evidence_yet',
                'score': 0.0 if boundary.tool_invocations else 1.0}


def application(out):
    import restate
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    from runtime.kernel.model import LocalModelCognition
    from runtime.kernel.telemetry_otel import recorder as build_recorder

    store = ArtifactStore(out / 'artifacts')
    recorder, shutdown = build_recorder(COLLECTOR, service='blaine-boundary-probe',
                                       resource_attributes={'blaine.probe': 'worker-execution-instrumentation'})
    audit = out / 'model-audit.jsonl'

    def record_model(value):
        with audit.open('ab', buffering=0) as stream:
            stream.write(encode({k: v for k, v in value.items() if k != 'decision'}) + b'\n')
    cognition = LocalModelCognition(endpoint='http://127.0.0.1:8000/v1', model=MODEL, audit=record_model)
    control = ControlPath((RecordingObserver(out / 'observer-calls.jsonl'),),
                          policy='PROCEED_ON_ERROR', budget_ms=3000, recorder=safe(recorder))
    instruments = Instrumentation(recorder=safe(recorder), control=control, profile=BLAINE_KERNEL_LOOP)
    capabilities = Capabilities(store, out / 'effects.sqlite', recorder=recorder)

    async def checkpoint(ctx, stage, state):
        # One-shot SIGKILL barrier after the second boundary is already journaled.
        if stage == 'decision' and state['iteration'] == 2 and not (out / 'restarted').exists():
            (out / 'killed-at.json').write_bytes(encode({'stage': stage, 'iteration': 2, 'pid': os.getpid()}))
            await asyncio.Event().wait()

    service = create_workflow(store, cognition, capabilities, checkpoint=checkpoint,
                              event_publisher=JsonlEventPublisher(out / 'events.jsonl'),
                              instrumentation=instruments)
    config = Config()
    config.bind = ['127.0.0.1:41090']
    try:
        asyncio.run(serve(restate.app([service]), config))
    finally:
        control.close()
        shutdown()


def start(out, name, command, environment, processes, ready_port):
    with (out / (name + '.log')).open('wb') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
    processes.append(process)

    def ready():
        if process.poll() is not None:
            raise RuntimeError(name + ' exited')
        if ready_port is None:
            return http(ADMIN, '/deployments') is not None
        try:
            with socket.create_connection(('127.0.0.1', ready_port), timeout=1):
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
    parser.add_argument('--task', default=TASK)
    parser.add_argument('--no-recovery', action='store_true',
                        help='run one clean instrumented Task and flush telemetry on shutdown')
    arguments = parser.parse_args()
    out = arguments.output.resolve()
    task = arguments.task
    if arguments.serve:
        return application(out)
    if out.exists():
        raise SystemExit('A fresh output directory is required')
    for port in PORTS:
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('127.0.0.1', port))
    out.mkdir(parents=True)
    evidence = out / 'evidence'
    evidence.mkdir()
    if arguments.no_recovery:
        (out / 'restarted').touch()  # disables the one-shot SIGKILL barrier
    (out / 'restate.toml').write_text(f'''cluster-name = "blaine-boundary-probe"
node-name = "boundary-probe"
base-dir = "{out / 'restate-data'}"
bind-ip = "127.0.0.1"
bind-port = 41122
advertised-host = "127.0.0.1"
listen-mode = "tcp"
auto-provision = true
default-journal-retention = "1 days"
[admin]
bind-address = "127.0.0.1:41070"
[ingress]
bind-address = "127.0.0.1:41080"
''')
    environment = {k: v for k, v in os.environ.items() if not k.startswith(('RESTATE_', 'OTEL_'))}
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    processes, summary = [], {'status': 'UNVERIFIED'}
    serve_command = [sys.executable, str(Path(__file__).resolve()), '--serve', '--output', str(out)]
    try:
        start(out, 'restate', [str(arguments.restate_server), '--config-file', str(out / 'restate.toml')],
              environment, processes, None)
        runtime = start(out, 'runtime', serve_command, environment, processes, 41090)
        http(ADMIN, '/deployments', {'uri': ENDPOINT})
        http(INGRESS, f'/CognitiveTaskV1/{task}/run/send', task_spec())
        before = []
        if not arguments.no_recovery:
            until(lambda: (out / 'killed-at.json').exists(), 'second boundary journaled', 300)
            before = [json.loads(line) for line in (out / 'observer-calls.jsonl').read_text().splitlines()]
            runtime.kill()
            runtime.wait(timeout=10)
            (out / 'restarted').touch()
            start(out, 'replacement', serve_command, environment, processes, 41090)

        def finished():
            state = http(INGRESS, f'/CognitiveTaskV1/{task}/status', method='POST')['payload']
            return state if state.get('result_ref') else None
        state = until(finished, 'task settled', 600)
        after = [json.loads(line) for line in (out / 'observer-calls.jsonl').read_text().splitlines()]
        result = http(INGRESS, f'/restate/workflow/CognitiveTaskV1/{task}/attach')
        journal = http(ADMIN, '/query', {'query': "SELECT name FROM sys_journal WHERE id IN "
                                         f"(SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/{task}/run') "
                                         "ORDER BY index"})
        rows = journal.get('rows') if isinstance(journal, dict) else journal
        names = []
        for row in rows or []:
            value = row.get('name') if isinstance(row, dict) else (row[0] if row else None)
            if isinstance(value, str):
                names.append(value)
        boundaries = sorted({row['index'] for row in after})
        replayed = [index for index in sorted({row['index'] for row in before})
                    if len([r for r in after if r['index'] == index]) == 1]
        summary = {
            'status': 'EXECUTED', 'task_id': task,
            'recovery_exercised': not arguments.no_recovery, 'model': MODEL, 'collector': COLLECTOR,
            'lifecycle': state['lifecycle'], 'iterations': state['revision'],
            'artifacts': sorted(state['artifacts']),
            'boundaries_admitted': boundaries,
            'observer_consultations': len(after),
            'observer_consultations_before_kill': len(before),
            'distinct_pids_consulting': sorted({row['pid'] for row in after}),
            'historical_boundaries_not_recomputed': replayed,
            'recomputed_boundaries': [index for index in sorted({row['index'] for row in before})
                                      if len([r for r in after if r['index'] == index]) > 1],
            'journal_continuation_steps': [name for name in names if 'continuation' in str(name)],
            'recovery_point': ('SIGKILL after the second boundary admission was journaled'
                               if not arguments.no_recovery else 'none; clean shutdown flush'),
            'capability_profile': BLAINE_KERNEL_LOOP.summary(),
            'result_outcome': result['payload']['outcome'] if result else None,
            'concerns': result['payload']['concerns'] if result else None,
        }
    except Exception as error:
        summary = {'status': 'FAILED', 'error_type': type(error).__name__, 'error': str(error)[:300]}
        raise
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        (evidence / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
        for name in ('observer-calls.jsonl', 'model-audit.jsonl', 'events.jsonl', 'killed-at.json'):
            if (out / name).exists():
                shutil.copyfile(out / name, evidence / name)
        print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
