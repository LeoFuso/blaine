"""Capability journal: the Task's own deterministic record of authority and effects.

Only the workflow appends, on the single INVOKE_CAPABILITY dispatch path, in
journaled steps. It is Task evidence for completion, not telemetry (ExecutionEvents
stay non-authoritative) and not a cross-Task ledger. Entries are immutable
content-addressed artifacts linked by ``previous_ref``; TaskState keeps only the
head reference and length.
"""
import hashlib
import re

from runtime.kernel.contracts import encode, fields, identifier, message, text, unpack

CLASSIFICATION = 'kernel@1'
# Effect scope of an operation class. Only TARGET_EFFECT is "mutation":
#   INTERNAL_EFFECT  changes only this Task's own durable state: its artifacts and
#                    evidence, journal, evaluations, a request published at the
#                    human boundary, local computation, semantic-review packets.
#   TARGET_READ      observes a target (workspace, external system) without
#                    changing it.
#   TARGET_EFFECT    may change state outside the Task: workspace files, process or
#                    terminal execution, external API, database or remote systems.
# Unknown classes are treated as TARGET_EFFECT, never as harmless.
INTERNAL_EFFECT, TARGET_READ, TARGET_EFFECT = 'internal_effect', 'target_read', 'target_effect'
# Reviewed, versioned capability -> operation-class table (Hub code next to
# PolicyGate). An unknown capability is unclassified and never admissible.
OPERATION_CLASSES = {
    'artifact.write': 'task.artifact.write',
    'artifact.read': 'task.artifact.read',
    'human.request': 'task.human.request',
    'text.stats': 'task.compute',
    'youtrack.read': 'external.read',
    'workspace.read': 'workspace.read',
    'worker.run': 'worker.run',
    'fixture.effect': 'external.effect',
}
TARGET_READ_CLASSES = frozenset({'workspace.read', 'external.read'})
TARGET_EFFECT_CLASSES = frozenset({'external.effect', 'worker.run', 'workspace.write', 'workspace.exec'})
MUTATING_CLASSES = TARGET_EFFECT_CLASSES
UNCLASSIFIED = 'unclassified'
PHASES = ('denied', 'admitted', 'observed')
OUTCOMES = ('success', 'failure', 'uncertain')
MAX_ENTRIES = 256
REF = r'artifact://[A-Za-z0-9_-]{1,80}/sha256:[0-9a-f]{64}'


def operation_class(capability: str) -> str:
    return OPERATION_CLASSES.get(capability, UNCLASSIFIED)


def effect_scope(operation_class: str) -> str:
    if operation_class.startswith('task.'):
        return INTERNAL_EFFECT
    if operation_class in TARGET_READ_CLASSES:
        return TARGET_READ
    return TARGET_EFFECT  # declared target effects, and anything unreviewed


def internal(operation_class: str) -> bool:
    return effect_scope(operation_class) == INTERNAL_EFFECT


def mutating(capabilities) -> bool:
    """Whether authority includes any TARGET_EFFECT (or unclassified) capability."""
    return any(effect_scope(operation_class(name)) == TARGET_EFFECT for name in capabilities)


