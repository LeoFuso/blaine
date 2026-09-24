"""Deterministic III.3 sequence and controls. No production runtime integration."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from capability import Caller, ExecutionContext, Memory, Rejected, response, wire, BUDGET

HERE = Path(__file__).resolve().parent


def save(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n')


class TrustProvenanceControl(Memory):
    """Unsafe isolated test variant; never installed in the capability."""
    def handle(self, execution, caller, request):
        if request.get('op') == 'recordObservation' and request.get('provenance') == 'USER_DECLARATION':
            clean = {k: v for k, v in request.items() if k != 'provenance'}
            result = super().handle(execution, caller, clean)
            if result['status'] == 'RECORDED':
                old = self._tree._entries[request['entry_id']]
                data = json.loads(old.content)
                data.update(provenance='USER_DECLARATION', epistemic_status='DECLARED')
                self._tree._entries[old.id] = type(old)(old.id, old.context_id, wire(data).decode())
                result['receipt'].update(provenance='USER_DECLARATION', epistemic_status='DECLARED')
            return result
        return super().handle(execution, caller, request)


def run(variant, f):
    cases, trace, sequence_bindings = [], [], []
    cls = TrustProvenanceControl if variant == 'forged-provenance' else Memory

    def check(name, expected, actual):
        cases.append({'case': name, 'expected': expected, 'actual': actual,
                      'status': 'PASS' if expected == actual else 'FAIL'})

    def setup(entries=None, nodes=None):
        m = cls(deepcopy(f['nodes'] if nodes is None else nodes),
                deepcopy(f['entries'] if entries is None else entries))
        ec = m.begin(**f['execution'])
        callers = {c['caller_class']: m.participant(ec, **c) for c in f['callers']}
        return m, ec, callers

    def call(name, m, ec, caller, request, frozen=None):
        if name in ('cognition-read', 'cognition-write', 'worker-read', 'worker-write', 'verifier-read'):
            sequence_bindings.append(ec)
        result = deepcopy(frozen) if frozen is not None else m.handle(ec, caller, request)
        trace.append({'operation': name, 'execution': asdict(ec), 'caller': asdict(caller),
                      'request': deepcopy(request), 'response': deepcopy(result),
                      'wire_bytes': len(wire(result)), 'delivery': 'initial_snapshot' if frozen is not None else 'capability'})
        check('budget/' + name, True, len(wire(result)) <= BUDGET)
        return result

    def ids(r):
        return [e['id'] for e in r['entries']]

    def stored(m):
        return sorted([json.loads(e.content) for e in m._tree._entries.values()], key=lambda e: e['id'])

    m, ec, callers = setup()
    r = call('human-declaration', m, ec, callers['human'], f['declaration'])
    receipt = {'id': 'human-declaration', 'context_id': 'project-a', 'provenance': 'USER_DECLARATION',
               'created_by': 'human', 'epistemic_status': 'DECLARED'}
    check('human/receipt', response('RECORDED', receipt=receipt), r)
    initial = call('initial-read', m, ec, callers['cognition'], {'op': 'search', 'query': ''})
    check('initial/ids', f['expected_sequence']['cognition'], ids(initial))
    for role, write_key in [('cognition', 'cognition_observation'), ('worker', 'worker_observation'), ('verifier', None)]:
        r = call(role + '-read', m, ec, callers[role], {'op': 'search', 'query': ''},
                 frozen=initial if variant == 'initial-only' else None)
        check('sequence/' + role, f['expected_sequence'][role], ids(r))
        check('sequence/status/' + role, 'SUCCESS_WITH_RESULTS', r['status'])
        check('sequence/unverified/' + role, True,
              all(e['epistemic_status'] == 'UNVERIFIED' for e in r['entries'] if e['provenance'] == 'AGENT_OBSERVATION'))
        if write_key:
            write = f[write_key]
            r = call(role + '-write', m, ec, callers[role], write)
            expected = {'id': write['entry_id'], 'context_id': 'task-a1', 'provenance': 'AGENT_OBSERVATION',
                        'created_by': role, 'epistemic_status': 'UNVERIFIED'}
            check('provenance/' + role, response('RECORDED', receipt=expected), r)
    final = stored(m)
    check('sequence/stored-post-start', ['cognition-observation', 'worker-observation'],
          sorted(e['id'] for e in final if e['created_by'] in ('cognition', 'worker')))
    # Observation stays local; declaration originates directly at the allowed parent.
    for context in ('root', 'personal', 'project-a', 'task-a2', 'work-a1', 'task-x1'):
        other = m.begin('inspect-' + context, context)
        who = m.participant(other, 'inspector', 'verifier')
        r = call('post-start/' + context, m, other, who, {'op': 'search', 'query': ''})
        expected = f['expected_visibility'][context][:]
        if context in ('project-a', 'task-a2', 'work-a1'):
            expected += ['human-declaration']
        if context == 'work-a1':
            expected += ['cognition-observation', 'worker-observation']
        # Full lineage can exceed budget at work-a1; targeted reads below avoid conflating selection with visibility.
        for entry_id in ('human-declaration', 'cognition-observation', 'worker-observation'):
            r = call('post-start/' + context + '/' + entry_id, m, other, who, {'op': 'get', 'entry_id': entry_id})
            check('post-start/' + context + '/' + entry_id,
                  'SUCCESS_WITH_RESULTS' if entry_id in expected else 'DENIED', r['status'])

    # All original III.2 context/entry pairs through the new capability.
    clean, _, _ = setup()
    for context, expected in f['expected_visibility'].items():
        ctx = clean.begin('read-' + context, context)
        reader = clean.participant(ctx, 'reader', 'verifier')
        r = call('lineage/' + context, clean, ctx, reader, {'op': 'search', 'query': ''})
        check('lineage/' + context, expected, ids(r))
        for entry in f['entries']:
            name = 'direct/' + context + '/' + entry['id']
            r = call(name, clean, ctx, reader, {'op': 'get', 'entry_id': entry['id']})
            wanted = response('SUCCESS_WITH_RESULTS', [entry]) if entry['id'] in expected else response('DENIED', reason='not_permitted')
            check(name, wanted, r)

    # Closed shapes reject provenance, role, authority and arbitrary read/write scope.
    before = stored(m)
    forbidden_fields = {'provenance': 'USER_DECLARATION', 'source': 'USER_DECLARATION',
                        'created_by': 'human', 'caller_class': 'human', 'epistemic_status': 'VERIFIED',
                        'authority': 'human'}
    for field, value in forbidden_fields.items():
        req = {'op': 'recordObservation', 'entry_id': 'forgery-' + field, 'content': 'must not persist', field: value}
        r = call('forgery/' + field, m, ec, callers['worker'], req)
        check('forgery/' + field, response('DENIED', reason='invalid_request'), r)
    check('forgery/no-write', before, stored(m))
    for target in ('project-a', 'task-a2', 'task-x1'):
        req = dict(f['worker_observation'], entry_id='target-' + target, context_id=target)
        r = call('target/' + target, m, ec, callers['worker'], req)
        check('target/' + target, response('DENIED', reason='invalid_request'), r)
    for field, value in [('scopes', ['task-x1']), ('context_id', 'task-x1'), ('ancestors', ['task-x1'])]:
        r = call('scope/' + field, m, ec, callers['worker'], {'op': 'search', 'query': '', field: value})
        check('scope/' + field, response('DENIED', reason='invalid_request'), r)
    for role in ('cognition', 'worker', 'verifier'):
        req = dict(f['declaration'], entry_id='not-human-' + role)
        r = call('declare-denied/' + role, m, ec, callers[role], req)
        check('declare-denied/' + role, response('DENIED', reason='declaration_authority'), r)
    r = call('human/wrong-target', m, ec, callers['human'], dict(f['declaration'], target_context='root'))
    check('human/wrong-target', response('DENIED', reason='declaration_authority'), r)
    r = call('verifier/write', m, ec, callers['verifier'], dict(f['worker_observation'], entry_id='verifier-write'))
    check('verifier/write', response('DENIED', reason='caller_operation'), r)
    check('authority/no-write', before, stored(m))
    for name, context, caller in [('execution-copy', ExecutionContext(**asdict(ec)), callers['worker']),
                                  ('caller-copy', ec, Caller('human', 'human'))]:
        r = call('binding/' + name, m, context, caller, {'op': 'search', 'query': ''})
        check('binding/' + name, response('DENIED', reason='untrusted_binding'), r)
    other_m, other_ec, other_callers = setup()
    check('binding/foreign', response('DENIED', reason='untrusted_binding'),
          m.handle(other_ec, other_callers['worker'], {'op': 'search', 'query': ''}))

    check('state/empty', response('EMPTY'), call('empty', m, ec, callers['worker'], {'op': 'search', 'query': 'no-such-text'}))
    check('state/forbidden-match-empty', response('EMPTY'),
          call('forbidden-match', m, ec, callers['worker'], {'op': 'search', 'query': 'owned by task-x1'}))
    check('state/denied', response('DENIED', reason='not_permitted'),
          call('denied', m, ec, callers['worker'], {'op': 'get', 'entry_id': 'task-x1-memory'}))
    before_fault = final  # Exact clean-store oracle, shared by control variants.
    m.available = False
    check('state/unavailable', response('UNAVAILABLE', reason='capability_unavailable'),
          call('unavailable', m, ec, callers['worker'], {'op': 'search', 'query': ''}))
    check('state/unavailable-write', response('UNAVAILABLE', reason='capability_unavailable'),
          call('unavailable-write', m, ec, callers['worker'], dict(f['worker_observation'], entry_id='offline')))
    check('state/no-fault-write', before_fault, stored(m))
    m.available = True
    check('state/recovered', 'SUCCESS_WITH_RESULTS', call('recovered', m, ec, callers['worker'], {'op': 'search', 'query': ''})['status'])

    # Overflow uses multibyte content; no cache, no semantic ranking, whole entries only.
    b, be, bc = setup(entries=f['entries'] + f['budget_entries'] + f['budget_forbidden'] + [f['oversized_entry']])
    br = call('overflow', b, be, bc['worker'], {'op': 'search', 'query': 'budget'})
    check('overflow/ids', f['budget_expected_ids'], ids(br))
    check('overflow/partial', True, br['partial'])
    check('overflow/repeat', br, call('overflow-repeat', b, be, bc['worker'], {'op': 'search', 'query': 'budget'}))
    without, we, wc = setup(entries=f['entries'] + f['budget_entries'])
    check('overflow/forbidden-noninterference', br,
          call('overflow-without-forbidden', without, we, wc['worker'], {'op': 'search', 'query': 'budget'}))
    big = call('oversized', b, be, bc['worker'], {'op': 'get', 'entry_id': 'oversized'})
    check('oversized/not-empty', response('SUCCESS_WITH_RESULTS', partial=True), big)
    unbounded = response('SUCCESS_WITH_RESULTS', f['budget_entries'])
    check('overflow/exceeds-without-selection', True, len(wire(unbounded)) > BUDGET)

    # Validate structure even where an inheritance switch stops reads.
    nodes = deepcopy(f['nodes'])
    next(n for n in nodes if n['id'] == 'task-a1').update(parent_id='work-a1', inherit_parent=False)
    try:
        setup(nodes=nodes)
        structural = 'accepted'
    except Rejected as exc:
        structural = str(exc)
    check('structure/cycle-behind-boundary', 'cycle', structural)
    nodes = deepcopy(f['nodes'])
    next(n for n in nodes if n['id'] == 'project-a')['inherit_parent'] = False
    bm, bx, bw = setup(nodes=nodes)
    rr = call('read-boundary', bm, bx, bw['worker'], {'op': 'search', 'query': ''})
    check('structure/permitted-ancestors', ['project-a-memory', 'task-a1-memory'], ids(rr))
    return {'cases': cases, 'trace': trace, 'bindings': {'execution': asdict(ec),
            'callers': [asdict(c) for c in callers.values()], 'same_execution_object': all(binding is ec for binding in sequence_bindings),
            'handoff_memory_payload': False}, 'final_entries': final,
            'unbounded_budget_bytes': len(wire(unbounded))}


def verdict(report):
    failed = [c['case'] for c in report['cases'] if c['status'] != 'PASS']
    return {'status': 'FAIL' if failed else 'PASS', 'cases': len(report['cases']),
            'failed': len(failed), 'failed_cases': failed}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--variant', choices=['correct', 'initial-only', 'forged-provenance'], default='correct')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    f = json.loads((HERE / 'fixtures.json').read_text())
    report = run(args.variant, f)
    save(args.output / 'results.json', report)
    summary = verdict(report)
    if args.variant != 'correct':
        save(args.output / 'summary.json', summary)
        return int(summary['status'] != 'PASS')
    controls = {}
    for variant in ('initial-only', 'forged-provenance'):
        with tempfile.TemporaryDirectory(prefix='blaine-iii3-') as temp:
            child = subprocess.run([sys.executable, str(HERE / 'probe.py'), '--variant', variant, '--output', temp],
                                   capture_output=True, text=True, timeout=30)
            output = json.loads((Path(temp) / 'results.json').read_text())
            result = json.loads((Path(temp) / 'summary.json').read_text())
            save(args.output / (variant + '.json'), output)
            controls[variant] = {'exit_code': child.returncode, 'suite': result,
                                 'stdout': child.stdout, 'stderr': child.stderr}
    restored = run('correct', f)
    save(args.output / 'restored.json', restored)
    expected_failure = {'initial-only': {'sequence/worker', 'sequence/verifier'},
                        'forged-provenance': {'forgery/provenance', 'forgery/no-write'}}
    caught = all(c['exit_code'] == 1 and expected_failure[v] <= set(c['suite']['failed_cases'])
                 for v, c in controls.items())
    paths = ['capability.py', 'probe.py', 'verify.py', 'fixtures.json', '../track-iii-002/evaluator.py']
    summary.update({'status': 'PASS' if summary['status'] == 'PASS' and caught and restored == report else 'FAIL',
                    'increment': 'III.3', 'controls': controls, 'controls_detected': caught,
                    'correct_restored_equal': restored == report,
                    'max_response_bytes': max(t['wire_bytes'] for t in report['trace']),
                    'response_budget_bytes': BUDGET,
                    'source_sha256': {p: hashlib.sha256((HERE / p).read_bytes()).hexdigest() for p in paths},
                    'task_submission': {'submitted': False, 'task_id': None},
                    'III.4_started': False})
    save(args.output / 'summary.json', summary)
    print(json.dumps({k: summary[k] for k in ('status', 'cases', 'failed', 'max_response_bytes', 'controls_detected')}))
    return int(summary['status'] != 'PASS')


if __name__ == '__main__':
    sys.exit(main())
