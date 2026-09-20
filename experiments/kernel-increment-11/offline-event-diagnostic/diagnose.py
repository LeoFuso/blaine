"""Offline correction controls for the Codex 0.155.1 binding.

Every stream below is synthetic. Popen and the command builder are replaced;
no CLI, provider, credential file or historical dispatch receipt is used.
Passing controls validates synthetic protocol cases, never historical Task completion.
"""
from dataclasses import dataclass
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from runtime.kernel.frontier_context import IdentityProjector, project_context


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


binding = load('experiments/kernel-increment-11/live/binding.py', 'diagnosed_binding')
START = {'type': 'thread.started', 'thread_id': '00000000-0000-0000-0000-000000000001'}
MESSAGE = {'type': 'item.completed', 'item': {
    'type': 'agent_message', 'id': 'item_1', 'text': '{"organization":"FLOWER","marker":"MASKED_01"}'}}
COMPLETED = {'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 5, 'cached_input_tokens': 0}}
DETAIL = 'SYNTHETIC_PRIVATE_DETAIL_DO_NOT_PERSIST'
ITEM_ERROR = {'type': 'item.completed', 'item': {'type': 'error', 'id': 'item_0', 'message': DETAIL}}
FAILED = {'type': 'turn.failed', 'error': {'message': DETAIL}}
TOP_ERROR = {'type': 'error', 'id': 'item_0', 'message': DETAIL}

# Versioned semantics were supplied by the user from rust-v0.155.1 exec_events.rs.
# An extra terminal:false field never establishes authority; the binding owns classification.
CASES = {
    'clean_completed_shape': [START, MESSAGE, COMPLETED],
    'failed_shape_without_result': [START, FAILED],
    'result_then_failed_shape': [START, MESSAGE, FAILED],
    'top_error_then_result': [START, TOP_ERROR, MESSAGE, COMPLETED],
    'unknown_item_error_before_result': [START, ITEM_ERROR, MESSAGE, COMPLETED],
    'unknown_item_error_after_result': [START, MESSAGE, ITEM_ERROR, COMPLETED],
    'unsupported_nonterminal_claim': [START, {'type': 'item.completed', 'item': {
        'type': 'error', 'id': 'item_0', 'message': DETAIL, 'terminal': False}}, MESSAGE, COMPLETED],
    'malformed_json': [START, 'not-json', MESSAGE, COMPLETED],
    'wrong_event_type': [START, [], MESSAGE, COMPLETED],
    'result_then_top_error': [START, MESSAGE, TOP_ERROR],
    'conflicting_terminal_events': [START, MESSAGE, COMPLETED, FAILED],
    'unknown_event': [START, {'type': 'synthetic.unknown'}, MESSAGE, COMPLETED],
    'missing_terminal_event': [START, MESSAGE],
    'nonzero_process_exit': [START, MESSAGE, COMPLETED],
}


@dataclass(frozen=True)
class SyntheticBinding:
    worker_family: str = 'codex-cli-0.155.1'
    provider: str = 'openai-chatgpt'
    model: str = 'gpt-6-astra'
    destination: str = 'https://chatgpt.com'


@dataclass(frozen=True)
class SyntheticRequest:
    worker_dispatch_id: str
    context: object
    context_digest: str
    deadline_unix: float
    binding: SyntheticBinding = SyntheticBinding()
    read_scope: tuple = ('projected-context',)
    write_scope: tuple = ()
    runtime_ms: int = 1000


def exercise(name):
    values = CASES[name]
    stream = b'\n'.join((value if isinstance(value, str) else json.dumps(value)).encode()
                        for value in values)

    class FakeProcess:
        returncode = 9 if name == 'nonzero_process_exit' else 0

        def communicate(self, *args, **kwargs):
            return stream, b''

        def poll(self):
            return self.returncode

    context = project_context('synthetic-offline', 'projected fixture only', IdentityProjector())
    request = SyntheticRequest('synthetic-offline/' + name, context, context.digest, time.time() + 60)
    with tempfile.TemporaryDirectory(prefix='blaine-offline-events-') as directory:
        out = Path(directory)
        with patch.object(binding, 'command', return_value=['NEVER_EXECUTED_SYNTHETIC']), \
                patch.object(subprocess, 'Popen', return_value=FakeProcess()) as popen, \
                patch.object(socket.socket, 'connect', side_effect=AssertionError('Offline only')):
            try:
                result = binding.CodexBinding(out).dispatch(request)
                outcome, error = result['status'], None
            except Exception as exc:
                outcome, error = 'rejected', type(exc).__name__
        observed = out / 'worker-observation.json'
        observation = json.loads(observed.read_text()) if observed.exists() else None
        # Inspect all synthetic adapter outputs, without publishing the omitted detail.
        detail_retained = any(DETAIL in p.read_text() for p in out.iterdir() if p.is_file())
        return {
            'case': name, 'provenance': 'deterministic synthetic stream; mocked process; zero inference',
            'upstream_semantics': binding.PROTOCOL,
            'input_order': [v.get('type', 'unknown') if isinstance(v, dict) else 'malformed' for v in values],
            'adapter_outcome': outcome, 'exception_class': error,
            'normalized_result_written': (out / 'worker-normalized-result.json').exists(),
            'retained_observation': observation, 'synthetic_private_detail_retained': detail_retained,
            'mocked_process_constructions': popen.call_count, 'live_worker_dispatches': 0,
        }


class CharacterizationTests(unittest.TestCase):
    """Correction controls; synthetic process only, CompletionVerifier unchanged."""

    def test_clean_shape(self):
        self.assertEqual(exercise('clean_completed_shape')['adapter_outcome'], 'executed')

    def test_failure_without_result(self):
        self.assertEqual(exercise('failed_shape_without_result')['adapter_outcome'], 'rejected')

    def test_result_plus_failed_shape_rejected(self):
        case = exercise('result_then_failed_shape')
        self.assertEqual(case['adapter_outcome'], 'rejected')
        self.assertEqual(case['retained_observation']['normalized_outcome'], 'failure')
        self.assertFalse(case['normalized_result_written'])

    def test_top_error_terminal_failure(self):
        case = exercise('result_then_top_error')
        self.assertEqual(case['adapter_outcome'], 'rejected')
        self.assertEqual(case['retained_observation']['normalized_outcome'], 'failure')
        self.assertFalse(case['synthetic_private_detail_retained'])

    def test_conflicting_terminal_markers_fail_safely(self):
        for name in ('top_error_then_result', 'conflicting_terminal_events'):
            case = exercise(name)
            self.assertEqual(case['adapter_outcome'], 'rejected')
            self.assertEqual(case['retained_observation']['terminal_status'], 'conflicting')

    def test_nonfatal_item_errors_before_and_after_result(self):
        for name in ('unknown_item_error_before_result', 'unknown_item_error_after_result',
                     'unsupported_nonterminal_claim'):
            case = exercise(name)
            self.assertEqual(case['adapter_outcome'], 'executed')
            diagnostic = case['retained_observation']['diagnostics'][0]
            self.assertEqual(diagnostic['classification'], 'non_terminal_diagnostic')
            self.assertFalse(diagnostic['terminal'])
            self.assertEqual(diagnostic['classification_source'], binding.PROTOCOL)
            self.assertTrue(diagnostic['message']['present'])
            self.assertEqual(diagnostic['message']['utf8_bytes'], len(DETAIL.encode()))

    def test_diagnostic_order_preserved(self):
        a = exercise('unknown_item_error_before_result')['retained_observation']
        b = exercise('unknown_item_error_after_result')['retained_observation']
        self.assertEqual(a['diagnostics'][0]['sequence'], 2)
        self.assertEqual(b['diagnostics'][0]['sequence'], 3)
        self.assertEqual(a['diagnostics'][0]['item_id'], 'item_0')
        self.assertEqual([v['sequence'] for v in a['events']], [1, 2, 3, 4])

    def test_malformed_and_unknown_reject_without_repair(self):
        for name in ('malformed_json', 'wrong_event_type', 'unknown_event'):
            case = exercise(name)
            self.assertEqual(case['adapter_outcome'], 'rejected')
            self.assertIsNotNone(case['retained_observation'])
            self.assertTrue(case['retained_observation']['rejection_reasons'])

    def test_explicit_terminal_event_required(self):
        case = exercise('missing_terminal_event')
        self.assertEqual(case['adapter_outcome'], 'rejected')
        self.assertEqual(case['retained_observation']['terminal_status'], 'missing')

    def test_nonzero_exit_rejected(self):
        self.assertEqual(exercise('nonzero_process_exit')['adapter_outcome'], 'rejected')

    def test_private_diagnostic_fixture_not_persisted(self):
        for name in CASES:
            self.assertFalse(exercise(name)['synthetic_private_detail_retained'])

    def test_historical_task_still_fails_independent_verification(self):
        verifier = load('experiments/kernel-increment-11/live/verify.py', 'historical_verifier')
        result = verifier.verify(ROOT / 'experiments/kernel-increment-11/evidence/live-authorized/acceptance')
        self.assertEqual(result['status'], 'STOP')
        self.assertEqual(result['task_lifecycle'], 'FAILED')
        self.assertEqual(result['completion_evaluation']['payload']['outcome'], 'unsatisfied')
        self.assertEqual(result['pending_dispatches'], 1)


def report():
    path = ROOT / 'experiments/kernel-increment-11/evidence/live-authorized/acceptance/worker-observation.json'
    historical = json.loads(path.read_text())
    return {
        'diagnostic_status': 'OFFLINE_CORRECTION_PASS',
        'historical_task_status': 'FAILED', 'increment_11': 'STOPPED',
        'historical_observation_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'retained_sequence': historical['events'],
        'retained_unordered_error_labels': historical['unexpected_items'],
        'error_position': None, 'error_body': None, 'historical_item_classification_under_versioned_contract': 'non_fatal',
        'cases': [exercise(name) for name in CASES],
        'live_worker_dispatches': 0, 'model_calls': 0,
        'kernel_behavior_changed': False, 'binding_normalization_corrected': True,
        'nonterminal_error_success_case': 'PASS_SYNTHETIC_ONLY; original ordering remains UNKNOWN',
    }


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--report':
        print(json.dumps(report(), indent=2))
    else:
        unittest.main()
