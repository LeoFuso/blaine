import unittest
from runtime.kernel.contracts import child_task_id, message, validate_result, validate_spec
from runtime.kernel.execution import policy_gate
from test_kernel import spec, state, decision


class ChildContracts(unittest.TestCase):
    def test_identity_is_stable_distinct_and_bounded(self):
        first = child_task_id('p' * 80, 'p/1')
        self.assertEqual(first, child_task_id('p' * 80, 'p/1'))
        self.assertNotEqual(first, child_task_id('p' * 80, 'p/2'))
        self.assertLessEqual(len(first), 80)

    def test_child_authority_and_descendant_allocation_cannot_expand(self):
        parent = spec()
        child = spec()
        current = {**state(), 'remaining_children': 1}
        raw = decision({'type': 'SPAWN_TASK', 'task_spec': message('TaskSpec', child)})
        self.assertEqual(policy_gate(raw, current, parent)['outcome'], 'allow')
        parent['autonomy']['allowed'] = ['artifact.write']
        self.assertIn('authority', policy_gate(raw, current, parent)['reason'])
        parent = spec()
        child['autonomy']['child_tasks'] = 1
        self.assertIn('allocation', policy_gate(raw, current, parent)['reason'])
        self.assertEqual(policy_gate(raw, {**current, 'remaining_children': 2}, parent)['outcome'], 'allow')

    def test_invalid_allocations_rejected(self):
        for value in (-1, 5, True, '1'):
            request = spec()
            request['autonomy']['child_tasks'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_spec(message('TaskSpec', request))

    def test_result_rejects_transcript_foreign_identity_and_evidence(self):
        ref = 'artifact://child/sha256:' + 'a' * 64
        payload = {'task_id': 'child', 'outcome': 'COMPLETED', 'artifacts': {'answer': ref},
                   'completion_ref': ref, 'concerns': []}
        self.assertEqual(validate_result(message('TaskResult', payload), 'child'), payload)
        invalid = [{**payload, 'transcript': ['full history']}, {**payload, 'task_id': 'another'},
                   {**payload, 'completion_ref': None}, {**payload, 'artifacts': {'answer': 'artifact://parent/sha256:' + 'a'*64}},
                   {**payload, 'concerns': ['x' * 8192]}]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(ValueError):
                validate_result(message('TaskResult', item), 'child')
        failure = {**payload, 'outcome': 'FAILED', 'completion_ref': None, 'artifacts': {}, 'concerns': ['Missing evidence']}
        self.assertEqual(validate_result(message('TaskResult', failure), 'child')['outcome'], 'FAILED')
