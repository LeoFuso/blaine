"""ACP adapter for D2 controls, usable over the established SSH stdio path."""
import asyncio
import json
import logging
import os
from pathlib import PurePosixPath
import re
import sys
from uuid import uuid4

from acp import PromptResponse, run_agent
from acp.schema import AgentMessageChunk, TextContentBlock

from runtime.acp_agent import BlaineAgent
from runtime.kernel.contracts import identifier, message, text as bounded_text, MAX_PACKET
from runtime.kernel.human import request_digest
from runtime.kernel.workspace import validate_read
from runtime.personal_agent import PersonalAgent, RestateBinding, decision_request, small_request

HELP = ('Use summarize <request-id>: <text>, decision <request-id>: <question>, '
        'inspect/result/cancel/fulfill <task-id>, artifact <task-id>: <name>, '
        'respond <task-id>: YES|NO, or task <JSON control request>.')


class StderrEvents:
    def publish(self, event):
        print(json.dumps(event), file=sys.stderr, flush=True)


class PersonalACP(BlaineAgent):
    def __init__(self, control):
        super().__init__()
        self.control = control
        self.workspaces = {}  # Ephemeral transport routing, never Task state.
        self.can_read = False

    async def initialize(self, protocol_version, client_capabilities=None, **kwargs):
        self.can_read = bool(client_capabilities and client_capabilities.fs and client_capabilities.fs.read_text_file)
        return await super().initialize(protocol_version, **kwargs)

    async def new_session(self, cwd, mcp_servers=None, **kwargs):
        session = await super().new_session(cwd, mcp_servers, **kwargs)
        self.workspaces[session.session_id] = cwd
        return session

    async def call(self, request):
        return await asyncio.to_thread(self.control.execute, request)

    async def command(self, text, session_id):
        bounded_text(text, MAX_PACKET)
        if text.startswith('task '):
            return await self.call(json.loads(text[5:]))
        match = re.fullmatch(r'(summarize|decision) ([A-Za-z0-9_-]{1,80}):\s*(\S[\s\S]*)', text)
        if match:
            action, request_id, value = match.groups()
            raw = small_request(value) if action == 'summarize' else decision_request(request_id, value)
            return await self.call({'operation': 'create', 'request_id': request_id, 'task_request': raw})
        match = re.fullmatch(r'(inspect|result|cancel|fulfill) ([A-Za-z0-9_-]{1,80})', text)
        if match:
            operation, task_id = match.groups()
            if operation != 'fulfill':
                return await self.call({'operation': operation, 'task_id': task_id})
            state = await self.call({'operation': 'inspect', 'task_id': task_id})
            raw = state.get('pending_workspace_read')
            if not raw or not self.can_read:
                raise ValueError('No authorized pending workspace read or client read capability unavailable')
            request = raw['payload']
            validate_read({k: request[k] for k in ('workspace', 'path', 'artifact')})
            root = PurePosixPath(self.workspaces[session_id])
            if root != PurePosixPath(request['workspace']):
                raise ValueError('Pending read belongs to a different workspace')
            # Only the kernel's admitted pending request can cause an ACP filesystem call.
            result = await asyncio.wait_for(self.conn.read_text_file(session_id=session_id,
                path=str(root / request['path'])), timeout=15)
            response = message('CapabilityResult', {'operation_id': request['operation_id'],
                'outcome': 'success', 'output': {'content': result.content}, 'artifacts': {}, 'error': None})
            return await self.call({'operation': 'workspace-result', 'task_id': task_id, 'response': response})
        match = re.fullmatch(r'(respond|artifact) ([A-Za-z0-9_-]{1,80}):\s*(\S[\s\S]*)', text)
        if match:
            operation, task_id, value = match.groups()
            if operation == 'artifact':
                return await self.call({'operation': 'artifact', 'task_id': task_id, 'name': identifier(value)})
            state = await self.call({'operation': 'inspect', 'task_id': task_id})
            request = state.get('pending_human_decision')
            if not request:
                raise ValueError('No pending HumanDecisionRequest')
            human = request['payload']
            response = message('HumanDecisionResponse', {'task_id': task_id,
                'request_id': human['request_id'], 'request_revision': human['revision'],
                'request_digest': request_digest(request), 'response_id': 'response-' + uuid4().hex, 'value': value})
            return await self.call({'operation': 'respond', 'task_id': task_id, 'response': response})
        raise ValueError(HELP)

    async def prompt(self, session_id, prompt, **kwargs):
        try:
            if session_id not in self.sessions or any(not isinstance(block, TextContentBlock) for block in prompt):
                raise ValueError('Unknown session or non-text request')
            text = '\n'.join(block.text for block in prompt).strip()
            result = await self.command(text, session_id)
            output = json.dumps(result)
        except (ValueError, OSError, TypeError) as error:
            # Never expose transport exception bodies, headers, credentials or private paths.
            output = json.dumps({'error': str(error) if isinstance(error, ValueError) else 'Control transport unavailable'})
        await self.conn.session_update(session_id=session_id, update=AgentMessageChunk(
            session_update='agent_message_chunk', content=TextContentBlock(type='text', text=output)))
        return PromptResponse(stop_reason='end_turn')


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    binding = RestateBinding(os.environ.get('BLAINE_D2_INGRESS', 'http://127.0.0.1:48080'))
    asyncio.run(run_agent(PersonalACP(PersonalAgent(binding, StderrEvents()))))
