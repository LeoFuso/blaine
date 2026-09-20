#!/usr/bin/env python3
"""Increment 5: scoped human responses, joined children, wait recovery."""
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
    fixtures = {}; scenarios = {}
    for answer in ('YES', 'NO'):
        parent = 'human-parent-' + answer.lower()
        child = child_task_id(parent, parent + '/1')
        request = message('HumanDecisionRequest', {'task_id': child, 'origin_task_id': parent,
            'request_id': 'decision-1', 'revision': 0, 'question': 'Proceed with operation D-1?',
            'allowed_responses': ['YES', 'NO']})
        child_spec = message('TaskSpec', {'objective': 'Obtain a scoped human decision without choosing it.',
            'completion': [{'criterion': 'Valid scoped response', 'evidence': {'artifact': 'response',
                'verifier': 'human_response', 'request': request}}],
            'capabilities': ['human.request'], 'autonomy': {'allowed': ['human.request']}})
        parent_spec = spec('Consume independently verified human decision reference', 'parent exact answer', 1)
        parent_spec['payload']['capabilities'].append('human.request')
        parent_spec['payload']['autonomy']['allowed'].append('human.request')
        fixtures[parent] = {'actions': [{'type':'SPAWN_TASK','task_spec':child_spec}, {'type':'COMPLETE'}, write('parent exact answer'), {'type':'COMPLETE'}]}
        fixtures[child] = {'actions': [
            {'type':'COMPLETE'},
            {'type':'INVOKE_CAPABILITY','capability':'human.request','input':{'request':request}},
            {'type':'WAIT','wait_id':'decision-1','input_type':'human_response'}, {'type':'COMPLETE'}]}
        scenarios[answer] = {'parent':parent,'child':child,'request':request,'parent_spec':parent_spec,'child_spec':child_spec}
    save('specs', scenarios)
    (out / 'fixtures.json').write_bytes(encode(fixtures))
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
                   [sys.executable, str(ROOT / 'experiments/kernel-increment-1/probe_app.py')])
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
        from runtime.kernel.human import request_digest
        results = {}; negatives = []
        for answer, case in scenarios.items():
            parent, child = case['parent'], case['child']
            save(answer+'-submission', call(parent, 'run/send', case['parent_spec']))
            waiting = until(lambda: (s if (s := status(child)).get('lifecycle') == 'WAITING' else None), 'human child waiting')
            before = {'parent':status(parent),'child':waiting}
            assert before['parent']['lifecycle']=='WAITING'
            save(answer+'-before',before)
            body = message('HumanDecisionResponse', {'task_id':child,'request_id':'decision-1',
                'request_revision':0,'request_digest':request_digest(case['request']),
                'response_id':'response-'+answer.lower(),'value':answer})
            bad_values = [('value','MAYBE'),('task_id',parent),('request_id','unrelated'),
                          ('request_revision',99),('request_digest','0'*64)]
            invalids = []
            for field,value in bad_values:
                bad=json.loads(json.dumps(body)); bad['payload'][field]=value
                invalids.append((field,bad))
            bad=json.loads(json.dumps(body)); bad['version']=2; invalids.append(('unsupported_version',bad))
            bad=json.loads(json.dumps(body)); del bad['payload']['value']; invalids.append(('malformed',bad))
            for label,bad in invalids:
                try:
                    call(child,'submit_human_response',bad)
                    raise AssertionError('Invalid response accepted: '+label)
                except BASE['urllib'].error.HTTPError as error:
                    assert error.code==400
                    negatives.append({'case':answer,'control':label,'status':error.code,'response':json.loads(error.read())})
                assert status(child)==waiting
            if answer=='YES':
                save('journals-before',{child:journal(child),parent:journal(parent)})
                kill('runtime'); start('runtime'); kill('server'); start('server')
                after={'parent':status(parent),'child':status(child)}
                assert before==after
                save('after-restart',after)
            save(answer+'-response',body)
            save(answer+'-receipt',call(child,'submit_human_response',body))
            final=until(lambda: (s if (s:=status(parent)).get('result_ref') else None),'parent completed')
            assert final['lifecycle']=='COMPLETED'
            child_state=status(child); assert child_state['lifecycle']=='COMPLETED'
            result=http(INGRESS,f'/restate/workflow/CognitiveTaskV1/{child}/attach')
            validate_result(result,child)
            store=ArtifactStore(out/'artifacts')
            response_ref=result['payload']['artifacts']['response']
            assert store.read_json(child,response_ref)==body
            assert store.read_json(child,child_state['completion_ref'])['payload']['outcome']=='satisfied'
            try:
                call(child,'submit_human_response',body)
                raise AssertionError('Completed wait accepted duplicate')
            except BASE['urllib'].error.HTTPError as error:
                assert error.code==409
                negatives.append({'case':answer,'control':'duplicate','status':error.code})
            save(answer+'-final',{'parent':final,'child':child_state,'child_result':result})
            save(answer+'-journals',{child:journal(child),parent:journal(parent)})
            results[answer]={'outcome':'COMPLETED','response_ref':response_ref,'result_bytes':len(encode(result))}
        audit=[json.loads(x) for x in (out/'cognition.jsonl').read_text().splitlines()]
        for answer,case in scenarios.items():
            parent,child=case['parent'],case['child']
            turns={x['packet']['payload']['iteration']:x['packet']['payload'] for x in audit if x['packet']['payload']['task_id']==parent}
            assert len(turns)==4
            assert turns[2]['observations'][0]['kind']=='TaskResult'
            assert turns[3]['observations'][0]['payload']['outcome']=='unsatisfied'
            assert len([x for x in audit if x['packet']['payload']['task_id']==child])==4
        calls=[json.loads(x) for x in (out/'capabilities.jsonl').read_text().splitlines()]
        assert len([x for x in calls if x['request']['payload']['capability']=='human.request'])==2
        save('negative-controls',negatives)
        save('invocations',http(ADMIN,'/query',{'query':"SELECT id,target,status FROM sys_invocation WHERE target LIKE '%/run'"}))
        save('summary',{'status':'PASS','cases':results,'negative_controls':len(negatives),
            'runtime_sigkills':1,'server_sigkills':1,'same_states_after_restart':True,
            'published_requests':2,'parent_completion_independent':True,'model_calls':0,
            'cognition':'scripted adapter','human_input':'controlled test input, not a real user approval',
            'next_increment':6})
        print('PASS: scoped YES and NO; negative controls; wait recovery; bounded child results',flush=True)
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
        for name in ('cognition.jsonl','capabilities.jsonl'):
            if (out/name).exists(): shutil.copyfile(out/name,evidence/name)
        if (out/'artifacts').exists(): shutil.copytree(out/'artifacts',evidence/'artifacts',dirs_exist_ok=True)
        print(f'Evidence: {evidence}', flush=True)


if __name__ == '__main__':
    main()
