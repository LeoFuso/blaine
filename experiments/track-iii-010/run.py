"""Trusted deterministic harness. Never imports the independent checker."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from receiver import receive, wire
D = Path(__file__).resolve().parent


def load(p): return json.loads(Path(p).read_text())
def save(p,v): Path(p).write_text(json.dumps(v,indent=2,sort_keys=True,ensure_ascii=False)+'\n')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def changed(base, change):
    s = copy.deepcopy(base)
    if change == 'NARROW_POLICY':
        s['policy_revision'] = 'P2'
        s['policy']['deny_ids'] = ['old-rule']
    elif change == 'REPARENT':
        s['topology_revision'] = 'T2'
        next(n for n in s['nodes'] if n['id']=='task-main')['parent_id'] = 'project-new'
    elif change == 'MISSING_EVIDENCE':
        s['current_evidence'] = {}
    return s


def export(response, stdout=None, stderr='', exit_code=0):
    stdout = wire(response)+'\n' if stdout is None else stdout
    return dict(response=response,stdout=stdout,stderr=stderr,exit_code=exit_code,
                response_bytes=len(stdout.encode()))


class Harness:
    def __init__(self, directory, mutation):
        self.directory=directory
        self.mutation=mutation
        self.attestations=[]
        self.number=0

    def call(self, envelope, state, process=False, checkpoint=False, participant='worker'):
        # Local boundaries also destroy object identity via JSON on both sides.
        raw = envelope if isinstance(envelope,str) else wire(envelope)
        if not process:
            owned = json.loads(wire(state))
            response = receive(raw,owned,participant=participant,mutation=self.mutation)
            return export(json.loads(wire(response))), owned, None
        self.number += 1
        stem = self.directory / str(self.number)
        state_path=stem.with_suffix('.state.json'); input_path=stem.with_suffix('.transfer.json')
        proof_path=stem.with_suffix('.proof.json'); checkpoint_path=stem.with_suffix('.checkpoint.json')
        save(state_path,state); input_path.write_text(raw)
        command=[sys.executable,str(D/'receiver.py'),'--state',str(state_path),
                 '--envelope',str(input_path),'--attestation',str(proof_path),
                 '--participant',participant]
        if checkpoint: command += ['--checkpoint',str(checkpoint_path)]
        if self.mutation: command += ['--mutation',self.mutation]
        proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        stdout,stderr=proc.communicate(timeout=15)
        attestation=load(proof_path)
        self.attestations.append(dict(operation=self.number,parent_pid=os.getpid(),
                                     launched_pid=proc.pid,child=attestation))
        e=export(json.loads(stdout),stdout,stderr,proc.returncode)
        e['process']={'separate_process':proc.pid!=os.getpid(),
                      'child_report_matches_popen':attestation['pid']==proc.pid,
                      'parent_pid_matches':attestation['ppid']==os.getpid(),
                      'operation':self.number,'writer_exited_before_return':proc.poll() is not None}
        return e, None, load(checkpoint_path) if checkpoint else None


def execute(output,mutation):
    output.mkdir(parents=True,exist_ok=True)
    base=load(D/'state.json'); cases=load(D/'cases.json')
    with tempfile.TemporaryDirectory(prefix='iii10-') as temporary:
        h=Harness(Path(temporary),mutation)
        results=[]
        for c in cases:
            state=changed(base,c['state_change']); e=copy.deepcopy(c['envelope'])
            phases=[]
            if c['group']=='CHECKPOINT_RESUME':
                start=copy.deepcopy(cases[0]['envelope'])
                before,_,checkpoint=h.call(start,base,process=True,checkpoint=True)
                phases.append(dict(stage='before_checkpoint',export=before,state_change='UNCHANGED'))
                checkpoint.update({k:v for k,v in e.items() if k!='claims'})
                checkpoint['claims'].update(e['claims'])
                e=checkpoint  # Freshly parsed file after checkpoint writer has exited.
            elif c['id']=='C4':
                before,_,_=h.call(e,base,process=True)
                phases.append(dict(stage='prior_success',export=before,state_change='UNCHANGED'))
            process=c['group']!='LOCAL_HANDOFF'
            actual,_,_=h.call(e,state,process=process,participant='cognition' if c['id']=='A1' else 'worker')
            phases.append(dict(stage='received',export=actual,state_change=c['state_change']))
            if c['id']=='A1':
                for participant in ['worker','verifier']:
                    value,_,_=h.call(e,state,participant=participant)
                    phases.append(dict(stage=participant,export=value,state_change='UNCHANGED'))
            # Identical trusted-state replay, including current denials.
            replay,_,_=h.call(e,state,process=process)
            phases.append(dict(stage='same_state_replay',export=replay,state_change=c['state_change']))
            results.append(dict(id=c['id'],group=c['group'],envelope=e,trusted_state=state,phases=phases))

        probes=[]
        def probe(name,env=None,state=None,status='INVALID_CONTEXT',ids=None,participant='worker',process=False):
            ee=copy.deepcopy(cases[0]['envelope']) if env is None else env
            ss=copy.deepcopy(base) if state is None else state
            out,after,_=h.call(ee,ss,process=process,participant=participant)
            probes.append(dict(name=name,envelope=ee,trusted_state=ss,expected_status=status,
                               expected_ids=ids if ids is not None else [],export=out))
            return out,after
        def request(op):
            ee=copy.deepcopy(cases[0]['envelope']); ee['claims']['request']=op; return ee
        probe('empty',request({'op':'search','query':'NO-MATCH-LITERAL'}),status='EMPTY')
        for id_ in ['protected-x','protected-root','sibling-private','descendant-private','missing-id']:
            probe('direct-'+id_,request({'op':'get','id':id_}),status='DENIED')
        for field,value in [('target_context','project-old'),('provenance','USER_DECLARATION'),('destination_context','root')]:
            req={'op':'recordObservation','id':'note-1','content':'Post-start scoped observation.',field:value}
            probe('write-forged-'+field,request(req),status='DENIED')
        write,after=probe('scoped-write',request({'op':'recordObservation','id':'note-1','content':'Post-start scoped observation.'}),
                          status='SUCCESS',ids=['task-main::note-1'])
        probe('continuous-verifier',state=after,status='SUCCESS',participant='verifier',
              ids=sorted(cases[0]['expected_ids']+['task-main::note-1']),process=True)
        for context,ids in [('project-old',['old-rule','public-rule']),('attempt',sorted(cases[0]['expected_ids']+['descendant-private','task-main::note-1']))]:
            ss=copy.deepcopy(after); ss['bindings']['execution-main']['context_id']=context
            ee=copy.deepcopy(cases[0]['envelope']); ee['context_id']=context
            probe('write-visibility-'+context,ee,ss,status='SUCCESS',ids=ids)
        for field,value in [('policy_ref','unknown'),('topology_ref','unknown'),('binding_ref','foreign'),('execution_id','foreign')]:
            ee=copy.deepcopy(cases[0]['envelope']); ee[field]=value
            probe('invalid-'+field,ee,status='DENIED' if field in ('binding_ref','execution_id') else 'INVALID_CONTEXT',process=True)
        probe('malformed-json','{"execution_id":')
        probe('duplicate-field-json','{"execution_id":"one","execution_id":"two"}')
        for corruption in ['missing-parent','cycle','duplicate-id','self-parent']:
            ss=copy.deepcopy(base)
            if corruption=='missing-parent': ss['nodes'][-1]['parent_id']='absent'
            elif corruption=='cycle': ss['nodes'][-2]['parent_id']='task-x'
            elif corruption=='self-parent': ss['nodes'][-1]['parent_id']='task-x'
            else: ss['nodes'].append(copy.deepcopy(ss['nodes'][-1]))
            probe('hidden-topology-'+corruption,state=ss)
        for corruption in ['unavailable','malformed','unknown','contradictory']:
            ss=copy.deepcopy(base)
            if corruption=='unavailable': ss['policy']=None
            elif corruption=='malformed': ss['policy']={'grants':[]}
            elif corruption=='unknown': ss['policy_revision']='unknown'
            else: ss['context_domains']['task-main']='employer-x'
            probe('policy-'+corruption,state=ss,status='UNAVAILABLE' if corruption=='unavailable' else 'INVALID_CONTEXT')
        # Exercise deterministic whole-response bounding with eligible oversized content.
        ss=copy.deepcopy(base)
        ss['entries'] += [dict(id=f'zz-bulk-{i}',context_id='task-main',domain='personal',
                              content='Bounded synthetic observation '+('λ'*240),
                              provenance='AGENT_OBSERVATION',semantic_status='UNVERIFIED') for i in range(8)]
        probe('budget',state=ss,status='SUCCESS',ids=cases[0]['expected_ids'])
        # Exact-size edge: false is one byte longer than true in JSON.
        ss=copy.deepcopy(base)
        ss['entries']=[dict(id='edge',context_id='task-main',domain='personal',content='',
                           provenance='AGENT_OBSERVATION',semantic_status='UNVERIFIED')]
        skeleton=dict(status='SUCCESS',entries=ss['entries'],partial=True,
                      receipt=dict(context_id='task-main',trace_id='trace-main',parent_operation_id='op-origin'),
                      diagnostic={'code':'SUCCESS'})
        ss['entries'][0]['content']='x'*(2048-len((wire(skeleton)+'\n').encode()))
        probe('budget-marker-edge',state=ss,status='SUCCESS',ids=[])
        save(output/'results.json',dict(cases=results,probes=probes,mutation=mutation))
        save(output/'process-attestations.json',h.attestations)
        # Only exports here are caller-visible. Full results contain protected fixture audit.
        exports=[dict(case=c['id'],stage=p['stage'],state_change=p['state_change'],export=p['export'])
                 for c in results for p in c['phases']]
        exports += [dict(probe_number=i,export=p['export']) for i,p in enumerate(probes)]
        save(output/'exports.json',exports)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--mutation',choices=['serialized-scope','stale-policy','serialized-provenance'])
    args=ap.parse_args()
    freeze=load(D/'evidence/fixture-freeze.json')
    assert all(sha(D/n)==s for n,s in freeze['sha256'].items()), 'Frozen corpus changed'
    execute(args.output,args.mutation)


if __name__=='__main__': main()
