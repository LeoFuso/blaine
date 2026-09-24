"""Codex app-server boundary observation, using neutral synthetic streams only.

No Codex process is started here and no inference occurs. The live protocol
evidence lives in the experiment's retained observations.
"""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    'codex_appserver_tests', ROOT / 'experiments/worker-execution-instrumentation/codex_appserver.py')
codex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(codex)

from runtime.kernel.instrument import (  # noqa: E402
    ADMIT_CONTINUATION, INTERRUPT_EXECUTION, OBSERVE_CONTINUATION, OBSERVE_MODEL,
    OBSERVE_TOOL, REBIND_EFFORT, REBIND_MODEL, STEER_CONTINUATION, UnsupportedCapability,
)

THREAD = 'thread-fixture-1'
TURN = 'turn-fixture-1'


def inbound(method, params, at):
    return {'jsonrpc': '2.0', 'method': method, 'params': params, '_t_ms': at, '_dir': 'in'}


def outbound(identity, method, params, at):
    return {'jsonrpc': '2.0', 'id': identity, 'method': method, 'params': params, '_t_ms': at, '_dir': 'out'}


def response(identity, result, at):
    return {'jsonrpc': '2.0', 'id': identity, 'result': result, '_t_ms': at, '_dir': 'in'}


def usage(last, at, turn=TURN):
    return inbound(codex.BOUNDARY_MARKER, {'threadId': THREAD, 'turnId': turn,
        'tokenUsage': {'last': last, 'total': last}}, at)


def tool_pair(item_id, at, *, status='completed', exit_code=0, duration=7, command=None):
    item = {'type': 'commandExecution', 'id': item_id, 'command': command or ['fixture-command'],
            'status': 'inProgress'}
    done = {**item, 'status': status, 'exitCode': exit_code, 'durationMs': duration}
    return [inbound('item/started', {'threadId': THREAD, 'turnId': TURN, 'item': item, 'startedAtMs': 0}, at),
            inbound('item/completed', {'threadId': THREAD, 'turnId': TURN, 'item': done,
                                       'completedAtMs': 0}, at + duration)]


def stream_two_tools():
    return [inbound('thread/started', {'thread': {'id': THREAD}}, 1),
            inbound('turn/started', {'threadId': THREAD, 'turn': {'id': TURN, 'items': [],
                                                                  'status': 'inProgress'}}, 2),
            *tool_pair('call-one', 10),
            usage({'inputTokens': 100, 'outputTokens': 20, 'cachedInputTokens': 0,
                   'cacheWriteInputTokens': 90, 'reasoningOutputTokens': 5}, 20),
            *tool_pair('call-two', 30),
            usage({'inputTokens': 120, 'outputTokens': 15, 'cachedInputTokens': 90,
                   'cacheWriteInputTokens': 0, 'reasoningOutputTokens': 3}, 40),
            inbound('item/started', {'threadId': THREAD, 'turnId': TURN,
                                     'item': {'type': 'agentMessage', 'id': 'm1', 'text': 'fixture'},
                                     'startedAtMs': 0}, 45),
            inbound('item/completed', {'threadId': THREAD, 'turnId': TURN,
                                       'item': {'type': 'agentMessage', 'id': 'm1', 'text': 'fixture'},
                                       'completedAtMs': 0}, 48),
            usage({'inputTokens': 130, 'outputTokens': 8, 'cachedInputTokens': 90,
                   'cacheWriteInputTokens': 0, 'reasoningOutputTokens': 2}, 50),
            inbound('turn/completed', {'threadId': THREAD, 'turn': {'id': TURN, 'items': [],
                                                                    'status': 'completed'}}, 51)]


class BoundaryObservationTests(unittest.TestCase):
    def test_one_boundary_per_model_invocation_with_its_own_usage(self):
        observed = codex.observe(stream_two_tools()).summary()
        self.assertEqual(len(observed['boundaries']), 3)
        self.assertEqual(len(observed['model_invocations']), 3)
        self.assertEqual([m['input_tokens'] for m in observed['model_invocations']], [100, 120, 130])
        self.assertEqual([m['cached_input_tokens'] for m in observed['model_invocations']], [0, 90, 90])
        self.assertEqual([m['reasoning_output_tokens'] for m in observed['model_invocations']], [5, 3, 2])
        self.assertEqual([b['marker'] for b in observed['boundaries']], [codex.BOUNDARY_MARKER] * 3)
        self.assertEqual(observed['turn_status'], 'completed')
        self.assertEqual(observed['thread_id'], THREAD)

    def test_tool_calls_are_attributed_to_the_continuation_that_requested_them(self):
        observed = codex.observe(stream_two_tools()).summary()
        self.assertEqual([b['tools_in_previous_continuation'] for b in observed['boundaries']],
                         [['call-one'], ['call-two'], []])
        self.assertEqual([b['reason'] for b in observed['boundaries']],
                         ['tool_results', 'tool_results', 'model_result'])
        tools = observed['tool_invocations']
        self.assertEqual([t['boundary_index'] for t in tools], [0, 1])
        self.assertEqual([(t['status'], t['exit_code'], t['duration_ms']) for t in tools],
                         [('completed', 0, 7), ('completed', 0, 7)])

    def test_no_synchronous_admission_is_claimed_at_the_boundary(self):
        observed = codex.observe(stream_two_tools()).summary()
        self.assertTrue(all(b['synchronous_admission'] is False for b in observed['boundaries']))
        self.assertFalse(codex.CAPABILITIES.supports(ADMIT_CONTINUATION))

    def test_partial_usage_metadata_stays_absent_rather_than_zero(self):
        observed = codex.observe([usage({'inputTokens': 5}, 1)]).summary()
        invocation = observed['model_invocations'][0]
        self.assertEqual(invocation['input_tokens'], 5)
        self.assertIsNone(invocation['output_tokens'])
        self.assertIsNone(invocation['cached_input_tokens'])


