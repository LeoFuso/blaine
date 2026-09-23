"""Independent retained-evidence checker: stdlib JSON/hashes only; no SUT imports."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args()
    read=lambda name: json.loads((args.evidence/name).read_text())
    f=json.loads((HERE/'fixtures.json').read_text())
    r,s=read('results.json'),read('summary.json')
    checks=[]
    def check(name,value): checks.append({'check':name,'status':'PASS' if value else 'FAIL'})
    def wire(value): return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    cases={c['case']:c for c in r['cases']}
    trace={t['case']:t for t in r['trace']}
    check('unique-cases',len(cases)==len(r['cases'])==s['checks'])
    check('all-correct',s['failed']==0 and all(c['expected']==c['actual'] and c['status']=='PASS' for c in cases.values()))
    check('source-hashes',all(hashlib.sha256((HERE/p).read_bytes()).hexdigest()==digest for p,digest in s['source_sha256'].items()))
    check('accepted-III2-source',s['source_sha256']['../track-iii-002/evaluator.py']=='e4789efa17d81af51ae6612e63cb0cda7f6da44bcf057cecd884fe0701eba030')
    check('accepted-III3-source',s['source_sha256']['../track-iii-003/capability.py']=='83b9ccad75bbf07448ef88eec7823ff194f94d9bc51969795049a941ab9ffa0b')
    check('restored',read('restored.json')==r and s['restored_equal'])
    check('budget',all(len(wire(t['output']['response']))==t['response_bytes']<=2048 for t in r['trace']) and
          max(t['response_bytes'] for t in r['trace'])==s['max_response_bytes'])
    objects={e['id']:dict(e,kind='RAW') for e in f['entries']}
    objects.update({d['id']:d for d in f['derived']})
    expected_matrix={}
    for ctx,raw_ids in f['expected_raw'].items():
        allowed=set(raw_ids+f['expected_derived'][ctx])
        expected_matrix[ctx]={i:'SUCCESS_WITH_RESULTS' if i in allowed else 'DENIED' for i in objects}
        check('raw/'+ctx,[e['id'] for e in trace['search/'+ctx]['output']['response']['entries']]==raw_ids)
        check('derived-oracle/'+ctx,sorted(d['id'] for d in f['derived'] if set(d['source_ids'])<=set(raw_ids))==f['expected_derived'][ctx])
        for i,row in objects.items():
            actual=trace['direct/'+ctx+'/'+i]['output']['response']
            check('direct/'+ctx+'/'+i,actual['status']==expected_matrix[ctx][i] and
                  actual['entries']==([row] if i in allowed else []) and actual['receipt'] is None)
    check('visibility-matrix',r['visibility_matrix']==expected_matrix)
    for t in r['trace']:
        out=t['output']; response=out['response']
        check('diagnostic/'+t['case'],out['diagnostic']=={'status':response['status'],'returned_count':len(response['entries']),'partial':response['partial']})
        if response['status'] in ('DENIED','EMPTY','UNAVAILABLE'):
            check('empty-envelope/'+t['case'],response['entries']==[] and response['receipt'] is None and response['reason'] is None)
    exports=read('observables.json')
    check('observable-export',exports==r['observables'])
    check('complete-export',sum(map(len,exports.values()))==len(r['trace']) and all(
        exports[t['audience']][t['output_index']]==t['output'] for t in r['trace']))
    def leaks(outputs):
        findings=[]
        for domain,rows in outputs.items():
            forbidden={v for owner,values in f['protected_literals'].items() if owner!=domain for v in values}
            for index,row in enumerate(rows):
                encoded=wire(row).decode()
                hits=sorted(v for v in forbidden if v in encoded)
                if hits: findings.append({'audience':domain,'output_index':index,'literals':hits})
        return findings
    check('independent-literal-scan',leaks(exports)==[] and read('literal-leakage.json')==r['leakage'] and
          r['leakage']=={'status':'PASS','outputs_scanned':len(r['trace']),'leaking_outputs':0,'findings':[]})
    for e in f['entries']:
        if e['domain']!='public':
            check('literal-manifest/'+e['id'],{e['id'],e['created_by'],*e['content'].split()}<=set(f['protected_literals'][e['domain']]))
    for variant,required in [('structural-only',{'direct/task-personal-a/x-root-private','literal-leakage'}),
                              ('query-only-cache',{'cache/foreign','cache/forged-envelope','literal-leakage'})]:
        control=read(variant+'.json'); info=s['controls'][variant]
        failed={c['case'] for c in control['cases'] if c['expected']!=c['actual']}
        check('control/'+variant,required<=failed==set(info['suite']['failed_cases']) and len(failed)==info['suite']['failed']
              and info['exit_code']==1 and info['suite']['status']=='FAIL' and not info['stderr']
              and [(c['case'],c['expected']) for c in control['cases']]==[(c['case'],c['expected']) for c in r['cases']]
              and all(c['status']==('FAIL' if c['case'] in failed else 'PASS') for c in control['cases']))
        found=leaks(control['observables'])
        check('control-leak/'+variant,len(found)>0 and found==control['leakage']['findings'] and len(found)==info['leaking_outputs'])
    for prefix,ctx in [('personal','task-personal-a'),('x','task-x-a')]:
        events=[t for t in r['trace'] if t['case'].startswith('sequence/'+prefix+'/')]
        check('continuous-binding/'+prefix,all(t['issued_binding_matches'] and t['execution']=={'execution_id':'continuous-'+prefix,'context_id':ctx} for t in events)
              and {'cognition','worker','verifier','human'}=={t['caller']['caller_class'] for t in events})
        for suffix,provenance,state in [('human-declaration','USER_DECLARATION','DECLARED'),('cognition-observation','AGENT_OBSERVATION','UNVERIFIED'),('worker-observation','AGENT_OBSERVATION','UNVERIFIED')]:
            target=('project-personal' if prefix=='personal' else 'project-x') if suffix=='human-declaration' else ctx
            entry=next(e for e in r['continuous_final_records'] if e['id']==target+'::'+prefix+'-'+suffix)
            check('provenance/'+prefix+'/'+suffix,entry['domain']==f['context_domains'][ctx] and entry['classification']=='PRIVATE' and
                  entry['provenance']==provenance and entry['epistemic_status']==state)
    check('stop-boundary',s['status']=='PASS' and s['controls_detected'] and not s['III_5_started'] and s['task_submission']=={'submitted':False,'task_id':None})
    result={'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL','checks':checks,'check_count':len(checks)}
    (args.evidence/'verification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'checks':len(checks),'failed':[c['check'] for c in checks if c['status']=='FAIL']}))
    return int(result['status']!='PASS')


if __name__=='__main__': raise SystemExit(main())
