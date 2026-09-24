#!/usr/bin/env python3
"""Isolated Increment 1 acceptance probe. Owns and cleans up only its processes.

HISTORICAL, NON-GATING (classified 2026-09-24, E1.0): milestone evidence for Increment 1,
frozen as run. Its fixtures predate verifier-first progression (milestone 024) and fail
identically on unchanged code; current coverage of its properties is mapped in
experiments/personal-agent-hub/e1-0/regression.json and guarded by
tests/test_regression_coverage.py. Do not edit it to pass; do not treat it as a gate."""
import argparse
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import MAX_PACKET, encode, message

INGRESS = 'http://127.0.0.1:38080'
ADMIN = 'http://127.0.0.1:39070'
ENDPOINT = 'http://127.0.0.1:39080'
ANSWER = 'Increment 1 exact evidence.\n'
DIGEST = hashlib.sha256(ANSWER.encode()).hexdigest()
WRITE = {'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write', 'input': {'name': 'answer', 'content': ANSWER}}
READ = {'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.read', 'input': {'ref': '$answer'}}
EFFECT = {'type': 'INVOKE_CAPABILITY', 'capability': 'fixture.effect', 'input': {'value': 'one bounded effect'}}
COMPLETE = {'type': 'COMPLETE'}
HANDOFF = {'type': 'HANDOFF', 'specialist': 'specialist'}
WAIT = {'type': 'WAIT', 'wait_id': 'review', 'input_type': 'text'}
FIXTURES = {
    'multi': {'actions': [WRITE, READ, COMPLETE]},
    'premature': {'actions': [COMPLETE, WRITE, COMPLETE]},
    'handoff': {'actions': [HANDOFF, WRITE, COMPLETE]},
    'wait': {'actions': [WAIT, WRITE, COMPLETE]},
    'denial': {'actions': [EFFECT, WRITE, COMPLETE]},
    'recovery': {'actions': [EFFECT, WRITE, HANDOFF, WAIT, COMPLETE],
                 'barriers': ['decision/3', 'outcome/3']},
    'response-loss': {'actions': [EFFECT, WRITE, COMPLETE], 'lose_effect_response': True},
}


def http(base, path, value=None, timeout=8, method=None):
    data = None if value is None else json.dumps(value).encode()
    request = urllib.request.Request(base + path, data=data, method=method,
                                     headers={'Accept': 'application/json', **({'Content-Type': 'application/json'} if data else {})})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
        return json.loads(body) if body else None


def until(function, description, seconds=90):
    deadline = time.monotonic() + seconds
    last = None
    while time.monotonic() < deadline:
        try:
            last = function()
            if last:
                return last
        except urllib.error.HTTPError as error:
            if error.code < 500:
                raise
            last = str(error)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last = str(error)
        time.sleep(.1)
    raise AssertionError(f'Timeout: {description}; last={last}')


