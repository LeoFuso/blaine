"""E2.0 deterministic verifiers over target effects: capability_result@1, change_set@1.

Both read only the Task's capability journal and retained EffectReceipts; neither
calls a provider or trusts prose. Uncertain effects make them ``unknown``, never a
pass or a failure; a failed predicate is remediable (a new effect may satisfy it).
"""
from runtime.kernel.contracts import fields, identifier, text
from runtime.kernel.effects import WRITE

STATES = ('applied', 'conflict', 'rejected', 'completed', 'timed_out', 'canceled', 'not_started')
RESULT_PREDICATES = {
    'state': ({'name', 'equals'}, set()),
    'exit_code': ({'name', 'equals'}, set()),
    'result_field': ({'name', 'field', 'equals'}, set()),
    'result_after_last_change': ({'name'}, set()),
    'resulting_digest': ({'name', 'sha256'}, set()),
    'cleanup_confirmed': ({'name'}, set()),
}
CHANGE_PREDICATES = {
    'changed': ({'name', 'paths'}, set()),
    'expected_content': ({'name', 'path', 'sha256'}, set()),
    'only_paths': ({'name', 'allowed'}, set()),
    'evidence_complete': ({'name'}, set()),
}
UNKNOWN_STATES = ('uncertain', 'different_state')


def validate_predicates(value, table):
    if not isinstance(value, list) or not 1 <= len(value) <= 8:
        raise ValueError('Expected 1..8 predicates')
    for item in value:
        if not isinstance(item, dict) or item.get('name') not in table:
            raise ValueError('Unsupported predicate')
        fields(item, *table[item['name']])
    return value


def validate_result_params(verifier: dict) -> dict:
    fields(verifier, {'kind', 'version', 'operation_class', 'predicates'},
           {'operation', 'profile', 'path', 'workspace_id', 'subject'})
    if verifier['operation_class'] not in ('workspace.write', 'workspace.exec'):
        raise ValueError('capability_result selects a target-effect class')
    for key in ('operation', 'profile', 'workspace_id'):
        if key in verifier:
            text(verifier[key], 100)
    if 'path' in verifier:
        text(verifier['path'], 512)
    for item in validate_predicates(verifier['predicates'], RESULT_PREDICATES):
        if item['name'] == 'state' and item['equals'] not in STATES:
            raise ValueError('Unknown effect state')
        if item['name'] == 'exit_code' and type(item['equals']) is not int:
            raise ValueError('exit_code compares an integer')
        if item['name'] == 'result_field':
            identifier(item['field'])
        if item['name'] == 'resulting_digest':
            text(item['sha256'], 64)
    return verifier


def validate_change_params(verifier: dict) -> dict:
    fields(verifier, {'kind', 'version', 'workspace_id', 'predicates'}, {'subject'})
    identifier(verifier['workspace_id'])
    for item in validate_predicates(verifier['predicates'], CHANGE_PREDICATES):
        for key in ('paths', 'allowed'):
            if key in item:
                if not isinstance(item[key], list) or not 1 <= len(item[key]) <= 32:
                    raise ValueError('Expected a bounded path list')
                for path in item[key]:
                    text(path, 512)
    return verifier


def records(facts: dict, store, task_id: str) -> list[dict]:
    """One record per target effect, in admission order, with its resolved status."""
    positions = {}
    for index, (_, entry) in enumerate(facts['entries']):
        positions.setdefault((entry['phase'], entry.get('operation_id')), index)
    analysis = facts['analysis']
    result = []
    for operation, admitted in analysis['admitted'].items():
        if operation not in analysis['dispatched'] and operation not in analysis['observed']:
            continue  # admitted, still in flight (or awaiting approval)
        if admitted['operation_class'] not in ('workspace.write', 'workspace.exec'):
            continue
        dispatched = analysis['dispatched'].get(operation)
        request = store.read_json(task_id, dispatched['request_ref'])['payload'] if dispatched else None
        observed = analysis['observed'].get(operation)
        record = {'operation_id': operation, 'operation_class': admitted['operation_class'],
                  'admitted_at': positions[('admitted', operation)], 'request': request,
                  'dispatched_at': positions.get(('dispatched', operation)),
                  'settled_at': positions.get(('observed', operation)), 'receipt': None, 'receipt_ref': None,
                  'status': 'in_flight'}
        if observed:
            if observed['outcome'] == 'not_dispatched':
                record['status'] = 'not_dispatched'
            elif observed['outcome'] == 'uncertain':
                record['status'] = 'uncertain'
                for entry in analysis['reconciled'].get(operation, []):
                    if entry['state'] == 'APPLIED':
                        record['receipt_ref'] = entry['receipt_ref']
                    elif entry['state'] == 'NOT_APPLIED':
                        record['status'] = 'not_applied'
                    elif entry['state'] == 'DIFFERENT_STATE':
                        record['status'] = 'different_state'
                    if entry['state'] != 'STILL_UNKNOWN':
                        record['settled_at'] = facts['entries'].index(
                            next(e for e in facts['entries'] if e[1] is entry))
            else:
                record['receipt_ref'] = observed['receipt_ref']
            if record['receipt_ref']:
                receipt = store.read_json(task_id, record['receipt_ref'])['payload']
                record['receipt'], record['status'] = receipt, receipt['state']
        result.append(record)
    return result


