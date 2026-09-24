"""Check retained III.3 JSON independently, without importing the system under test."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    read = lambda name: json.loads((args.evidence / name).read_text())
    report, summary = read('results.json'), read('summary.json')
    fixture = json.loads((HERE / 'fixtures.json').read_text())
    checks = []

    def check(name, condition):
        checks.append({'check': name, 'status': 'PASS' if condition else 'FAIL'})

    def size(value):
        return len(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))

    cases = {c['case']: c for c in report['cases']}
    trace = {t['operation']: t for t in report['trace']}
    check('unique-cases', len(cases) == len(report['cases']) == summary['cases'] == 394)
    check('correct-oracles', all(c['expected'] == c['actual'] and c['status'] == 'PASS' for c in cases.values()))
    check('source-hashes', all(hashlib.sha256((HERE / p).read_bytes()).hexdigest() == digest
                               for p, digest in summary['source_sha256'].items()))
    check('accepted-tree-source', summary['source_sha256']['../track-iii-002/evaluator.py'] ==
          'e4789efa17d81af51ae6612e63cb0cda7f6da44bcf057cecd884fe0701eba030')
    check('restored', read('restored.json') == report and summary['correct_restored_equal'])
    check('budget', summary['response_budget_bytes'] == 2048 and all(
        size(t['response']) == t['wire_bytes'] <= 2048 for t in report['trace']))
    check('max-response', max(size(t['response']) for t in report['trace']) == summary['max_response_bytes'])
    check('denials-no-content', all(t['response']['entries'] == [] and t['response']['receipt'] is None
                                  for t in report['trace'] if t['response']['status'] == 'DENIED'))
    for context, expected in fixture['expected_visibility'].items():
        check('lineage/' + context, [e['id'] for e in trace['lineage/' + context]['response']['entries']] == expected)
        for entry in fixture['entries']:
            value = trace['direct/' + context + '/' + entry['id']]['response']
            check('direct/' + context + '/' + entry['id'],
                  value['entries'] == ([entry] if entry['id'] in expected else []) and
                  value['status'] == ('SUCCESS_WITH_RESULTS' if entry['id'] in expected else 'DENIED'))
    for role in ('cognition', 'worker', 'verifier'):
        event = trace[role + '-read']
        check('sequence/' + role, event['execution'] == fixture['execution'] and
              event['caller']['caller_class'] == role and event['delivery'] == 'capability' and
              [e['id'] for e in event['response']['entries']] == fixture['expected_sequence'][role])
    check('shared-binding', report['bindings']['same_execution_object'] and not report['bindings']['handoff_memory_payload'])
    final = {e['id']: e for e in report['final_entries']}
    for name, owner, source, author, state in [
            ('human-declaration', 'project-a', 'USER_DECLARATION', 'human', 'DECLARED'),
            ('cognition-observation', 'task-a1', 'AGENT_OBSERVATION', 'cognition', 'UNVERIFIED'),
            ('worker-observation', 'task-a1', 'AGENT_OBSERVATION', 'worker', 'UNVERIFIED')]:
        entry = final[name]
        check('provenance/' + name, (entry['context_id'], entry['provenance'], entry['created_by'], entry['epistemic_status']) ==
              (owner, source, author, state))
    for op, status in [('empty', 'EMPTY'), ('denied', 'DENIED'), ('unavailable', 'UNAVAILABLE'),
                       ('recovered', 'SUCCESS_WITH_RESULTS')]:
        check('state/' + op, trace[op]['response']['status'] == status)
    overflow = trace['overflow']['response']
    check('overflow', overflow['partial'] and [e['id'] for e in overflow['entries']] == fixture['budget_expected_ids']
          and report['unbounded_budget_bytes'] > 2048 and overflow == trace['overflow-repeat']['response'] ==
          trace['overflow-without-forbidden']['response'])
    check('oversized', trace['oversized']['response']['status'] == 'SUCCESS_WITH_RESULTS' and
          trace['oversized']['response']['partial'] and not trace['oversized']['response']['entries'])
    for variant, failures in [('initial-only', {'sequence/worker', 'sequence/verifier'}),
                              ('forged-provenance', {'forgery/provenance', 'forgery/no-write', 'authority/no-write', 'state/no-fault-write'})]:
        control = read(variant + '.json')
        actual_failed = {c['case'] for c in control['cases'] if c['actual'] != c['expected']}
        retained = summary['controls'][variant]
        check('control/' + variant, actual_failed == failures == set(retained['suite']['failed_cases']) and
              retained['exit_code'] == 1 and retained['suite']['status'] == 'FAIL' and
              retained['suite']['failed'] == len(failures) and retained['suite']['cases'] == len(cases) and
              all(c['status'] == ('FAIL' if c['case'] in failures else 'PASS') for c in control['cases']) and
              [(c['case'], c['expected']) for c in control['cases']] ==
              [(c['case'], c['expected']) for c in report['cases']])
    frozen = {t['operation']: t for t in read('initial-only.json')['trace']}
    check('control/frozen-snapshot', all(frozen[r + '-read']['response'] == frozen['initial-read']['response'] and
          frozen[r + '-read']['delivery'] == 'initial_snapshot' for r in ('cognition', 'worker', 'verifier')))
    forged = {c['case']: c for c in read('forged-provenance.json')['cases']}
    check('control/persisted-forgery', any(e['id'] == 'forgery-provenance' and e['provenance'] == 'USER_DECLARATION'
                                         for e in forged['forgery/no-write']['actual']))
    check('summary', summary['status'] == 'PASS' and summary['failed'] == 0 and summary['controls_detected']
          and summary['III.4_started'] is False and summary['task_submission'] == {'submitted': False, 'task_id': None})
    output = {'status': 'PASS' if all(c['status'] == 'PASS' for c in checks) else 'FAIL',
              'checks': checks, 'check_count': len(checks)}
    (args.evidence / 'verification.json').write_text(json.dumps(output, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': output['status'], 'checks': len(checks)}))
    return int(output['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())
