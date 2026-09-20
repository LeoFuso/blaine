"""Offline regression controls; synthetic provider responses, never live inference."""
import copy
import json
from pathlib import Path
import unittest

from runtime.kernel.contracts import message
from runtime.kernel.execution import policy_gate
from runtime.kernel.model import LocalModelCognition, decision_schema


EVIDENCE = Path(__file__).resolve().parents[1] / 'experiments/kernel-increment-8/evidence/verified-resolution'


class HumanCapabilityShapeTests(unittest.TestCase):
    def setUp(self):
        captured = json.loads((EVIDENCE / 'counterexample.json').read_text())
        self.packet = json.loads(captured['exact_provider_request']['messages'][1]['content'])
        self.spec = json.loads((EVIDENCE / 'acceptance/procedure-spec.json').read_text())['payload']
        turn = self.packet['payload']
        self.state = {'task_id': turn['task_id'], 'revision': turn['task_revision'],
                      'iteration': turn['iteration'], 'lifecycle': 'RUNNING', 'artifacts': {}}
        self.request = copy.deepcopy(self.spec['completion'][0]['evidence']['request'])

    def decision(self, value):
        turn = self.packet['payload']
        return message('CognitiveDecision', {k: turn[k] for k in ('task_id', 'task_revision', 'turn_id')} | {
            'next_action': {'type': 'INVOKE_CAPABILITY', 'capability': 'human.request', 'input': value}})

    def adapter(self, decision):
        return LocalModelCognition(transport=lambda _: {
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(decision)}}]
        })(self.packet)

    def test_input_schema_is_exact_and_valid_input_is_admitted(self):
        actions = decision_schema(self.packet['payload'])['properties']['payload']['properties']['next_action']['anyOf']
        action = next(a for a in actions if a['properties'].get('capability', {}).get('const') == 'human.request')
        schema = action['properties']['input']
        self.assertEqual(set(schema['properties']), {'request'})
        self.assertEqual(schema['required'], ['request'])
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(schema['properties']['request']['properties']['version'], {'const': 1})
        raw = self.decision({'request': self.request})
        self.assertEqual(self.adapter(raw), raw)
        self.assertEqual(policy_gate(raw, self.state, self.spec)['outcome'], 'allow')

    def test_extra_version_and_other_unknown_input_fields_rejected_without_repair(self):
        for name, value in [('version', 1), ('unexpected', 'forbidden'), ('kind', 'CapabilityInput')]:
            raw = self.decision({'request': self.request, name: value})
            before = copy.deepcopy(raw)
            with self.subTest(field=name):
                parsed = self.adapter(raw)
                self.assertEqual(parsed, before)
                self.assertEqual(policy_gate(parsed, self.state, self.spec)['outcome'], 'deny')
                self.assertEqual(parsed, before)

    def test_malformed_request_objects_not_repaired_or_defaulted(self):
        unknown = copy.deepcopy(self.request); unknown['unexpected'] = True
        missing_version = {k: v for k, v in self.request.items() if k != 'version'}
        for value in ({}, {'version': 1}, {'request': None}, {'request': unknown}, {'request': missing_version}):
            raw = self.decision(value)
            before = copy.deepcopy(raw)
            with self.subTest(input=value):
                parsed = self.adapter(raw)
                self.assertEqual(parsed, before)
                self.assertEqual(policy_gate(parsed, self.state, self.spec)['outcome'], 'deny')
                self.assertEqual(parsed, before)

    def test_nonobject_inputs_fail_before_returning_a_decision(self):
        for value in (None, [], 'request'):
            with self.subTest(input=value), self.assertRaises(ValueError):
                self.adapter(self.decision(value))


if __name__ == '__main__':
    unittest.main()
