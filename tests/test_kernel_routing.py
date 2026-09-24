"""Policy C: local-first execution with bounded, trusted escalation.

Synthetic fixtures only. No provider call, no classifier and no heuristic router
is required by anything here, which is itself part of what Policy C asserts.
"""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from runtime.kernel import workflow
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import (
    MAX_TURNS, accept_task_request, child_request, message, validate_spec,
)
from runtime.kernel.event_sinks import JsonlEventPublisher
from runtime.kernel.execution import Capabilities, policy_gate
from runtime.kernel.routing import (
    LOCAL_BINDING, LOCAL_TURN_BUDGET, POLICY, REPETITION_THRESHOLD, admit_escalation,
    effective_capabilities,
    escalation_condition, narrow_grant, validate_grant,
)

GOOD = hashlib.sha256(b'GOOD').hexdigest()
REMOTE = 'remote-tier'


class Registry:
    def __init__(self, *a): self.handlers = {}
    def main(self, **kw):
        def accept(f): self.run = f; return f
        return accept
    def handler(self, **kw):
        def accept(f): self.handlers[f.__name__] = f; return f
        return accept


class NoAmendment:
    async def peek(self):
        return None


class Context:
    def __init__(self): self.saved, self.steps = {}, []
    def key(self): return 'control'
    def request(self): return SimpleNamespace(id='local-test-invocation')
    def set(self, k, v): self.saved[k] = v
    async def run_typed(self, name, fn, *options, **kw):
        self.steps.append(name)
        return fn(**kw)

    def promise(self, name, type_hint=None):
        # No contract amendment is submitted in these fixtures.
        return NoAmendment()


def spec(capabilities=('artifact.write',), content=b'GOOD'):
    return message('TaskSpec', {'objective': 'Produce the exact deliverable.',
        'completion': [{'criterion': 'Exact', 'evidence': {'artifact': 'answer',
            'sha256': hashlib.sha256(content).hexdigest()}}],
        'capabilities': list(capabilities), 'autonomy': {'allowed': list(capabilities)}})


def writes(*contents):
    return [{'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write',
             'input': {'name': 'answer', 'content': value}} for value in contents]


class Scripted:
    """Local cognition stand-in; repeats its last action once exhausted."""
    def __init__(self, actions, label='local'):
        self.actions, self.label, self.calls = list(actions), label, []

    def __call__(self, packet):
        turn = packet['payload']
        self.calls.append(turn['iteration'])
        action = self.actions[min(turn['iteration'], len(self.actions)) - 1]
        return message('CognitiveDecision', {k: turn[k] for k in ('task_id', 'task_revision', 'turn_id')}
                       | {'next_action': action})


async def run_task(*, request=None, local=None, escalation=None, binding=None,
                   publisher=None, directory=None, task_spec=None):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(directory or temporary)
        store = ArtifactStore(root / 'artifacts')
        capabilities = Capabilities(store, root / 'effects.sqlite')
        with patch.object(workflow.restate, 'Workflow', Registry):
            service = workflow.create_workflow(store, local or Scripted(writes('GOOD')), capabilities,
                                               event_publisher=publisher,
                                               escalation_cognitive=escalation,
                                               escalation_binding=binding)
        ctx = Context()
        result = await service.run(ctx, request or task_spec or spec())
        return result, ctx, store


