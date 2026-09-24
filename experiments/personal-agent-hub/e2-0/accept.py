#!/usr/bin/env python3
"""E2.0 target-effect acceptance on a real Restate server with SIGKILLs.

Isolated loopback ports and a fresh data directory; owns and stops only the
restate-server and probe runtime it starts. All target effects hit the
deterministic FixtureTarget (SQLite); nothing touches a real file, IDE or process.
After the live run the retained evidence is re-verified offline.
"""
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

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from runtime.kernel import completion, journal
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode, message
from runtime.kernel.human import request_digest
import effect_fixtures as ef

INGRESS, ADMIN, ENDPOINT = 'http://127.0.0.1:38380', 'http://127.0.0.1:39370', 'http://127.0.0.1:39380'
PORTS = (38380, 39370, 39380, 35422)
HAPPY = {'1': 'read', '2': 'draft', '3': 'write', '4': 'run'}
FIXTURES = {
    'change': {'request': ef.change_request('change'), 'script': HAPPY,
               'barriers': ['dispatched/3', 'effect_observed/4'], 'expected': 'COMPLETED'},
    'response-loss': {'request': ef.change_request('response-loss'), 'script': HAPPY, 'expected': 'COMPLETED'},
    'lost-reply': {'request': ef.change_request('lost-reply'), 'script': HAPPY, 'expected': 'COMPLETED'},
    'outage': {'request': ef.change_request('outage'), 'barriers': ['dispatched/3'], 'expected': 'COMPLETED',
               'script': {'1': 'read', '2': 'draft', '3': 'write', '4': 'write', '5': 'wait', '6': 'write', '7': 'run'}},
    'process-control': {'request': ef.change_request('process-control', profiles=('unit-tests', 'slow-build')),
                        'expected': 'COMPLETED',
                        'script': {'1': 'read', '2': 'draft', '3': 'write', '4': 'run-slow', '5': 'run', '6': 'run',
                                   '7': 'wait', '8': 'run'}},
    'approval': {'request': ef.change_request('approval', ask_before=('workspace.write',)), 'script': HAPPY,
                 'expected': 'COMPLETED'},
    'cancel-before-dispatch': {'request': ef.change_request('cancel-before-dispatch', ask_before=('workspace.write',)),
                               'script': {'1': 'read', '2': 'draft', '3': 'write', '4': 'wait'}, 'expected': 'CANCELLED'},
    # Task-level cancellation through the effect machinery (not rollback).
    'task-cancel-approval': {'request': ef.change_request('task-cancel-approval', ask_before=('workspace.write',)),
                             'script': {'1': 'read', '2': 'draft', '3': 'write'}, 'expected': 'CANCELLED'},
    'task-cancel-active': {'request': ef.change_request('task-cancel-active'), 'script': {'1': 'run', '2': 'wait'},
                           'barriers': ['task_stop_effect/1'], 'expected': 'CANCELLED'},
    'task-cancel-race': {'request': ef.change_request('task-cancel-race'), 'script': {'1': 'run', '2': 'wait'},
                         'expected': 'CANCELLED'},
    'task-cancel-unknown': {'request': ef.change_request('task-cancel-unknown'), 'script': {'1': 'run', '2': 'wait'},
                            'expected': 'CANCELLED'},
}


def http(base, path, value=None, method='POST', timeout=10):
    data = None if value is None else json.dumps(value).encode()
    request = urllib.request.Request(base + path, data=data, method=method, headers={
        'Accept': 'application/json', **({'Content-Type': 'application/json'} if data else {})})
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
            last = str(error)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last = str(error)
        time.sleep(0.1)
    raise AssertionError(f'Timeout: {description}; last={last}')


