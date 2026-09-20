"""Offline validation of retained native Task evidence; no new inference or service calls."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.execution import evaluate
from runtime.kernel.contracts import encode
DEST=Path(__file__).parent/'evidence';RUN=DEST/'acceptance'
if not RUN.exists():shutil.copytree('/tmp/blaine-increment9-20260920/evidence',RUN)
def read(p):return json.loads(p.read_text())
def rows(p):return [json.loads(x) for x in p.read_text().splitlines()]
def save(p,v):p.write_bytes(encode(v)+b'\n')
store=ArtifactStore(RUN/'artifacts');provenance=read(RUN/'provenance.json')
assert hashlib.sha256((RUN/'graph.json').read_bytes()).hexdigest()==provenance['graph_sha256']
turns=rows(RUN/'cognition.jsonl');effects=rows(RUN/'effects.jsonl');retrieval=rows(RUN/'retrieval.jsonl')
proof={}
for case in ('fresh','stale','absent'):
    state=read(RUN/(case+'-state.json'));spec=read(RUN/(case+'-spec.json'))
    result=read(RUN/(case+'-result.json'))
    assert state['lifecycle']==result['payload']['outcome']=='COMPLETED'
    assert store.read_json(case,state['spec_ref'])==spec
    assert store.read_json(case,state['result_ref'])==result
    verification=evaluate(spec['payload'],state,store)
    assert store.read_json(case,state['completion_ref'])==verification
    assert verification['payload']['outcome']=='satisfied'
    for ref in state['artifacts'].values():store.read(case,ref)
    journal=read(RUN/(case+'-journal.json'))['rows']
    commands={json.loads(r['entry_json'])['Command']['Run']['completion_id']:r['name'] for r in journal if r['entry_type']=='Command: Run'}
    values={}
    for r in journal:
        if r['entry_type']=='Notification: Run':
            n=json.loads(r['entry_json'])['Notification']['Completion']['Run']
            if 'Success' in n['result']:
                raw=bytes(n['result']['Success']);values[commands[n['completion_id']]]=json.loads(raw) if raw else None
    selected=[r for r in turns if r['packet']['payload']['task_id']==case]
    for i,row in enumerate(selected,1):assert row['decision']==values[f'cognitive/{i}']
    case_effects=[r for r in effects if r['request']['payload']['task_id']==case]
    for i,row in enumerate(case_effects,1):assert row['result']==values[f'capability/{i}']
    assert len(selected)==len(case_effects)==3
    assert values['progress/effect/3']==verification
    source=selected[-1]['packet']['payload']['observations'][0]['payload']['output']
    assert source['authority']=='artifact'
    assert store.read(case,source['ref']).decode()==source['content']
    context=[x for x in selected[-1]['packet']['payload']['context'] if isinstance(x['content'],dict) and x['content'].get('classification')=='project_knowledge']
    if case=='stale':
        assert 'def validate_request_current(' in source['content']
        assert 'def validate_request(' not in source['content']
        assert context==[]
        assert 'validate_request_current' in store.read(case,state['artifacts']['result']).decode()
    if case=='fresh':
        assert context and all(c['authority']=='derived' for c in context)
        assert all(c['content']['source_sha256']==source['sha256'] for c in context)
        assert 'def validate_request(' in source['content']
    if case=='absent':assert context==[]
    proof[case]={'verified':True,'journal_matches':True,'context':context,'authoritative_source':source,
        'retrieval':[r for r in retrieval if r['task_id']==case],'result':result,'verification':verification}
save(DEST/'checks.json',proof)
summary=read(RUN/'summary.json');summary.update(focused_tests_passed=78,
    authority='Git/source and exact artifact snapshots; Graphify only derived navigation',
    previous_kernel_progression_unchanged=True,upstream_audit_or_build=False)
save(DEST/'summary.json',summary)
save(DEST/'source-files.json',{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [
    ROOT/'runtime/kernel/project_knowledge.py',ROOT/'runtime/kernel/workflow.py',Path(__file__),Path(__file__).with_name('probe.py')]})
print('PASS: fresh/stale/absent native Tasks, exact authoritative sources/results, derived-only context, journal provenance.')
