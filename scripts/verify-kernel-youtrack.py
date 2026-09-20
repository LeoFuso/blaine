#!/usr/bin/env python3
"""Increment 6 scoped Card read gate on isolated Restate; does not manage inference."""
import argparse
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
from runtime.kernel.contracts import encode, message
BASE = runpy.run_path(str(ROOT / 'scripts/verify-kernel.py'))
http, until = BASE['http'], BASE['until']
ADMIN, INGRESS, ENDPOINT = BASE['ADMIN'], BASE['INGRESS'], BASE['ENDPOINT']
CONTENT='CARD_READ_PROBE_COMPLETE'
CASES={'allowed':'Read the scoped coordination Card then produce exact probe evidence.',
       'denied':'Attempt denied Card read, observe denial, then produce permitted probe evidence.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--restate-server', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    if out.exists(): raise RuntimeError('Use a fresh output directory')
    for port in (38080,39070,39080,35122):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1); sock.bind(('127.0.0.1',port))
    out.mkdir(parents=True); evidence=out/'evidence'; evidence.mkdir()
    read={'type':'INVOKE_CAPABILITY','capability':'youtrack.read','input':{'issue_id':'NCP-2'}}
    write={'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'answer','content':CONTENT}}
    (out/'fixtures.json').write_bytes(encode({case:{'actions':[read,write,{'type':'COMPLETE'}]} for case in CASES}))
    def save(name,value): (evidence/(name+'.json')).write_bytes(encode(value)+b'\n')
    save('versions',{'server':subprocess.check_output([str(args.restate_server),'--version'],text=True).strip(),
                     'sdk':importlib.metadata.version('restate-sdk')})
    (out/'restate.toml').write_text(f'''cluster-name = "blaine-model-probe"
node-name = "model-probe"
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
    env={k:v for k,v in os.environ.items() if not k.startswith('RESTATE_')}
    env.update(KERNEL_PROBE_DIR=str(out),PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1')
    processes=[]
    def start(name,command):
        with (out/(name+'.txt')).open('wb') as log:
            p=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        processes.append(p)
        def ready():
            if p.poll() is not None: raise RuntimeError(name+' exited')
            if name=='server': return http(ADMIN,'/deployments') is not None
            try:
                with socket.create_connection(('127.0.0.1',39080),timeout=1): return True
            except OSError: return False
        until(ready,name+' ready',40)
    try:
        start('server',[str(args.restate_server),'--config-file',str(out/'restate.toml')])
        start('runtime',[sys.executable,str(ROOT/'experiments/kernel-increment-6/probe_app.py')])
        save('deployment',http(ADMIN,'/deployments',{'uri':ENDPOINT}))
        states={}
        for task,objective in CASES.items():
            spec=message('TaskSpec',{'objective':objective,'completion':[{'criterion':'Exact answer','evidence':{'artifact':'answer','sha256':hashlib.sha256(CONTENT.encode()).hexdigest()}}],
                'capabilities':['artifact.write','youtrack.read'],'autonomy':{'allowed':['artifact.write','youtrack.read'] if task=='allowed' else ['artifact.write']}})
            save(task+'-spec',spec)
            save(task+'-submission',http(INGRESS,f'/CognitiveTaskV1/{task}/run/send',spec))
            def complete():
                s=http(INGRESS,f'/CognitiveTaskV1/{task}/status',method='POST')['payload']
                return s if s.get('result_ref') else None
            state=until(complete,task+' finished',150)
            states[task]=state; save(task+'-state',state)
            expected='COMPLETED'
            assert state['lifecycle']==expected,state
            save(task+'-result',http(INGRESS,f'/restate/workflow/CognitiveTaskV1/{task}/attach'))
            save(task+'-journal',http(ADMIN,'/query',{'query':f"SELECT * FROM sys_journal WHERE id IN (SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/{task}/run') ORDER BY index"}))
            print('PASS',task,flush=True)
        turns=[json.loads(x) for x in (out/'cognition.jsonl').read_text().splitlines()]
        grouped={task:[x for x in turns if x['packet']['payload']['task_id']==task] for task in CASES}
        actions=lambda task:[x['decision']['payload']['next_action']['type'] for x in grouped[task]]
        assert grouped['allowed'][1]['packet']['payload']['observations'][0]['payload']['output']['issue_id']=='NCP-2'
        assert grouped['allowed'][1]['packet']['payload']['observations'][0]['payload']['outcome']=='success'
        assert grouped['denied'][1]['packet']['payload']['observations'][0]['kind']=='PolicyDecision'
        calls=[json.loads(x) for x in (out/'capabilities.jsonl').read_text().splitlines()]
        card_calls=[x for x in calls if x['request']['payload']['capability']=='youtrack.read']
        assert len(card_calls)==1 and card_calls[0]['request']['payload']['task_id']=='allowed'
        save('summary',{'status':'PASS','cases':list(CASES),'live_card_reads':1,'denied_card_effects':0,
            'cognition':'scripted adapter','model_calls':0,'connector':'existing authenticated YouTrack MCP through controlled experiment bridge',
            'issue':'NCP-2','writes_to_youtrack':0,'card_state_controls_task_lifecycle':False,'next_increment':7})
    except Exception as error:
        save('summary',{'status':'FAIL','gate':'STOP','error':str(error),'exception':type(error).__name__})
        raise
    finally:
        for p in reversed(processes):
            p.terminate()
            try: p.wait(timeout=10)
            except subprocess.TimeoutExpired: p.kill(); p.wait(timeout=5)
        for name in ('cognition.jsonl','capabilities.jsonl','connector-request.json','connector-response.json'):
            if (out/name).exists(): shutil.copyfile(out/name,evidence/name)
        if (out/'artifacts').exists(): shutil.copytree(out/'artifacts',evidence/'artifacts',dirs_exist_ok=True)
        print('Evidence:',evidence,flush=True)

if __name__=='__main__': main()
