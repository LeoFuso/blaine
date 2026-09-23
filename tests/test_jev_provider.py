"""Offline controls for the isolated Jev candidate. No network, no SDK, no key.

Every provider response here is a synthetic fake. The real authenticated call is
exercised only by the experiment's probe, never by this suite.
"""
import importlib.util
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def _load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


jev = _load('jev_provider_tests', 'experiments/jev-provider-carveout/jev_provider.py')
carveout = _load('jev_carveout_tests', 'experiments/jev-provider-carveout/carveout.py')

from runtime.kernel.instrument import ContinuationBoundary, ExecutionIdentity, validate_assessment  # noqa: E402
from runtime.kernel.worker_routing import (  # noqa: E402
    Assessment, ScriptedClassifier, Workload, select,
)
from runtime.kernel.frontier import WorkerBinding  # noqa: E402

SECRET = 'SECRET_FIXTURE_DO_NOT_EMIT'
LOCAL = WorkerBinding('local', 'fixture-family', 'fixture-local', 'fixture-model',
                      'http://127.0.0.1:8000/v1', False, ('code',), 1)
STRONG = WorkerBinding('strong', 'fixture-family', 'fixture-remote', 'fixture-large',
                       'https://provider.invalid/v1', True, ('code',), 3)
RANKS = {'local': 0, 'strong': 2}


def answer(kind='choice', **changes):
    base = {'choice': SimpleNamespace(type='choice', choice='JUST_RIGHT', confidence=0.81,
                                      probabilities={'JUST_RIGHT': 0.81, 'OVERKILL': 0.19}),
            'score': SimpleNamespace(type='score', score=0.4, confidence=0.7, probabilities={}),
            'noul': SimpleNamespace(type='noul', noul=0.25)}[kind]
    for key, value in changes.items():
        setattr(base, key, value)
    return base


def fake_client(answers, usage=(11, 3), model='jev-fixture', error=None):
    class Client:
        def __init__(self):
            self.calls = []

        def system_one(self, state, questions):
            self.calls.append({'state': state, 'questions': questions})
            if error is not None:
                raise error
            return SimpleNamespace(model=model, answers=dict(answers),
                                   usage=SimpleNamespace(input_tokens=usage[0], output_tokens=usage[1]))

        def close(self):
            self.closed = True
    return Client()


def provider(**kwargs):
    client = fake_client(**kwargs)
    return jev.JevProvider(client_factory=lambda: client), client


class CredentialTests(unittest.TestCase):
    def test_presence_is_checked_without_binding_the_value(self):
        with patch.dict(os.environ, {jev.API_KEY_ENV: SECRET}, clear=False):
            self.assertTrue(jev.credential_present())
        environment = {k: v for k, v in os.environ.items() if k != jev.API_KEY_ENV}
        with patch.dict(os.environ, environment, clear=True):
            self.assertFalse(jev.credential_present())

    def test_a_real_client_is_refused_without_a_credential(self):
        environment = {k: v for k, v in os.environ.items() if k != jev.API_KEY_ENV}
        with patch.dict(os.environ, environment, clear=True):
            with self.assertRaises(jev.JevUnavailable) as raised:
                jev.JevProvider().client()
        self.assertEqual(raised.exception.category, 'credential_absent')

    def test_no_credential_reaches_a_result_or_a_failure(self):
        with patch.dict(os.environ, {jev.API_KEY_ENV: SECRET}, clear=False):
            live, _ = provider(answers={'suitability': answer()})
            self.assertNotIn(SECRET, repr(live.ask({'a': 1}, {'suitability': {}})))
            broken, _ = provider(answers={}, error=RuntimeError(SECRET))
            with self.assertRaises(jev.JevUnavailable) as raised:
                broken.ask({'a': 1}, {'suitability': {}})
        self.assertNotIn(SECRET, repr(raised.exception.category))
        self.assertNotIn(SECRET, str(raised.exception))
        self.assertIsNone(raised.exception.__cause__)


