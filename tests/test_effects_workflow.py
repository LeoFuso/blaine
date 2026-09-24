"""E2.0 target-effect lifecycle through the workflow, with journaled replay.

Deterministic FixtureTarget only; the real-Restate SIGKILL acceptance lives in
experiments/personal-agent-hub/e2-0.
"""
from copy import deepcopy
from pathlib import Path
import unittest

import restate

from runtime.kernel import journal
from runtime.kernel.contracts import message

from test_completion_workflow import Base
import effect_fixtures as ef

TASK = 'task-e20'


class EffectsBase(Base):
    def setUp(self):
        super().setUp()
        self.target = ef.FixtureTarget(self.root / 'target.sqlite')
        self.target.put_file(ef.CONFIG, ef.BEFORE)
        self.target.behave('unit-tests', polls=2, exit_code=0, result={'tests': 4, 'failures': 0})

    def harness(self, script, crash_at=(), **options):
        hooks = []
        self.hooks = hooks
        pending = set(crash_at)
        async def checkpoint(ctx, stage, state):
            self.checkpoints.append((stage, deepcopy(state)))
            for hook in hooks:
                await hook(stage, state)
            if stage in pending:
                pending.discard(stage)
                from completion_harness import Crash
                raise Crash(stage)
        from completion_harness import Harness
        from test_completion_workflow import Audited, Cognition
        holder = []
        self.cognition = Cognition(script)
        self.capabilities = Audited(self.store, self.root / 'fixture.sqlite', holder)
        harness = Harness(self.store, self.cognition, self.capabilities, checkpoint=checkpoint, **options)
        holder.append(harness)
        return harness

    async def drive(self, harness, key=TASK, request=None):
        return await super().drive(harness, key=key, request=request)

    def chain(self, result, key=TASK):
        return super().chain(result, key=key)

    def start(self, script, request=None, crash_at=(), **options):
        harness = self.harness(script, crash_at=crash_at, target_provider=self.target,
                               exec_profiles=ef.PROFILES, **options)
        return harness, request or ef.change_request(TASK)

    def happy(self):
        return {1: lambda t: ef.read(),
                2: lambda t: ef.draft(),
                3: lambda t: ef.write(ef.artifact_ref(t, 'draft'), receipt_ref=ef.latest_receipt(t)),
                4: lambda t: ef.run()}

    def entries(self, harness, key=TASK):
        state = harness.state(key)
        return [e for _, e in journal.read(self.store, key, state['journal_head'], state['journal_length'])]

    def statuses(self, evaluation):
        return {c['id']: c['status'] for c in evaluation['payload']['criteria']}

    def evaluation(self, harness, key=TASK):
        return self.store.read_json(key, harness.state(key)['completion_ref'])



