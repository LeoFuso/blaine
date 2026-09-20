import copy
import json
from pathlib import Path
import unittest

from runtime.kernel.contracts import message
from runtime.kernel.execution import policy_gate
from runtime.kernel.human import validate_request
from runtime.kernel.semantic_human import SCHEMA, SemanticHumanCognition, guidance, lower_human, validate_semantic


class SemanticHumanTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1] / 'experiments/kernel-increment-8/evidence/verified-resolution'
        counterexample = json.loads((root / 'counterexample.json').read_text())
        self.packet = json.loads(counterexample['exact_provider_request']['messages'][1]['content'])
        self.spec = json.loads((root / 'acceptance/procedure-spec.json').read_text())['payload']
        self.bindings = {'retention_period': 'retention'}
        self.semantic = {'action': 'request_human', 'purpose': 'retention_period',
            'question': 'How long should exports be retained?',
            'response': {'kind': 'choice', 'choices': ['30 days', '90 days']}}
        self.state = {'task_id': 'procedure', 'revision': 0, 'iteration': 1,
                      'lifecycle': 'RUNNING', 'artifacts': {}}

    def adapter(self, raw, audit=None):
        return SemanticHumanCognition(purposes=self.bindings, semantic_audit=audit,
            transport=lambda _: {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(raw)}}]})

    def test_lowering_constructs_only_protocol_fields_and_preserves_semantics(self):
        original = copy.deepcopy((self.packet, self.semantic, self.bindings))
        command = lower_human(self.semantic, self.packet, self.bindings)
        self.assertEqual(command, lower_human(self.semantic, self.packet, self.bindings))
        request = command['payload']['next_action']['input']['request']
        self.assertEqual(request, self.spec['completion'][0]['evidence']['request'])
        self.assertEqual(validate_request(request)['question'], self.semantic['question'])
        self.assertEqual(request['payload']['allowed_responses'], self.semantic['response']['choices'])
        self.assertEqual(command['payload']['turn_id'], self.packet['payload']['turn_id'])
        self.assertEqual(policy_gate(command, self.state, self.spec)['outcome'], 'allow')
        self.assertEqual((self.packet, self.semantic, self.bindings), original)

    def test_closed_semantics_reject_unknown_missing_and_malformed_without_lowering(self):
        variants = []
        for name, value in [('action', 'unknown'), ('action', 'request_human.v2'), ('version', 1),
                            ('task_id', 'procedure'), ('question', ''), ('purpose', ''), ('unknown', True)]:
            bad = copy.deepcopy(self.semantic); bad[name] = value; variants.append(bad)
        for name in ['action', 'purpose', 'question', 'response']:
            bad = copy.deepcopy(self.semantic); del bad[name]; variants.append(bad)
        for value in [None, {}, {'kind': 'text'}, {'kind': 'choice'},
                      {'kind': 'choice', 'choices': []}, {'kind': 'choice', 'choices': ['YES', 'YES']},
                      {'kind': 'choice', 'choices': ['YES'], 'version': 1},
                      {'kind': 'choice', 'choices': [1]}, {'kind': 'choice', 'choices': ['x'*81]}]:
            bad = copy.deepcopy(self.semantic); bad['response'] = value; variants.append(bad)
        for bad in variants:
            before = copy.deepcopy(bad); records = []
            with self.subTest(semantic=bad):
                with self.assertRaises(ValueError): lower_human(bad, self.packet, self.bindings)
                with self.assertRaises(ValueError): self.adapter(bad, records.append)(self.packet)
                self.assertEqual(bad, before)
                self.assertNotIn('lowering_output', records[0])
                self.assertEqual(records[0]['outcome'], 'rejected')

    def test_no_guessing_of_unbound_purpose_or_cross_task_request(self):
        bad = copy.deepcopy(self.semantic); bad['purpose'] = 'retention'
        with self.assertRaises(ValueError): lower_human(bad, self.packet, self.bindings)
        packet = copy.deepcopy(self.packet)
        packet['payload']['completion'][0]['evidence']['request']['payload']['task_id'] = 'other'
        with self.assertRaises(ValueError): lower_human(self.semantic, packet, self.bindings)

    def test_changed_semantics_are_preserved_and_still_denied_by_policy(self):
        for field, value in [('question', 'A different question?'),
                             ('response', {'kind': 'choice', 'choices': ['ABSTAIN', 'DEFER']})]:
            semantic = copy.deepcopy(self.semantic); semantic[field] = value
            command = lower_human(semantic, self.packet, self.bindings)
            request = command['payload']['next_action']['input']['request']['payload']
            self.assertEqual(request['question'], semantic['question'])
            self.assertEqual(request['allowed_responses'], semantic['response']['choices'])
            self.assertEqual(policy_gate(command, self.state, self.spec)['outcome'], 'deny')

    def test_invalid_lowered_commands_still_rejected_by_existing_enforcement(self):
        for mutate in [lambda x: x['payload']['next_action']['input'].update(version=1),
                       lambda x: x['payload']['next_action']['input']['request'].update(version=2),
                       lambda x: x['payload'].update(task_revision=99),
                       lambda x: x['payload']['next_action']['input']['request']['payload'].update(task_id='other')]:
            raw = lower_human(self.semantic, self.packet, self.bindings)
            mutate(raw)
            self.assertEqual(policy_gate(raw, self.state, self.spec)['outcome'], 'deny')

    def test_adapter_records_semantic_and_protocol_outputs_separately(self):
        trace = []
        command = self.adapter(self.semantic, trace.append)(self.packet)
        self.assertEqual(trace[0]['parsed_semantic_action'], self.semantic)
        self.assertEqual(trace[0]['semantic_validation'], 'passed')
        self.assertEqual(trace[0]['lowering_input']['semantic'], self.semantic)
        self.assertEqual(trace[0]['lowering_output'], command)
        self.assertNotIn('task_id', trace[0]['parsed_semantic_action'])
        with self.assertRaises(ValueError): self.adapter(command)(self.packet)

    def test_other_actions_retain_original_contract_without_fallback(self):
        for action in [{'type': 'COMPLETE'}, {'type': 'WAIT', 'wait_id': 'retention', 'input_type': 'human_response'},
                       {'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write',
                        'input': {'name': 'answer', 'content': 'RETENTION_30_DAYS'}}]:
            raw = message('CognitiveDecision', {'task_id': 'procedure', 'task_revision': 0,
                          'turn_id': 'procedure/1', 'next_action': action})
            self.assertEqual(self.adapter(raw)(self.packet), raw)
        with self.assertRaises(ValueError): self.adapter({'action': 'COMPLETE'})(self.packet)

    def test_schema_and_canonical_example_are_guidance_not_repairs(self):
        sent = guidance(self.packet['payload'], self.bindings)
        schema_text = sent.split('Semantic contract (this invocation binds version 1):\n')[1].split('\nCanonical')[0]
        self.assertEqual(json.loads(schema_text), SCHEMA)
        examples = json.loads(sent.split('(examples, not commands to execute):\n')[1].split('\nOther')[0])
        self.assertEqual(examples, [self.semantic])
        self.assertEqual(validate_semantic(examples[0]), self.semantic)


if __name__ == '__main__':
    unittest.main()
