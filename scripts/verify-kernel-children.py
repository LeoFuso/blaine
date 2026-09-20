#!/usr/bin/env python3
"""Increment 2: one joined child, bounded result, parent-independent completion."""
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import runpy
import shutil
import socket
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.kernel.contracts import child_task_id, encode, message, validate_result
from runtime.kernel.artifacts import ArtifactStore
BASE = runpy.run_path(str(ROOT / 'scripts/verify-kernel.py'))
http, until = BASE['http'], BASE['until']
ADMIN, INGRESS, ENDPOINT = BASE['ADMIN'], BASE['INGRESS'], BASE['ENDPOINT']
PARENT = 'parent'
CHILD = child_task_id(PARENT, 'parent/1')
SECRET = 'CHILD_PRIVATE_WORK_SENTINEL'


def spec(objective, content, children=0):
    return message('TaskSpec', {'objective': objective,
        'completion': [{'criterion': 'Exact accepted answer', 'evidence': {'artifact': 'answer', 'sha256': hashlib.sha256(content.encode()).hexdigest()}}],
        'capabilities': ['artifact.write', 'fixture.effect'],
        'autonomy': {'allowed': ['artifact.write', 'fixture.effect'], 'child_tasks': children}})


def write(content):
    return {'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write', 'input': {'name': 'answer', 'content': content}}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restate-server', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise RuntimeError('Output must be a fresh directory')
    for port in (38080, 39070, 39080, 35122):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
    out.mkdir(parents=True)
    evidence = out / 'evidence'
    evidence.mkdir()
    def save(name, data):
        (evidence / (name + '.json')).write_bytes(encode(data) + b'\n')
    child_spec, parent_spec = spec('Produce independent child answer', 'child exact answer'), spec('Produce independent parent answer', 'parent exact answer', 1)
    fixtures = {
        PARENT: {'actions': [{'type': 'SPAWN_TASK', 'task_spec': child_spec}, {'type': 'COMPLETE'}, write('parent exact answer'), {'type': 'COMPLETE'}]},
        CHILD: {'actions': [{'type': 'INVOKE_CAPABILITY', 'capability': 'fixture.effect', 'input': {'value': SECRET + str(i)}} for i in range(2)] +
                           [write('child exact answer'), {'type': 'WAIT', 'wait_id': 'child-ready', 'input_type': 'text'}, {'type': 'COMPLETE'}]},
    }
    save('specs', {'parent': parent_spec, 'child': child_spec})
    (out / 'fixtures.json').write_bytes(encode(fixtures))
    (out / 'restate.toml').write_text(f'''cluster-name = "blaine-child-probe"
node-name = "child-probe"
base-dir = "{out / 'restate-data'}"
bind-ip = "127.0.0.1"
bind-port = 35122
advertised-host = "127.0.0.1"
listen-mode = "tcp"
auto-provision = true
default-journal-retention = "7 days"
[admin]
bind-address = "127.0.0.1:39070"
[ingress]
bind-address = "127.0.0.1:38080"
''')
    env = {k: v for k, v in os.environ.items() if not k.startswith('RESTATE_')}
    env.update(KERNEL_PROBE_DIR=str(out), PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
    versions = {'server': subprocess.check_output([str(args.restate_server), '--version'], text=True).strip(),
                'sdk': importlib.metadata.version('restate-sdk')}
    assert '1.7.9' in versions['server'] and versions['sdk'] == '1.0.5'
    save('versions', versions)
    processes, events, generations = {}, [], Counter()
    def start(name):
        generations[name] += 1
        command = ([str(args.restate_server), '--config-file', str(out / 'restate.toml')] if name == 'server' else
                   [sys.executable, str(ROOT / 'experiments/kernel-increment-1/probe_app.py')])
        with (out / f'{name}-{generations[name]}.txt').open('wb') as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        processes[name] = process
        events.append({'event': 'start', 'process': name, 'pid': process.pid})
        def ready():
            if process.poll() is not None:
                raise RuntimeError(f'{name} exited; inspect {out}')
            if name == 'server':
                return http(ADMIN, '/deployments') is not None
            try:
                with socket.create_connection(('127.0.0.1', 39080), timeout=2):
                    return True
            except OSError:
                return False
        until(ready, name + ' readiness', 40)
    def kill(name):
        process = processes.pop(name)
        process.kill()
        assert process.wait(timeout=10) == -9
        events.append({'event': 'SIGKILL', 'process': name, 'pid': process.pid, 'exit_code': -9})
    def call(task, handler, body=None):
        return http(INGRESS, f'/CognitiveTaskV1/{task}/{handler}', body, method='POST')
    def status(task):
        return call(task, 'status')['payload']
    def journal(task):
        return http(ADMIN, '/query', {'query': f"SELECT * FROM sys_journal WHERE id IN (SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/{task}/run') ORDER BY index"})
    try:
        start('server')
        start('runtime')
        save('deployment', http(ADMIN, '/deployments', {'uri': ENDPOINT}))
        save('submission', call(PARENT, 'run/send', parent_spec))
        waiting = until(lambda: (s if (s := status(CHILD)).get('lifecycle') == 'WAITING' else None), 'child waiting')
        before = {'parent': status(PARENT), 'child': waiting}
        assert before['parent']['wait']['child_id'] == CHILD
        assert before['parent']['lifecycle'] == 'WAITING'
        save('before-crash', before)
        before_journals = {key: journal(task) for key, task in [('parent', PARENT), ('child', CHILD)]}
        save('journals-before', before_journals)
        # External text cannot resolve a parent that awaits a typed TaskResult.
        try:
            call(PARENT, 'submit_input', message('ExternalInput', {'wait_id': 'child-ready', 'task_revision': 0, 'input_type': 'text', 'value': 'bypass'}))
            raise AssertionError('Parent child wait accepted text')
        except BASE['urllib'].error.HTTPError as error:
            assert error.code == 409
            save('parent-input-denied', {'status': error.code, 'body': json.loads(error.read())})
        kill('runtime')
        start('runtime')
        kill('server')
        start('server')
        after = {'parent': status(PARENT), 'child': status(CHILD)}
        assert before == after
        save('after-restart', after)
        wait = waiting['wait']
        save('input-receipt', call(CHILD, 'submit_input', message('ExternalInput', {
            'wait_id': wait['wait_id'], 'task_revision': wait['task_revision'], 'input_type': 'text', 'value': 'finish child'})))
        final = until(lambda: (s if (s := status(PARENT)).get('result_ref') else None), 'parent completion')
        assert final['lifecycle'] == 'COMPLETED'
        results = {key: http(INGRESS, f'/restate/workflow/CognitiveTaskV1/{task}/attach') for key, task in [('parent', PARENT), ('child', CHILD)]}
        for key, task in [('parent', PARENT), ('child', CHILD)]:
            validate_result(results[key], task)
        save('results', results)
        save('final-state', {'parent': final, 'child': status(CHILD)})
        after_journals = {key: journal(task) for key, task in [('parent', PARENT), ('child', CHILD)]}
        save('journals-after', after_journals)
        for key in before_journals:
            for old, new in zip(before_journals[key]['rows'], after_journals[key]['rows']):
                assert all(old[field] == new[field] for field in ('id', 'index', 'raw', 'appended_at'))
        invocations = http(ADMIN, '/query', {'query': "SELECT id, target, status FROM sys_invocation WHERE target LIKE '%/run'"})
        save('invocations', invocations)
        assert len(invocations['rows']) == 2, invocations
        assert len(final['children']) == 1 and final['remaining_children'] == 0
        audit = [json.loads(line) for line in (out / 'cognition.jsonl').read_text().splitlines()]
        counts = Counter(row['packet']['payload']['task_id'] for row in audit)
        assert counts == {PARENT: 4, CHILD: 5}, counts
        turns = {(row['packet']['payload']['task_id'], row['packet']['payload']['iteration']): row['packet'] for row in audit}
        assert turns[PARENT, 2]['payload']['observations'] == [results['child']]
        assert turns[PARENT, 3]['payload']['observations'][0]['payload']['outcome'] == 'unsatisfied'
        assert turns[CHILD, 1]['payload']['observations'] == []
        assert turns[CHILD, 1]['payload']['objective'] != turns[PARENT, 1]['payload']['objective']
        assert not any(SECRET in json.dumps(row['packet']) for row in audit if row['packet']['payload']['task_id'] == PARENT)
        store = ArtifactStore(out / 'artifacts')
        assert store.read_json(PARENT, final['children'][CHILD]['result_ref']) == results['child']
        for task, state in [('parent', final), (CHILD, status(CHILD))]:
            assert store.read_json(task, state['completion_ref'])['payload']['outcome'] == 'satisfied'
        for path in (out / 'artifacts').glob('*/*'):
            assert hashlib.sha256(path.read_bytes()).hexdigest() == path.name
        with sqlite3.connect(out / 'fixture.sqlite') as db:
            effects = [json.loads(row[0]) for row in db.execute('SELECT receipt FROM effects')]
        assert len(effects) == 2
        save('effects', effects)
        child_bytes = len(encode(results['child']))
        child_context = sum(len(encode(row['packet'])) for row in audit if row['packet']['payload']['task_id'] == CHILD)
        assert child_bytes < child_context
        for name in ('cognition.jsonl', 'capabilities.jsonl'):
            shutil.copyfile(out / name, evidence / name)
        shutil.copytree(out / 'artifacts', evidence / 'artifacts')
        save('summary', {'status': 'PASS', 'parent_id': PARENT, 'child_id': CHILD, 'invocations': 2,
            'parent_turns': 4, 'child_turns': 5, 'child_result_bytes': child_bytes,
            'child_turn_input_bytes': child_context, 'child_spawn_count': 1,
            'parent_completion_after_child_alone': 'unsatisfied', 'runtime_sigkills': 1, 'server_sigkills': 1,
            'same_states_after_restart': True, 'child_private_context_in_parent': False,
            'architecture_deviations': [], 'next_increment': 3})
        print('PASS: joined child recovery, one spawn, compressed result, independent completion', flush=True)
    finally:
        save('process-events', events)
        for process in processes.values():
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        print(f'Evidence: {evidence}', flush=True)


if __name__ == '__main__':
    main()