class ProviderResultTests(unittest.TestCase):
    def test_usage_uses_the_existing_vocabulary_and_leaves_cost_unknown(self):
        live, _ = provider(answers={'suitability': answer()})
        result = live.ask({'a': 1}, {'suitability': {}})
        self.assertEqual(result['usage']['input_tokens'], 11)
        self.assertEqual(result['usage']['output_tokens'], 3)
        self.assertEqual(result['usage']['model_calls'], 1)
        self.assertIsNone(result['usage']['cost_microusd'])
        self.assertEqual(result['usage']['model_call_ids'], [])
        self.assertIn('UNKNOWN', result['cost_observability'])
        self.assertGreaterEqual(result['latency_ms'], 0)
        self.assertEqual(result['model'], 'jev-fixture')

    def test_absent_token_counters_stay_absent_rather_than_zero(self):
        live, _ = provider(answers={'suitability': answer()}, usage=(None, None))
        usage = live.ask({'a': 1}, {'suitability': {}})['usage']
        self.assertIsNone(usage['input_tokens'])
        self.assertIsNone(usage['output_tokens'])

    def test_answer_projection_is_closed(self):
        live, _ = provider(answers={'a': answer('choice'), 'b': answer('score'), 'c': answer('noul')})
        answers = live.ask({'a': 1}, {'a': {}})['answers']
        self.assertEqual(answers['a']['choice'], 'JUST_RIGHT')
        self.assertEqual(set(answers['b']), {'type', 'score', 'confidence'})
        self.assertEqual(answers['c'], {'type': 'noul', 'noul': 0.25})

    def test_malformed_answers_are_rejected(self):
        for bad in (answer(confidence=1.4), answer(probabilities={'x': 2.0}),
                    answer(probabilities={str(n): 0.1 for n in range(20)}),
                    SimpleNamespace(type='unreleased-kind')):
            with self.subTest(bad=bad), self.assertRaises((ValueError, TypeError)):
                live, _ = provider(answers={'suitability': bad})
                live.ask({'a': 1}, {'suitability': {}})

    def test_every_provider_failure_maps_to_a_bounded_category(self):
        for name, category in jev.FAILURES.items():
            with self.subTest(name=name):
                error = type(name, (Exception,), {})(SECRET)
                live, _ = provider(answers={}, error=error)
                with self.assertRaises(jev.JevUnavailable) as raised:
                    live.ask({'a': 1}, {'suitability': {}})
                self.assertEqual(raised.exception.category, category)
        live, _ = provider(answers={}, error=KeyError('unmapped'))
        with self.assertRaises(jev.JevUnavailable) as raised:
            live.ask({'a': 1}, {'suitability': {}})
        self.assertEqual(raised.exception.category, 'unexpected_error')


class RoutingCandidateTests(unittest.TestCase):
    def test_suitability_reuses_the_existing_vocabulary(self):
        live, client = provider(answers={'suitability': answer(choice='OVERKILL')})
        assessment = jev.JevWorkloadClassifier(live, RANKS).assess(Workload(('code',), 1), STRONG)
        self.assertIsInstance(assessment, Assessment)
        self.assertEqual(assessment.suitability, 'OVERKILL')
        self.assertEqual(assessment.binding_id, 'strong')
        self.assertEqual(assessment.cost_to_success_rank, RANKS['strong'])
        self.assertIn('scripted deployment input', assessment.reason)

    def test_only_declared_metadata_is_sent_to_the_provider(self):
        live, client = provider(answers={'suitability': answer()})
        jev.JevWorkloadClassifier(live, RANKS).assess(Workload(('code',), 1), STRONG)
        state = client.calls[0]['state']
        self.assertEqual(set(state), {'required_capabilities', 'minimum_quality',
                                      'binding_capabilities', 'binding_quality'})
        self.assertNotIn('destination', repr(state))
        self.assertNotIn('provider', repr(state))

    def test_an_answer_outside_the_vocabulary_is_refused(self):
        live, _ = provider(answers={'suitability': answer(choice='PERFECT')})
        with self.assertRaises(jev.JevUnavailable) as raised:
            jev.JevWorkloadClassifier(live, RANKS).assess(Workload(('code',), 1), STRONG)
        self.assertEqual(raised.exception.category, 'invalid_response')

    def test_the_candidate_never_produces_authorization(self):
        live, _ = provider(answers={'suitability': answer(choice='JUST_RIGHT')})
        classifier = jev.JevWorkloadClassifier(live, RANKS)
        denied = {'local': {'outcome': 'deny'}, 'strong': {'outcome': 'deny'}}
        result = select(Workload(('code',), 1), (LOCAL, STRONG), classifier, denied)
        # Every candidate was judged suitable, and routing still selects nothing.
        self.assertEqual(result['outcome'], 'STOP_OR_ESCALATE')
        self.assertIsNone(result['selected_binding'])


