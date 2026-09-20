#!/usr/bin/env python3
"""Exactly one live worker dispatch through existing frontier/Restate boundaries."""
import argparse,asyncio,hashlib,json,os,runpy,shutil,socket,subprocess,sys,time
from dataclasses import asdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(Path(__file__).resolve().parent))
from binding import CodexBinding
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode,message,validate_spec
from runtime.kernel.frontier_context import project_context
from runtime.kernel.frontier import (FrontierAuthority,WorkerBinding,GlobalGuardrails,DispatchBudget,
    authority_from_json,proposal_message,authorize,reserve,invoke,settle,record_usage)
from runtime.kernel.execution import Capabilities
from runtime.kernel.workflow import create_workflow
from runtime.kernel.events import safe_prepare,safe_publish,event_identity
from runtime.kernel.event_sinks import JsonlEventPublisher
BASE=runpy.run_path(str(ROOT/'scripts/verify-kernel.py'))
http,until,ADMIN,INGRESS,ENDPOINT=(BASE[k] for k in ('http','until','ADMIN','INGRESS','ENDPOINT'))
TASK='frontier-live-binding-001'

class SyntheticProjector:
    projector_id='synthetic-live-v1'
    def project(self,resolved):
        assert json.loads(resolved)=={'organization':'ORCHID','marker':'7319'}
        return encode({'organization':'FLOWER','marker':'MASKED_01'}).decode()