class ControlObservationTests(unittest.TestCase):
    def test_steering_is_correlated_with_the_continuation_that_consumes_it(self):
        records = [inbound('thread/started', {'thread': {'id': THREAD}}, 1),
                   inbound('turn/started', {'threadId': THREAD, 'turn': {'id': TURN, 'items': [],
                                                                         'status': 'inProgress'}}, 2),
                   # The steer is issued while the tool item is still open.
                   tool_pair('call-slow', 10, duration=100)[0],
                   outbound(9, 'turn/steer', {'threadId': THREAD, 'expectedTurnId': TURN,
                                              'input': [{'type': 'text', 'text': 'fixture addendum'}]}, 30),
                   response(9, {'turnId': TURN}, 31),
                   tool_pair('call-slow', 10, duration=100)[1],
                   usage({'inputTokens': 10, 'outputTokens': 2}, 111),
                   inbound('item/started', {'threadId': THREAD, 'turnId': TURN,
                       'item': {'type': 'userMessage', 'id': 'u1', 'content': []}, 'startedAtMs': 0}, 112),
                   inbound('item/completed', {'threadId': THREAD, 'turnId': TURN,
                       'item': {'type': 'userMessage', 'id': 'u1', 'content': []}, 'completedAtMs': 0}, 112),
                   usage({'inputTokens': 20, 'outputTokens': 4}, 200)]
        steering = codex.observe(records).summary()['steering']
        self.assertEqual(len(steering), 1)
        entry = steering[0]
        self.assertEqual(entry['phase'], 'consumed')
        self.assertTrue(entry['tool_active_at_request'])
        self.assertEqual(entry['boundary_index_at_request'], 0)
        # Accepted immediately, consumed only after the next boundary marker.
        self.assertLess(entry['accepted_at_ms'], 100)
        self.assertEqual(entry['consumed_at_boundary_index'], 1)
        self.assertGreater(entry['consumed_at_ms'], 111)
        self.assertTrue(codex.CAPABILITIES.supports(STEER_CONTINUATION))

    def test_interrupt_leaves_an_unterminated_tool_item_without_a_fabricated_outcome(self):
        records = [inbound('thread/started', {'thread': {'id': THREAD}}, 1),
                   inbound('turn/started', {'threadId': THREAD, 'turn': {'id': TURN, 'items': [],
                                                                         'status': 'inProgress'}}, 2),
                   inbound('item/started', {'threadId': THREAD, 'turnId': TURN,
                       'item': {'type': 'commandExecution', 'id': 'call-killed',
                                'command': ['fixture-command'], 'status': 'inProgress'},
                       'startedAtMs': 0}, 10),
                   outbound(9, 'turn/interrupt', {'threadId': THREAD, 'turnId': TURN}, 20),
                   response(9, {}, 21),
                   usage({'inputTokens': 9, 'outputTokens': 1}, 22),
                   inbound('turn/completed', {'threadId': THREAD, 'turn': {'id': TURN, 'items': [],
                                                                           'status': 'interrupted'}}, 23)]
        observed = codex.observe(records).summary()
        self.assertEqual(observed['turn_status'], 'interrupted')
        self.assertEqual(observed['tool_invocations'], [])
        self.assertEqual(len(observed['unterminated_tool_items']), 1)
        self.assertEqual(observed['unterminated_tool_items'][0]['status'], 'unterminated')
        self.assertNotIn('exit_code', observed['unterminated_tool_items'][0])
        self.assertEqual(observed['approvals'][0]['control'], 'turn/interrupt')
        self.assertFalse(observed['approvals'][0]['blocking'])
        self.assertTrue(codex.CAPABILITIES.supports(INTERRUPT_EXECUTION, 'agent_turn'))

    def test_approval_callback_is_recorded_as_a_pre_tool_blocking_point(self):
        records = [{'jsonrpc': '2.0', 'id': 0, 'method': 'item/commandExecution/requestApproval',
                    'params': {'threadId': THREAD}, '_t_ms': 5, '_dir': 'in'},
                   *tool_pair('call-one', 10),
                   usage({'inputTokens': 3, 'outputTokens': 1}, 30)]
        approvals = codex.observe(records).summary()['approvals']
        self.assertEqual(len(approvals), 1)
        self.assertTrue(approvals[0]['blocking'])
        self.assertEqual(approvals[0]['boundary_relation'], 'pre_tool_execution')
        # A blocking tool-admission callback is not a continuation admission.
        self.assertFalse(codex.CAPABILITIES.supports(ADMIT_CONTINUATION))


