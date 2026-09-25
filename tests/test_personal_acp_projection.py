"""personal_acp renders the same conversation projection as the desktop."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from acp.schema import AllowedOutcome, RequestPermissionResponse, TextContentBlock

from runtime.kernel.conversation import ConversationService
from runtime.personal_acp import PersonalACP
from runtime.personal_brief import BriefService, CodingPolicy
from runtime.personal_conversation import PersonalConversation
from runtime.personal_projection import ConversationProjection

from test_personal_pa3 import BRIEF, FakeAgent, ScriptedModel, deployment


class RespondingAgent(FakeAgent):
    def __init__(self):
        super().__init__()
        self.responses = []

    def execute(self, request):
        if request['operation'] == 'respond':
            self.responses.append(request)
            self.views[request['task_id']] = {'task_id': request['task_id'], 'lifecycle': 'RUNNING', 'effects': []}
            return {'kind': 'InputReceipt'}
        return super().execute(request)


class Services:
    def __init__(self, base, agent, replies):
        self.store = ConversationService(base / 'data')
        self.agent = agent
        model = ScriptedModel(replies)
        self.conversation = PersonalConversation(self.store, model, agent)
        self.briefs = BriefService(self.store, model, agent, CodingPolicy(deployment(base / 'repo')))
        self.projection = ConversationProjection(self.store, agent)


class ACPConversation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        os.environ['BLAINE_CONVERSATION_KEY_DIR'] = tmp.name + '/keys'
        self.addCleanup(os.environ.pop, 'BLAINE_CONVERSATION_KEY_DIR', None)
        self.agent = RespondingAgent()
        self.services = Services(Path(tmp.name), self.agent, ['Agreed — use /execute when ready.', BRIEF])
        self.acp = PersonalACP(self.agent, self.services)
        self.acp.on_connect(AsyncMock())
        self.acp.conn.request_permission.return_value = RequestPermissionResponse(
            outcome=AllowedOutcome(outcome='selected', option_id='APPROVE'))
        self.sid = (await self.acp.new_session('/fixture')).session_id
        self.conversation = self.acp.views[self.sid]['conversation']

    async def say(self, text):
        self.acp.conn.session_update.reset_mock()
        response = await self.acp.prompt(self.sid, [TextContentBlock(type='text', text=text)])
        self.assertEqual(response.stop_reason, 'end_turn')
        return [call.kwargs['update'] for call in self.acp.conn.session_update.call_args_list]

    async def test_plain_text_is_a_conversation_turn_rendered_from_the_projection(self):
        updates = await self.say('Please add bounded tests')
        texts = [u.content.text for u in updates if u.session_update == 'agent_message_chunk']
        self.assertEqual(texts, ['Agreed — use /execute when ready.'])  # own prompt not echoed
        self.assertEqual(self.agent.created, {})  # a conversation turn creates no Task

    async def test_execute_brief_task_and_human_request_follow_the_same_semantics_as_the_desktop(self):
        await self.say('Please add bounded tests')
        updates = await self.say('/execute')
        self.assertIn('Execution Brief proposed', updates[-1].content.text)
        updates = await self.say('/execute confirm')
        [task_id] = self.agent.created
        start = next(u for u in updates if u.session_update == 'tool_call')
        self.assertEqual((start.tool_call_id, start.status, start.kind), (task_id, 'in_progress', 'execute'))
        self.assertTrue(any(u.session_update == 'plan' for u in updates))
        # The Task now waits on an approval: ACP asks through a native permission request.
        self.agent.views[task_id] = {'task_id': task_id, 'lifecycle': 'WAITING', 'effects': [
            {'operation_id': f'{task_id}/4', 'operation_class': 'workspace.write', 'status': 'awaiting_approval',
             'path': 'tests/test_human_response_bounds.py'}],
            'pending_human_decision': {'version': 1, 'kind': 'HumanDecisionRequest', 'payload': {
                'task_id': task_id, 'origin_task_id': task_id, 'request_id': 'approve-4', 'revision': 0,
                'question': 'Approve workspace.write tests/test_human_response_bounds.py?',
                'allowed_responses': ['APPROVE', 'DENY']}}}
        await self.say('/status')
        asked = self.acp.conn.request_permission.call_args.kwargs
        self.assertEqual([o.option_id for o in asked['options']], ['APPROVE', 'DENY'])
        self.assertEqual([o.kind for o in asked['options']], ['allow_once', 'reject_once'])
        [answer] = self.agent.responses
        self.assertEqual((answer['task_id'], answer['response']['payload']['value'],
                          answer['response']['payload']['request_id']), (task_id, 'APPROVE', 'approve-4'))

    async def test_attaching_the_desktop_conversation_replays_it(self):
        store = self.services.store
        store.create_conversation('desktop-thread')
        store.add_message('desktop-thread', 'human', 'from the desktop', message_id='d1')
        store.add_message('desktop-thread', 'agent', 'reply on the desktop', message_id='d2')
        updates = await self.say('/conversation desktop-thread')  # attaching replays from cursor 0
        texts = [u.content.text for u in updates if u.session_update == 'agent_message_chunk']
        self.assertEqual(texts, ['› from the desktop', 'reply on the desktop'])
        updates = await self.say('/status')  # resumed cursor: nothing is re-emitted
        texts = [u.content.text for u in updates if u.session_update == 'agent_message_chunk']
        self.assertEqual(texts, ['No Task in this Conversation yet.'])

    async def test_diagnostic_d2_syntax_still_reaches_the_control_surface(self):
        self.agent.views['task-diag'] = {'lifecycle': 'UNAVAILABLE'}
        updates = await self.say('inspect task-diag')
        self.assertIn('UNAVAILABLE', updates[-1].content.text)


if __name__ == '__main__':
    unittest.main()
