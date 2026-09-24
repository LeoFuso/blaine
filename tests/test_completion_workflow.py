"""E1.0 Completion Contract lifecycle through the workflow, with journaled replay.

Uses the deterministic Restate stand-in in completion_harness; the real-server
SIGKILL acceptance is experiments/personal-agent-hub/e1-0.
"""
from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import restate

from runtime.kernel import completion, journal
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import message
from runtime.kernel.execution import Capabilities

from completion_harness import Crash, Harness
import completion_fixtures as fx

TASK = 'task-e10'
GOOD = hashlib.sha256(b'GOOD').hexdigest()


class Cognition:
    """Scripted cognition by iteration; records every physical call."""
    def __init__(self, script):
        self.script, self.calls = script, []

    def __call__(self, packet):
        turn = packet['payload']
        self.calls.append(turn['iteration'])
        return fx.decision(packet, self.script[turn['iteration']](turn))


class Audited(Capabilities):
    """Checks the structural invariant: dispatch only after a journaled admission."""
    def __init__(self, store, path, harness_ref):
        super().__init__(store, path)
        self.harness_ref, self.executed = harness_ref, Counter()

    def execute(self, request):
        payload = request['payload']
        state = self.harness_ref[0].state(payload['task_id'])
        entries = journal.read(self.store, payload['task_id'], state['journal_head'], state['journal_length'])
        admitted = [e for _, e in entries if e['phase'] == 'admitted' and e['operation_id'] == payload['operation_id']]
        assert len(admitted) == 1 and entries[-1][1] is admitted[0], 'dispatch without a preceding admission'
        self.executed[payload['operation_id']] += 1
        return super().execute(request)


class Reviewer:
    def __init__(self, verdict='satisfied', confidence='high'):
        self.verdict, self.confidence, self.calls = verdict, confidence, []

    def __call__(self, packet):
        request = packet['payload']
        self.calls.append(request['evidence_digest'])
        return message('SemanticReviewResult', {**{k: request[k] for k in (
            'task_id', 'criterion_id', 'contract_revision', 'evidence_digest')},
            'verdict': self.verdict, 'confidence': self.confidence, 'rationale': 'Stub judgement.',
            'evidence_refs': [item['ref'] for item in request['evidence']]})


def receipt(turn):
    """Cognition cites the admitted receipt its packet references."""
    receipts = [item['source'] for item in turn['context']
                if item['authority'] == 'artifact' and item['content'].get('name') == 'receipt']
    assert len(receipts) == 1, receipts
    return receipts[0]


def cite(turn):
    return fx.write('findings', fx.findings(receipt(turn)))


def fabricate(turn):
    return fx.write('findings', fx.findings(receipt(turn), quote='return Response.serverError(); // fabricated'))