def app(out):
    import restate
    from hypercorn.asyncio import serve
    from hypercorn.config import Config
    fixture=json.loads((out/'fixture.json').read_text());store=ArtifactStore(out/'artifacts')
    publisher=JsonlEventPublisher(out/'events.jsonl');provider=CodexBinding(out);prepared={}
    def cognitive(packet):
        turn=packet['payload'];i=turn['iteration']
        if i==1:action={'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'packet','content':encode(fixture['packet']).decode()}}
        elif i==2:
            ref=next(x['source'] for x in turn['context'] if x['authority']=='artifact' and x['content'].get('name')=='packet')
            action={'type':'INVOKE_CAPABILITY','capability':'worker.run','input':{'packet_ref':ref,'artifact':'result'}}
        else:action={'type':'COMPLETE'} # failed effect: no redispatch; existing verifier/turn bound owns failure
        return message('CognitiveDecision',{k:turn[k] for k in ('task_id','task_revision','turn_id')}|{'next_action':action})
    def worker(packet,op):
        gate,request,authority=prepared[op]
        result=invoke(request,provider,guardrails=GlobalGuardrails(kill_switch=(out/'cancel-worker').exists()),authority=authority) if request else None
        (out/'dispatch-result.json').write_bytes(encode({'gate':gate,'result':result}))
        return {'outcome':'success' if result and result['status']=='executed' else 'failure',
            'attempt_id':op+'-codex','operation_id':op,'content':result['content'] if result else '', 'frontier_result':result}
    async def checkpoint(ctx,stage,state):
        if not state['decision_ref']:return
        decision=store.read_json(TASK,state['decision_ref'])
        if decision['payload']['next_action'].get('capability')!='worker.run':return
        op=state['decision_id'];run='run:'+ctx.request().id
        async def event(label,kind,outcome,value,cause):
            ref=await ctx.run_typed('live-evidence/'+label,store.put_json,task_id=TASK,value=value)
            ev=await ctx.run_typed('live-event/'+label,safe_prepare,task_id=TASK,run_id=run,step_id='frontier/'+label,
                event_type=kind,outcome=outcome,producer={'kind':'deterministic_application','component':'blaine.frontier.live-probe'},
                references={'capability_call_id':op,'restate_invocation_id':ctx.request().id},payload_refs=(ref,),cause=cause)
            await ctx.run_typed('live-publish/'+label,safe_publish,publisher=publisher,event=ev)
            return event_identity(run,'frontier/'+label)
        if stage=='decision':
            raw=await ctx.get('frontier-authority')
            if raw is None:
                raw=await ctx.run_typed('accept-frontier-authority',lambda:fixture['authority']);ctx.set('frontier-authority',raw)
            authority=authority_from_json(raw)
            projection=project_context(TASK,fixture['resolved'],SyntheticProjector())
            cause=await event('projection','artifact.produced','recorded',{'projector_id':projection.projector_id,
                'version':projection.version,'context_digest':projection.digest,'context_ref':projection.ref},event_identity(run,'start'))
            budget=DispatchBudget.from_json(await ctx.get('frontier-budget') or asdict(DispatchBudget()))
            gate,request=authorize(fixture['proposal'],authority,budget,guardrails=GlobalGuardrails(kill_switch=(out/'cancel-worker').exists()),
                state=state,spec=validate_spec(fixture['spec']),decision=decision,now=await ctx.time(),context=projection)
            prepared[op]=(gate,request,authority)
            selected={'gate':gate,'authority':raw,'request':asdict(request) if request else None,'budget_before':asdict(budget)}
            cause=await event('admission','policy.evaluated',gate['outcome'],selected,cause)
            if request:budget=reserve(budget,request)
            ctx.set('frontier-budget',asdict(budget))
            await event('reservation','policy.evaluated',gate['outcome'],{'budget':asdict(budget),'worker_dispatch_id':request.worker_dispatch_id if request else None},cause)
        elif stage=='effect_persisted':
            gate,request,authority=prepared[op]
            observation=store.read_json(TASK,state['observation_ref'])
            result=store.read_json(TASK,observation['payload']['output']['evidence_ref'])['frontier_result']
            budget=DispatchBudget.from_json(await ctx.get('frontier-budget'))
            ledger=await ctx.get('frontier-accounting') or {}
            if request:
                budget=settle(budget,request,result['status']);ledger=record_usage(ledger,request,result)
                ctx.set('frontier-accounting',ledger)
            ctx.set('frontier-budget',asdict(budget))
            record={'budget':asdict(budget),'accounting':ledger,'result':result,'model_call_count':None,'provider_internal_retry_count':None}
            await event('settlement','capability.finished','success' if result and result['status']=='executed' else 'failure',record,event_identity(run,'frontier/reservation'))
    workflow=create_workflow(store,cognitive,Capabilities(store,out/'effects.sqlite',worker=worker),checkpoint=checkpoint,event_publisher=publisher)
    config=Config();config.bind=['127.0.0.1:39080'];asyncio.run(serve(restate.app([workflow]),config))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True,type=Path);parser.add_argument('--serve',action='store_true');parser.add_argument('--restate-server',type=Path)
    a=parser.parse_args();out=a.output.resolve()
    if a.serve:return app(out)
    if out.exists():raise ValueError('Fresh output required; never reuse/reset a live attempt')
    for port in (38080,39070,39080,35122):
        with socket.socket() as sock:sock.bind(('127.0.0.1',port))
    out.mkdir();ev=out/'evidence';ev.mkdir();store=ArtifactStore(out/'artifacts')
    resolved=encode({'organization':'ORCHID','marker':'7319'}).decode()
    projected=project_context(TASK,resolved,SyntheticProjector());ref=store.put(TASK,projected.content.encode());assert ref==projected.ref
    binding=WorkerBinding('codex-live','codex-cli-0.155.1','openai-chatgpt','gpt-6-astra','https://chatgpt.com',True,('structured-echo',),1)
    authority=FrontierAuthority(2,TASK,(binding,),True,True,'human-authorized-single-live-dispatch',ref,('projected-context',),(),1,int(time.time())+300,60000)
    proposal=proposal_message({'task_id':TASK,'binding_id':binding.binding_id,'provider':binding.provider,'model':binding.model,
        'destination':binding.destination,'context_ref':ref,'read_scope':['projected-context'],'write_scope':[],'runtime_ms':60000})
    packet=message('WorkerInput',{'task_id':TASK,'objective':'Return the supplied projected organization and marker as one JSON object; no tools or additional work.',
        'context':[{'source':ref,'content':projected.content}]})
    spec=message('TaskSpec',{'objective':'Verify one authorized live worker returns the exact projected synthetic organization and marker.',
        'completion':[{'criterion':'Exact projected-value JSON result','evidence':{'artifact':'result','sha256':projected.digest}}],
        'capabilities':['artifact.write','worker.run'],'autonomy':{'allowed':['artifact.write','worker.run']}})
    fixture={'resolved':resolved,'projected':asdict(projected),'authority':asdict(authority),'proposal':proposal,'packet':packet,'spec':spec}
    (out/'fixture.json').write_bytes(encode(fixture))
    (out/'restate.toml').write_text(f'''cluster-name = "blaine-frontier-live"
node-name = "live-probe"
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
    def save(name,value):(ev/(name+'.json')).write_bytes(encode(value))
    # Retain concrete grant/context BEFORE the one authorized external invocation.
    save('pre-dispatch',{'task_id':TASK,'projected_context':asdict(projected),'authority':asdict(authority),
        'worker_dispatch_limit':1,'deadline_ms':60000,'provider_internal_retries':None,'model_call_count':None,
        'blaine_retries':0,'final_provider_prompt':None,'provider_boundary':'https://chatgpt.com'})
    processes=[]
    def start(name,argv):
        with (out/(name+'.log')).open('wb') as log:p=subprocess.Popen(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        processes.append(p)
        def ready():
            if p.poll() is not None:raise RuntimeError(name+' exited')
            if name=='server':return http(ADMIN,'/deployments') is not None
            try:
                with socket.create_connection(('127.0.0.1',39080),timeout=1):return True
            except OSError:return False
        until(ready,name+' ready',30);return p
    try:
        start('server',[str(a.restate_server),'--config-file',str(out/'restate.toml')])
        start('runtime',[sys.executable,str(Path(__file__).resolve()),'--serve','--output',str(out)])
        save('deployment',http(ADMIN,'/deployments',{'uri':ENDPOINT}))
        save('submission',http(INGRESS,f'/CognitiveTaskV1/{TASK}/run/send',spec))
        def done():
            state=http(INGRESS,f'/CognitiveTaskV1/{TASK}/status',method='POST')['payload']
            return state if state.get('result_ref') else None
        state=until(done,'single live probe final state',100);save('state',state)
        save('result',http(INGRESS,f'/restate/workflow/CognitiveTaskV1/{TASK}/attach'))
        save('journal',http(ADMIN,'/query',{'query':f"SELECT * FROM sys_journal WHERE id IN (SELECT id FROM sys_invocation WHERE target = 'CognitiveTaskV1/{TASK}/run') ORDER BY index"}))
        save('execution',{'status':'EXECUTED_PENDING_VERIFICATION','lifecycle':state['lifecycle'],'one_shot':True})
        print(json.dumps({'lifecycle':state['lifecycle'],'task_id':TASK,'output':str(out)}))
    finally:
        (out/'cancel-worker').touch()
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
        save('processes',{'all_stopped':all(p.poll() is not None for p in processes)})
        for pattern in ('*.json','*.jsonl','worker-input.txt'):
            for f in out.glob(pattern):shutil.copyfile(f,ev/f.name)
        shutil.copytree(out/'artifacts',ev/'artifacts',dirs_exist_ok=True)

if __name__=='__main__':main()