def verify(evidence: Path) -> dict:
    """Offline: reproduce every verdict from retained artifacts; check effect counts."""
    def read(name):
        return json.loads((evidence / f'{name}.json').read_text())
    store = ArtifactStore(evidence / 'artifacts')
    executions = Counter((row['operation_id'], row['kind']) for row in read('executions'))
    report = {}
    for task, fixture in FIXTURES.items():
        final, result = read(f'{task}-final'), read(f'{task}-result')
        assert result['payload']['outcome'] == fixture['expected'] == final['lifecycle'], (task, final['lifecycle'])
        evaluation = store.read_json(task, final['completion_ref'])
        contract = store.read_json(task, final['contract_ref'])['payload']
        assert completion.evaluate_contract(contract, final['contract_ref'], final, store) == evaluation, task
        assert evaluation['payload']['legality']['legal'] == (fixture['expected'] == 'COMPLETED'), task
        entries = [e for _, e in journal.read(store, task, final['journal_head'], final['journal_length'])]
        authorities = {r: journal.validate_authority(store.read_json(task, r), task)
                       for r in {e['authority_ref'] for e in entries if 'authority_ref' in e}}
        analysis = journal.analyze(list(enumerate(entries)), authorities)
        assert not analysis['problems'], (task, analysis['problems'])
        for operation, effect in final['effects'].items():
            ran = executions[(operation, 'write')] + executions[(operation, 'exec')]
            assert executions[(operation, 'cancel')] <= 1, (task, operation, 'duplicate stop request')
            # Each logical effect executed at most once at the provider, whatever retries happened.
            assert ran <= 1, (task, operation, ran)
            if effect['status'] in ('applied', 'completed', 'timed_out', 'canceled'):
                assert ran == 1, (task, operation, effect['status'])
            if effect['status'] in ('not_dispatched', 'not_applied', 'conflict'):
                assert executions[(operation, 'write')] == 0, (task, operation)
        report[task] = {'outcome': final['lifecycle'],
                        'criteria': {c['id']: c['status'] for c in evaluation['payload']['criteria']},
                        'effects': {op: e['status'] for op, e in final['effects'].items()},
                        'journal': [f"{e['phase']}:{e.get('operation_class') or e.get('outcome') or e.get('state') or ''}"
                                    for e in entries],
                        'offline_reproduced': True}
    for name, rows in read('journal-prefixes').items():
        assert rows['unchanged'] == rows['before'], name
    cognition = [json.loads(line) for line in (evidence / 'cognition.jsonl').read_text().splitlines()]
    assert all(n == 1 for n in Counter((r['task_id'], r['iteration']) for r in cognition).values())
    for path in (evidence / 'artifacts').glob('*/*'):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == path.name
    return {'outcome': 'PASS', 'tasks': report, 'cognitive_turns': len(cognition), 'duplicate_cognitive_turns': 0,
            'provider_executions': sum(executions.values()), 'duplicate_provider_executions': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restate-server', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, default=Path(__file__).resolve().parent / 'evidence')
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise RuntimeError('Use a new output directory; do not reuse Task identities/data')
    for port in PORTS:
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
    out.mkdir(parents=True)
    evidence = args.evidence.resolve()
    if evidence.exists():
        shutil.rmtree(evidence)
    evidence.mkdir(parents=True)

    def save(name, value):
        (evidence / f'{name}.json').write_bytes(encode(value) + b'\n')

    versions = {'server': subprocess.check_output([str(args.restate_server), '--version'], text=True).strip(),
                'sdk': importlib.metadata.version('restate-sdk'), 'python': sys.version.split()[0]}
    assert '1.7.9' in versions['server'] and versions['sdk'] == '1.0.5', versions
    save('versions', versions)
    (out / 'fixtures.json').write_bytes(encode({k: {x: v[x] for x in ('script', 'barriers') if x in v}
                                                for k, v in FIXTURES.items()}))
    save('fixtures', {k: {x: v[x] for x in ('script', 'barriers', 'expected') if x in v} for k, v in FIXTURES.items()})
    (out / 'restate.toml').write_text(f'''cluster-name = "blaine-e20-probe"
node-name = "e20-probe"
base-dir = "{out / 'restate-data'}"
bind-ip = "127.0.0.1"
bind-port = 35422
advertised-host = "127.0.0.1"
listen-mode = "tcp"
auto-provision = true
default-journal-retention = "7 days"
[admin]
bind-address = "127.0.0.1:39370"
[ingress]
bind-address = "127.0.0.1:38380"
''')
    target = ef.FixtureTarget(out / 'target.sqlite')
    environment = {k: v for k, v in os.environ.items() if not k.startswith('RESTATE_')}
    environment.update(E20_PROBE_DIR=str(out), PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
    processes, generations, events, prefixes, checks = {}, Counter(), [], {}, {}

    def start(name):
        generations[name] += 1
        command = ([str(args.restate_server), '--config-file', str(out / 'restate.toml')] if name == 'server'
                   else [sys.executable, str(Path(__file__).resolve().parent / 'probe_app.py')])
        with (out / f'{name}-{generations[name]}.log').open('wb') as log:
            process = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=log, stderr=subprocess.STDOUT)
        processes[name] = process
        events.append({'action': 'start', 'process': name, 'generation': generations[name]})
        def ready():
            if process.poll() is not None:
                raise RuntimeError(f'{name} exited; inspect {out}')
            if name == 'server':
                return http(ADMIN, '/deployments', method='GET') is not None
            try:
                with socket.create_connection(('127.0.0.1', 39380), timeout=2):
                    return True
            except OSError:
                return False
        until(ready, f'{name} ready', 40)

    def kill(name, reason):
        process = processes.pop(name)
        process.kill()
        assert process.wait(timeout=10) == -9
        events.append({'action': 'SIGKILL', 'process': name, 'reason': reason})

    def restart(*names, reason):
        for name in names:
            kill(name, reason)
        for name in ('server', 'runtime'):
            if name in names:
                start(name)

    def call(task, handler, body=None):
        return http(INGRESS, f'/CognitiveTaskV1/{task}/{handler}', body)

    def status(task):
        return call(task, 'status')['payload']

    def rows(task):
        return http(ADMIN, '/query', {'query': "SELECT id, index, raw, appended_at FROM sys_journal WHERE id IN "
                    f"(SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/{task}/run') ORDER BY index"})['rows']

    def snapshot(task, label):
        prefixes[f'{task}/{label}'] = {'before': rows(task)}

    def effect(task, operation, statuses):
        return until(lambda: (s if (s := status(task)).get('effects', {}).get(f'{task}/{operation}', {}).get('status')
                              in statuses else None), f'{task}/{operation} in {statuses}')

    def waiting(task, input_type):
        return until(lambda: (s if (s := status(task)).get('lifecycle') == 'WAITING'
                              and s['wait']['input_type'] == input_type else None), f'{task} waiting {input_type}')

    def barrier(task, marker, reason, before_release=None):
        probe = until(lambda: (p if (p := call(task, 'probe_status')).get('marker') == marker else None), f'{task} {marker}')
        snapshot(task, marker)
        restart('runtime', reason=reason)
        restored = status(task)
        for key in ('journal_head', 'journal_length', 'effects', 'artifacts', 'contract_ref', 'completion_ref'):
            assert restored[key] == probe['state'][key], (task, marker, key)
        checks[f'{task}/{marker}'] = {'restored_equal': True, 'journal_length': restored['journal_length']}
        if before_release:
            before_release()
        call(task, 'release_probe', {'marker': marker})

    def resume_text(task):
        wait = waiting(task, 'text')['wait']
        call(task, 'submit_input', message('ExternalInput', {'wait_id': 'continue', 'task_revision': wait['task_revision'],
                                                             'input_type': 'text', 'value': 'continue'}))

    def finish(task):
        final = until(lambda: (s if (s := status(task)).get('lifecycle') in ('COMPLETED', 'FAILED', 'CANCELLED')
                               and s['result_ref'] else None), task + ' terminal', seconds=120)
        save(f'{task}-final', final)
        save(f'{task}-result', http(INGRESS, f'/restate/workflow/CognitiveTaskV1/{task}/attach', method='GET'))
        for key, value in prefixes.items():
            if key.startswith(task + '/'):
                final_rows = {row['index']: row for row in rows(task)}
                value['unchanged'] = [final_rows.get(row['index']) for row in value['before']]
        print(f"{task}: {final['lifecycle']} {({op: e['status'] for op, e in final['effects'].items()})}", flush=True)
        return final

    def submit(task):
        # One scenario at a time against a fresh target file, so kills never land in another Task.
        target.put_file(ef.CONFIG, ef.BEFORE)
        target.behave('unit-tests', polls=2, exit_code=0, result={'tests': 4, 'failures': 0})
        checks[f'{task}/submission'] = call(task, 'run/send', FIXTURES[task]['request'])

    try:
        start('server')
        start('runtime')
        save('deployment', http(ADMIN, '/deployments', {'uri': ENDPOINT}))

        # 1. Conditional write and verified tests; runtime dies after dispatch is
        # journaled (before the provider call) and after an exec result is admitted.
        submit('change')
        barrier('change', 'dispatched/3', 'write dispatched in the journal, provider not yet called')
        barrier('change', 'effect_observed/4', 'exec receipt admitted, before evaluation')
        finish('change')

        # 2. Response loss: the provider commits and the runtime dies before Restate
        # records the step; the retry recovers the receipt instead of writing again.
        target.set_fault('after_commit', 'block')
        submit('response-loss')
        until(lambda: (out / 'effect-committed').exists(), 'write committed at the provider')
        snapshot('response-loss', 'effect-committed')
        target.set_fault('after_commit', None)
        kill('runtime', 'provider committed the write; step result not yet journaled')
        (out / 'release-effect').write_text('release')
        start('runtime')
        checks['response-loss/write-executions'] = len(target.executions('response-loss/3'))
        finish('response-loss')

        # 3. A dropped reply is uncertain and reconciles APPLIED from the receipt.
        target.set_fault('after_commit', 'lose_response')
        submit('lost-reply')
        finish('lost-reply')

        # 4. Provider outage at dispatch with non-authoritative receipts: STILL_UNKNOWN,
        # new effects refused, server SIGKILL while unknown, then NOT_APPLIED and a new effect.
        submit('outage')
        def outage():
            target.set_fault('unavailable', True)
            target.set_fault('receipts_authoritative', False)
        barrier('outage', 'dispatched/3', 'write dispatched; provider about to become unreachable', before_release=outage)
        waiting('outage', 'text')
        checks['outage/unknown'] = {k: status('outage')['effects'][f'outage/{k}']['status'] for k in (3,)}
        restart('server', reason='Task waiting with an unreconciled uncertain effect')
        target.set_fault('unavailable', None)
        target.set_fault('receipts_authoritative', True)
        resume_text('outage')
        finish('outage')

        # 5. Process control: deadline stop, requested cancel with confirmed stop, an
        # unconfirmed stop (uncertain, reconciled later), and durable timers across a kill.
        target.behave('slow-build', polls=99)
        target.behave('unit-tests', polls=99, operation='process-control/5')
        target.behave('unit-tests', polls=99, stop='unknown', operation='process-control/6')
        submit('process-control')
        effect('process-control', 4, ('running',))
        restart('runtime', reason='process supervised on durable timers')
        effect('process-control', 4, ('timed_out',))
        effect('process-control', 5, ('running',))
        checks['process-control/cancel-5'] = call('process-control', 'cancel_effect',
                                                  message('EffectCancelRequest', {'operation_id': 'process-control/5'}))
        effect('process-control', 5, ('canceled',))
        effect('process-control', 6, ('running',))
        call('process-control', 'cancel_effect', message('EffectCancelRequest', {'operation_id': 'process-control/6'}))
        waiting('process-control', 'text')
        checks['process-control/unconfirmed-stop'] = status('process-control')['effects']['process-control/6']['status']
        target.behave('unit-tests', polls=1, exit_code=0, result={'tests': 4, 'failures': 0}, operation='process-control/6')
        resume_text('process-control')
        finish('process-control')

        # 6. Approval through the existing human boundary, across runtime and server loss.
        submit('approval')
        wait = waiting('approval', 'human_response')
        restart('runtime', 'server', reason='Task waiting on effect approval')
        human = http(INGRESS, '/CognitiveTaskV1/approval/inspect')['pending_human_decision']
        checks['approval/request'] = human['payload']['question']
        call('approval', 'submit_human_response', message('HumanDecisionResponse', {'task_id': 'approval',
            'request_id': wait['wait']['wait_id'], 'request_revision': 0, 'request_digest': request_digest(human),
            'response_id': 'approve-1', 'value': 'APPROVE'}))
        finish('approval')

        # 7. Cancellation before dispatch: proven not to have happened.
        submit('cancel-before-dispatch')
        waiting('cancel-before-dispatch', 'human_response')
        checks['cancel-before-dispatch/cancel'] = call('cancel-before-dispatch', 'cancel_effect',
            message('EffectCancelRequest', {'operation_id': 'cancel-before-dispatch/3'}))
        waiting('cancel-before-dispatch', 'text')
        call('cancel-before-dispatch', 'cancel')
        finish('cancel-before-dispatch')

        # 8. Task cancel while awaiting approval: the effect closes as never dispatched.
        submit('task-cancel-approval')
        waiting('task-cancel-approval', 'human_response')
        call('task-cancel-approval', 'cancel')
        finish('task-cancel-approval')

        # 9. Task cancel with an active process: confirmed stop; the runtime dies in
        # the middle of the cancellation and the replay sends no second stop.
        target.behave('unit-tests', polls=99, operation='task-cancel-active/1')
        submit('task-cancel-active')
        effect('task-cancel-active', 1, ('running',))
        call('task-cancel-active', 'cancel')
        barrier('task-cancel-active', 'task_stop_effect/1', 'runtime dies during Task cancellation')
        finish('task-cancel-active')

        # 10. The process completes before the stop: its completion is the outcome.
        target.behave('unit-tests', polls=99, operation='task-cancel-race/1')
        submit('task-cancel-race')
        effect('task-cancel-race', 1, ('running',))
        target.behave('unit-tests', polls=1, exit_code=0, result={'failures': 0}, operation='task-cancel-race/1')
        call('task-cancel-race', 'cancel')
        finish('task-cancel-race')

        # 11. The stop cannot be confirmed: CANCELLED, with the effect explicitly STILL_UNKNOWN.
        target.behave('unit-tests', polls=99, stop='unknown', operation='task-cancel-unknown/1')
        submit('task-cancel-unknown')
        effect('task-cancel-unknown', 1, ('running',))
        call('task-cancel-unknown', 'cancel')
        final = finish('task-cancel-unknown')
        checks['task-cancel-unknown/effect'] = final['effects']['task-cancel-unknown/1']['status']
        checks['task-cancel-unknown/concerns'] = http(INGRESS, '/restate/workflow/CognitiveTaskV1/task-cancel-unknown/attach',
                                                      method='GET')['payload']['concerns']

        save('checks', checks)
        save('journal-prefixes', prefixes)
        save('process-events', events)
        with sqlite3.connect(out / 'target.sqlite') as db:
            save('executions', [{'operation_id': op, 'kind': kind} for op, kind in
                                db.execute('SELECT operation_id, kind FROM executions ORDER BY rowid')])
        shutil.copytree(out / 'artifacts', evidence / 'artifacts')
        for name in ('cognition.jsonl', 'events.jsonl'):
            shutil.copyfile(out / name, evidence / name)
    finally:
        for name, process in list(processes.items()):
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    summary = verify(evidence)
    summary.update(runtime_sigkills=sum(1 for e in events if e['action'] == 'SIGKILL' and e['process'] == 'runtime'),
                   server_sigkills=sum(1 for e in events if e['action'] == 'SIGKILL' and e['process'] == 'server'),
                   versions=versions, real_target_effects=0, live_model_calls=0, cloud_calls=0, ide_or_terminal=False)
    save('summary', summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'tasks'}, indent=2))


if __name__ == '__main__':
    main()