class Base(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.store = ArtifactStore(self.root / 'artifacts')
        self.checkpoints = []

    def harness(self, script, crash_at=(), **options):
        pending = set(crash_at)
        async def checkpoint(ctx, stage, state):
            self.checkpoints.append((stage, deepcopy(state)))
            if stage in pending:
                pending.discard(stage)
                raise Crash(stage)
        holder = []
        self.cognition = Cognition(script)
        self.capabilities = Audited(self.store, self.root / 'fixture.sqlite', holder)
        harness = Harness(self.store, self.cognition, self.capabilities, checkpoint=checkpoint, **options)
        holder.append(harness)
        return harness

    async def drive(self, harness, key=TASK, request=None):
        """Invoke, replaying after every simulated crash, until return or suspension."""
        for _ in range(16):
            try:
                return await harness.invoke(key, request)
            except Crash:
                request = None
        self.fail('Too many crashes')

    def chain(self, result, key=TASK):
        """TaskResult -> evaluation -> contract revision -> journal, from artifacts only."""
        evaluation = self.store.read_json(key, result['payload']['completion_ref'])
        contract = self.store.read_json(key, evaluation['payload']['contract_ref'])
        entries = journal.read(self.store, key, evaluation['payload']['journal_head'], evaluation['payload']['journal_length'])
        return evaluation, contract, entries

    def at(self, stage, iteration):
        """The checkpointed state (checkpoints also re-fire on replay; the last wins)."""
        return [s for name, s in self.checkpoints if name == stage and s['iteration'] == iteration][-1]

    def statuses(self, evaluation):
        return {c['id']: c['status'] for c in evaluation['payload']['criteria']}


class Investigation(Base):
    async def investigate(self, *writes, reviewer=None, crash_at=(), request=None):
        script = {2 + index: write for index, write in enumerate(writes)}
        harness = self.harness(script, crash_at=crash_at, semantic_reviewer=reviewer)
        self.assertIsNone(await self.drive(harness, request=request or fx.investigation_request(TASK)))
        waiting = harness.state(TASK)
        self.assertEqual((waiting['lifecycle'], waiting['wait']['input_type']), ('WAITING', 'workspace_result'))
        receipt = await harness.call(TASK, 'submit_workspace_result', fx.read_result(TASK))
        self.assertEqual(receipt['payload']['outcome'], 'ACCEPTED')
        return harness, await self.drive(harness)

    async def test_cited_findings_complete_and_result_explains_why(self):
        harness, result = await self.investigate(cite)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        evaluation, contract, entries = self.chain(result)
        self.assertEqual(evaluation['version'], 2)
        self.assertEqual(evaluation['payload']['contract_ref'], harness.state(TASK)['contract_ref'])
        self.assertEqual(contract['payload']['revision'], 0)
        self.assertEqual(self.statuses(evaluation), {
            'c1': 'satisfied', 'no-mutation': 'satisfied', 'workspace-scope': 'satisfied',
            'code-path-inspected': 'satisfied', 'findings-cited': 'satisfied', 'conclusion-explicit': 'satisfied',
            'cause-supported': 'unknown'})  # ADVISORY semantic without a deployed reviewer never blocks
        self.assertTrue(evaluation['payload']['legality']['legal'])
        self.assertTrue(any('Advisory cause-supported unknown' in c for c in result['payload']['concerns']))
        self.assertEqual([(e['phase'], e.get('operation_class')) for _, e in entries], [
            ('admitted', 'workspace.read'), ('observed', None), ('admitted', 'task.artifact.write'), ('observed', None)])
        receipt_ref = entries[1][1]['receipt_ref']
        self.assertIn(receipt_ref, next(c for c in evaluation['payload']['criteria'] if c['id'] == 'findings-cited')['evidence_refs'])
        self.assertEqual(self.store.read_json(TASK, receipt_ref)['kind'], 'WorkspaceReadReceipt')
        # Offline reproduction from retained artifacts and the Task state it names.
        final = harness.state(TASK)
        again = completion.evaluate_contract(contract['payload'], final['contract_ref'], final, self.store)
        self.assertEqual(again, evaluation)
        self.assertEqual(self.capabilities.executed, Counter({TASK + '/1': 1, TASK + '/2': 1}))

    async def test_fabricated_quote_fails_then_verified_findings_complete(self):
        harness, result = await self.investigate(fabricate, cite)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        after_fabrication = self.store.read_json(TASK, self.at('verification-effect', 2)['completion_ref'])
        self.assertEqual(self.statuses(after_fabrication)['findings-cited'], 'failed')
        self.assertIn('Quote not present', next(c['detail'] for c in after_fabrication['payload']['criteria']
                                                if c['id'] == 'findings-cited'))
        self.assertEqual(self.at('verification-effect', 2)['lifecycle'], 'RUNNING')
        self.assertEqual(self.cognition.calls, [2, 3])

    async def test_model_complete_is_neither_necessary_nor_sufficient(self):
        harness, result = await self.investigate(lambda turn: {'type': 'COMPLETE'}, cite)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        requested = self.at('verification-request', 2)
        self.assertEqual(requested['lifecycle'], 'RUNNING')
        self.assertEqual(self.statuses(self.store.read_json(TASK, requested['completion_ref']))['findings-cited'], 'pending')

    async def test_semantic_review_cannot_override_deterministic_failure(self):
        reviewer = Reviewer('satisfied', 'high')
        harness, result = await self.investigate(fabricate, cite, reviewer=reviewer)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        contradicted = self.store.read_json(TASK, self.at('verification-effect', 2)['completion_ref'])['payload']
        self.assertEqual({c['id']: c['status'] for c in contradicted['criteria']}['cause-supported'], 'unknown')
        self.assertFalse(contradicted['legality']['legal'])
        self.assertTrue(any('deterministic verdict stands' in c for c in contradicted['concerns']))
        final = self.statuses(self.chain(result)[0])
        self.assertEqual(final['cause-supported'], 'satisfied')
        # One journaled call per (revision, evidence) state with ready dependencies.
        self.assertEqual(len(reviewer.calls), len(set(reviewer.calls)))

    async def test_low_confidence_semantic_stays_unknown_and_advisory(self):
        harness, result = await self.investigate(cite, reviewer=Reviewer('satisfied', 'low'))
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        self.assertEqual(self.statuses(self.chain(result)[0])['cause-supported'], 'unknown')

    async def test_required_semantic_escalates_to_human_and_waits(self):
        request = fx.human_request(TASK, 'review-cause', ('SUPPORTED', 'NOT_SUPPORTED'))
        semantic = fx.semantic_criterion(level='REQUIRED', source='user', on_low='request_human',
                                         artifact='cause-review', request=request, accept=['SUPPORTED'])
        contract = fx.investigation_contract(TASK, semantic=False, extra=[semantic])
        publish = lambda turn: {'type': 'INVOKE_CAPABILITY', 'capability': 'human.request',
                                'input': {'request': next(c['request'] for c in turn['contract']['criteria']
                                                          if c['id'] == 'cause-supported')}}
        request_message = fx.investigation_request(TASK, contract=contract, extra_capabilities=('human.request',))
        harness, result = await self.investigate(cite, publish, reviewer=Reviewer('satisfied', 'low'),
                                                 request=request_message)
        self.assertIsNone(result)
        state = harness.state(TASK)
        self.assertEqual((state['lifecycle'], state['wait']['input_type']), ('WAITING', 'human_response'))
        self.assertEqual(self.statuses(self.store.read_json(TASK, state['completion_ref']))['cause-supported'], 'waiting_human')
        await harness.call(TASK, 'submit_human_response', fx.human_response(TASK, request, 'SUPPORTED'))
        result = await self.drive(harness)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        self.assertEqual(self.statuses(self.chain(result)[0])['cause-supported'], 'satisfied')

    async def test_duplicate_results_are_admitted_once(self):
        harness, result = await self.investigate(cite)
        with self.assertRaises(restate.TerminalError) as late:
            await harness.call(TASK, 'submit_workspace_result', fx.read_result(TASK))
        self.assertEqual(late.exception.status_code, 409)
        _, _, entries = self.chain(result)
        self.assertEqual(Counter(e['operation_id'] for _, e in entries if e['phase'] == 'observed'),
                         Counter({TASK + '/1': 1, TASK + '/2': 1}))
        state = harness.state(TASK)
        contract = self.store.read_json(TASK, state['contract_ref'])['payload']
        first = self.store.put_json(TASK, completion.evaluate_contract(contract, state['contract_ref'], state, self.store))
        self.assertEqual(first, self.store.put_json(TASK, completion.evaluate_contract(contract, state['contract_ref'], state, self.store)))

    async def test_crash_and_replay_reproduce_identical_durable_state(self):
        baseline_harness, baseline = await self.investigate(fabricate, cite, reviewer=Reviewer())
        baseline_state = baseline_harness.state(TASK)
        self.store = ArtifactStore(self.root / 'replayed')  # fresh store: same content, same refs
        self.checkpoints = []
        reviewer = Reviewer()
        crashes = ('contract_retained', 'admitted', 'receipt_admitted', 'verification-effect', 'decision')
        harness, result = await self.investigate(fabricate, cite, reviewer=reviewer, crash_at=crashes)
        self.assertEqual(result, baseline)
        state = harness.state(TASK)
        for key in ('contract_ref', 'contract_revision', 'journal_head', 'journal_length', 'completion_ref',
                    'result_ref', 'authority_ref', 'semantic_reviews', 'artifacts'):
            self.assertEqual(state[key], baseline_state[key], key)
        self.assertEqual(set(self.capabilities.executed.values()), {1})
        self.assertEqual(self.cognition.calls, [2, 3])
        self.assertEqual(len(reviewer.calls), len(set(reviewer.calls)))
        self.assertGreater(harness.tasks[TASK].invocations, len(crashes))

    async def test_policy_denial_is_journaled_and_reported(self):
        effect = lambda turn: {'type': 'INVOKE_CAPABILITY', 'capability': 'fixture.effect', 'input': {'value': 'x'}}
        harness, result = await self.investigate(effect, cite)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        _, _, entries = self.chain(result)
        denied = [e for _, e in entries if e['phase'] == 'denied']
        self.assertEqual([(e['capability'], e['operation_class']) for e in denied], [('fixture.effect', 'external.effect')])
        self.assertNotIn(TASK + '/2', self.capabilities.executed)
        self.assertTrue(any('PolicyGate denied 1' in c for c in result['payload']['concerns']))

    async def test_admitted_mutation_fails_the_invariant_irrecoverably(self):
        effect = lambda turn: {'type': 'INVOKE_CAPABILITY', 'capability': 'fixture.effect', 'input': {'value': 'x'}}
        request = fx.investigation_request(TASK, extra_capabilities=('fixture.effect',))
        harness, result = await self.investigate(effect, cite, request=request)
        self.assertEqual(result['payload']['outcome'], 'FAILED')
        self.assertIn('Invariant criteria failed: no-mutation', result['payload']['concerns'][0])
        evaluation, _, _ = self.chain(result)
        self.assertEqual(self.statuses(evaluation)['no-mutation'], 'failed')
        self.assertEqual(self.cognition.calls, [2])

    async def test_cognition_cannot_change_the_contract(self):
        attempts = [lambda turn: {'type': 'AMEND_CONTRACT', 'operations': [{'op': 'waive', 'id': 'findings-cited'}]},
                    lambda turn: fx.write('contract', {'criteria': []}), cite]
        harness, result = await self.investigate(*attempts)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        self.assertEqual(harness.state(TASK)['contract_revision'], 0)
        outcome = next(s for stage, s in self.checkpoints if stage == 'outcome' and s['iteration'] == 2)
        denial = self.store.read_json(TASK, outcome['observation_ref'])
        self.assertEqual((denial['kind'], denial['payload']['outcome']), ('PolicyDecision', 'deny'))
        _, contract, entries = self.chain(result)
        self.assertEqual(contract['payload'], self.store.read_json(TASK, outcome['contract_ref'])['payload'])
        self.assertNotIn('contract', harness.state(TASK)['contract_ref'])
        self.assertEqual([e['phase'] for _, e in entries].count('denied'), 0)  # not a capability


class HumanBoundary(Base):
    def spec(self):
        self.request = fx.human_request(TASK, 'decide', ('YES', 'NO'))
        return message('TaskSpec', {'objective': 'Produce and approve the answer.', 'completion': [
            {'criterion': 'Exact answer', 'evidence': {'artifact': 'answer', 'sha256': GOOD}},
            {'criterion': 'Human decided', 'evidence': {'artifact': 'decision', 'verifier': 'human_response',
                                                         'request': self.request}}],
            'capabilities': ['artifact.write', 'human.request'],
            'autonomy': {'allowed': ['artifact.write', 'human.request']}})

    def script(self):
        return {1: lambda turn: fx.write('answer', 'GOOD'),
                2: lambda turn: {'type': 'INVOKE_CAPABILITY', 'capability': 'human.request',
                                 'input': {'request': turn['completion'][1]['evidence']['request']}},
                3: lambda turn: {'type': 'COMPLETE'}}

    async def wait_for_human(self, crash_at=()):
        harness = self.harness(self.script(), crash_at=crash_at)
        self.assertIsNone(await self.drive(harness, request=self.spec()))
        state = harness.state(TASK)
        self.assertEqual((state['lifecycle'], state['wait']['input_type'], state['wait']['wait_id']),
                         ('WAITING', 'human_response', 'decide'))
        return harness, state

    async def test_v0_human_criterion_waits_and_the_same_task_resumes(self):
        harness, waiting = await self.wait_for_human(crash_at=('suspended',))
        evaluation = self.store.read_json(TASK, waiting['completion_ref'])
        self.assertEqual(self.statuses(evaluation), {'c1': 'satisfied', 'c2': 'waiting_human'})
        self.assertIn('REQUIRED c2 is waiting_human', evaluation['payload']['legality']['blockers'])
        await harness.call(TASK, 'submit_human_response', fx.human_response(TASK, self.request, 'NO'))
        result = await self.drive(harness)
        self.assertEqual(result['payload']['task_id'], TASK)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        final = harness.state(TASK)
        for key in ('contract_ref', 'spec_ref', 'authority_ref', 'request_digest'):
            self.assertEqual(final[key], waiting[key])
        self.assertEqual(final['journal_length'], waiting['journal_length'])
        self.assertEqual({k: v for k, v in final['artifacts'].items() if k in waiting['artifacts']}, waiting['artifacts'])
        with self.assertRaises(restate.TerminalError) as duplicate:
            await harness.call(TASK, 'submit_human_response', fx.human_response(TASK, self.request, 'YES', 'response-2'))
        self.assertEqual(duplicate.exception.status_code, 409)

    async def test_user_waiver_during_human_wait_completes_visibly(self):
        harness, waiting = await self.wait_for_human()
        waive = fx.amendment(TASK, [{'op': 'waive', 'id': 'c2', 'reason': 'Approval no longer needed.'}])
        receipt = await harness.call(TASK, 'amend_contract', waive)
        self.assertEqual(receipt['payload']['outcome'], 'SUBMITTED')
        result = await self.drive(harness)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        evaluation, contract, _ = self.chain(result)
        self.assertEqual(self.statuses(evaluation), {'c1': 'satisfied', 'c2': 'waived'})
        self.assertEqual(contract['payload']['revision'], 1)
        self.assertEqual(contract['payload']['previous_ref'], waiting['contract_ref'])
        amendment = self.store.read_json(TASK, contract['payload']['amendment_ref'])['payload']
        self.assertEqual((amendment['actor']['kind'], amendment['from_revision'], amendment['to_revision']), ('user', 0, 1))
        self.assertEqual(self.store.read_json(TASK, amendment['actor']['ref']), waive)
        self.assertTrue(any('c2 waived, not satisfied' in c for c in result['payload']['concerns']))
        with self.assertRaises(restate.TerminalError):
            await harness.call(TASK, 'submit_human_response', fx.human_response(TASK, self.request, 'YES'))

    async def test_amendments_are_authorized_compare_and_set_and_idempotent(self):
        harness, _ = await self.wait_for_human()
        async def rejected(request, status):
            with self.assertRaises(restate.TerminalError) as error:
                await harness.call(TASK, 'amend_contract', request)
            self.assertEqual(error.exception.status_code, status, error.exception.message)
            return error.exception.message
        self.assertIn('only the user', await rejected(fx.amendment(TASK, [{'op': 'waive', 'id': 'c2', 'reason': 'x'}],
            actor={'kind': 'operator', 'via': 'policy_exception',
                   'exception_for': {'rule': 'r', 'digest': 'sha256:' + 'a' * 64}}), 403))
        await rejected(fx.amendment(TASK, [{'op': 'waive', 'id': 'missing', 'reason': 'x'}]), 400)
        await rejected(fx.amendment(TASK, [{'op': 'waive', 'id': 'c1', 'reason': 'x'}], from_revision=3), 409)
        first = fx.amendment(TASK, [{'op': 'waive', 'id': 'c2', 'reason': 'First.'}], request_id='first')
        second = fx.amendment(TASK, [{'op': 'rebind', 'id': 'c1', 'verifier': {'kind': 'artifact_digest', 'version': 1,
                              'artifact': 'answer', 'sha256': 'f' * 64}}], request_id='second')
        self.assertEqual((await harness.call(TASK, 'amend_contract', first))['payload']['outcome'], 'SUBMITTED')
        self.assertIn('already amended', await rejected(second, 409))
        self.assertEqual((await harness.call(TASK, 'amend_contract', first))['payload']['outcome'], 'ALREADY_SUBMITTED')
        result = await self.drive(harness)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        self.assertEqual(harness.tasks[TASK].executions['amend/1'], 1)
        self.assertEqual(harness.state(TASK)['contract_revision'], 1)
        self.assertEqual((await harness.call(TASK, 'amend_contract', first))['payload']['outcome'], 'ALREADY_SUBMITTED')
        await rejected(fx.amendment(TASK, [{'op': 'waive', 'id': 'c1', 'reason': 'x'}], from_revision=1), 409)  # terminal


class Revisions(Base):
    def spec(self):
        return message('TaskSpec', {'objective': 'Produce the answer.', 'completion': [
            {'criterion': 'Exact answer', 'evidence': {'artifact': 'answer', 'sha256': GOOD}}],
            'capabilities': ['artifact.write'], 'autonomy': {'allowed': ['artifact.write']}})

    async def test_legality_uses_the_current_revision(self):
        harness = self.harness({1: lambda turn: {'type': 'WAIT', 'wait_id': 'go', 'input_type': 'text'},
                                2: lambda turn: fx.write('answer', 'GOOD'),
                                3: lambda turn: fx.write('extra', 'MORE')}, crash_at=('amended',))
        self.assertIsNone(await self.drive(harness, request=self.spec()))
        added = {'id': 'extra', 'requirement': 'The extra deliverable exists.', 'level': 'REQUIRED',
                 'provenance': {'source': 'user'}, 'verifier': {'kind': 'artifact_digest', 'version': 1,
                 'artifact': 'extra', 'sha256': hashlib.sha256(b'MORE').hexdigest()}}
        await harness.call(TASK, 'amend_contract', fx.amendment(TASK, [{'op': 'add', 'criterion': added}]))
        wait = harness.state(TASK)['wait']
        await harness.call(TASK, 'submit_input', message('ExternalInput', {
            'wait_id': 'go', 'task_revision': wait['task_revision'], 'input_type': 'text', 'value': 'continue'}))
        result = await self.drive(harness)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        after_answer = self.at('verification-effect', 2)
        evaluation = self.store.read_json(TASK, after_answer['completion_ref'])['payload']
        self.assertEqual((evaluation['contract_revision'], evaluation['outcome']), (1, 'unsatisfied'))
        self.assertEqual({c['id']: c['status'] for c in evaluation['criteria']}, {'c1': 'satisfied', 'extra': 'pending'})
        final, contract, _ = self.chain(result)
        self.assertEqual((final['payload']['contract_revision'], contract['payload']['revision']), (1, 1))
        self.assertEqual(self.cognition.calls, [1, 2, 3])

    async def test_unbound_required_criterion_blocks_until_the_user_binds_it(self):
        contract = message('CompletionContract', {'task_id': TASK, 'revision': 0, 'previous_ref': None,
            'amendment_ref': None, 'task_type': None, 'criteria': [
                completion.lower_spec(self.spec()['payload'], TASK)['criteria'][0],
                {'id': 'tests-pass', 'requirement': 'Tests pass.', 'level': 'REQUIRED',
                 'provenance': {'source': 'user'}, 'verifier': {'kind': 'unbound'}}]})
        request = message('TaskRequest', {'task_spec': self.spec(), 'grant': {'capabilities': ['artifact.write']},
                                          'contract': contract})
        harness = self.harness({1: lambda turn: fx.write('answer', 'GOOD'),
                                2: lambda turn: {'type': 'WAIT', 'wait_id': 'bind', 'input_type': 'text'},
                                3: lambda turn: fx.write('report', 'PASS')})
        self.assertIsNone(await self.drive(harness, request=request))
        blocked = self.store.read_json(TASK, harness.state(TASK)['completion_ref'])['payload']
        self.assertIn('REQUIRED tests-pass is unbound', blocked['legality']['blockers'])
        await harness.call(TASK, 'amend_contract', fx.amendment(TASK, [{'op': 'bind', 'id': 'tests-pass',
            'binding_provenance': 'repository', 'verifier': {'kind': 'artifact_digest', 'version': 1,
            'artifact': 'report', 'sha256': hashlib.sha256(b'PASS').hexdigest()}}]))
        wait = harness.state(TASK)['wait']
        await harness.call(TASK, 'submit_input', message('ExternalInput', {
            'wait_id': 'bind', 'task_revision': wait['task_revision'], 'input_type': 'text', 'value': 'bound'}))
        result = await self.drive(harness)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        _, contract, _ = self.chain(result)
        bound = contract['payload']['criteria'][1]
        self.assertEqual((bound['verifier']['kind'], bound['binding_provenance']), ('artifact_digest', 'repository'))

    async def test_mutating_authority_rejects_unbound_contract_at_intake(self):
        contract = message('CompletionContract', {'task_id': TASK, 'revision': 0, 'previous_ref': None,
            'amendment_ref': None, 'task_type': None, 'criteria': [
                completion.lower_spec(self.spec()['payload'], TASK)['criteria'][0],
                {'id': 'tests-pass', 'requirement': 'Tests pass.', 'level': 'REQUIRED',
                 'provenance': {'source': 'user'}, 'verifier': {'kind': 'unbound'}}]})
        spec = deepcopy(self.spec())
        spec['payload']['capabilities'] = spec['payload']['autonomy']['allowed'] = ['artifact.write', 'fixture.effect']
        request = message('TaskRequest', {'task_spec': spec, 'contract': contract,
                                          'grant': {'capabilities': ['artifact.write', 'fixture.effect']}})
        harness = self.harness({})
        with self.assertRaises(restate.TerminalError) as rejected:
            await harness.invoke(TASK, request)
        self.assertEqual(rejected.exception.status_code, 400)
        self.assertIn('mutating authority', rejected.exception.message)


if __name__ == '__main__':
    unittest.main()
