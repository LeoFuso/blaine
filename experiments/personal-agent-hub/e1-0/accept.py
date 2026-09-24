#!/usr/bin/env python3
"""E1.0 Completion Contract acceptance on a real Restate server with SIGKILLs.

Isolated: owns and stops only the restate-server and probe runtime it starts, on
dedicated loopback ports and a fresh data directory. Scripted cognition, stub
reviewer; no model, provider, network, IDE or workstation. After the live run the
retained evidence is re-verified offline from artifacts alone.
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
import threading
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]
from runtime.kernel import completion, journal
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import child_task_id, encode, message
from runtime.personal_agent import ControlRejected, PersonalAgent, RestateBinding
import completion_fixtures as fx

INGRESS, ADMIN, ENDPOINT = 'http://127.0.0.1:38280', 'http://127.0.0.1:39270', 'http://127.0.0.1:39280'
PORTS = (38280, 39270, 39280, 35322)
GOOD = hashlib.sha256(b'GOOD').hexdigest()
POLICY_DIGEST = 'sha256:' + hashlib.sha256(b'synthetic designated project policy v1').hexdigest()
# No operator binding exists yet; this harness acts as that trusted binding, labelled.
OPERATOR = {'kind': 'operator', 'via': 'policy_exception', 'binding': 'e10-operator-fixture'}


def answer_spec(task, human=False, effect=False):
    completion_items = [{'criterion': 'Exact answer', 'evidence': {'artifact': 'answer', 'sha256': GOOD}}]
    capabilities = ['artifact.write'] + (['fixture.effect'] if effect else [])
    if human:
        completion_items.append({'criterion': 'Human decided', 'evidence': {'artifact': 'decision',
            'verifier': 'human_response', 'request': fx.human_request(task, 'decide', ('YES', 'NO'))}})
        capabilities.append('human.request')
    return message('TaskSpec', {'objective': 'Produce the exact answer.', 'completion': completion_items,
                                'capabilities': capabilities, 'autonomy': {'allowed': capabilities}})


def policy_request(task):
    spec = answer_spec(task)
    c1 = completion.lower_spec(spec['payload'], task)['criteria'][0]
    policy = {'id': 'canonical-check', 'level': 'REQUIRED', 'requirement': 'The canonical check report passes.',
              'provenance': {'source': 'project_policy', 'ref': 'example-policy#canonical-check',
                             'designation_ref': f'artifact://{task}/sha256:' + 'a' * 64, 'source_digest': POLICY_DIGEST},
              'verifier': {'kind': 'artifact_digest', 'version': 1, 'artifact': 'check',
                           'sha256': hashlib.sha256(b'PASS').hexdigest()}}
    contract = message('CompletionContract', {'task_id': task, 'revision': 0, 'previous_ref': None,
        'amendment_ref': None, 'task_type': None, 'criteria': [c1, policy]})
    return message('TaskRequest', {'task_spec': spec, 'grant': {'capabilities': ['artifact.write']}, 'contract': contract})


PARENT = 'child-parent'
CHILD = child_task_id(PARENT, PARENT + '/1')


def parent_spec():
    child = message('TaskSpec', {'objective': 'Obtain a scoped human decision without choosing it.', 'completion': [
        {'criterion': 'Human decided', 'evidence': {'artifact': 'decision', 'verifier': 'human_response',
         'request': message('HumanDecisionRequest', {'task_id': CHILD, 'origin_task_id': PARENT, 'request_id': 'decide',
             'revision': 0, 'question': 'Proceed with the scoped change?', 'allowed_responses': ['YES', 'NO']})}}],
        'capabilities': ['human.request'], 'autonomy': {'allowed': ['human.request']}})
    capabilities = ['artifact.write', 'human.request']
    return child, message('TaskSpec', {'objective': 'Delegate a human decision to a child, then answer.',
        'completion': [{'criterion': 'Exact answer', 'evidence': {'artifact': 'answer', 'sha256': GOOD}}],
        'capabilities': capabilities, 'autonomy': {'allowed': capabilities, 'child_tasks': 1}})


FIXTURES = {
    'investigation': {'request': fx.investigation_request('investigation'), 'script': {'2': 'fabricate', '3': 'cite'},
                      'barriers': ['contract_retained/0', 'receipt_admitted/1', 'admitted/2'], 'expected': 'COMPLETED'},
    'denial': {'request': fx.investigation_request('denial'),
               'script': {'2': 'effect', '3': 'amend-attempt', '4': 'handoff', '5': 'cite'},
               'barriers': ['outcome/4'], 'expected': 'COMPLETED'},
    'irrecoverable': {'request': fx.investigation_request('irrecoverable', extra_capabilities=('fixture.effect',)),
                      'script': {'2': 'effect'}, 'expected': 'FAILED'},
    'human-resume': {'request': answer_spec('human-resume', human=True),
                     'script': {'1': 'write-answer', '2': 'human-request'}, 'expected': 'COMPLETED'},
    'human-waiver': {'request': answer_spec('human-waiver', human=True),
                     'script': {'1': 'write-answer', '2': 'human-request'}, 'barriers': ['amended/2'],
                     'expected': 'COMPLETED'},
    'policy-exception': {'request': policy_request('policy-exception'), 'script': {'1': 'write-answer', '2': 'wait'},
                         'expected': 'COMPLETED'},
    PARENT: {'request': parent_spec()[1], 'spawn': parent_spec()[0], 'script': {'1': 'spawn', '2': 'write-answer'},
             'expected': 'COMPLETED'},
    CHILD: {'script': {'1': 'human-request'}, 'expected': 'COMPLETED', 'child_of': PARENT},
    'response-loss': {'request': answer_spec('response-loss', effect=True), 'script': {'1': 'effect', '2': 'write-answer'},
                      'lose_effect_response': True, 'expected': 'COMPLETED'},
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
    """Offline: every verdict must be reproducible from retained artifacts and state."""
    def read(name):
        return json.loads((evidence / f'{name}.json').read_text())
    store = ArtifactStore(evidence / 'artifacts')
    report = {}
    for task, fixture in FIXTURES.items():
        final, result = read(f'{task}-final'), read(f'{task}-result')
        assert result['payload']['outcome'] == fixture['expected'] == final['lifecycle'], task
        evaluation = store.read_json(task, result['payload']['completion_ref'])
        assert evaluation['version'] == 2 and evaluation['payload']['contract_ref'] == final['contract_ref'], task
        contract = completion.validate_contract(store.read_json(task, final['contract_ref']), task, False)
        revisions, cursor = [], final['contract_ref']
        while cursor:
            revision = store.read_json(task, cursor)['payload']
            revisions.append(revision['revision'])
            if revision['amendment_ref']:
                amendment = store.read_json(task, revision['amendment_ref'])['payload']
                assert (amendment['to_revision'], amendment['from_ref']) == (revision['revision'], revision['previous_ref'])
                action = store.read_json(task, amendment['actor']['ref'])
                assert action['kind'] == 'CompletionContractAmendmentSubmission'
                assert action['payload']['actor'] == {k: amendment['actor'][k] for k in ('kind', 'via', 'binding')}
            cursor = revision['previous_ref']
        assert revisions == list(range(final['contract_revision'], -1, -1)), (task, revisions)
        assert completion.evaluate_contract(contract, final['contract_ref'], final, store) == evaluation, task
        legal = evaluation['payload']['legality']['legal']
        assert legal == (fixture['expected'] == 'COMPLETED'), task
        if legal:
            required = [c for c in evaluation['payload']['criteria'] if c['gating']]
            assert all(c['status'] in ('satisfied', 'waived') for c in required), task
        entries = journal.read(store, task, final['journal_head'], final['journal_length'])
        analysis = journal.analyze(entries, {r: journal.validate_authority(store.read_json(task, r), task)
                                             for r in {e['authority_ref'] for _, e in entries if 'authority_ref' in e}})
        assert not analysis['problems'] or task == 'irrecoverable', (task, analysis['problems'])
        report[task] = {'outcome': final['lifecycle'], 'contract_revisions': revisions[::-1],
                        'criteria': {c['id']: c['status'] for c in evaluation['payload']['criteria']},
                        'journal': [e['phase'] + ':' + e.get('operation_class', e.get('outcome', '')) for _, e in entries],
                        'concerns': result['payload']['concerns'], 'legal': legal,
                        'offline_reproduced': True}
    for name, rows in read('journal-prefixes').items():
        assert rows['unchanged'] == rows['before'], name
    cognition = [json.loads(line) for line in (evidence / 'cognition.jsonl').read_text().splitlines()]
    assert all(n == 1 for n in Counter((r['task_id'], r['iteration']) for r in cognition).values())
    capabilities = [json.loads(line) for line in (evidence / 'capabilities.jsonl').read_text().splitlines()]
    attempts = Counter(r['operation_id'] for r in capabilities)
    # The only physical re-execution is the deliberate response-loss retry, and the
    # effect it retried was committed once.
    assert attempts.pop('response-loss/1') == 2 and all(n == 1 for n in attempts.values()), attempts
    effects = read('effects')
    assert [e['operation_id'] for e in effects] == ['irrecoverable/2', 'response-loss/1'], effects
    lost = journal.read(store, 'response-loss', read('response-loss-final')['journal_head'],
                        read('response-loss-final')['journal_length'])
    assert [(e['phase'], e['operation_id']) for _, e in lost if e.get('operation_id') == 'response-loss/1'] == [
        ('admitted', 'response-loss/1'), ('observed', 'response-loss/1')]
    child_contract = store.read_json(CHILD, read(f'{CHILD}-final')['contract_ref'])['payload']
    assert child_contract['criteria'][0]['provenance'] == {'source': 'parent_task', 'ref': PARENT}
    parent_final = read(f'{PARENT}-final')
    assert parent_final['children'][CHILD]['result_ref'] and parent_final['lifecycle'] == 'COMPLETED'
    denial = read('denial-final')
    assert denial['active_specialist'] == 'specialist' and read('checks')['denial/outcome/4']['restored_equal']
    reviews = [json.loads(line) for line in (evidence / 'reviews.jsonl').read_text().splitlines()]
    assert all(n == 1 for n in Counter((r['task_id'], r['criterion_id'], r['contract_revision'],
                                        r['evidence_digest']) for r in reviews).values())
    for path in (evidence / 'artifacts').glob('*/*'):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == path.name
    return {'outcome': 'PASS', 'tasks': report, 'cognitive_turns': len(cognition),
            'duplicate_cognitive_turns': 0, 'capability_executions': len(capabilities),
            'duplicate_capability_executions': 0, 'response_loss_retries': 1, 'duplicate_committed_effects': 0, 'semantic_reviews': len(reviews), 'duplicate_semantic_reviews': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restate-server', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new scratch directory for server/runtime data')
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
    (out / 'fixtures.json').write_bytes(encode({k: {x: v[x] for x in ('script', 'barriers', 'lose_effect_response', 'spawn') if x in v}
                                                for k, v in FIXTURES.items()}))
    save('fixtures', FIXTURES)
    (out / 'restate.toml').write_text(f'''cluster-name = "blaine-e10-probe"
node-name = "e10-probe"
base-dir = "{out / 'restate-data'}"
bind-ip = "127.0.0.1"
bind-port = 35322
advertised-host = "127.0.0.1"
listen-mode = "tcp"
auto-provision = true
default-journal-retention = "7 days"
[admin]
bind-address = "127.0.0.1:39270"
[ingress]
bind-address = "127.0.0.1:38280"
''')
    environment = {k: v for k, v in os.environ.items() if not k.startswith('RESTATE_')}
    environment.update(E10_PROBE_DIR=str(out), PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
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
                with socket.create_connection(('127.0.0.1', 39280), timeout=2):
                    return True
            except OSError:
                return False
        until(ready, f'{name} ready', 40)

    def kill(name, reason):
        process = processes.pop(name)
        process.kill()
        code = process.wait(timeout=10)
        assert code == -9, code
        events.append({'action': 'SIGKILL', 'process': name, 'exit_code': code, 'reason': reason})

    def call(task, handler, body=None):
        return http(INGRESS, f'/CognitiveTaskV1/{task}/{handler}', body)

    def refused(task, handler, body, code):
        try:
            call(task, handler, body)
        except urllib.error.HTTPError as error:
            assert error.code == code, (handler, error.code, error.read())
            return {'status_code': error.code, 'body': json.loads(error.read() or b'{}')}
        raise AssertionError(f'{handler} unexpectedly accepted')

    agent = PersonalAgent(RestateBinding(INGRESS))

    def amend_as_user(task, content):
        """Through the real Personal Agent binding, which establishes the user actor."""
        try:
            return {'status_code': 200, 'body': agent.execute({'operation': 'amend', 'task_id': task, 'amendment': content})}
        except ControlRejected as error:
            return {'status_code': int(str(error).rsplit('HTTP ', 1)[1].rstrip(')')), 'body': str(error)}

    def status(task):
        return call(task, 'status')['payload']

    def rows(task):
        return http(ADMIN, '/query', {'query': "SELECT id, index, raw, appended_at FROM sys_journal WHERE id IN "
                    f"(SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/{task}/run') ORDER BY index"})['rows']

    def snapshot(task, label):
        prefixes[f'{task}/{label}'] = {'before': rows(task)}

    def barrier(task, marker, reason, process='runtime'):
        probe = until(lambda: (p if (p := call(task, 'probe_status')).get('marker') == marker else None), task + ' ' + marker)
        snapshot(task, marker)
        kill(process, reason)
        start(process)
        restored = status(task)
        for key in ('contract_ref', 'contract_revision', 'journal_head', 'journal_length', 'completion_ref', 'artifacts',
                    'active_specialist', 'context_ref', 'decision_ref'):
            assert restored[key] == probe['state'][key], (task, marker, key)
        checks[f'{task}/{marker}'] = {'restored_equal': True, 'contract_revision': restored['contract_revision'],
                                      'journal_length': restored['journal_length']}
        call(task, 'release_probe', {'marker': marker})

    def waiting(task, input_type):
        return until(lambda: (s if (s := status(task)).get('lifecycle') == 'WAITING'
                              and s['wait']['input_type'] == input_type else None), f'{task} waiting {input_type}')

    def finish(task):
        final = until(lambda: (s if (s := status(task)).get('lifecycle') in ('COMPLETED', 'FAILED') and s['result_ref'] else None),
                      task + ' terminal')
        save(f'{task}-final', final)
        save(f'{task}-result', http(INGRESS, f'/restate/workflow/CognitiveTaskV1/{task}/attach', method='GET'))
        for key, value in prefixes.items():
            if key.startswith(task + '/'):
                final_rows = {row['index']: row for row in rows(task)}
                value['unchanged'] = [final_rows.get(row['index']) for row in value['before']]
        print(f"{task}: {final['lifecycle']}", flush=True)
        return final

    try:
        start('server')
        start('runtime')
        save('deployment', http(ADMIN, '/deployments', {'uri': ENDPOINT}))
        def submit(task):
            # One scenario at a time, so a SIGKILL never lands inside another Task's step.
            checks[f'{task}/submission'] = call(task, 'run/send', FIXTURES[task]['request'])

        submit('investigation')
        # Investigation: crash at contract retention, after evidence admission and
        # between admission and dispatch; server crash while waiting on the workspace.
        barrier('investigation', 'contract_retained/0', 'contract revision 0 retained before any effect')
        waiting('investigation', 'workspace_result')
        checks['investigation/invariant-waiver'] = amend_as_user('investigation', fx.amendment_content(
            'investigation', [{'op': 'waive', 'id': 'no-mutation', 'reason': 'Try to drop the invariant.'}]))
        assert checks['investigation/invariant-waiver']['status_code'] == 403
        forged = fx.amendment_content('investigation', [{'op': 'waive', 'id': 'no-mutation', 'reason': 'x'}])
        forged['payload']['actor'] = OPERATOR  # content claiming an operator actor through the user binding
        checks['investigation/forged-actor-via-binding'] = amend_as_user('investigation', forged)
        assert checks['investigation/forged-actor-via-binding']['status_code'] == 400
        checks['investigation/model-actor'] = refused('investigation', 'amend_contract', fx.amendment(
            'investigation', [{'op': 'waive', 'id': 'findings-cited', 'reason': 'x'}],
            actor={'kind': 'model', 'via': 'modify-constraints', 'binding': 'e10'}), 400)
        checks['investigation/bare-content'] = refused('investigation', 'amend_contract', fx.amendment_content(
            'investigation', [{'op': 'waive', 'id': 'findings-cited', 'reason': 'x'}]), 400)
        snapshot('investigation', 'workspace-wait')
        kill('server', 'Task waiting on a workspace result')
        start('server')
        waiting('investigation', 'workspace_result')
        checks['investigation/result'] = call('investigation', 'submit_workspace_result', fx.read_result('investigation'))
        checks['investigation/duplicate-result'] = refused('investigation', 'submit_workspace_result',
                                                           fx.read_result('investigation'), 409)
        barrier('investigation', 'receipt_admitted/1', 'read receipt admitted to the journal')
        barrier('investigation', 'admitted/2', 'capability admitted, not yet dispatched')
        finish('investigation')
        for task in ('denial', 'irrecoverable'):
            submit(task)
            waiting(task, 'workspace_result')
            call(task, 'submit_workspace_result', fx.read_result(task))
            if task == 'denial':
                # HANDOFF owner and specialist packet committed, then the runtime dies.
                barrier(task, 'outcome/4', 'HANDOFF committed before the next cognition')
            finish(task)

        # A joined child waits on a human decision; the runtime dies while both wait.
        submit(PARENT)
        waiting(CHILD, 'human_response')
        until(lambda: status(PARENT).get('lifecycle') == 'WAITING', 'parent waits on its child')
        snapshot(CHILD, 'child-human-wait')
        kill('runtime', 'child waiting on a human decision, parent waiting on the child')
        start('runtime')
        waiting(CHILD, 'human_response')
        child_request = parent_spec()[0]['payload']['completion'][0]['evidence']['request']
        checks['child-human/response'] = call(CHILD, 'submit_human_response', fx.human_response(CHILD, child_request, 'YES'))
        finish(CHILD)
        finish(PARENT)

        # Effect committed, step result lost: the retry must reuse the committed effect.
        submit('response-loss')
        until(lambda: (out / 'effect-committed.jsonl').exists(), 'effect committed before its step result')
        snapshot('response-loss', 'effect-committed')
        kill('runtime', 'fixture effect committed before Restate recorded the capability result')
        (out / 'release-effect').write_text('retry may return the existing receipt')
        start('runtime')
        finish('response-loss')

        # Human resume across runtime and server loss.
        submit('human-resume')
        waiting('human-resume', 'human_response')
        snapshot('human-resume', 'human-wait')
        kill('runtime', 'Task waiting on a human decision')
        kill('server', 'Task waiting on a human decision')
        start('server')
        start('runtime')
        wait = waiting('human-resume', 'human_response')
        request = fx.human_request('human-resume', 'decide', ('YES', 'NO'))
        checks['human-resume/response'] = call('human-resume', 'submit_human_response',
                                               fx.human_response('human-resume', request, 'NO'))
        checks['human-resume/duplicate-response'] = refused('human-resume', 'submit_human_response',
            fx.human_response('human-resume', request, 'YES', 'response-2'), 409)
        final = finish('human-resume')
        assert final['contract_revision'] == 0 and wait['wait']['wait_id'] == 'decide'

        # Concurrent amendments to one revision: exactly one wins; the winner is idempotent.
        submit('human-waiver')
        waiting('human-waiver', 'human_response')
        requests = [fx.amendment_content('human-waiver', [{'op': 'waive', 'id': 'c2', 'reason': f'Approval not needed ({name}).'}],
                                         request_id=name) for name in ('left', 'right')]
        outcomes = [None, None]
        def amend(index):
            outcomes[index] = amend_as_user('human-waiver', requests[index])
        threads = [threading.Thread(target=amend, args=(i,)) for i in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(30)
        codes = sorted(o['status_code'] for o in outcomes)
        assert codes == [200, 409], outcomes
        winner = requests[[o['status_code'] for o in outcomes].index(200)]
        checks['human-waiver/concurrent'] = outcomes
        checks['human-waiver/retry'] = amend_as_user('human-waiver', winner)
        assert checks['human-waiver/retry']['body']['payload']['outcome'] == 'ALREADY_SUBMITTED'
        barrier('human-waiver', 'amended/2', 'amendment applied, before re-evaluation')
        final = finish('human-waiver')
        assert final['contract_revision'] == 1
        checks['human-waiver/late-response'] = refused('human-waiver', 'submit_human_response', fx.human_response(
            'human-waiver', fx.human_request('human-waiver', 'decide', ('YES', 'NO')), 'YES'), 409)

        # Project policy: user text cannot waive it; only a matching operator exception can.
        submit('policy-exception')
        wait = waiting('policy-exception', 'text')
        waive = [{'op': 'waive', 'id': 'canonical-check', 'reason': 'Canonical check unavailable today.'}]
        checks['policy-exception/user'] = amend_as_user('policy-exception', fx.amendment_content('policy-exception', waive))
        assert checks['policy-exception/user']['status_code'] == 403
        named = {'rule': 'example-policy#canonical-check', 'digest': POLICY_DIGEST}
        checks['policy-exception/user-naming-the-rule'] = amend_as_user('policy-exception', fx.amendment_content(
            'policy-exception', waive, request_id='named', exception_for=named))
        assert checks['policy-exception/user-naming-the-rule']['status_code'] == 400
        edited = {'rule': 'example-policy#canonical-check', 'digest': 'sha256:' + 'e' * 64}
        checks['policy-exception/edited-policy-digest'] = refused('policy-exception', 'amend_contract',
            fx.amendment('policy-exception', waive, actor=OPERATOR, request_id='wrong', exception_for=edited), 403)
        checks['policy-exception/operator'] = call('policy-exception', 'amend_contract',
            fx.amendment('policy-exception', waive, actor=OPERATOR, request_id='exception', exception_for=named))
        stale = message('ExternalInput', {'wait_id': 'continue', 'task_revision': wait['wait']['task_revision'] + 1,
                                          'input_type': 'text', 'value': 'go'})
        checks['policy-exception/stale-input'] = refused('policy-exception', 'submit_input', stale, 409)
        call('policy-exception', 'submit_input', message('ExternalInput', {
            'wait_id': 'continue', 'task_revision': wait['wait']['task_revision'], 'input_type': 'text', 'value': 'go'}))
        finish('policy-exception')
        checks['policy-exception/terminal-amendment'] = refused('policy-exception', 'amend_contract',
            fx.amendment('policy-exception', waive, from_revision=1, actor=OPERATOR, request_id='late', exception_for=named), 409)

        save('checks', checks)
        save('journal-prefixes', prefixes)
        save('process-events', events)
        shutil.copytree(out / 'artifacts', evidence / 'artifacts')
        with sqlite3.connect(out / 'fixture.sqlite') as db:
            save('effects', [{'operation_id': op, 'receipt': json.loads(receipt)}
                             for op, _, receipt in db.execute('SELECT * FROM effects ORDER BY operation_id')])
        for name in ('cognition.jsonl', 'capabilities.jsonl', 'reviews.jsonl', 'events.jsonl', 'effect-committed.jsonl'):
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
                   versions=versions, live_model_calls=0, cloud_calls=0, workstation_or_ide=False)
    save('summary', summary)
    print(json.dumps({k: v for k, v in summary.items() if k != 'tasks'}, indent=2))


if __name__ == '__main__':
    main()
