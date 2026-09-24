"""III.6 bounded outcome admission, not production contracts or semantic entailment."""
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'track-iii-005'))
from gate import PromotionGate, digest, wire
from security import SecurityMemory


@dataclass(frozen=True,eq=False)
class AdmissionBinding:
    pass


def response(status,receipt=None):
    return {'status':status,'receipt':receipt,'diagnostic':{'status':status}}


class OutcomeAdmission:
    def __init__(self,fixture):
        f=deepcopy(fixture)
        self.memory=SecurityMemory(f['memory'])
        self.executions=f['executions']
        self.envelopes=f['envelopes']
        self.evidence=f['evidence']
        self.catalog=f['support_catalog']
        self.bindings={}
        self.audit=[]
        self.provenance={}
        self.replays={}
        self.available=True

    def issue(self,execution_id):
        """Trusted harness only. Caller requests never select execution/context."""
        spec=self.executions[execution_id]
        ec=self.memory.begin(execution_id,spec['context_id'])
        token=AdmissionBinding()
        self.bindings[token]=ec
        return token

    def evidence_value(self,row,requirement):
        return row['result'] if row else 'MISSING'

    def resolve(self,ec):
        """Resolve trusted records; validate identity/requirements before classifying."""
        spec=self.executions[ec.execution_id]
        envelope=deepcopy(self.envelopes.get(ec.execution_id))
        bundle={'execution_id':ec.execution_id,'context_id':ec.context_id,'domain':spec['domain'],
                'requirements':deepcopy(spec['requirements']),'contract_ref':spec['contract_ref'],
                'envelope':envelope,'evidence':[]}
        if envelope is None:
            return 'INCOMPLETE',bundle
        expected_fields={'id','execution_id','context_id','domain','status','required_evidence','contract_ref'}
        if (not isinstance(envelope,dict) or set(envelope)!=expected_fields
                or not isinstance(envelope['id'],str) or not envelope['id']
                or envelope['execution_id']!=ec.execution_id or envelope['context_id']!=ec.context_id
                or envelope['domain']!=spec['domain'] or spec['domain']!=self.memory._security[ec]
                or envelope['required_evidence']!=[q['id'] for q in spec['requirements']]
                or envelope['contract_ref']!=spec['contract_ref']
                or envelope['status'] not in ('SUCCEEDED','FAILED','UNKNOWN','INCOMPLETE','CANCELLED')):
            return 'CONTRADICTORY',bundle
        values=[]
        for q in spec['requirements']:
            row=deepcopy(self.evidence.get(q['id']))
            bundle['evidence'].append(row)
            if row is not None:
                valid_results={'PRESENT','ABSENT','MISSING','UNKNOWN','UNAVAILABLE','NOT_RUN'} if q['kind']=='ARTIFACT' else {'PASS','FAIL','MISSING','UNKNOWN','UNAVAILABLE','NOT_RUN'}
                if (not isinstance(row,dict) or set(row)!={'id','execution_id','context_id','domain','kind','result','verifier_id','facts','raw'}
                        or any(row[k]!=v for k,v in [('id',q['id']),('execution_id',ec.execution_id),('context_id',ec.context_id),('domain',spec['domain']),('kind',q['kind'])])
                        or not isinstance(row['result'],str) or row['result'] not in valid_results
                        or not isinstance(row['verifier_id'],str) or not row['verifier_id']
                        or not isinstance(row['facts'],list) or any(not isinstance(x,str) for x in row['facts'])
                        or not isinstance(row['raw'],str)):
                    return 'CONTRADICTORY',bundle
            values.append(self.evidence_value(row,q))
        if 'UNAVAILABLE' in values:
            return 'UNAVAILABLE',bundle
        contract=values[[q['id'] for q in spec['requirements']].index(spec['contract_ref'])]
        failures=any(v in ('FAIL','ABSENT') for v in values)
        if (contract=='PASS' and failures or envelope['status']=='SUCCEEDED' and failures
                or envelope['status']=='FAILED' and contract=='PASS'):
            return 'CONTRADICTORY',bundle
        if envelope['status']=='SUCCEEDED' and all(v==q['success'] for v,q in zip(values,spec['requirements'])):
            return 'VERIFIED_SUCCESS',bundle
        noncontract_failure=any(v in ('FAIL','ABSENT') and q['id']!=spec['contract_ref'] for v,q in zip(values,spec['requirements']))
        if envelope['status']=='FAILED' and contract=='FAIL' and noncontract_failure:
            return 'VERIFIED_FAILURE',bundle
        return 'INCOMPLETE',bundle

    def qualified_outcome(self,classification,claim):
        # Worker/model claims have no effect on the trusted classification.
        return classification

    def admit(self,token,request):
        ec=self.bindings.get(token) if isinstance(token,AdmissionBinding) else None
        audit={'version':'outcome-v1','untrusted_request':deepcopy(request)}
        def finish(status,receipt=None):
            audit['status']=status;self.audit.append(deepcopy(audit))
            return response(status,receipt)
        if not ec:
            return finish('REJECTED_UNSUPPORTED')
        audit.update(execution_id=ec.execution_id,context_id=ec.context_id,domain=self.memory._security[ec])
        if (not isinstance(request,dict) or set(request)!={'op','request_id','worker_claim','candidate'}
                or request['op']!='admitReflection' or not isinstance(request['request_id'],str)
                or not 0<len(request['request_id'])<=80
                or not isinstance(request['candidate'],dict) or set(request['candidate'])!={'content','intent'}
                or not isinstance(request['candidate']['content'],str) or not 0<len(request['candidate']['content'].encode())<=1024
                or request['candidate']['intent'] not in ('SUCCESS','FAILURE','OBSERVATION')
                or not isinstance(request['worker_claim'],dict) or set(request['worker_claim'])!={'status','text'}
                or request['worker_claim']['status'] not in ('SUCCESS','FAILURE','UNKNOWN')
                or not isinstance(request['worker_claim']['text'],str) or len(request['worker_claim']['text'])>1024):
            return finish('REJECTED_UNSUPPORTED')
        if not self.available or not self.memory.available:
            return finish('UNAVAILABLE')
        policy=self.memory.policy_state(ec)
        if policy:
            return finish('UNAVAILABLE' if policy=='UNAVAILABLE' else 'REJECTED_UNSUPPORTED')
        classification,bundle=self.resolve(ec)
        audit['authoritative']=deepcopy(bundle)
        audit['resolved_classification']=classification
        classification=self.qualified_outcome(classification,request['worker_claim'])
        audit['effective_classification']=classification
        if classification in ('CONTRADICTORY','UNAVAILABLE'):
            return finish('REJECTED_CONTRADICTORY' if classification=='CONTRADICTORY' else 'UNAVAILABLE')
        candidate=request['candidate']
        support=next((x for x in self.catalog[ec.execution_id] if x['candidate']==candidate),None)
        if not support:
            return finish('REJECTED_UNSUPPORTED')
        facts={v for e in bundle['evidence'] if isinstance(e,dict) for v in e.get('facts',[])}
        if not set(support['facts'])<=facts:
            return finish('REJECTED_UNSUPPORTED')
        desired={'SUCCESS':'VERIFIED_SUCCESS','FAILURE':'VERIFIED_FAILURE','OBSERVATION':'UNVERIFIED'}[candidate['intent']]
        if desired!='UNVERIFIED' and classification!=desired:
            return finish('REJECTED_UNSUPPORTED')
        decision='RETAINED_UNVERIFIED' if desired=='UNVERIFIED' else 'ADMITTED_'+desired
        audit['candidate_support']=deepcopy(support)
        fingerprint=digest({'candidate':candidate,'authoritative':bundle})
        key=(ec.execution_id,request['request_id'])
        if key in self.replays:
            old=self.replays[key]
            if old['fingerprint']!=fingerprint:
                return finish('REJECTED_UNSUPPORTED')
            return finish(decision,deepcopy(old['receipt']))
        n=1
        while ec.context_id+'::reflection-'+str(n) in self.memory.raw:n+=1
        entry_id=ec.context_id+'::reflection-'+str(n)
        domain=self.memory._security[ec]
        entry={'id':entry_id,'context_id':ec.context_id,'domain':domain,'classification':'PRIVATE',
               'content':candidate['content'],'created_by':'outcome-admission',
               'provenance':'AGENT_OBSERVATION' if desired=='UNVERIFIED' else 'VERIFIED_OUTCOME',
               'epistemic_status':desired,'admission':{'kind':'REFLECTION_CANDIDATE','version':'outcome-v1'}}
        self.memory._tree.handle(self.memory._executions[ec],{'op':'write','entry_id':entry_id,'content':wire(entry).decode()})
        self.memory.raw[entry_id]=entry
        receipt={'entry_id':entry_id,'provenance':entry['provenance'],'epistemic_status':desired,'version':'outcome-v1'}
        self.provenance[entry_id]={'derived_from':deepcopy(bundle),'candidate_support':deepcopy(support),
                                   'snapshot_digest':digest(bundle),'admission_version':'outcome-v1'}
        self.replays[key]={'fingerprint':fingerprint,'receipt':deepcopy(receipt)}
        return finish(decision,receipt)
