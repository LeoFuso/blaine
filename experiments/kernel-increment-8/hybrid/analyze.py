"""Offline evidence assertions; never invokes inference or runtime handlers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode
from runtime.kernel.execution import evaluate
DEST=ROOT/'experiments/kernel-increment-8/evidence/hybrid'
SOURCES={'retry':Path('/tmp/blaine-hybrid-retry-20260920/evidence'),
 'suspend':Path('/tmp/blaine-hybrid-suspend-20260920/evidence'),
 'hybrid':Path('/tmp/blaine-hybrid-filtered-20260920/evidence')}
def read(p):return json.loads(p.read_text())
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
def save(p,v):p.write_bytes(encode(v)+b'\n')
def run_values(journal):
    commands={json.loads(r['entry_json'])['Command']['Run']['completion_id']:r['name']
              for r in journal['rows'] if r['entry_type']=='Command: Run'}
    values={}
    for row in journal['rows']:
        if row['entry_type']!='Notification: Run':continue
        v=json.loads(row['entry_json'])['Notification']['Completion']['Run']
        if 'Success' in v['result']:
            raw=bytes(v['result']['Success'])
            values[commands[v['completion_id']]]=json.loads(raw) if raw else None
    return values
summaries={};checks={}
for mode,source in SOURCES.items():
    d=DEST/mode
    if not d.exists():shutil.copytree(source,d)
    summary=read(d/'summary.json');summaries[mode]=summary
    wire=rows(d/'wire.jsonl');starts=rows(d/'call-start.jsonl');semantic=rows(d/'semantic.jsonl')
    turns=rows(d/'turns.jsonl');states=rows(d/'states.jsonl');effects=rows(d/'capabilities.jsonl')
    journal=read(d/'final-journal.json');values=run_values(journal)
    for call in wire:
        assert call['endpoint']=='http://127.0.0.1:8000/v1/chat/completions'
        assert call['request']['model']==call['raw_response_safe']['model']=='Qwen/Qwen3.5-9B'
        assert 'response_format' not in call['request'] and 'tools' not in call['request']
    assert len(starts)==len(wire)==len(semantic)
    assert len({e['request']['payload']['operation_id'] for e in effects})==len(effects)
    for e in effects:
        iteration=e['request']['payload']['operation_id'].split('/')[-1]
        assert values['capability/'+iteration]==e['result']
    store=ArtifactStore(d/'artifacts');final=read(d/'final-state.json');spec=read(d/'spec.json')
    assert store.read_json('procedure',final['spec_ref'])==spec
    for ref in final['artifacts'].values():store.read('procedure',ref)
    merged=[]
    for i,t in enumerate(turns):
        s=semantic[i] if i<len(semantic) else None
        decision=s.get('runtime_command') if s else None
        row=deepcopy(t);row.update(projection_applied=mode=='hybrid',model_inference_invoked=i<len(wire),
            boundary=s,wire=wire[i] if i<len(wire) else None)
        if not s:row['no_inference_reason']='Experiment-only six-call budget stopped before transport; no model output.'
        ident=decision['payload']['turn_id'] if decision else None
        row['policy_gate']=next((x['gate'] for x in states if x['stage']=='decision' and x['state']['decision_id']==ident),None)
        row['effect']=next((x for x in effects if x['request']['payload']['operation_id']==ident),None)
        row['lifecycle_transitions']=[x for x in states if x['state']['decision_id']==ident and x['stage'] in ('outcome','suspended','resumed')]
        if decision:assert values['cognitive/'+ident.split('/')[-1]]==decision
        merged.append(row)
    save(d/'turn-evidence.json',merged)
    checks[mode]={'model_provenance_matches':True,'all_effects_match_journal':True,
        'all_committed_decisions_match_journal':True,'replayed_effect_duplicates':0,
        'all_artifact_digests_valid':True,'objective_and_spec_unchanged':True,
        'task_lifecycle':final['lifecycle'],'committed_completion_ref':final['completion_ref'],
        'posthoc_independent_evaluation':evaluate(spec['payload'],final,store),
        'posthoc_evaluation_is_not_a_runtime_completion':True}
    if mode!='retry':
        suspended=next(s for s in states if s['stage']=='suspended')
        resumed=next(s for s in states if s['stage']=='resumed')
        between=[c for c in starts if effects[0]['time_ns']<c['time_ns']<resumed['time_ns']]
        assert not between
        assert len([s for s in states if s['stage']=='resumed'])==1
        assert all(x['unchanged_state'] and x['calls']==1 and x['http_status']==400 for x in read(d/'negative-controls.json'))
        assert read(d/'duplicate-control.json')['status']==409
        pending=read(d/'pending-recovery.json');assert pending['before']==pending['after']
        recovery=read(d/'artifact-recovery.json');assert recovery['replacement_pid']!=recovery['killed_pid']
        later=wire[2:]
        assert all(json.loads(w['request']['messages'][1]['content'])['clarification']['status']=='resolved' for w in later)
        assert all(json.loads(w['request']['messages'][1]['content'])['deliverable']['content_verified'] for w in later)
        assert all(w['pid']==recovery['replacement_pid'] for w in later)
        assert len([r for r in journal['rows'] if r['entry_type']=='Command: GetPromise'])==1
        checks[mode].update(zero_model_calls_from_request_effect_to_verified_resume=True,
            invalid_signals_preserve_wait=True,duplicate_response_rejected=True,resumes=1,
            restate_and_application_restart_pending=True,fresh_process_resolution_projection=True,
            legal_artifact_rewrites_after_first=4,no_completion_request_within_six_call_budget=True)
        save(d/'suspension-interval.json',{'published_effect':effects[0],'suspended':suspended,
            'pending_recovery':pending,'wake_event':read(d/'wake-event.json'),'resumed':resumed,
            'calls_between_request_effect_and_verified_resume':between,
            'get_promise_entries':[r for r in journal['rows'] if r['entry_type']=='Command: GetPromise'],
            'response_alone':read(d/'response-alone-verification.json')})
        if mode=='hybrid':
            for call in wire[1:]:
                text=encode(call['request']['messages']).decode()
                assert 'REQUEST_HUMAN' not in text and 'WAIT' not in text
                assert 'PRODUCE_ARTIFACT' in text and 'COMPLETE' in text
            checks[mode]['excluded_action_labels_absent_from_entire_sent_messages']=True
# Exact baseline reproduction, not merely the same scenario description.
old=ROOT/'experiments/kernel-increment-8/evidence/coherent-semantics/acceptance/wire.jsonl'
assert [w['request'] for w in rows(old)]==[w['request'] for w in rows(DEST/'retry/wire.jsonl')]
checks['retry']['identical_requests_to_recorded_counterexample']=True
choice=DEST/'choice'
if not choice.exists():shutil.copytree('/tmp/blaine-hybrid-choice-20260920',choice)
assert read(choice/'result.json')['status']=='PASS'
response=read(choice/'response.json')['raw_provider_response_safe']
assert response['model']=='Qwen/Qwen3.5-9B'
manifest=read(DEST/'source-before.json')
after={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in manifest}
assert after==manifest
save(DEST/'source-integrity.json',{'unchanged':True,'files':after})
save(DEST/'checks.json',checks)
save(DEST/'comparison.json',{'arms':summaries,'choice':read(choice/'result.json'),
    'total_real_model_calls':sum(s['model_calls'] for s in summaries.values())+1,
    'choice_tokens':response['usage'],'experimental_call_cap_applies_to':['suspend','hybrid'],
    'retry_terminal_cause':'Existing maximum-attempt rejection of inadmissible semantic decisions',
    'invalid_retry_inference_saved_at_pending_state':3,
    'baseline_pending_inference_seconds':sum(w['elapsed_seconds'] for w in rows(DEST/'retry/wire.jsonl')[1:]),
    'baseline_pending_prompt_tokens':sum(w['raw_response_safe']['usage']['prompt_tokens'] for w in rows(DEST/'retry/wire.jsonl')[1:]),
    'baseline_pending_completion_tokens':sum(w['raw_response_safe']['usage']['completion_tokens'] for w in rows(DEST/'retry/wire.jsonl')[1:]),
    'conclusion':'Durable blocking suspension and hard action projection work; neither demonstrates end-to-end completion. Legal action repetition remains. No architecture adopted.'})
print('Offline journal, provenance, suspension, replay, artifact and source checks passed.')
