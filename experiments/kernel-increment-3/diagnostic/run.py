"""Two fixture states x two output modes. No runtime/capability execution."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.context import reconstruct
from runtime.kernel.contracts import encode, message, validate_spec
from runtime.kernel.execution import evaluate
from runtime.kernel.model import LocalModelCognition, SYSTEM, strict_json

CONTENT = 'QWEN_EVIDENCE_V1'
OBJECTIVE = 'Produce artifact named answer with exact content QWEN_EVIDENCE_V1. When durable evidence shows the answer exists, request COMPLETE. When it is missing, request artifact.write.'


def safe_response(response):
    # Retain the provider's exact content string before parsing. Never persist
    # private reasoning/reasoning_content, even if a provider adds it.
    choices = []
    for choice in response.get('choices', []):
        msg = choice.get('message', {})
        choices.append({'index': choice.get('index'), 'finish_reason': choice.get('finish_reason'),
                        'message': {k: msg[k] for k in ('role', 'content', 'tool_calls', 'function_call') if k in msg},
                        'omitted_message_fields': [k for k in msg if k not in ('role', 'content', 'tool_calls', 'function_call')]})
    return {k: response[k] for k in ('id','model','object','created','usage') if k in response} | {'choices': choices}


def fixtures(out):
    store = ArtifactStore(out / 'fixture-artifacts')
    spec = validate_spec(message('TaskSpec', {'objective': OBJECTIVE,
        'completion': [{'criterion': 'Exact answer', 'evidence': {'artifact': 'answer', 'sha256': hashlib.sha256(CONTENT.encode()).hexdigest()}}],
        'capabilities': ['artifact.write', 'fixture.effect'], 'autonomy': {'allowed': ['artifact.write']}}))
    base = {'task_id':'diagnostic','revision':1,'lifecycle':'RUNNING','iteration':2,
            'active_specialist':'coordinator','spec_ref':store.put_json('diagnostic',message('TaskSpec',spec)),
            'decision_id':'diagnostic/1','decision_ref':None,'context_ref':None,'observation_ref':None,
            'wait':None,'artifacts':{},'completion_ref':None,'result_ref':None,'remaining_children':0,'children':{}}
    result = {}
    for name in ('missing', 'satisfied'):
        state=deepcopy(base)
        if name=='satisfied': state['artifacts']['answer']=store.put('diagnostic',CONTENT.encode())
        evaluation=evaluate(spec,state,store)
        state['observation_ref']=store.put_json('diagnostic',evaluation)
        result[name]={'packet':reconstruct(state,spec,store),'completion_state':evaluation['payload']['outcome'],
                      'expected_action':'INVOKE_CAPABILITY' if name=='missing' else 'COMPLETE'}
    return result


def integrity(packet):
    turn=packet['payload']
    base={'version':1,'kind':'CognitiveDecision','payload':{k:turn[k] for k in ('task_id','task_revision','turn_id')}}
    invoke=deepcopy(base);invoke['payload']['next_action']={'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'answer','content':CONTENT}}
    unknown=deepcopy(base);unknown['payload']['next_action']={'type':'UNKNOWN_ACTION'}
    records=[]
    for name,content in [('invoke',json.dumps(invoke)),('unknown',json.dumps(unknown)),('malformed','not JSON')]:
        raw={'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':content}}]}
        row={'fixture':name,'raw_response':raw,'effect_dispatched':False}
        try:
            parsed=LocalModelCognition(transport=lambda _:raw)(packet)
            row.update(parsed=parsed,validation='PASS')
            assert name=='invoke' and parsed==invoke
        except ValueError:
            row.update(parsed=None,validation='REJECTED')
            assert name!='invoke'
        records.append(row)
    return records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--samples',type=int,default=1,choices=(1,2,3))
    args=parser.parse_args()
    out=args.output.resolve()
    if out.exists(): raise RuntimeError('Refuse to overwrite diagnostic evidence')
    out.mkdir(parents=True)
    def save(name,value): (out/(name+'.json')).write_bytes(encode(value)+b'\n')
    data=fixtures(out)
    save('fixtures',data);save('integrity',integrity(data['missing']['packet']))
    (out/'system-prompt.txt').write_text(SYSTEM+'\n')
    (out/'adapter-before.py').write_bytes((ROOT/'runtime/kernel/model.py').read_bytes())
    results=[]
    for state,fixture in data.items():
        messages={}
        for mode in ('schema','json-only'):
            for sample in range(1,args.samples+1):
                row={'fixture':state,'output_mode':mode,'sample':sample,'expected_action':fixture['expected_action'],
                     'completion_state':fixture['completion_state'],'effect_dispatched':False,'packet':fixture['packet']}
                def transport(body):
                    sent=deepcopy(body)
                    if mode=='json-only': sent.pop('response_format')
                    row['request']=sent
                    # Exactly the current transport and wire serializer for A.
                    response=LocalModelCognition().request(sent)
                    row['provider_response']=safe_response(response)
                    return response
                try:
                    parsed=LocalModelCognition(transport=transport)(deepcopy(fixture['packet']))
                    row.update(parsed=parsed,parsed_action=parsed['payload']['next_action']['type'],validation='PASS')
                    raw=strict_json(row['provider_response']['choices'][0]['message']['content'])
                    row['raw_equals_parsed']=raw==parsed
                except ValueError as error:
                    row.update(parsed=None,parsed_action=None,validation='REJECTED',error=str(error),
                               validation_detail=str(error.__cause__ or error))
                try:
                    raw=strict_json(row['provider_response']['choices'][0]['message']['content'])
                    row['raw_action']=raw['payload']['next_action']['type']
                    row['missing_envelope_fields']=sorted({'version','kind','payload'}-raw.keys())
                except (ValueError,TypeError,KeyError):
                    row['raw_action']=None
                messages[mode]=row['request']['messages']
                results.append(row)
                save(f'{state}-{mode}-{sample}',row)
                print(state,mode,row['parsed_action'],row['validation'],flush=True)
        assert messages['schema']==messages['json-only']
    correct=lambda mode:all(r['validation']=='PASS' and r['parsed_action']==r['expected_action'] for r in results if r['output_mode']==mode)
    semantic=lambda mode:all(r['raw_action']==r['expected_action'] for r in results if r['output_mode']==mode)
    transformed=any(r.get('raw_equals_parsed') is False for r in results)
    classification=('ADAPTER_DEFECT' if transformed else
                    'CONSTRAINED_DECODING_DEFECT' if semantic('json-only') and not semantic('schema') else
                    'MIXED / UNRESOLVED')
    save('summary',{'classification':classification,'live_calls':len(results),'samples_per_state_mode':args.samples,
         'schema_correct':correct('schema'),'json_only_correct':correct('json-only'),
         'schema_semantic_choice_correct':semantic('schema'),'json_only_semantic_choice_correct':semantic('json-only'),
         'identical_semantic_messages_across_modes':True,'integrity_controls':'PASS','effects_dispatched':0,
         'adapter_before_sha256':hashlib.sha256((out/'adapter-before.py').read_bytes()).hexdigest(),
         'classification_scope':'Action choice before validation; JSON-only wire validity is reported separately.',
         'rows':[{k:r[k] for k in ('fixture','output_mode','sample','expected_action','raw_action','parsed_action','validation','completion_state','effect_dispatched')} for r in results]})

if __name__=='__main__': main()
