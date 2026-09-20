"""Scripted local-only acceptance deployment; production workflow owns all Tasks."""
import asyncio,json,os
from pathlib import Path
import restate
from hypercorn.asyncio import serve
from hypercorn.config import Config
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode,message
from runtime.kernel.execution import Capabilities
from runtime.kernel.workflow import create_workflow
from runtime.kernel.event_sinks import JsonlEventPublisher
ROOT=Path(os.environ['KERNEL_PROBE_DIR']);FIXTURES=json.loads((ROOT/'fixtures.json').read_text())

def audit(file,value):
    with (ROOT/file).open('ab',buffering=0) as f:
        f.write(encode({'pid':os.getpid(),**value})+b'\n');os.fsync(f.fileno())

def cognitive(packet):
    t=packet['payload'];f=FIXTURES[t['task_id']];i=t['iteration']
    if f['role']=='parent':
        if i==1:action=f['spawn']
        elif i==2 and all(x['outcome']=='COMPLETED' for x in t['observations'][0]['payload']['children']):
            action={'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'answer','content':'A+B'}}
        else:action={'type':'COMPLETE'}
    else:
        if i==1:action={'type':'INVOKE_CAPABILITY','capability':'fixture.effect','input':{'value':'PRIVATE_CHILD_'+f['value']}}
        elif i==2:action={'type':'WAIT','wait_id':'release','input_type':'text'}
        elif i==3:action={'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'answer','content':'WRONG' if f['fails'] else f['value']}}
        else:action={'type':'COMPLETE'}
    result=message('CognitiveDecision',{k:t[k] for k in ('task_id','task_revision','turn_id')}|{'next_action':action})
    audit('cognition.jsonl',{'packet':packet,'decision':result});return result

class Audited(Capabilities):
    def execute(self,request):
        audit('capabilities.jsonl',{'request':request})
        return super().execute(request)

async def checkpoint(ctx,stage,state):
    # A test-only durable barrier after fan-in proves replay of consumed outcomes.
    if stage=='children_joined' and FIXTURES[state['task_id']].get('join_barrier'):
        ctx.set('probe',{'stage':stage,'state':state})
        await ctx.promise('probe-joined',type_hint=dict).value()

store=ArtifactStore(ROOT/'artifacts')
workflow=create_workflow(store,cognitive,Audited(store,ROOT/'effects.sqlite'),checkpoint=checkpoint,
    event_publisher=JsonlEventPublisher(ROOT/'events.jsonl'))
@workflow.handler()
async def probe_status(ctx:restate.WorkflowSharedContext)->dict:return await ctx.get('probe') or {}
@workflow.handler()
async def release_probe(ctx:restate.WorkflowSharedContext,request:dict)->dict:
    await ctx.promise('probe-joined',type_hint=dict).resolve({'released':True});return {'released':True}

if __name__=='__main__':
    config=Config();config.bind=['127.0.0.1:39080'];asyncio.run(serve(restate.app([workflow]),config))
