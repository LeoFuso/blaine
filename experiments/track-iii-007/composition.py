"""III.7 fixture composition only; earlier experiment sources remain unchanged."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'track-iii-006'))
from admission import OutcomeAdmission, digest, wire
from promotion_v2 import PromotionGate


def load(name):return json.loads((HERE/name).read_text())
def save(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True,ensure_ascii=False)+'\n')


def build(include_controls=True):
    f=load('fixtures.json');g=load('gate-fixture.json');a=OutcomeAdmission(f);gate=PromotionGate(g);gate.memory=a.memory
    checks=[];origins=[];promoted={}
    def check(name,expected,actual):checks.append({'case':name,'expected':expected,'actual':actual,'status':'PASS' if expected==actual else 'FAIL'})
    for r in f['prior_cases']:
        eid='prior-'+r['key'];token=a.issue(eid);candidate=f['support_catalog'][eid][0]['candidate']
        # Prior synthetic execution/verifier results agree with trusted admission envelope.
        observed='INCOMPLETE' if r['attempt'] is None else 'SUCCEEDED' if r['attempt']==r['expected'] else 'FAILED'
        check('prior-outcome/'+r['key'],f['envelopes'][eid]['status'],observed)
        admitted=a.admit(token,{'op':'admitReflection','request_id':'learn','worker_claim':{'status':'SUCCESS','text':'Worker says done; this is not evidence.'},'candidate':candidate})
        want={'SUCCESS':'ADMITTED_VERIFIED_SUCCESS','FAILURE':'ADMITTED_VERIFIED_FAILURE','OBSERVATION':'RETAINED_UNVERIFIED'}[r['intent']]
        check('admission/'+r['key'],want,admitted['status'])
        source_id=admitted['receipt']['entry_id'];source=deepcopy(a.memory.raw[source_id]);dest='project' if r['context']=='prior' else 'employer-x'
        bind=gate.issue(r['context'],'SYSTEM_PROMOTION_SERVICE','trusted-promotion')
        request={'op':'requestPromotion','request_id':'promote-'+r['key'],'source_id':source_id,'destination':dest,'candidate':{'content':r['content']}}
        result=gate.request_promotion(bind,request)
        check('promotion/'+r['key'],'ADMITTED',result['status'])
        entry=deepcopy(a.memory.raw[result['receipt']['entry_id']]);promoted[r['key']]=entry
        check('status-preserved/'+r['key'],[source['provenance'],source['epistemic_status']],[entry['provenance'],entry['epistemic_status']])
        check('source-immutable/'+r['key'],source,a.memory.raw[source_id])
        check('replay/'+r['key'],result,gate.request_promotion(bind,request))
        origins.append({'key':r['key'],'execution':eid,'prior_verifier':observed,'admission':admitted,'source':source,'promotion':result,'destination':entry,'private_provenance':deepcopy(a.provenance[source_id])})
    # All later contexts can read promoted project entries; no private sibling or protected source.
    visibility=[]
    for t in f['tasks']:
        ec=a.memory.begin(t['id'],t['id']);caller=a.memory.participant(ec,'reader','cognition')
        for origin in origins:
            for kind,obj in [('source',origin['source']),('destination',origin['destination'])]:
                response=a.memory.exchange(ec,caller,{'op':'get','id':obj['id']})['response']
                expected='SUCCESS_WITH_RESULTS' if kind=='destination' and origin['key']!='protected' else 'DENIED'
                check('visibility/'+t['id']+'/'+origin['key']+'/'+kind,expected,response['status'])
                visibility.append({'task':t['id'],'key':origin['key'],'kind':kind,'response':response})
        check('forged-scope/'+t['id'],'DENIED',a.memory.exchange(ec,caller,{'op':'search','kind':'RAW','query':'','domain':'employer-x'})['response']['status'])
    # Preserve declarations without mixing them into the behavioral memory variable.
    human_memory=OutcomeAdmission(f).memory;ec=human_memory.begin('human','prior');human=human_memory.participant(ec,'human-personal','human')
    declared=human_memory.exchange(ec,human,{'op':'declare','id':'preference','content':'Prefer constructor injection.','target_context':'project'})
    check('human-declaration','USER_DECLARATION',declared['response']['receipt']['provenance'])
    # Cross-domain checks use the same new schema and unchanged admission/scanner code.
    # These are isolated copies, never the behavioral memory plane.
    cross=[]
    for mode in (('raw','safe','unavailable','unknown','forged','authority') if include_controls else ()):
        gg=PromotionGate(g);gg.memory=build(False)[0].memory
        src=deepcopy(promoted['protected']);dest='root'
        content=src['content'] if mode=='raw' else 'Check all required conditions before applying a historical transformation.'
        request={'op':'requestPromotion','request_id':'cross','source_id':src['id'],'destination':dest,'candidate':{'content':content}}
        gg.approvals=[{'source_id':src['id'],'source_digest':digest(src),'destination':dest,'candidate_digest':digest(request['candidate']),'decision':'APPROVED','reviewer':'synthetic-reviewer'}]
        if mode in ('unavailable','unknown'):gg.scanner_modes['secret']=mode
        if mode=='forged':request['candidate']['declassified']=True
        token=gg.issue('employer-x','AGENT' if mode=='authority' else 'SYSTEM_PROMOTION_SERVICE','cross-service')
        result=gg.request_promotion(token,request)
        expected={'raw':'REJECTED_SECURITY','safe':'ADMITTED','unavailable':'UNAVAILABLE','unknown':'REJECTED_SCANNER','forged':'REJECTED_POLICY','authority':'REJECTED_AUTHORITY'}[mode]
        check('cross/'+mode,expected,result['status'])
        check('cross-source/'+mode,src,gg.memory.raw[src['id']])
        entry=gg.memory.raw.get(result['receipt']['entry_id']) if result['receipt'] else None
        if entry:check('cross-status',src['epistemic_status'],entry['epistemic_status'])
        # Replayed success cannot override current scanner unavailability.
        replay=None
        if mode=='safe':
            gg.scanner_modes['secret']='unavailable';replay=gg.request_promotion(token,request)
            check('cross-replay-fail-closed','UNAVAILABLE',replay['status'])
        cross.append({'mode':mode,'response':result,'entry':entry,'replay':replay,'private_audit':deepcopy(gg.audit)})
    # Explicit source diff guard: only provenance/status acceptance and version changed.
    old=(HERE.parent/'track-iii-005/gate.py').read_text()
    part="source['provenance'] not in ('USER_DECLARATION','AGENT_OBSERVATION')\n                or source['epistemic_status']!=('DECLARED' if source['provenance']=='USER_DECLARATION' else 'UNVERIFIED')"
    replacement="source['provenance'] not in ('USER_DECLARATION','AGENT_OBSERVATION','VERIFIED_OUTCOME')\n                or source['epistemic_status'] not in {'USER_DECLARATION':('DECLARED',), 'AGENT_OBSERVATION':('UNVERIFIED',), 'VERIFIED_OUTCOME':('VERIFIED_SUCCESS','VERIFIED_FAILURE')}[source['provenance']]"
    check('extension-exact-source',True,old.count(part)==1 and old.replace(part,replacement).replace('gate-v1','gate-v2')==(HERE/'promotion_v2.py').read_text())
    report={'checks':checks,'origins':origins,'visibility':visibility,'cross_boundary':cross,'human_declaration':declared,'private_admission_audit':a.audit,'private_promotion_audit':gate.audit,'status':'PASS' if all(c['status']=='PASS' for c in checks) else 'FAIL'}
    return a,gate,promoted,report


def retrieve(memory,ec,caller,topic):
    # Topic is fixture routing, never authority or a caller-provided scope list.
    result=memory.exchange(ec,caller,{'op':'search','kind':'RAW','query':'topic:'+topic})['response']
    assert len(wire(result))<=2048
    return result


if __name__=='__main__':
    _,_,_,r=build();save(HERE/'evidence/composition.json',r)
    print(json.dumps({'status':r['status'],'checks':len(r['checks']),'failed':[x['case'] for x in r['checks'] if x['status']=='FAIL']}))
    raise SystemExit(r['status']!='PASS')