class ShadowModeTests(unittest.TestCase):
    def shadow(self, **kwargs):
        live, client = provider(**kwargs)
        accepted = ScriptedClassifier(RANKS)
        return jev.ShadowClassifier(accepted, jev.JevWorkloadClassifier(live, RANKS)), accepted, client

    def test_routing_outcome_is_the_accepted_one(self):
        shadow, accepted, _ = self.shadow(answers={'suitability': answer(choice='UNDERPOWERED')})
        workload = Workload(('code',), 1)
        with_shadow = select(workload, (LOCAL, STRONG), shadow,
                             {'local': {'outcome': 'allow'}, 'strong': {'outcome': 'allow'}})
        without = select(workload, (LOCAL, STRONG), accepted,
                         {'local': {'outcome': 'allow'}, 'strong': {'outcome': 'allow'}})
        self.assertEqual(with_shadow, without)
        self.assertEqual(with_shadow['selected_binding'], 'local')

    def test_disagreement_is_recorded_not_applied(self):
        shadow, _, _ = self.shadow(answers={'suitability': answer(choice='UNDERPOWERED')})
        shadow.assess(Workload(('code',), 1), LOCAL)
        observation = shadow.observations[0]
        self.assertEqual(observation['accepted_suitability'], 'JUST_RIGHT')
        self.assertEqual(observation['candidate_suitability'], 'UNDERPOWERED')
        self.assertFalse(observation['agreement'])

    def test_candidate_failure_never_breaks_routing(self):
        shadow, _, _ = self.shadow(answers={}, error=RuntimeError('provider down'))
        decision = shadow.assess(Workload(('code',), 1), LOCAL)
        self.assertEqual(decision.suitability, 'JUST_RIGHT')
        self.assertEqual(shadow.observations[0]['candidate_failure'], 'unexpected_error')
        self.assertIsNone(shadow.observations[0]['candidate_suitability'])

    def test_a_candidate_changing_binding_identity_is_rejected(self):
        class Liar:
            def assess(self, workload, binding):
                return Assessment('other', 'OVERKILL', 0, 'fixture')
        shadow = jev.ShadowClassifier(ScriptedClassifier(RANKS), Liar())
        shadow.assess(Workload(('code',), 1), LOCAL)
        self.assertEqual(shadow.observations[0]['candidate_failure'],
                         'candidate_changed_binding_identity')


class BoundaryObserverTests(unittest.TestCase):
    def boundary(self):
        return ContinuationBoundary(ExecutionIdentity('task', 'run:1'), 2, 'tool_results',
                                    model_invocations=2, tool_invocations=1, last_tool_outcome='success')

    def test_classification_becomes_a_label_and_never_an_intervention(self):
        live, client = provider(answers={'progress': answer(choice='stalled', confidence=0.93)})
        assessment = jev.JevBoundaryObserver(live).inspect(self.boundary())
        validate_assessment(assessment, 'jev-boundary-observer')
        self.assertEqual(assessment['outcome'], 'PROCEED')
        self.assertEqual(assessment['label'], 'stalled')
        self.assertEqual(assessment['score'], 0.93)
        self.assertEqual(assessment['input_tokens'], 11)
        self.assertNotIn('admitted_intervention', assessment)

    def test_an_unavailable_provider_abstains_instead_of_blocking(self):
        live, _ = provider(answers={}, error=RuntimeError('provider down'))
        assessment = jev.JevBoundaryObserver(live).inspect(self.boundary())
        validate_assessment(assessment, 'jev-boundary-observer')
        self.assertEqual(assessment['outcome'], 'ABSTAIN')
        self.assertEqual(assessment['detail'], 'unexpected_error')

    def test_only_counters_and_digest_presence_leave_the_boundary(self):
        live, client = provider(answers={'progress': answer(choice='productive')})
        jev.JevBoundaryObserver(live).inspect(self.boundary())
        state = client.calls[0]['state']
        self.assertEqual(state['evidence_digest_present'], False)
        self.assertNotIn('task', repr(state))
        self.assertNotIn('run:1', repr(state))


