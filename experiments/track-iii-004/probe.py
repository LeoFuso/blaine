"""III.4 finite oracle suite and isolated controls. No live services."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from security import SecurityMemory, ExecutionContext, Caller, Rejected, response, wire, KINDS
from leak_scan import scan

HERE = Path(__file__).resolve().parent


class StructuralOnlyControl(SecurityMemory):
    def allowed_raw(self, ec, entry_id):
        e = self.raw.get(entry_id)
        return bool(e and e['context_id'] in self._tree._lineage(ec.context_id)
                    and entry_id not in self.policy['deny_ids'])


class QueryOnlyCacheControl(SecurityMemory):
    def cached(self, ec, query):
        for c in self.cache:
            if c['query'] == query:
                return self._pack([self.record(i) for i in c['ids']])
        return response('EMPTY')


def save(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + '\n')


def run(variant, f):
    cls = {'correct': SecurityMemory, 'structural-only': StructuralOnlyControl,
           'query-only-cache': QueryOnlyCacheControl}[variant]
    cases, trace = [], []
    observables = {'public': [], 'personal': [], 'employer-x': []}

    def check(name, expected, actual):
        cases.append({'case': name, 'expected': expected, 'actual': actual,
                      'status': 'PASS' if expected == actual else 'FAIL'})

    def bind(m, ctx, role='verifier', identity=None):
        ec = m.begin('execution-' + ctx, ctx)
        return ec, m.participant(ec, identity or role, role)

    def call(name, m, ec, caller, req, audience=None):
        output = m.exchange(ec, caller, req)
        domain = audience or f['context_domains'][ec.context_id]
        index = len(observables[domain])
        observables[domain].append(deepcopy(output))
        trace.append({'case': name, 'execution': asdict(ec), 'audience': domain, 'caller': asdict(caller),
                      'request': deepcopy(req), 'output_index': index, 'output': output,
                      'issued_binding_matches': m._callers.get(caller) is ec,
                      'response_bytes': len(wire(output['response']))})
        check('budget/' + name, True, len(wire(output['response'])) <= 2048)
        return output['response']

    def ids(r):
        return [e['id'] for e in r['entries']]

    def search(kind='RAW', query=''):
        return {'op': 'search', 'kind': kind, 'query': query}

    def full_record(i):
        row = next((e for e in f['entries'] if e['id'] == i), None)
        return dict(row, kind='RAW') if row else next(d for d in f['derived'] if d['id'] == i)

    m = cls(f)
    object_ids = sorted([e['id'] for e in f['entries']] + [d['id'] for d in f['derived']])
    matrix = {}
    for ctx, expected in f['expected_raw'].items():
        ec, caller = bind(m, ctx)
        r = call('search/' + ctx, m, ec, caller, search())
        check('search/' + ctx, expected, ids(r))
        check('search/status/' + ctx, 'SUCCESS_WITH_RESULTS', r['status'])
        expected_all = expected + f['expected_derived'][ctx]
        matrix[ctx] = {}
        for i in object_ids:
            r = call('direct/' + ctx + '/' + i, m, ec, caller, {'op': 'get', 'id': i})
            wanted = response('SUCCESS_WITH_RESULTS', [full_record(i)]) if i in expected_all else response('DENIED')
            check('direct/' + ctx + '/' + i, wanted, r)
            matrix[ctx][i] = r['status']
        for kind in sorted(KINDS):
            r = call('derived/' + ctx + '/' + kind, m, ec, caller, search(kind))
            expected_kind = sorted(i for i in f['expected_derived'][ctx] if full_record(i)['kind'] == kind)
            check('derived/' + ctx + '/' + kind, expected_kind, ids(r))
        r = call('diagnostic/' + ctx, m, ec, caller, {'op': 'debug'})
        check('diagnostic/' + ctx, response('SUCCESS_WITH_RESULTS', [{'id': 'diagnostics',
              'raw_count': len(expected), 'derived_count': len(f['expected_derived'][ctx])}]), r)

    # Explicit graph oracles: edges and nodes both require all source permissions.
    for ctx, start, expected in [
            ('task-personal-a', 'personal-node', ['personal-edge', 'personal-local-node']),
            ('task-personal-a', 'global-node', []),
            ('task-personal-a', 'x-node', None),
            ('task-x-a', 'x-node', ['x-edge', 'x-local-node']),
            ('task-x-a', 'global-node', ['global-x-edge', 'x-node']),
            ('task-x-a', 'personal-node', None)]:
        ec, caller = bind(m, ctx)
        name = 'graph/' + ctx + '/' + start
        r = call(name, m, ec, caller, {'op': 'neighbors', 'id': start})
        check(name, response('DENIED') if expected is None else
              response('SUCCESS_WITH_RESULTS', [full_record(i) for i in expected]) if expected else response('EMPTY'), r)

    # Every request class and write path rejects arbitrary authority metadata.
    pe, pc = bind(m, 'task-personal-a', 'worker')
    before = deepcopy(m.raw)
    fields = {'domain': 'employer-x', 'security_domain': 'employer-x', 'context_kind': 'trusted',
              'classification': 'PUBLIC', 'source': 'USER_DECLARATION', 'provenance': 'USER_DECLARATION',
              'created_by': 'human-x', 'context_id': 'project-x', 'scopes': 'employer-x', 'policy': 'allow'}
    for field, value in fields.items():
        for op, req in [('read', search()), ('write', {'op': 'recordObservation', 'id': 'forgery', 'content': 'invalid'})]:
            name = 'forgery/' + op + '/' + field
            check(name, response('DENIED'), call(name, m, pe, pc, dict(req, **{field: value})))
    for target in ('project-personal', 'task-personal-b', 'task-x-a'):
        req = {'op': 'recordObservation', 'id': 'forgery', 'content': 'invalid', 'target_context': target}
        check('write-target/' + target, response('DENIED'), call('write-target/' + target, m, pe, pc, req))
    check('forgery/no-write', before, m.raw)
    for name, ec, caller in [('execution-copy', ExecutionContext(**asdict(pe)), pc),
                              ('caller-copy', pe, Caller('human-x', 'human'))]:
        check('binding/' + name, response('DENIED'), call('binding/' + name, m, ec, caller, search()))
    foreign = cls(f)
    fe, fc = bind(foreign, 'task-personal-a')
    check('binding/foreign', response('DENIED'), call('binding/foreign', m, fe, fc, search()))

    # Same query, wrong domain/context: fixture cache never selects by query alone.
    cache = {'query': 'cached-query', 'context_id': 'task-x-a', 'domain': 'employer-x',
             'policy_version': 'fixture-v1', 'revision': 0, 'ids': ['x-root-private', 'x-summary']}
    m.cache = [deepcopy(cache)]
    xe, xc = bind(m, 'task-x-a')
    for name, ec, caller, expected in [('own', xe, xc, ['x-root-private', 'x-summary']), ('foreign', pe, pc, [])]:
        r = call('cache/' + name, m, ec, caller, {'op': 'cached', 'query': 'cached-query'})
        check('cache/' + name, response('SUCCESS_WITH_RESULTS', [full_record(i) for i in expected]) if expected else response('EMPTY'), r)
    sibling, sc = bind(m, 'task-x-b')
    check('cache/sibling', response('EMPTY'), call('cache/sibling', m, sibling, sc, {'op': 'cached', 'query': 'cached-query'}))
    m.cache = [dict(cache, context_id='task-personal-a', domain='personal')]
    check('cache/forged-envelope', response('DENIED'), call('cache/forged-envelope', m, pe, pc, {'op': 'cached', 'query': 'cached-query'}))
    m.cache = [dict(cache, revision=-1)]
    check('cache/stale', response('DENIED'), call('cache/stale', m, xe, xc, {'op': 'cached', 'query': 'cached-query'}))
    m.cache = [deepcopy(cache)]

    # Cache freshness metadata must not reveal unrelated write activity.
    fresh=cls(f)
    fresh.cache=[deepcopy(cache)]
    bound,reader=bind(fresh,'task-x-a')
    initial_cache=call('cache-activity/initial',fresh,bound,reader,{'op':'cached','query':'cached-query'})
    for ctx,expected_status in [('task-personal-a','SUCCESS_WITH_RESULTS'),('task-x-b','SUCCESS_WITH_RESULTS'),('task-x-a','DENIED')]:
        writer_ec,writer=bind(fresh,ctx,'worker')
        wr=call('cache-activity/write/'+ctx,fresh,writer_ec,writer,{'op':'recordObservation','id':'activity','content':'synthetic local update'})
        check('cache-activity/write/'+ctx,'RECORDED',wr['status'])
        cr=call('cache-activity/read-after/'+ctx,fresh,bound,reader,{'op':'cached','query':'cached-query'})
        check('cache-activity/read-after/'+ctx,initial_cache if expected_status=='SUCCESS_WITH_RESULTS' else response('DENIED'),cr)
    # Continuous writes and human origin are orthogonal to security.
    sequence = cls(f)
    binding_ids = []
    for ctx, prefix, human_id, target in [('task-personal-a', 'personal', 'human-personal', 'project-personal'),
                                         ('task-x-a', 'x', 'human-x', 'project-x')]:
        ec = sequence.begin('continuous-' + prefix, ctx)
        participants = {role: sequence.participant(ec, human_id if role=='human' else prefix+'-'+role, role)
                        for role in ('human', 'cognition', 'worker', 'verifier')}
        binding_ids.append(ec)
        declaration = {'op': 'declare', 'id': prefix+'-human-declaration', 'content': prefix+'-declaration-literal', 'target_context': target}
        r = call('sequence/' + prefix + '/declare', sequence, ec, participants['human'], declaration)
        check('sequence/' + prefix + '/human', 'USER_DECLARATION', (r['receipt'] or {}).get('provenance'))
        check('sequence/' + prefix + '/human-target', target, (r['receipt'] or {}).get('context_id'))
        check('sequence/' + prefix + '/agent-cannot-declare', response('DENIED'),
              call('sequence/' + prefix + '/agent-declare', sequence, ec, participants['worker'], dict(declaration, id='not-human')))
        check('sequence/' + prefix + '/human-wrong-target', response('DENIED'),
              call('sequence/' + prefix + '/human-wrong-target', sequence, ec, participants['human'],
                   dict(declaration, target_context='project-x' if prefix=='personal' else 'project-personal')))
        check('sequence/' + prefix + '/verifier-write-denied', response('DENIED'),
              call('sequence/' + prefix + '/verifier-write-denied', sequence, ec, participants['verifier'],
                   {'op':'recordObservation','id':'verifier','content':'invalid'}))
        initial = call('sequence/' + prefix + '/initial', sequence, ec, participants['cognition'], search(query=prefix+'-cognition-literal'))
        check('sequence/' + prefix + '/initial-empty', response('EMPTY'), initial)
        for role in ('cognition', 'worker'):
            r = call('sequence/' + prefix + '/' + role + '-write', sequence, ec, participants[role],
                     {'op': 'recordObservation', 'id': prefix+'-'+role+'-observation', 'content': prefix+'-'+role+'-literal'})
            check('sequence/' + prefix + '/' + role + '-receipt', response('RECORDED', receipt={
                'id': ctx+'::'+prefix+'-'+role+'-observation', 'context_id': ctx, 'domain': f['context_domains'][ctx],
                'classification': 'PRIVATE', 'created_by': prefix+'-'+role, 'provenance': 'AGENT_OBSERVATION',
                'epistemic_status': 'UNVERIFIED'}), r)
            if role == 'cognition':
                r = call('sequence/' + prefix + '/worker-read', sequence, ec, participants['worker'], search(query=prefix+'-cognition-literal'))
                check('sequence/' + prefix + '/worker-sees-new', [ctx+'::'+prefix+'-cognition-observation'], ids(r))
        for suffix in ('human-declaration', 'cognition-observation', 'worker-observation'):
            identifier = (target if suffix=='human-declaration' else ctx)+'::'+prefix+'-'+suffix
            r = call('sequence/' + prefix + '/verifier/' + suffix, sequence, ec, participants['verifier'], {'op': 'get', 'id': identifier})
            check('sequence/' + prefix + '/verifier/' + suffix, [identifier], ids(r))
    for ctx in f['context_domains']:
        ec, caller = bind(sequence, ctx)
        for prefix, target, local, sibling in [('personal', 'project-personal', 'task-personal-a', 'task-personal-b'),
                                              ('x', 'project-x', 'task-x-a', 'task-x-b')]:
            for suffix in ('human-declaration', 'cognition-observation', 'worker-observation'):
                i = (target if suffix=='human-declaration' else local)+'::'+prefix+'-'+suffix
                visible = ctx in (target,local,sibling) if suffix=='human-declaration' else ctx==local
                r = call('write-visibility/' + ctx + '/' + i, sequence, ec, caller, {'op': 'get', 'id': i})
                check('write-visibility/' + ctx + '/' + i, 'SUCCESS_WITH_RESULTS' if visible else 'DENIED', r['status'])
    sequence_events = [t for t in trace if t['case'].startswith('sequence/')]
    check('sequence/trusted-shared-binding', True, all(t['issued_binding_matches'] for t in sequence_events)
          and all(len({t['execution']['execution_id'] for t in sequence_events if t['case'].startswith('sequence/'+p+'/')}) == 1
                  for p in ('personal', 'x')))

    # Policy/binding faults: every supported route, including writes, fails closed.
    faults = ['unavailable', 'malformed', 'unknown', 'contradictory', 'missing-domain', 'unknown-domain',
              'contradictory-binding', 'malformed-domain', 'contradictory-classification', 'unknown-entry-domain', 'missing-entry-domain']
    operations = [search(), {'op': 'get', 'id': 'x-root-private'}, {'op': 'neighbors', 'id': 'global-node'},
                  {'op': 'cached', 'query': 'cached-query'}, {'op': 'debug'},
                  {'op': 'recordObservation', 'id': 'fault-write', 'content': 'not persisted'},
                  {'op': 'declare', 'id': 'fault-human', 'content': 'not persisted', 'target_context': 'project-x'}]
    for fault in faults:
        broken = cls(f)
        ec, caller = bind(broken, 'task-x-a', 'worker')
        human = broken.participant(ec, 'human-x', 'human')
        broken.cache = [deepcopy(cache)]
        if fault=='unavailable': broken.policy=None
        if fault=='malformed': broken.policy={}
        if fault=='unknown': broken.policy['grants']['employer-x']=['unknown-domain']
        if fault=='contradictory': broken.policy['grants']['employer-x']=['public','personal']
        if fault=='missing-domain': del broken.context_domains['task-x-a']
        if fault=='unknown-domain': broken.context_domains['task-x-a']='unknown-domain'
        if fault=='contradictory-binding': broken.context_domains['task-x-a']='personal'
        if fault=='malformed-domain': broken.context_domains['task-x-a']=[]
        if fault=='contradictory-classification': broken.raw['x-root-private']['classification']='PUBLIC'
        if fault=='unknown-entry-domain': broken.raw['x-root-private']['domain']='unknown'
        if fault=='missing-entry-domain': del broken.raw['x-root-private']['domain']
        before = deepcopy(broken.raw)
        for req in operations:
            name='policy/' + fault + '/' + req['op']
            r=call(name,broken,ec,human if req['op']=='declare' else caller,req,audience='employer-x')
            check(name,response('UNAVAILABLE' if fault=='unavailable' else 'DENIED'),r)
        check('policy/no-write/'+fault,before,broken.raw)

    # Observable equivalence when hidden records/relationships do not exist.
    reduced=deepcopy(f)
    allowed=set(f['expected_raw']['task-personal-a'])
    reduced['entries']=[e for e in f['entries'] if e['id'] in allowed]
    reduced['derived']=[d for d in f['derived'] if d['id'] in f['expected_derived']['task-personal-a']]
    reduced['policy']['deny_ids']=[]
    small=cls(reduced)
    se,sp=bind(small,'task-personal-a')
    for op,req in [('debug',{'op':'debug'}),('hidden-get',{'op':'get','id':'x-root-private'}),
                   ('hidden-search',search(query='employer-x-secret-memory')),
                   ('graph',{'op':'neighbors','id':'global-node'}),('empty',search(query='absent'))]:
        a=call('noninterference/full/'+op,m,pe,pc,req)
        b=call('noninterference/reduced/'+op,small,se,sp,req)
        check('noninterference/'+op,b,a)
    # A foreign ID cannot collide in the current context's write namespace.
    collision_results=[]
    for label,fixture in [('full',f),('hidden-removed',reduced)]:
        collision_fixture=deepcopy(fixture)
        if label=='full':
            collision_fixture['entries'].append(deepcopy(f['collision_entry']))
        cm=cls(collision_fixture)
        ce,cc=bind(cm,'task-personal-a','worker')
        result=call('collision/'+label,cm,ce,cc,{'op':'recordObservation','id':'opaque-collision-key','content':'caller supplied an ID'})
        collision_results.append(result)
        check('collision/'+label,'RECORDED',result['status'])
    check('collision/noninterference',collision_results[0],collision_results[1])
    # The collision identifier is explicitly public/caller-known in the fixture;
    # its protected record and payload remain invisible in both responses.
    # Trusted read boundaries still narrow otherwise domain-permitted ancestors.
    bounded=deepcopy(f)
    next(n for n in bounded['nodes'] if n['id']=='project-personal')['inherit_parent']=False
    bm=cls(bounded)
    be,bc=bind(bm,'task-personal-a')
    r=call('lineage/closed-boundary',bm,be,bc,search())
    check('lineage/closed-boundary',['project-personal-memory','task-personal-a-memory'],ids(r))
    # Labels do not create authority; a real global policy refusal is also honored.
    relabeled=deepcopy(f)
    for node in relabeled['nodes']: node['kind']='trusted'
    lm=cls(relabeled)
    le,lc=bind(lm,'task-personal-a')
    check('labels/no-authority',f['expected_raw']['task-personal-a'],ids(call('labels/no-authority',lm,le,lc,search())))
    lm.policy['grants']['personal']=['personal']
    check('policy/public-opt-out',[i for i in f['expected_raw']['task-personal-a'] if i!='global-engineering-memory'],
          ids(call('policy/public-opt-out',lm,le,lc,search())))
    unavailable=cls(f)
    ue,uc=bind(unavailable,'task-personal-a')
    unavailable.available=False
    check('state/capability-unavailable',response('UNAVAILABLE'),call('state/capability-unavailable',unavailable,ue,uc,search()))
    # Entire structure remains validated even behind a closed read edge.
    invalid=deepcopy(f)
    next(n for n in invalid['nodes'] if n['id']=='project-x').update(parent_id='task-x-a',inherit_parent=False)
    try:
        cls(invalid)
        outcome='accepted'
    except Rejected as exc:
        outcome=str(exc)
    check('structure/cycle-behind-boundary','cycle',outcome)
    invalid=deepcopy(f)
    invalid['derived'][0]['source_ids']=['missing-source']
    try:
        cls(invalid)
        outcome='accepted'
    except Rejected as exc:
        outcome=str(exc)
    check('derivation/unknown-source','invalid_derivation',outcome)
    invalid=deepcopy(f)
    next(d for d in invalid['derived'] if d['id']=='cross-edge')['source_ids']=['personal-root-private']
    try:
        cls(invalid)
        outcome='accepted'
    except Rejected as exc:
        outcome=str(exc)
    check('derivation/edge-missing-source','invalid_derivation',outcome)
    leakage=scan(observables,f['protected_literals'])
    check('literal-leakage','PASS',leakage['status'])
    return {'cases':cases,'trace':trace,'visibility_matrix':matrix,'observables':observables,
            'leakage':leakage,'continuous_final_records':list(sequence.raw.values())}


def verdict(report):
    failed=[c['case'] for c in report['cases'] if c['status']=='FAIL']
    return {'status':'FAIL' if failed else 'PASS','checks':len(report['cases']),'failed':len(failed),'failed_cases':failed}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--variant',choices=['correct','structural-only','query-only-cache'],default='correct')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    fixture=json.loads((HERE/'fixtures.json').read_text())
    result=run(args.variant,fixture)
    save(args.output/'results.json',result)
    summary=verdict(result)
    if args.variant=='correct':
        save(args.output/'observables.json',result['observables'])
        save(args.output/'literal-leakage.json',result['leakage'])
        controls={}
        for variant in ('structural-only','query-only-cache'):
            with tempfile.TemporaryDirectory(prefix='blaine-iii4-') as temp:
                child=subprocess.run([sys.executable,str(HERE/'probe.py'),'--variant',variant,'--output',temp],capture_output=True,text=True,timeout=30)
                control=json.loads((Path(temp)/'results.json').read_text())
                save(args.output/(variant+'.json'),control)
                controls[variant]={'exit_code':child.returncode,'suite':verdict(control),'leaking_outputs':control['leakage']['leaking_outputs'],
                                   'stdout':child.stdout,'stderr':child.stderr}
        restored=run('correct',fixture)
        save(args.output/'restored.json',restored)
        caught=all(c['exit_code']==1 and c['leaking_outputs']>0 and 'literal-leakage' in c['suite']['failed_cases'] for c in controls.values())
        summary.update(controls=controls,controls_detected=caught,restored_equal=restored==result,
                       max_response_bytes=max(t['response_bytes'] for t in result['trace']),
                       source_sha256={p:hashlib.sha256((HERE/p).read_bytes()).hexdigest() for p in ['security.py','probe.py','leak_scan.py','verify.py','fixtures.json','../track-iii-002/evaluator.py','../track-iii-003/capability.py']},
                       task_submission={'submitted':False,'task_id':None},III_5_started=False)
        if not caught or restored!=result: summary['status']='FAIL'
    save(args.output/'summary.json',summary)
    print(json.dumps({k:summary[k] for k in ('status','checks','failed')}))
    return int(summary['status']!='PASS')


if __name__=='__main__':
    raise SystemExit(main())
