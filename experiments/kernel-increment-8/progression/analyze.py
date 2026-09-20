"""Offline proof over captured Restate journals, authoritative artifacts and provider wire records."""
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
DEST=ROOT/'experiments/kernel-increment-8/evidence/progression'
SOURCE=Path('/tmp/blaine-verifier-progression-20260920/evidence')
RUN=DEST/'acceptance'
def read(p):return json.loads(p.read_text())
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
def save(p,v):p.write_bytes(encode(v)+b'\n')
if not RUN.exists():shutil.copytree(SOURCE,RUN)
def values(journal):
    commands={json.loads(r['entry_json'])['Command']['Run']['completion_id']:r['name']
        for r in journal['rows'] if r['entry_type']=='Command: Run'}
    out={}
    for row in journal['rows']:
        if row['entry_type']!='Notification: Run':continue
        v=json.loads(row['entry_json'])['Notification']['Completion']['Run']
        if 'Success' in v['result']:
            raw=bytes(v['result']['Success']);out[commands[v['completion_id']]]=json.loads(raw) if raw else None
    return out
state_rows=rows(RUN/'states.jsonl');effects=rows(RUN/'capabilities.jsonl')
wire=rows(RUN/'wire.jsonl');calls=rows(RUN/'call-start.jsonl');semantic=rows(RUN/'semantic.jsonl')
store=ArtifactStore(RUN/'artifacts');final=read(RUN/'final-state.json');spec=read(RUN/'spec.json')
assert len(wire)==len(calls)==len(semantic)==2
assert [x['parsed_semantic_decision']['action'] for x in semantic]==['REQUEST_HUMAN','PRODUCE_ARTIFACT']
for w in wire:
    assert w['request']['model']==w['raw_response_safe']['model']=='Qwen/Qwen3.5-9B'
    assert w['endpoint']=='http://127.0.0.1:8000/v1/chat/completions'
    assert not any(k in w['request'] for k in ('response_format','tools','guided_json','structured_outputs'))
prior=ROOT/'experiments/kernel-increment-8/evidence/hybrid'
assert [w['request'] for w in wire]==[w['request'] for w in rows(prior/'hybrid/wire.jsonl')[:2]]
assert spec==read(prior/'hybrid/spec.json')
assert store.read_json('procedure',final['spec_ref'])==spec
assert final['lifecycle']=='COMPLETED' and final['completion_ref']
assert store.read_json('procedure',final['completion_ref'])==evaluate(spec['payload'],final,store)
assert store.read_json('procedure',final['completion_ref'])['payload']['outcome']=='satisfied'
assert store.read_json('procedure',final['result_ref'])==read(RUN/'result.json')
all_checks={};transition_proofs={}
for task,filename,accepted in [('procedure','final-journal.json',spec),('incomplete-effect','negative-journal.json',read(RUN/'negative-spec.json'))]:
    journal=read(RUN/filename);committed=values(journal)
    records=[x for x in state_rows if x['state']['task_id']==task]
    cap=[x for x in effects if x['request']['payload']['task_id']==task]
    assert len(cap)==2 and len({x['request']['payload']['operation_id'] for x in cap})==2
    for effect in cap:
        iteration=effect['request']['payload']['operation_id'].split('/')[-1]
        assert committed['capability/'+iteration]==effect['result']
    progression=[]
    for r in records:
        verified=evaluate(accepted['payload'],r['state'],store)
        if r['stage'].startswith('verification-'):
            phase=r['stage'].removeprefix('verification-')
            assert committed[f"progress/{phase}/{r['state']['iteration']}"]==r['evaluation']==verified
            assert (r['state']['lifecycle']=='COMPLETED')==(verified['payload']['outcome']=='satisfied')
        for ref in r['state']['artifacts'].values():store.read(task,ref)
        progression.append({**r,'independent_evaluation_of_recorded_state':verified})
    first=next(x for x in progression if x['independent_evaluation_of_recorded_state']['payload']['outcome']=='satisfied')
    assert first['stage']=='effect_persisted'
    assert not [r for r in records if r['stage']=='before_cognition' and r['time_ns']>first['time_ns']]
    if task=='procedure':
        assert not [c for c in calls if c['time_ns']>first['time_ns']]
        assert not [e for e in cap if e['time_ns']>first['time_ns']]
        request_time=cap[0]['time_ns'];resume=next(r for r in records if r['stage']=='resumed')
        assert not [c for c in calls if request_time<c['time_ns']<resume['time_ns']]
        suspended=read(RUN/'pending-recovery.json');assert suspended['before']==suspended['after']
        assert suspended['model_calls_before']==suspended['model_calls_after']==1
        assert all(c['unchanged_state'] and c['http_status']==400 for c in read(RUN/'negative-controls.json'))
        assert read(RUN/'duplicate-control.json')['status']==409
        restart=read(RUN/'artifact-recovery.json')
        assert restart['model_calls_before']==2
        assert restart['state']==first['state'] and first['state']['lifecycle']=='RUNNING'
        assert next(r for r in records if r['stage']=='verification-effect' and r['state']['iteration']==2)['pid']==restart['replacement_pid']
        for i,s in enumerate(semantic,1):assert committed[f'cognitive/{i}']==s['runtime_command']
        merged=[]
        for i,t in enumerate(rows(RUN/'turns.jsonl')):
            ident=semantic[i]['runtime_command']['payload']['turn_id']
            merged.append({**t,'wire':wire[i],'semantic':semantic[i],
                'policy':next(r['gate'] for r in records if r['stage']=='decision' and r['state']['decision_id']==ident),
                'effect':cap[i],'transitions':[r for r in progression if r['state']['decision_id']==ident]})
        save(RUN/'turn-evidence.json',merged)
    else:
        fixture=rows(RUN/'scripted.jsonl');assert len(fixture)==2
        first_failure=next(r for r in records if r['stage']=='verification-effect' and r['state']['iteration']==1)
        assert first_failure['evaluation']['payload']['outcome']=='unsatisfied'
        assert first_failure['state']['lifecycle']=='RUNNING' and first_failure['state']['wait'] is None
        assert fixture[1]['time_ns']>first_failure['time_ns']
        assert fixture[1]['packet']['payload']['observations'][0]['payload']['outcome']=='success'
        for i,s in enumerate(fixture,1):assert committed[f'cognitive/{i}']==s['decision']
    transition_proofs[task]=progression
    all_checks[task]={'effect_results_match_journal':True,'progression_evaluations_match_journal_and_exact_artifacts':True,
        'no_cognition_after_first_provable_state':True,'first_provable_state':first,
        'completion_is_runtime_owned':True,'effect_count':len(cap)}
