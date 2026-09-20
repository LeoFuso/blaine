#!/usr/bin/env python3
"""One real model choice over a retained authoritative pre-effect state snapshot.
No Task is resumed and no effects execute. This is explicitly a snapshot replay.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode
from runtime.kernel.execution import policy_gate
from runtime.kernel.model import LocalModelCognition
from runtime.kernel.semantic_bridge import SemanticDecisionBridge
from runtime.kernel.semantic_provider import validate_admissibility
from actions import derive, validate, lower_handoff, ProjectedProvider

p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
args=p.parse_args();source=args.source;out=args.output
if out.exists():raise ValueError('Fresh output required')
out.mkdir(parents=True)
def save(name,value):(out/(name+'.json')).write_bytes(encode(value)+b'\n')
initial=json.loads((source/'turns.jsonl').read_text().splitlines()[0]);state=initial['state'];packet=initial['packet']
store=ArtifactStore(source/'artifacts');spec=store.read_json('procedure',state['spec_ref'])['payload']
bridge=SemanticDecisionBridge(None,store,'retention_period','retention','answer')
context=bridge.project(packet);projection=derive(state,spec,context,choice=True)
context['allowed_actions']=projection['actions'];context['specialist']=state['active_specialist']
context['procedure']=[x.split('\n\nREQUEST_HUMAN')[0] for x in context['procedure']]
wire=LocalModelCognition()
def transport(body):
    save('request',{'endpoint':wire.endpoint+'/chat/completions','body':body})
    started=time.monotonic();response=wire.request(body)
    safe={k:response.get(k) for k in ('id','model','created','usage')}
    safe['choices']=[{'finish_reason':c.get('finish_reason'),'content':c.get('message',{}).get('content')} for c in response.get('choices',[])]
    save('response',{'raw_provider_response_safe':safe,'elapsed_seconds':time.monotonic()-started})
    return response
accepted=bridge.request(packet['payload'])['payload']
alternatives=[{'action':'REQUEST_HUMAN','purpose':'retention_period','question':accepted['question'],
    'response':{'kind':'choice','choices':accepted['allowed_responses']}}, {'action':'HANDOFF','specialist':'specialist'}]
checks=[]
for a in alternatives:
    validate(a,projection,context)
    command=lower_handoff(a,packet) if a['action']=='HANDOFF' else bridge.lower(a,packet)
    gate=policy_gate(command,state,spec);assert gate['outcome']=='allow'
    checks.append({'semantic':a,'runtime_command':command,'policy_gate':gate,'effect_executed':False})
save('input',{'snapshot_replay':True,'authoritative_state_at_original_turn':state,'packet':packet,
    'semantic_context':context,'projection':projection,'legal_alternatives':checks,
    'strategies':['Coordinator asks the scoped question directly.','Coordinator transfers ownership to an eligible specialist who can clarify the same requirement.']})
try:
    raw=ProjectedProvider(wire.model,transport).decide(deepcopy(context),projection['actions'])
    save('parsed',raw);validate(raw,projection,context)
    if raw['action']!='HANDOFF':validate_admissibility(raw,context)
    command=lower_handoff(raw,packet) if raw['action']=='HANDOFF' else bridge.lower(raw,packet)
    gate=policy_gate(command,state,spec);assert gate['outcome']=='allow'
    save('result',{'status':'PASS','semantic':raw,'validation':'passed','lowering':command,'policy_gate':gate,
        'effect_executed':False,'model_calls':1,'semantic_strategy_selected_by':'Qwen/Qwen3.5-9B',
        'scope':'One live inference on frozen authoritative state; no runtime Task continuation or effect claimed.'})
except Exception as error:
    save('result',{'status':'FAIL','error':str(error),'effect_executed':False});raise