class CarveoutPreparationTests(unittest.TestCase):
    def row(self, **changes):
        base = {'task_id': 'fixture-task', 'binding_id': 'local',
                'accepted_suitability': 'JUST_RIGHT', 'candidate_suitability': 'JUST_RIGHT',
                'agreement': True, 'candidate_failure': None}
        return base | changes

    def test_comparison_rows_are_closed_and_use_the_existing_vocabulary(self):
        carveout.validate_observation(self.row())
        for bad in ({'accepted_suitability': 'PERFECT'}, {'candidate_suitability': 'PERFECT'},
                    {'human_label': 'PERFECT'}, {'extra': 1},
                    {'candidate_suitability': None},
                    {'candidate_suitability': 'JUST_RIGHT', 'candidate_failure': 'rate_limited'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                carveout.validate_observation(self.row(**bad))

    def test_nothing_is_concluded_below_the_sample_floor(self):
        summary = carveout.aggregate([self.row(task_id=f'fixture-{n}') for n in range(5)])
        self.assertEqual(summary['verdict'], 'INSUFFICIENT_SAMPLE')
        self.assertEqual(summary['adoption_decision'], 'NOT_MADE_HERE')
        self.assertFalse(summary['routing_changed_by_this_comparison'])
        self.assertIn('UNKNOWN', summary['monetary_cost'])

    def test_an_unlabelled_full_sample_is_still_not_ready_for_a_verdict(self):
        rows = [self.row(task_id=f'fixture-{n}') for n in range(carveout.MINIMUM_SAMPLE)]
        summary = carveout.aggregate(rows)
        self.assertEqual(summary['verdict'], 'UNLABELLED')
        self.assertEqual(summary['agreement_with_accepted'], 1.0)
        self.assertIsNone(summary['candidate_error_vs_label'])

    def test_labelled_rows_produce_comparable_error_rates(self):
        rows = [self.row(task_id=f'fixture-{n}', human_label='JUST_RIGHT')
                for n in range(carveout.MINIMUM_SAMPLE)]
        rows[0] = self.row(task_id='fixture-0', candidate_suitability='OVERKILL',
                           agreement=False, human_label='JUST_RIGHT')
        summary = carveout.aggregate(rows)
        self.assertEqual(summary['verdict'], 'READY_FOR_REVIEW')
        self.assertEqual(summary['accepted_error_vs_label'], 0.0)
        self.assertGreater(summary['candidate_error_vs_label'], 0.0)
        self.assertEqual(summary['adoption_decision'], 'NOT_MADE_HERE')

    def test_a_shadow_observation_fits_the_comparison_row(self):
        shadow, _, _ = ShadowModeTests().shadow(answers={'suitability': answer()})
        shadow.assess(Workload(('code',), 1), LOCAL)
        observed = shadow.observations[0]
        row = {'task_id': 'fixture-task', 'binding_id': observed['binding_id'],
               'accepted_suitability': observed['accepted_suitability'],
               'candidate_suitability': observed['candidate_suitability'],
               'agreement': observed['agreement'], 'candidate_failure': observed['candidate_failure'],
               'workload': observed['workload'], 'candidate_reason': observed['candidate_reason']}
        self.assertEqual(carveout.validate_observation(row)['agreement'], True)


class NotAdoptedTests(unittest.TestCase):
    def test_the_kernel_contains_no_jev_reference(self):
        for path in sorted((ROOT / 'runtime').rglob('*.py')):
            with self.subTest(path=path.name):
                body = path.read_text().lower()
                self.assertNotIn('jev', body)
                self.assertNotIn('typesafe', body)

    def test_the_accepted_classifier_remains_the_scripted_one(self):
        accepted = ScriptedClassifier(RANKS)
        assessment = accepted.assess(Workload(('code',), 1), LOCAL)
        self.assertEqual(assessment.suitability, 'JUST_RIGHT')
        self.assertIn('Scripted', assessment.reason)


if __name__ == '__main__':
    unittest.main()
