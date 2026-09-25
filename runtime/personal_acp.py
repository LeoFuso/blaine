"""Host-side ACP adapter, reached through the private relay.

With the Personal Agent services deployed, an ACP session is a Blaine Conversation:
plain text is a conversation turn, `/execute` compiles and confirms an Execution
Brief, and everything the user sees is rendered from the same conversation
projection the desktop renders (docs/contracts/conversation-projection.md):
Tasks as tool calls with a plan, human requests as ACP permission requests,
results and follow-ups as messages. The D2 control syntax stays for diagnostics.
"""
import asyncio
import json
import logging
import os
from pathlib import PurePosixPath
import re
import sys
from uuid import uuid4

from acp import PromptResponse, run_agent
from acp.schema import (AgentMessageChunk, AgentPlanUpdate, ContentToolCallContent, PermissionOption, PlanEntry,
                        ResourceContentBlock, TextContentBlock, ToolCallProgress, ToolCallStart, ToolCallUpdate)

from runtime.acp_agent import BlaineAgent
from runtime.kernel.contracts import identifier, message, text as bounded_text, MAX_PACKET
from runtime.kernel.human import request_digest
from runtime.kernel.workspace import validate_read
from runtime.personal_agent import PersonalAgent, RestateBinding, decision_request, human_response, small_request

HELP = ('Use summarize <request-id>: <text>, decision <request-id>: <question>, '
        'inspect/result/cancel/fulfill <task-id>, artifact <task-id>: <name>, '
        'respond <task-id>: YES|NO, or task <JSON control request>.')
RESOURCE_NOTICE = 'Attached resource links were not opened or used; workspace context is unavailable in E0.C.'
CONVERSATION_HELP = ('Talk to Blaine in plain text. /execute compiles an Execution Brief from the conversation; '
                     '/execute confirm runs it as a durable Task, /execute discard drops it. /wait follows the '
                     'running Task, /approve or /deny answers a pending request, /status shows the Tasks, '
                     '/conversation <id> attaches another Conversation (e.g. the desktop one).')
DIAGNOSTIC = re.compile(r'(summarize|decision|inspect|result|cancel|fulfill|respond|artifact|task)\b')
TOOL_STATUS = {'submitting': 'pending', 'running': 'in_progress', 'waiting_human': 'in_progress',
               'unavailable': 'in_progress', 'completed': 'completed', 'failed': 'failed', 'cancelled': 'failed'}
PLAN_STATUS = {'done': 'completed', 'failed': 'completed', 'in_progress': 'in_progress', 'waiting': 'in_progress'}


def text_update(text):
    return AgentMessageChunk(session_update='agent_message_chunk', content=TextContentBlock(type='text', text=text))


def content(text):
    return [ContentToolCallContent(type='content', content=TextContentBlock(type='text', text=text))]


def steps_text(entry):
    marks = {'done': '✓', 'failed': '✕', 'in_progress': '…', 'waiting': '⏸'}
    lines = [f"{marks.get(s['status'], '·')} {s['label']}" + (f" — {s['detail']}" if s.get('detail') else '')
             for s in entry.get('steps', [])]
    return f"Task {entry['phase']}\n" + '\n'.join(lines)


def acp_updates(entry, view):
    """ACP rendering of one projection entry. `view` is per-session memory (never Task state)."""
    kind = entry['kind']
    if kind == 'message':
        if entry['role'] == 'agent':
            return [text_update(entry['text'])]
        return [] if entry['entry_id'] in view['sent'] else [text_update('› ' + entry['text'])]
    if kind == 'followup':
        return [text_update(entry['text'])]
    if kind == 'brief':
        if entry['status'] == 'proposed':
            requested = entry['requested']
            return [text_update(
                f"Execution Brief proposed: {entry['objective']}\n"
                f"Deliverable: {entry['deliverable']['path']} in {entry['deliverable']['workspace_id']}\n"
                f"Reads first: {', '.join(entry['inspect']) or '—'}; targeted tests: {', '.join(entry['targeted_tests'])}\n"
                f"Requests: {', '.join(requested['capabilities'])}; profiles {', '.join(requested['profiles'])}; "
                f"asks before: {', '.join(requested['ask_before']) or 'nothing'}\n"
                'Reply /execute confirm to run it as a durable Task, or /execute discard.')]
        return [text_update('Execution Brief discarded.')] if entry['status'] == 'rejected' else []
    if kind == 'task':
        task_id, status = entry['task_id'], TOOL_STATUS.get(entry['phase'], 'in_progress')
        title = 'Blaine Task: ' + ((entry.get('deliverable') or {}).get('path') or entry.get('objective') or task_id)[:120]
        plan = AgentPlanUpdate(session_update='plan', entries=[
            PlanEntry(content=s['label'] + (f" — {s['detail']}" if s.get('detail') else ''), priority='medium',
                      status=PLAN_STATUS.get(s['status'], 'pending')) for s in entry.get('steps', [])])
        if task_id not in view['started']:
            view['started'].add(task_id)
            start = ToolCallStart(session_update='tool_call', tool_call_id=task_id, title=title, kind='execute',
                                  status=status, content=content(steps_text(entry)))
            return [start, plan]
        return [ToolCallProgress(session_update='tool_call_update', tool_call_id=task_id, status=status,
                                 content=content(steps_text(entry))), plan]
    if kind == 'result' and entry.get('task_id'):
        status = 'completed' if entry.get('lifecycle') == 'COMPLETED' else 'failed'
        return [ToolCallProgress(session_update='tool_call_update', tool_call_id=entry['task_id'], status=status,
                                 content=content(entry.get('markdown') or ''))]
    return []  # human requests are asked, not printed