class Effects(EffectsBase):
    # ------------------------------------------------------------------ happy path and legality
    async def test_conditional_write_and_verified_tests_complete_the_task(self):
        harness, request = self.start(self.happy())
        result = await self.drive(harness, request=request)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        self.assertEqual(self.target.file(ef.CONFIG), ef.AFTER)
        evaluation = self.chain(result)[0]
        self.assertEqual(set(self.statuses(evaluation).values()), {'satisfied'})
        self.assertTrue(evaluation['payload']['legality']['legal'])
        phases = [(e['phase'], e.get('operation_class') or e.get('outcome')) for e in self.entries(harness)]
        self.assertEqual(phases, [
            ('admitted', 'workspace.read'), ('observed', 'success'),
            ('admitted', 'task.artifact.write'), ('observed', 'success'),
            ('admitted', 'workspace.write'), ('dispatched', None), ('observed', 'success'),
            ('admitted', 'workspace.exec'), ('dispatched', None), ('observed', 'success')])
        self.assertEqual(sorted(k for _, k in self.target.executions()), ['exec', 'write'])

    async def test_completion_is_illegal_until_effect_criteria_are_proven(self):
        harness, request = self.start({**self.happy(), 4: lambda t: {'type': 'WAIT', 'wait_id': 'hold', 'input_type': 'text'}})
        self.assertIsNone(await self.drive(harness, request=request))
        evaluation = self.evaluation(harness)
        self.assertFalse(evaluation['payload']['legality']['legal'])
        self.assertEqual(self.statuses(evaluation)['tests-pass'], 'pending')
        self.assertEqual(self.statuses(evaluation)['change-made'], 'satisfied')

    # ------------------------------------------------------------------ authority
    async def test_unauthorized_effects_are_denied_before_dispatch(self):
        other = {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.write', 'input': {
            'workspace_id': 'wsp-other', 'path': ef.CONFIG, 'precondition': {'absent': True}, 'content_ref': '$'}}
        script = {1: lambda t: ef.draft(),
                  2: lambda t: {**other, 'input': {**other['input'], 'content_ref': ef.artifact_ref(t, 'draft')}},
                  3: lambda t: ef.run('slow-build'),
                  4: lambda t: ef.run('unit-tests', args=['--tests', 'x']),
                  5: lambda t: ef.write(ef.artifact_ref(t, 'draft'), path='../escape.txt'),
                  6: lambda t: {'type': 'WAIT', 'wait_id': 'hold', 'input_type': 'text'}}
        harness, request = self.start(script)
        self.assertIsNone(await self.drive(harness, request=request))
        denied = [e for e in self.entries(harness) if e['phase'] == 'denied']
        self.assertEqual([e['operation_class'] for e in denied], ['workspace.write', 'workspace.exec', 'workspace.exec', 'workspace.write'])
        self.assertEqual(self.target.executions(), [])
        self.assertEqual(self.target.file(ef.CONFIG), ef.BEFORE)

    async def test_admitted_unallowed_target_effect_is_a_terminal_invariant_violation(self):
        request = ef.change_request(TASK)
        predicates = request['payload']['contract']['payload']['criteria'][1]['verifier']['predicates']
        predicates[0]['allowed'] = ['workspace.write']  # the contract allows writes, not execution
        harness, _ = self.start({**self.happy()}, request=request)
        result = await self.drive(harness, request=request)
        self.assertEqual(result['payload']['outcome'], 'FAILED')
        self.assertIn('Invariant criteria failed: no-unauthorized-effect', result['payload']['concerns'][0])

    # ------------------------------------------------------------------ conflicts
    async def test_changed_target_conflicts_without_overwrite_and_a_new_effect_retries(self):
        edited = ef.BEFORE + '# reviewed\n'
        replanned = ef.AFTER + '# reviewed\n'
        self.target.set_fault('external_edit', edited)
        script = {1: lambda t: ef.read(), 2: lambda t: ef.draft(replanned),
                  3: lambda t: ef.write(ef.artifact_ref(t, 'draft'), receipt_ref=ef.latest_receipt(t)),
                  4: lambda t: ef.read(),
                  5: lambda t: ef.write(ef.artifact_ref(t, 'draft'), receipt_ref=ef.latest_receipt(t)),
                  6: lambda t: {'type': 'WAIT', 'wait_id': 'hold', 'input_type': 'text'}}
        harness, request = self.start(script)
        self.assertIsNone(await self.drive(harness, request=request))
        effects = harness.state(TASK)['effects']
        self.assertEqual({op: e['status'] for op, e in effects.items()}, {f'{TASK}/3': 'conflict', f'{TASK}/5': 'applied'})
        conflict = self.store.read_json(TASK, effects[f'{TASK}/3']['receipt_ref'])['payload']
        self.assertEqual(conflict['write']['before'], {'sha256': __import__('hashlib').sha256(edited.encode()).hexdigest()})
        self.assertEqual(self.target.file(ef.CONFIG), replanned)
        self.assertEqual(self.target.executions(f'{TASK}/3'), [])  # the conflicting write never wrote
        self.assertEqual(self.cognition.calls, [1, 2, 3, 4, 5, 6])  # a conflict is remediable

    # ------------------------------------------------------------------ remediable execution
    async def test_failing_tests_are_remediable_and_a_later_run_completes(self):
        async def fix(stage, state):
            if stage == 'effect_observed' and state['iteration'] == 4:
                self.target.behave('unit-tests', polls=1, exit_code=0, result={'tests': 4, 'failures': 0})
        self.target.behave('unit-tests', polls=1, exit_code=1, result={'tests': 4, 'failures': 1})
        harness, request = self.start({**self.happy(), 5: lambda t: ef.run()})
        self.hooks.append(fix)
        result = await self.drive(harness, request=request)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        failing = self.store.read_json(TASK, self.at('verification-effect', 4)['completion_ref'])
        self.assertEqual((self.statuses(failing)['tests-pass'], failing['payload']['irrecoverable']), ('failed', []))

    async def test_timeout_stops_the_process_and_is_not_success(self):
        request = ef.change_request(TASK, profiles=('unit-tests', 'slow-build'))
        self.target.behave('slow-build', polls=99)
        script = {1: lambda t: ef.run('slow-build'), 2: lambda t: {'type': 'WAIT', 'wait_id': 'hold', 'input_type': 'text'}}
        harness, _ = self.start(script, request=request)
        self.assertIsNone(await self.drive(harness, request=request))
        record = harness.state(TASK)['effects'][f'{TASK}/1']
        receipt = self.store.read_json(TASK, record['receipt_ref'])['payload']
        self.assertEqual((record['status'], receipt['exec']['cleanup'], receipt['exec']['started']),
                         ('timed_out', 'confirmed', True))
        self.assertEqual(self.cognition.calls, [1, 2])

    # ------------------------------------------------------------------ cancellation
    async def test_cancel_before_dispatch_proves_no_effect(self):
        harness, request = self.start({**self.happy(), 4: lambda t: {'type': 'WAIT', 'wait_id': 'hold', 'input_type': 'text'}},
                                      request=ef.change_request(TASK, ask_before=('workspace.write',)))
        self.assertIsNone(await self.drive(harness, request=request))
        state = harness.state(TASK)
        self.assertEqual((state['lifecycle'], state['wait']['wait_id']), ('WAITING', 'approve-3'))
        await harness.call(TASK, 'cancel_effect', message('EffectCancelRequest', {'operation_id': f'{TASK}/3'}))
        self.assertIsNone(await self.drive(harness))
        record = harness.state(TASK)['effects'][f'{TASK}/3']
        self.assertEqual(record['status'], 'not_dispatched')
        self.assertIn('Canceled before dispatch', self.store.read_json(TASK, record['receipt_ref'])['payload']['reason'])
        self.assertEqual(self.target.executions(), [])
        self.assertNotIn('dispatched', [e['phase'] for e in self.entries(harness)])

    async def test_cancel_running_process_with_confirmed_stop(self):
        self.target.behave('unit-tests', polls=99)
        harness, request = self.start({1: lambda t: ef.run(), 2: lambda t: {'type': 'WAIT', 'wait_id': 'hold', 'input_type': 'text'}})
        async def cancel(stage, state):
            if stage == 'dispatched':
                await harness.call(TASK, 'cancel_effect', message('EffectCancelRequest', {'operation_id': f'{TASK}/1'}))
        self.hooks.append(cancel)
        self.assertIsNone(await self.drive(harness, request=request))
        record = harness.state(TASK)['effects'][f'{TASK}/1']
        receipt = self.store.read_json(TASK, record['receipt_ref'])['payload']
        # CANCELED says the process was stopped, and that it had started: not "did not happen".
        self.assertEqual((record['status'], receipt['exec']['started'], receipt['exec']['cleanup']),
                         ('canceled', True, 'confirmed'))

    async def test_cancel_with_unconfirmed_stop_is_uncertain_until_reconciled(self):
        self.target.behave('unit-tests', polls=99, stop='unknown')
        harness, request = self.start({1: lambda t: ef.run(), 2: lambda t: ef.run(),
                                       3: lambda t: {'type': 'WAIT', 'wait_id': 'hold', 'input_type': 'text'}})
        async def cancel(stage, state):
            if stage == 'dispatched' and state['iteration'] == 1:
                await harness.call(TASK, 'cancel_effect', message('EffectCancelRequest', {'operation_id': f'{TASK}/1'}))
        self.hooks.append(cancel)
        self.assertIsNone(await self.drive(harness, request=request))
        state = harness.state(TASK)
        self.assertEqual(state['effects'][f'{TASK}/1']['status'], 'uncertain')  # still running per the provider
        self.assertNotIn(f'{TASK}/2', state['effects'])  # PolicyGate refused a new target effect
        denied = [e for e in self.entries(harness) if e['phase'] == 'denied']
        self.assertIn('reconciled first', denied[0]['reason'])
        self.target.behave('unit-tests', polls=1, exit_code=0, result={'failures': 0})
        wait = state['wait']
        await harness.call(TASK, 'submit_input', message('ExternalInput', {
            'wait_id': 'hold', 'task_revision': wait['task_revision'], 'input_type': 'text', 'value': 'go'}))
        with self.assertRaises(KeyError):  # script exhausted after reconciliation at the next boundary
            await self.drive(harness)
        reconciled = [e for e in self.entries(harness) if e['phase'] == 'reconciled']
        self.assertEqual([e['state'] for e in reconciled][-1], 'APPLIED')

    # ------------------------------------------------------------------ response loss and reconciliation
    async def test_crash_after_commit_recovers_the_receipt_without_a_second_write(self):
        self.target.set_fault('after_commit', 'crash')
        harness, request = self.start(self.happy())
        result = await self.drive(harness, request=request)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        self.assertEqual(len(self.target.executions(f'{TASK}/3')), 1)
        outcome = [e for e in self.entries(harness) if e.get('operation_id') == f'{TASK}/3']
        self.assertEqual([e['phase'] for e in outcome], ['admitted', 'dispatched', 'observed'])

    async def test_lost_response_reconciles_applied_from_the_receipt(self):
        self.target.set_fault('after_commit', 'lose_response')
        harness, request = self.start(self.happy())
        result = await self.drive(harness, request=request)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        write = [e for e in self.entries(harness) if e.get('operation_id') == f'{TASK}/3']
        self.assertEqual([(e['phase'], e.get('outcome') or e.get('state')) for e in write][2:],
                         [('observed', 'uncertain'), ('reconciled', 'APPLIED')])
        self.assertEqual(len(self.target.executions(f'{TASK}/3')), 1)

    async def test_unreachable_provider_reconciles_not_applied_when_absence_is_authoritative(self):
        async def recover(stage, state):
            if stage == 'dispatched' and state['iteration'] == 3:
                self.target.set_fault('unavailable', True)
            if stage == 'effect_observed' and state['iteration'] == 3:
                self.target.set_fault('unavailable', None)
        script = {**self.happy(), 4: lambda t: ef.write(ef.artifact_ref(t, 'draft'), receipt_ref=ef.latest_receipt(t)),
                  5: lambda t: ef.run()}
        harness, request = self.start(script)
        self.hooks.append(recover)
        result = await self.drive(harness, request=request)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        effects = harness.state(TASK)['effects']
        self.assertEqual(effects[f'{TASK}/3']['status'], 'not_applied')
        self.assertEqual(effects[f'{TASK}/4']['status'], 'applied')  # a new intentional effect, new identity

    async def test_insufficient_evidence_stays_unknown_and_blocks_completion(self):
        async def outage(stage, state):
            if stage == 'dispatched' and state['iteration'] == 3:
                self.target.set_fault('unavailable', True)
            if stage == 'effect_observed' and state['iteration'] == 3:
                self.target.set_fault('unavailable', None)
                self.target.set_fault('receipts_authoritative', False)
        script = {**self.happy(), 4: lambda t: ef.run(), 5: lambda t: {'type': 'WAIT', 'wait_id': 'hold', 'input_type': 'text'}}
        harness, request = self.start(script)
        self.hooks.append(outage)
        self.assertIsNone(await self.drive(harness, request=request))
        state = harness.state(TASK)
        self.assertEqual(state['effects'][f'{TASK}/3']['status'], 'uncertain')
        evaluation = self.evaluation(harness)
        self.assertEqual(self.statuses(evaluation)['change-made'], 'unknown')
        self.assertEqual(self.statuses(evaluation)['no-unauthorized-effect'], 'unknown')
        self.assertFalse(evaluation['payload']['legality']['legal'])
        reconciled = [e['state'] for e in self.entries(harness) if e['phase'] == 'reconciled']
        self.assertTrue(reconciled and set(reconciled) == {'STILL_UNKNOWN'})
        self.assertEqual(self.target.file(ef.CONFIG), ef.BEFORE)

    # ------------------------------------------------------------------ approval
    async def test_approval_waits_and_the_same_effect_continues(self):
        harness, request = self.start(self.happy(), request=ef.change_request(TASK, ask_before=('workspace.write',)))
        self.assertIsNone(await self.drive(harness, request=request))
        state = harness.state(TASK)
        human = self.store.read_json(TASK, state['wait']['request_ref'])
        self.assertEqual(self.target.executions(), [])
        response = message('HumanDecisionResponse', {'task_id': TASK, 'request_id': 'approve-3', 'request_revision': 0,
            'request_digest': __import__('runtime.kernel.human', fromlist=['request_digest']).request_digest(human),
            'response_id': 'approval-1', 'value': 'APPROVE'})
        await harness.call(TASK, 'submit_human_response', response)
        result = await self.drive(harness)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        dispatched = [e for e in self.entries(harness) if e['phase'] == 'dispatched' and e['operation_id'] == f'{TASK}/3']
        self.assertEqual(len(dispatched), 1)
        self.assertEqual(self.store.read_json(TASK, dispatched[0]['approval_ref'])['payload']['value'], 'APPROVE')

    # ------------------------------------------------------------------ replay
    async def test_crashes_and_replay_reproduce_the_same_outcome(self):
        baseline, request = self.start(self.happy())
        expected = await self.drive(baseline, request=request)
        baseline_state = baseline.state(TASK)
        self.store = __import__('runtime.kernel.artifacts', fromlist=['ArtifactStore']).ArtifactStore(self.root / 'replayed')
        self.target = ef.FixtureTarget(self.root / 'target-2.sqlite')
        self.target.put_file(ef.CONFIG, ef.BEFORE)
        self.target.behave('unit-tests', polls=2, exit_code=0, result={'tests': 4, 'failures': 0})
        harness, request = self.start(self.happy(), crash_at=('dispatched', 'effect_observed', 'effect_persisted', 'admitted'))
        result = await self.drive(harness, request=request)
        self.assertEqual(result, expected)
        for key in ('journal_head', 'journal_length', 'completion_ref', 'effects', 'artifacts', 'result_ref'):
            self.assertEqual(harness.state(TASK)[key], baseline_state[key], key)
        self.assertEqual(sorted(k for _, k in self.target.executions()), ['exec', 'write'])


