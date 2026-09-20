#!/usr/bin/env python3
"""Three bounded native Restate Tasks; real Graphify snapshot, scripted cognition, no inference."""
import argparse
import ast
import asyncio
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import socket
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode,message
from runtime.kernel.execution import Capabilities
from runtime.kernel.project_knowledge import ProjectKnowledgeContext
from runtime.kernel.workflow import create_workflow
BASE=runpy.run_path(str(ROOT/'scripts/verify-kernel.py'))
http,until,ADMIN,INGRESS,ENDPOINT=(BASE[k] for k in ('http','until','ADMIN','INGRESS','ENDPOINT'))

def rows(path):return [json.loads(x) for x in path.read_text().splitlines()]

def app(out):
    import restate
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    fixtures=json.loads((out/'fixtures.json').read_text());store=ArtifactStore(out/'artifacts')
    def audit(name,data):
        with (out/name).open('ab',buffering=0) as stream:
            stream.write(encode(data)+b'\n');os.fsync(stream.fileno())
    def provider(request):
        task=request['task_id']
        return ProjectKnowledgeContext(out/'sources'/task,
            None if task=='absent' else out/'graph.json', fixtures['indexed_sources'],
            lambda row:audit('retrieval.jsonl',{'task_id':task,**row}))(request)
    def cognitive(packet):
        turn=packet['payload'];task=turn['task_id'];iteration=turn['iteration']
        if iteration==1:
            action={'type':'INVOKE_CAPABILITY','capability':'artifact.write',
                'input':{'name':'source-snapshot','content':fixtures['cases'][task]['source']}}
        elif iteration==2:
            ref=turn['observations'][0]['payload']['artifacts']['source-snapshot']
            action={'type':'INVOKE_CAPABILITY','capability':'artifact.read','input':{'ref':ref}}
        elif iteration==3:
            observed=turn['observations'][0]['payload']['output']
            assert observed['authority']=='artifact'
            # Deterministic fixture parses supplied exact source; no hidden filesystem/tool access.
            names=sorted(n.name for n in ast.parse(observed['content']).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)))
            action={'type':'INVOKE_CAPABILITY','capability':'artifact.write',
                'input':{'name':'result','content':encode(names).decode()}}
        else:raise AssertionError('Unexpected cognition after sufficient evidence')
        decision=message('CognitiveDecision',{k:turn[k] for k in ('task_id','task_revision','turn_id')}|{'next_action':action})
        audit('cognition.jsonl',{'provider':'scripted deterministic fixture; not LLM inference','packet':packet,'decision':decision})
        return decision
    class Audited(Capabilities):
        def execute(self,request):
            result=super().execute(request);audit('effects.jsonl',{'request':request,'result':result});return result
    async def checkpoint(ctx,stage,state):
        def record():
            audit('states.jsonl',{'stage':stage,'state':state,
                'evaluation':store.read_json(state['task_id'],state['completion_ref']) if state['completion_ref'] else None})
        await ctx.run_typed(f'probe/{stage}/{state["iteration"]}',record)
    service=create_workflow(store,cognitive,Audited(store,out/'effects.sqlite'),providers=(provider,),checkpoint=checkpoint)
    config=Config();config.bind=['127.0.0.1:39080'];asyncio.run(serve(restate.app([service]),config))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--restate-server',type=Path);parser.add_argument('--serve',action='store_true');a=parser.parse_args()
    out=a.output.resolve()
    if a.serve:return app(out)
    if out.exists():raise ValueError('Fresh output directory required')
    for port in (38080,39070,39080,35122):
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);sock.bind(('127.0.0.1',port))
    out.mkdir(parents=True);ev=out/'evidence';ev.mkdir()
    def save(name,value):(ev/(name+'.json')).write_bytes(encode(value)+b'\n')
    prior=json.loads((ROOT/'experiments/graphify-carveout/results.json').read_text())
    graph=Path(prior['work_directory'])/'initial-graph.json';raw=graph.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==prior['initial']['artifact_sha256']
    original=subprocess.check_output(['git','show',prior['corpus_sha']+':runtime/task.py'],cwd=ROOT)
    assert original==(ROOT/'runtime/task.py').read_bytes()
    fixtures={'indexed_sources':{'runtime/task.py':hashlib.sha256(original).hexdigest()},'cases':{}}
    for case in ('fresh','stale','absent'):
        source=original.decode().replace('def validate_request(', 'def validate_request_current(') if case=='stale' else original.decode()
        f=out/'sources'/case/'runtime/task.py';f.parent.mkdir(parents=True);f.write_text(source)
        fixtures['cases'][case]={'source':source,'expected_names':['summarize_objective','validate_request_current' if case=='stale' else 'validate_request']}
    (out/'graph.json').write_bytes(raw);(out/'fixtures.json').write_bytes(encode(fixtures))
    save('provenance',{'graph_sha256':hashlib.sha256(raw).hexdigest(),'graphify_commit':prior['upstream_sha'],
        'source_commit':prior['corpus_sha'],'source_path':'runtime/task.py','indexed_source_sha256':fixtures['indexed_sources']['runtime/task.py'],
        'source_binding':'Initial clean corpus graph from retained carveout, pinned Git blob matches current source before mutation',
        'graphify_extraction_rerun':False,'model_calls':0,'source_fixture_mutated_only_for_stale_case':True})
    (out/'restate.toml').write_text(f'''cluster-name = "blaine-knowledge-probe"
node-name = "knowledge-probe"
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
        until(ready,name+' ready',40)
    summary={'status':'UNVERIFIED'}
    try:
        start('server',[str(a.restate_server),'--config-file',str(out/'restate.toml')])
        start('runtime',[sys.executable,str(Path(__file__).resolve()),'--serve','--output',str(out)])
        save('deployment',http(ADMIN,'/deployments',{'uri':ENDPOINT}))
        for case,fixture in fixtures['cases'].items():
            spec=message('TaskSpec',{'objective':'Locate validate_request','completion':[
                {'criterion':'Exact current source snapshot','evidence':{'artifact':'source-snapshot','sha256':hashlib.sha256(fixture['source'].encode()).hexdigest()}},
                {'criterion':'Source declarations','evidence':{'artifact':'result','sha256':hashlib.sha256(encode(fixture['expected_names'])).hexdigest()}}],
                'capabilities':['artifact.read','artifact.write'],'autonomy':{'allowed':['artifact.read','artifact.write']}})
            save(case+'-spec',spec);save(case+'-submission',http(INGRESS,f'/CognitiveTaskV1/{case}/run/send',spec))
            def complete():
                s=http(INGRESS,f'/CognitiveTaskV1/{case}/status',method='POST')['payload'];return s if s.get('result_ref') else None
            state=until(complete,case+' complete',30);save(case+'-state',state)
            assert state['lifecycle']=='COMPLETED',state
            save(case+'-result',http(INGRESS,f'/restate/workflow/CognitiveTaskV1/{case}/attach'))
            save(case+'-journal',http(ADMIN,'/query',{'query':f"SELECT * FROM sys_journal WHERE id IN (SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/{case}/run') ORDER BY index"}))
        retrieval=rows(out/'retrieval.jsonl');turns=rows(out/'cognition.jsonl')
        fresh=[r for r in retrieval if r['task_id']=='fresh'];stale=[r for r in retrieval if r['task_id']=='stale']
        assert all(r['selected'] for r in fresh)
        assert all(not r['selected'] and any(x['reason']=='source digest mismatch' for x in r['excluded']) for r in stale)
        assert all(r['status']=='absent' for r in retrieval if r['task_id']=='absent')
        for case in fixtures['cases']:
            selected=[t for t in turns if t['packet']['payload']['task_id']==case]
            assert len(selected)==3
            items=[i for i in selected[-1]['packet']['payload']['context'] if isinstance(i['content'],dict) and i['content'].get('classification')=='project_knowledge']
            assert bool(items)==(case=='fresh')
            assert all(i['authority']=='derived' for i in items)
            authoritative=selected[-1]['packet']['payload']['observations'][0]['payload']['output']
            assert authoritative['authority']=='artifact' and authoritative['content']==fixtures['cases'][case]['source']
        summary={'status':'PASS','cases':['fresh','stale','absent'],'model_calls':0,
            'cognition':'scripted; native Restate lifecycle and exact artifact verification',
            'tasks_completed':3,'cognitive_turns':len(turns),'effects':len(rows(out/'effects.jsonl')),
            'max_retrieved_context_bytes':max(r.get('context_bytes',0) for r in retrieval),
            'source_over_stale_index':True,'provider_absence_preserves_execution':True,
            'graphify_build_rerun':False,'next_increment':10}
    except Exception as error:
        summary={'status':'FAIL','error':str(error)};raise
    finally:
        save('summary',summary)
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=10)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
        for f in out.glob('*.jsonl'):shutil.copyfile(f,ev/f.name)
        for f in out.glob('*.txt'):shutil.copyfile(f,ev/f.name)
        for f in ('graph.json','fixtures.json'):shutil.copyfile(out/f,ev/f)
        if (out/'artifacts').exists():shutil.copytree(out/'artifacts',ev/'artifacts',dirs_exist_ok=True)
        print(json.dumps(summary,indent=2),flush=True);print('Evidence:',ev,flush=True)
if __name__=='__main__':main()