class AuthorityTests(unittest.IsolatedAsyncioTestCase):
    def grant(self, capabilities=('artifact.write',), escalation=None):
        return validate_grant({'capabilities': list(capabilities), 'escalation_binding': escalation})

    async def test_effective_authority_is_request_intersected_with_grant(self):
        requested = spec(('artifact.write', 'fixture.effect'))['payload']
        self.assertEqual(sorted(effective_capabilities(requested, None)),
                         ['artifact.write', 'fixture.effect'])
        bounded = effective_capabilities(requested, self.grant(('artifact.write',)))
        self.assertEqual(sorted(bounded), ['artifact.write'])

    async def test_a_granted_task_cannot_use_a_capability_outside_the_grant(self):
        request = message('TaskRequest', {'task_spec': spec(('artifact.write', 'fixture.effect')),
            'initial_action': writes('GOOD')[0],
            'grant': {'capabilities': ['artifact.write'], 'escalation_binding': None}})
        effect = {'type': 'INVOKE_CAPABILITY', 'capability': 'fixture.effect', 'input': {'value': 'x'}}
        result, ctx, _ = await run_task(request=request, local=Scripted([effect, *writes('GOOD')]))
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        state = ctx.saved['task']['payload']
        self.assertEqual(state['grant']['capabilities'], ['artifact.write'])

    async def test_a_child_may_only_narrow_effective_authority(self):
        parent = self.grant(('artifact.write', 'fixture.effect'), REMOTE)
        self.assertEqual(narrow_grant(parent, None), parent)
        narrowed = narrow_grant(parent, {'capabilities': ['artifact.write'], 'escalation_binding': None})
        self.assertEqual(narrowed['capabilities'], ['artifact.write'])
        widened = narrow_grant(parent, {'capabilities': ['artifact.write', 'youtrack.read'],
                                        'escalation_binding': None})
        self.assertEqual(widened['capabilities'], ['artifact.write'])
        # An unbounded parent cannot hand out a bound it does not itself carry.
        self.assertIsNone(narrow_grant(None, {'capabilities': ['artifact.write']}))

    async def test_policy_gate_refuses_a_child_beyond_effective_authority(self):
        parent = spec(('artifact.write', 'fixture.effect'))['payload']
        parent['autonomy']['child_tasks'] = 2
        child = spec(('fixture.effect',))
        decision = message('CognitiveDecision', {'task_id': 'control', 'task_revision': 0,
            'turn_id': 'control/1', 'next_action': {'type': 'SPAWN_TASK', 'task_spec': child}})
        state = {'task_id': 'control', 'revision': 0, 'lifecycle': 'RUNNING', 'iteration': 1,
                 'artifacts': {}, 'remaining_children': 2}
        self.assertEqual(policy_gate(decision, state, parent)['outcome'], 'allow')
        bounded = self.grant(('artifact.write',))
        denied = policy_gate(decision, state, parent, bounded)
        self.assertEqual(denied['outcome'], 'deny')
        self.assertIn('authority', denied['reason'])


class BindingAuthorityTests(unittest.IsolatedAsyncioTestCase):
    async def test_a_task_specification_cannot_carry_a_binding(self):
        raw = spec()
        raw['payload']['binding'] = REMOTE
        with self.assertRaises(ValueError):
            validate_spec(raw)
        raw['payload'].pop('binding')
        raw['payload']['grant'] = {'capabilities': ['artifact.write']}
        with self.assertRaises(ValueError):
            validate_spec(raw)

    async def test_a_model_written_child_request_carries_no_grant_of_its_own(self):
        # The workflow builds the envelope; a child spec is model-writable text.
        envelope = child_request('parent', 'parent/1', None, validate_spec(spec()),
                                 validate_grant({'capabilities': ['artifact.write'],
                                                 'escalation_binding': None}))
        accepted, parent, grant = accept_task_request(
            envelope, workflow.child_task_id('parent', 'parent/1', None))
        self.assertEqual(parent['task_id'], 'parent')
        self.assertIsNone(grant['escalation_binding'])

    async def test_a_child_cannot_obtain_a_binding_its_parent_lacks(self):
        parent = validate_grant({'capabilities': ['artifact.write'], 'escalation_binding': None})
        with self.assertRaises(ValueError):
            narrow_grant(parent, {'capabilities': ['artifact.write'], 'escalation_binding': REMOTE})


class PolicyCExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_an_eligible_task_starts_locally_and_never_escalates_when_it_completes(self):
        remote = Scripted(writes('GOOD'), label='remote')
        result, ctx, _ = await run_task(local=Scripted(writes('GOOD')), escalation=remote, binding=REMOTE)
        state = ctx.saved['task']['payload']
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        self.assertEqual(state['binding'], LOCAL_BINDING)
        self.assertIsNone(state['escalation'])
        # A locally completed Task never reaches the escalation adapter.
        self.assertEqual(remote.calls, [])

    async def test_a_stuck_task_recommends_escalation_and_is_denied_without_authority(self):
        # The same wrong artifact every turn: refused, with no new evidence.
        local = Scripted(writes('DRAFT'))
        result, ctx, _ = await run_task(local=local)
        state = ctx.saved['task']['payload']
        self.assertEqual(result['payload']['outcome'], 'FAILED')
        self.assertEqual(state['escalation']['reason'], 'repeated_verifier_rejection')
        self.assertEqual(state['escalation']['admission'], 'denied_no_grant')
        self.assertEqual(state['binding'], LOCAL_BINDING)
        # A denied recommendation does not stop local work; the loop runs out.
        self.assertEqual(len(local.calls), MAX_TURNS)

    async def test_a_task_still_changing_its_evidence_reaches_the_turn_budget_instead(self):
        # Different wrong content each turn: progress, so the repeat rule stays quiet.
        local = Scripted(writes(*[f'DRAFT-{n}' for n in range(1, MAX_TURNS + 1)]))
        _, ctx, _ = await run_task(local=local)
        state = ctx.saved['task']['payload']
        self.assertEqual(state['escalation']['reason'], 'local_turn_budget_reached')
        self.assertEqual(state['escalation']['iteration'], LOCAL_TURN_BUDGET)

    async def test_escalation_is_denied_when_the_grant_authorizes_no_binding(self):
        request = message('TaskRequest', {'task_spec': spec(), 'initial_action': writes('DRAFT')[0],
            'grant': {'capabilities': ['artifact.write'], 'escalation_binding': None}})
        remote = Scripted(writes('GOOD'), label='remote')
        _, ctx, _ = await run_task(request=request, local=Scripted(writes('DRAFT')),
                                   escalation=remote, binding=REMOTE)
        self.assertEqual(ctx.saved['task']['payload']['escalation']['admission'], 'denied_not_authorized')
        self.assertEqual(remote.calls, [])

    async def test_escalation_is_denied_when_the_deployment_lacks_the_named_binding(self):
        request = message('TaskRequest', {'task_spec': spec(), 'initial_action': writes('DRAFT')[0],
            'grant': {'capabilities': ['artifact.write'], 'escalation_binding': REMOTE}})
        _, ctx, _ = await run_task(request=request, local=Scripted(writes('DRAFT')))
        self.assertEqual(ctx.saved['task']['payload']['escalation']['admission'],
                         'denied_binding_unavailable')

    async def test_an_authorized_escalation_continues_inside_the_same_task(self):
        request = message('TaskRequest', {'task_spec': spec(), 'initial_action': writes('DRAFT')[0],
            'grant': {'capabilities': ['artifact.write'], 'escalation_binding': REMOTE}})
        local, remote = Scripted(writes('DRAFT')), Scripted(writes('GOOD'), label='remote')
        result, ctx, _ = await run_task(request=request, local=local, escalation=remote, binding=REMOTE)
        state = ctx.saved['task']['payload']
        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        self.assertEqual(state['escalation']['admission'], 'admitted')
        self.assertEqual(state['binding'], REMOTE)
        # Same Task identity throughout: no second lifecycle, no child Task.
        self.assertEqual(result['payload']['task_id'], 'control')
        self.assertEqual(state['children'], {})
        escalated_at = state['escalation']['iteration']
        self.assertTrue(all(call < escalated_at for call in local.calls))
        self.assertEqual(remote.calls[0], escalated_at)

    async def test_completion_remains_the_verifiers_decision_after_escalation(self):
        request = message('TaskRequest', {'task_spec': spec(), 'initial_action': writes('DRAFT')[0],
            'grant': {'capabilities': ['artifact.write'], 'escalation_binding': REMOTE}})
        # The escalated tier also fails to satisfy the contract; the verifier decides.
        result, _, _ = await run_task(request=request, local=Scripted(writes('DRAFT')),
                                      escalation=Scripted(writes('ALSO-WRONG')), binding=REMOTE)
        self.assertEqual(result['payload']['outcome'], 'FAILED')

    async def test_repeated_verifier_rejection_is_a_deterministic_condition(self):
        self.assertIsNone(escalation_condition(1, []))
        self.assertIsNone(escalation_condition(2, ['a', 'b', 'a']))
        self.assertEqual(escalation_condition(2, ['a', 'a', 'a']), 'repeated_verifier_rejection')
        self.assertEqual(escalation_condition(LOCAL_TURN_BUDGET, []), 'local_turn_budget_reached')

    async def test_admission_is_a_trusted_decision_not_a_recommendation(self):
        grant = validate_grant({'capabilities': ['artifact.write'], 'escalation_binding': REMOTE})
        self.assertEqual(admit_escalation(None, REMOTE)['outcome'], 'denied_no_grant')
        self.assertEqual(admit_escalation(grant, None)['outcome'], 'denied_binding_unavailable')
        self.assertEqual(admit_escalation(grant, 'other-tier')['outcome'], 'denied_binding_unavailable')
        self.assertEqual(admit_escalation(grant, REMOTE), {'outcome': 'admitted', 'binding': REMOTE})