class LifecycleInvariant(EffectsBase):
    """Never COMPLETED with an unresolved target effect, whatever the contract says."""
    async def test_contract_without_reconciliation_criterion_still_cannot_complete(self):
        request = ef.change_request(TASK)
        request['payload']['contract']['payload']['criteria'] = request['payload']['contract']['payload']['criteria'][:1]
        fired = set()
        async def outage(stage, state):  # checkpoints re-fire on replay; act once
            if stage == 'dispatched' and state['iteration'] == 3 and 'down' not in fired:
                fired.add('down')
                self.target.set_fault('unavailable', True)
            if stage == 'effect_observed' and state['iteration'] == 3 and 'up' not in fired:
                fired.add('up')
                self.target.set_fault('unavailable', None)
                self.target.set_fault('receipts_authoritative', False)
        script = {1: lambda t: ef.read(),
                  2: lambda t: {'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write',
                                'input': {'name': 'content', 'content': ef.AFTER}},
                  3: lambda t: ef.write(ef.artifact_ref(t, 'content'), receipt_ref=ef.latest_receipt(t)),
                  4: lambda t: ef.draft(),  # satisfies the only criterion
                  5: lambda t: {'type': 'WAIT', 'wait_id': 'hold', 'input_type': 'text'}}
        harness, _ = self.start(script, request=request)
        self.hooks.append(outage)
        self.assertIsNone(await self.drive(harness, request=request))
        state = harness.state(TASK)
        self.assertEqual((state['lifecycle'], state['effects'][f'{TASK}/3']['status']), ('WAITING', 'uncertain'))
        evaluation = self.evaluation(harness)['payload']
        self.assertEqual(evaluation['outcome'], 'satisfied')  # the contract alone would allow completion
        self.assertFalse(evaluation['legality']['legal'])
        self.assertIn(f'Target effects with unresolved outcome: {TASK}/3', evaluation['legality']['blockers'])
        self.target.set_fault('receipts_authoritative', True)
        await harness.call(TASK, 'submit_input', message('ExternalInput', {
            'wait_id': 'hold', 'task_revision': state['wait']['task_revision'], 'input_type': 'text', 'value': 'go'}))
        result = await self.drive(harness)
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')  # once reconciled NOT_APPLIED
        self.assertEqual(harness.state(TASK)['effects'][f'{TASK}/3']['status'], 'not_applied')


