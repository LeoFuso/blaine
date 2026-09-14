import unittest
from unittest.mock import AsyncMock, patch

from acp.schema import TextContentBlock
from runtime.acp_agent import BlaineAgent, execute, parse_command


class Commands(unittest.TestCase):
    def test_multiline_objective_and_signal(self):
        self.assertEqual(parse_command('create task: hello\nworld'), ('create', None, 'hello\nworld'))
        self.assertEqual(parse_command('continue task-123: approved: yes'), ('continue', 'task-123', 'approved: yes'))
        self.assertEqual(parse_command('status task-123'), ('status', 'task-123', None))

    def test_rejects_empty_and_path_injection(self):
        for text in ('create task: ', 'continue task-1: ', 'status ../x', 'status x/y', 'hello', 'status x?y'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_command(text)


class Bridge(unittest.IsolatedAsyncioTestCase):
    async def test_status_reads_runtime_without_local_task(self):
        expected = {'task_id': 'task-existing', 'status': 'WAITING_FOR_USER'}
        with patch('runtime.acp_agent.request', return_value=expected) as call:
            self.assertEqual(await execute('status task-existing'), expected)
        call.assert_called_once_with('/TaskWorkflow/task-existing/status')

    async def test_uncertain_create_preserves_id(self):
        with patch('runtime.acp_agent.request', side_effect=TimeoutError('timeout')):
            with self.assertRaisesRegex(ValueError, r'Submission uncertain for task-[0-9a-f]{32}'):
                await execute('create task: sample')

    async def test_errors_are_protocol_updates(self):
        agent = BlaineAgent()
        connection = AsyncMock()
        agent.on_connect(connection)
        session = await agent.new_session(cwd='/does/not/exist')
        response = await agent.prompt(session.session_id, [TextContentBlock(type="text", text='invalid')])
        self.assertEqual(response.stop_reason, 'end_turn')
        update = connection.session_update.call_args.kwargs['update']
        self.assertTrue(update.content.text.startswith('Error:'))
