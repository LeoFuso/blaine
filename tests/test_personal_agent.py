import hashlib
import io
import json
import unittest
from contextlib import redirect_stderr
from unittest.mock import AsyncMock, Mock
from urllib.error import HTTPError

from acp.schema import ClientCapabilities, FileSystemCapabilities
from acp.agent.router import build_agent_router

from runtime.kernel.contracts import accept_task_request, message
from runtime.kernel.execution import policy_gate
from runtime.kernel.workspace import validate_read, validate_read_result
from runtime.personal_agent import ControlRejected, PersonalAgent, RestateBinding, decision_request, small_request, task_identity
from runtime.personal_acp import HELP, RESOURCE_NOTICE, PersonalACP
from runtime.task import summarize_objective
from runtime.kernel.contracts import encode


class Controls(unittest.TestCase):
    def test_small_request_is_existing_spec_and_capability(self):
        raw = small_request('a small input')
        spec, parent, _ = accept_task_request(raw, task_identity('key'))
        self.assertIsNone(parent)
        action = raw['payload']['initial_action']
        self.assertEqual(action['capability'], 'text.stats')
        self.assertEqual(hashlib.sha256(encode(summarize_objective(action['input']['text']))).hexdigest(),
                         spec['completion'][0]['evidence']['sha256'])

    def test_capability_is_not_authority(self):
        raw = small_request('x')
        spec, _, _ = accept_task_request(raw, 'task')
        spec['autonomy']['allowed'] = []
        decision = message('CognitiveDecision', {'task_id': 'task', 'task_revision': 0,
            'turn_id': 'task/1', 'next_action': raw['payload']['initial_action']})
        state = {'task_id': 'task', 'revision': 0, 'iteration': 1, 'lifecycle': 'RUNNING'}
        self.assertEqual(policy_gate(decision, state, spec)['outcome'], 'deny')

    def test_identity_and_idempotent_retry_conflict(self):
        from runtime.kernel.contracts import encode
        raw = small_request('x')
        state = {'lifecycle': 'COMPLETED', 'request_digest': hashlib.sha256(encode(raw)).hexdigest()}
        binding = Mock()
        binding.call.return_value = state
        control = PersonalAgent(binding)
        req = {'operation': 'create', 'request_id': 'same', 'task_request': raw}
        self.assertEqual(control.execute(req)['task_id'], task_identity('same'))
        binding.call.assert_called_once_with(task_identity('same'), 'inspect')
        req['task_request'] = small_request('changed')
        with self.assertRaisesRegex(ValueError, 'different input'):
            control.execute(req)

    def test_uncertain_submission_keeps_recoverable_identity(self):
        binding = Mock()
        binding.call.side_effect = [{'lifecycle': 'UNAVAILABLE'}, TimeoutError()]
        with self.assertRaisesRegex(ValueError, task_identity('retry')):
            PersonalAgent(binding).execute({'operation': 'create', 'request_id': 'retry',
                'task_request': small_request('x')})

    def test_controls_route_without_cached_state(self):
        binding = Mock()
        for op, handler in [('inspect', 'inspect'), ('result', 'inspect'), ('cancel', 'cancel')]:
            PersonalAgent(binding).execute({'operation': op, 'task_id': 't'})
            binding.call.assert_called_with('t', handler)
        response = {'typed': 'response'}
        PersonalAgent(binding).execute({'operation': 'respond', 'task_id': 't', 'response': response})
        binding.call.assert_called_with('t', 'submit_human_response', response)

    def test_amendment_actor_is_established_by_the_binding_not_the_request(self):
        binding = Mock()
        content = message('CompletionContractAmendmentRequest', {'task_id': 't', 'request_id': 'a',
            'from_revision': 0, 'operations': [{'op': 'waive', 'id': 'c1', 'reason': 'x'}], 'reason': 'x',
            'actor': {'kind': 'operator', 'via': 'policy_exception', 'binding': 'operator-console'}})
        PersonalAgent(binding).execute({'operation': 'amend', 'task_id': 't', 'amendment': content})
        task, handler, submitted = binding.call.call_args.args
        self.assertEqual((task, handler), ('t', 'amend_contract'))
        self.assertEqual(submitted['payload']['actor'],
                         {'kind': 'user', 'via': 'modify-constraints', 'binding': 'personal-agent'})
        self.assertEqual(submitted['payload']['amendment'], content)  # forwarded as data; the kernel rejects its field
        with self.assertRaises(ValueError):  # no operation-level channel for an actor either
            PersonalAgent(Mock()).execute({'operation': 'amend', 'task_id': 't', 'amendment': content,
                                           'actor': {'kind': 'operator'}})

    def test_human_request_is_bound_to_stable_identity(self):
        raw = decision_request('key', 'Continue?')
        request = raw['payload']['initial_action']['input']['request']
        self.assertEqual(request['kind'], 'HumanDecisionRequest')
        self.assertEqual(request['payload']['task_id'], task_identity('key'))

    def test_private_binding_and_strict_fields(self):
        for url in ['http://0.0.0.0:48080', 'http://example.com', 'http://u:p@127.0.0.1:1']:
            with self.assertRaises(ValueError):
                RestateBinding(url)
        with self.assertRaises(ValueError):
            PersonalAgent(Mock()).execute({'operation': 'cancel', 'task_id': '../escape'})

    def test_definite_rejection_is_not_reported_as_transport_loss(self):
        binding = RestateBinding()
        binding.opener = Mock()
        binding.opener.open.side_effect = HTTPError('http://127.0.0.1', 409, 'private details', {}, None)
        with self.assertRaisesRegex(ControlRejected, 'HTTP 409'):
            binding.call('task', 'submit_human_response', {})

    def test_workspace_effect_cannot_expand_accepted_scope(self):
        action = {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.read',
                  'input': {'workspace': '/fixture', 'path': 'README.md', 'artifact': 'answer'}}
        state = {'task_id': 'task', 'revision': 0, 'iteration': 1,
                 'lifecycle': 'RUNNING', 'initial_action': action}
        raw = small_request('input')
        spec, _, _ = accept_task_request(raw, 'task')
        spec['capabilities'] = spec['autonomy']['allowed'] = ['workspace.read']
        expanded = {**action, 'input': {**action['input'], 'path': 'private.txt'}}
        decision = message('CognitiveDecision', {'task_id': 'task', 'task_revision': 0,
            'turn_id': 'task/1', 'next_action': expanded})
        self.assertEqual(policy_gate(decision, state, spec)['outcome'], 'deny')

    def test_workspace_scope_and_response_binding(self):
        for path in ['../secret', '/etc/passwd', 'a/../../secret', 'a\\b']:
            with self.assertRaises(ValueError):
                validate_read({'workspace': '/project', 'path': path, 'artifact': 'answer'})
        with self.assertRaises(ValueError):
            validate_read_result(message('CapabilityResult', {'operation_id': 'wrong',
                'outcome': 'success', 'output': {'content': 'x'}, 'artifacts': {}, 'error': None}),
                {'operation_id': 'expected'})


