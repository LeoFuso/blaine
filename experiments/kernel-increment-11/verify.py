#!/usr/bin/env python3
"""Independent offline gate: provider records, Restate journal, events and verifier."""
from collections import Counter
import json
import hashlib
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode,validate_spec
from runtime.kernel.events import validate_event
from runtime.kernel.execution import evaluate


def verify(root):
    def assert_no_raw_fixture(text, fixture):
        # Read the exact values from the run being verified, including historical runs.
        # Current fixture spellings must not replace historical evidence expectations.
        values = [field.strip().split('=', 1)[1] for field in fixture['raw_context'].split(';')]
        assert len(values) == 2 and all(values)
        assert all(value not in text for value in values)
    def read(name):return json.loads((root/(name+'.json')).read_text())
    def rows(name):return [json.loads(x) for x in (root/(name+'.jsonl')).read_text().splitlines()]
    def results(name):
        commands={};values={}
        for row in read(name)['rows']:
            data=json.loads(row['entry_json'])
            if row['entry_type']=='Command: Run':commands[data['Command']['Run']['completion_id']]=row['name']
            elif row['entry_type']=='Notification: Run':
                item=data['Notification']['Completion']['Run']
                if 'Success' in item['result']:
                    raw=bytes(item['result']['Success'])
                    values[item['completion_id']]=json.loads(raw) if raw else None
        return {commands[k]:v for k,v in values.items() if k in commands}
    def states(name,key):
        records=[]
        for row in read(name)['rows']:
            if row['entry_type']=='Command: SetState':
                entry=json.loads(row['entry_json'])['Command']['SetState']
                if entry['key']==key:records.append(json.loads(bytes(entry['value'])))
        return records
    fixtures=read('fixtures');calls=rows('provider-calls');policies=rows('policy');settlements=rows('settlements')
    events=rows('events');store=ArtifactStore(root/'artifacts');checks=[]
    assert read('execution')['status']=='EXECUTED_PENDING_INDEPENDENT_VERIFICATION'
    counts=Counter(c['request']['task_id'] for c in calls)
    assert counts=={'authorized':1,'repeat':1,'not-executed':1,'timeout':1},counts
    assert len({c['request']['worker_dispatch_id'] for c in calls})==len(calls)
    for call in calls:
        request=call['request'];admitted=next(p for p in policies if 'dispatch:'+p['operation_id']==request['worker_dispatch_id'])
        assert admitted['gate']=={'outcome':'allow','reason_category':'admitted'}
        assert request==admitted['authorized']
        grant=fixtures[request['task_id']]['authority']
        for key in ('task_id','context_ref'):
            assert request[key]==grant[key]
        assert request['binding']==grant['bindings'][0]
        assert set(request['read_scope'])<=set(grant['read_scope']) and set(request['write_scope'])<=set(grant['write_scope'])
        assert 'approval_ref' not in request and 'budget' not in request
        assert request['version']==3
        assert request['context']['content']==store.read(request['task_id'],request['context_ref']).decode()
        assert request['context']==fixtures[request['task_id']]['projected_context']
        assert request['context_digest']==request['context']['digest']==hashlib.sha256(request['context']['content'].encode('utf-8')).hexdigest()
        assert request['context_ref'].endswith(request['context_digest'])
        assert_no_raw_fixture(json.dumps(request), fixtures[request['task_id']])
    for case,fixture in fixtures.items():
        state=read(case+'-state');result=read(case+'-result');journal=results(case+'-journal')
        assert result==store.read_json(case,state['result_ref'])
        assert evaluate(validate_spec(fixture['spec']),state,store)['payload']['outcome']=='satisfied'
        assert state['lifecycle']==result['payload']['outcome']=='COMPLETED'
        assert store.read_json(case,state['artifacts']['report'])==fixture['expected']
        case_policies=[p for p in policies if p['task_id']==case]
        assert len(case_policies)==(2 if case=='repeat' else 1)
        for policy in case_policies:
            i=policy['operation_id'].rsplit('/',1)[1]
            assert journal['frontier-policy/'+i].startswith('artifact://'+case+'/sha256:')
            if policy['gate']['outcome']=='deny':
                assert policy['authorized'] is None and policy['budget_before']==policy['budget_reserved']
                assert not any(c['request']['worker_dispatch_id']=='dispatch:'+policy['operation_id'] for c in calls)
        final=[x for x in settlements if x['task_id']==case][-1]['budget']
        assert states(case+'-journal','frontier-budget')[-1]==final
        assert states(case+'-journal','frontier-authority')==[fixture['authority']]
        accounting=states(case+'-journal','frontier-accounting')
        if case in ('authorized','repeat','not-executed','timeout','substitution'):
            assert len(accounting)==1 and len(accounting[0])==1
            observed=next(iter(accounting[0].values()))
            assert observed['accounting_mode']=='observed_only'
            assert observed['worker_dispatch_id']=='dispatch:'+case+'/2'
            assert final['dispatches']==1
            assert not any(k in final for k in ('tokens_charged','cost_charged_microusd','reserved_tokens'))
            if case in ('authorized','repeat'):
                assert final['completed_effects']==1 and len(final['settled'])==1 and not final['pending']
                assert observed['usage']['model_calls']==3 # SYNTHETIC illustrative counters, not inference
                assert observed['usage']['input_tokens']==120 and observed['usage']['output_tokens']==30
                assert observed['usage']['cost_microusd'] is None
                assert observed['worker_session_id']!=observed['worker_dispatch_id']
            elif case in ('not-executed','substitution'):
                assert final['completed_effects']==0 and not final['pending'] and len(final['settled'])==1
            else:
                assert final['completed_effects']==0 and len(final['pending'])==1 and not final['settled']
                assert observed['usage']['model_calls'] is None and observed['status']=='unknown'
        else:
            assert not accounting and final==fixture['initial_budget']
        task_events=[e for e in events if e['task_id']==case];known={e['event_id'] for e in task_events}
        assert len(known)==len(task_events) and len({e['run_id'] for e in task_events})==1
        for event in task_events:
            validate_event(event)
            if 'causation_event_id' in event:assert event['causation_event_id'] in known
            for ref in event['payload_refs']:store.read(case,ref['ref'])
        gate_events=[e for e in task_events if e['step_id'].startswith('frontier/policy/')]
        assert len(gate_events)==len(case_policies)
        for event,policy in zip(gate_events,case_policies):
            evidence=store.read_json(case,event['payload_refs'][0]['ref'])
            assert evidence['gate']==policy['gate'] and event['outcome']==policy['gate']['outcome']
        assert task_events[-1]['event_type']=='completion.finished'
        checks.append({'case':case,'status':'PASS','provider_calls':counts[case],'reason_category':case_policies[-1]['gate']['reason_category'],
            'final_budget':final,'independent_verifier':'satisfied','events':len(task_events)})
    before=results('authorized-before-restart');after=results('authorized-journal')
    assert before['capability/2']==after['capability/2']
    held=states('authorized-before-restart','frontier-budget')[-1]
    assert len(held['pending'])==1 and held['completed_effects']==0
    assert not states('authorized-before-restart','frontier-accounting')
    assert states('authorized-journal','frontier-budget')[0]==held
    assert 'frontier-audit-settlement/2' not in before and 'frontier-audit-settlement/2' in after
    assert len([x for x in settlements if x['task_id']=='authorized'])==1
    assert read('recovery')['killed_pid']!=read('recovery')['replacement_pid']
    assert read('processes')['all_stopped']
    routing_ref=after['frontier-routing/2']
    routing=store.read_json('authorized',routing_ref)
    economical=routing['economical_sufficient'];strong=routing['strong_required']
    assert economical['selected_binding']=='economical' and strong['selected_binding']=='strong'
    authorized_call=next(c for c in calls if c['request']['task_id']=='authorized')
    assert authorized_call['request']['binding']['binding_id']==economical['selected_binding']
    recorded=next(iter(states('authorized-journal','frontier-accounting')[-1].values()))
    assert all(recorded['observed_producer'][k]==authorized_call['request']['binding'][k] for k in recorded['observed_producer'])
    assert [c['assessment']['suitability'] for c in economical['candidates']]==['UNDERPOWERED','JUST_RIGHT','OVERKILL','OVERKILL']
    assert routing['explicit_strong_authorization']['outcome']=='allow'
    assert routing['none_adequate']['outcome']=='STOP_OR_ESCALATE'
    disabled=store.read_json('disabled',results('disabled-journal')['frontier-routing/2'])
    assert disabled['economical_sufficient']['outcome']=='STOP_OR_ESCALATE'
    assert all(c['authorization']['outcome']=='deny' for c in disabled['economical_sufficient']['candidates'] if c['binding']['frontier'])
    usage_events=[e for e in events if e['step_id'].startswith('frontier/usage/')]
    assert len(usage_events)==5
    for event in usage_events:
        assert store.read_json(event['task_id'],event['payload_refs'][0]['ref'])==states(event['task_id']+'-journal','frontier-accounting')[-1]
    projections=rows('projection');dispatches=rows('dispatch-results')
    projection_checks=[]
    assert len(projections)==len(policies)==23
    for policy in policies:
        task=policy['task_id'];op=policy['operation_id']
        projection=next(p for p in projections if p['operation_id']==op)
        i=op.rsplit('/',1)[1]
        task_events=[e for e in events if e['task_id']==task]
        projection_event=next(e for e in task_events if e['step_id']=='frontier/projection/'+i)
        gate_event=next(e for e in task_events if e['step_id']=='frontier/policy/'+i)
        assert task_events.index(projection_event)<task_events.index(gate_event)
        metadata=store.read_json(task,projection_event['payload_refs'][0]['ref'])
        assert 'content' not in metadata and 'raw_context' not in metadata
        if task=='projection-failure':
            assert metadata['outcome']=='failed' and policy['authorized'] is None
        else:
            assert metadata['outcome']=='projected'
            projected=fixtures[task]['projected_context']
            assert metadata['context_digest']==projected['digest']
            assert hashlib.sha256(projected['content'].encode()).hexdigest()!=hashlib.sha256(fixtures[task]['raw_context'].encode()).hexdigest()
        if policy['authorized']:
            assert policy['authorized']['context_digest']==metadata['context_digest']
            assert policy['authorized']['context_ref']==metadata['context_ref']
        projection_checks.append({'task_id':task,'operation_id':op,'status':'PASS','projection_outcome':metadata['outcome'],
                                  'provider_calls':counts[task],'context_digest':metadata.get('context_digest')})
    for task in ('projection-failure','raw-bypass','substitution'):
        assert counts[task]==0
    replaced=next(d for d in dispatches if d['operation_id']=='substitution/2')
    assert replaced['result']['reason_category']=='context_authorization_mismatch'
    assert replaced['result']['status']=='not_executed' and not replaced['result']['provider_invoked']
    # Scan events AND their referenced payloads: no raw fixture data in telemetry.
    for event in events:
        assert_no_raw_fixture(json.dumps(event), fixtures[event['task_id']])
        for ref in event['payload_refs']:
            content=store.read(event['task_id'],ref['ref']).decode()
            assert_no_raw_fixture(content, fixtures[event['task_id']])
    assert before['frontier-projection/2']==after['frontier-projection/2']
    return {'status':'PASS','increment':11,'scope':'projected-context frontier request v3; unchanged authority v2; synthetic only',
        'projection_A_to_F':'PASS','projection_checks':projection_checks,
        'raw_context_absent_from_provider_and_telemetry':True,'projected_digest_checked_before_adapter':True,
        'acceptance_A_to_J':'PASS','routing_evidence':routing_ref,
        'one_dispatch_multiple_model_calls':'illustrative synthetic usage; not live inference',
        'universal_token_cost_caps':False,'provider_billing_integration':False,
        'observed_accounting_not_authority':True,'accounting_recorded_once_after_restart':True,
        'cases':checks,'provider_invocations':len(calls),'executed_synthetic_effects':2,'cloud_inference_calls':0,
        'events':len(events),'same_authorized_request_recovered':True,'committed_effect_not_reexecuted':True,
        'budget_settled_once_after_restart':True,'denied_effect_budget_unchanged':True,
        'next':'STOP before real provider call; Increment 12 not started'}

if __name__=='__main__':
    root=Path(sys.argv[1]);report=verify(root)
    (root/'verification.json').write_bytes(encode(report)+b'\n');print(json.dumps(report,indent=2))
