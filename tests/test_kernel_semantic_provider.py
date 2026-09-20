import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.context import reconstruct
from runtime.kernel.contracts import message, validate_spec, encode
from runtime.kernel.execution import evaluate, policy_gate
from runtime.kernel.human import request_digest
from runtime.kernel.semantic_bridge import SemanticDecisionBridge
from runtime.kernel.semantic_provider import JsonSemanticDecisionProvider, validate_semantic


class FixedProvider:
    def __init__(self, decision): self.decision = decision; self.inputs = []
    def decide(self, context, admissible_actions):
        self.inputs.append(copy.deepcopy(context))
        return copy.deepcopy(self.decision)


class SemanticProviderTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(); self.addCleanup(directory.cleanup)
        self.store = ArtifactStore(Path(directory.name))
        self.task, self.req = 'PRIVATE_TASK_7', 'PRIVATE_REQUEST_2'
        self.request = message('HumanDecisionRequest', {'task_id': self.task, 'origin_task_id': 'PRIVATE_ORIGIN_9',
            'request_id': self.req, 'revision': 0, 'question': 'Retention period?', 'allowed_responses': ['30 days', '90 days']})
        self.spec = validate_spec(message('TaskSpec', {'objective': 'Retention is unresolved. Produce RETENTION_30_DAYS after clarification.',
            'capabilities': ['human.request', 'artifact.write'], 'autonomy': {'allowed': ['human.request', 'artifact.write']},
            'completion': [{'criterion': 'Human clarification', 'evidence': {'artifact': 'response', 'verifier': 'human_response', 'request': self.request}},
                {'criterion': 'Exact deliverable', 'evidence': {'artifact': 'answer', 'sha256': hashlib.sha256(b'RETENTION_30_DAYS').hexdigest()}}]}))
        self.state = {'task_id': self.task, 'revision': 0, 'iteration': 1, 'lifecycle': 'RUNNING',
            'active_specialist': 'coordinator', 'spec_ref': self.store.put_json(self.task, message('TaskSpec', self.spec)),
            'observation_ref': None, 'artifacts': {}, 'human_responses': {}}
        self.semantic = {'action': 'REQUEST_HUMAN', 'purpose': 'retention_period', 'question': 'Retention period?',
                         'response': {'kind': 'choice', 'choices': ['30 days', '90 days']}}
        self.provider = FixedProvider(self.semantic)
        self.bridge = SemanticDecisionBridge(self.provider, self.store, 'retention_period', self.req, 'answer')

    def packet(self): return reconstruct(self.state, self.spec, self.store)

    def publish(self):
        self.state['artifacts']['human-request-' + self.req] = self.store.put_json(self.task, self.request)

    def resolve(self):
        raw = message('HumanDecisionResponse', {'task_id': self.task, 'request_id': self.req,
            'request_revision': 0, 'request_digest': request_digest(self.request), 'response_id': 'PRIVATE_RESPONSE_3', 'value': '30 days'})
        ref = self.store.put_json(self.task, raw)
        self.state['artifacts']['response'] = ref
        self.state['human_responses'][self.req] = ref

    def test_request_and_wait_preconditions_reject_without_substitution(self):
        wait = {'action': 'WAIT', 'purpose': 'retention_period'}
        self.assertEqual(self.bridge.project(self.packet())['clarification']['status'], 'missing')
        with self.assertRaisesRegex(ValueError, 'No external condition'): self.bridge.lower(wait, self.packet())
        self.assertEqual(policy_gate(self.bridge(self.packet()), self.state, self.spec)['outcome'], 'allow')
        self.publish()
        self.assertEqual(self.bridge.project(self.packet())['clarification']['status'], 'pending')
        with self.assertRaisesRegex(ValueError, 'already pending'): self.bridge.lower(self.semantic, self.packet())
        # WAIT stays representable, but this known blocking path cannot ask cognition for it.
        self.assertEqual(validate_semantic(wait), wait)
        self.assertEqual(self.bridge.project(self.packet())['allowed_actions'], [])
        with self.assertRaisesRegex(ValueError, 'hard-admissible'): self.bridge.lower(wait, self.packet())
        self.resolve()
        with self.assertRaises(ValueError): self.bridge.lower(wait, self.packet())
        with self.assertRaises(ValueError): self.bridge.lower(self.semantic, self.packet())

    def test_pending_requires_exact_published_request_not_claim(self):
        self.state['artifacts']['human-request-' + self.req] = self.store.put(self.task, b'published')
        self.assertEqual(self.bridge.project(self.packet())['clarification']['status'], 'missing')

    def test_provider_input_contains_no_runtime_metadata_or_commands(self):
        self.publish(); self.resolve()
        self.state['artifacts']['answer'] = self.store.put(self.task, b'RETENTION_30_DAYS')
        self.provider.decision = {'action': 'COMPLETE'}
        before = copy.deepcopy((self.state, self.spec))
        self.bridge(self.packet())
        context = self.provider.inputs[0]
        self.assertEqual(context['clarification']['value'], '30 days')
        self.assertEqual(context['deliverable'], {'present': True, 'content_verified': True})
        sent = encode(context).decode()
        for token in ['PRIVATE_', 'artifact://', 'CognitiveDecision', 'HumanDecision', 'version', 'task_id', 'request_id', 'sha256', 'human.request', 'artifact.write']:
            self.assertNotIn(token, sent)
        self.assertEqual((self.state, self.spec), before)
        self.assertEqual(context['goal'], self.spec['objective'])
        self.assertNotIn('history', context)

    def test_runtime_fields_unknown_fields_and_hybrids_are_rejected(self):
        bad_values = [{'action': 'UNKNOWN'}, {'version': 1, 'kind': 'CognitiveDecision', 'payload': {}},
            {'action': 'COMPLETE', 'version': 1}, {'action': 'WAIT'}, {'action': 'PRODUCE_ARTIFACT'},
            {'action': 'PRODUCE_ARTIFACT', 'content': 'x', 'input': {}},
            {'action': 'REQUEST_HUMAN', 'purpose': 'retention_period', 'question': 'Retention period?', 'response': {'kind': 'text'}}]
        for key in ['task_id', 'request_id', 'provenance', 'unknown']:
            bad_values.append({**self.semantic, key: 'forbidden'})
        for key in self.semantic:
            bad = copy.deepcopy(self.semantic); del bad[key]; bad_values.append(bad)
        for bad in bad_values:
            with self.subTest(raw=bad), self.assertRaises(ValueError): self.bridge.lower(bad, self.packet())

    def test_lowering_preserves_semantics_and_existing_policy_remains_authoritative(self):
        command = self.bridge.lower(self.semantic, self.packet())
        self.assertEqual(command['payload']['next_action']['input']['request'], self.request)
        altered = copy.deepcopy(self.semantic); altered['question'] = 'Different question?'
        raw = self.bridge.lower(altered, self.packet())
        self.assertEqual(raw['payload']['next_action']['input']['request']['payload']['question'], altered['question'])
        self.assertEqual(policy_gate(raw, self.state, self.spec)['outcome'], 'deny')
        command['payload']['next_action']['input']['version'] = 1
        self.assertEqual(policy_gate(command, self.state, self.spec)['outcome'], 'deny')
        produce = self.bridge.lower({'action': 'PRODUCE_ARTIFACT', 'content': 'exact bytes\n'}, self.packet())
        self.assertEqual(produce['payload']['next_action']['input'], {'name': 'answer', 'content': 'exact bytes\n'})

    def test_completion_and_resolution_remain_independent(self):
        complete = self.bridge.lower({'action': 'COMPLETE'}, self.packet())
        self.assertEqual(complete['payload']['next_action'], {'type': 'COMPLETE'})
        self.assertEqual(evaluate(self.spec, self.state, self.store)['payload']['outcome'], 'unsatisfied')
        self.resolve()
        self.assertEqual(self.bridge.project(self.packet())['clarification']['status'], 'resolved')
        self.assertEqual(evaluate(self.spec, self.state, self.store)['payload']['outcome'], 'unsatisfied')
        self.state['artifacts']['answer'] = self.store.put(self.task, b'RETENTION_30_DAYS')
        self.assertEqual(evaluate(self.spec, self.state, self.store)['payload']['outcome'], 'satisfied')
        self.state['human_responses'] = {}
        self.assertEqual(self.bridge.project(self.packet())['clarification']['status'], 'missing')

    def test_provider_cannot_mutate_context_to_authorize_wait(self):
        class MutatingProvider:
            def decide(self, context, admissible_actions):
                context['clarification']['status'] = 'pending'
                return {'action': 'WAIT', 'purpose': 'retention_period'}
        bridge = SemanticDecisionBridge(MutatingProvider(), self.store, 'retention_period', self.req, 'answer')
        with self.assertRaisesRegex(ValueError, 'No external condition'): bridge(self.packet())
        self.assertEqual(bridge.project(self.packet())['clarification']['status'], 'missing')

    def test_replacement_provider_needs_only_semantic_context(self):
        class OtherProvider:
            def decide(self, context, admissible_actions):
                self.keys = set(context)
                return {'action': 'COMPLETE'}
        other = OtherProvider()
        bridge = SemanticDecisionBridge(other, self.store, 'retention_period', self.req, 'answer')
        command = bridge(self.packet())
        self.assertEqual(command, self.bridge.lower({'action': 'COMPLETE'}, self.packet()))
        self.assertEqual(other.keys, {'goal', 'clarification', 'deliverable', 'procedure', 'allowed_actions'})

    def test_hard_projection_filters_policy_without_selecting_strategy(self):
        context = self.bridge.project(self.packet())
        self.assertEqual(context['allowed_actions'], ['REQUEST_HUMAN', 'PRODUCE_ARTIFACT', 'COMPLETE'])
        self.spec['autonomy']['allowed'] = ['artifact.write']
        context = self.bridge.project(self.packet())
        self.assertEqual(context['allowed_actions'], ['PRODUCE_ARTIFACT', 'COMPLETE'])
        self.provider.decision = self.semantic
        with self.assertRaisesRegex(ValueError, 'hard-admissible'): self.bridge(self.packet())
        self.assertEqual(self.state['artifacts'], {})

    def test_pending_never_calls_provider_and_resolved_never_exposes_request_shape(self):
        self.publish()
        with self.assertRaisesRegex(ValueError, 'No admissible'): self.bridge(self.packet())
        self.assertEqual(self.provider.inputs, [])
        self.resolve()
        sent = []
        def transport(body):
            sent.append(body)
            return {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"action":"PRODUCE_ARTIFACT","content":"RETENTION_30_DAYS"}'}}]}
        bridge = SemanticDecisionBridge(JsonSemanticDecisionProvider('fixture', transport), self.store, 'retention_period', self.req, 'answer')
        bridge(self.packet())
        messages = encode(sent[0]['messages']).decode()
        self.assertNotIn('REQUEST_HUMAN', messages)
        self.assertNotIn('WAIT', messages)
        self.assertIn('PRODUCE_ARTIFACT', messages)
        self.assertIn('COMPLETE', messages)

    def test_legal_rewrite_not_masked_by_quality_preference(self):
        self.publish(); self.resolve()
        self.state['artifacts']['answer'] = self.store.put(self.task, b'RETENTION_30_DAYS')
        self.assertEqual(self.bridge.project(self.packet())['allowed_actions'], ['PRODUCE_ARTIFACT', 'COMPLETE'])
        # Runtime skips cognition in this completed state; projection itself does not choose a strategy.

    def test_json_provider_sees_and_returns_only_semantics(self):
        sent = []
        def transport(body):
            sent.append(body)
            return {'choices': [{'finish_reason': 'stop', 'message': {'content': '{"action":"COMPLETE"}'}}]}
        provider = JsonSemanticDecisionProvider('fixture-model', transport)
        context = self.bridge.project(self.packet())
        self.assertEqual(provider.decide(context, context['allowed_actions']), {'action': 'COMPLETE'})
        self.assertEqual(json.loads(sent[0]['messages'][1]['content']), context)
        self.assertNotIn('tools', sent[0]); self.assertNotIn('response_format', sent[0])
        self.assertNotIn('CognitiveDecision', sent[0]['messages'][0]['content'])
        for bad in ['{"action":"COMPLETE","action":"WAIT"}', 'not json']:
            provider = JsonSemanticDecisionProvider('fixture-model', lambda _: {'choices': [
                {'finish_reason': 'stop', 'message': {'content': bad}}]})
            with self.assertRaises(ValueError): provider.decide(context, context['allowed_actions'])


if __name__ == '__main__': unittest.main()
