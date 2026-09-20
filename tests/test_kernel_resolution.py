import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.context import reconstruct
from runtime.kernel.contracts import MAX_CONTENT, MAX_PACKET, encode, message, validate_spec
from runtime.kernel.execution import evaluate
from runtime.kernel.human import request_digest


class ResolutionTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.store = ArtifactStore(self.root / 'artifacts')
        self.request = message('HumanDecisionRequest', {'task_id': 'task', 'origin_task_id': 'origin',
            'request_id': 'retention', 'revision': 3, 'question': 'Retention duration?',
            'allowed_responses': ['30 days', '90 days']})
        self.spec = validate_spec(message('TaskSpec', {'objective': 'Retention is unresolved.',
            'completion': [{'criterion': 'Clarification', 'evidence': {'artifact': 'response',
                'verifier': 'human_response', 'request': self.request}},
                {'criterion': 'Deliverable', 'evidence': {'artifact': 'answer',
                    'sha256': hashlib.sha256(b'exact').hexdigest()}}]}))
        self.response = message('HumanDecisionResponse', {'task_id': 'task', 'request_id': 'retention',
            'request_revision': 3, 'request_digest': request_digest(self.request),
            'response_id': 'response-1', 'value': '30 days'})
        self.state = {'task_id': 'task', 'revision': 9, 'iteration': 7,
            'active_specialist': 'coordinator', 'spec_ref': self.store.put_json('task', message('TaskSpec', self.spec)),
            'observation_ref': self.store.put_json('task', message('CapabilityResult', {'operation_id': 'task/6',
                'outcome': 'success', 'artifacts': {}, 'output': {}, 'error': None})),
            'artifacts': {}, 'human_responses': {}}

    def accept(self, raw=None):
        ref = self.store.put_json('task', raw if raw is not None else self.response)
        self.state['artifacts']['response'] = ref
        self.state['human_responses']['retention'] = ref
        return ref

    def packet(self):
        return reconstruct(self.state, self.spec, self.store)

    def resolutions(self):
        return [x for x in self.packet()['payload']['context'] if isinstance(x['content'], dict)
                and x['content'].get('kind') == 'HumanDecisionResolution']

    def test_no_response_does_not_invent_a_resolution(self):
        self.assertEqual(self.resolutions(), [])

    def test_verified_resolution_outlives_observation_without_mutating_intent(self):
        ref = self.accept()
        before = copy.deepcopy((self.state, self.spec))
        packet = self.packet()
        item = self.resolutions()[0]
        self.assertEqual(item['content'], message('HumanDecisionResolution', {
            'task_id': 'task', 'origin_task_id': 'origin', 'request_id': 'retention',
            'request_revision': 3, 'value': '30 days', 'status': 'verified', 'response_ref': ref}))
        self.assertEqual(item['source'], ref)
        self.assertEqual(item['authority'], 'artifact')
        self.assertLessEqual(len(encode(item)), MAX_CONTENT)
        self.assertLessEqual(len(encode(packet)), MAX_PACKET)
        self.assertEqual(packet['payload']['observations'][0]['kind'], 'CapabilityResult')
        self.assertEqual(packet['payload']['objective'], 'Retention is unresolved.')
        self.assertEqual((self.state, self.spec), before)
        self.assertTrue(any('take precedence' in str(x['content']) for x in packet['payload']['context']))

    def test_wrong_task_request_stale_malformed_and_unverified_are_not_resolutions(self):
        variants = []
        for key, value in [('task_id', 'other'), ('request_id', 'unrelated'), ('request_revision', 2),
                           ('request_digest', '0'*64), ('value', 'forever')]:
            raw = copy.deepcopy(self.response); raw['payload'][key] = value; variants.append(raw)
        for version in [2, True, '1']:
            raw = copy.deepcopy(self.response); raw['version'] = version; variants.append(raw)
        raw = copy.deepcopy(self.response); del raw['payload']['value']; variants.append(raw)
        for raw in variants:
            with self.subTest(raw=raw):
                self.accept(raw)
                self.assertEqual(self.resolutions(), [])
                self.assertNotEqual(evaluate(self.spec, self.state, self.store)['payload']['outcome'], 'satisfied')
        ref = self.accept()
        self.state['human_responses'] = {}
        self.assertEqual(self.resolutions(), [])
        self.assertNotIn(ref, encode(self.packet()).decode())

    def test_unrelated_response_and_prior_request_revision_do_not_leak(self):
        self.accept()
        other_request = copy.deepcopy(self.request)
        other_request['payload'].update(request_id='unrelated', allowed_responses=['EXCLUDED_SENTINEL'])
        other = copy.deepcopy(self.response)
        other['payload'].update(request_id='unrelated', value='EXCLUDED_SENTINEL',
                                request_digest=request_digest(other_request))
        ref = self.store.put_json('task', other)
        self.state['human_responses']['unrelated'] = ref
        self.state['artifacts']['other-response'] = ref
        other_spec = {**self.spec, 'completion': [{'criterion': 'Other decision', 'evidence': {
            'artifact': 'other-response', 'verifier': 'human_response', 'request': other_request}}]}
        self.assertEqual(evaluate(other_spec, self.state, self.store)['payload']['outcome'], 'satisfied')
        packet = encode(self.packet()).decode()
        self.assertNotIn('EXCLUDED_SENTINEL', packet)
        self.assertNotIn(ref, packet)
        self.assertNotIn('other-response', packet)
        self.assertEqual(len(self.resolutions()), 1)
        # The accepted request changes in this test fixture; its prior response
        # cannot become a resolution of the new request just because it persists.
        self.spec['completion'][0]['evidence']['request']['payload']['revision'] = 4
        self.assertEqual(self.resolutions(), [])

    def test_corrupt_artifact_cannot_be_projected(self):
        ref = self.accept()
        (self.store.root / 'task' / ref.rsplit(':', 1)[1]).write_text('tampered')
        self.assertEqual(self.resolutions(), [])

    def test_response_alone_cannot_complete_exact_deliverable(self):
        self.accept()
        result = evaluate(self.spec, self.state, self.store)['payload']
        self.assertEqual(result['outcome'], 'unsatisfied')
        self.assertEqual([c['outcome'] for c in result['criteria']], ['satisfied', 'unsatisfied'])
        self.state['artifacts']['answer'] = self.store.put('task', b'exact')
        self.assertEqual(evaluate(self.spec, self.state, self.store)['payload']['outcome'], 'satisfied')

    def test_fresh_process_reconstructs_from_persisted_artifact(self):
        self.accept()
        inputs = self.root / 'inputs.json'
        inputs.write_bytes(encode({'state': self.state, 'spec': self.spec}))
        code = '''import json,sys
from pathlib import Path
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.context import reconstruct
data=json.loads(Path(sys.argv[1]).read_text())
print(json.dumps(reconstruct(data['state'],data['spec'],ArtifactStore(Path(sys.argv[2])))))
'''
        output = subprocess.check_output([sys.executable, '-c', code, str(inputs), str(self.store.root)], text=True)
        self.assertEqual(json.loads(output), self.packet())


if __name__ == '__main__':
    unittest.main()
