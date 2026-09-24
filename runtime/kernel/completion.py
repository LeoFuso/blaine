"""Completion Contract v1: what must be demonstrated before a Task may be COMPLETED.

The contract is durable Task data, separate from the plan and from authority.
Revisions, amendments and evaluations are immutable artifacts; TaskState keeps
references and counters. Criterion status is never stored in a contract; it is a
property of an evaluation. Exactly one deterministic function, ``legality``,
decides whether COMPLETED is allowed. See docs/contracts/completion-contract.md.
"""
from copy import deepcopy
import hashlib
import json
import re

from runtime.kernel import citation, effect_evidence, journal, review
from runtime.kernel.contracts import encode, fields, identifier, message, text, unpack
from runtime.kernel.human import validate_request, validate_response

LEVELS = ('REQUIRED', 'ADVISORY')
AUTHORITATIVE = ('task_type', 'operator_rule', 'project_policy', 'user', 'parent_task')
DERIVED = ('repository', 'memory', 'model')
SOURCES = AUTHORITATIVE + DERIVED
VERIFIERS = ('artifact_digest', 'human_response', 'capability_journal', 'evidence_citation',
             'capability_result', 'change_set', 'semantic_review', 'unbound')
NOT_IMPLEMENTED = {}
DETERMINISTIC = ('artifact_digest', 'capability_journal', 'evidence_citation', 'capability_result', 'change_set')
STATUSES = ('satisfied', 'pending', 'failed', 'unknown', 'waiting_human', 'waived')
PASSING = ('satisfied', 'waived')
MAX_CRITERIA = 16
ACTORS = {'user': ('modify-constraints', 'human_response'),
          'operator': ('policy_exception', 'policy_update'),
          'project_policy': ('policy_update',)}
OPERATIONS = {'add': ({'op', 'criterion'}, set()),
              'bind': ({'op', 'id', 'verifier'}, {'binding_provenance'}),
              'rebind': ({'op', 'id', 'verifier'}, set()),
              'waive': ({'op', 'id', 'reason'}, set()),
              'elevate': ({'op', 'id'}, set()),
              'supersede': ({'op', 'id', 'by'}, set())}
DIGEST = r'sha256:[0-9a-f]{64}'
PROVISIONAL = '0' * 64


class AmendmentDenied(ValueError):
    """The actor's authority does not cover the criterion's source."""


class AmendmentConflict(ValueError):
    """The amendment names a revision that is no longer current."""


# ------------------------------------------------------------------ validation

def rank(provenance: dict) -> int:
    """Precedence on conflict (contract: Precedence and conflicts)."""
    if provenance['source'] == 'task_type':
        return 7 if provenance.get('invariant') else 4
    return {'operator_rule': 6, 'project_policy': 6, 'user': 5, 'parent_task': 3,
            'repository': 2, 'memory': 1, 'model': 0}[provenance['source']]


def invariant(criterion: dict) -> bool:
    return criterion['provenance']['source'] == 'task_type' and criterion['provenance'].get('invariant') is True


def validate_provenance(value: object, task_type: dict | None) -> dict:
    provenance = fields(value, {'source'}, {'ref', 'actor', 'invariant', 'designation_ref',
                                            'source_digest', 'confirmed_from'})
    source = provenance['source']
    if source not in SOURCES:
        raise ValueError('Unknown criterion provenance source')
    for key in ('ref', 'actor'):
        if key in provenance:
            text(provenance[key], 256)
    if 'invariant' in provenance and (source != 'task_type' or type(provenance['invariant']) is not bool):
        raise ValueError('Only task_type criteria may be invariant')
    if source == 'task_type' and (task_type is None or
                                  provenance.get('ref') != f"{task_type['template']}@{task_type['version']}"):
        raise ValueError('task_type provenance must name the contract template')
    if source in ('operator_rule', 'project_policy'):
        # Policy is referenced by rule id and pinned digest so an exception can name it.
        if 'ref' not in provenance or not re.fullmatch(DIGEST, str(provenance.get('source_digest'))):
            raise ValueError('Policy provenance requires a rule ref and pinned source_digest')
    elif 'source_digest' in provenance:
        raise ValueError('source_digest is only meaningful for policy provenance')
    if source == 'project_policy':
        # Designation, not content, confers trust (Context Plane CP-B5).
        journal.ref(provenance.get('designation_ref'))
    elif 'designation_ref' in provenance:
        raise ValueError('designation_ref is only meaningful for project_policy')
    if 'confirmed_from' in provenance and (source != 'user' or provenance['confirmed_from'] not in DERIVED):
        raise ValueError('confirmed_from records a user confirmation of derived provenance')
    return provenance


def validate_accept(verifier: dict, request: dict) -> None:
    if 'accept' in verifier:
        accept = verifier['accept']
        allowed = request['payload']['allowed_responses']
        if (not isinstance(accept, list) or not accept or len(set(accept)) != len(accept)
                or not set(accept) <= set(allowed)):
            raise ValueError('accept must be a non-empty subset of the allowed responses')