def ref(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(REF, value):
        raise ValueError('Invalid artifact reference')
    return value


def digest(value: object) -> str:
    return 'sha256:' + hashlib.sha256(encode(value)).hexdigest()


def compile_authority(task_id: str, capabilities, workspaces, externally_bounded: bool) -> dict:
    """E1.0 effective authority from the existing trusted grant intersection.

    E1.C extends the same artifact with delegation and constraint provenance.
    """
    names = sorted(set(capabilities))
    return message('EffectiveAuthority', {
        'task_id': identifier(task_id), 'revision': 0, 'classification': CLASSIFICATION,
        'capabilities': names,
        'operation_classes': sorted({operation_class(name) for name in names}),
        'workspaces': sorted(set(workspaces)), 'externally_bounded': bool(externally_bounded)})


def validate_authority(raw: object, task_id: str) -> dict:
    authority = fields(unpack(raw, 'EffectiveAuthority'), {
        'task_id', 'revision', 'classification', 'capabilities', 'operation_classes',
        'workspaces', 'externally_bounded'})
    if authority['task_id'] != task_id or authority['classification'] != CLASSIFICATION:
        raise ValueError('Authority does not belong to this Task/classification')
    for key in ('capabilities', 'operation_classes', 'workspaces'):
        if not isinstance(authority[key], list) or len(authority[key]) > 32:
            raise ValueError('Invalid authority list')
        for item in authority[key]:
            text(item, 512)
    return authority


COMMON = {'task_id', 'seq', 'previous_ref', 'phase'}
SHAPES = {
    'denied': ({'decision_id', 'capability', 'operation_class', 'provider', 'operation',
                'reason', 'authority_ref', 'contract_revision'}, {'workspace_id'}),
    'admitted': ({'decision_id', 'operation_id', 'capability', 'operation_class', 'provider',
                  'operation', 'request_digest', 'authority_ref', 'contract_revision'}, {'workspace_id'}),
    'observed': ({'operation_id', 'outcome', 'receipt_ref'}, set()),
}


def validate_entry(raw: object, task_id: str) -> dict:
    payload = unpack(raw, 'CapabilityJournalEntry')
    phase = payload.get('phase')
    if phase not in SHAPES:
        raise ValueError('Invalid journal phase')
    required, optional = SHAPES[phase]
    fields(payload, COMMON | required, optional)
    if payload['task_id'] != task_id or type(payload['seq']) is not int or payload['seq'] < 0:
        raise ValueError('Misaddressed journal entry')
    if payload['previous_ref'] is not None:
        ref(payload['previous_ref'])
    if phase == 'observed':
        text(payload['operation_id'], 100)
        if payload['outcome'] not in OUTCOMES:
            raise ValueError('Invalid observed outcome')
        ref(payload['receipt_ref'])
    else:
        for key in ('decision_id', 'capability', 'operation_class', 'provider', 'operation'):
            text(payload[key], 100)
        ref(payload['authority_ref'])
        if type(payload['contract_revision']) is not int or payload['contract_revision'] < 0:
            raise ValueError('Invalid journal contract revision')
        if phase == 'admitted':
            text(payload['operation_id'], 100)
            if not re.fullmatch(r'sha256:[0-9a-f]{64}', str(payload['request_digest'])):
                raise ValueError('Invalid request digest')
        else:
            text(payload['reason'], 512)
        if 'workspace_id' in payload:
            text(payload['workspace_id'], 512)
    return payload


def append(store, task_id: str, head: str | None, length: int, entry: dict) -> str:
    """Retain one entry after ``head``. Deterministic bytes, so replay yields the same ref."""
    if length >= MAX_ENTRIES:
        raise ValueError('Capability journal limit reached')
    value = message('CapabilityJournalEntry', {
        'task_id': task_id, 'seq': length, 'previous_ref': head, **entry})
    validate_entry(value, task_id)
    return store.put_json(task_id, value)


def read(store, task_id: str, head: str | None, length: int) -> list[tuple[str, dict]]:
    """Walk the hash chain back from ``head``; oldest first. Malformed chains raise."""
    if type(length) is not int or not 0 <= length <= MAX_ENTRIES:
        raise ValueError('Invalid journal length')
    entries, cursor = [], head
    while cursor is not None:
        if len(entries) >= length:
            raise ValueError('Journal chain is longer than its recorded length')
        payload = validate_entry(store.read_json(task_id, cursor), task_id)
        entries.append((cursor, payload))
        cursor = payload['previous_ref']
    entries.reverse()
    if len(entries) != length or [p['seq'] for _, p in entries] != list(range(length)):
        raise ValueError('Journal chain does not match its recorded length and order')
    return entries


def analyze(entries: list[tuple[str, dict]], authorities: dict[str, dict]) -> dict:
    """Structural and authority facts every journal verdict and legality check share."""
    admitted, observed, denials, problems = {}, {}, [], []
    for entry_ref, entry in entries:
        match entry['phase']:
            case 'denied':
                denials.append(entry)
            case 'admitted':
                if entry['operation_id'] in admitted:
                    problems.append(f"operation {entry['operation_id']} admitted twice")
                admitted[entry['operation_id']] = entry
                authority = authorities.get(entry['authority_ref'])
                if authority is None:
                    problems.append(f"operation {entry['operation_id']} cites unknown authority")
                elif entry['operation_class'] not in authority['operation_classes'] or \
                        entry['capability'] not in authority['capabilities']:
                    problems.append(f"operation {entry['operation_id']} ({entry['operation_class']}) outside effective authority")
                elif 'workspace_id' in entry and entry['workspace_id'] not in authority['workspaces']:
                    problems.append(f"operation {entry['operation_id']} targets a workspace outside effective authority")
            case 'observed':
                if entry['operation_id'] not in admitted:
                    problems.append(f"operation {entry['operation_id']} observed without admission")
                if entry['operation_id'] in observed:
                    problems.append(f"operation {entry['operation_id']} observed twice")
                observed[entry['operation_id']] = entry
    return {'admitted': admitted, 'observed': observed, 'denials': denials, 'problems': problems,
            'length': len(entries)}


PREDICATES = {
    'operation_classes_subset': ({'name', 'allowed'}, set()),
    'admitted_before_observed': ({'name'}, set()),
    'workspace_subset': ({'name'}, set()),
    'observed_operation_present': ({'name', 'operations'}, set()),
    'no_target_effect': ({'name'}, {'allowed'}),
}


def validate_predicates(value: object) -> list[dict]:
    if not isinstance(value, list) or not 1 <= len(value) <= 8:
        raise ValueError('Expected 1..8 journal predicates')
    for item in value:
        if not isinstance(item, dict) or item.get('name') not in PREDICATES:
            raise ValueError('Unsupported capability_journal predicate')
        fields(item, *PREDICATES[item['name']])
        for key in ('allowed', 'operations'):
            if key in item:
                if not isinstance(item[key], list) or not 1 <= len(item[key]) <= 16:
                    raise ValueError('Expected a bounded predicate list')
                for name in item[key]:
                    text(name, 100)
    return value


def verify(predicates: list[dict], analysis: dict, authorities: dict[str, dict]) -> tuple[str, str]:
    """capability_journal@1. Violations are permanent: the journal is append-only."""
    admitted, observed = analysis['admitted'], analysis['observed']
    if analysis['problems']:
        # An observed entry without admission is a kernel defect; nothing built
        # on this journal can be trusted, so every journal criterion fails.
        return 'failed', 'Journal integrity or authority violation: ' + '; '.join(analysis['problems'])[:380]
    pending = []
    for predicate in predicates:
        match predicate['name']:
            case 'operation_classes_subset':
                outside = sorted({e['operation_class'] for e in admitted.values()
                                  if not internal(e['operation_class']) and e['operation_class'] not in predicate['allowed']})
                if outside:
                    return 'failed', f"Admitted external classes {outside} outside {sorted(predicate['allowed'])}"
            case 'admitted_before_observed':
                pass  # structural; enforced for every journal above
            case 'workspace_subset':
                for entry in admitted.values():
                    if 'workspace_id' in entry and entry['workspace_id'] not in authorities[entry['authority_ref']]['workspaces']:
                        return 'failed', f"Operation {entry['operation_id']} targeted a workspace outside the Task's scope"
            case 'no_target_effect':
                # "No mutation": no admitted TARGET_EFFECT outside the explicitly
                # allowed classes (default none). INTERNAL_EFFECT and TARGET_READ
                # never violate it, so a Task can always build its own evidence.
                effects = sorted({e['operation_class'] for e in admitted.values()
                                  if effect_scope(e['operation_class']) == TARGET_EFFECT
                                  and e['operation_class'] not in predicate.get('allowed', [])})
                if effects:
                    return 'failed', f"Admitted target effects {effects}"
            case 'observed_operation_present':
                if not any(observed.get(op, {}).get('outcome') == 'success' and entry['operation'] in predicate['operations']
                           for op, entry in admitted.items()):
                    pending.append(predicate['name'])
    classes = sorted({e['operation_class'] for e in admitted.values()})
    summary = (f"{analysis['length']} entries; admitted classes {classes}; "
               f"{len(analysis['denials'])} denial(s)")
    if pending:
        return 'pending', summary + f"; awaiting {pending}"
    return 'satisfied', summary