class RoutingEvidenceTests(unittest.IsolatedAsyncioTestCase):
    async def exercise(self, directory, **kwargs):
        publisher = JsonlEventPublisher(Path(directory) / 'events.jsonl')
        return await run_task(publisher=publisher, directory=directory, **kwargs)

    async def test_routing_evidence_is_retained_authoritatively(self):
        with tempfile.TemporaryDirectory() as directory:
            result, ctx, store = await self.exercise(directory, local=Scripted(writes('GOOD')))
            state = ctx.saved['task']['payload']
            record = store.read_json('control', state['routing_ref'])['payload']
            self.assertEqual(record['policy'], POLICY)
            # Thresholds travel with the record so it survives their revision.
            self.assertEqual(record['local_turn_budget'], LOCAL_TURN_BUDGET)
            self.assertEqual(record['repetition_threshold'], REPETITION_THRESHOLD)
            self.assertIn('experimental defaults', record['thresholds_are'])
            self.assertEqual(record['outcome'], 'COMPLETED')
            self.assertTrue(record['started_local'])
            self.assertFalse(record['escalated'])
            self.assertFalse(record['externally_bounded'])
            self.assertEqual(record['final_binding'], LOCAL_BINDING)
            self.assertIn('unclassified', record['escalation_interpretation'])
            self.assertGreaterEqual(record['total_turns'], 1)
            self.assertTrue(record['context_refs'])
            # Discoverable from the append-only record, not from runtime state.
            events = [json.loads(line) for line in (Path(directory) / 'events.jsonl').read_text().splitlines()]
            routing = [e for e in events if e['producer']['component'] == 'blaine.kernel.routing']
            self.assertEqual([e['event_type'] for e in routing], ['artifact.produced'])
            self.assertIn(state['routing_ref'], routing[0]['references']['artifact_ids'])

    async def test_the_deterministic_report_derives_metrics_without_a_model(self):
        import importlib.util
        spec_ = importlib.util.spec_from_file_location(
            'routing_report', Path(__file__).resolve().parents[1] / 'scripts/routing-report.py')
        report_module = importlib.util.module_from_spec(spec_)
        spec_.loader.exec_module(report_module)
        with tempfile.TemporaryDirectory() as directory:
            await self.exercise(directory, local=Scripted(writes('GOOD')))
            store = ArtifactStore(Path(directory) / 'artifacts')
            records, skipped = report_module.routing_records(
                Path(directory) / 'events.jsonl', store, None)
            report = report_module.summarize(records, skipped, None)
            self.assertEqual(report['tasks_observed'], 1)
            self.assertEqual(report['completed_locally'], 1)
            self.assertEqual(report['escalated'], 0)
            self.assertEqual(report['local_completion_rate'], 1.0)
            self.assertEqual(report['sufficiency'], 'INSUFFICIENT_SAMPLE')
            self.assertEqual(report['unreadable_records'], 0)
            self.assertIn('sampling_rule', report)
            # A reporting guardrail, never a significance claim.
            self.assertEqual(report['minimum_reporting_sample'],
                             report_module.MINIMUM_REPORTING_SAMPLE)
            self.assertTrue(any('not statistical significance' in limit
                                for limit in report['interpretation_limits']))

    async def test_escalation_provenance_survives_for_later_attribution(self):
        request = message('TaskRequest', {'task_spec': spec(), 'initial_action': writes('DRAFT')[0],
            'grant': {'capabilities': ['artifact.write'], 'escalation_binding': REMOTE}})
        with tempfile.TemporaryDirectory() as directory:
            _, ctx, store = await self.exercise(directory, request=request,
                                                local=Scripted(writes('DRAFT')),
                                                escalation=Scripted(writes('GOOD')), binding=REMOTE)
            record = store.read_json('control', ctx.saved['task']['payload']['routing_ref'])['payload']
            self.assertTrue(record['escalated'])
            self.assertTrue(record['externally_bounded'])
            self.assertIn(record['escalation_reason'],
                          {'repeated_verifier_rejection', 'local_turn_budget_reached'})
            self.assertEqual(record['escalation_admission'], 'admitted')
            self.assertLessEqual(record['escalation_iteration'], LOCAL_TURN_BUDGET)
            self.assertEqual(record['final_binding'], REMOTE)
            self.assertIn('unclassified', record['escalation_interpretation'])


class NoRouterRequiredTests(unittest.TestCase):
    def test_policy_c_requires_no_classifier_and_no_heuristic(self):
        import runtime.kernel.routing as routing
        # No provider or classifier is imported or referenced by the policy path.
        for module in (routing, workflow):
            body = Path(module.__file__).read_text().lower()
            for absent in ('jev', 'typesafe', 'workloadclassifier', 'shadowclassifier'):
                with self.subTest(module=module.__name__, absent=absent):
                    self.assertNotIn(absent, body)


if __name__ == '__main__':
    unittest.main()
