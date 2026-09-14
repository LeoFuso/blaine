#!/usr/bin/env python3
"""Real official-SDK clients, fresh processes, strict capture of ACP stdout."""
import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from acp import Client, text_block
from acp.client import ClientSideConnection
from acp.stdio import spawn_stdio_transport

EVIDENCE = ROOT / '.local/evidence/002-acp'


class CaptureReader(asyncio.StreamReader):
    def __init__(self, reader, capture):
        super().__init__()
        self.reader, self.capture = reader, capture

    async def readuntil(self, separator=b"\n"):
        line = await self.reader.readuntil(separator)
        if line:
            self.capture.write(line)
            self.capture.flush()
        return line

    def __getattr__(self, name):
        return getattr(self.reader, name)


class Observer(Client):
    def __init__(self):
        self.chunks = []

    async def session_update(self, session_id, update, **kwargs):
        if update.session_update == 'agent_message_chunk':
            self.chunks.append(update.content.text)


@asynccontextmanager
async def session(label):
    observer = Observer()
    with (EVIDENCE / f'{label}.stdout.jsonl').open('wb') as capture, \
         (EVIDENCE / f'{label}.stderr.log').open('wb') as stderr:
        async with spawn_stdio_transport(str(ROOT / 'scripts/run-acp-agent.sh'), cwd=ROOT, stderr=stderr) as (reader, writer, process):
            conn = ClientSideConnection(observer, writer, CaptureReader(reader, capture))
            try:
                initialized = await conn.initialize(protocol_version=1)
                assert initialized.protocol_version == 1
                created = await conn.new_session(cwd=str(ROOT), mcp_servers=[])
                yield conn, observer, created.session_id, process
            finally:
                await conn.close()
    lines = (EVIDENCE / f'{label}.stdout.jsonl').read_text().splitlines()
    assert lines, 'No captured protocol output'
    for line in lines:
        message = json.loads(line)  # Any banner or ordinary stdout fails.
        assert message['jsonrpc'] == '2.0'
        assert 'method' in message or 'id' in message


async def command(conn, observer, session_id, text):
    observer.chunks.clear()
    response = await conn.prompt(session_id=session_id, prompt=[text_block(text)])
    assert response.stop_reason == 'end_turn'
    result = ''.join(observer.chunks)
    with (EVIDENCE / 'commands.jsonl').open('a') as log:
        log.write(json.dumps({'session_id': session_id, 'command': text, 'response': result}) + '\n')
    return result


async def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / 'commands.jsonl').write_text('')
    objective = 'Verify interactive durable task'
    async with session('first') as (conn, observer, sid, process):
        state = json.loads(await command(conn, observer, sid, 'create task: ' + objective))
        task_id = state['task_id']
        assert state['status'] == 'WAITING_FOR_USER', state
        assert state['operation_result']['word_count'] == 4
        before = json.loads(await command(conn, observer, sid, 'status ' + task_id))
        assert before == state
        first_pid, first_session = process.pid, sid
        process.kill()
        assert await process.wait() == -9
    async with session('second') as (conn, observer, sid, process):
        assert process.pid != first_pid and sid != first_session
        recovered = json.loads(await command(conn, observer, sid, 'status ' + task_id))
        assert recovered == before
        missing = json.loads(await command(conn, observer, sid, 'status unknown-' + task_id))
        assert missing['status'] == 'NOT_FOUND'
        assert (await command(conn, observer, sid, 'create task: ')).startswith('Error:')
        assert (await command(conn, observer, sid, 'continue unknown-' + task_id + ': approve')).startswith('Error:')
        completed = json.loads(await command(conn, observer, sid, 'continue ' + task_id + ': approved in a new session'))
        assert completed['status'] == 'COMPLETED', completed
        assert completed['task_id'] == task_id
        assert completed['result']['objective'] == objective
        assert completed['result']['user_input'] == 'approved in a new session'
        assert json.loads(await command(conn, observer, sid, 'status ' + task_id)) == completed
        assert json.loads(await command(conn, observer, sid, 'continue ' + task_id + ': duplicate')) == completed
        second_pid = process.pid
    summary = {'status': 'PASS', 'task_id': task_id, 'first_pid': first_pid, 'second_pid': second_pid,
               'first_session': first_session, 'second_session': sid, 'killed_exit': -9,
               'session_independence': 'PASS', 'stdout_protocol_only': 'PASS', 'result': completed}
    (EVIDENCE / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    asyncio.run(asyncio.wait_for(main(), timeout=90))
