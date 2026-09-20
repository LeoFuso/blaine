#!/usr/bin/env python3
"""Increment 7: bounded replaceable Goose worker with independently verified evidence."""
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import runpy
import shutil
import socket
import sqlite3
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.kernel.contracts import child_task_id, encode, message, validate_result
from runtime.kernel.artifacts import ArtifactStore
BASE = runpy.run_path(str(ROOT / 'scripts/verify-kernel.py'))
http, until = BASE['http'], BASE['until']
ADMIN, INGRESS, ENDPOINT = BASE['ADMIN'], BASE['INGRESS'], BASE['ENDPOINT']
PARENT = 'parent'
CHILD = child_task_id(PARENT, 'parent/1')
SECRET = 'CHILD_PRIVATE_WORK_SENTINEL'


def spec(objective, content, children=0):
    return message('TaskSpec', {'objective': objective,
        'completion': [{'criterion': 'Exact accepted answer', 'evidence': {'artifact': 'answer', 'sha256': hashlib.sha256(content.encode()).hexdigest()}}],
        'capabilities': ['artifact.write', 'fixture.effect'],
        'autonomy': {'allowed': ['artifact.write', 'fixture.effect'], 'child_tasks': children}})


def write(content):
    return {'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write', 'input': {'name': 'answer', 'content': content}}


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restate-server', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists():
        raise RuntimeError('Output must be a fresh directory')
    for port in (38080, 39070, 39080, 35122):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(('127.0.0.1', port))
    out.mkdir(parents=True)
    evidence = out / 'evidence'
    evidence.mkdir()
    def save(name, data):
        (evidence / (name + '.json')).write_bytes(encode(data) + b'\n')
    task='worker-task'; sentinel='EXCLUDED_PRIVATE_73281'
    packet=message('WorkerInput', {'task_id':task,
        'objective':'Uppercase the two supplied names and join them with |. Append | followed by the private code if supplied, otherwise UNKNOWN. Return only this single line.',
        'context':[{'source':'fixture:selected-names:v1','content':'Names, in order: alpha, beta.'}]})
    task_spec=spec('Produce the requested worker artifact. Private context excluded from worker: '+sentinel,'ALPHA|BETA|UNKNOWN')
    task_spec['payload']['capabilities'].append('worker.run')
    task_spec['payload']['autonomy']['allowed'].append('worker.run')
    worker_action={'type':'INVOKE_CAPABILITY','capability':'worker.run','input':{'packet_ref':'resolved-by-probe','artifact':'answer'}}
    fixtures={task:{'actions':[
        {'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'worker_packet','content':encode(packet).decode()}},
        worker_action, {'type':'COMPLETE'}, {'type':'WAIT','wait_id':'replace-worker','input_type':'text'},
        worker_action, {'type':'COMPLETE'}]}}
    save('spec',task_spec);save('worker-packet',packet)
    (out/'fixtures.json').write_bytes(encode(fixtures))
    (out / 'restate.toml').write_text(f'''cluster-name = "blaine-child-probe"
node-name = "child-probe"
base-dir = "{out / 'restate-data'}"
bind-ip = "127.0.0.1"
bind-port = 35122
advertised-host = "127.0.0.1"
listen-mode = "tcp"
auto-provision = true
default-journal-retention = "7 days"
[admin]
bind-address = "127.0.0.1:39070"
[ingress]
bind-address = "127.0.0.1:38080"
''')
    env = {k: v for k, v in os.environ.items() if not k.startswith('RESTATE_')}
    env.update(KERNEL_PROBE_DIR=str(out), PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE='1')
    versions = {'server': subprocess.check_output([str(args.restate_server), '--version'], text=True).strip(),
                'sdk': importlib.metadata.version('restate-sdk')}
    assert '1.7.9' in versions['server'] and versions['sdk'] == '1.0.5'
    save('versions', versions)
    processes, events, generations = {}, [], Counter()
    def start(name):
        generations[name] += 1
        command = ([str(args.restate_server), '--config-file', str(out / 'restate.toml')] if name == 'server' else
                   [sys.executable, str(ROOT / 'experiments/kernel-increment-7/probe_app.py')])
        with (out / f'{name}-{generations[name]}.txt').open('wb') as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        processes[name] = process
        events.append({'event': 'start', 'process': name, 'pid': process.pid})
        def ready():
            if process.poll() is not None:
                raise RuntimeError(f'{name} exited; inspect {out}')
            if name == 'server':
                return http(ADMIN, '/deployments') is not None
            try:
                with socket.create_connection(('127.0.0.1', 39080), timeout=2):
                    return True
            except OSError:
                return False
        until(ready, name + ' readiness', 40)
    def kill(name):
        process = processes.pop(name)
        process.kill()
        assert process.wait(timeout=10) == -9
        events.append({'event': 'SIGKILL', 'process': name, 'pid': process.pid, 'exit_code': -9})
    def call(task, handler, body=None):
        return http(INGRESS, f'/CognitiveTaskV1/{task}/{handler}', body, method='POST')
    def status(task):
        return call(task, 'status')['payload']
    def journal(task):
        return http(ADMIN, '/query', {'query': f"SELECT * FROM sys_journal WHERE id IN (SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/{task}/run') ORDER BY index"})
    try:
        start('server')
        start('runtime')
        save('deployment', http(ADMIN, '/deployments', {'uri': ENDPOINT}))
        import signal
        save('submission',call(task,'run/send',task_spec))
        until(lambda:(out/'first-main-seen').exists(),'worker at controlled inference barrier')
        first=json.loads((out/'workers-started.jsonl').read_text().splitlines()[0])
        os.kill(first['pid'],signal.SIGKILL)
        save('worker-kill',{'pid':first['pid'],'attempt_id':first['attempt_id'],'signal':'SIGKILL',
            'point':'Worker sent bounded main request; test barrier held before forwarding'})
        waiting=until(lambda:(s if (s:=status(task)).get('lifecycle')=='WAITING' else None),'Task waiting for replacement')
        assert waiting['task_id']==task and 'worker_packet' in waiting['artifacts']
        assert 'answer' not in waiting['artifacts']
        store=ArtifactStore(out/'artifacts')
        assert store.read_json(task,waiting['completion_ref'])['payload']['outcome']=='unsatisfied'
        save('before-restart',waiting);save('journal-before',journal(task))
        kill('runtime');start('runtime');kill('server');start('server')
        after=status(task);assert after==waiting;save('after-restart',after)
        wait=waiting['wait']
        save('resume',call(task,'submit_input',message('ExternalInput',{'wait_id':wait['wait_id'],
            'task_revision':wait['task_revision'],'input_type':'text','value':'Use a fresh worker and retained bounded packet'})))
        final=until(lambda:(s if (s:=status(task)).get('result_ref') else None),'worker Task completion',100)
        save('final',final);save('journal-after',journal(task))
        assert final['lifecycle']=='COMPLETED',final
        assert store.read(task,final['artifacts']['answer'])==b'ALPHA|BETA|UNKNOWN'
        assert store.read_json(task,final['completion_ref'])['payload']['outcome']=='satisfied'
        workers=[json.loads(x) for x in (out/'workers.jsonl').read_text().splitlines()]
        assert len(workers)==2 and workers[0]['result']['outcome']=='interrupted' and workers[1]['result']['outcome']=='success'
        assert workers[0]['result']['attempt_id']!=workers[1]['result']['attempt_id']
        assert workers[0]['packet']==workers[1]['packet']==packet
        network=[json.loads(x) for x in (out/'network.jsonl').read_text().splitlines()]
        requests=[x for x in network if x['event']=='request']
        assert not any(x['event']=='blocked' for x in network)
        assert requests and all(x['url']=='http://127.0.0.1:8000/v1/chat/completions' and x['request']['model']=='Qwen/Qwen3.5-9B' for x in requests)
        assert all(sentinel not in json.dumps(x) and not x['request'].get('tools') for x in requests)
        assert any(x['event']=='response_model' and x['purpose']=='main_worker' and x['model']=='Qwen/Qwen3.5-9B' for x in network)
        turns=[json.loads(x) for x in (out/'cognition.jsonl').read_text().splitlines()]
        assert len(turns)==6
        save('summary',{'status':'PASS','task_id':task,'cognitive_turns':6,'cognitive_adapter':'scripted',
            'worker_adapter':'Goose 1.50.1','model':'Qwen/Qwen3.5-9B','worker_attempts':2,
            'first_attempt_interrupted':True,'fresh_worker_packet_equal':True,'max_worker_packet_bytes':max(x['packet_bytes'] for x in workers),
            'sentinel_in_any_worker_request':False,'worker_tools_available':False,
            'main_worker_requests':sum(x['purpose']=='main_worker' for x in requests),
            'auxiliary_title_requests':sum(x['purpose']=='auxiliary_title' for x in requests),
            'first_main_request_forwarded':False,'runtime_sigkills':1,'server_sigkills':1,
            'same_Task_after_restart':True,'completion':'independent exact artifact verifier','next_increment':8})
        print('PASS: bounded Goose worker, excluded sentinel, interruption/replacement, verified completion',flush=True)
    except Exception as error:
        save('summary',{'status':'FAIL','gate':'STOP','error':str(error),'exception':type(error).__name__})
        raise
    finally:
        save('process-events', events)
        for process in processes.values():
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for name in ('cognition.jsonl','capabilities.jsonl','workers.jsonl','workers-started.jsonl','network.jsonl'):
            if (out/name).exists():shutil.copyfile(out/name,evidence/name)
        if (out/'artifacts').exists():shutil.copytree(out/'artifacts',evidence/'artifacts',dirs_exist_ok=True)
        print(f'Evidence: {evidence}', flush=True)


if __name__ == '__main__':
    main()
