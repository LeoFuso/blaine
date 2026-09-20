"""Offline characterization of the existing adapter, NOT a worker-success gate.

Every stream below is synthetic. Popen and the command builder are replaced;
no CLI, provider, credential file or historical dispatch receipt is used.
Passing controls means the recorded behavior is reproducible, including defects.
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
START = {'type': 'thread.started', 'thread_id': 'synthetic-session'}
MESSAGE = {'type': 'item.completed', 'item': {
    'type': 'agent_message', 'text': '{"organization":"FLOWER","marker":"MASKED_01"}'}}
COMPLETED = {'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 5}}
DETAIL = 'SYNTHETIC_PRIVATE_DETAIL_DO_NOT_PERSIST'
ITEM_ERROR = {'type': 'item.completed', 'item': {'type': 'error', 'message': DETAIL}}
FAILED = {'type': 'turn.failed', 'error': {'message': DETAIL}}
TOP_ERROR = {'type': 'error', 'message': DETAIL}

# These are parser inputs, not assertions about what the upstream protocol permits.
# In particular terminal:false is an unsupported synthetic claim, not protocol evidence.
CASES = {
    'clean_completed_shape': [START, MESSAGE, COMPLETED],
    'failed_shape_without_result': [START, FAILED],
    'result_then_failed_shape': [START, MESSAGE, FAILED],
    'top_error_then_result': [START, TOP_ERROR, MESSAGE, COMPLETED],
    'unknown_item_error_before_result': [START, ITEM_ERROR, MESSAGE, COMPLETED],
    'unknown_item_error_after_result': [START, MESSAGE, ITEM_ERROR, COMPLETED],
    'unsupported_nonterminal_claim': [START, {'type': 'item.completed', 'item': {
        'type': 'error', 'message': DETAIL, 'terminal': False}}, MESSAGE, COMPLETED],
    'malformed_json': [START, 'not-json', MESSAGE, COMPLETED],
    'wrong_event_type': [START, [], MESSAGE, COMPLETED],
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
            'upstream_semantics': 'UNKNOWN; fixture does not establish protocol terminality',
            'input_order': [v.get('type', 'unknown') if isinstance(v, dict) else 'malformed' for v in values],
            'adapter_outcome': outcome, 'exception_class': error,
            'normalized_result_written': (out / 'worker-normalized-result.json').exists(),
            'retained_observation': observation, 'synthetic_private_detail_retained': detail_retained,
            'mocked_process_constructions': popen.call_count, 'live_worker_dispatches': 0,
        }


class CharacterizationTests(unittest.TestCase):
    """Expected current behavior, not approval of the existing acceptance policy."""

    def test_clean_shape(self):
        self.assertEqual(exercise('clean_completed_shape')['adapter_outcome'], 'executed')

    def test_failure_without_result(self):
        self.assertEqual(exercise('failed_shape_without_result')['adapter_outcome'], 'rejected')

    def test_result_plus_failed_shape_exposes_admission_gap(self):
        self.assertEqual(exercise('result_then_failed_shape')['adapter_outcome'], 'executed')

    def test_top_error_not_in_rejection_predicate(self):
        case = exercise('top_error_then_result')
        self.assertEqual(case['adapter_outcome'], 'executed')
        self.assertEqual(case['retained_observation']['events'][1]['type'], 'error')
        self.assertFalse(case['synthetic_private_detail_retained'])

    def test_unknown_error_remains_rejected_even_with_nonterminal_claim(self):
        for name in ('unknown_item_error_before_result', 'unsupported_nonterminal_claim'):
            case = exercise(name)
            self.assertEqual(case['adapter_outcome'], 'rejected')
            self.assertEqual(case['retained_observation']['unexpected_items'], ['unrequested_item:error'])

    def test_error_order_lost_but_public_order_kept(self):
        a = exercise('unknown_item_error_before_result')['retained_observation']
        b = exercise('unknown_item_error_after_result')['retained_observation']
        self.assertEqual(a['events'], b['events'])
        self.assertEqual(a['unexpected_items'], b['unexpected_items'])
        self.assertEqual([v['type'] for v in a['events']], ['thread.started', 'item.completed', 'turn.completed'])

    def test_malformed_rejects_without_repair(self):
        case = exercise('malformed_json')
        self.assertEqual(case['adapter_outcome'], 'rejected')
        self.assertIn('non_json_cli_output', case['retained_observation']['unexpected_items'])

    def test_non_object_event_loses_observation(self):
        case = exercise('wrong_event_type')
        self.assertEqual(case['exception_class'], 'AttributeError')
        self.assertIsNone(case['retained_observation'])

    def test_terminal_event_not_required_by_current_adapter(self):
        self.assertEqual(exercise('missing_terminal_event')['adapter_outcome'], 'executed')

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
        'diagnostic_status': 'STOP_PROTOCOL_SEMANTICS_UNVERIFIED',
        'historical_task_status': 'FAILED', 'increment_11': 'STOPPED',
        'historical_observation_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'retained_sequence': historical['events'],
        'retained_unordered_error_labels': historical['unexpected_items'],
        'error_position': None, 'error_body': None, 'error_terminality': None,
        'cases': [exercise(name) for name in CASES],
        'live_worker_dispatches': 0, 'model_calls': 0,
        'production_or_binding_behavior_changed': False,
        'nonterminal_error_success_case': 'NOT ESTABLISHED: no local versioned exec protocol semantics found',
    }


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--report':
        print(json.dumps(report(), indent=2))
    else:
        unittest.main()