class StderrEvents:
    def publish(self, event):
        print(json.dumps(event), file=sys.stderr, flush=True)


class PersonalACP(BlaineAgent):
    def __init__(self, control, services=None):
        super().__init__()
        self.control = control
        self.services = services  # Personal Agent services; None keeps the D2 control-only adapter
        self.workspaces = {}  # Ephemeral transport routing, never Task state.
        self.views = {}  # session -> {conversation, cursor, started, sent, asked}; rendering memory only
        self.can_read = False

    async def initialize(self, protocol_version, client_capabilities=None, **kwargs):
        self.can_read = bool(client_capabilities and client_capabilities.fs and client_capabilities.fs.read_text_file)
        return await super().initialize(protocol_version, **kwargs)

    async def new_session(self, cwd, mcp_servers=None, **kwargs):
        session = await super().new_session(cwd, mcp_servers, **kwargs)
        self.workspaces[session.session_id] = cwd
        self.attach(session.session_id, 'acp-' + session.session_id[:32])
        return session

    def attach(self, session_id, conversation_id):
        self.views[session_id] = {'conversation': conversation_id, 'cursor': 0, 'started': set(),
                                  'sent': set(), 'asked': set()}

    # ------------------------------------------------------------------ conversation mode
    async def run(self, function, *args):
        return await asyncio.to_thread(function, *args)

    async def emit(self, session_id):
        """Render everything the projection changed since this session's cursor."""
        view = self.views[session_id]
        for _ in range(8):  # bounded: answering a request may change the projection again
            read = await self.run(self.services.projection.read, view['conversation'], view['cursor'])
            view['cursor'] = read['cursor']
            pending = []
            for entry in read['entries']:
                for update in acp_updates(entry, view):
                    await self.conn.session_update(session_id=session_id, update=update)
                if entry['kind'] == 'human_request' and entry['status'] == 'pending' and entry['entry_id'] not in view['asked']:
                    pending.append(entry)
            if not pending:
                return
            for entry in pending:
                await self.ask(session_id, entry)

    async def ask(self, session_id, entry):
        """A Task's human request as an ACP permission request; the Task decides what an answer means."""
        self.views[session_id]['asked'].add(entry['entry_id'])
        kinds = {'APPROVE': 'allow_once', 'DENY': 'reject_once'}
        options = [PermissionOption(option_id=value, name=value.title(), kind=kinds.get(value, 'allow_once'))
                   for value in entry['options']]
        response = await self.conn.request_permission(session_id=session_id, options=options,
            tool_call=ToolCallUpdate(tool_call_id=entry['task_id'], title=entry.get('question') or 'Blaine requests a decision',
                                     status='in_progress'))
        outcome = response.outcome
        if getattr(outcome, 'outcome', None) != 'selected':
            await self.conn.session_update(session_id=session_id, update=text_update(
                'The request is still pending; answer later with /approve or /deny.'))
            return
        await self.answer(entry['task_id'], outcome.option_id, entry['request_id'])

    async def answer(self, task_id, value, request_id):
        def respond():
            state = self.services.agent.execute({'operation': 'inspect', 'task_id': task_id})
            envelope = human_response(state, task_id, value, request_id)
            return self.services.agent.execute({'operation': 'respond', 'task_id': task_id, 'response': envelope})
        return await self.run(respond)

    async def conversation_turn(self, session_id, text):
        view = self.views[session_id]
        conversation = view['conversation']
        await self.emit(session_id)
        if not text.startswith('/'):
            message_id = 'acp' + uuid4().hex[:24]
            view['sent'].add(message_id)
            await self.run(self.services.conversation.converse, conversation, message_id, text)
        else:
            command, _, argument = text[1:].partition(' ')
            argument = argument.strip()
            if command == 'help':
                await self.conn.session_update(session_id=session_id, update=text_update(CONVERSATION_HELP))
            elif command == 'conversation':
                self.attach(session_id, argument)
            elif command == 'execute' and not argument:
                await self.run(self.services.briefs.propose, conversation)
            elif command == 'execute' and argument in ('confirm', 'discard'):
                proposed = [b for b in await self.run(self.services.store.list_briefs, conversation)
                            if b['status'] == 'proposed']
                if not proposed:
                    raise ValueError('No proposed Execution Brief; use /execute first.')
                action = self.services.briefs.confirm if argument == 'confirm' else self.services.briefs.reject
                await self.run(action, conversation, proposed[-1]['brief_id'])
            elif command in ('approve', 'deny'):
                read = await self.run(self.services.projection.read, conversation, 0)
                pending = [e for e in read['entries'] if e['kind'] == 'human_request' and e['status'] == 'pending']
                if not pending:
                    raise ValueError('No pending request in this Conversation.')
                await self.answer(pending[-1]['task_id'], 'APPROVE' if command == 'approve' else 'DENY',
                                  pending[-1]['request_id'])
            elif command == 'status':
                read = await self.run(self.services.projection.read, conversation, 0)
                tasks = [e for e in read['entries'] if e['kind'] == 'task']
                text = '\n\n'.join(steps_text(e) for e in tasks) or 'No Task in this Conversation yet.'
                await self.conn.session_update(session_id=session_id, update=text_update(text))
            elif command == 'wait':
                minutes = min(30, max(1, int(argument or 10)))
                deadline = asyncio.get_running_loop().time() + 60 * minutes
                while asyncio.get_running_loop().time() < deadline:
                    await self.emit(session_id)
                    read = await self.run(self.services.projection.read, conversation, 0)
                    active = [e for e in read['entries'] if e['kind'] == 'task'
                              and (e['phase'] in ('submitting', 'running', 'unavailable') or e['delivery'] != 'surfaced')
                              and e['phase'] != 'waiting_human']
                    if not active:
                        break
                    await asyncio.sleep(3)
            else:
                raise ValueError(CONVERSATION_HELP)
        await self.emit(session_id)

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
        resource_links = False
        try:
            known_session = session_id in self.sessions
            supported = all(isinstance(block, (TextContentBlock, ResourceContentBlock)) for block in prompt)
            if not known_session or not supported:
                # Diagnose IDE compatibility without recording prompts, resource URIs,
                # metadata, or client-supplied session identifiers. Labels are bounded.
                kinds = ('text', 'image', 'audio', 'resource_link', 'resource')
                counts = {kind: 0 for kind in (*kinds, 'unknown')}
                for block in prompt:
                    kind = getattr(block, 'type', None)
                    counts[kind if kind in kinds else 'unknown'] += 1
                print(json.dumps({'event': 'acp_prompt_rejected',
                    'known_session': known_session, 'block_counts': counts}),
                    file=sys.stderr, flush=True)
                if not known_session:
                    raise ValueError('Unknown ACP session; start a new Blaine chat.')
                raise ValueError('Images, audio and embedded resource content are unsupported in E0.C. '
                                 'No workspace operation was performed.')
            # ResourceLink is baseline ACP input, not permission to resolve a URI.
            # Do not turn link names, descriptions or metadata into control text.
            resource_links = any(isinstance(block, ResourceContentBlock) for block in prompt)
            text = '\n'.join(block.text for block in prompt if isinstance(block, TextContentBlock)).strip()
            if not text:
                raise ValueError('A text control command is required. Resource links are not opened in E0.C.')
            if self.services is not None and not DIAGNOSTIC.match(text):
                await self.conversation_turn(session_id, text)
                return PromptResponse(stop_reason='end_turn')
            result = await self.command(text, session_id)
            output = json.dumps(result)
        except (ValueError, OSError, TypeError) as error:
            # Never expose transport exception bodies, headers, credentials or private paths.
            output = json.dumps({'error': str(error) if isinstance(error, ValueError) else 'Control transport unavailable'})
        if resource_links:
            output = RESOURCE_NOTICE + '\n' + output
        await self.conn.session_update(session_id=session_id, update=AgentMessageChunk(
            session_update='agent_message_chunk', content=TextContentBlock(type='text', text=output)))
        return PromptResponse(stop_reason='end_turn')


if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    binding = RestateBinding(os.environ.get('BLAINE_D2_INGRESS', 'http://127.0.0.1:48080'))
    services = None
    if os.environ.get('BLAINE_DEPLOYMENT_CONFIG'):
        # Same composition root as the bridge: one Conversation store, one projection.
        from runtime.personal_services import Services
        services = Services()
    asyncio.run(run_agent(PersonalACP(PersonalAgent(binding, StderrEvents()), services)))