def verify_replay(evidence):
    """Verify saved server journal bytes independently of application log claims."""
    def rows(name):
        result = json.loads((evidence / (name + '.json')).read_text())['rows']
        assert result, name
        return result

    def run_result(entries, name):
        commands = [json.loads(row['entry_json'])['Command']['Run'] for row in entries
                    if row['entry_type'] == 'Command: Run' and row['name'] == name]
        assert len(commands) == 1, name
        completion = commands[0]['completion_id']
        results = [json.loads(row['entry_json'])['Notification']['Completion']['Run'] for row in entries
                   if row['entry_type'] == 'Notification: Run']
        matches = [item for item in results if item['completion_id'] == completion]
        return json.loads(bytes(matches[0]['result']['Success'])) if matches else None

    checks = []
    for task, suffix in (('recovery', 'before-decision-crash'), ('recovery', 'before-handoff-crash'),
                         ('recovery', 'before-server-crash'), ('response-loss', 'before-effect-crash')):
        before, after = rows(f'{task}-journal-{suffix}'), rows(f'{task}-journal-final')
        final = {row['index']: row for row in after}
        for row in before:
            for key in ('id', 'raw', 'appended_at'):
                assert row[key] == final[row['index']][key], (task, row['index'], key)
        checks.append({'task': task, 'checkpoint': suffix, 'unchanged_journal_entries': len(before)})
    committed = run_result(rows('recovery-journal-before-decision-crash'), 'cognitive/3')
    assert committed['payload']['next_action'] == HANDOFF
    assert run_result(rows('recovery-journal-before-decision-crash'), 'capability/1')['payload']['outcome'] == 'success'
    assert run_result(rows('response-loss-journal-before-effect-crash'), 'cognitive/1') is not None
    assert run_result(rows('response-loss-journal-before-effect-crash'), 'capability/1') is None
    assert run_result(rows('response-loss-journal-final'), 'capability/1')['payload']['outcome'] == 'success'
    handoff = json.loads((evidence / 'recovery-handoff-committed.json').read_text())['state']
    packet = ArtifactStore(evidence / 'artifacts').read_json('recovery', handoff['context_ref'])
    audit = [json.loads(line) for line in (evidence / 'cognition.jsonl').read_text().splitlines()]
    actual = next(row['packet'] for row in audit if row['packet']['payload']['turn_id'] == 'recovery/4')
    assert packet == actual
    assert ANSWER.strip() not in json.dumps(actual)
    result = {'outcome': 'PASS', 'checkpoints': checks, 'handoff_decision_committed_before_kill': True,
              'next_specialist_received_exact_committed_packet': True,
              'effect_response_absent_before_kill_present_after_retry': True}
    (evidence / 'replay-checks.json').write_bytes(encode(result) + b'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restate-server', type=Path, default=ROOT / '.local/bin/restate-server')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise RuntimeError('Use a new output directory; do not reuse Task identities/data')
    for port in (38080, 39070, 39080, 35122):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
    out.mkdir(parents=True)
    evidence = out / 'evidence'
    evidence.mkdir()

    def save(name, value):
        (evidence / (name + '.json')).write_bytes(encode(value) + b'\n')

    versions = {'server': subprocess.check_output([str(args.restate_server), '--version'], text=True).strip(),
                'sdk': importlib.metadata.version('restate-sdk'), 'python': sys.version}
    assert '1.7.9' in versions['server'] and versions['sdk'] == '1.0.5', versions
    save('versions', versions)
    (out / 'fixtures.json').write_bytes(encode(FIXTURES))
    (out / 'restate.toml').write_text(f'''cluster-name = "blaine-kernel-probe"
node-name = "kernel-probe"
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
    environment = {k: v for k, v in os.environ.items() if not k.startswith('RESTATE_')}
    environment.update(KERNEL_PROBE_DIR=str(out), PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
    processes = {}
    generations = Counter()
    events = []

    def start(name):
        generations[name] += 1
        command = ([str(args.restate_server), '--config-file', str(out / 'restate.toml')] if name == 'server'
                   else [sys.executable, str(ROOT / 'experiments/kernel-increment-1/probe_app.py')])
        with (out / f'{name}-{generations[name]}.log').open('wb') as log:
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
        processes[name] = process
        events.append({'action': 'start', 'process': name, 'pid': process.pid, 'generation': generations[name]})
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
        until(ready, f'{name} ready', 40)

    def kill(name, reason):
        process = processes.pop(name)
        process.kill()
        code = process.wait(timeout=10)
        assert code == -9, code
        events.append({'action': 'SIGKILL', 'process': name, 'pid': process.pid, 'exit_code': code, 'reason': reason})
        save('process-events', events)

    def call(task, handler, body=None):
        return http(INGRESS, f'/CognitiveTaskV1/{task}/{handler}', body, method='POST')

    def status(task):
        return call(task, 'status')['payload']

    def submit(task):
        capabilities = ['artifact.write', 'artifact.read', 'fixture.effect']
        spec = message('TaskSpec', {'objective': f'Verify {task} using exact artifact evidence',
                    'completion': [{'criterion': 'answer contains the accepted exact bytes',
                                    'evidence': {'artifact': 'answer', 'sha256': DIGEST}}],
                    'capabilities': capabilities,
                    'autonomy': {'allowed': [cap for cap in capabilities if task != 'denial' or cap != 'fixture.effect']}})
        save(task + '-spec', spec)
        receipt = call(task, 'run/send', spec)
        save(task + '-submission', receipt)
        return receipt

    def journal(task, suffix):
        # Constant test identities, not external SQL input.
        rows = http(ADMIN, '/query', {'query': f"SELECT * FROM sys_journal WHERE id IN (SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/{task}/run') ORDER BY index"})
        save(task + '-journal-' + suffix, rows)
        return rows

    def finish(task):
        final = until(lambda: (s if (s := status(task)).get('lifecycle') in ('COMPLETED', 'FAILED') and s['result_ref'] else None), task + ' completion')
        assert final['lifecycle'] == 'COMPLETED', final
        result = http(INGRESS, f'/restate/workflow/CognitiveTaskV1/{task}/attach', method='GET')
        save(task + '-final', message('TaskState', final))
        save(task + '-result', result)
        assert result['payload']['task_id'] == task
        assert result['payload']['completion_ref'] == final['completion_ref']
        journal(task, 'final')
        return final

    def resume(task):
        current = until(lambda: (s if (s := status(task)).get('lifecycle') == 'WAITING' else None), task + ' waiting')
        save(task + '-waiting', message('TaskState', current))
        wait = current['wait']
        body = message('ExternalInput', {k: wait[k] for k in ('wait_id', 'task_revision', 'input_type')} | {'value': 'reviewed bounded input'})
        wrong = json.loads(json.dumps(body))
        wrong['payload']['task_revision'] += 1
        try:
            call(task, 'submit_input', wrong)
            raise AssertionError('Stale input accepted')
        except urllib.error.HTTPError as error:
            assert error.code == 409, error.read()
            save(task + '-stale-input', {'status_code': error.code, 'body': json.loads(error.read())})
        receipt = call(task, 'submit_input', body)
        save(task + '-input', {'request': body, 'receipt': receipt})

    try:
        start('server')
        start('runtime')
        save('deployment', http(ADMIN, '/deployments', {'uri': ENDPOINT}))
        for task in ('multi', 'premature', 'handoff', 'wait', 'denial'):
            submit(task)
            if task == 'wait':
                resume(task)
            finish(task)
            print(f'PASS {task}', flush=True)

        submit('recovery')
        decision = until(lambda: (p if (p := call('recovery', 'probe_status')).get('marker') == 'decision/3' else None), 'committed decision barrier')
        save('recovery-decision-committed', decision)
        journal('recovery', 'before-decision-crash')
        assert decision['state']['decision_id'] == 'recovery/3'
        kill('runtime', 'HANDOFF decision committed before ownership transition')
        start('runtime')
        assert status('recovery')['decision_ref'] == decision['state']['decision_ref']
        call('recovery', 'release_probe', {'marker': 'decision/3'})
        handoff = until(lambda: (p if (p := call('recovery', 'probe_status')).get('marker') == 'outcome/3' else None), 'committed handoff barrier')
        save('recovery-handoff-committed', handoff)
        journal('recovery', 'before-handoff-crash')
        assert handoff['state']['active_specialist'] == 'specialist'
        kill('runtime', 'HANDOFF owner and specialist packet committed before next cognition')
        start('runtime')
        restored = status('recovery')
        for key in ('task_id', 'decision_ref', 'active_specialist', 'context_ref', 'artifacts'):
            assert restored[key] == handoff['state'][key], key
        save('recovery-handoff-restored', restored)
        call('recovery', 'release_probe', {'marker': 'outcome/3'})
        until(lambda: status('recovery')['lifecycle'] == 'WAITING', 'recovery durable wait')
        journal('recovery', 'before-server-crash')
        kill('server', 'Task waiting on durable input promise')
        start('server')
        resume('recovery')
        recovered = finish('recovery')
        assert recovered['active_specialist'] == 'specialist'
        print('PASS recovery (two runtime SIGKILLs, one server SIGKILL)', flush=True)

        submit('response-loss')
        until(lambda: (out / 'effect-committed.jsonl').exists(), 'effect committed before run response')
        journal('response-loss', 'before-effect-crash')
        kill('runtime', 'fixture effect committed before Restate records capability result')
        (out / 'release-effect').write_text('retry may return the existing receipt')
        start('runtime')
        finish('response-loss')
        print('PASS response-loss', flush=True)

        cognition = [json.loads(line) for line in (out / 'cognition.jsonl').read_text().splitlines()]
        attempts = [json.loads(line) for line in (out / 'capabilities.jsonl').read_text().splitlines()]
        turns = {(row['packet']['payload']['task_id'], row['packet']['payload']['iteration']): row['packet']['payload'] for row in cognition}
        counts = Counter((row['packet']['payload']['task_id'], row['packet']['payload']['iteration']) for row in cognition)
        assert all(count == 1 for count in counts.values()), counts
        for task, fixture in FIXTURES.items():
            assert sum(count for (key, _), count in counts.items() if key == task) == len(fixture['actions'])
        assert turns['multi', 1]['observations'] == []
        assert turns['multi', 2]['observations'][0]['payload']['operation_id'] == 'multi/1'
        assert turns['multi', 3]['observations'][0]['payload']['output']['content'] == ANSWER
        assert turns['premature', 2]['observations'][0]['payload']['outcome'] == 'unsatisfied'
        assert 'missing' in turns['premature', 2]['observations'][0]['payload']['criteria'][0]['detail']
        assert turns['handoff', 2]['specialist'] == 'specialist'
        assert turns['handoff', 2]['observations'][0]['kind'] == 'HandoffResult'
        assert turns['recovery', 4]['specialist'] == 'specialist'
        assert turns['recovery', 4]['observations'][0]['kind'] == 'HandoffResult'
        assert ANSWER.strip() not in json.dumps(turns['recovery', 4])  # earlier artifact bytes were not forwarded
        assert turns['wait', 2]['observations'][0]['payload']['value'] == 'reviewed bounded input'
        assert turns['recovery', 5]['observations'][0]['payload']['value'] == 'reviewed bounded input'
        assert turns['denial', 2]['observations'][0]['kind'] == 'PolicyDecision'
        assert not any(row['request']['payload']['operation_id'] == 'denial/1' for row in attempts)
        effect_attempts = Counter(row['request']['payload']['operation_id'] for row in attempts if row['request']['payload']['capability'] == 'fixture.effect')
        assert effect_attempts == {'recovery/1': 1, 'response-loss/1': 2}, effect_attempts
        with sqlite3.connect(out / 'fixture.sqlite') as db:
            effects = [{'operation_id': op, 'request': json.loads(req), 'receipt': json.loads(receipt)}
                       for op, req, receipt in db.execute('SELECT * FROM effects ORDER BY operation_id')]
        assert [row['operation_id'] for row in effects] == ['recovery/1', 'response-loss/1']
        store = ArtifactStore(out / 'artifacts')
        verified = []
        for path in sorted((out / 'artifacts').glob('*/*')):
            ref = f'artifact://{path.parent.name}/sha256:{path.name}'
            content = store.read(path.parent.name, ref)
            assert hashlib.sha256(content).hexdigest() == path.name
            verified.append({'ref': ref, 'bytes': len(content)})
        assert all(len(encode(row['packet'])) <= MAX_PACKET for row in cognition)
        shutil.copytree(out / 'artifacts', evidence / 'artifacts')
        for name in ('cognition.jsonl', 'capabilities.jsonl', 'effect-committed.jsonl'):
            shutil.copyfile(out / name, evidence / name)
        save('effects', effects)
        save('verified-artifacts', verified)
        save('process-events', events)
        verify_replay(evidence)
        save('summary', {'outcome': 'PASS', 'tasks': list(FIXTURES),
                        'cognitive_turns': len(cognition), 'all_committed_turns_called_once': True,
                        'max_context_packet_bytes': max(len(encode(row['packet'])) for row in cognition),
                        'fixture_effect_rows': len(effects), 'effect_attempts': dict(effect_attempts),
                        'verified_artifacts': len(verified), 'runtime_sigkills': 3, 'server_sigkills': 1,
                        'assertions': ['multi-turn durable observations', 'premature completion rejected',
                            'same-Task bounded HANDOFF', 'typed WAIT/resume and stale-input rejection',
                            'policy denial without dispatch', 'journaled cognition not repeated',
                            'handoff owner/packet survives restart', 'committed effect not repeated',
                            'response-loss retry deduplicated', 'artifact digests valid after recovery']})
    finally:
        for name, process in list(processes.items()):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        print(f'Evidence: {evidence}', flush=True)


if __name__ == '__main__':
    main()