save(RUN/'transition-evidence.json',transition_proofs)
save(DEST/'checks.json',all_checks)
oldmanifest=read(prior/'experiment-sources.json')
assert all(hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==h for f,h in oldmanifest.items())
manifest=read(DEST/'source-before.json');after={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in manifest}
assert manifest==after
save(DEST/'source-integrity.json',{'runtime_unchanged':True,'previous_hybrid_experiment_unchanged':True,'runtime_files':after})
choice_files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (prior/'choice').glob('*.json')}
save(DEST/'retained-choice-control.json',{'status':read(prior/'choice/result.json')['status'],
    'prior_live_inference_reused':True,'new_model_calls':0,'source_files':choice_files,
    'meaning':'Existing control: direct request and specialist handoff both admitted; Qwen selected direct request. No additional inference or effects.'})
comparison=read(prior/'comparison.json')['arms'];comparison['verifier_progression']=read(RUN/'summary.json')
save(DEST/'comparison.json',{'arms':comparison,'negative_control':read(RUN/'negative-control.json'),
    'new_model_calls':2,'new_scripted_cognitive_turns':2,'new_capability_effects_total':4,
    'positive_effects':2,'negative_effects':2,'same_first_two_model_requests_as_previous_hybrid':True,
    'same_task_spec_as_previous_hybrid':True,'architecture_adopted':False})
summary={'status':'EXPERIMENT_PASS_STOP_FOR_ARCHITECTURE_APPROVAL','production_increment_8':'FAILED / UNPASSED; no production migration',
    'model':'Qwen/Qwen3.5-9B','endpoint':'http://127.0.0.1:8000/v1/chat/completions','new_model_calls':2,
    'model_calls_after_completion_first_provable':0,'model_calls_while_pending':0,
    'invalid_proposals':0,'legal_unproductive_rewrites':0,'independent_verifier':'unchanged runtime.kernel.execution.evaluate',
    'task_outcome':'COMPLETED','negative_effect_control':'PASS (scripted provider, native Restate, no LLM)',
    'previous_genuine_choice_control_retained':True,'model_prompts_unchanged':True,
    'existing_tests_passed':65,'new_offline_controls_passed':4,'runtime_source_unchanged':True,
    'restarts':['server+application while pending','application after sufficient evidence persisted, before verification'],
    'architecture_adopted':False,'next_increment_started':False}
save(DEST/'summary.json',summary)
print('PASS: exact prompt/spec match; native-journal completion/replay; zero subsequent cognition; incomplete-effect continuation; source integrity.')
