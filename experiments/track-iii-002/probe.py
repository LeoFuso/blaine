"""Offline III.2 acceptance: literal oracles, all-pairs ID checks, isolated mutant."""
import argparse
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from evaluator import BoundContext, ContextTree, Rejected

HERE = Path(__file__).resolve().parent


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot(tree):
    """Trusted test-harness inspection, not caller retrieval."""
    return [asdict(entry) for entry in sorted(tree._entries.values(), key=lambda e: e.id)]


class SiblingLeakControl(ContextTree):
    """Intentionally wrong, isolated in the test runner; never the evaluator."""
    def _lineage(self, context_id):
        allowed = super()._lineage(context_id)
        parent = self._nodes[context_id].parent_id
        if parent is not None:
            allowed.update(n.id for n in self._nodes.values() if n.parent_id == parent)
        return allowed


def run_suite(tree_type, fixture):
    rows = []

    def check(name, invariant, expected, call):
        try:
            actual = call()
        except Rejected as exc:
            actual = {'denied': str(exc)}
        except Exception as exc:
            actual = {'unexpected_error': type(exc).__name__, 'detail': str(exc)}
        rows.append({'case': name, 'invariant': invariant, 'expected': expected,
                     'actual': actual, 'status': 'PASS' if actual == expected else 'FAIL'})

    def fresh(nodes=None, entries=None):
        return tree_type(deepcopy(fixture['nodes'] if nodes is None else nodes),
                         deepcopy(fixture['entries'] if entries is None else entries))

    def ids(tree, binding):
        return [e.id for e in tree.handle(binding, {'op': 'read'})]

    tree = fresh()
    contexts = sorted(fixture['expected_visibility'])
    bindings = {c: tree.bind(c) for c in contexts}
    for context in contexts:
        check('visibility/' + context, 'exact_lineage_visibility',
              fixture['expected_visibility'][context], lambda c=context: ids(tree, bindings[c]))
    # Exact entry contents and denial results, not just a count or subset check.
    for context in contexts:
        for entry in fixture['entries']:
            expected = (entry if entry['id'] in fixture['expected_visibility'][context]
                        else {'denied': 'not_visible'})
            check('direct/' + context + '/' + entry['id'], 'direct_id_isolation', expected,
                  lambda c=context, e=entry: asdict(tree.handle(bindings[c],
                                                   {'op': 'get', 'entry_id': e['id']})))
    check('direct/unknown', 'direct_id_isolation', {'denied': 'not_visible'},
          lambda: tree.handle(bindings['task-a1'], {'op': 'get', 'entry_id': 'absent'}))

    before = snapshot(tree)
    for i, request in enumerate(fixture['forged_requests'] + fixture['forged_writes']):
        check('forged/request-' + str(i), 'binding_authority', {'denied': 'invalid_request'},
              lambda r=request: tree.handle(bindings['task-a1'], r))
    check('forged/no-mutation', 'binding_authority', before, lambda: snapshot(tree))
    check('binding/constructed-token', 'binding_authority', {'denied': 'untrusted_binding'},
          lambda: tree.handle(BoundContext(), {'op': 'read'}))
    check('binding/foreign-tree-token', 'binding_authority', {'denied': 'untrusted_binding'},
          lambda: tree.handle(fresh().bind('task-x1'), {'op': 'read'}))
    check('binding/string-id', 'binding_authority', {'denied': 'untrusted_binding'},
          lambda: tree.handle('task-x1', {'op': 'read'}))
    check('binding/unknown-context', 'binding_authority', {'denied': 'unknown_context'},
          lambda: tree.bind('absent'))
    for op in ('bind', 'children', 'parent', 'promote', 'get_context'):
        check('unsupported/' + op, 'closed_request_surface', {'denied': 'invalid_request'},
              lambda op=op: tree.handle(bindings['task-a1'], {'op': op, 'context_id': 'task-x1'}))

    write = fixture['write']
    request = write['request']
    expected_entry = {'id': request['entry_id'], 'context_id': write['expected_owner'],
                      'content': request['content']}
    check('write/receipt', 'current_context_write', expected_entry,
          lambda: asdict(tree.handle(bindings[write['binding']], request)))
    check('write/storage', 'current_context_write',
          sorted(before + [expected_entry], key=lambda e: e['id']), lambda: snapshot(tree))
    for context in contexts:
        expected = fixture['expected_visibility'][context][:]
        if context in write['expected_observers']:
            expected.append(request['entry_id'])
        check('write/visibility/' + context, 'write_inheritance_no_upward_flow', sorted(expected),
              lambda c=context: ids(tree, bindings[c]))
    after_write = snapshot(tree)
    check('write/duplicate-foreign-entry', 'current_context_write', {'denied': 'duplicate_entry_id'},
          lambda: tree.handle(bindings['task-a1'],
                             {'op': 'write', 'entry_id': 'task-x1-memory', 'content': 'overwrite'}))
    check('write/no-overwrite', 'current_context_write', after_write, lambda: snapshot(tree))

    for case in fixture['malformed']:
        def malformed(case=case):
            nodes = deepcopy(fixture['nodes'])
            if case.get('empty'):
                nodes = []
            if 'duplicate' in case:
                nodes.append(deepcopy(next(n for n in nodes if n['id'] == case['duplicate'])))
            if 'change' in case:
                change = case['change']
                node = next(n for n in nodes if n['id'] == change['node'])
                node.update(change.get('set', {}))
                if 'remove' in change:
                    del node[change['remove']]
            # A returned object would be an acceptance failure, even with no reads.
            fresh(nodes=nodes, entries=[])
            return {'accepted': True}
        check('malformed/' + case['id'], 'malformed_tree_fail_closed',
              {'denied': case['expected_reason']}, malformed)

    for name, alter, reason in (
        ('unknown-owner', lambda es: es[0].update(context_id='absent'), 'unknown_entry_context'),
        ('duplicate-entry', lambda es: es.append(deepcopy(es[0])), 'duplicate_entry_id'),
    ):
        def bad_entries(alter=alter):
            entries = deepcopy(fixture['entries'])
            alter(entries)
            fresh(entries=entries)
            return {'accepted': True}
        check('malformed-entry/' + name, 'entry_integrity', {'denied': reason}, bad_entries)

    nodes = deepcopy(fixture['nodes'])
    for node in nodes:
        node['kind'] = 'initiative'  # Same label at every level: no label-based dispatch.
    relabeled = fresh(nodes=nodes)
    reordered = fresh(nodes=list(reversed(fixture['nodes'])),
                      entries=list(reversed(fixture['entries'])))
    for context in contexts:
        check('labels/' + context, 'label_independence', fixture['expected_visibility'][context],
              lambda c=context: ids(relabeled, relabeled.bind(c)))
        check('ordering/' + context, 'input_order_independence', fixture['expected_visibility'][context],
              lambda c=context: ids(reordered, reordered.bind(c)))

    extension = fixture['extension']
    extended = fresh(nodes=fixture['nodes'] + [extension['node']],
                     entries=fixture['entries'] + [extension['entry']])
    check('extension/new-level', 'generic_specialization', extension['expected_ids'],
          lambda: ids(extended, extended.bind(extension['node']['id'])))
    for context in contexts:
        check('extension/old-context/' + context, 'generic_specialization',
              fixture['expected_visibility'][context], lambda c=context: ids(extended, extended.bind(c)))

    nodes = deepcopy(fixture['nodes'])
    boundary = fixture['boundary']
    next(n for n in nodes if n['id'] == boundary['node'])['inherit_parent'] = False
    bounded = fresh(nodes=nodes)
    check('boundary/permitted-ancestors', 'trusted_read_boundary', boundary['expected_ids'],
          lambda: ids(bounded, bounded.bind(boundary['binding'])))
    check('boundary/root-direct-denied', 'trusted_read_boundary', {'denied': 'not_visible'},
          lambda: bounded.handle(bounded.bind(boundary['binding']),
                                 {'op': 'get', 'entry_id': 'root-memory'}))
    check('boundary/caller-cannot-open', 'trusted_read_boundary', {'denied': 'invalid_request'},
          lambda: bounded.handle(bounded.bind(boundary['binding']),
                                 {'op': 'read', 'inherit_parent': True}))

    # Later changes to constructor input cannot rewrite the trusted hierarchy.
    source_nodes = deepcopy(fixture['nodes'])
    isolated = tree_type(source_nodes, deepcopy(fixture['entries']))
    source_nodes[0]['parent_id'] = 'task-x1'
    check('binding/input-copy', 'binding_authority', fixture['expected_visibility']['task-a1'],
          lambda: ids(isolated, isolated.bind('task-a1')))
    return rows


