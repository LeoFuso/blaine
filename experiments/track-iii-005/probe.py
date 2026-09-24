"""Finite III.5 oracle suite. Negative variants run only in isolated processes."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from gate import PromotionGate, PromotionBinding, digest, result, wire

HERE=Path(__file__).resolve().parent


class FailOpenControl(PromotionGate):
    def scanner_admissible(self,report,name):
        if isinstance(report,dict) and report.get('status') in ('UNKNOWN','UNAVAILABLE'):
            return True
        return super().scanner_admissible(report,name)


def save(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n')


def run(variant,f):
    cls=FailOpenControl if variant=='fail-open' else PromotionGate
    checks=[]; scenarios=[]; public_exports=[]; probes=[]
    def check(name,expected,actual):
        checks.append({'case':name,'expected':deepcopy(expected),'actual':deepcopy(actual),'status':'PASS' if expected==actual else 'FAIL'})
    def setup(fixture=None):
        gate=cls(f if fixture is None else fixture)
        tokens={b['name']:gate.issue(b['context'],b['role'],b['name']) for b in f['bindings']}
        return gate,tokens
    def reader(g,ctx,role='verifier',name='reader'):
        ec=g.memory.begin('inspect-'+ctx,ctx)
        return ec,g.memory.participant(ec,name,role)
    def view(g,ctx='root'):
        ec,who=reader(g,ctx)
        return g.destination_view(ec,who)
    def req(source='protected-source',dest='root',candidate='safe',rid='request-1'):
        return {'op':'requestPromotion','request_id':rid,'source_id':source,'destination':dest,'candidate':deepcopy(f['candidates'][candidate])}
    def source_views(g,source):
        out={}
        for ctx in ('root','personal','employer-x','child-personal','parent-personal'):
            ec,c=reader(g,ctx)
            out[ctx]=g.memory.exchange(ec,c,{'op':'get','id':source})
        return out
    def evaluate(name,expected,request=None,actor='cross-service',configure=None):
        g,t=setup()
        if configure: configure(g)
        request=deepcopy(request or req())
        before=deepcopy(g.memory.raw)
        visibility_before=source_views(g,request['source_id'])
        response=g.request_promotion(t[actor],request)
        visibility_after=source_views(g,request['source_id'])
        public=view(g)
        public_exports.append(public)
        destination=request['destination'] if request['destination'] in g.memory.context_domains else 'root'
        after_original={i:deepcopy(g.memory.raw[i]) for i in before}
        added=[deepcopy(e) for i,e in g.memory.raw.items() if i not in before]
        check(name+'/status',expected,response['status'])
        check(name+'/source-immutability',before,after_original)
        check(name+'/source-visibility',visibility_before,visibility_after)
        check(name+'/write-count',1 if expected=='ADMITTED' else 0,len(added))
        check(name+'/bounded-receipt',True,len(wire(response))<=2048)
        later=None
        if expected=='ADMITTED':
            bound=g.bindings[t[actor]]['execution']
            later_worker=g.memory.participant(bound,'later-worker','worker')
            later=g.memory.exchange(bound,later_worker,{'op':'get','id':response['receipt']['entry_id']})
            check(name+'/continuous-read','SUCCESS_WITH_RESULTS',later['response']['status'])
            src=before[request['source_id']]
            check(name+'/origin',(src['provenance'],src['epistemic_status']),
                  (added[0]['provenance'],added[0]['epistemic_status']) if added else None)
            check(name+'/destination',destination,added[0]['context_id'] if added else None)
        scenarios.append({'case':name,'expected_status':expected,'request':request,'actor':actor,
                          'response':response,'source_before':before,'source_after':after_original,
                          'source_visibility_before':visibility_before,'source_visibility_after':visibility_after,
                          'added_entries':added,'later_participant_read':later,'destination_visible':view(g,destination),'public_visible':public,
                          'private_audit':deepcopy(g.audit)})
        return g,t,response

    evaluate('same','ADMITTED',req('local-observation','parent-personal','same'),actor='same-service')
    evaluate('same-human','ADMITTED',req('local-human','parent-personal','human-safe'),actor='same-service')
    evaluate('safe','ADMITTED')
    evaluate('cross-human-safe','ADMITTED',req('protected-human','root','human-safe'))
    evaluate('cross-human-raw','REJECTED_SECURITY',req('protected-human','root','raw'))
    for candidate in ['raw']+f['scanner_names']:
        evaluate('unsafe/'+candidate,'REJECTED_SECURITY',req(candidate=candidate))
    for actor in ('agent','human'):
        evaluate('authority/'+actor,'REJECTED_AUTHORITY',req('local-observation','parent-personal','same'),actor=actor)
    for destination in ('sibling-personal','attempt-personal','employer-x','child-personal','project-personal','missing'):
        evaluate('destination/'+destination,'REJECTED_POLICY',req('local-observation',destination,'same'),actor='same-service')
    evaluate('destination/parent-not-authorized','REJECTED_POLICY',req('deep-protected','project-x','safe'),actor='deep-service')
    evaluate('same/secret-denied','REJECTED_SECURITY',req('local-observation','parent-personal','secret'),actor='same-service')
    evaluate('destination/skip-parent','REJECTED_POLICY',req('deep-protected','root','safe'),actor='deep-service')
    evaluate('source/missing','REJECTED_POLICY',req('missing'))
    evaluate('source/foreign','REJECTED_POLICY',actor='personal-service')
    evaluate('approval/missing','REJECTED_SECURITY',configure=lambda g:g.approvals.clear())
    evaluate('approval/uncertain','REJECTED_SECURITY',configure=lambda g:[a.update(decision='UNCERTAIN') for a in g.approvals])
    evaluate('approval/source-changed','REJECTED_SECURITY',configure=lambda g:g.memory.raw['protected-source'].update(content='Changed protected source.'))
    evaluate('policy/missing','UNAVAILABLE',configure=lambda g:setattr(g,'policy',None))
    evaluate('policy/malformed','REJECTED_POLICY',configure=lambda g:setattr(g,'policy',{}))
    evaluate('capability/unavailable','UNAVAILABLE',configure=lambda g:setattr(g,'available',False))
    evaluate('security-policy/unavailable','UNAVAILABLE',configure=lambda g:setattr(g.memory,'policy',None))
    evaluate('source/invalid-verified-status','REJECTED_POLICY',configure=lambda g:g.memory.raw['protected-source'].update(epistemic_status='VERIFIED_OUTCOME'))

    for scanner in f['scanner_names']:
        for fault in f['scanner_faults']:
            expected='UNAVAILABLE' if fault=='unavailable' else 'REJECTED_SCANNER'
            evaluate('scanner/'+scanner+'/'+fault,expected,configure=lambda g,s=scanner,m=fault:g.scanner_modes.update({s:m}))
    # Real unsafe content gets through ONLY under the fail-open control.
    for fault in ('unavailable','unknown'):
        evaluate('unsafe-fault/'+fault,'UNAVAILABLE' if fault=='unavailable' else 'REJECTED_SCANNER',
                 req(candidate='secret'),configure=lambda g,m=fault:g.scanner_modes.update(secret=m))
    forged={'caller_role':'SYSTEM_PROMOTION_SERVICE','promotion_authority':True,'declassified':True,
            'provenance':'VERIFIED_OUTCOME','scanner_result':'CLEAN','policy_result':'ALLOW','public':True,'destination_context':'root'}
    for field,value in forged.items():
        request=req();request[field]=value
        evaluate('forgery/'+field,'REJECTED_POLICY',request)
    request=req();request['candidate']['provenance']='VERIFIED_OUTCOME'
    evaluate('forgery/candidate-metadata','REJECTED_POLICY',request)
    request=req();request['candidate']['epistemic_status']='VERIFIED_OUTCOME'
    evaluate('forgery/verified-status','REJECTED_POLICY',request)
    request=req('local-observation','parent-personal','same');request['caller_role']='SYSTEM_PROMOTION_SERVICE'
    evaluate('forgery/agent-role','REJECTED_AUTHORITY',request,actor='agent')
    request=req();request['destination']='personal'
    evaluate('forgery/destination','REJECTED_POLICY',request)

    # Ordinary writes and explicit human declaration remain different paths.
    g,t=setup(); before=deepcopy(g.memory.raw)
    ec,worker=reader(g,'child-personal','worker')
    for field,value in {'destination_context':'parent-personal','target_context':'parent-personal','global':True,'public':True,
                        'provenance':'VERIFIED','declassified':True}.items():
        r=g.memory.exchange(ec,worker,{'op':'recordObservation','id':'ordinary','content':'local',field:value})
        check('ordinary/forgery/'+field,'DENIED',r['response']['status'])
        probes.append({'case':'ordinary/forgery/'+field,'output':r})
    check('ordinary/forgery-no-write',before,g.memory.raw)
    ordinary=g.memory.exchange(ec,worker,{'op':'recordObservation','id':'ordinary','content':'local'})
    pe,pw=reader(g,'parent-personal')
    hidden=g.memory.exchange(pe,pw,{'op':'get','id':'child-personal::ordinary'})
    check('ordinary/local-only','DENIED',hidden['response']['status'])
    human=g.memory.participant(ec,'human-personal','human')
    declaration=g.memory.exchange(ec,human,{'op':'declare','id':'declaration','content':'Human direct declaration.','target_context':'parent-personal'})
    check('declaration/human-origin','USER_DECLARATION',declaration['response']['receipt']['provenance'])
    check('declaration/not-promotion',[],g.audit)
    probes.append({'case':'write-vs-declaration','ordinary':ordinary,'parent-read':hidden,'declaration':declaration,'private_audit':g.audit})

    # Exact replay rechecks admission; changed candidates cannot reuse identity.
    g,t=setup();request=req()
    first=g.request_promotion(t['cross-service'],request); first_view=view(g)
    again=g.request_promotion(t['cross-service'],request); again_view=view(g)
    check('replay/identical',first,again);check('replay/no-effects',first_view,again_view)
    changed=g.request_promotion(t['cross-service'],req(candidate='safe-alternative'))
    check('replay/changed-request','REJECTED_POLICY',changed['status'])
    g.scanner_modes['secret']='unavailable'
    faulted=g.request_promotion(t['cross-service'],request)
    check('replay/rechecks-scanners','UNAVAILABLE',faulted['status'])
    check('replay/fault-no-destination-effects',first_view,view(g))
    public_exports.extend([first_view,again_view,view(g)])
    probes.append({'case':'replay','first':first,'again':again,'changed':changed,'faulted':faulted,'public_before':first_view,'public_after':view(g),'private_audit':g.audit})

    denied_gate,denied_tokens=setup()
    denied_request=req(candidate='raw')
    rejected_first=denied_gate.request_promotion(denied_tokens['cross-service'],denied_request)
    rejected_again=denied_gate.request_promotion(denied_tokens['cross-service'],denied_request)
    check('replay/rejection-identical',rejected_first,rejected_again)
    check('replay/rejection-no-effects',0,view(denied_gate)['visible_revision'])
    probes.append({'case':'replay/rejected','first':rejected_first,'again':rejected_again,'public':view(denied_gate)})
    public_exports.append(view(denied_gate))
    # Hidden source existence and private activity cannot alter destination IDs/revisions.
    collision=[]
    for extra in (False,True):
        fixture=deepcopy(f)
        if extra:
            fixture['memory']['entries'].append(dict(next(e for e in fixture['memory']['entries'] if e['id']=='protected-source'),id='same-private-id'))
        g,t=setup(fixture)
        if extra:
            g.request_promotion(t['same-service'],req('local-observation','parent-personal','same',rid='same-private-id'))
            g.request_promotion(t['cross-service'],req(candidate='raw',rid='rejected-private-id'))
        public_before=view(g)
        admitted=g.request_promotion(t['cross-service'],req(rid='same-private-id'))
        snapshot=view(g)
        check('metadata/public-before/'+str(extra),0,public_before['visible_revision'])
        check('metadata/public-after/'+str(extra),1,snapshot['visible_revision'])
        collision.append({'admitted':admitted,'public':snapshot})
        public_exports.extend([public_before,snapshot])
    check('metadata/no-global-id-or-activity-effects',collision[0],collision[1])
    probes.append({'case':'metadata/noninterference','without_hidden_activity':collision[0],'with_hidden_activity':collision[1]})

    # Destination get/failed promotion probes have identical missing vs hidden results.
    g,t=setup();root,rc=reader(g,'root');personal,pc=reader(g,'personal','worker')
    pairs=[]
    for source_id in ('protected-source','absent-source'):
        got=g.memory.exchange(root,rc,{'op':'get','id':source_id})
        rejected=g.request_promotion(t['personal-service'],req(source=source_id))
        pairs.append({'get':got,'promotion':rejected})
        public_exports.append({'memory_probe':got,'promotion_probe':rejected})
    check('identifier/missing-vs-hidden',pairs[0],pairs[1])
    check('identifier/deny','DENIED',pairs[0]['get']['response']['status'])
    probes.append({'case':'identifier/existence','results':pairs})
    # A caller-known opaque local key collides only in its own namespace.
    writes=[]
    for exists in (False,True):
        h,ht=setup()
        if exists: h.memory.raw['opaque-known-key']=dict(h.memory.raw['protected-source'],id='opaque-known-key')
        e,c=reader(h,'personal','worker')
        writes.append(h.memory.exchange(e,c,{'op':'recordObservation','id':'opaque-known-key','content':'caller input'}))
    check('identifier/write-collision',writes[0],writes[1])
    probes.append({'case':'identifier/write-collision','outputs':writes})
    check('binding/fabricated',result('REJECTED_AUTHORITY'),g.request_promotion(PromotionBinding(),req()))
    other,ot=setup()
    check('binding/foreign',result('REJECTED_AUTHORITY'),g.request_promotion(ot['cross-service'],req()))

    # Literal scan covers entire serialized destination exports, not private audit.
    leaks=[]
    for index,output in enumerate(public_exports):
        encoded=json.dumps(output,sort_keys=True,ensure_ascii=False)
        hits=[s for s in f['protected_literals'] if s in encoded]
        if hits:leaks.append({'index':index,'literals':hits})
    check('destination/literal-leakage',[],leaks)
    return {'checks':checks,'scenarios':scenarios,'probes':probes,'public_exports':public_exports,
            'leakage':{'status':'FAIL' if leaks else 'PASS','outputs_scanned':len(public_exports),'findings':leaks}}


def verdict(report):
    failed=[c['case'] for c in report['checks'] if c['status']=='FAIL']
    return {'status':'FAIL' if failed else 'PASS','checks':len(report['checks']),'failed':len(failed),'failed_cases':failed}


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--variant',choices=['correct','fail-open'],default='correct');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    f=json.loads((HERE/'fixtures.json').read_text());r=run(a.variant,f);s=verdict(r)
    save(a.output/'results.json',r)
    if a.variant=='correct':
        save(a.output/'destination-exports.json',r['public_exports']);save(a.output/'leakage.json',r['leakage'])
        with tempfile.TemporaryDirectory(prefix='blaine-iii5-') as temp:
            child=subprocess.run([sys.executable,str(HERE/'probe.py'),'--variant','fail-open','--output',temp],capture_output=True,text=True,timeout=30)
            mutant=json.loads((Path(temp)/'results.json').read_text());save(a.output/'fail-open.json',mutant)
        restored=run('correct',f);save(a.output/'restored.json',restored)
        caught=child.returncode==1 and mutant['leakage']['findings'] and 'unsafe-fault/unavailable/status' in verdict(mutant)['failed_cases']
        s.update(mutation={'exit_code':child.returncode,'stdout':child.stdout,'stderr':child.stderr,'suite':verdict(mutant),'leaking_outputs':len(mutant['leakage']['findings'])},controls_detected=bool(caught),restored_equal=restored==r,
                 source_sha256={name:hashlib.sha256((HERE/name).read_bytes()).hexdigest() for name in ['gate.py','probe.py','verify.py','fixtures.json','../track-iii-004/security.py','../track-iii-003/capability.py','../track-iii-002/evaluator.py']},III_6_started=False,task_submission={'submitted':False,'task_id':None})
        if not caught or restored!=r:s['status']='FAIL'
    save(a.output/'summary.json',s)
    print(json.dumps({k:s[k] for k in ('status','checks','failed')}));return int(s['status']!='PASS')


if __name__=='__main__':raise SystemExit(main())
