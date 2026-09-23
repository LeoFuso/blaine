"""Independent evidence checker; does not import the evaluator or probe."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def verify(directory):
    def read(name):
        return json.loads((directory / name).read_text())

    fixture = json.loads((HERE / 'fixtures.json').read_text())
    rows = read('results.json')
    restored = read('restored-results.json')
    mutants = read('mutation-results.json')
    mutation = read('mutation-control.json')
    summary = read('summary.json')
    cases = {row['case']: row for row in rows}
    require(len(cases) == len(rows), 'duplicate case identity')
    require(rows == restored, 'correct post-control results differ')
    require(all(r['actual'] == r['expected'] and r['status'] == 'PASS' for r in rows),
            'correct evaluator did not satisfy every oracle')
    for name, digest in summary['source_sha256'].items():
        require(hashlib.sha256((HERE / name).read_bytes()).hexdigest() == digest,
                'source mismatch: ' + name)
    require(set(summary['source_sha256']) == {'evaluator.py', 'probe.py', 'verify.py', 'fixtures.json'},
            'incomplete source provenance')
    # Bind the fixture to the assigned topology, rather than trusting its label.
    parents = {'root': None, 'personal': 'root', 'project-a': 'personal',
               'task-a1': 'project-a', 'work-a1': 'task-a1', 'task-a2': 'project-a',
               'employer-x': 'root', 'project-x': 'employer-x', 'task-x1': 'project-x',
               'work-x1': 'task-x1', 'task-x2': 'project-x'}
    require({n['id']: n['parent_id'] for n in fixture['nodes']} == parents, 'wrong fixed tree')
    require(len(fixture['nodes']) == len(parents), 'duplicate fixture context')
    require(set(fixture['expected_visibility']) == set(parents), 'missing literal visibility oracle')
    require(fixture['expected_visibility']['root'] == ['root-memory'], 'root oracle changed')
    require(fixture['expected_visibility']['work-a1'] ==
            ['personal-memory', 'project-a-memory', 'root-memory', 'task-a1-memory', 'work-a1-memory'],
            'downward oracle changed')
    for context, expected in fixture['expected_visibility'].items():
        require(cases['visibility/' + context]['expected'] == expected, 'visibility oracle drift')
        for entry in fixture['entries']:
            name = 'direct/' + context + '/' + entry['id']
            wanted = entry if entry['id'] in expected else {'denied': 'not_visible'}
            require(cases[name]['expected'] == wanted, 'direct ID coverage/oracle drift: ' + name)
        expected_write = sorted(expected + (['new-observation'] if context in ('task-a1', 'work-a1') else []))
        require(cases['write/visibility/' + context]['expected'] == expected_write,
                'write visibility oracle drift')
        for family in ('labels/', 'ordering/', 'extension/old-context/'):
            require(cases[family + context]['expected'] == expected, 'metamorphic case drift')
    for case in fixture['malformed']:
        require(cases['malformed/' + case['id']]['actual'] == {'denied': case['expected_reason']},
                'malformed tree not rejected')
    for index in range(len(fixture['forged_requests']) + len(fixture['forged_writes'])):
        require(cases['forged/request-' + str(index)]['actual'] == {'denied': 'invalid_request'},
                'forged request accepted')
    for name in ('constructed-token', 'foreign-tree-token', 'string-id'):
        require(cases['binding/' + name]['actual'] == {'denied': 'untrusted_binding'}, 'forged binding accepted')
    for name in ('bind', 'children', 'parent', 'promote', 'get_context'):
        require(cases['unsupported/' + name]['actual'] == {'denied': 'invalid_request'}, 'unexpected API')
    require(cases['write/receipt']['actual']['context_id'] == 'task-a1', 'wrong write owner')
    require(cases['boundary/permitted-ancestors']['actual'] == fixture['boundary']['expected_ids'],
            'boundary mismatch')
    require(cases['boundary/root-direct-denied']['actual'] == {'denied': 'not_visible'},
            'direct boundary bypass')
    require({r['case'] for r in mutants} == set(cases), 'mutant used a different suite')
    require(all(r['expected'] == cases[r['case']]['expected'] for r in mutants), 'mutant oracle changed')
    failed = [r for r in mutants if r['actual'] != r['expected']]
    require(bool(failed), 'mutation survived')
    require(all(r['status'] == ('PASS' if r['actual'] == r['expected'] else 'FAIL') for r in mutants),
            'incorrect mutation verdict')
    by_name = {r['case']: r for r in failed}
    require('task-a2-memory' in by_name['visibility/task-a1']['actual'], 'no observed sibling leak')
    require(by_name['direct/task-a1/task-a2-memory']['actual']['context_id'] == 'task-a2',
            'direct-ID control did not leak sibling')
    require(mutation['actual_process_exit'] == mutation['expected_process_exit'] == 1,
            'mutated suite did not exit with failure')
    require(mutation['suite']['failed'] == len(failed), 'mutation count drift')
    require(mutation['suite']['status'] == 'FAIL' and mutation['correct_after_control']['status'] == 'PASS',
            'control/restoration status drift')
    require(mutation['evaluator_and_oracle_hashes_unchanged'] and mutation['correct_results_byte_equivalent'],
            'control modified evaluator or oracle')
    require(summary['status'] == 'PASS' and summary['case_count'] == len(rows)
            and summary['passed'] == len(rows) and summary['failed'] == 0, 'summary mismatch')
    counts = {}
    for row in rows:
        counter = counts.setdefault(row['invariant'], {'passed': 0, 'failed': 0})
        counter['passed'] += 1
    require(summary['invariants'] == counts, 'invariant aggregation mismatch')
    return {'status': 'PASS', 'correct_cases': len(rows), 'direct_id_pairs': len(parents) * len(fixture['entries']),
            'malformed_trees_rejected': len(fixture['malformed']), 'mutation_failures': len(failed),
            'same_oracle_for_mutant': True, 'correct_after_control': True,
            'source_hashes_verified': len(summary['source_sha256'])}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    print(json.dumps(verify(args.evidence), indent=2, sort_keys=True))