class SafetyAndHonestyTests(unittest.TestCase):
    def test_unknown_notifications_are_counted_without_copying_their_discriminator(self):
        records = [inbound('some/unreleased/notification', {'secretish': 'FIXTURE_UNKNOWN_MARKER'}, 1),
                   usage({'inputTokens': 1, 'outputTokens': 1}, 2)]
        observed = codex.observe(records).summary()
        self.assertEqual(observed['unknown_events'], 1)
        self.assertNotIn('FIXTURE_UNKNOWN_MARKER', repr(observed))
        self.assertNotIn('some/unreleased/notification', repr(observed))
        self.assertEqual(len(observed['boundaries']), 1)

    def test_malformed_records_are_counted_instead_of_raising(self):
        records = ['not an object', {'method': 17, '_dir': 'in'},
                   inbound('item/completed', {'item': 'not an object'}, 3),
                   inbound(codex.BOUNDARY_MARKER, 'not an object', 4)]
        observed = codex.observe(records).summary()
        self.assertEqual(observed['malformed_events'], 4)
        self.assertEqual(observed['boundaries'], [])
        self.assertEqual(codex.observe('not a list').summary()['malformed_events'], 1)
        self.assertEqual(codex.observe([{}] * 5000).summary()['malformed_events'], 1)

    def test_tool_request_content_is_a_digest_unless_capture_is_enabled(self):
        records = tool_pair('call-one', 10, command=['fixture-command', 'CONTENT_MARKER_DO_NOT_EMIT'])
        default = codex.observe(records).summary()
        self.assertNotIn('CONTENT_MARKER_DO_NOT_EMIT', repr(default))
        self.assertEqual(len(default['tool_invocations'][0]['request_digest']), 64)
        self.assertNotIn('command', default['tool_invocations'][0])
        captured = codex.observe(records, capture_content=True).summary()
        self.assertIn('CONTENT_MARKER_DO_NOT_EMIT', repr(captured['tool_invocations'][0]['command']))

    def test_model_text_and_reasoning_never_enter_the_observation(self):
        records = [inbound('item/completed', {'threadId': THREAD, 'turnId': TURN, 'completedAtMs': 0,
                       'item': {'type': 'reasoning', 'id': 'r1', 'content': 'PRIVATE_REASONING_MARKER'}}, 1),
                   inbound('item/completed', {'threadId': THREAD, 'turnId': TURN, 'completedAtMs': 0,
                       'item': {'type': 'agentMessage', 'id': 'm1', 'text': 'ANSWER_TEXT_MARKER'}}, 2),
                   usage({'inputTokens': 1, 'outputTokens': 1}, 3)]
        observed = repr(codex.observe(records).summary())
        self.assertNotIn('PRIVATE_REASONING_MARKER', observed)
        self.assertNotIn('ANSWER_TEXT_MARKER', observed)

    def test_rebinding_is_declared_only_at_the_granularity_the_protocol_provides(self):
        for capability in (REBIND_MODEL, REBIND_EFFORT):
            with self.subTest(capability=capability):
                self.assertTrue(codex.CAPABILITIES.supports(capability, 'agent_turn'))
                self.assertFalse(codex.CAPABILITIES.supports(capability, 'continuation'))
        self.assertTrue(codex.CAPABILITIES.supports(OBSERVE_CONTINUATION))
        self.assertTrue(codex.CAPABILITIES.supports(OBSERVE_MODEL))
        self.assertTrue(codex.CAPABILITIES.supports(OBSERVE_TOOL))
        with self.assertRaises(UnsupportedCapability):
            codex.CAPABILITIES.require(ADMIT_CONTINUATION)

    def test_declared_evidence_class_matches_what_was_actually_executed(self):
        summary = codex.CAPABILITIES.summary()['capabilities']
        for capability in (OBSERVE_CONTINUATION, OBSERVE_MODEL, OBSERVE_TOOL, STEER_CONTINUATION,
                           INTERRUPT_EXECUTION):
            self.assertEqual(summary[capability]['evidence'], 'live')
        for capability in (REBIND_MODEL, REBIND_EFFORT):
            self.assertEqual(summary[capability]['evidence'], 'protocol')
        self.assertEqual(summary[ADMIT_CONTINUATION]['evidence'], 'none')


if __name__ == '__main__':
    unittest.main()