def summarize(rows):
    invariants = {}
    for row in rows:
        entry = invariants.setdefault(row['invariant'], {'passed': 0, 'failed': 0})
        entry['passed' if row['status'] == 'PASS' else 'failed'] += 1
    return {'status': 'PASS' if all(r['status'] == 'PASS' for r in rows) else 'FAIL',
            'case_count': len(rows), 'passed': sum(r['status'] == 'PASS' for r in rows),
            'failed': sum(r['status'] == 'FAIL' for r in rows), 'invariants': invariants,
            'failed_cases': [r['case'] for r in rows if r['status'] == 'FAIL']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--variant', choices=['correct', 'sibling-leak'], default='correct')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    fixture = json.loads((HERE / 'fixtures.json').read_text())
    hashes = {name: sha(HERE / name) for name in ('evaluator.py', 'probe.py', 'verify.py', 'fixtures.json')}
    rows = run_suite(ContextTree if args.variant == 'correct' else SiblingLeakControl, fixture)
    summary = summarize(rows)
    write_json(args.output / 'results.json', rows)
    if args.variant == 'sibling-leak':
        write_json(args.output / 'summary.json', summary)
        return 0 if summary['status'] == 'PASS' else 1

    # Run exactly the same oracle suite in a fresh process with a deliberately
    # wrong rule. No edits/patches to evaluator.py, no lingering monkey patch.
    with tempfile.TemporaryDirectory(prefix='blaine-iii2-mutant-') as directory:
        result = subprocess.run([sys.executable, str(HERE / 'probe.py'), '--variant',
                                 'sibling-leak', '--output', directory],
                                capture_output=True, text=True, timeout=30)
        control = json.loads((Path(directory) / 'summary.json').read_text())
        write_json(args.output / 'mutation-results.json',
                   json.loads((Path(directory) / 'results.json').read_text()))
    after = run_suite(ContextTree, fixture)
    restored = summarize(after)
    write_json(args.output / 'restored-results.json', after)
    unchanged = all(sha(HERE / name) == digest for name, digest in hashes.items())
    detected = (result.returncode == 1 and control['status'] == 'FAIL' and
                'visibility/task-a1' in control['failed_cases'] and
                'direct/task-a1/task-a2-memory' in control['failed_cases'])
    mutation = {'rule': 'incorrectly include current-context siblings in readable lineage',
                'variant_location': 'probe.py:SiblingLeakControl',
                'expected_process_exit': 1, 'actual_process_exit': result.returncode,
                'suite': control, 'detected': detected,
                'correct_after_control': restored,
                'correct_results_byte_equivalent': rows == after,
                'evaluator_and_oracle_hashes_unchanged': unchanged,
                'stdout': result.stdout, 'stderr': result.stderr}
    write_json(args.output / 'mutation-control.json', mutation)
    success = (summary['status'] == 'PASS' and detected and restored['status'] == 'PASS'
               and rows == after and unchanged)
    summary.update({'status': 'PASS' if success else 'FAIL', 'increment': 'III.2',
                    'scope': 'isolated deterministic context algebra; not production security',
                    'source_sha256': hashes, 'mutation_detected': detected,
                    'correct_after_control': restored['status'],
                    'repeat_results_equal': rows == after,
                    'task_submission': {'submitted': False, 'task_id': None},
                    'deferred': {'cache': 'No cache implemented; enforcement deferred',
                                 'traversal': 'No traversal API; unsupported shapes denied',
                                 'promotion': 'No promotion operation; unsupported shape denied',
                                 'III.3': 'Not started'},
                    'runtime_imports': False, 'external_dependencies': []})
    write_json(args.output / 'summary.json', summary)
    print(json.dumps({'status': summary['status'], 'cases': len(rows),
                      'mutation_failed_cases': control['failed'],
                      'restored': restored['status']}, sort_keys=True))
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
