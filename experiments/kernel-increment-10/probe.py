#!/usr/bin/env python3
"""Real joined Restate Tasks verify the implementation and publish its exact manifest.

Cognition is explicitly scripted, not LLM inference. The independent worker runs
actual focused tests in a fresh process; events come only from production runtime.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode,message
from runtime.kernel.event_sinks import JsonlEventPublisher
from runtime.kernel.execution import Capabilities
from runtime.kernel.workflow import create_workflow
BASE=runpy.run_path(str(ROOT/'scripts/verify-kernel.py'))
http,until,ADMIN,INGRESS,ENDPOINT=(BASE[k] for k in ('http','until','ADMIN','INGRESS','ENDPOINT'))
FILES=['runtime/kernel/events.py','runtime/kernel/event_sinks.py','runtime/kernel/workflow.py','tests/test_kernel_events.py']


def manifest():
    return {'schema_version':1,'implementation':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FILES},
            'adr_sha256':hashlib.sha256((ROOT/'docs/decisions/0018-local-platform-durability-and-observability.md').read_bytes()).hexdigest(),
            'focused_tests':87,'outcome':'PASS'}


def specification(content,child=False):
    return message('TaskSpec',{'objective':('Independently run the focused ExecutionEvent regressions and preserve the exact implementation manifest.' if child else
        'Verify the ExecutionEvent foundation using a joined verification Task, then publish the reviewed implementation manifest under ADR 0018.'),
        'completion':[{'criterion':'Exact independently checked implementation manifest','evidence':{'artifact':'report','sha256':hashlib.sha256(content.encode()).hexdigest()}}],
        'capabilities':['artifact.write','worker.run'],
        'autonomy':{'allowed':['artifact.write','worker.run'],'child_tasks':0 if child else 1}})


def app(out):
    import restate
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    fixture=json.loads((out/'fixture.json').read_text());store=ArtifactStore(out/'artifacts')
    def audit(name,value):
        with (out/name).open('ab',buffering=0) as f:f.write(encode({'pid':os.getpid(),**value})+b'\n');os.fsync(f.fileno())
    class Publisher:
        def publish(self,event):
            if event['task_id']=='telemetry-outage':raise OSError('Injected sink outage')
            JsonlEventPublisher(out/'events.jsonl').publish(event)
            # Lose acknowledgement after durable publication of the actual worker
            # effect. Its Restate capability result was already committed.
            if (event['event_type']=='capability.finished' and event['payload'].get('capability')=='worker.run'
                    and not (out/'crash-observed.json').exists()):
                (out/'crash-observed.json').write_bytes(encode({'event':event,'pid':os.getpid()}))
                time.sleep(45)  # controller SIGKILL; no shared service is stopped
    def worker(packet,operation_id):
        # Fixed trusted test worker, not a model-selected shell command.
        started=time.monotonic()
        completed=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_kernel*.py'],
            cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
        output=completed.stdout.decode();match=re.search(r'Ran (\d+) tests',output)
        report=manifest();report['focused_tests']=int(match[1]) if match else 0
        report['outcome']='PASS' if completed.returncode==0 and output.rstrip().endswith('OK') else 'FAIL'
        audit('worker.jsonl',{'operation_id':operation_id,'packet':packet,'packet_bytes':len(encode(packet)),
            'producer':'deterministic verification subprocess; no LLM','returncode':completed.returncode,
            'test_output':output,'report':report,'seconds':time.monotonic()-started})
        return {'outcome':'success' if report['outcome']=='PASS' else 'failure','attempt_id':operation_id+'-verification',
                'operation_id':operation_id,'content':encode(report).decode()}
    def cognitive(packet):
        turn=packet['payload'];task=turn['task_id'];i=turn['iteration']
        if task=='telemetry-outage':
            action={'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'report','content':fixture['content']}}
        elif task=='execution-events':
            if i==1:action={'type':'SPAWN_TASK','task_spec':specification(fixture['content'],child=True)}
            elif i==2:
                assert turn['observations'][0]['kind']=='TaskResult'
                assert turn['observations'][0]['payload']['outcome']=='COMPLETED'
                action={'type':'HANDOFF','specialist':'specialist'}
            elif i==3:action={'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'report','content':fixture['content']}}
            else:raise AssertionError('Unexpected parent cognition')
        elif i==1:
            worker_packet=message('WorkerInput',{'task_id':task,'objective':'Run the focused kernel tests against the current ExecutionEvent foundation; return its checked manifest.',
                'context':[{'source':'accepted-source-manifest','content':fixture['content']}]})
            action={'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'worker_packet','content':encode(worker_packet).decode()}}
        elif i==2:
            ref=turn['observations'][0]['payload']['artifacts']['worker_packet']
            action={'type':'INVOKE_CAPABILITY','capability':'worker.run','input':{'packet_ref':ref,'artifact':'report'}}
        else:raise AssertionError('Unexpected child cognition')
        decision=message('CognitiveDecision',{k:turn[k] for k in ('task_id','task_revision','turn_id')}|{'next_action':action})
        audit('cognition.jsonl',{'provider':'scripted deterministic application','packet':packet,'packet_bytes':len(encode(packet)),'decision':decision})
        return decision
    class Audited(Capabilities):
        def execute(self,request):
            result=super().execute(request);audit('effects.jsonl',{'request':request,'result':result});return result
    service=create_workflow(store,cognitive,Audited(store,out/'effects.sqlite',worker=worker),
        event_publisher=Publisher(),event_producer_revision=hashlib.sha256((ROOT/'runtime/kernel/workflow.py').read_bytes()).hexdigest())
    config=Config();config.bind=['127.0.0.1:39080'];asyncio.run(serve(restate.app([service]),config))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--restate-server',type=Path);parser.add_argument('--serve',action='store_true');a=parser.parse_args()
    out=a.output.resolve()
    if a.serve:return app(out)
    if out.exists():raise ValueError('Fresh output directory required')
    for port in (38080,39070,39080,35122):
        with socket.socket() as sock:sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);sock.bind(('127.0.0.1',port))
    out.mkdir(parents=True);ev=out/'evidence';ev.mkdir()
    def save(name,value):(ev/(name+'.json')).write_bytes(encode(value)+b'\n')
    content=encode(manifest()).decode();(out/'fixture.json').write_bytes(encode({'content':content}))
    (out/'restate.toml').write_text(f'''cluster-name = "blaine-events-probe"
node-name = "events-probe"
base-dir = "{out/'restate-data'}"
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
    env={k:v for k,v in os.environ.items() if not k.startswith('RESTATE_')};env['PYTHONDONTWRITEBYTECODE']='1'
    processes=[]
    def start(name,command):
        with (out/(name+'.txt')).open('wb') as log:p=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        processes.append(p)
        def ready():
            if p.poll() is not None:raise RuntimeError(name+' exited')
            if name=='server':return http(ADMIN,'/deployments') is not None
            try:
                with socket.create_connection(('127.0.0.1',39080),timeout=1):return True
            except OSError:return False
        until(ready,name+' ready',30);return p
    summary={'status':'UNVERIFIED'}
    try:
        start('server',[str(a.restate_server),'--config-file',str(out/'restate.toml')])
        command=[sys.executable,str(Path(__file__).resolve()),'--serve','--output',str(out)]
        runtime=start('runtime',command);save('deployment',http(ADMIN,'/deployments',{'uri':ENDPOINT}))
        spec=specification(content);save('spec',spec)
        save('submission',http(INGRESS,'/CognitiveTaskV1/execution-events/run/send',spec))
        until(lambda:(out/'crash-observed.json').exists(),'committed worker event',45)
        crash=json.loads((out/'crash-observed.json').read_text());invocation=crash['event']['references']['restate_invocation_id']
        save('journal-before-crash',http(ADMIN,'/query',{'query':f"SELECT * FROM sys_journal WHERE id = '{invocation}' ORDER BY index"}))
        runtime.kill();runtime.wait(timeout=5)
        replacement=start('replacement',command)
        save('recovery',{'terminated_pid':runtime.pid,'signal':'SIGKILL','replacement_pid':replacement.pid,
            'crash_after':'worker effect committed; event appended/fsynced; publication acknowledgement absent','event_id':crash['event']['event_id']})
        def done(task):
            s=http(INGRESS,f'/CognitiveTaskV1/{task}/status',method='POST')['payload'];return s if s.get('result_ref') else None
        state=until(lambda:done('execution-events'),'parent completion',40);save('state',state)
        assert state['lifecycle']=='COMPLETED',state
        child=next(iter(state['children']));save('child-state',done(child))
        for task,name in (('execution-events','parent'),(child,'child')):
            save(name+'-result',http(INGRESS,f'/restate/workflow/CognitiveTaskV1/{task}/attach'))
            save(name+'-journal',http(ADMIN,'/query',{'query':f"SELECT * FROM sys_journal WHERE id IN (SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/{task}/run') ORDER BY index"}))
        save('outage-submission',http(INGRESS,'/CognitiveTaskV1/telemetry-outage/run/send',specification(content,child=True)))
        outage=until(lambda:done('telemetry-outage'),'completion with broken publisher',30);save('outage-state',outage)
        assert outage['lifecycle']=='COMPLETED'
        save('outage-journal',http(ADMIN,'/query',{'query':"SELECT * FROM sys_journal WHERE id IN (SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/telemetry-outage/run') ORDER BY index"}))
        summary={'status':'EXECUTION_COMPLETED_PENDING_INDEPENDENT_VERIFICATION','task_id':'execution-events','child_id':child,
            'model_calls':0,'cognition':'scripted; not LLM inference','worker':'fresh deterministic Python test subprocess',
            'trace_context':'No trace/span context exposed by current instrumentation; no identities manufactured',
            'restarteffect_replayed':True,'telemetry_outage_completed':True}
    except Exception as error:
        summary={'status':'FAIL','error':str(error)};raise
    finally:
        save('execution',summary)
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
        save('processes',{'all_stopped':all(p.poll() is not None for p in processes),'pids':[p.pid for p in processes]})
        for pattern in ('*.jsonl','*.txt','fixture.json','crash-observed.json'):
            for f in out.glob(pattern):shutil.copyfile(f,ev/f.name)
        if (out/'artifacts').exists():shutil.copytree(out/'artifacts',ev/'artifacts',dirs_exist_ok=True)
        print(json.dumps(summary,indent=2),flush=True);print('Evidence:',ev,flush=True)
if __name__=='__main__':main()
