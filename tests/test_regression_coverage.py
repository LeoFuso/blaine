"""Regression classification guard and coverage re-homed from frozen historical harnesses.

Historical harnesses stay frozen as milestone evidence. This guard fails if any
property they covered is not mapped to a current gating test or acceptance check
that actually exists, so the classification cannot hide a real regression.
"""
import importlib
import json
from pathlib import Path
import unittest

from runtime.kernel.contracts import child_task_id, message, validate_spec
from runtime.kernel.execution import policy_gate

ROOT = Path(__file__).resolve().parents[1]
E10 = ROOT / 'experiments/personal-agent-hub/e1-0'


class ChildHumanBinding(unittest.TestCase):
    """Formerly covered only by the Increment 5 harness."""
    def decision(self, origin, task_id):
        request = message('HumanDecisionRequest', {'task_id': task_id, 'origin_task_id': origin, 'request_id': 'decide',
            'revision': 0, 'question': 'Proceed?', 'allowed_responses': ['YES', 'NO']})
        child = message('TaskSpec', {'objective': 'Ask.', 'completion': [{'criterion': 'Decided', 'evidence': {
            'artifact': 'decision', 'verifier': 'human_response', 'request': request}}],
            'capabilities': ['human.request'], 'autonomy': {'allowed': ['human.request']}})
        return message('CognitiveDecision', {'task_id': 'parent', 'task_revision': 0, 'turn_id': 'parent/1',
                                             'next_action': {'type': 'SPAWN_TASK', 'task_spec': child}})

    def test_child_human_request_must_bind_parent_and_child(self):
        spec = validate_spec(message('TaskSpec', {'objective': 'Delegate.', 'completion': [
            {'criterion': 'Exact', 'evidence': {'artifact': 'answer', 'sha256': 'a' * 64}}],
            'capabilities': ['human.request'], 'autonomy': {'allowed': ['human.request'], 'child_tasks': 1}}))
        state = {'task_id': 'parent', 'revision': 0, 'iteration': 1, 'lifecycle': 'RUNNING', 'artifacts': {},
                 'remaining_children': 1}
        child = child_task_id('parent', 'parent/1')
        self.assertEqual(policy_gate(self.decision('parent', child), state, spec)['outcome'], 'allow')
        for origin, target in (('elsewhere', child), ('parent', 'child-' + '0' * 64)):
            with self.subTest(origin=origin, target=target):
                denied = policy_gate(self.decision(origin, target), state, spec)
                self.assertEqual(denied['outcome'], 'deny')
                self.assertIn('bind to its parent', denied['reason'])


class Classification(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((E10 / 'regression.json').read_text())
        self.checks = set(json.loads((E10 / 'evidence/checks.json').read_text()))
        self.scenarios = set(json.loads((E10 / 'evidence/fixtures.json').read_text()))
        self.gating = {h['harness'] for h in self.record['gating']['restate_harnesses']}

    def resolve(self, reference):
        kind, _, target = reference.partition(':')
        match kind:
            case 'tests':
                module, cls, method = target.split('.')
                self.assertTrue(callable(getattr(getattr(importlib.import_module(module), cls), method)), reference)
            case 'acceptance':
                self.assertIn(target, self.checks | self.scenarios, reference)
            case 'restate':
                self.assertIn(target, self.gating, reference)
                self.assertTrue((ROOT / target).exists(), reference)
            case _:
                self.fail(f'Unknown coverage reference {reference}')

    def test_every_frozen_property_maps_to_existing_gating_coverage(self):
        historical = self.record['historical_non_gating']
        self.assertEqual({h['harness'] for h in historical},
                         {'scripts/verify-kernel.py', 'scripts/verify-kernel-children.py', 'scripts/verify-kernel-human.py'})
        for harness in historical:
            self.assertNotIn(harness['harness'], self.gating)
            self.assertTrue(harness['baseline_result'].startswith('FAIL (identical'), harness['harness'])
            self.assertIn('HISTORICAL', (ROOT / harness['harness']).read_text()[:600], harness['harness'])
            self.assertTrue(harness['covered_by'])
            for prop, references in harness['covered_by'].items():
                with self.subTest(harness=harness['harness'], property=prop):
                    self.assertTrue(references)
                    for reference in references:
                        self.resolve(reference)

    def test_gating_harnesses_pass(self):
        for harness in self.record['gating']['restate_harnesses']:
            self.assertEqual(harness.get('result', harness.get('branch_result')), 'PASS', harness['harness'])
        summary = json.loads((E10 / 'evidence/summary.json').read_text())
        self.assertEqual(summary['outcome'], 'PASS')


if __name__ == '__main__':
    unittest.main()
