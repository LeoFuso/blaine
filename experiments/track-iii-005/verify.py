"""Independent JSON/hash/literal checker; does not import the gate or runner."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);a=p.parse_args()
    read=lambda name:json.loads((a.evidence/name).read_text())
    f=json.loads((HERE/'fixtures.json').read_text());r=read('results.json');s=read('summary.json')
    checks=[]
    def check(name,value):checks.append({'check':name,'status':'PASS' if value else 'FAIL'})
    def wire(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()
    def digest(v):return hashlib.sha256(wire(v)).hexdigest()
    cases={c['case']:c for c in r['checks']};scenarios={c['case']:c for c in r['scenarios']}
    check('all-literal-expectations',len(cases)==len(r['checks'])==s['checks'] and all(c['actual']==c['expected'] and c['status']=='PASS' for c in r['checks']))
    check('source-hashes',all(hashlib.sha256((HERE/path).read_bytes()).hexdigest()==d for path,d in s['source_sha256'].items()))
    prior=json.loads((HERE/'../track-iii-004/evidence/summary.json').read_text())
    check('accepted-prior-sources',all(s['source_sha256'][p]==prior['source_sha256'][q] for p,q in [('../track-iii-004/security.py','security.py'),('../track-iii-003/capability.py','../track-iii-003/capability.py'),('../track-iii-002/evaluator.py','../track-iii-002/evaluator.py')]))
    check('restored',read('restored.json')==r and s['restored_equal'])
    required={'same':'ADMITTED','same-human':'ADMITTED','safe':'ADMITTED','cross-human-safe':'ADMITTED','cross-human-raw':'REJECTED_SECURITY','authority/agent':'REJECTED_AUTHORITY','authority/human':'REJECTED_AUTHORITY','approval/missing':'REJECTED_SECURITY','approval/uncertain':'REJECTED_SECURITY','approval/source-changed':'REJECTED_SECURITY','policy/missing':'UNAVAILABLE','policy/malformed':'REJECTED_POLICY','source/invalid-verified-status':'REJECTED_POLICY'}
    required.update({'unsafe/'+name:'REJECTED_SECURITY' for name in ['raw']+f['scanner_names']})
    required.update({'scanner/'+name+'/'+fault:'UNAVAILABLE' if fault=='unavailable' else 'REJECTED_SCANNER' for name in f['scanner_names'] for fault in f['scanner_faults']})
    for name,expected in required.items():
        check('required/'+name,scenarios[name]['response']['status']==expected==scenarios[name]['expected_status'])
    for c in r['scenarios']:
        name=c['case'];src=c['source_before'].get(c['request']['source_id']);added=c['added_entries'];admitted=c['expected_status']=='ADMITTED'
        check('state/'+name,c['source_before']==c['source_after'] and c['source_visibility_before']==c['source_visibility_after'] and len(added)==int(admitted))
        check('receipt-bound/'+name,len(wire(c['response']))<=2048)
        if not admitted:
            check('denial/'+name,c['response']=={'status':c['expected_status'],'receipt':None,'diagnostic':{'status':c['expected_status']}})
        else:
            e=added[0];receipt=c['response']['receipt'];audit=c['private_audit'][-1]
            check('origin/'+name,e['provenance']==src['provenance']==receipt['provenance'] and e['epistemic_status']==src['epistemic_status']==receipt['epistemic_status'] and audit['source']==src and audit['source_digest']==digest(src))
            check('metadata-whitelist/'+name,set(e)=={'id','context_id','domain','classification','content','provenance','epistemic_status','created_by','admission'} and e['admission']=={'kind':'PROMOTED_REPRESENTATION','gate_version':'gate-v1','policy_version':'promotion-policy-v1'})
            check('separation/'+name,e['id']==c['request']['destination']+'::admission-1' and e['id']!=src['id'] and e['created_by']=='promotion-gate' and e['admission']['kind']=='PROMOTED_REPRESENTATION' and
                  set(receipt)=={'status','entry_id','provenance','epistemic_status','gate_version','policy_version'} and e['content']==c['request']['candidate']['content'])
            if audit['cross_boundary']:
                check('cross-gates/'+name,len(audit['scanners'])==len(f['scanner_names']) and all(x['report']['status']=='CLEAN' for x in audit['scanners']) and audit['approval']['source_digest']==digest(src) and audit['approval']['candidate_digest']==digest(c['request']['candidate']))
    # Each deterministic category actually finds its own unsafe fixture, not just another scanner.
    for name in f['scanner_names']:
        audit=scenarios['unsafe/'+name]['private_audit'][-1]
        report=next(x['report'] for x in audit['scanners'] if x['name']==name)
        check('scanner-category/'+name,report['status']=='MATCH' and bool(report['matches']))
    public=read('destination-exports.json')
    check('export-exact',public==r['public_exports'])
    def findings(outputs):
        return [{'index':i,'literals':[literal for literal in f['protected_literals'] if literal in wire(o).decode()]} for i,o in enumerate(outputs) if any(literal in wire(o).decode() for literal in f['protected_literals'])]
    check('independent-destination-leak-scan',findings(public)==[] and read('leakage.json')==r['leakage']=={'status':'PASS','outputs_scanned':len(public),'findings':[]})
    for c in r['scenarios']:
        if c['request']['destination']=='root':
            check('destination-all-representations/'+c['case'],findings([c['destination_visible']])==[])
    probes={x['case']:x for x in r['probes']}
    replay=probes['replay']
    check('rejected-replay',probes['replay/rejected']['first']==probes['replay/rejected']['again'] and probes['replay/rejected']['first']['status']=='REJECTED_SECURITY' and probes['replay/rejected']['public']['visible_revision']==0)
    check('replay',replay['first']==replay['again'] and replay['first']['status']=='ADMITTED' and replay['changed']['status']=='REJECTED_POLICY' and replay['faulted']['status']=='UNAVAILABLE' and replay['public_before']==replay['public_after'])
    check('activity-and-ids',probes['metadata/noninterference']['without_hidden_activity']==probes['metadata/noninterference']['with_hidden_activity'] and probes['identifier/existence']['results'][0]==probes['identifier/existence']['results'][1] and probes['identifier/write-collision']['outputs'][0]==probes['identifier/write-collision']['outputs'][1])
    mutant=read('fail-open.json');failed={c['case'] for c in mutant['checks'] if c['expected']!=c['actual']};info=s['mutation']
    check('mutation-oracles',[(c['case'],c['expected']) for c in mutant['checks']]==[(c['case'],c['expected']) for c in r['checks']] and all(c['status']==('FAIL' if c['case'] in failed else 'PASS') for c in mutant['checks']))
    check('mutation-failure',info['exit_code']==1 and not info['stderr'] and info['suite']['status']=='FAIL' and info['suite']['failed']==len(failed) and set(info['suite']['failed_cases'])==failed and {'unsafe-fault/unavailable/status','destination/literal-leakage','replay/rechecks-scanners'}<=failed)
    hits=findings(mutant['public_exports'])
    check('mutation-real-leak',len(hits)>0 and hits==mutant['leakage']['findings'] and len(hits)==info['leaking_outputs'] and any('SYNTH_TOKEN_ABCDEF123456' in hit['literals'] for hit in hits))
    unsafe=next(c for c in mutant['scenarios'] if c['case']=='unsafe-fault/unavailable')
    check('mutation-real-admission',unsafe['response']['status']=='ADMITTED' and unsafe['added_entries'][0]['content']==f['candidates']['secret']['content'])
    check('summary',s['status']=='PASS' and s['failed']==0 and s['controls_detected'] and not s['III_6_started'] and s['task_submission']=={'submitted':False,'task_id':None})
    report={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','check_count':len(checks),'checks':checks}
    save=a.evidence/'verification.json';save.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':report['status'],'checks':len(checks),'failed':[c['check'] for c in checks if c['status']=='FAIL']}))
    return int(report['status']!='PASS')


if __name__=='__main__':raise SystemExit(main())
