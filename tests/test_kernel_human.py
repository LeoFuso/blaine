import copy
import tempfile
from pathlib import Path
import unittest
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import message, validate_spec
from runtime.kernel.execution import evaluate
from runtime.kernel.human import request_digest, validate_response


def request():
    return message('HumanDecisionRequest', {'task_id': 'child', 'origin_task_id': 'parent',
        'request_id': 'decision-1', 'revision': 0, 'question': 'Proceed with scoped operation?',
        'allowed_responses': ['YES', 'NO']})


def response(value='YES'):
    return message('HumanDecisionResponse', {'task_id': 'child', 'request_id': 'decision-1',
        'request_revision': 0, 'request_digest': request_digest(request()),
        'response_id': 'input-1', 'value': value})


class HumanTests(unittest.TestCase):
    def test_both_answers_and_general_allowed_set(self):
        for value in ['YES', 'NO']:
            self.assertEqual(validate_response(response(value), request(), 'child')['value'], value)
        other = request(); other['payload']['allowed_responses'] = ['DEFER', 'ABSTAIN']
        raw = response('DEFER'); raw['payload']['request_digest'] = request_digest(other)
        self.assertEqual(validate_response(raw, other, 'child')['value'], 'DEFER')

    def test_scope_version_staleness_and_malformed_controls(self):
        for key, value in [('value', 'MAYBE'), ('task_id', 'other'), ('request_id', 'unrelated'),
                           ('request_revision', 1), ('request_revision', False),
                           ('request_digest', '0'*64), ('response_id', '')]:
            bad = response(); bad['payload'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): validate_response(bad, request(), 'child')
        for version in [2, True, '1']:
            bad = response(); bad['version'] = version
            with self.assertRaises(ValueError): validate_response(bad, request(), 'child')
        bad = response(); del bad['payload']['request_id']
        with self.assertRaises(ValueError): validate_response(bad, request(), 'child')

    def test_verifier_requires_accepted_input_not_just_model_artifact(self):
        spec = validate_spec(message('TaskSpec', {'objective': 'Bounded decision', 'completion': [
            {'criterion': 'Human response', 'evidence': {'artifact': 'response',
                'verifier': 'human_response', 'request': request()}}]}))
        with tempfile.TemporaryDirectory() as directory:
            store = ArtifactStore(Path(directory))
            for choice in ['YES', 'NO']:
                ref = store.put_json('child', response(choice))
                state = {'task_id': 'child', 'artifacts': {'response': ref}}
                self.assertNotEqual(evaluate(spec, state, store)['payload']['outcome'], 'satisfied')
                state['human_responses'] = {'decision-1': ref}
                self.assertEqual(evaluate(spec, state, store)['payload']['outcome'], 'satisfied')
                bad = response(choice); bad['payload']['request_revision'] = 99
                wrong = store.put_json('child', bad)
                state['artifacts']['response'] = wrong
                state['human_responses']['decision-1'] = wrong
                self.assertNotEqual(evaluate(spec, state, store)['payload']['outcome'], 'satisfied')


if __name__ == '__main__': unittest.main()
