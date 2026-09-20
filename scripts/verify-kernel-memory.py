#!/usr/bin/env python3
"""Increment 4 live memory gate on isolated Restate; does not manage inference."""
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
CONTENTS = {'recall': 'VIOLET_7429', 'absent': 'FALLBACK_5281', 'conflict': 'CURRENT_GREEN_6204'}
CASES = {
    'recall': 'Project Aurelia release marker. Retrieve the remembered release marker from semantic context and write it as the exact content of artifact answer. The marker is deliberately not provided in this Task text. Once the artifact exists, request COMPLETE.',
    'absent': 'Project Nebula has no relevant semantic memory. Write exact content FALLBACK_5281 to artifact answer, using this current Task specification. Once the artifact exists, request COMPLETE.',
    'conflict': 'Project Borealis release marker. Current authoritative Task specification supersedes older memory: write exact content CURRENT_GREEN_6204 to artifact answer. Disregard any conflicting historical marker in semantic context. Once the exact current artifact exists, request COMPLETE.',
}


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
    def save(name,value): (evidence/(name+'.json')).write_bytes(encode(value)+b'\n')
    save('versions',{'server':subprocess.check_output([str(args.restate_server),'--version'],text=True).strip(),
                     'sdk':importlib.metadata.version('restate-sdk')})
    (out/'restate.toml').write_text(f'''cluster-name = "blaine-memory-probe"
node-name = "memory-probe"
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
        start('runtime',[sys.executable,str(ROOT/'experiments/kernel-increment-4/probe_app.py')])
        save('deployment',http(ADMIN,'/deployments',{'uri':ENDPOINT}))
        states={}
        for task,objective in CASES.items():
            spec=message('TaskSpec',{'objective':objective,'completion':[{'criterion':'Exact answer','evidence':{'artifact':'answer','sha256':hashlib.sha256(CONTENTS[task].encode()).hexdigest()}}],
                'capabilities':['artifact.write','fixture.effect'],'autonomy':{'allowed':['artifact.write']}})
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
        memories=[json.loads(x) for x in (out/'memory.jsonl').read_text().splitlines()]
        for case in CASES:
            assert actions(case)==['INVOKE_CAPABILITY','COMPLETE'], (case,actions(case))
            assert grouped[case][0]['decision']['payload']['next_action']['input']['content']==CONTENTS[case]
            entries=[x for x in memories if x['task_id']==case]
            assert entries
            if case=='absent': assert all(x['context']==[] for x in entries)
            else:
                expected_marker='VIOLET_7429' if case=='recall' else 'OLD_RED_1938'
                assert all(expected_marker in json.dumps(x['context']) for x in entries),entries
            assert all(x['context_bytes']<=4096 for x in entries)
        assert 'VIOLET_7429' not in CASES['recall']
        audits=[json.loads(x) for x in (out/'model.jsonl').read_text().splitlines()]
        wires=[json.loads(x) for x in (out/'wire.jsonl').read_text().splitlines()]
        assert all(x['raw_response_safe']['model']=='Qwen/Qwen3.5-9B' for x in wires)
        seed=json.loads((ROOT/'experiments/kernel-increment-4/evidence/resumed/seed/seed-complete.json').read_text())
        assert all(x['pid'] != seed['pid'] for x in memories)
        calls=[json.loads(x) for x in (out/'capabilities.jsonl').read_text().splitlines()]
        assert len(calls)==3
        assert all(x['request']['payload']['capability']=='artifact.write' for x in calls)
        save('summary',{'status':'PASS','gate':'PASS','cases':list(CASES),'model_turns':len(audits),
            'max_packet_bytes':max(x['packet_bytes'] for x in audits),
            'total_prompt_tokens':sum(x['usage']['prompt_tokens'] for x in audits),
            'total_completion_tokens':sum(x['usage']['completion_tokens'] for x in audits),
            'fresh_process':{'seed_pid':seed['pid'],'runtime_pids':sorted(set(x['pid'] for x in memories))},
            'architecture_deviations':[],'next_increment':5})
    except Exception as error:
        save('summary',{'status':'FAIL','gate':'STOP','error':str(error),'exception':type(error).__name__,
                        'cases':'See retained per-case state and model/context records','next_increment':4})
        raise
    finally:
        for p in reversed(processes):
            p.terminate()
            try: p.wait(timeout=10)
            except subprocess.TimeoutExpired: p.kill(); p.wait(timeout=5)
        for name in ('process.jsonl','memory.jsonl','wire.jsonl','cognition.jsonl','capabilities.jsonl','policy.jsonl','model.jsonl'):
            if (out/name).exists(): shutil.copyfile(out/name,evidence/name)
        if (out/'artifacts').exists(): shutil.copytree(out/'artifacts',evidence/'artifacts',dirs_exist_ok=True)
        print('Evidence:',evidence,flush=True)

if __name__=='__main__': main()
