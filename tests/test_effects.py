"""E2.0 effect contract units: lowering, receipts, attempts, reconciliation, verifiers."""
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest

from runtime.kernel import completion, effect_evidence, effects, journal
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import message
from runtime.kernel.execution import policy_gate
from runtime.kernel.routing import validate_grant

import effect_fixtures as ef

TASK = 'task-units'


class Fixture(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        self.store = ArtifactStore(root / 'artifacts')
        self.target = ef.FixtureTarget(root / 'target.sqlite')
        self.target.put_file(ef.CONFIG, ef.BEFORE)
        self.draft = self.store.put(TASK, ef.AFTER.encode())
        profiles = {name: profile.payload() for name, profile in ef.PROFILES.items()}
        self.authority = journal.compile_authority(TASK, ['workspace.write', 'workspace.exec', 'artifact.write'],
                                                   [ef.WORKSPACE], True, profiles=profiles)['payload']
        self.state = {'task_id': TASK, 'artifacts': {'draft': self.draft}, 'contract_revision': 0}

    def write_request(self, precondition=None, receipts=frozenset()):
        value = {'workspace_id': ef.WORKSPACE, 'path': ef.CONFIG, 'content_ref': self.draft,
                 'precondition': precondition or {'sha256': ef.SHA['before']}}
        return effects.lower(TASK, TASK + '/3', 'workspace.write', effects.validate_write_input(value), self.state,
                             self.store, 'artifact://task-units/sha256:' + 'a' * 64, self.authority, set(receipts))


class Lowering(Fixture):
    def test_write_request_binds_identity_precondition_and_content_digest(self):
        request = self.write_request()['payload']
        self.assertEqual((request['operation_id'], request['operation'], request['precondition']),
                         (TASK + '/3', 'write_file', {'sha256': ef.SHA['before']}))
        self.assertEqual((request['content_sha256'], request['content_bytes']), (ef.SHA['after'], len(ef.AFTER)))

    def test_receipt_precondition_lowers_to_the_admitted_evidence_digest(self):
        read = effects.read(self.target, TASK, TASK + '/1', effects.validate_read_input(
            {'form': 'file', 'workspace_id': ef.WORKSPACE, 'path': ef.CONFIG, 'artifact': 'current'}), self.store)
        with self.assertRaisesRegex(ValueError, 'not admitted'):
            self.write_request({'receipt': read['receipt_ref']})
        request = self.write_request({'receipt': read['receipt_ref']}, {read['receipt_ref']})['payload']
        self.assertEqual((request['precondition'], request['precondition_evidence']),
                         ({'sha256': ef.SHA['before']}, read['receipt_ref']))

    def test_inputs_reject_unsafe_or_unbounded_effects(self):
        base = {'workspace_id': ef.WORKSPACE, 'path': ef.CONFIG, 'content_ref': self.draft, 'precondition': {'absent': True}}
        for bad in ({**base, 'path': '/etc/passwd'}, {**base, 'path': '../x'}, {**base, 'path': 'file://x'},
                    {**base, 'precondition': {}}, {**base, 'precondition': {'mtime': 1}},
                    {**base, 'precondition': {'absent': True, 'sha256': 'a' * 64}}, {**base, 'mode': '0777'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                effects.validate_write_input(bad)
        self.state['artifacts']['big'] = big = self.store.put(TASK, b'x' * (effects.MAX_WRITE_BYTES + 1))
        with self.assertRaisesRegex(ValueError, 'size cap'):
            effects.lower(TASK, 'op', 'workspace.write', {**base, 'content_ref': big}, self.state, self.store,
                          'artifact://task-units/sha256:' + 'a' * 64, self.authority, set())
        for bad in ({'workspace_id': ef.WORKSPACE, 'profile': 'sh -c'}, {'workspace_id': ef.WORKSPACE, 'profile': 'x', 'cmd': 'rm'}):
            with self.assertRaises(ValueError):
                effects.validate_exec_input(bad)
        with self.assertRaisesRegex(ValueError, 'Arguments outside'):
            effects.admit_exec({'workspace_id': ef.WORKSPACE, 'profile': 'unit-tests', 'args': ['--init-script', 'x']}, self.authority)
        with self.assertRaisesRegex(ValueError, 'shell text'):
            effects.validate_profile({**ef.PROFILES['unit-tests'].payload(), 'executable': 'bash -c "x"'})

    def test_exec_request_pins_the_reviewed_profile(self):
        request = effects.lower(TASK, 'op', 'workspace.exec', {'workspace_id': ef.WORKSPACE, 'profile': 'unit-tests',
                                'args': ['--offline']}, self.state, self.store, 'artifact://task-units/sha256:' + 'a' * 64,
                                self.authority, set())['payload']
        self.assertEqual(request['command'], {'executable': './gradlew', 'args': ['--no-daemon', 'test', '--offline']})
        self.assertEqual(request['profile']['digest'], effects.profile_digest(ef.PROFILES['unit-tests'].payload()))


class Receipts(Fixture):
    def test_receipts_must_answer_the_exact_request_consistently(self):
        request = self.write_request()
        good = self.target.dispatch(request, {'content': ef.AFTER})
        self.assertEqual(effects.validate_receipt(good, request, self.store)['state'], 'applied')
        lying = deepcopy(good)
        lying['payload']['write']['readback_sha256'] = 'b' * 64
        other = deepcopy(good)
        other['payload']['operation_id'] = 'elsewhere'
        silent_conflict = deepcopy(good)
        silent_conflict['payload']['state'] = 'conflict'
        for bad in (lying, other, silent_conflict):
            with self.assertRaises(ValueError):
                effects.validate_receipt(bad, request, self.store)

    def test_dispatch_is_idempotent_per_operation_and_rejects_reuse(self):
        request = self.write_request()
        first = effects.attempt(self.target, request, {'content': ef.AFTER}, self.store)['payload']
        again = effects.attempt(self.target, request, {'content': ef.AFTER}, self.store)['payload']
        self.assertEqual((first['delivery'], again['delivery']), ('dispatched', 'recovered'))
        self.assertEqual(first['receipt'], again['receipt'])
        self.assertEqual(len(self.target.executions(TASK + '/3')), 1)
        with self.assertRaisesRegex(ValueError, 'reused'):
            changed = deepcopy(request)
            changed['payload']['content_bytes'] += 1
            self.target.dispatch(changed, {'content': ef.AFTER})

    def test_lost_response_and_unreachable_provider_are_uncertain_not_failure(self):
        self.target.set_fault('after_commit', 'lose_response')
        self.assertEqual(effects.attempt(self.target, self.write_request(), {'content': ef.AFTER}, self.store)['payload']['kind'],
                         'uncertain')
        self.target.set_fault('unavailable', True)
        self.assertEqual(effects.attempt(self.target, self.write_request({'absent': True}), {'content': ef.AFTER},
                                         self.store)['payload']['kind'], 'uncertain')
        self.assertEqual(effects.attempt(None, self.write_request(), {}, self.store)['payload']['kind'], 'not_dispatched')


class Cancellation(Fixture):
    def exec_request(self, op):
        return effects.lower(TASK, op, 'workspace.exec', {'workspace_id': ef.WORKSPACE, 'profile': 'unit-tests'},
                             self.state, self.store, 'artifact://task-units/sha256:' + 'a' * 64, self.authority, set())

    def test_completion_can_win_the_race_and_stop_is_never_non_occurrence(self):
        request = self.exec_request('x/1')
        self.target.behave('unit-tests', polls=1, exit_code=0, operation='x/1')
        self.assertEqual(effects.attempt(self.target, request, {}, self.store)['payload']['receipt']['payload']['state'], 'running')
        effects.poll(self.target, request, self.store)  # the process finishes first
        won = effects.cancel(self.target, request, self.store, 'requested')['payload']
        self.assertEqual((won['delivery'], won['receipt']['payload']['state']), ('completed_first', 'completed'))
        stopped_request = self.exec_request('x/2')
        self.target.behave('unit-tests', polls=99, operation='x/2')
        effects.attempt(self.target, stopped_request, {}, self.store)
        stopped = effects.cancel(self.target, stopped_request, self.store, 'timeout')['payload']['receipt']['payload']
        self.assertEqual((stopped['state'], stopped['exec']['started']), ('timed_out', True))
        with self.assertRaises(ValueError):
            effects.cancel(self.target, stopped_request, self.store, 'because')  # unknown reason is not a stop


class Reconciliation(Fixture):
    def reconcile(self, request):
        return effects.reconcile(self.target, request, self.store)['payload']['state']

    def test_receipt_decides_applied_and_authoritative_absence_decides_not_applied(self):
        request = self.write_request()
        self.target.set_fault('after_commit', 'lose_response')
        effects.attempt(self.target, request, {'content': ef.AFTER}, self.store)
        self.assertEqual(self.reconcile(request), effects.APPLIED)
        self.assertEqual(self.reconcile(self.write_request({'absent': True})), effects.NOT_APPLIED)

    def test_matching_hash_alone_never_attributes_the_write(self):
        self.target.set_fault('receipts_authoritative', False)
        self.target.put_file(ef.CONFIG, ef.AFTER)  # someone else made the same change
        self.assertEqual(self.reconcile(self.write_request()), effects.STILL_UNKNOWN)
        self.target.put_file(ef.CONFIG, ef.BEFORE)
        self.assertEqual(self.reconcile(self.write_request()), effects.STILL_UNKNOWN)
        self.target.put_file(ef.CONFIG, 'something else\n')
        self.assertEqual(self.reconcile(self.write_request()), effects.DIFFERENT_STATE)
        self.target.set_fault('unavailable', True)
        self.assertEqual(self.reconcile(self.write_request()), effects.STILL_UNKNOWN)
        self.assertEqual(effects.reconcile(None, self.write_request(), self.store)['payload']['state'], effects.STILL_UNKNOWN)


class JournalFixture(Fixture):
    def chain(self, entries):
        head, length = None, 0
        authority = self.store.put_json(TASK, journal.compile_authority(TASK, ['workspace.write'], [ef.WORKSPACE], True))
        for entry in entries:
            head = journal.append(self.store, TASK, head, length, {**entry, **({'authority_ref': authority}
                                  if entry['phase'] in ('admitted', 'denied') else {})})
            length += 1
        return completion.load_journal({'task_id': TASK, 'journal_head': head, 'journal_length': length,
                                        'authority_ref': authority}, self.store)

    def admitted(self, op='t/1'):
        return {'phase': 'admitted', 'decision_id': op, 'operation_id': op, 'capability': 'workspace.write',
                'operation_class': 'workspace.write', 'provider': 'fixture', 'operation': 'write_file',
                'request_digest': 'sha256:' + 'c' * 64, 'contract_revision': 0, 'workspace_id': ef.WORKSPACE}

    def dispatched(self, op='t/1'):
        request = self.store.put_json(TASK, self.write_request())
        return {'phase': 'dispatched', 'operation_id': op, 'request_ref': request, 'request_digest': 'sha256:' + 'd' * 64}

    def observed(self, outcome, op='t/1'):
        return {'phase': 'observed', 'operation_id': op, 'outcome': outcome,
                'receipt_ref': self.store.put_json(TASK, message('EffectOutcome', {'kind': outcome}))}

    def reconciled(self, state, op='t/1'):
        return {'phase': 'reconciled', 'operation_id': op, 'state': state, 'evidence_ref': self.draft}


class JournalLifecycle(JournalFixture):
    def test_effect_lifecycle_integrity(self):
        cases = {
            'dispatch without admission': [self.dispatched()],
            'observed without dispatch': [self.admitted(), self.observed('success')],
            'dispatched then not_dispatched': [self.admitted(), self.dispatched(), self.observed('not_dispatched')],
            'reconciled without uncertainty': [self.admitted(), self.dispatched(), self.observed('success'), self.reconciled('APPLIED')],
        }
        for name, entries in cases.items():
            with self.subTest(name):
                self.assertTrue(self.chain(entries)['analysis']['problems'])
        good = self.chain([self.admitted(), self.observed('not_dispatched')])
        self.assertEqual(good['analysis']['problems'], [])

    def test_effects_reconciled_is_unknown_until_concluded(self):
        predicates = [{'name': 'no_target_effect', 'allowed': ['workspace.write']}, {'name': 'effects_reconciled'}]
        open_ = self.chain([self.admitted(), self.dispatched(), self.observed('uncertain'), self.reconciled('STILL_UNKNOWN')])
        self.assertEqual(journal.verify(predicates, open_['analysis'], open_['authorities'])[0], 'unknown')
        closed = self.chain([self.admitted(), self.dispatched(), self.observed('uncertain'), self.reconciled('NOT_APPLIED')])
        self.assertEqual(journal.verify(predicates, closed['analysis'], closed['authorities'])[0], 'satisfied')
        forbidden = self.chain([self.admitted(), self.dispatched(), self.observed('uncertain')])
        self.assertEqual(journal.verify([{'name': 'no_target_effect'}, {'name': 'effects_reconciled'}],
                                        forbidden['analysis'], forbidden['authorities'])[0], 'failed')  # failure dominates


class UnresolvedInvariantInput(JournalFixture):
    def test_only_target_effects_are_unresolved(self):
        internal = {**self.admitted('t/2'), 'capability': 'artifact.write', 'operation_class': 'task.artifact.write'}
        internal.pop('workspace_id')
        read = {**self.admitted('t/3'), 'capability': 'workspace.read', 'operation_class': 'workspace.read'}
        facts = self.chain([internal, self.observed('uncertain', 't/2'), read, self.observed('uncertain', 't/3')])
        self.assertEqual(facts['analysis']['unresolved_effects'], [])
        facts = self.chain([self.admitted(), self.dispatched()])  # in flight
        self.assertEqual(facts['analysis']['unresolved_effects'], ['t/1'])
        facts = self.chain([self.admitted(), self.dispatched(), self.observed('uncertain'), self.reconciled('STILL_UNKNOWN')])
        self.assertEqual(facts['analysis']['unresolved_effects'], ['t/1'])
        facts = self.chain([self.admitted(), self.dispatched(), self.observed('uncertain'), self.reconciled('APPLIED')])
        self.assertEqual(facts['analysis']['unresolved_effects'], [])


def record(op, status, path=ef.CONFIG, before=None, after=None, at=0, exit_code=None, result=None, cls='workspace.write',
           profile=None):
    receipt = None
    if status in ('applied', 'conflict'):
        receipt = {'state': status, 'write': {'workspace_id': ef.WORKSPACE, 'path': path, 'before': before or {'sha256': ef.SHA['before']},
                   **({'after': after, 'readback_sha256': after['sha256']} if after else {})}}
    elif status in ('completed', 'timed_out', 'canceled'):
        receipt = {'state': status, 'exec': {'started': True, 'cleanup': 'confirmed', 'exit_code': exit_code, 'result': result or {}}}
    request = ({'operation': 'write_file', 'workspace_id': ef.WORKSPACE, 'path': path, 'content_ref': 'c', 'precondition_evidence': None}
               if cls == 'workspace.write' else {'operation': 'run_profile', 'workspace_id': ef.WORKSPACE, 'profile': {'id': profile}})
    return {'operation_id': op, 'operation_class': cls, 'admitted_at': at, 'dispatched_at': at + 1, 'settled_at': at + 2,
            'request': request, 'receipt': receipt, 'receipt_ref': 'r-' + op if receipt else None, 'status': status}


class Verifiers(unittest.TestCase):
    change = {'kind': 'change_set', 'version': 1, 'workspace_id': ef.WORKSPACE, 'predicates': [
        {'name': 'changed', 'paths': [ef.CONFIG]}, {'name': 'expected_content', 'path': ef.CONFIG, 'sha256': ef.SHA['after']},
        {'name': 'only_paths', 'allowed': [ef.CONFIG]}]}
    tests = {'kind': 'capability_result', 'version': 1, 'operation_class': 'workspace.exec', 'profile': 'unit-tests',
             'predicates': [{'name': 'exit_code', 'equals': 0}, {'name': 'result_after_last_change'}]}

    def change_set(self, effects_):
        return effect_evidence.verify_change_set(effect_evidence.validate_change_params(self.change), effects_, lambda r: True)[0]

    def test_change_set(self):
        applied = record('w1', 'applied', after={'sha256': ef.SHA['after']})
        self.assertEqual(self.change_set([applied]), 'satisfied')
        self.assertEqual(self.change_set([]), 'pending')
        self.assertEqual(self.change_set([record('w1', 'conflict')]), 'pending')  # a conflict changed nothing
        stray = record('w2', 'applied', path='service/other.txt', before={'absent': True}, after={'sha256': 'e' * 64}, at=3)
        self.assertEqual(self.change_set([applied, stray]), 'failed')
        wrong = record('w1', 'applied', after={'sha256': 'f' * 64})
        self.assertEqual(self.change_set([wrong]), 'failed')
        self.assertEqual(self.change_set([applied, record('w3', 'uncertain', at=5)]), 'unknown')
        fixed = record('w4', 'applied', before={'sha256': 'f' * 64}, after={'sha256': ef.SHA['after']}, at=7)
        self.assertEqual(self.change_set([record('w3', 'uncertain'), fixed]), 'satisfied')  # later applied write fixes net state
        reverted = record('w5', 'applied', before={'sha256': ef.SHA['after']}, after={'sha256': ef.SHA['before']}, at=9)
        self.assertEqual(self.change_set([applied, reverted]), 'pending')  # net change is what counts

    def test_capability_result(self):
        verify = lambda effects_: effect_evidence.verify_result(effect_evidence.validate_result_params(self.tests), effects_)[0]
        write = record('w1', 'applied', after={'sha256': ef.SHA['after']}, at=0)
        passed = record('x1', 'completed', cls='workspace.exec', profile='unit-tests', exit_code=0, at=4)
        self.assertEqual(verify([]), 'pending')
        self.assertEqual(verify([write, passed]), 'satisfied')
        self.assertEqual(verify([write, record('x1', 'completed', cls='workspace.exec', profile='unit-tests', exit_code=1, at=4)]), 'failed')
        self.assertEqual(verify([write, record('x1', 'timed_out', cls='workspace.exec', profile='unit-tests', at=4)]), 'failed')
        self.assertEqual(verify([write, record('x1', 'uncertain', cls='workspace.exec', profile='unit-tests', at=4)]), 'unknown')
        stale = record('w2', 'applied', after={'sha256': 'e' * 64}, at=8)
        self.assertEqual(verify([write, passed, stale]), 'failed')  # tests ran before the last change
        self.assertEqual(verify([write, passed, record('w2', 'conflict', at=8)]), 'satisfied')
        self.assertEqual(verify([record('x0', 'not_dispatched', cls='workspace.exec', profile='unit-tests')]), 'pending')

    def test_parameters_are_closed_and_provider_neutral(self):
        for bad in ({**self.tests, 'operation_class': 'workspace.read'}, {**self.tests, 'predicates': [{'name': 'llm_says_ok'}]},
                    {**self.tests, 'predicates': [{'name': 'exit_code', 'equals': '0'}]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                effect_evidence.validate_result_params(bad)
        with self.assertRaises(ValueError):
            effect_evidence.validate_change_params({**self.change, 'predicates': [{'name': 'git_diff_clean'}]})


class Authority(Fixture):
    def decision(self, action):
        return message('CognitiveDecision', {'task_id': TASK, 'task_revision': 0, 'turn_id': TASK + '/1', 'next_action': action})

    def test_proposal_is_not_authority(self):
        spec = {'capabilities': ['workspace.write', 'workspace.exec'], 'autonomy': {'allowed': ['workspace.write', 'workspace.exec']},
                'completion': []}
        state = {'task_id': TASK, 'revision': 0, 'iteration': 1, 'lifecycle': 'RUNNING', 'artifacts': {'draft': self.draft},
                 'effects': {}}
        write = ef.write(self.draft, sha256=ef.SHA['before'])
        self.assertEqual(policy_gate(self.decision(write), state, spec, None, None, self.authority)['outcome'], 'allow')
        self.assertIn('not in effective authority', policy_gate(self.decision(write), state, spec)['reason'])
        other = deepcopy(write)
        other['input']['workspace_id'] = 'wsp-elsewhere'
        self.assertEqual(policy_gate(self.decision(other), state, spec, None, None, self.authority)['outcome'], 'deny')
        blocked = {**state, 'effects': {TASK + '/0': {'status': 'uncertain'}}}
        self.assertIn('reconciled first', policy_gate(self.decision(write), blocked, spec, None, None, self.authority)['reason'])
        self.assertEqual(policy_gate(self.decision(ef.run('slow-build')), state, spec, None, None,
                                     {**self.authority, 'profiles': {}})['outcome'], 'deny')

    def test_grant_carries_effect_authority_as_envelope_data(self):
        grant = validate_grant({'capabilities': ['workspace.write'], 'workspaces': [ef.WORKSPACE],
                                'profiles': ['unit-tests'], 'ask_before': ['workspace.write']})
        self.assertEqual((grant['workspaces'], grant['profiles'], grant['ask_before']),
                         ([ef.WORKSPACE], ['unit-tests'], ['workspace.write']))
        self.assertEqual(validate_grant({'capabilities': ['artifact.write']}),
                         {'capabilities': ['artifact.write'], 'escalation_binding': None})  # E1 grants unchanged
        with self.assertRaises(ValueError):
            journal.validate_authority(journal.compile_authority(TASK, ['artifact.write'], [], True,
                                                                 ask_before=['artifact.write']), TASK)


if __name__ == '__main__':
    unittest.main()
