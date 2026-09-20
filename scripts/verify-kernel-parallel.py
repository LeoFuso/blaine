#!/usr/bin/env python3
"""Increment 12: native Restate, bounded parallel children, controlled SIGKILLs. No models."""
import argparse,hashlib,importlib.metadata,json,os,runpy,shutil,socket,sqlite3,subprocess,sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from runtime.kernel.contracts import child_task_id,message,encode
BASE=runpy.run_path(str(ROOT/'scripts/verify-kernel.py'));http,until=BASE['http'],BASE['until']
ADMIN,INGRESS,ENDPOINT=BASE['ADMIN'],BASE['INGRESS'],BASE['ENDPOINT']

def spec(value,allocation=0,denied=False):
    return message('TaskSpec',{'objective':'Produce exact '+value+' using only local fixtures.',
        'completion':[{'criterion':'Exact answer','evidence':{'artifact':'answer','sha256':hashlib.sha256(value.encode()).hexdigest()}}],
        'capabilities':['artifact.write','fixture.effect'],
        'autonomy':{'allowed':['artifact.write'] if denied else ['artifact.write','fixture.effect'],'child_tasks':allocation}})

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--restate-server',type=Path,required=True);a=p.parse_args()
    out=a.output.resolve()
    if out.exists():raise ValueError('Fresh output directory required')
    for port in (38080,39070,39080,35122):
        with socket.socket() as s:s.bind(('127.0.0.1',port))
    out.mkdir(parents=True);e=out/'evidence';e.mkdir()
    def save(name,value):(e/(name+'.json')).write_bytes(encode(value)+b'\n')
    fixtures={};cases={}
    for case in ['ab','ba','failure','denial']:
        parent='parallel-'+case;ids=[child_task_id(parent,parent+'/1',i) for i in range(2)]
        children=[spec(value,denied=case=='denial' and i==1) for i,value in enumerate(['A','B'])]
        fixtures[parent]={'role':'parent','spawn':{'type':'SPAWN_TASK','task_specs':children,'independent':True},'join_barrier':case=='ab'}
        for i,key in enumerate(ids):fixtures[key]={'role':'child','value':['A','B'][i],'fails':case in ['failure','denial'] and i==1}
        cases[case]={'parent':parent,'children':ids,'parent_spec':spec('A+B',2),'child_specs':children,'order':[1,0] if case=='ba' else [0,1]}
    (out/'fixtures.json').write_bytes(encode(fixtures));save('cases',cases)
    (out/'restate.toml').write_text(f'''cluster-name = "blaine-parallel-probe"
node-name = "parallel-probe"
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
    env={k:v for k,v in os.environ.items() if not k.startswith('RESTATE_')}
    env.update(KERNEL_PROBE_DIR=str(out),PYTHONPATH=str(ROOT),PYTHONDONTWRITEBYTECODE='1')
    versions={'server':subprocess.check_output([str(a.restate_server),'--version'],text=True).strip(),'sdk':importlib.metadata.version('restate-sdk')}
    assert '1.7.9' in versions['server'] and versions['sdk']=='1.0.5';save('versions',versions)
    processes={};generations=Counter();process_events=[]
    def start(name):
        generations[name]+=1
        argv=[str(a.restate_server),'--config-file',str(out/'restate.toml')] if name=='server' else [sys.executable,str(ROOT/'experiments/kernel-increment-12/probe_app.py')]
        with (out/f'{name}-{generations[name]}.log').open('wb') as log:proc=subprocess.Popen(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        processes[name]=proc;process_events.append({'event':'start','process':name,'pid':proc.pid})
        def ready():
            if proc.poll() is not None:raise RuntimeError(name+' exited')
            if name=='server':return http(ADMIN,'/deployments') is not None
            try:
                with socket.create_connection(('127.0.0.1',39080),timeout=1):return True
            except OSError:return False
        until(ready,name+' ready',30)
    def kill(name):
        proc=processes.pop(name);proc.kill();assert proc.wait(timeout=10)==-9
        process_events.append({'event':'SIGKILL','process':name,'pid':proc.pid,'exit_code':-9})
    def call(task,handler,body=None):return http(INGRESS,f'/CognitiveTaskV1/{task}/{handler}',body,method='POST')
    def status(task):return call(task,'status')['payload']
    def snapshot(ids):return {x:status(x) for x in ids}
    def journal(task):return http(ADMIN,'/query',{'query':f"SELECT * FROM sys_journal WHERE id IN (SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/{task}/run') ORDER BY index"})
    def counts():return dict(Counter(json.loads(x)['packet']['payload']['task_id'] for x in (out/'cognition.jsonl').read_text().splitlines()))
    def restart(label,ids):
        before=snapshot(ids);before_counts=counts();before_j={x:journal(x) for x in ids}
        kill('runtime');kill('server');start('server');start('runtime')
        after=snapshot(ids);assert before==after
        assert counts()==before_counts
        save(label,{'before':before,'after':after,'cognition_before':before_counts,'cognition_after':counts(),'journals_before':before_j})
    try:
        start('server');start('runtime');save('deployment',http(ADMIN,'/deployments',{'uri':ENDPOINT}))
        finals={};results={};all_journals={}
        for name,case in cases.items():
            parent=case['parent'];children=case['children'];ids=[parent,*children]
            save(name+'-submission',call(parent,'run/send',case['parent_spec']))
            for child in children:until(lambda c=child:status(c).get('lifecycle')=='WAITING','child wait')
            waiting=snapshot(ids);assert waiting[parent]['lifecycle']=='WAITING'
            save(name+'-waiting',{'states':waiting,'cognition':counts()})
            if name=='ab':restart('restart-after-creation',ids)
            # Human/text signal to parent cannot forge a child outcome.
            try:
                call(parent,'submit_input',message('ExternalInput',{'wait_id':'release','task_revision':0,'input_type':'text','value':'unrelated'}))
                raise AssertionError('parent accepted unrelated input')
            except BASE['urllib'].error.HTTPError as err:assert err.code==409;save(name+'-parent-input-denied',{'status':err.code})
            for ordinal,pos in enumerate(case['order']):
                child=children[pos];wait=status(child)['wait']
                save(name+f'-receipt-{ordinal}',call(child,'submit_input',message('ExternalInput',{'wait_id':wait['wait_id'],'task_revision':wait['task_revision'],'input_type':'text','value':'release'})))
                until(lambda c=child:status(c).get('result_ref'),'child terminal')
                save(name+f'-completion-{ordinal}',{'child':child,'states':snapshot(ids),'cognition':counts()})
                if ordinal==0:
                    assert status(parent)['lifecycle']=='WAITING' and counts()[parent]==1
                    if name=='ab':restart('restart-after-one-completion',ids)
            if name=='ab':
                until(lambda:call(parent,'probe_status').get('stage')=='children_joined','join barrier')
                restart('restart-after-fan-in',ids)
                save('join-release',call(parent,'release_probe',{}))
            until(lambda:status(parent).get('result_ref'),'parent terminal')
            finals[name]=snapshot(ids)
            for task in ids:
                results[task]=http(INGRESS,f'/restate/workflow/CognitiveTaskV1/{task}/attach');all_journals[task]=journal(task)
            # Duplicate external response cannot progress a terminal child.
            try:
                call(children[0],'submit_input',message('ExternalInput',{'wait_id':'release','task_revision':1,'input_type':'text','value':'duplicate'}))
                raise AssertionError('duplicate accepted')
            except BASE['urllib'].error.HTTPError as err:assert err.code==409
        save('final-states',finals);save('results',results);save('journals',all_journals)
        save('invocations',http(ADMIN,'/query',{'query':"SELECT id,target,status FROM sys_invocation WHERE target LIKE '%/run'"}))
        with sqlite3.connect(out/'effects.sqlite') as db:save('effects',[json.loads(x[0]) for x in db.execute('SELECT receipt FROM effects')])
    finally:
        for name,proc in processes.items():
            proc.terminate()
            try:proc.wait(timeout=10)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
        save('process-events',process_events);save('processes',{'all_stopped':all(x.poll() is not None for x in processes.values())})
        for file in ['cognition.jsonl','capabilities.jsonl','events.jsonl']:
            if (out/file).exists():shutil.copyfile(out/file,e/file)
        shutil.copytree(out/'artifacts',e/'artifacts',dirs_exist_ok=True)
    verify=runpy.run_path(str(ROOT/'experiments/kernel-increment-12/verify.py'))['verify']
    report=verify(e);save('summary',report);print(json.dumps(report,indent=2))

if __name__=='__main__':main()