def select(verifier: dict, effects: list[dict]) -> list[dict]:
    chosen = []
    for record in effects:
        request = record['request'] or {}
        if record['operation_class'] != verifier['operation_class']:
            continue
        if 'operation' in verifier and request.get('operation') != verifier['operation']:
            continue
        if 'profile' in verifier and request.get('profile', {}).get('id') != verifier['profile']:
            continue
        if 'path' in verifier and request.get('path') != verifier['path']:
            continue
        if 'workspace_id' in verifier and request.get('workspace_id') != verifier['workspace_id']:
            continue
        if record['status'] in ('not_dispatched', 'not_applied'):
            continue  # definitely never ran; not an outcome to judge
        chosen.append(record)
    return chosen


def verify_result(verifier: dict, effects: list[dict]) -> tuple[str, str, list[str]]:
    """capability_result@1 over the latest matching effect."""
    chosen = select(verifier, effects)
    if not chosen:
        return 'pending', 'No matching target effect has run', []
    record = chosen[-1]
    refs = [record['receipt_ref']] if record['receipt_ref'] else []
    if record['status'] in UNKNOWN_STATES or record['status'] == 'in_flight' or record['receipt'] is None:
        return 'unknown', f"Latest matching effect {record['operation_id']} is {record['status']}", refs
    receipt = record['receipt']
    exec_ = receipt.get('exec', {})
    for predicate in verifier['predicates']:
        match predicate['name']:
            case 'state':
                ok = receipt['state'] == predicate['equals']
            case 'exit_code':
                ok = receipt['state'] == 'completed' and exec_.get('exit_code') == predicate['equals']
            case 'result_field':
                ok = receipt['state'] == 'completed' and exec_.get('result', {}).get(predicate['field']) == predicate['equals']
            case 'resulting_digest':
                ok = receipt['state'] == 'applied' and receipt['write'].get('after') == {'sha256': predicate['sha256']}
            case 'cleanup_confirmed':
                ok = exec_.get('cleanup') in ('confirmed', 'not_applicable')
            case 'result_after_last_change':
                later = [w for w in effects if w['operation_class'] == WRITE and w['dispatched_at'] is not None
                         and w['dispatched_at'] > record['dispatched_at'] and w['status'] not in ('not_applied', 'conflict', 'rejected')]
                ok = not later
        if not ok:
            return 'failed', f"{predicate['name']} not met by {record['operation_id']} ({receipt['state']})", refs
    return 'satisfied', f"{record['operation_id']} {receipt['state']}; {len(verifier['predicates'])} predicate(s) held", refs


def matches(path: str, allowed: list[str]) -> bool:
    return any(path == item or (item.endswith('/') and path.startswith(item)) for item in allowed)


def verify_change_set(verifier: dict, effects: list[dict], artifacts_exist) -> tuple[str, str, list[str]]:
    """change_set@1: the net change of admitted writes in one workspace."""
    writes = [r for r in effects if r['operation_class'] == WRITE and r['request']
              and r['request']['workspace_id'] == verifier['workspace_id']]
    net, unknown, refs = {}, set(), []
    for record in writes:
        path = record['request']['path']
        if record['status'] in UNKNOWN_STATES or record['status'] == 'in_flight':
            unknown.add(path)
            continue
        if record['status'] != 'applied':
            continue
        write = record['receipt']['write']
        refs.append(record['receipt_ref'])
        entry = net.setdefault(path, {'before': write['before'], 'records': []})
        entry['after'] = write['after']
        entry['records'].append(record)
        unknown.discard(path)  # a later applied write fixes the net state again
    changed = {path for path, entry in net.items() if entry['after'] != entry['before']}
    pending = []
    for predicate in verifier['predicates']:
        match predicate['name']:
            case 'only_paths':
                outside = sorted(p for p in changed if not matches(p, predicate['allowed']))
                if outside:
                    return 'failed', f'Changes outside the allowed paths: {outside}', refs
            case 'expected_content':
                path = predicate['path']
                if path in changed and net[path]['after'] != {'sha256': predicate['sha256']}:
                    return 'failed', f'{path} changed to unexpected content', refs
                if path not in changed:
                    pending.append(path)
            case 'changed':
                pending += [p for p in predicate['paths'] if p not in changed]
            case 'evidence_complete':
                for path in changed:
                    for record in net[path]['records']:
                        write, request = record['receipt']['write'], record['request']
                        if not (write.get('readback_sha256') and artifacts_exist(request['content_ref'])
                                and (request.get('precondition_evidence') is None
                                     or artifacts_exist(request['precondition_evidence']))):
                            return 'failed', f'Incomplete before/after evidence for {path}', refs
    if unknown:
        return 'unknown', f'Uncertain writes leave the change set unknown: {sorted(unknown)}', refs
    if pending:
        return 'pending', f'Expected changes not yet made: {sorted(set(pending))}', refs
    return 'satisfied', f'{len(changed)} path(s) changed as required: {sorted(changed)}'[:512], refs
