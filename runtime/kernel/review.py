"""semantic_review@1: a bounded model judgement the kernel admits deterministically.

The reviewer is a deployment-injected adapter, like cognition. It receives the
fixed deterministic verdicts and the subject evidence as a bounded packet, never
the producer's reasoning. Its output is retained and consumed by reference, so
replay reuses it. It never changes another criterion's verdict, it cannot pass a
criterion whose deterministic dependencies failed, and low confidence resolves to
``unknown`` or a human decision, never to ``satisfied``.
"""
from collections.abc import Callable

from runtime.kernel.contracts import MAX_CONTENT, MAX_PACKET, encode, fields, identifier, message, text, unpack

SemanticReviewer = Callable[[dict], dict]
VERDICTS = ('satisfied', 'unsatisfied', 'unknown', 'request_human')
CONFIDENCE = ('high', 'low')
TERMINAL = ('satisfied', 'failed', 'waived')


def validate_params(verifier: dict) -> dict:
    fields(verifier, {'kind', 'version', 'subject', 'question', 'on_low_confidence'},
           {'depends_on', 'artifact', 'request', 'accept'})
    text(verifier['subject'], 128)
    text(verifier['question'], 512)
    if verifier['on_low_confidence'] not in ('unknown', 'request_human'):
        raise ValueError('on_low_confidence must be unknown or request_human')
    depends = verifier.get('depends_on', [])
    if not isinstance(depends, list) or len(depends) > 16 or len(set(depends)) != len(depends):
        raise ValueError('Invalid semantic dependencies')
    for item in depends:
        identifier(item)
    human = {'artifact', 'request'} & verifier.keys()
    if verifier['on_low_confidence'] == 'request_human' and human != {'artifact', 'request'}:
        raise ValueError('request_human requires a contract-fixed human request and artifact')
    if verifier['on_low_confidence'] == 'unknown' and (human or 'accept' in verifier):
        raise ValueError('A human request is only meaningful with request_human')
    return verifier


def subject_artifact(verifier: dict) -> str:
    return verifier['subject'].split('.', 1)[0]


def request(task_id: str, criterion: dict, contract_revision: int, evidence_digest: str,
            dependencies: list[dict], state: dict, store) -> dict:
    """Bounded packet: question, fixed deterministic verdicts and the subject evidence."""
    verifier = criterion['verifier']
    evidence = []
    name = subject_artifact(verifier)
    evidence_ref = state['artifacts'].get(name)
    if evidence_ref:
        content = store.read(task_id, evidence_ref)
        evidence.append({'name': name, 'ref': evidence_ref,
                         'content': content[:MAX_CONTENT].decode('utf-8', errors='replace'),
                         'truncated': len(content) > MAX_CONTENT})
    packet = message('SemanticReviewRequest', {
        'task_id': task_id, 'criterion_id': criterion['id'], 'contract_revision': contract_revision,
        'evidence_digest': evidence_digest, 'subject': verifier['subject'], 'question': verifier['question'],
        'deterministic': dependencies, 'evidence': evidence})
    if len(encode(packet)) > MAX_PACKET:
        raise ValueError('Semantic review packet exceeds budget')
    return packet


def call(reviewer: SemanticReviewer | None, packet: dict) -> dict:
    """The journaled step body. Adapter failure is an observation, never a Task crash."""
    if reviewer is None:
        return message('SemanticReviewFailure', {'reason': 'No semantic reviewer is deployed'})
    try:
        raw = reviewer(packet)
        validate_result(raw, packet)
        return raw
    except Exception as error:  # the model boundary: any failure becomes an unknown verdict
        return message('SemanticReviewFailure', {'reason': f'Reviewer output rejected: {error}'[:512]})


def validate_result(raw: object, packet: dict) -> dict:
    result = fields(unpack(raw, 'SemanticReviewResult'), {
        'task_id', 'criterion_id', 'contract_revision', 'evidence_digest', 'verdict',
        'confidence', 'rationale', 'evidence_refs'})
    expected = packet['payload']
    if any(result[key] != expected[key] for key in ('task_id', 'criterion_id', 'contract_revision', 'evidence_digest')):
        raise ValueError('Semantic result does not answer this review request')
    if result['verdict'] not in VERDICTS or result['confidence'] not in CONFIDENCE:
        raise ValueError('Invalid semantic verdict or confidence')
    text(result['rationale'], 512)
    allowed = {item['ref'] for item in expected['evidence']}
    if not isinstance(result['evidence_refs'], list) or not set(result['evidence_refs']) <= allowed:
        raise ValueError('Semantic rationale must cite evidence from its packet')
    return result


def status(verifier: dict, retained: dict | None, dependencies: dict[str, str],
           human: tuple[str, str] | None) -> tuple[str, str, str | None]:
    """(status, detail, concern). ``human`` is the escalation's human verdict, if any."""
    if human is not None and human[0] in ('satisfied', 'failed'):
        return human[0], 'Human decision on escalated semantic review: ' + human[1], None
    if any(value not in TERMINAL for value in dependencies.values()):
        return 'pending', 'Deterministic dependencies have no verdict yet', None
    if retained is None:
        return 'pending', 'Semantic review not yet run for current evidence', None
    escalate = verifier['on_low_confidence'] == 'request_human'
    if retained['kind'] == 'SemanticReviewFailure':
        verdict, confidence, detail = 'unknown', 'low', retained['payload']['reason']
    else:
        result = retained['payload']
        verdict, confidence, detail = result['verdict'], result['confidence'], result['rationale']
    failed = sorted(name for name, value in dependencies.items() if value == 'failed')
    if verdict == 'satisfied' and failed:
        # The deterministic verdict stands; the contradiction is visible, not resolved.
        return ('unknown', f'Semantic satisfied contradicts deterministic failure of {failed}',
                f'Semantic review contradicted deterministic verdict(s) {failed}; deterministic verdict stands')
    if confidence == 'high' and verdict == 'satisfied':
        return 'satisfied', detail, None
    if confidence == 'high' and verdict == 'unsatisfied':
        return 'failed', detail, None
    if escalate:
        pending = human[1] if human else 'human decision not yet requested'
        return 'waiting_human', f'Low-confidence or unresolved semantic review escalated: {pending}', None
    return 'unknown', f'Low-confidence or unresolved semantic review: {detail}'[:512], None
