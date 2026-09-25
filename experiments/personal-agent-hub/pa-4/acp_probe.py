"""Minimal ACP client: drive the real blaine-agent over stdio and print what it renders."""
import asyncio, sys
from acp import spawn_agent_process
from acp.schema import DeniedOutcome, RequestPermissionResponse, TextContentBlock

class Probe:
    async def request_permission(self, options, session_id, tool_call, **kwargs):
        print(f"  [permission requested] {tool_call.title} options={[o.option_id for o in options]} -> left pending (human answers in the desktop)")
        return RequestPermissionResponse(outcome=DeniedOutcome(outcome='cancelled'))
    async def session_update(self, session_id, update, **kwargs):
        kind = update.session_update
        if kind == 'agent_message_chunk':
            print('  [message]', update.content.text[:600].replace('\n', ' | '))
        elif kind in ('tool_call', 'tool_call_update'):
            text = update.content[0].content.text if update.content else ''
            print(f'  [{kind}] {update.tool_call_id[:24]}… status={update.status} :: {text[:500].replace(chr(10), " | ")}')
        elif kind == 'plan':
            print('  [plan]', ' / '.join(f'{e.status}:{e.content[:60]}' for e in update.entries))
    async def write_text_file(self, **kwargs): raise NotImplementedError
    async def read_text_file(self, **kwargs): raise NotImplementedError

async def main(prompts):
    async with spawn_agent_process(lambda agent: Probe(), '/home/leofuso/.local/bin/blaine-agent') as (conn, process):
        await conn.initialize(protocol_version=1)
        session = await conn.new_session(cwd='/home/leofuso/workspace/blaine-pa3-target', mcp_servers=[])
        for prompt in prompts:
            print(f'> {prompt}')
            await conn.prompt(session_id=session.session_id, prompt=[TextContentBlock(type='text', text=prompt)])

asyncio.run(main(sys.argv[1:]))