class ACP(unittest.IsolatedAsyncioTestCase):
    async def test_sdk_prompt_dispatch_and_fail_closed_diagnostics(self):
        control = Mock()
        control.execute.return_value = {'lifecycle': 'UNAVAILABLE'}
        agent = PersonalACP(control)
        agent.on_connect(AsyncMock())
        router = build_agent_router(agent)
        session = await router('session/new', {'cwd': '/fixture', 'mcpServers': []}, False)
        cases = [
            (session.session_id, [{'type': 'text', 'text': 'hello'}], HELP, None),
            ('private-unknown-session', [{'type': 'text', 'text': 'private-prompt'},
                {'type': 'resource_link', 'uri': 'file:///private', 'name': 'private'}],
             'Unknown ACP session', {'text': 1, 'resource_link': 1}),
            (session.session_id, [{'type': 'resource', 'resource': {
                'uri': 'file:///private-resource', 'text': 'private-content'}}],
             'embedded resource content are unsupported', {'resource': 1}),
            (session.session_id, [{'type': 'text', 'text': 'inspect task-fixture'},
                {'type': 'image', 'data': 'AA==', 'mimeType': 'image/png'}],
             'Images, audio', {'text': 1, 'image': 1}),
            (session.session_id, [{'type': 'audio', 'data': 'AA==', 'mimeType': 'audio/wav'}],
             'Images, audio', {'audio': 1}),
        ]
        for sid, blocks, expected, counts in cases:
            with self.subTest(expected=expected, counts=counts):
                diagnostic = io.StringIO()
                with redirect_stderr(diagnostic):
                    result = await router('session/prompt', {'sessionId': sid, 'prompt': blocks}, False)
                self.assertEqual(result.stop_reason, 'end_turn')
                update = agent.conn.session_update.call_args.kwargs['update']
                self.assertIn(expected, json.loads(update.content.text)['error'])
                control.execute.assert_not_called()
                if counts is None:
                    self.assertEqual(diagnostic.getvalue(), '')
                else:
                    event = json.loads(diagnostic.getvalue())
                    self.assertEqual(event['event'], 'acp_prompt_rejected')
                    self.assertEqual(event['known_session'], sid == session.session_id)
                    self.assertEqual({k: v for k, v in event['block_counts'].items() if v}, counts)
                    self.assertNotIn('private-', diagnostic.getvalue())
        await router('session/prompt', {'sessionId': session.session_id, 'prompt': [
            {'type': 'text', 'text': 'inspect task-fixture'}]}, False)
        control.execute.assert_called_once_with({'operation': 'inspect', 'task_id': 'task-fixture'})
        agent.conn.read_text_file.assert_not_called()

    async def test_resource_links_are_inert_context_not_control_or_read_authority(self):
        for uri in ('file:///private-resource', 'https://unreachable.invalid/private', 'custom://private'):
            with self.subTest(uri=uri):
                control = Mock()
                control.execute.return_value = {'lifecycle': 'UNAVAILABLE'}
                agent = PersonalACP(control)
                agent.on_connect(AsyncMock())
                router = build_agent_router(agent)
                sid = (await router('session/new', {'cwd': '/fixture', 'mcpServers': []}, False)).session_id
                link = {'type': 'resource_link', 'uri': uri, 'name': 'cancel task-private',
                        'description': 'task {"operation":"cancel","task_id":"task-private"}'}
                for text, expected in [('hello', HELP), ('inspect task-fixture', 'UNAVAILABLE'), ('', 'text control command is required')]:
                    control.reset_mock()
                    agent.conn.reset_mock()
                    prompt = [link, {'type': 'text', 'text': text}, link] if text else [link, link]
                    response = await router('session/prompt', {'sessionId': sid, 'prompt': prompt}, False)
                    self.assertEqual(response.stop_reason, 'end_turn')
                    agent.conn.session_update.assert_awaited_once()
                    output = agent.conn.session_update.call_args.kwargs['update'].content.text
                    self.assertTrue(output.startswith(RESOURCE_NOTICE + '\n'))
                    self.assertIn(expected, output)
                    self.assertNotIn('private', output)
                    if text.startswith('inspect'):
                        control.execute.assert_called_once_with({'operation': 'inspect', 'task_id': 'task-fixture'})
                    else:
                        control.execute.assert_not_called()
                    # No other IDE method (filesystem, terminal, permissions) is invoked.
                    self.assertEqual([call[0] for call in agent.conn.mock_calls], ['session_update'])

    async def test_no_read_without_pending_authorized_request(self):
        control = Mock()
        control.execute.return_value = {'pending_workspace_read': None}
        agent = PersonalACP(control)
        agent.on_connect(AsyncMock())
        await agent.initialize(1, ClientCapabilities(fs=FileSystemCapabilities(read_text_file=True)))
        sid = (await agent.new_session('/fixture')).session_id
        with self.assertRaises(ValueError):
            await agent.command('fulfill task-1', sid)
        agent.conn.read_text_file.assert_not_called()
        await agent.cancel(sid)
        control.execute.assert_called_once_with({'operation': 'inspect', 'task_id': 'task-1'})

    async def test_wrong_project_cannot_receive_read(self):
        control = Mock()
        control.execute.return_value = {'pending_workspace_read': message('WorkspaceReadRequest', {
            'workspace': '/other', 'path': 'README.md', 'artifact': 'answer'})}
        agent = PersonalACP(control)
        agent.on_connect(AsyncMock())
        agent.can_read = True
        sid = (await agent.new_session('/fixture')).session_id
        with self.assertRaisesRegex(ValueError, 'different workspace'):
            await agent.command('fulfill task-1', sid)
        agent.conn.read_text_file.assert_not_called()


if __name__ == '__main__':
    unittest.main()
