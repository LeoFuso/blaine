"""Offline admission only. Trusted bindings/approvals; no production API or DLP."""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'track-iii-004'))
from security import SecurityMemory, wire


def digest(value):
    return hashlib.sha256(wire(value)).hexdigest()


def result(status, receipt=None):
    return {'status':status,'receipt':receipt,'diagnostic':{'status':status}}


@dataclass(frozen=True,eq=False)
class PromotionBinding:
    """Only tokens registered by trusted harness issuance have authority."""


def scan(name,content,source,manifest,mode='normal'):
    if mode=='crash': raise RuntimeError('synthetic crash')
    if mode=='timeout': raise TimeoutError('synthetic timeout; no real timer')
    if mode=='malformed': return {'clean':True}
    state={'unavailable':'UNAVAILABLE','unknown':'UNKNOWN','cannot_evaluate':'UNEVALUABLE'}.get(mode)
    matches=[]
    if not state:
        if name=='secret':
            matches=[m.group() for pattern in manifest[name] for m in re.finditer(pattern,content)]
        elif name=='source_fragment':
            tokens=lambda text: re.findall(r'[a-z0-9]+',text.lower())
            original=tokens(source); candidate=' '.join(tokens(content))
            matches=[' '.join(original[i:i+8]) for i in range(max(0,len(original)-7))
                     if ' '.join(original[i:i+8]) in candidate]
        else:
            matches=[literal for literal in manifest[name] if literal.lower() in content.lower()]
        state='MATCH' if matches else 'CLEAN'
    return {'scanner':name,'version':'synthetic-v1','status':state,'matches':matches}


