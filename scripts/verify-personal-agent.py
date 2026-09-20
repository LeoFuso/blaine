#!/usr/bin/env python3
"""D2 acceptance using real Restate and independent official-SDK ACP processes."""
import argparse
import asyncio
from contextlib import asynccontextmanager
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import time
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from acp import Client, text_block
from acp.client import ClientSideConnection
from acp.schema import ClientCapabilities, FileSystemCapabilities, ReadTextFileResponse
from acp.stdio import spawn_stdio_transport
from runtime.kernel.contracts import encode, message
from runtime.kernel.human import request_digest
from runtime.personal_agent import small_request, task_identity

ADMIN = 'http://127.0.0.1:49070'
INGRESS = 'http://127.0.0.1:48080'
ENDPOINT = 'http://127.0.0.1:49080'


def http(base, path, body=None):
    request = Request(base + path, data=encode(body) if body is not None else None,
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    with build_opener(ProxyHandler({})).open(request, timeout=5) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def wait_ready(check):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        try:
            if check():
                return
        except OSError:
            pass
        time.sleep(.1)
    raise TimeoutError('Service did not become ready')


async def acceptance(args):
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    evidence = out / 'evidence'
    evidence.mkdir()
    fixture = out / 'disposable-project'
    fixture.mkdir()
    content = 'Disposable ACP project fixture.\n'
    (fixture / 'README.md').write_text(content)
    def save(name, value):
        (evidence / (name + '.json')).write_bytes(encode(value) + b'\n')
    for port in (48080, 49070, 49080, 45122):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
    config = out / 'restate.toml'
    config.write_text(f'''cluster-name = "blaine-d2"
node-name = "d2"
base-dir = "{out / 'restate-data'}"
bind-ip = "127.0.0.1"
bind-port = 45122
advertised-host = "127.0.0.1"
listen-mode = "tcp"
auto-provision = true
default-journal-retention = "7 days"
[admin]
bind-address = "127.0.0.1:49070"
[ingress]
bind-address = "127.0.0.1:48080"
''')
    env = {k: v for k, v in os.environ.items() if not k.startswith('RESTATE_')}
    env.update(BLAINE_D2_DATA=str(out / 'runtime'), PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
    processes = {}
    process_events = []
    generations = {}
    sessions = []
    transcript = []
    task_ids = []
    def start(name):
        generations[name] = generations.get(name, 0) + 1
        command = ([str(args.restate_server.resolve()), '--config-file', str(config)] if name == 'restate' else
            [sys.executable, '-m', 'runtime.personal_runtime'])
        with (out / f'{name}-{generations[name]}.log').open('wb') as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        processes[name] = process
        process_events.append({'action': 'start', 'process': name, 'pid': process.pid})
        def ready():
            if process.poll() is not None:
                raise RuntimeError(f'{name} exited; inspect {out}')
            if name == 'restate':
                return http(ADMIN, '/deployments') is not None
            with socket.create_connection(('127.0.0.1', 49080), timeout=1):
                return True
        wait_ready(ready)

    def kill(name):
        process = processes.pop(name)
        process.kill()
        assert process.wait(timeout=10) == -9
        process_events.append({'action': 'SIGKILL', 'process': name, 'pid': process.pid})

    class Observer(Client):
        def __init__(self):
            self.chunks, self.reads = [], []

        async def session_update(self, session_id, update, **kwargs):
            if update.session_update == 'agent_message_chunk':
                self.chunks.append(update.content.text)

        async def read_text_file(self, session_id, path, **kwargs):
            target = Path(path).resolve()
            assert target == fixture / 'README.md', 'Fixture denies all other paths'
            self.reads.append({'session_id': session_id, 'path': 'README.md'})
            return ReadTextFileResponse(content=target.read_text())

    @asynccontextmanager
    async def session(label):
        observer = Observer()
        with (out / f'acp-{label}.stderr.log').open('wb') as stderr:
            async with spawn_stdio_transport(sys.executable, '-m', 'runtime.personal_acp',
                    cwd=ROOT, env=env, stderr=stderr) as (reader, writer, process):
                conn = ClientSideConnection(observer, writer, reader)
                try:
                    await conn.initialize(protocol_version=1, client_capabilities=ClientCapabilities(
                        fs=FileSystemCapabilities(read_text_file=True)))
                    sid = (await conn.new_session(cwd=str(fixture), mcp_servers=[])).session_id
                    sessions.append({'label': label, 'pid': process.pid, 'session_id': sid})
                    async def command(text):
                        observer.chunks.clear()
                        response = await conn.prompt(session_id=sid, prompt=[text_block(text)])
                        assert response.stop_reason == 'end_turn'
                        result = json.loads(''.join(observer.chunks))
                        transcript.append({'session': label, 'operation': text.split(' ', 1)[0], 'result': result})
                        return result
                    yield command, process, observer
                finally:
                    await conn.close()

    async def until(command, task_id, expected):
        for _ in range(200):
            result = await command('inspect ' + task_id)
            if result.get('lifecycle') == expected and (expected == 'WAITING' or result.get('result_ref')):
                return result
            await asyncio.sleep(.1)
        raise AssertionError((expected, result))

    try:
        start('restate')
        start('runtime')
        save('deployment', http(ADMIN, '/deployments', {'uri': ENDPOINT}))
        save('versions', {'restate': subprocess.check_output([str(args.restate_server), '--version'], text=True).strip(),
            'sdk': importlib.metadata.version('restate-sdk'), 'acp': importlib.metadata.version('agent-client-protocol')})
        async with session('first') as (command, process, observer):
            async with session('concurrent') as (other_command, _, _):
                creates = await asyncio.gather(command('summarize small: Small deterministic remote input'),
                    other_command('summarize small: Small deterministic remote input'))
            small = creates[0]['task_id']
            assert small == creates[1]['task_id'] == task_identity('small')
            save('concurrent-create', creates)
            human = (await command('decision human: Continue the bounded Task?'))['task_id']
            cancelled = (await command('decision cancelled: Await explicit cancellation?'))['task_id']
            task_ids += [small, human, cancelled]
            waiting = await until(command, human, 'WAITING')
            save('human-before-client-loss', waiting)
            process.kill()
            assert await process.wait() == -9
            process_events.append({'action': 'SIGKILL', 'process': 'personal-agent', 'pid': process.pid})
        async with session('second') as (command, process, observer):
            recovered = await command('inspect ' + human)
            assert recovered == waiting
            assert (await command('decision human: Continue the bounded Task?'))['task_id'] == human
            save('human-after-controller-restart', recovered)
            replay = await command('summarize small: Small deterministic remote input')
            assert replay['task_id'] == small
            assert 'error' in await command('summarize small: Different input')
            final = await until(command, small, 'COMPLETED')
            assert final['completion']['payload']['outcome'] == 'satisfied'
            answer = await command('artifact ' + small + ': answer')
            assert json.loads(answer['content'])['word_count'] == 4
            save('small-result', await command('result ' + small))
            save('small-artifact', answer)
            pending = recovered['pending_human_decision']
            wrong = message('HumanDecisionResponse', {'task_id': human, 'request_id': 'decision-1',
                'request_revision': 99, 'request_digest': request_digest(pending), 'response_id': 'wrong', 'value': 'YES'})
            invalid = await command('task ' + json.dumps({'operation': 'respond', 'task_id': human, 'response': wrong}))
            assert 'error' in invalid
            assert (await command('inspect ' + human))['lifecycle'] == 'WAITING'
            kill('runtime')
            kill('restate')
            start('restate')
            start('runtime')
            assert (await command('inspect ' + human)) == recovered
            assert (await command('respond ' + human + ': YES'))['payload']['outcome'] == 'ACCEPTED'
            save('human-completed', await until(command, human, 'COMPLETED'))
            receipt = await command('cancel ' + cancelled)
            assert receipt['outcome'] == 'CANCELLATION_REQUESTED'
            save('cancellation-receipt', receipt)
            save('cancelled', await until(command, cancelled, 'CANCELLED'))
            assert 'error' in await command('respond ' + cancelled + ': YES')
            assert (await command('cancel ' + cancelled))['outcome'] == 'ALREADY_TERMINAL'

            # Existing TaskSpec plus one bounded initial action; no filesystem daemon.
            raw = message('TaskRequest', {'task_spec': message('TaskSpec', {
                'objective': 'Read disposable project README through authorized ACP',
                'completion': [{'criterion': 'Exact fixture bytes', 'evidence': {
                    'artifact': 'answer', 'sha256': hashlib.sha256(content.encode()).hexdigest()}}],
                'capabilities': ['workspace.read'], 'autonomy': {'allowed': ['workspace.read']}}),
                'initial_action': {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.read',
                    'input': {'workspace': str(fixture), 'path': 'README.md', 'artifact': 'answer'}}})
            create = {'operation': 'create', 'request_id': 'workspace', 'task_request': raw}
            workspace = (await command('task ' + json.dumps(create)))['task_id']
            task_ids.append(workspace)
            save('workspace-waiting', await until(command, workspace, 'WAITING'))
            assert observer.reads == []
            process.kill()
            assert await process.wait() == -9
            process_events.append({'action': 'SIGKILL', 'process': 'personal-agent', 'pid': process.pid})
        async with session('third') as (command, process, observer):
            assert (await command('inspect ' + workspace))['lifecycle'] == 'WAITING'
            invalid = message('CapabilityResult', {'operation_id': 'wrong-operation', 'outcome': 'success',
                'output': {'content': content}, 'artifacts': {}, 'error': None})
            assert 'error' in await command('task ' + json.dumps({'operation': 'workspace-result',
                'task_id': workspace, 'response': invalid}))
            assert (await command('inspect ' + workspace))['lifecycle'] == 'WAITING'
            assert (await command('fulfill ' + workspace))['payload']['outcome'] == 'ACCEPTED'
            save('workspace-completed', await until(command, workspace, 'COMPLETED'))
            assert (await command('artifact ' + workspace + ': answer'))['content'] == content
            assert len(observer.reads) == 1
            save('workspace-acp-reads', observer.reads)
            raw['payload']['task_spec']['payload']['autonomy']['allowed'] = []
            denied = (await command('task ' + json.dumps({'operation': 'create',
                'request_id': 'denied', 'task_request': raw})))['task_id']
            task_ids.append(denied)
            state = await until(command, denied, 'FAILED')
            assert state['artifacts'] == {} and state['pending_workspace_read'] is None
            assert 'error' in await command('fulfill ' + denied)
            assert len(observer.reads) == 1
            save('authority-denied', state)
            assert (await command('inspect nonexistent'))['lifecycle'] == 'UNAVAILABLE'
            assert 'error' in await command('artifact ' + small + ': nonexistent')

        rows = http(ADMIN, '/query', {'query': "SELECT target, id FROM sys_invocation WHERE target LIKE 'CognitiveTaskV1/%/run'"})
        save('task-creation-count', rows)
        values = rows['rows']
        assert len(values) == len(task_ids) == 5, rows
        assert len({row['target'] for row in values}) == 5
        journals = http(ADMIN, '/query', {'query': "SELECT * FROM sys_journal WHERE id IN (SELECT id FROM sys_invocation WHERE target LIKE 'CognitiveTaskV1/%/run') ORDER BY id, index"})
        save('journals', [{k: row.get(k) for k in ('id', 'index', 'entry_type', 'name', 'appended_at')}
                          for row in journals['rows']])
        # No model/cognitive step, including known human/workspace waits.
        names = [row.get('name', '') or '' for row in journals['rows']]
        # A denied Task tries the explicit deterministic STOP adapter after gate denial.
        assert sum(name.startswith('cognitive/') for name in names) <= 1, names
        by_target = {row['target']: row['id'] for row in values}
        for task_id in task_ids[:-1]:
            invocation = by_target[f'CognitiveTaskV1/{task_id}/run']
            assert not any((row.get('name') or '').startswith('cognitive/')
                           for row in journals['rows'] if row['id'] == invocation)
        events = [json.loads(line) for line in (out / 'runtime/events.jsonl').read_text().splitlines()]
        assert len([event for event in events if event['event_type'] == 'task.started']) == 5
        assert any(event['event_type'] == 'policy.evaluated' and event['outcome'] == 'deny'
                   and event['task_id'] == denied for event in events)
        save('execution-events', events)
        control_events = []
        for path in out.glob('acp-*.stderr.log'):
            for line in path.read_text().splitlines():
                if line.startswith('{'):
                    event = json.loads(line)
                    if event.get('event_type') == 'personal_agent.control':
                        control_events.append(event)
        assert {'create', 'inspect', 'result', 'artifact', 'respond', 'cancel', 'workspace-result'} <= {e['step_id'] for e in control_events}
        assert any(e['outcome'] == 'rejected' for e in control_events)
        save('control-events', control_events)
        shutil.copytree(out / 'runtime/artifacts', evidence / 'artifacts')
        save('sessions', sessions)
        save('process-events', process_events)
        save('control-transcript', transcript)
        save('summary', {'outcome': 'PASS', 'task_count': 5, 'task_ids': task_ids,
            'stable_identity': True, 'independent_sessions': len(sessions), 'controller_sigkills': 2,
            'client_loss_without_task_loss': True, 'request_replay_without_duplicate': True,
            'concurrent_create_same_task': True, 'task_started_events': 5,
            'human_suspension_resume': True, 'native_cancellation': True, 'result_retrieval': True,
            'runtime_restart': True, 'restate_restart': True, 'policy_denial_without_acp_read': True,
            'acp_workspace_read': 'official SDK disposable fixture', 'live_intellij': 'not exercised',
            'model_calls': 0})
        print('PASS D2 native Restate / ACP controls; evidence: ' + str(evidence), flush=True)
    finally:
        save('process-events', process_events)
        save('control-transcript', transcript)
        for process in processes.values():
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restate-server', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    asyncio.run(acceptance(parser.parse_args()))
