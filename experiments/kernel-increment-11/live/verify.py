"""Offline independent verification. Never runs a worker or contacts a provider."""
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode,validate_spec
from runtime.kernel.execution import evaluate
from runtime.kernel.events import validate_event


def verify(root):
    def read(name):return json.loads((root/(name+'.json')).read_text())
    fixture=read('fixture');state=read('state');task=state['task_id'];store=ArtifactStore(root/'artifacts')
    result=read('result');dispatch=read('dispatch-result');observation=read('worker-observation')
    request=read('authorized-worker-request');started=read('worker-dispatch-started')
    expected={'organization':'FLOWER','marker':'MASKED_01'};exact=encode(expected)
    context=(root/'worker-input.txt').read_bytes();grant=fixture['authority']
    assert context==exact==request['context']['content'].encode()
    digest=hashlib.sha256(context).hexdigest()
    assert request['context_digest']==fixture['projected']['digest']==digest
    assert grant['context_ref']==request['context_ref']==f'artifact://{task}/sha256:{digest}'
    assert request['authority_digest']==hashlib.sha256(encode(grant)).hexdigest()
    assert request['binding']==grant['bindings'][0]
    assert started['worker_dispatch_id']==request['worker_dispatch_id']=='dispatch:'+task+'/2'
    assert request['read_scope']==['projected-context'] and request['write_scope']==[]
    assert observation['worker_dispatch_count']==1
    assert observation['model_call_count'] is None and observation['provider_internal_retry_count'] is None
    assert observation['final_provider_prompt'] is None and observation['monetary_cost'] is None
    events=[validate_event(json.loads(x)) for x in (root/'events.jsonl').read_text().splitlines()]
    assert len({e['event_id'] for e in events})==len(events)
    assert {e['task_id'] for e in events}=={task} and len({e['run_id'] for e in events})==1
    for e in events:
        assert 'ORCHID' not in json.dumps(e)
        for ref in e['payload_refs']:
            payload=store.read(task,ref['ref']).decode()
            assert 'ORCHID' not in payload and '\\"7319\\"' not in payload and '"7319"' not in payload
    # Server journal proves one capability execution and one accounting settlement.
    states={};commands=[]
    for row in read('journal')['rows']:
        data=json.loads(row['entry_json'])
        if row['entry_type']=='Command: SetState':
            v=data['Command']['SetState'];states.setdefault(v['key'],[]).append(json.loads(bytes(v['value'])))
        if row['entry_type']=='Command: Run':commands.append(row['name'])
    assert commands.count('capability/2')==1 and commands.count('live-evidence/settlement')==1
    assert states['frontier-authority']==[grant]
    assert len(states['frontier-accounting'])==1
    budget=states['frontier-budget'][-1];ledger=states['frontier-accounting'][-1]
    assert budget['dispatches']==1 and len(ledger)==1
    evaluation=evaluate(validate_spec(fixture['spec']),state,store)
    version = observation.get('observation_version')
    assert version is None or (type(version) is int and version == 2)
    corrected_observation = observation.get('observation_version') == 2
    protocol_success = (not corrected_observation or (
        observation['protocol'] == 'codex-exec/rust-v0.155.1'
        and observation['terminal_status'] == 'success'
        and observation['normalized_outcome'] == 'success'
        and not observation['rejection_reasons']))
    passed=(state['lifecycle']=='COMPLETED' and evaluation['payload']['outcome']=='satisfied'
            and observation['exit_code']==0 and not observation['unexpected_items']
            and dispatch['result']['status']=='executed' and protocol_success)
    if passed:
        assert store.read(task,state['artifacts']['result'])==exact
        assert read('worker-normalized-result')['content']==exact.decode()
        assert result==store.read_json(task,state['result_ref'])
        assert budget['completed_effects']==1 and not budget['pending'] and len(budget['settled'])==1
        assert events[-1]['event_type']=='completion.finished' and events[-1]['outcome']=='COMPLETED'
    assert read('processes')['all_stopped']
    report = {'status':'PASS' if passed else 'STOP','task_id':task,'task_lifecycle':state['lifecycle'],
        'worker_dispatch_count':1,'model_call_count':None,'provider_internal_retry_count':None,
        'worker_session_id':observation['worker_session_id'],'worker':'Codex CLI 0.155.1','model_intent':'gpt-6-astra',
        'resolved_model':None,'resolved_account':None,'provider':'built-in OpenAI / ChatGPT','trust_boundary':'https://chatgpt.com',
        'exact_provider_prompt':None,'projector_id':fixture['projected']['projector_id'],'projected_context':context.decode(),
        'context_digest':digest,'worker_received_exact_authorized_projection':True,
        'raw_context_in_worker_input_or_events':False,'completion_evaluation':evaluation,
        'public_worker_messages':[] if corrected_observation else [e['item']['text'] for e in observation['events'] if e.get('type')=='item.completed'],
        'admitted_result':read('worker-normalized-result')['content'] if passed else None,
        'unexpected_worker_items':observation['unexpected_items'],
        'error_item_body':'NOT_RETAINED; cause cannot be isolated from this capture',
        'usage':observation['usage'],'monetary_cost':None,'runtime_ms':observation['runtime_ms'],
        'budget':budget,'accounting':ledger,'events':len(events),'one_reservation':True,'settlement_evaluation_count':1,
        'settled_dispatches':len(budget['settled']),'pending_dispatches':len(budget['pending']),
        'blaine_retry':False,'replacement':False,'fallback':False,'escalation':False,
        'replay_note':'No destructive live replay attempted; isolated proof retained, native journal plus exclusive adapter receipt used',
        'increment_11_ready_to_close':passed,'increment_12_started':False}
    if corrected_observation:
        report.update(observation_version=2, protocol=observation['protocol'],
                      terminal_status=observation['terminal_status'], diagnostics=observation['diagnostics'],
                      error_item_body='STRUCTURE_ONLY; untrusted diagnostic text intentionally omitted',
                      rejection_reasons=observation['rejection_reasons'])
    return report

if __name__=='__main__':
    root=Path(sys.argv[1]);result=verify(root)
    (root/'verification.json').write_bytes(encode(result));print(json.dumps(result,indent=2))