class PromotionGate:
    def __init__(self,fixture):
        self.f=deepcopy(fixture)
        self.memory=SecurityMemory(self.f['memory'])
        self.policy=deepcopy(self.f['promotion_policy'])
        self.approvals=deepcopy(self.f['approvals'])
        self.bindings={}
        self.audit=[]  # Protected harness-only audit, never a destination API.
        self.receipts={}  # Only successful, destination-scoped receipts.
        self.replays={}
        self.scanner_modes={}
        self.available=True

    def issue(self,context,role,name):
        token=PromotionBinding()
        self.bindings[token]={'execution':self.memory.begin(name,context),'role':role,'principal':name}
        return token

    def scanner_admissible(self,report,name):
        return (isinstance(report,dict) and set(report)=={'scanner','version','status','matches'}
                and report['scanner']==name and report['version']=='synthetic-v1'
                and report['status']=='CLEAN' and report['matches']==[])

    def request_promotion(self,token,request):
        binding=self.bindings.get(token) if isinstance(token,PromotionBinding) else None
        internal={'gate_version':'gate-v1','request':deepcopy(request),'scanners':[]}
        def finish(status,receipt=None):
            internal['status']=status
            internal['receipt']=deepcopy(receipt)
            self.audit.append(internal)
            return result(status,receipt)
        # Authority denial precedes source lookup: an agent cannot probe existence.
        if not binding or binding['role']!='SYSTEM_PROMOTION_SERVICE':
            return finish('REJECTED_AUTHORITY')
        ec=binding['execution']
        internal.update(audit_domain=self.memory._security[ec],principal=binding['principal'])
        if (not isinstance(request,dict) or set(request)!={'op','request_id','source_id','destination','candidate'}
                or request['op']!='requestPromotion' or not isinstance(request['candidate'],dict)
                or set(request['candidate'])!={'content'}
                or not isinstance(request['candidate']['content'],str)
                or not 0<len(request['candidate']['content'].encode())<=1024
                or any(not isinstance(request[k],str) or not 0<len(request[k])<=80 for k in ('request_id','source_id','destination'))):
            return finish('REJECTED_POLICY')
        if not self.available or self.policy is None:
            return finish('UNAVAILABLE')
        if self.policy!=self.f['promotion_policy']:
            return finish('REJECTED_POLICY')
        state=self.memory.policy_state(ec)
        if state or not self.memory.available:
            return finish('UNAVAILABLE' if state=='UNAVAILABLE' or not self.memory.available else 'REJECTED_POLICY')
        source=self.memory.raw.get(request['source_id'])
        # Source must belong to the current bound context, not just be named.
        if (not source or source['context_id']!=ec.context_id or not self.memory.allowed(ec,source['id'])):
            return finish('REJECTED_POLICY')
        internal['source']=deepcopy(source)
        dest=request['destination']
        parent=self.memory._tree._nodes[ec.context_id].parent_id
        if dest!=parent or [ec.context_id,dest] not in self.policy['routes']:
            return finish('REJECTED_POLICY')
        if (source['provenance'] not in ('USER_DECLARATION','AGENT_OBSERVATION')
                or source['epistemic_status']!=('DECLARED' if source['provenance']=='USER_DECLARATION' else 'UNVERIFIED')
                or source['epistemic_status'] not in self.policy['admissible_statuses']):
            return finish('REJECTED_POLICY')
        candidate=request['candidate']
        destination_domain=self.memory.context_domains[dest]
        cross=source['domain']!=destination_domain
        internal.update(destination=dest,cross_boundary=cross,source_digest=digest(source),candidate_digest=digest(candidate),policy_version=self.policy['version'])
        if cross:
            approval=next((a for a in self.approvals if a=={
                'source_id':source['id'],'source_digest':digest(source),'destination':dest,
                'candidate_digest':digest(candidate),'decision':'APPROVED','reviewer':'synthetic-reviewer'}),None)
            if not approval:
                return finish('REJECTED_SECURITY')
            internal['approval']=deepcopy(approval)
        # Secret-like test tokens are never reusable, including same-domain writes.
        required=self.f['scanner_names'] if cross else ['secret']
        reports=[]
        for name in required:
            try:
                report=scan(name,candidate['content'],source['content'],self.f['scanner_manifest'],self.scanner_modes.get(name,'normal'))
            except TimeoutError:
                report={'status':'TIMEOUT'}
            except Exception as exc:
                report={'status':'CRASH','error_type':type(exc).__name__}
            internal['scanners'].append({'name':name,'report':deepcopy(report)})
            reports.append((name,report))
        bad=[r for name,r in reports if not self.scanner_admissible(r,name)]
        if bad:
            if any(isinstance(r,dict) and r.get('status')=='UNAVAILABLE' for r in bad):
                return finish('UNAVAILABLE')
            if any(not isinstance(r,dict) or r.get('status')!='MATCH' for r in bad):
                return finish('REJECTED_SCANNER')
            return finish('REJECTED_SECURITY')
        # Replay lookup is after authority, policy, current source and scanners.
        key=(ec.context_id,binding['principal'],request['request_id'])
        fingerprint=digest({'request':request,'source':source,'policy':self.policy})
        if key in self.replays:
            previous=self.replays[key]
            if previous['fingerprint']!=fingerprint:
                return finish('REJECTED_POLICY')
            return finish('ADMITTED',deepcopy(previous['receipt']))
        # No source hash, caller request ID, global counter or private provenance IDs.
        n=1
        while dest+'::admission-'+str(n) in self.memory.raw:
            n+=1
        entry_id=dest+'::admission-'+str(n)
        entry={'id':entry_id,'context_id':dest,'domain':destination_domain,
               'classification':'PUBLIC' if destination_domain=='public' else 'PRIVATE',
               'content':candidate['content'],'provenance':source['provenance'],
               'epistemic_status':source['epistemic_status'],'created_by':'promotion-gate',
               'admission':{'kind':'PROMOTED_REPRESENTATION','gate_version':'gate-v1','policy_version':self.policy['version']}}
        # Atomic for this sequential in-process experiment; no durable transaction claim.
        self.memory._tree.handle(self.memory._tree.bind(dest),{'op':'write','entry_id':entry_id,'content':wire(entry).decode()})
        self.memory.raw[entry_id]=entry
        receipt={'status':'ADMITTED','entry_id':entry_id,'provenance':source['provenance'],
                 'epistemic_status':source['epistemic_status'],'gate_version':'gate-v1','policy_version':self.policy['version']}
        self.receipts[entry_id]=deepcopy(receipt)
        self.replays[key]={'fingerprint':fingerprint,'receipt':deepcopy(receipt)}
        return finish('ADMITTED',receipt)

    def destination_view(self,ec,caller):
        # Reuse the governed memory capability, not an unscoped store projection.
        fetched=self.memory.exchange(ec,caller,{'op':'search','kind':'RAW','query':''})
        r=fetched['response']
        ids={e['id'] for e in r['entries']}
        return {'memory':fetched,'receipts':[deepcopy(v) for i,v in sorted(self.receipts.items()) if i in ids],
                'visible_revision':self.memory.visible_revision(ec) if r['status'] in ('SUCCESS_WITH_RESULTS','EMPTY') else None}