class TaskCancellation(EffectsBase):
    """Task cancel uses the effect machinery: stop, recover or reconcile. Not rollback."""
    def running(self, **behaviour):
        self.target.behave('unit-tests', polls=99, operation=f'{TASK}/1', **behaviour)
        return {1: lambda t: ef.run(), 2: lambda t: {'type': 'WAIT', 'wait_id': 'hold', 'input_type': 'text'}}

    async def cancel_at_dispatch(self, harness, before=None):
        async def hook(stage, state):
            if stage == 'dispatched' and state['iteration'] == 1 and not harness.tasks[TASK].cancel_requested:
                if before:
                    before()
                await harness.call(TASK, 'cancel')
        self.hooks.append(hook)

    def kinds(self, operation=f'{TASK}/1'):
        return sorted(kind for _, kind in self.target.executions(operation))

    async def test_task_cancel_before_dispatch_closes_the_effect_as_never_dispatched(self):
        harness, request = self.start(self.happy(), request=ef.change_request(TASK, ask_before=('workspace.write',)))
        self.assertIsNone(await self.drive(harness, request=request))
        await harness.call(TASK, 'cancel')
        result = await self.drive(harness)
        self.assertEqual(result['payload']['outcome'], 'CANCELLED')
        self.assertEqual(harness.state(TASK)['effects'][f'{TASK}/3']['status'], 'not_dispatched')
        self.assertNotIn('dispatched', [e['phase'] for e in self.entries(harness)])
        self.assertEqual(self.target.executions(), [])
        self.assertTrue(any('never dispatched' in c for c in result['payload']['concerns']))

    async def test_task_cancel_stops_an_active_effect_with_confirmed_stop(self):
        harness, request = self.start(self.running())
        await self.cancel_at_dispatch(harness)
        result = await self.drive(harness, request=request)
        self.assertEqual(result['payload']['outcome'], 'CANCELLED')
        record = harness.state(TASK)['effects'][f'{TASK}/1']
        receipt = self.store.read_json(TASK, record['receipt_ref'])['payload']
        self.assertEqual((record['status'], receipt['exec']['started'], receipt['exec']['cleanup']), ('canceled', True, 'confirmed'))
        self.assertEqual(self.kinds(), ['cancel', 'exec'])  # one execution, one stop request
        self.assertTrue(any('partial effects possible' in c for c in result['payload']['concerns']))

    async def test_effect_completion_can_win_the_race_with_task_cancel(self):
        harness, request = self.start(self.running())
        await self.cancel_at_dispatch(harness, before=lambda: self.target.behave(
            'unit-tests', polls=1, exit_code=0, result={'failures': 0}, operation=f'{TASK}/1'))
        result = await self.drive(harness, request=request)
        self.assertEqual(result['payload']['outcome'], 'CANCELLED')
        self.assertEqual(harness.state(TASK)['effects'][f'{TASK}/1']['status'], 'completed')
        self.assertEqual(self.kinds(), ['exec'])  # no stop request was needed or sent
        self.assertTrue(any('completed before the stop' in c for c in result['payload']['concerns']))

    async def test_task_cancel_keeps_a_still_unknown_effect_explicit(self):
        harness, request = self.start(self.running(stop='unknown'))
        await self.cancel_at_dispatch(harness)
        result = await self.drive(harness, request=request)
        self.assertEqual(result['payload']['outcome'], 'CANCELLED')
        self.assertEqual(harness.state(TASK)['effects'][f'{TASK}/1']['status'], 'uncertain')
        self.assertTrue(any('STILL_UNKNOWN' in c for c in result['payload']['concerns']))
        evaluation = self.store.read_json(TASK, result['payload']['completion_ref'])['payload']
        self.assertIn(f'Target effects with unresolved outcome: {TASK}/1', evaluation['legality']['blockers'])
        self.assertEqual([e['state'] for e in self.entries(harness) if e['phase'] == 'reconciled'], ['STILL_UNKNOWN'])

    async def test_crash_during_task_cancellation_replays_without_duplicate_stop(self):
        harness, request = self.start(self.running(), crash_at=('task_stop_effect',))
        await self.cancel_at_dispatch(harness)
        result = await self.drive(harness, request=request)
        self.assertEqual(result['payload']['outcome'], 'CANCELLED')
        self.assertEqual(harness.state(TASK)['effects'][f'{TASK}/1']['status'], 'canceled')
        self.assertEqual(self.kinds(), ['cancel', 'exec'])
        self.assertEqual(harness.tasks[TASK].executions[f'task-stop/{TASK}/1'], 1)
        self.assertGreater(harness.tasks[TASK].invocations, 1)


if __name__ == '__main__':
    unittest.main()
