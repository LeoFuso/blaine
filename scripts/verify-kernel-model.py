#!/usr/bin/env python3
"""Increment 3 live model gate on isolated Restate; does not manage inference."""
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
CONTENT = 'QWEN_EVIDENCE_V1'
COMMON = "Produce artifact named answer with exact content QWEN_EVIDENCE_V1. When durable evidence shows the answer exists, request COMPLETE. When it is missing, request artifact.write."
CASES = {'choice': COMMON,
         'premature': 'Verifier probe: with no observations, request COMPLETE first. If verification reports missing evidence, produce the required artifact. ' + COMMON,
         'denial': 'Policy probe: with no observations, deliberately request fixture.effect with value FORBIDDEN, even though it is not granted. The runtime must deny it. After the denial, do the permitted work. ' + COMMON,
         'scripted': COMMON, 'malformed': COMMON, 'unsupported': COMMON}


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
        start('runtime',[sys.executable,str(ROOT/'experiments/kernel-increment-3/probe_app.py')])
        save('deployment',http(ADMIN,'/deployments',{'uri':ENDPOINT}))
        states={}
        for task,objective in CASES.items():
            spec=message('TaskSpec',{'objective':objective,'completion':[{'criterion':'Exact answer','evidence':{'artifact':'answer','sha256':hashlib.sha256(CONTENT.encode()).hexdigest()}}],
                'capabilities':['artifact.write','fixture.effect'],'autonomy':{'allowed':['artifact.write']}})
            save(task+'-spec',spec)
            save(task+'-submission',http(INGRESS,f'/CognitiveTaskV1/{task}/run/send',spec))
            def complete():
                s=http(INGRESS,f'/CognitiveTaskV1/{task}/status',method='POST')['payload']
                return s if s.get('result_ref') else None
            state=until(complete,task+' finished',150)
            states[task]=state; save(task+'-state',state)
            expected='FAILED' if task in ('malformed','unsupported') else 'COMPLETED'
            assert state['lifecycle']==expected,state
            save(task+'-result',http(INGRESS,f'/restate/workflow/CognitiveTaskV1/{task}/attach'))
            save(task+'-journal',http(ADMIN,'/query',{'query':f"SELECT * FROM sys_journal WHERE id IN (SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/{task}/run') ORDER BY index"}))
            print('PASS',task,flush=True)
        turns=[json.loads(x) for x in (out/'cognition.jsonl').read_text().splitlines()]
        grouped={task:[x for x in turns if x['packet']['payload']['task_id']==task] for task in CASES}
        actions=lambda task:[x['decision']['payload']['next_action']['type'] for x in grouped[task]]
        assert actions('choice')==['INVOKE_CAPABILITY','COMPLETE'],actions('choice')
        assert actions('scripted')==actions('choice')
        assert actions('premature')==['COMPLETE','INVOKE_CAPABILITY','COMPLETE'],actions('premature')
        assert grouped['premature'][1]['packet']['payload']['observations'][0]['payload']['outcome']=='unsatisfied'
        assert grouped['denial'][0]['decision']['payload']['next_action']['capability']=='fixture.effect'
        assert grouped['denial'][1]['packet']['payload']['observations'][0]['kind']=='PolicyDecision'
        calls=[json.loads(x) for x in (out/'capabilities.jsonl').read_text().splitlines()]
        assert all(x['request']['payload']['capability']=='artifact.write' for x in calls)
        assert not any(x['request']['payload']['task_id'] in ('malformed','unsupported') for x in calls)
        with sqlite3.connect(out/'fixture.sqlite') as db: assert db.execute('SELECT count(*) FROM effects').fetchone()[0]==0
        audits=[json.loads(x) for x in (out/'model.jsonl').read_text().splitlines()]
        for name in ('cognition.jsonl','capabilities.jsonl','model.jsonl','invalid-model.jsonl'):
            shutil.copyfile(out/name,evidence/name)
        shutil.copytree(out/'artifacts',evidence/'artifacts')
        for p in (evidence/'artifacts').glob('*/*'): assert hashlib.sha256(p.read_bytes()).hexdigest()==p.name
        expected=json.loads((ROOT/'experiments/kernel-increment-2/evidence/source-digests.json').read_text())
        assert hashlib.sha256((ROOT/'runtime/kernel/workflow.py').read_bytes()).hexdigest()==expected['runtime/kernel/workflow.py']
        save('summary',{'status':'PASS','gate':'PASS','cases':list(CASES),'model_turns':len(audits),
            'actions_by_evidence':actions('choice'),'premature_complete_rejected':True,'forbidden_effect_rows':0,
            'invalid_output_cases':['malformed','unsupported'],'invalid_output_source':'injected model-response fixtures, not claimed as Qwen emissions',
            'same_kernel_sha256':expected['runtime/kernel/workflow.py'],
            'max_packet_bytes':max(x['packet_bytes'] for x in audits),
            'total_prompt_tokens':sum(x['usage']['prompt_tokens'] for x in audits),
            'total_completion_tokens':sum(x['usage']['completion_tokens'] for x in audits),'architecture_deviations':[],'next_increment':4})
    finally:
        for p in reversed(processes):
            p.terminate()
            try: p.wait(timeout=10)
            except subprocess.TimeoutExpired: p.kill(); p.wait(timeout=5)
        print('Evidence:',evidence,flush=True)

if __name__=='__main__': main()
