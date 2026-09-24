"""Independent retained-evidence oracle. Does not import receiver or runner."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

D=Path(__file__).resolve().parent
ROOT=D.parents[1]


def load(p): return json.loads(Path(p).read_text())
def encoded(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def evaluate(directory):
    failures=[]; checks=0; content_hits=[]; metadata_hits=[]; sizes=[]
    def check(ok,label):
        nonlocal checks
        checks+=1
        if not ok: failures.append(label)
    fixture=load(D/'cases.json'); base=load(D/'state.json')
    frozen=load(D/'evidence/fixture-freeze.json')
    for name,h in frozen['sha256'].items(): check(digest(D/name)==h,'fixture hash '+name)
    registration=load(D/'evidence/preregistration.json')
    for name,h in registration['sha256'].items(): check(digest(ROOT/name)==h,'implementation/source hash '+name)
    data=load(directory/'results.json'); proof=load(directory/'process-attestations.json')
    proof_by_id={p['operation']:p for p in proof}
    check(len(proof_by_id)==len(proof),'unique process operations')
    check(len(data['cases'])==12,'exactly 12 primary cases')
    check(Counter(c['group'] for c in data['cases'])=={
        'LOCAL_HANDOFF':4,'CHECKPOINT_RESUME':4,'SECOND_PROCESS':4},'four per group')
    check([c['id'] for c in data['cases']]==[c['id'] for c in fixture],'case identity/order')
    allowed_pairs={('USER_DECLARATION','DECLARED'),('AGENT_OBSERVATION','UNVERIFIED'),
                   ('VERIFIED_OUTCOME','VERIFIED_SUCCESS'),('VERIFIED_OUTCOME','VERIFIED_FAILURE')}

    def visibility(state):
        # Independent lineage/policy calculation; no SUT import or summary field.
        b=state['bindings']['execution-main']; parents={n['id']:n for n in state['nodes']}
        lineage=set(); node=b['context_id']
        while node is not None:
            if node in lineage: raise ValueError('invalid trusted structure')
            lineage.add(node); row=parents[node]
            node=row['parent_id'] if row['inherit_parent'] else None
        return [r for r in state['entries'] if r['context_id'] in lineage
                and r['domain'] in state['policy']['grants'][b['domain']]
                and r['id'] not in state['policy']['deny_ids']]

    def exported(label,e,state,expected_status,expected_ids,allowed=None):
        r=e['response']; raw=e['stdout']; sizes.append(len(raw.encode()))
        check(e['exit_code']==0,label+' receiver exit')
        check(e['stderr']=='',label+' stderr empty')
        check(raw==encoded(r)+'\n',label+' exact serialized output')
        check(e['response_bytes']==len(raw.encode())<=2048,label+' entire response budget')
        check(set(r)=={'status','entries','partial','receipt','diagnostic'},label+' closed response')
        check(r['diagnostic']=={'code':r['status']},label+' status-only diagnostics')
        check(r['status']==expected_status,label+' state')
        check(sorted(x['id'] for x in r['entries'])==sorted(expected_ids),label+' exact visibility')
        canonical={row['id']:row for row in state['entries']}
        for row in r['entries']:
            check(row==canonical.get(row['id']),label+' source and provenance '+row['id'])
            check((row.get('provenance'),row.get('semantic_status')) in allowed_pairs,label+' provenance pair')
        if expected_status in ('SUCCESS','EMPTY'):
            check(r['receipt'] is not None and r['receipt']['context_id']==state['bindings']['execution-main']['context_id'],label+' current binding')
        else:
            check(r['receipt'] is None and r['entries']==[],label+' non-leaking rejection')
        permitted=set(expected_ids if allowed is None else allowed)
        # Independently scan all caller fields (including stdout, diagnostics, receipts).
        # Each export is judged under its own receiving state, not a later policy.
        text=encoded(e)
        for row in state['entries']:
            if row['id'] not in permitted:
                for kind,value in [('content',row['content']),('metadata',row['id'])]:
                    if value and value in text:
                        (content_hits if kind=='content' else metadata_hits).append({'export':label,'literal':value})
        for literal in ['RAW_SUCCESS_LOG_CANARY','RAW_FAILURE_LOG_CANARY']:
            if literal in text: content_hits.append({'export':label,'literal':literal})
        for literal in ['task-x','employer-x','binding-evidence','private_audit']:
            if literal in text: metadata_hits.append({'export':label,'literal':literal})
        if 'process' in e:
            p=e['process']; att=proof_by_id.get(p['operation'],{})
            check(all(p[k] is True for k in ['separate_process','child_report_matches_popen','parent_pid_matches','writer_exited_before_return']),label+' process flags')
            check(bool(att) and att['child']['pid']==att['launched_pid']!=att['parent_pid']
                  and att['child']['ppid']==att['parent_pid'],label+' actual independent PID evidence')

    def current_state(f):
        s=json.loads(encoded(base))
        if f['state_change']=='NARROW_POLICY':
            s['policy_revision']='P2'; s['policy']['deny_ids']=['old-rule']
        elif f['state_change']=='REPARENT':
            s['topology_revision']='T2'
            for n in s['nodes']:
                if n['id']=='task-main': n['parent_id']='project-new'
        elif f['state_change']=='MISSING_EVIDENCE': s['current_evidence']={}
        return s

    case_states={}
    for c,f in zip(data['cases'],fixture):
        state=current_state(f); case_states[c['id']]=state
        check(c['trusted_state']==state,c['id']+' exact trusted fixture')
        check({k:v for k,v in c['envelope'].items() if k!='claims'}==
              {k:v for k,v in f['envelope'].items() if k!='claims'},c['id']+' exact transfer refs')
        if c['group']=='CHECKPOINT_RESUME':
            check('historical_packet' in c['envelope']['claims'],c['id']+' persisted historical packet')
            check(c['phases'][0]['stage']=='before_checkpoint',c['id']+' checkpoint writer')
            check('process' in c['phases'][0]['export'],c['id']+' checkpoint writer actually exited')
        else: check(c['envelope']==f['envelope'],c['id']+' exact envelope')
        phases={p['stage']:p for p in c['phases']}
        for p in c['phases']:
            prior=p['stage'] in ('before_checkpoint','prior_success')
            expected_ids=fixture[0]['expected_ids'] if prior else f['expected_ids']
            expected_status='SUCCESS' if prior else f['expected_status']
            st=base if prior else state
            exported(c['id']+'/'+p['stage'],p['export'],st,expected_status,expected_ids)
            if expected_status=='SUCCESS':
                check(sorted(x['id'] for x in visibility(st))==sorted(expected_ids),c['id']+' independent lineage/security/policy oracle')
                check(p['export']['response']['receipt']['trace_id']==('trace-main' if prior else f['envelope']['trace_id']),c['id']+' correlation preserved')
                check(p['export']['response']['receipt']['parent_operation_id']=='op-origin',c['id']+' parent operation preserved')
            if c['group']=='SECOND_PROCESS' or c['group']=='CHECKPOINT_RESUME':
                check('process' in p['export'],c['id']+' separate receiver/writer present')
        check(phases['received']['export']['response']==phases['same_state_replay']['export']['response'],c['id']+' same-state replay')
        if c['id'] in ('B2','C3'):
            check('old-rule' not in encoded(phases['received']['export']),c['id']+' current P2 beats snapshot')
        if c['id']=='B3':
            check('new-rule' in encoded(phases['received']['export']) and 'old-rule' not in encoded(phases['received']['export']),c['id']+' current T2 beats lineage')
        if c['id']=='C4': check(phases['prior_success']['export']['response']['status']=='SUCCESS' and phases['received']['export']['response']['status']=='UNAVAILABLE','past success not authority')

    probe_by_name={p['name']:p for p in data['probes']}
    required_probes={'empty','scoped-write','continuous-verifier','write-visibility-project-old',
                     'write-visibility-attempt','malformed-json','duplicate-field-json','budget','budget-marker-edge'}
    required_probes |= {'direct-'+x for x in ['protected-x','protected-root','sibling-private','descendant-private','missing-id']}
    required_probes |= {'write-forged-'+x for x in ['target_context','provenance','destination_context']}
    required_probes |= {'invalid-'+x for x in ['policy_ref','topology_ref','binding_ref','execution_id']}
    required_probes |= {'hidden-topology-'+x for x in ['missing-parent','cycle','duplicate-id','self-parent']}
    required_probes |= {'policy-'+x for x in ['unavailable','malformed','unknown','contradictory']}
    check(set(probe_by_name)==required_probes,'supplemental probe coverage')
    for name,p in probe_by_name.items():
        state=p['trusted_state']; e=p['export']; ids=[]; status='INVALID_CONTEXT'; allowed=None
        if name=='empty': status='EMPTY'; allowed=[r['id'] for r in visibility(state)]
        elif name=='scoped-write':
            status='SUCCESS'; ids=['task-main::note-1']
            state=json.loads(encoded(state))
            state['entries'].append(dict(id='task-main::note-1',context_id='task-main',domain='personal',content='Post-start scoped observation.',provenance='AGENT_OBSERVATION',semantic_status='UNVERIFIED'))
            allowed=[r['id'] for r in visibility(state)]
        elif name in ('continuous-verifier','write-visibility-project-old','write-visibility-attempt'):
            status='SUCCESS'; ids=sorted(r['id'] for r in visibility(state))
        elif name.startswith(('direct-','write-forged-')) or name in ('invalid-binding_ref','invalid-execution_id'): status='DENIED'
        elif name=='policy-unavailable': status='UNAVAILABLE'
        elif name=='budget-marker-edge':
            status='SUCCESS'; allowed=['edge']
            check(e['response']['partial'] is True and e['response']['entries']==[], 'full marker accounting at boundary')
        elif name=='budget':
            status='SUCCESS'; allowed=[r['id'] for r in visibility(state)]
            # Reconstruct deterministic complete-packet selection from authoritative rows.
            trial={'status':'SUCCESS','entries':[],'partial':False,'diagnostic':{'code':'SUCCESS'},
                   'receipt':{'context_id':'task-main','trace_id':'trace-main','parent_operation_id':'op-origin'}}
            for row in sorted(visibility(state),key=lambda r:r['id']):
                trial['entries'].append(row)
                if len((encoded(trial)+'\n').encode())>2048: trial['entries'].pop()
            ids=[r['id'] for r in trial['entries']]
            check(e['response']['partial'] is True and len(ids)<len(allowed),'budget actually selects/truncates')
        exported('probe/'+name,e,state,status,ids,allowed)
    for key in ['protected-x','protected-root','sibling-private','descendant-private']:
        check(probe_by_name['direct-'+key]['export']['response']==probe_by_name['direct-missing-id']['export']['response'],'ID probe indistinguishable '+key)
    check('task-main::note-1' not in encoded(probe_by_name['write-visibility-project-old']['export']),'ordinary write never promotes')
    check('task-main::note-1' in encoded(probe_by_name['continuous-verifier']['export']),'later process re-queries new observation')
    # Reconstruct exported evidence; no internal envelope/state/audit in the public projection.
    expected_exports=[dict(case=c['id'],stage=p['stage'],state_change=p['state_change'],export=p['export'])
                      for c in data['cases'] for p in c['phases']]
    expected_exports += [dict(probe_number=i,export=p['export']) for i,p in enumerate(data['probes'])]
    check(load(directory/'exports.json')==expected_exports,'complete caller export projection')
    check(not content_hits,'zero forbidden content')
    check(not metadata_hits,'zero forbidden metadata')
    return dict(status='PASS' if not failures else 'FAIL',checks=checks,failures=failures,
                primary_cases=len(data['cases']),groups=dict(Counter(c['group'] for c in data['cases'])),
                max_response_bytes=max(sizes),exports_scanned=len(sizes),
                forbidden_content_hits=content_hits,forbidden_metadata_hits=metadata_hits,
                process_operations=len(proof),mutation=data['mutation'])


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('directory',type=Path); ap.add_argument('--output',type=Path)
    args=ap.parse_args()
    try: report=evaluate(args.directory)
    except (KeyError,ValueError,TypeError,OSError) as exc:
        report={'status':'FAIL','failures':['Incomplete/malformed evidence: '+type(exc).__name__]}
    raw=json.dumps(report,indent=2,sort_keys=True)+'\n'
    if args.output: args.output.write_text(raw)
    else: print(raw,end='')
    return 0 if report['status']=='PASS' else 1


if __name__=='__main__': sys.exit(main())
