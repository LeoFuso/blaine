#!/usr/bin/env python3
"""Offline independent verification: events + exact artifacts + Restate journal.

Never used by runtime progression. Task completion evidence is evaluated separately
by the unchanged kernel verifier; this checks the acceptance claims afterwards.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode, validate_spec
from runtime.kernel.events import validate_event
from runtime.kernel.execution import evaluate


def verify(directory):
    def read(name):return json.loads((directory/(name+'.json')).read_text())
    def lines(name):return [json.loads(line) for line in (directory/(name+'.jsonl')).read_text().splitlines()]
    def journal_results(name):
        rows=read(name)['rows'];commands={};results={}
        for row in rows:
            entry=json.loads(row['entry_json'])
            if row['entry_type']=='Command: Run':commands[entry['Command']['Run']['completion_id']]=row['name']
            if row['entry_type']=='Notification: Run':
                item=entry['Notification']['Completion']['Run']
                if 'Success' in item['result']:results[item['completion_id']]=json.loads(bytes(item['result']['Success']))
        return {commands[k]:v for k,v in results.items() if k in commands}
    events=lines('events');assert events
    for event in events:validate_event(event)
    ids=[e['event_id'] for e in events];assert len(ids)==len(set(ids))
    state=read('state');child_state=read('child-state');execution=read('execution')
    assert execution['status']=='EXECUTION_COMPLETED_PENDING_INDEPENDENT_VERIFICATION'
    store=ArtifactStore(directory/'artifacts');details=[]
    for current,name in ((state,'parent'),(child_state,'child')):
        task=current['task_id'];selected=[e for e in events if e['task_id']==task]
        assert selected and len({e['run_id'] for e in selected})==1
        assert selected[0]['event_type']=='task.started' and selected[-1]['event_type']=='completion.finished'
        assert selected[-1]['outcome']=='COMPLETED'
        for previous,event in zip(selected,selected[1:]):assert event['causation_event_id']==previous['event_id']
        for event in selected:
            assert event['producer']['kind']=='deterministic_application'
            assert event['producer']['component'] and event['producer']['code_revision']
            assert 'trace_id' not in event and 'span_id' not in event
            assert event['run_id']!='' and event['run_id']!=task
            for item in event['payload_refs']:store.read(task,item['ref'])
            for ref in event['references'].get('artifact_ids',[]):store.read(task,ref)
        kinds=[e['event_type'] for e in selected]
        for kind in ('task.started','cognition.decided','policy.evaluated','capability.finished','artifact.produced','verifier.evaluated','completion.finished'):assert kind in kinds
        # At least one complete semantic operation, linked to a prior admitted decision.
        for effect in (e for e in selected if e['event_type']=='capability.finished'):
            prior=next(e for e in selected if e['event_id']==effect['causation_event_id'])
            assert prior['event_type']=='policy.evaluated' and prior['outcome']=='allow'
            assert prior['references']['decision_id']==effect['references']['capability_call_id']
        satisfied=[e for e in selected if e['event_type']=='verifier.evaluated' and e['outcome']=='satisfied']
        assert len(satisfied)==1
        later=selected[selected.index(satisfied[0])+1:]
        assert not any(e['event_type'] in ('cognition.decided','capability.finished') for e in later)
        spec=validate_spec(store.read_json(task,current['spec_ref']))
        assert evaluate(spec,current,store)['payload']['outcome']=='satisfied'
        assert read(name+'-result')==store.read_json(task,current['result_ref'])
        assert read(name+'-result')['payload']['outcome']=='COMPLETED'
        journal=journal_results(name+'-journal')
        for event in selected:
            assert journal['event-prepare/'+event['step_id']]==event
            assert journal['event-publish/'+event['step_id']]=='published'
        details.append({'task_id':task,'run_id':selected[0]['run_id'],'events':len(selected),'event_types':dict(Counter(kinds)),
            'result_bytes':len(encode(read(name+'-result'))),'independent_completion':'satisfied'})
    worker=lines('worker');assert len(worker)==1 and worker[0]['returncode']==0
    assert worker[0]['report']['outcome']=='PASS' and worker[0]['report']['focused_tests']==87
    assert 'Ran 87 tests' in worker[0]['test_output'] and worker[0]['test_output'].rstrip().endswith('OK')
    for path,digest in worker[0]['report']['implementation'].items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==digest
    assert store.read(state['task_id'],state['artifacts']['report'])==encode(worker[0]['report'])
    assert store.read(child_state['task_id'],child_state['artifacts']['report'])==encode(worker[0]['report'])
    before=journal_results('journal-before-crash');after=journal_results('child-journal')
    assert before['capability/2']==after['capability/2']
    assert 'event-prepare/capability/2' in before and 'event-publish/capability/2' not in before
    lost=read('recovery')['event_id'];assert ids.count(lost)==1
    effects=lines('effects');assert len([x for x in effects if x['request']['payload']['capability']=='worker.run'])==1
    worker_event=next(e for e in events if e['event_type']=='capability.finished' and e['payload']['capability']=='worker.run')
    assert worker_event['references']['worker_session_id']==worker[0]['operation_id']+'-verification'
    turns=lines('cognition');parent_turns=[x for x in turns if x['packet']['payload']['task_id']==state['task_id']]
    assert len(parent_turns)==3 and len([x for x in turns if x['packet']['payload']['task_id']==child_state['task_id']])==2
    child_observation=parent_turns[1]['packet']['payload']['observations'][0]
    assert child_observation==read('child-result') and 'history' not in child_observation['payload']
    assert parent_turns[2]['packet']['payload']['specialist']=='specialist'
    outage=read('outage-state');assert outage['lifecycle']=='COMPLETED'
    assert evaluate(validate_spec(store.read_json(outage['task_id'],outage['spec_ref'])),outage,store)['payload']['outcome']=='satisfied'
    assert not any(e['task_id']==outage['task_id'] for e in events)
    outage_journal=journal_results('outage-journal')
    assert all(v=='publication_failed' for k,v in outage_journal.items() if k.startswith('event-publish/'))
    assert 'SECRET_FIXTURE_DO_NOT_EMIT' not in (directory/'events.jsonl').read_text()
    assert read('processes')['all_stopped']
    return {'status':'PASS','tasks':details,'model_calls':0,'worker_test_executions':1,
        'worker_packet_bytes':worker[0]['packet_bytes'],'cognitive_packet_bytes':[x['packet_bytes'] for x in turns],
        'events':len(events),'maximum_event_bytes':max(len(encode(e)) for e in events),
        'replay_lost_ack_deduplicated':True,'no_repeated_committed_worker_effect':True,
        'no_authority_dependency_on_telemetry':True,'parent_receives_bounded_child_result':True,
        'trace_context':'absent, not fabricated','classification_guard':'closed metadata; no SECRET payload class accepted',
        'sink':'JSONL acceptance/local forensics only; no platform backend selected'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);a=p.parse_args()
    report=verify(a.evidence);(a.evidence/'verification.json').write_bytes(encode(report)+b'\n');print(json.dumps(report,indent=2))
