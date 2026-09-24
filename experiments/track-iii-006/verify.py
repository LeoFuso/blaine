"""Independent retained-evidence checks. No implementation or runner imports."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);args=p.parse_args()
    read=lambda n:json.loads((args.evidence/n).read_text())
    f=json.loads((HERE/'fixtures.json').read_text());r=read('results.json');s=read('summary.json')
    checks=[]
    def check(name,ok):checks.append({'check':name,'status':'PASS' if ok else 'FAIL'})
    def encoded(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    def digest(v):return hashlib.sha256(encoded(v)).hexdigest()
    cases={c['case']:c for c in r['checks']};scenarios={c['case']:c for c in r['scenarios']}
    check('all-literal-expectations',len(cases)==len(r['checks'])==s['checks'] and all(c['expected']==c['actual'] and c['status']=='PASS' for c in r['checks']))
    check('source-hashes',all(hashlib.sha256((HERE/n).read_bytes()).hexdigest()==d for n,d in s['source_sha256'].items()))
    prior=json.loads((HERE/'../track-iii-005/evidence/summary.json').read_text())
    check('accepted-prior-sources',all(s['source_sha256'][p]==prior['source_sha256'][q] for p,q in [('../track-iii-005/gate.py','gate.py'),('../track-iii-004/security.py','../track-iii-004/security.py'),('../track-iii-003/capability.py','../track-iii-003/capability.py'),('../track-iii-002/evaluator.py','../track-iii-002/evaluator.py')]))
    check('restored',read('restored.json')==r and s['restored_equal'])
    for c in f['cases']:check('required/'+c['name'],scenarios[c['name']]['response']['status']==c['expected'])
    # Assert each required success component independently, including absent objects.
    for index in range(3):
        for state in ('FAIL','MISSING','UNKNOWN','UNAVAILABLE','NOT_RUN'):
            c=scenarios['requirement/'+str(index)+'/'+state]
            check('requirement/'+str(index)+'/'+state,c['response']['status']!='ADMITTED_VERIFIED_SUCCESS' and c['added_entries']==[])
    for c in r['scenarios']:
        name=c['case'];execution=c['execution'];spec=f['executions'][execution]
        check('immutable/'+name,c['evidence_before']==c['evidence_after'] and c['envelopes_before']==c['envelopes_after'] and
              c['evidence_digest_before']==c['evidence_digest_after'] and c['envelope_digest_before']==c['envelope_digest_after'])
        check('receipt-bound/'+name,len(encoded(c['response']))<=2048)
        entries=c['added_entries'];wanted=c['expected_status'] in ('ADMITTED_VERIFIED_SUCCESS','ADMITTED_VERIFIED_FAILURE','RETAINED_UNVERIFIED')
        check('write-count/'+name,len(entries)==int(wanted))
        permitted={'child-personal','attempt-personal'} if spec['context_id']=='child-personal' else {'task-x','work-x'}
        for ctx,output in c['reads'].items():
            expected='UNAVAILABLE' if name=='security/unavailable' else 'SUCCESS_WITH_RESULTS' if wanted and ctx in permitted else 'DENIED'
            check('scope/'+name+'/'+ctx,output['response']['status']==expected and
                  (bool(output['response']['entries']) if expected=='SUCCESS_WITH_RESULTS' else output['response']['entries']==[]))
        if not entries:
            check('rejection-safe/'+name,c['response']=={'status':c['expected_status'],'receipt':None,'diagnostic':{'status':c['expected_status']}})
            continue
        entry=entries[0];prov=c['private_provenance'][entry['id']];bundle=prov['derived_from']
        status=c['response']['status'];sem={'ADMITTED_VERIFIED_SUCCESS':'VERIFIED_SUCCESS','ADMITTED_VERIFIED_FAILURE':'VERIFIED_FAILURE','RETAINED_UNVERIFIED':'UNVERIFIED'}[status]
        check('local-entry/'+name,entry['context_id']==spec['context_id'] and entry['domain']==spec['domain'] and entry['classification']=='PRIVATE' and entry['id']==spec['context_id']+'::reflection-1')
        check('status/'+name,entry['epistemic_status']==sem and entry['provenance']==('AGENT_OBSERVATION' if sem=='UNVERIFIED' else 'VERIFIED_OUTCOME'))
        check('metadata-projection/'+name,set(entry)=={'id','context_id','domain','classification','content','created_by','provenance','epistemic_status','admission'} and set(c['response']['receipt'])=={'entry_id','provenance','epistemic_status','version'})
        check('private-evidence-link/'+name,bundle['execution_id']==execution and bundle['context_id']==spec['context_id'] and bundle['domain']==spec['domain'] and prov['snapshot_digest']==digest(bundle) and bundle['requirements']==spec['requirements'] and bundle['contract_ref']==spec['contract_ref'])
        if sem!='UNVERIFIED':
            envelope=bundle['envelope'];rows={e['id']:e for e in bundle['evidence'] if e is not None}
            check('trusted-envelope/'+name,envelope['execution_id']==execution and envelope['context_id']==spec['context_id'] and envelope['domain']==spec['domain'] and envelope['required_evidence']==[q['id'] for q in spec['requirements']] and all(e['execution_id']==execution and e['context_id']==spec['context_id'] and e['domain']==spec['domain'] and e['verifier_id'] for e in rows.values()))
            if sem=='VERIFIED_SUCCESS':
                check('all-success-evidence/'+name,envelope['status']=='SUCCEEDED' and all(q['id'] in rows and rows[q['id']]['kind']==q['kind'] and rows[q['id']]['result']==q['success'] for q in spec['requirements']))
            else:
                check('actual-failure-evidence/'+name,envelope['status']=='FAILED' and rows[spec['contract_ref']]['result']=='FAIL' and any(e['result'] in ('FAIL','ABSENT') for i,e in rows.items() if i!=spec['contract_ref']))
            check('explicit-support/'+name,prov['candidate_support'] in f['support_catalog'][execution] and prov['candidate_support']['candidate']==c['request']['candidate'] and set(prov['candidate_support']['facts'])<={v for e in rows.values() for v in e['facts']})
    exports=read('retrieval-exports.json')
    check('export-exact',exports==r['retrieval_exports'])
    hits=[]
    for i,row in enumerate(exports):
        forbidden=f['private_evidence_literals']+(f['protected_memory_literals'] if row['audience']!='employer-x' else [])
        found=[v for v in forbidden if v in encoded(row['output']).decode()]
        if found:hits.append({'index':i,'literals':found})
    check('independent-leak-scan',hits==[] and read('leakage.json')==r['leakage']=={'status':'PASS','outputs_scanned':len(exports),'findings':[]})
    probes={p['case']:p for p in r['probes']}
    replay=probes['replay']
    check('replay-current-inputs',replay['first']==replay['again'] and replay['first']['status']=='ADMITTED_VERIFIED_SUCCESS' and replay['changed']['status']=='REJECTED_UNSUPPORTED' and replay['contradictory']['status']=='REJECTED_CONTRADICTORY' and replay['new_snapshot']['status']=='REJECTED_UNSUPPORTED' and replay['fresh']['status']=='ADMITTED_VERIFIED_SUCCESS')
    check('human-separate',probes['human-direct']['admission_audit']==[] and probes['human-direct']['response']['response']['receipt']['provenance']=='USER_DECLARATION')
    check('promotion-separate',probes['separate-promotion']['result']['status']=='REJECTED_POLICY')
    for variant,unsafe in [('worker-claim','B-success'),('missing-as-pass','G-success')]:
        mutant=read(variant+'.json');info=s['controls'][variant]
        failed={c['case'] for c in mutant['checks'] if c['expected']!=c['actual']}
        check('control/'+variant,info['exit_code']==1 and not info['stderr'] and info['suite']['status']=='FAIL' and failed==set(info['suite']['failed_cases']) and len(failed)==info['suite']['failed'] and unsafe+'/decision' in failed and
              [(c['case'],c['expected']) for c in mutant['checks']]==[(c['case'],c['expected']) for c in r['checks']] and all(c['status']==('FAIL' if c['case'] in failed else 'PASS') for c in mutant['checks']))
        unsafe_case=next(c for c in mutant['scenarios'] if c['case']==unsafe)
        check('actual-unsafe-success/'+variant,unsafe_case['response']['status']=='ADMITTED_VERIFIED_SUCCESS' and unsafe_case['added_entries'][0]['epistemic_status']=='VERIFIED_SUCCESS' and unsafe_case['evidence_before']['execution-'+('B' if variant=='worker-claim' else 'G')+'-evidence-1']['result']==('FAIL' if variant=='worker-claim' else 'MISSING'))
    check('summary',s['status']=='PASS' and s['failed']==0 and s['controls_detected'] and not s['III_7_started'] and s['task_submission']=={'submitted':False,'task_id':None})
    report={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','check_count':len(checks),'checks':checks}
    (args.evidence/'verification.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'checks':len(checks),'failed':[c['check'] for c in checks if c['status']=='FAIL']}))
    return int(report['status']!='PASS')


if __name__=='__main__':raise SystemExit(main())
