"""Deterministic III.6 scenarios; unsafe subclasses are runner-only controls."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from admission import OutcomeAdmission, AdmissionBinding, PromotionGate, digest, wire

HERE=Path(__file__).resolve().parent


class WorkerClaimControl(OutcomeAdmission):
    def qualified_outcome(self,classification,claim):
        return 'VERIFIED_SUCCESS' if claim['status']=='SUCCESS' else classification


class MissingEvidenceControl(OutcomeAdmission):
    def evidence_value(self,row,requirement):
        value=super().evidence_value(row,requirement)
        return requirement['success'] if value in ('MISSING','UNKNOWN','NOT_RUN') else value


def save(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n')


def run(variant,f):
    cls={'correct':OutcomeAdmission,'worker-claim':WorkerClaimControl,'missing-as-pass':MissingEvidenceControl}[variant]
    checks=[];scenarios=[];probes=[];exports=[]
    def check(name,expected,actual):
        checks.append({'case':name,'expected':deepcopy(expected),'actual':deepcopy(actual),'status':'PASS' if expected==actual else 'FAIL'})
    def setup(execution='execution-A'):
        a=cls(f);token=a.issue(execution)
        return a,token
    def request(candidate=None,rid='reflection-1'):
        return {'op':'admitReflection','request_id':rid,'candidate':deepcopy(candidate or f['cases'][0]['candidate']), 'worker_claim':deepcopy(f['worker_claim'])}
    def memory_view(a,ctx):
        ec=a.memory.begin('view-'+ctx,ctx);c=a.memory.participant(ec,'reader','verifier')
        return a.memory.exchange(ec,c,{'op':'search','kind':'RAW','query':''})
    def evaluate(name,execution,candidate,expected,configure=None,req=None):
        a,t=setup(execution)
        if configure:configure(a)
        before=deepcopy(a.memory.raw)
        evidence_digest_before=digest(a.evidence);envelope_digest_before=digest(a.envelopes)
        refs=[q['id'] for q in a.executions[execution]['requirements']]
        before_evidence={i:deepcopy(a.evidence.get(i)) for i in refs}
        before_envelopes={execution:deepcopy(a.envelopes.get(execution))}
        given=deepcopy(req or request(candidate))
        result=a.admit(t,given)
        added=[deepcopy(e) for i,e in a.memory.raw.items() if i not in before]
        wants=expected in ('ADMITTED_VERIFIED_SUCCESS','ADMITTED_VERIFIED_FAILURE','RETAINED_UNVERIFIED')
        check(name+'/decision',expected,result['status'])
        check(name+'/write-count',int(wants),len(added))
        check(name+'/evidence-immutable',evidence_digest_before,digest(a.evidence))
        check(name+'/envelope-immutable',envelope_digest_before,digest(a.envelopes))
        check(name+'/memory-sources-immutable',before,{i:a.memory.raw[i] for i in before})
        check(name+'/receipt-budget',True,len(wire(result))<=2048)
        binding=a.bindings[t]
        candidate_id=binding.context_id+'::reflection-1'
        reads={}
        for ctx in f['memory']['context_domains']:
            ec=a.memory.begin('inspect-'+ctx,ctx);c=a.memory.participant(ec,'reader','verifier')
            got=a.memory.exchange(ec,c,{'op':'get','id':candidate_id})
            reads[ctx]=got
            allowed_contexts=['task-x','work-x'] if binding.context_id=='task-x' else ['child-personal','attempt-personal']
            check(name+'/scope/'+ctx,'UNAVAILABLE' if name=='security/unavailable' else 'SUCCESS_WITH_RESULTS' if wants and ctx in allowed_contexts else 'DENIED',got['response']['status'])
            exports.append({'audience':f['memory']['context_domains'][ctx],'output':got})
        later=a.memory.participant(binding,'later-worker','worker')
        continuous=a.memory.exchange(binding,later,{'op':'get','id':candidate_id})
        check(name+'/continuous','UNAVAILABLE' if name=='security/unavailable' else 'SUCCESS_WITH_RESULTS' if wants else 'DENIED',continuous['response']['status'])
        exports.append({'audience':f['executions'][execution]['domain'],'output':continuous})
        if wants:
            status={'ADMITTED_VERIFIED_SUCCESS':'VERIFIED_SUCCESS','ADMITTED_VERIFIED_FAILURE':'VERIFIED_FAILURE','RETAINED_UNVERIFIED':'UNVERIFIED'}[expected]
            check(name+'/semantic-status',status,added[0]['epistemic_status'] if added else None)
            check(name+'/provenance','AGENT_OBSERVATION' if status=='UNVERIFIED' else 'VERIFIED_OUTCOME',added[0]['provenance'] if added else None)
        check(name+'/public-activity',0,a.memory.visible_revision(a.memory.begin('public-inspect','root')))
        scenarios.append({'case':name,'execution':execution,'request':given,'expected_status':expected,'response':result,
                          'evidence_before':before_evidence,'evidence_after':{i:deepcopy(a.evidence.get(i)) for i in refs},'envelopes_before':before_envelopes,'envelopes_after':{execution:deepcopy(a.envelopes.get(execution))},
                          'evidence_digest_before':evidence_digest_before,'evidence_digest_after':digest(a.evidence),'envelope_digest_before':envelope_digest_before,'envelope_digest_after':digest(a.envelopes),
                          'added_entries':added,'reads':reads,'continuous_read':continuous,'private_provenance':deepcopy(a.provenance),'private_audit':deepcopy(a.audit)})
        return a,t,result

    for c in f['cases']:evaluate(c['name'],c['execution'],c['candidate'],c['expected'])
    base=f['cases'][0]['candidate']
    # Exhaust each required success component rather than inferring success from no FAIL.
    for index in range(3):
        for state in ('FAIL','MISSING','UNKNOWN','UNAVAILABLE','NOT_RUN'):
            value='ABSENT' if index==2 and state=='FAIL' else state
            expected='REJECTED_CONTRADICTORY' if state=='FAIL' else 'UNAVAILABLE' if state=='UNAVAILABLE' else 'REJECTED_UNSUPPORTED'
            evaluate('requirement/'+str(index)+'/'+state,'execution-A',base,expected,
                     configure=lambda a,i=index,v=value:a.evidence['execution-A-evidence-'+str(i)].update(result=v))
    evaluate('evidence/absent-row','execution-A',base,'REJECTED_UNSUPPORTED',configure=lambda a:a.evidence.pop('execution-A-evidence-1'))
    evaluate('envelope/missing','execution-A',base,'REJECTED_UNSUPPORTED',configure=lambda a:a.envelopes.pop('execution-A'))
    evaluate('envelope/requirements-removed','execution-A',base,'REJECTED_CONTRADICTORY',configure=lambda a:a.envelopes['execution-A'].update(required_evidence=[]))
    evaluate('evidence/foreign-execution','execution-A',base,'REJECTED_CONTRADICTORY',configure=lambda a:a.evidence['execution-A-evidence-1'].update(execution_id='execution-X'))
    evaluate('evidence/foreign-domain','execution-A',base,'REJECTED_CONTRADICTORY',configure=lambda a:a.evidence['execution-A-evidence-1'].update(domain='employer-x'))
    evaluate('evidence/malformed','execution-A',base,'REJECTED_CONTRADICTORY',configure=lambda a:a.evidence['execution-A-evidence-1'].update(result='UNRECOGNIZED'))
    evaluate('evidence/support-fact-missing','execution-D',f['support_catalog']['execution-D'][1]['candidate'],'REJECTED_UNSUPPORTED',configure=lambda a:[e.update(facts=['approach-B']) for e in a.evidence.values() if e['execution_id']=='execution-D'])
    evaluate('candidate/unsupported-text','execution-A',{'content':'Strategy Z always works everywhere.','intent':'SUCCESS'},'REJECTED_UNSUPPORTED')
    evaluate('capability/unavailable','execution-A',base,'UNAVAILABLE',configure=lambda a:setattr(a,'available',False))
    evaluate('security/unavailable','execution-A',base,'UNAVAILABLE',configure=lambda a:setattr(a.memory,'policy',None))
    evaluate('security/malformed','execution-A',base,'REJECTED_UNSUPPORTED',configure=lambda a:setattr(a.memory,'policy',{}))
    for field,value in {'status':'VERIFIED_SUCCESS','provenance':'VERIFIED_OUTCOME','evidence_complete':True,'completion':'PASS','destination':'parent-personal'}.items():
        given=request();given['candidate'][field]=value
        evaluate('forgery/candidate/'+field,'execution-A',base,'REJECTED_UNSUPPORTED',req=given)
    for field,value in {'outcome':'VERIFIED_SUCCESS','execution_id':'execution-X','security_domain':'employer-x','evidence':['pretend-pass'],'parent':'parent-personal'}.items():
        given=request();given[field]=value
        evaluate('forgery/request/'+field,'execution-A',base,'REJECTED_UNSUPPORTED',req=given)
    # Opposite worker claims cannot change a verified result or a failure result.
    for execution,cand,expected in [('execution-A',base,'ADMITTED_VERIFIED_SUCCESS'),('execution-B',base,'REJECTED_UNSUPPORTED')]:
        given=request(cand);given['worker_claim']={'status':'FAILURE','text':'I think the work failed.'}
        evaluate('claim-invariance/'+execution,execution,cand,expected,req=given)

    # Human declaration does not go through the outcome admission stage.
    a,t=setup('execution-X');ec=a.bindings[t]
    human=a.memory.participant(ec,'human-x','human')
    declaration=a.memory.exchange(ec,human,{'op':'declare','id':'human-teaching','content':'For this project, prefer constructor injection.','target_context':'project-x'})
    check('human/provenance','USER_DECLARATION',declaration['response']['receipt']['provenance'])
    check('human/separate-admission',[],a.audit)
    check('human/no-derived-work-evidence',{},a.provenance)
    probes.append({'case':'human-direct','response':declaration,'admission_audit':deepcopy(a.audit)})

    # Revalidate current trusted inputs BEFORE the private replay lookup.
    a,t=setup();given=request()
    first=a.admit(t,given);first_store=deepcopy(a.memory.raw)
    again=a.admit(t,given)
    check('replay/identical',first,again);check('replay/no-duplicate',first_store,a.memory.raw)
    a.evidence['execution-A-evidence-1']['result']='MISSING'
    changed=a.admit(t,given)
    check('replay/missing-reevaluated','REJECTED_UNSUPPORTED',changed['status'])
    check('replay/no-revocation-or-rewrite',first_store,a.memory.raw)
    a.evidence['execution-A-evidence-1']['result']='FAIL'
    contradictory=a.admit(t,given)
    check('replay/contradiction-reevaluated','REJECTED_CONTRADICTORY',contradictory['status'])
    a.evidence['execution-A-evidence-1']['result']='PASS'
    a.envelopes['execution-A']['id']='execution-A-outcome-2'
    new_snapshot=a.admit(t,given)
    check('replay/new-snapshot-conflict','REJECTED_UNSUPPORTED',new_snapshot['status'])
    fresh=a.admit(t,request(rid='new-snapshot-request'))
    check('replay/new-request-revalidated','ADMITTED_VERIFIED_SUCCESS',fresh['status'])
    probes.append({'case':'replay','first':first,'again':again,'changed':changed,'contradictory':contradictory,'new_snapshot':new_snapshot,'fresh':fresh,'private_provenance':deepcopy(a.provenance),'private_audit':deepcopy(a.audit)})

    # III.5 remains separate and fail-closed for the new, not-yet-adapted taxonomy.
    a,t,result=evaluate('promotion/local-only','execution-A',base,'ADMITTED_VERIFIED_SUCCESS')
    gate=PromotionGate(json.loads((HERE/'../track-iii-005/fixtures.json').read_text()))
    gate.memory=a.memory
    before=deepcopy(a.memory.raw)
    bound=gate.issue('child-personal','SYSTEM_PROMOTION_SERVICE','promotion-service')
    promoted=gate.request_promotion(bound,{'op':'requestPromotion','request_id':'separate','source_id':result['receipt']['entry_id'],'destination':'parent-personal','candidate':{'content':base['content']}})
    check('promotion/unsupported-taxonomy-fails-closed','REJECTED_POLICY',promoted['status'])
    check('promotion/no-effects',before,a.memory.raw)
    probes.append({'case':'separate-promotion','result':promoted,'private_audit':deepcopy(gate.audit)})

    # Evidence IDs are not capabilities; ordinary memory retrieval cannot fetch raw evidence.
    a,t,result=evaluate('private-evidence/X','execution-X',base,'ADMITTED_VERIFIED_SUCCESS')
    reads=[]
    for ctx in ('task-x','personal','root'):
        ec=a.memory.begin('evidence-probe-'+ctx,ctx);caller=a.memory.participant(ec,'reader','verifier')
        for eid in ('execution-X-evidence-1','absent-evidence'):
            out=a.memory.exchange(ec,caller,{'op':'get','id':eid})
            check('private-evidence/'+ctx+'/'+eid,'DENIED',out['response']['status'])
            reads.append(out);exports.append({'audience':a.memory.context_domains[ctx],'output':out})
    probes.append({'case':'raw-evidence-probes','outputs':reads})
    fake=a.admit(AdmissionBinding(),request())
    check('binding/fabricated','REJECTED_UNSUPPORTED',fake['status'])
    other,foreign=setup();check('binding/foreign','REJECTED_UNSUPPORTED',a.admit(foreign,request())['status'])
    # Ordinary writes also cannot choose the verified provenance/status.
    ec=a.bindings[t];worker=a.memory.participant(ec,'worker','worker')
    out=a.memory.exchange(ec,worker,{'op':'recordObservation','id':'forgery','content':'success','provenance':'VERIFIED_OUTCOME','epistemic_status':'VERIFIED_SUCCESS'})
    check('ordinary/forged-verification','DENIED',out['response']['status'])
    probes.append({'case':'ordinary-forgery','output':out})

    leaks=[]
    for i,item in enumerate(exports):
        encoded=json.dumps(item['output'],sort_keys=True,ensure_ascii=False)
        forbidden=f['private_evidence_literals']+(f['protected_memory_literals'] if item['audience']!='employer-x' else [])
        hits=[x for x in forbidden if x in encoded]
        if hits:leaks.append({'index':i,'literals':hits})
    check('retrieval/literal-leakage',[],leaks)
    return {'checks':checks,'scenarios':scenarios,'probes':probes,'retrieval_exports':exports,
            'leakage':{'status':'FAIL' if leaks else 'PASS','outputs_scanned':len(exports),'findings':leaks}}


def verdict(r):
    failures=[c['case'] for c in r['checks'] if c['status']=='FAIL']
    return {'status':'FAIL' if failures else 'PASS','checks':len(r['checks']),'failed':len(failures),'failed_cases':failures}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--variant',choices=['correct','worker-claim','missing-as-pass'],default='correct');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    f=json.loads((HERE/'fixtures.json').read_text());r=run(a.variant,f);s=verdict(r);save(a.output/'results.json',r)
    if a.variant=='correct':
        save(a.output/'retrieval-exports.json',r['retrieval_exports']);save(a.output/'leakage.json',r['leakage'])
        controls={}
        for variant in ('worker-claim','missing-as-pass'):
            with tempfile.TemporaryDirectory(prefix='blaine-iii6-') as temp:
                child=subprocess.run([sys.executable,str(HERE/'probe.py'),'--variant',variant,'--output',temp],capture_output=True,text=True,timeout=30)
                mutant=json.loads((Path(temp)/'results.json').read_text());save(a.output/(variant+'.json'),mutant)
                controls[variant]={'exit_code':child.returncode,'stdout':child.stdout,'stderr':child.stderr,'suite':verdict(mutant)}
        restored=run('correct',f);save(a.output/'restored.json',restored)
        caught=all(c['exit_code']==1 for c in controls.values()) and 'B-success/decision' in controls['worker-claim']['suite']['failed_cases'] and 'G-success/decision' in controls['missing-as-pass']['suite']['failed_cases']
        s.update(controls=controls,controls_detected=caught,restored_equal=restored==r,source_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ['admission.py','probe.py','verify.py','fixtures.json','../track-iii-005/gate.py','../track-iii-004/security.py','../track-iii-003/capability.py','../track-iii-002/evaluator.py']},III_7_started=False,task_submission={'submitted':False,'task_id':None})
        if not caught or restored!=r:s['status']='FAIL'
    save(a.output/'summary.json',s);print(json.dumps({k:s[k] for k in ('status','checks','failed')}));return int(s['status']!='PASS')


if __name__=='__main__':raise SystemExit(main())