def validate_verifier(value: object, task_id: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError('Invalid verifier')
    kind = value.get('kind')
    if kind in NOT_IMPLEMENTED:
        raise ValueError(f'Verifier {kind} is {NOT_IMPLEMENTED[kind]}')
    if kind not in VERIFIERS:
        raise ValueError('Verifier kind is outside the closed taxonomy')
    if kind == 'unbound':
        return fields(value, {'kind'})
    if type(value.get('version')) is not int or value['version'] != 1:
        raise ValueError('Unsupported verifier version')
    match kind:
        case 'artifact_digest':
            fields(value, {'kind', 'version', 'artifact', 'sha256'}, {'subject'})
            identifier(value['artifact'])
            if not isinstance(value['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', value['sha256']):
                raise ValueError('Expected exact SHA-256 completion evidence')
        case 'human_response':
            fields(value, {'kind', 'version', 'artifact', 'request'}, {'accept', 'subject'})
            identifier(value['artifact'])
            if validate_request(value['request'])['task_id'] != task_id:
                raise ValueError('Human request does not belong to this Task')
            validate_accept(value, value['request'])
        case 'capability_journal':
            fields(value, {'kind', 'version', 'predicates'}, {'subject'})
            journal.validate_predicates(value['predicates'])
        case 'evidence_citation':
            citation.validate_params(value)
        case 'capability_result':
            effect_evidence.validate_result_params(value)
        case 'change_set':
            effect_evidence.validate_change_params(value)
        case 'semantic_review':
            review.validate_params(value)
            if 'request' in value:
                identifier(value['artifact'])
                if validate_request(value['request'])['task_id'] != task_id:
                    raise ValueError('Human request does not belong to this Task')
                validate_accept(value, value['request'])
    if 'subject' in value:
        text(value['subject'], 128)
    return value


def validate_actor_record(value: object) -> dict:
    actor = fields(value, {'kind', 'via', 'binding', 'ref'}, {'response_ref', 'exception_for'})
    if actor['kind'] not in ACTORS or actor['via'] not in ACTORS[actor['kind']]:
        raise ValueError('Invalid amendment actor')
    identifier(actor['binding'])
    journal.ref(actor['ref'])
    if 'response_ref' in actor:
        journal.ref(actor['response_ref'])
    if 'exception_for' in actor:
        fields(actor['exception_for'], {'rule', 'digest'})
    return actor


def validate_criterion(value: object, task_id: str, task_type: dict | None) -> dict:
    criterion = fields(value, {'id', 'requirement', 'level', 'provenance', 'verifier'},
                       {'superseded_by', 'waiver', 'binding_provenance'})
    identifier(criterion['id'])
    text(criterion['requirement'], 512)
    if criterion['level'] not in LEVELS:
        raise ValueError('Criterion level must be REQUIRED or ADVISORY')
    provenance = validate_provenance(criterion['provenance'], task_type)
    verifier = validate_verifier(criterion['verifier'], task_id)
    if criterion['level'] == 'REQUIRED' and provenance['source'] not in AUTHORITATIVE:
        raise ValueError('Repository, memory and model provenance may only create ADVISORY criteria')
    if verifier['kind'] == 'semantic_review' and criterion['level'] == 'REQUIRED' and (
            provenance['source'] not in ('user', 'operator_rule') or verifier['on_low_confidence'] != 'request_human'):
        raise ValueError('A REQUIRED semantic review needs user/operator_rule provenance and a human path')
    if 'binding_provenance' in criterion and criterion['binding_provenance'] not in SOURCES:
        raise ValueError('Invalid binding provenance')
    if 'superseded_by' in criterion:
        identifier(criterion['superseded_by'])
    if 'waiver' in criterion:
        waiver = fields(criterion['waiver'], {'revision', 'actor', 'reason'})
        if type(waiver['revision']) is not int or waiver['revision'] < 1:
            raise ValueError('A waiver is created only by an amendment')
        validate_actor_record(waiver['actor'])
        text(waiver['reason'], 512)
        if invariant(criterion):
            raise ValueError('A task-type invariant cannot be waived')
    return criterion


def human_bindings(criteria: list[dict]) -> dict[str, dict]:
    """Contract-fixed human requests: human_response criteria and semantic escalations."""
    bindings = {}
    for criterion in criteria:
        verifier = criterion['verifier']
        if verifier['kind'] == 'human_response' or (verifier['kind'] == 'semantic_review' and 'request' in verifier):
            request_id = verifier['request']['payload']['request_id']
            if request_id in bindings:
                raise ValueError('Duplicate human request identity')
            bindings[request_id] = {'criterion': criterion['id'], 'artifact': verifier['artifact'],
                                    'request': verifier['request'], **({'accept': verifier['accept']} if 'accept' in verifier else {})}
    return bindings


def validate_contract(raw: object, task_id: str, mutating: bool) -> dict:
    contract = fields(unpack(raw, 'CompletionContract'),
                      {'task_id', 'revision', 'previous_ref', 'amendment_ref', 'task_type', 'criteria'}, {'request'})
    if contract['task_id'] != identifier(task_id):
        raise ValueError('Contract does not belong to this Task')
    if type(contract['revision']) is not int or contract['revision'] < 0:
        raise ValueError('Invalid contract revision')
    links = [contract['previous_ref'], contract['amendment_ref']]
    if contract['revision'] == 0:
        if links != [None, None]:
            raise ValueError('Revision 0 has no predecessor or amendment')
    else:
        for item in links:
            journal.ref(item)
    task_type = contract['task_type']
    if task_type is not None:
        fields(task_type, {'template', 'version'})
        identifier(task_type['template'])
        if type(task_type['version']) is not int or task_type['version'] < 1:
            raise ValueError('Invalid task_type version')
    if 'request' in contract:
        text(contract['request'], 1024)
    criteria = contract['criteria']
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= MAX_CRITERIA:
        raise ValueError('Expected 1..16 contract criteria')
    for criterion in criteria:
        validate_criterion(criterion, task_id, task_type)
        if 'waiver' in criterion and criterion['waiver']['revision'] > contract['revision']:
            raise ValueError('Waiver is newer than its contract revision')
    by_id = {c['id']: c for c in criteria}
    if len(by_id) != len(criteria):
        raise ValueError('Criterion ids must be unique')
    human_bindings(criteria)
    for criterion in criteria:
        if 'superseded_by' in criterion:
            target = by_id.get(criterion['superseded_by'])
            if (target is None or target is criterion or 'superseded_by' in target or invariant(criterion)
                    or rank(target['provenance']) < rank(criterion['provenance'])):
                raise ValueError('A criterion may be superseded only by an existing equal-or-higher precedence criterion')
    deterministic_subjects = {c['verifier']['subject'] for c in criteria
                              if c['verifier']['kind'] in DETERMINISTIC and 'subject' in c['verifier']}
    for criterion in criteria:
        verifier = criterion['verifier']
        if verifier['kind'] == 'semantic_review':
            # Deterministic-first: a model never verifies what a deterministic verifier checks.
            if verifier['subject'] in deterministic_subjects:
                raise ValueError('semantic_review cannot target a deterministically verified subject')
            for name in verifier.get('depends_on', []):
                if name not in by_id or by_id[name]['verifier']['kind'] not in DETERMINISTIC:
                    raise ValueError('semantic_review may depend only on deterministic criteria')
        if verifier['kind'] == 'unbound' and criterion['level'] == 'REQUIRED' and mutating:
            raise ValueError('A Task with mutating authority must start with every REQUIRED criterion bound')
    if not any(c['level'] == 'REQUIRED' and 'superseded_by' not in c for c in criteria):
        raise ValueError('A contract needs at least one REQUIRED criterion')
    return contract


# ------------------------------------------------------------------ intake

def lower_spec(spec: dict, task_id: str, parent: dict | None = None) -> dict:
    """v0 TaskSpec.completion -> revision 0, with the exact existing meaning."""
    criteria = []
    for number, item in enumerate(spec['completion'], 1):
        evidence = item['evidence']
        if evidence.get('verifier') == 'human_response':
            verifier = {'kind': 'human_response', 'version': 1, 'artifact': evidence['artifact'],
                        'request': evidence['request']}
        else:
            verifier = {'kind': 'artifact_digest', 'version': 1, 'artifact': evidence['artifact'],
                        'sha256': evidence['sha256']}
        provenance = {'source': 'parent_task', 'ref': parent['task_id']} if parent else {'source': 'user'}
        criteria.append({'id': f'c{number}', 'requirement': item['criterion'], 'level': 'REQUIRED',
                         'provenance': provenance, 'verifier': verifier})
    return {'task_id': task_id, 'revision': 0, 'previous_ref': None, 'amendment_ref': None,
            'task_type': None, 'criteria': criteria}


def envelope_contract(request: object) -> object | None:
    if isinstance(request, dict) and request.get('kind') == 'TaskRequest' and isinstance(request.get('payload'), dict):
        return request['payload'].get('contract')
    return None


def accept_contract(spec: dict, parent: dict | None, raw: object | None, task_id: str, mutating: bool) -> dict:
    """Revision 0: the trusted envelope contract, or the lowered TaskSpec.completion.

    An envelope contract must carry every lowered TaskSpec criterion unchanged, so
    the accepted TaskSpec never means less than it did before contracts existed.
    """
    lowered = lower_spec(spec, task_id, parent)
    if raw is None:
        return validate_contract(message('CompletionContract', lowered), task_id, mutating)
    if parent is not None:
        raise ValueError('A child contract is lowered from its TaskSpec only')
    contract = validate_contract(raw, task_id, mutating)
    if contract['revision'] != 0:
        raise ValueError('Intake accepts contract revision 0 only')
    by_id = {c['id']: c for c in contract['criteria']}
    for criterion in lowered['criteria']:
        if by_id.get(criterion['id']) != criterion:
            raise ValueError('Envelope contract must carry the lowered TaskSpec.completion criteria unchanged')
    return contract


def human_binding(contract: dict, request_id: str) -> dict:
    binding = human_bindings(contract['criteria']).get(request_id)
    if binding is None:
        raise ValueError('Expected one accepted human request')
    return binding


def gating(criterion: dict) -> bool:
    """REQUIRED and not superseded. A waived criterion still gates; it passes as ``waived``."""
    return criterion['level'] == 'REQUIRED' and 'superseded_by' not in criterion


def cognition_view(contract: dict, spec: dict) -> dict:
    """What the Task must demonstrate, for cognition. Evidence of status stays in evaluations."""
    known = {c['evidence']['request']['payload']['request_id'] for c in spec['completion']
             if c['evidence'].get('verifier') == 'human_response'}
    criteria = []
    for criterion in contract['criteria']:
        verifier = criterion['verifier']
        item = {'id': criterion['id'], 'level': criterion['level'], 'requirement': criterion['requirement'],
                'verifier': verifier['kind']}
        if 'artifact' in verifier:
            item['artifact'] = verifier['artifact']
        if 'request' in verifier and verifier['request']['payload']['request_id'] not in known:
            item['request'] = verifier['request']
        if 'superseded_by' in criterion:
            item['superseded_by'] = criterion['superseded_by']
        if 'waiver' in criterion:
            item['waived'] = True
        criteria.append(item)
    return {'revision': contract['revision'], 'criteria': criteria}


# ------------------------------------------------------------------ evaluation

def evidence_digest(state: dict) -> str:
    return 'sha256:' + hashlib.sha256(encode([sorted((state.get('artifacts') or {}).items()),
                                              sorted((state.get('human_responses') or {}).items())])).hexdigest()


def digest_verdict(verifier: dict, state: dict, store) -> tuple[str, str, list[str]]:
    evidence_ref = state['artifacts'].get(verifier['artifact'])
    if not evidence_ref:
        return 'pending', 'Required artifact is missing', []
    try:
        content = store.read(state['task_id'], evidence_ref)
    except (OSError, ValueError) as error:
        return 'unknown', str(error)[:512], [evidence_ref]
    if hashlib.sha256(content).hexdigest() == verifier['sha256']:
        return 'satisfied', 'Exact artifact digest verified', [evidence_ref]
    return 'failed', 'Artifact does not match accepted digest', [evidence_ref]


def human_verdict(verifier: dict, state: dict, store) -> tuple[str, str, list[str]]:
    request = verifier['request']
    request_id = request['payload']['request_id']
    evidence_ref = state['artifacts'].get(verifier['artifact'])
    if not evidence_ref:
        if 'human-request-' + request_id in state['artifacts']:
            return 'waiting_human', f'Human decision {request_id} requested; awaiting response', []
        return 'pending', 'Required artifact is missing', []
    try:
        content = store.read(state['task_id'], evidence_ref)
        if evidence_ref != state.get('human_responses', {}).get(request_id):
            raise ValueError('Artifact was not accepted through the human input boundary')
        response = validate_response(json.loads(content), request, state['task_id'])
    except (OSError, ValueError) as error:
        return 'unknown', str(error)[:512], [evidence_ref]
    if 'accept' in verifier and response['value'] not in verifier['accept']:
        return 'failed', f"Human answered {response['value']!r}, outside the accepting set", [evidence_ref]
    return 'satisfied', 'Scoped response accepted and allowed value independently verified', [evidence_ref]


def load_journal(state: dict, store) -> dict:
    """Journal facts shared by verifiers and legality. Read failures are reported, not hidden."""
    task_id = state['task_id']
    try:
        entries = journal.read(store, task_id, state.get('journal_head'), state.get('journal_length', 0))
        refs = {e['authority_ref'] for _, e in entries if 'authority_ref' in e}
        if state.get('authority_ref'):
            refs.add(state['authority_ref'])
        authorities = {r: journal.validate_authority(store.read_json(task_id, r), task_id) for r in sorted(refs)}
    except (OSError, ValueError, TypeError) as error:
        return {'error': f'Capability journal unreadable: {error}'[:512]}
    analysis = journal.analyze(entries, authorities)
    receipts = {e['receipt_ref'] for e in analysis['observed'].values() if e['outcome'] == 'success'}
    facts = {'error': None, 'entries': entries, 'authorities': authorities, 'analysis': analysis, 'receipts': receipts}
    try:
        facts['effects'], facts['effects_error'] = effect_evidence.records(facts, store, task_id), None
    except (OSError, ValueError, TypeError, KeyError) as error:
        # Only the effect verifiers lose their evidence; journal facts stay usable.
        facts['effects'], facts['effects_error'] = None, f'Effect evidence unreadable: {error}'[:512]
    return facts


def retained_review(record: dict | None, contract_revision: int, digest: str, state: dict, store) -> dict | None:
    if not record or record['contract_revision'] != contract_revision or record['evidence_digest'] != digest:
        return None
    try:
        return store.read_json(state['task_id'], record['ref'])
    except (OSError, ValueError):
        return None


def assess(contract: dict, state: dict, store, facts: dict | None = None) -> list[dict]:
    """Per-criterion verdicts. Pure over retained artifacts and the given state."""
    facts = facts if facts is not None else load_journal(state, store)
    digest = evidence_digest(state)
    results, by_id = [], {}
    for criterion in contract['criteria']:
        verifier = criterion['verifier']
        kind = verifier['kind']
        entry = {'id': criterion['id'], 'level': criterion['level'], 'gating': gating(criterion),
                 'verifier': kind if kind == 'unbound' else f"{kind}@{verifier['version']}",
                 'status': 'pending', 'evidence_refs': [], 'detail': ''}
        if kind == 'unbound':
            entry['detail'] = 'Verifier unbound; binding it is an amendment'
        elif kind == 'artifact_digest':
            entry['status'], entry['detail'], entry['evidence_refs'] = digest_verdict(verifier, state, store)
        elif kind == 'human_response':
            entry['status'], entry['detail'], entry['evidence_refs'] = human_verdict(verifier, state, store)
        elif kind == 'capability_journal':
            if facts['error']:
                entry['status'], entry['detail'] = 'unknown', facts['error']
            else:
                entry['status'], entry['detail'] = journal.verify(verifier['predicates'], facts['analysis'], facts['authorities'])
                entry['journal_range'] = [0, facts['analysis']['length']]
        elif kind in ('capability_result', 'change_set'):
            if facts['error'] or facts.get('effects') is None:
                entry['status'], entry['detail'] = 'unknown', facts['error'] or facts['effects_error']
            elif kind == 'capability_result':
                entry['status'], entry['detail'], entry['evidence_refs'] = effect_evidence.verify_result(
                    verifier, facts['effects'])
            else:
                entry['status'], entry['detail'], entry['evidence_refs'] = effect_evidence.verify_change_set(
                    verifier, facts['effects'], lambda r: r in state['artifacts'].values() or r in facts['receipts'])
        elif kind == 'evidence_citation':
            if facts['error']:
                entry['status'], entry['detail'] = 'unknown', facts['error']
            else:
                entry['status'], entry['detail'], entry['evidence_refs'] = citation.verify(
                    verifier, state, store, facts['receipts'])
        if 'superseded_by' in criterion:
            entry['superseded_by'] = criterion['superseded_by']
        results.append(entry)
        by_id[criterion['id']] = entry
    # Semantic review reads deterministic verdicts as fixed inputs, never the reverse.
    for criterion, entry in zip(contract['criteria'], results):
        verifier = criterion['verifier']
        if verifier['kind'] != 'semantic_review':
            continue
        dependencies = {name: by_id[name]['status'] for name in verifier.get('depends_on', [])}
        human = human_verdict(verifier, state, store)[:2] if 'request' in verifier else None
        record = (state.get('semantic_reviews') or {}).get(criterion['id'])
        retained = retained_review(record, contract['revision'], digest, state, store)
        entry['status'], entry['detail'], concern = review.status(verifier, retained, dependencies, human)
        if record and retained is not None:
            entry['evidence_refs'] = [record['ref']]
        if concern:
            entry['concern'] = concern
    for criterion, entry in zip(contract['criteria'], results):
        if 'waiver' in criterion:
            waiver = criterion['waiver']
            entry['status'] = 'waived'
            entry['detail'] = (f"Waived at revision {waiver['revision']} by {waiver['actor']['kind']} "
                               f"({waiver['actor']['via']}): {waiver['reason']}")[:512]
            entry['waiver_ref'] = waiver['actor']['ref']
        entry['detail'] = entry['detail'][:512]
    return results


def outcome(results: list[dict]) -> str:
    required = [item for item in results if item['gating']]
    if all(item['status'] in PASSING for item in required):
        return 'satisfied'
    if any(item['status'] in ('unknown', 'waiting_human') for item in required):
        return 'unknown'
    return 'unsatisfied'


def concerns(contract: dict, results: list[dict], facts: dict) -> list[str]:
    ordered = []
    for criterion, entry in zip(contract['criteria'], results):
        if entry['status'] == 'waived':
            ordered.append(f"{entry['level']} criterion {entry['id']} waived, not satisfied: {entry['detail']}"[:512])
    if not facts['error'] and facts['analysis'].get('unreconciled'):
        ordered.append(f"Target effects with unknown outcome, not reconciled: {facts['analysis']['unreconciled']}"[:512])
    if not facts['error'] and facts['analysis']['denials']:
        denials = facts['analysis']['denials']
        ordered.append(f"PolicyGate denied {len(denials)} capability request(s): "
                       f"{sorted({d['operation_class'] for d in denials})}"[:512])
    for entry in results:
        if 'concern' in entry:
            ordered.append(entry.pop('concern')[:512])
    for entry in results:
        if entry['level'] == 'ADVISORY' and entry['status'] not in PASSING:
            ordered.append(f"Advisory {entry['id']} {entry['status']}: {entry['detail']}"[:512])
    for entry in results:
        if 'superseded_by' in entry:
            ordered.append(f"Criterion {entry['id']} superseded by {entry['superseded_by']}")
    return ordered[:8]


def legality(contract: dict, contract_ref: str | None, evaluation: dict, state: dict, store,
             facts: dict | None = None) -> dict:
    """The single deterministic answer to: may this Task become COMPLETED now?

    Recomputable offline from retained artifacts and the Task state it names.
    """
    facts = facts if facts is not None else load_journal(state, store)
    blockers = []
    if (evaluation['contract_ref'] != contract_ref or evaluation['contract_ref'] != state.get('contract_ref')
            or evaluation['contract_revision'] != contract['revision']
            or evaluation['contract_revision'] != state.get('contract_revision')):
        blockers.append('Evaluation is not against the current contract revision')
    if (evaluation['evidence_digest'] != evidence_digest(state)
            or evaluation['journal_head'] != state.get('journal_head')
            or evaluation['journal_length'] != state.get('journal_length', 0)):
        blockers.append('Evaluation is stale against current evidence or journal')
    for criterion, entry in zip(contract['criteria'], evaluation['criteria']):
        if entry['id'] != criterion['id']:
            blockers.append('Evaluation criteria do not match the contract')
            break
        if criterion['level'] != 'REQUIRED' or 'superseded_by' in criterion:
            continue
        if criterion['verifier']['kind'] == 'unbound' and 'waiver' not in criterion:
            blockers.append(f"REQUIRED {criterion['id']} is unbound")
        elif entry['status'] not in PASSING:
            blockers.append(f"REQUIRED {criterion['id']} is {entry['status']}")
    if len(evaluation['criteria']) != len(contract['criteria']):
        blockers.append('Evaluation criteria do not match the contract')
    wait = state.get('wait')
    if wait and wait.get('input_type') == 'human_response':
        blockers.append(f"Human decision {wait.get('wait_id')} is outstanding")
    if facts['error']:
        blockers.append(facts['error'])
    elif facts['analysis']['problems']:
        blockers.append('Capability journal violation: ' + '; '.join(facts['analysis']['problems'])[:400])
    for criterion in contract['criteria']:
        if 'waiver' not in criterion:
            continue
        actor = criterion['waiver']['actor']
        denied = authority_gap('waive', criterion, actor)
        if denied:
            blockers.append(f"Waiver of {criterion['id']} lacks authority: {denied}")
            continue
        try:
            action = unpack(store.read_json(state['task_id'], actor['ref']), 'CompletionContractAmendmentSubmission')
            # The waiver's actor must be the one the binding established for that action.
            if (action['actor'] != {k: actor[k] for k in ('kind', 'via', 'binding')}
                    or action['amendment']['payload']['task_id'] != state['task_id']):
                raise ValueError('foreign or re-attributed action')
        except (OSError, ValueError, TypeError):
            blockers.append(f"Waiver of {criterion['id']} does not reference a retained human action")
            continue
        if actor['via'] == 'human_response' and actor.get('response_ref') not in (state.get('human_responses') or {}).values():
            blockers.append(f"Waiver of {criterion['id']} cites an unaccepted human response")
    legal = not blockers and evaluation['outcome'] == 'satisfied'
    return {'legal': legal, 'blockers': blockers[:16]}


def terminal(criterion: dict, entry: dict) -> bool:
    """An irrecoverable (monotonic) invariant violation, as opposed to a remediable miss.

    Terminal only when all hold: the criterion gates completion, nobody may waive or
    change it (task-type invariant), and its failure is a fact later evidence cannot
    undo. A ``capability_journal`` failure is such a fact: the journal is append-only,
    so an admitted prohibited effect stays admitted. Every other ``failed`` REQUIRED
    criterion (a failed test, a bad quote, a digest mismatch, a waivable user journal
    criterion) is remediable: it blocks COMPLETED but the Task keeps working.
    """
    return (entry['status'] == 'failed' and gating(criterion) and invariant(criterion)
            and criterion['verifier']['kind'] == 'capability_journal')


def evaluate_contract(contract: dict, contract_ref: str | None, state: dict, store) -> dict:
    """CompletionEvaluation v2 with the legality decision it supports."""
    facts = load_journal(state, store)
    results = assess(contract, state, store, facts)
    evaluation = {
        'task_id': state['task_id'], 'contract_ref': contract_ref, 'contract_revision': contract['revision'],
        'evidence_digest': evidence_digest(state), 'journal_head': state.get('journal_head'),
        'journal_length': state.get('journal_length', 0), 'outcome': outcome(results),
        'criteria': results}
    evaluation['concerns'] = concerns(contract, results, facts)
    evaluation['irrecoverable'] = [entry['id'] for criterion, entry in zip(contract['criteria'], results)
                                   if terminal(criterion, entry)]
    evaluation['legality'] = legality(contract, contract_ref, evaluation, state, store, facts)
    return {'version': 2, 'kind': 'CompletionEvaluation', 'payload': evaluation}


V1_STATUS = {'satisfied': 'satisfied', 'waived': 'satisfied', 'pending': 'unsatisfied', 'failed': 'unsatisfied',
             'waiting_human': 'unsatisfied', 'unknown': 'unknown'}


def project_v1(contract: dict, results: list[dict]) -> dict:
    """The v1 CompletionEvaluation shape for existing readers, from the same verdicts."""
    findings = [{'criterion': criterion['requirement'], 'outcome': V1_STATUS[entry['status']],
                 'evidence_ref': entry['evidence_refs'][0] if entry['evidence_refs'] else None,
                 'detail': entry['detail']} for criterion, entry in zip(contract['criteria'], results)]
    outcomes = {item['outcome'] for item in findings}
    return message('CompletionEvaluation', {
        'outcome': 'unsatisfied' if 'unsatisfied' in outcomes else 'unknown' if 'unknown' in outcomes else 'satisfied',
        'criteria': findings})


def semantic_due(contract: dict, results: list[dict], state: dict) -> list[dict]:
    """Semantic criteria whose deterministic dependencies have verdicts and whose
    retained review does not match the current revision and evidence."""
    by_id = {entry['id']: entry for entry in results}
    digest = evidence_digest(state)
    due = []
    for criterion in contract['criteria']:
        verifier = criterion['verifier']
        if verifier['kind'] != 'semantic_review' or 'waiver' in criterion or 'superseded_by' in criterion:
            continue
        if any(by_id[name]['status'] not in review.TERMINAL for name in verifier.get('depends_on', [])):
            continue
        record = (state.get('semantic_reviews') or {}).get(criterion['id'])
        if record and record['contract_revision'] == contract['revision'] and record['evidence_digest'] == digest:
            continue
        due.append(criterion)
    return due


def dependency_view(criterion: dict, results: list[dict]) -> list[dict]:
    by_id = {entry['id']: entry for entry in results}
    return [{'id': name, 'status': by_id[name]['status'], 'verifier': by_id[name]['verifier']}
            for name in criterion['verifier'].get('depends_on', [])]


# ------------------------------------------------------------------ amendments

def validate_actor_context(value: object) -> dict:
    """The effective actor, established by the authenticated binding, never by content.

    ``binding`` names the trusted component that authenticated the principal and
    constructed this context (as the grant is constructed for a TaskRequest).
    """
    actor = fields(value, {'kind', 'via', 'binding'})
    if actor['kind'] not in ACTORS or actor['via'] not in ACTORS[actor['kind']]:
        raise ValueError('Actor kind and channel do not form an amendment authority')
    identifier(actor['binding'])
    return actor


def validate_amendment_request(raw: object, task_id: str) -> dict:
    """The requested change. Untrusted content: it carries no actor or authority field."""
    request = fields(unpack(raw, 'CompletionContractAmendmentRequest'),
                     {'task_id', 'request_id', 'from_revision', 'operations', 'reason'},
                     {'exception_for', 'response_ref'})
    if request['task_id'] != identifier(task_id):
        raise ValueError('Amendment does not belong to this Task')
    identifier(request['request_id'])
    if type(request['from_revision']) is not int or request['from_revision'] < 0:
        raise ValueError('Invalid from_revision')
    text(request['reason'], 512)
    if 'response_ref' in request:
        journal.ref(request['response_ref'])
    if 'exception_for' in request:
        exception = fields(request['exception_for'], {'rule', 'digest'})
        text(exception['rule'], 256)
        if not re.fullmatch(DIGEST, str(exception['digest'])):
            raise ValueError('Policy exception digest must be pinned')
    operations = request['operations']
    if not isinstance(operations, list) or not 1 <= len(operations) <= 8:
        raise ValueError('Expected 1..8 amendment operations')
    for operation in operations:
        if not isinstance(operation, dict) or operation.get('op') not in OPERATIONS:
            raise ValueError('Unknown amendment operation')
        fields(operation, *OPERATIONS[operation['op']])
        if 'id' in operation:
            identifier(operation['id'])
        if operation['op'] == 'waive':
            text(operation['reason'], 512)
        if operation['op'] == 'supersede':
            identifier(operation['by'])
    return request


def validate_amendment_submission(raw: object, task_id: str) -> tuple[dict, dict]:
    """(trusted actor context, untrusted request) from the binding's envelope."""
    envelope = fields(unpack(raw, 'CompletionContractAmendmentSubmission'), {'actor', 'amendment'})
    actor = validate_actor_context(envelope['actor'])
    request = validate_amendment_request(envelope['amendment'], task_id)
    if (actor['via'] == 'human_response') != ('response_ref' in request):
        raise ValueError('A human_response amendment cites exactly its accepted response')
    if (actor['via'] == 'policy_exception') != ('exception_for' in request):
        raise ValueError('A policy exception names exactly the rule and digest it sets aside')
    return actor, request


def submission(actor: dict, amendment: dict) -> dict:
    """Envelope a binding sends: its authenticated actor around the requested change."""
    return message('CompletionContractAmendmentSubmission', {'actor': actor, 'amendment': amendment})


def authority_gap(operation: str, criterion: dict, actor: dict) -> str | None:
    """None when ``actor`` may perform ``operation`` on ``criterion``; else the reason."""
    source = criterion['provenance']['source']
    if invariant(criterion):
        return 'a task-type invariant changes only with the authority it evidences, never within this Task'
    if source in ('operator_rule', 'project_policy'):
        if operation in ('bind', 'elevate'):
            if actor['kind'] == 'operator' or (actor['kind'] == 'project_policy' and source == 'project_policy'):
                return None
            return f'{source} criteria are bound only by operator policy'
        if actor['kind'] != 'operator' or actor['via'] != 'policy_exception':
            return f'{source} criterion {criterion["id"]} requires an operator policy exception'
        expected = {'rule': criterion['provenance']['ref'], 'digest': criterion['provenance']['source_digest']}
        if actor.get('exception_for') != expected:
            return 'the policy exception names a different rule or digest'
        return None
    if actor['kind'] != 'user':
        return f'only the user may change {source} criteria'
    return None


def add_gap(criterion: dict, actor: dict) -> str | None:
    source = criterion['provenance']['source']
    allowed = {'user': ('user',), 'operator': ('operator_rule',), 'project_policy': ('project_policy',)}[actor['kind']]
    if source not in allowed:
        return f"a {actor['kind']} actor cannot add {source} criteria mid-Task"
    if actor['kind'] != 'user' and actor['via'] != 'policy_update':
        return 'policy criteria are added only by a policy update'
    return None


def apply_amendment(contract: dict, contract_ref: str, actor: dict, request: dict, action_ref: str,
                    state: dict, mutating: bool) -> tuple[dict, dict]:
    """(amendment payload, next revision payload). Raises on conflict or missing authority.

    ``actor`` is the binding-established context; ``request`` never supplies authority.
    """
    if request['from_revision'] != contract['revision'] or contract_ref != state.get('contract_ref'):
        raise AmendmentConflict('Amendment is not against the current contract revision')
    record = {**validate_actor_context(actor), 'ref': journal.ref(action_ref)}
    if actor['via'] == 'human_response':
        if request['response_ref'] not in (state.get('human_responses') or {}).values():
            raise AmendmentDenied('The cited human response was not accepted for this Task')
        record['response_ref'] = request['response_ref']
    if 'exception_for' in request:
        record['exception_for'] = request['exception_for']
    actor = record
    task_id = contract['task_id']
    revision = contract['revision'] + 1
    updated = deepcopy(contract)
    by_id = {c['id']: c for c in updated['criteria']}

    def target(name: str) -> dict:
        if name not in by_id:
            raise ValueError(f'Unknown criterion {name}')
        return by_id[name]

    for operation in request['operations']:
        match operation['op']:
            case 'add':
                criterion = validate_criterion(deepcopy(operation['criterion']), task_id, updated['task_type'])
                if criterion['id'] in by_id or {'waiver', 'superseded_by'} & criterion.keys():
                    raise ValueError('Added criteria need a new id and no waiver or supersession')
                gap = add_gap(criterion, actor)
                if gap:
                    raise AmendmentDenied(gap)
                updated['criteria'].append(criterion)
                by_id[criterion['id']] = criterion
            case 'bind':
                criterion = target(operation['id'])
                if criterion['verifier']['kind'] != 'unbound' and criterion['level'] != 'ADVISORY':
                    raise ValueError('bind replaces an unbound or ADVISORY verifier; use rebind')
                verifier = validate_verifier(deepcopy(operation['verifier']), task_id)
                if verifier['kind'] == 'unbound':
                    raise ValueError('bind must supply a verifier')
                gap = authority_gap('bind', criterion, actor)
                if gap:
                    raise AmendmentDenied(gap)
                criterion['verifier'] = verifier
                if 'binding_provenance' in operation:
                    criterion['binding_provenance'] = operation['binding_provenance']
            case 'rebind':
                criterion = target(operation['id'])
                if criterion['level'] != 'REQUIRED':
                    raise ValueError('rebind changes a REQUIRED criterion; use bind for ADVISORY')
                verifier = validate_verifier(deepcopy(operation['verifier']), task_id)
                if verifier['kind'] == 'unbound':
                    raise ValueError('rebind must supply a verifier')
                gap = authority_gap('rebind', criterion, actor)
                if gap:
                    raise AmendmentDenied(gap)
                criterion['verifier'] = verifier
            case 'waive':
                criterion = target(operation['id'])
                if 'waiver' in criterion:
                    raise ValueError('Criterion is already waived')
                gap = authority_gap('waive', criterion, actor)
                if gap:
                    raise AmendmentDenied(gap)
                criterion['waiver'] = {'revision': revision, 'actor': record, 'reason': operation['reason']}
            case 'elevate':
                criterion = target(operation['id'])
                if criterion['level'] != 'ADVISORY':
                    raise ValueError('Only ADVISORY criteria can be elevated')
                source = criterion['provenance']['source']
                if source in DERIVED:
                    if actor['kind'] != 'user':
                        raise AmendmentDenied('Only the user may confirm a derived suggestion for this Task')
                    criterion['provenance'] = {'source': 'user', 'confirmed_from': source}
                else:
                    gap = authority_gap('elevate', criterion, actor)
                    if gap:
                        raise AmendmentDenied(gap)
                criterion['level'] = 'REQUIRED'
            case 'supersede':
                criterion = target(operation['id'])
                target(operation['by'])
                if 'superseded_by' in criterion:
                    raise ValueError('Criterion is already superseded')
                gap = authority_gap('supersede', criterion, actor)
                if gap:
                    raise AmendmentDenied(gap)
                criterion['superseded_by'] = operation['by']
    updated.update(revision=revision, previous_ref=contract_ref,
                   amendment_ref=f'artifact://{task_id}/sha256:{PROVISIONAL}')
    validate_contract(message('CompletionContract', updated), task_id, mutating)
    amendment = {'task_id': task_id, 'request_id': request['request_id'], 'from_revision': contract['revision'],
                 'to_revision': revision, 'from_ref': contract_ref, 'operations': request['operations'],
                 'actor': record, 'provenance': actor['kind'], 'reason': request['reason']}
    return amendment, updated


def seal(updated: dict, amendment_ref: str, task_id: str, mutating: bool) -> dict:
    sealed = {**updated, 'amendment_ref': journal.ref(amendment_ref)}
    return validate_contract(message('CompletionContract', sealed), task_id, mutating)
