"""evidence_citation@1: provenance of cited findings, never their truth.

A findings artifact conforms to its schema and every citation names a receipt the
Task itself admitted (an observed-success capability journal entry). A quoted span
must appear verbatim in the receipt's returned content within the cited lines:
the Context Plane's exact-excerpt semantics. No retrieval happens here; only
retained artifacts are read.
"""
import hashlib
import json

from runtime.kernel.contracts import fields, identifier, text, unpack
from runtime.kernel.journal import ref

SCHEMAS = {'InvestigationFindings@1': 'InvestigationFindings'}
PREDICATES = {
    'every_claim_cited': ({'name'}, set()),
    'quotes_match_receipts': ({'name'}, set()),
    'min_cited_receipts': ({'name', 'operation', 'count'}, {'path_prefix'}),
    'conclusion_status_present': ({'name'}, set()),
    'unresolved_requires_uncertainty': ({'name'}, set()),
}
MAX_CLAIMS = 16
MAX_CITATIONS = 8


def validate_params(verifier: dict) -> dict:
    fields(verifier, {'kind', 'version', 'artifact', 'schema', 'predicates'}, {'subject'})
    identifier(verifier['artifact'])
    if verifier['schema'] not in SCHEMAS:
        # ExplanationFindings@1 and LocationFindings@1 arrive with E1.D templates.
        raise ValueError('Findings schema is not implemented in this kernel')
    predicates = verifier['predicates']
    if not isinstance(predicates, list) or not 1 <= len(predicates) <= 8:
        raise ValueError('Expected 1..8 citation predicates')
    for item in predicates:
        if not isinstance(item, dict) or item.get('name') not in PREDICATES:
            raise ValueError('Unsupported evidence_citation predicate')
        fields(item, *PREDICATES[item['name']])
        if item['name'] == 'min_cited_receipts':
            text(item['operation'], 100)
            if type(item['count']) is not int or not 1 <= item['count'] <= MAX_CLAIMS:
                raise ValueError('Invalid citation count')
            if 'path_prefix' in item:
                text(item['path_prefix'], 512)
    return verifier


def citation(value: object) -> dict:
    item = fields(value, {'receipt_ref', 'path', 'lines', 'quote'})
    ref(item['receipt_ref'])
    text(item['path'], 512)
    lines = item['lines']
    if (not isinstance(lines, list) or len(lines) != 2 or any(type(x) is not int for x in lines)
            or not 1 <= lines[0] <= lines[1]):
        raise ValueError('Citation lines must be an ordered 1-based pair')
    text(item['quote'], 512)
    return item


def citations(value: object) -> list[dict]:
    if not isinstance(value, list) or len(value) > MAX_CITATIONS:
        raise ValueError('Invalid citation list')
    return [citation(item) for item in value]


def validate_findings(raw: object) -> dict:
    """InvestigationFindings@1 (workspace-capability.md, example 1)."""
    findings = fields(unpack(raw, 'InvestigationFindings'),
                      {'conclusion', 'claims', 'uncertainties'}, {'hypotheses'})
    conclusion = fields(findings['conclusion'], {'status', 'statement'})
    if conclusion['status'] not in ('supported', 'unresolved'):
        raise ValueError('Conclusion status must be supported or unresolved')
    text(conclusion['statement'], 1024)
    if not isinstance(findings['claims'], list) or len(findings['claims']) > MAX_CLAIMS:
        raise ValueError('Invalid claims')
    for claim in findings['claims']:
        fields(claim, {'text', 'citations'})
        text(claim['text'], 512)
        citations(claim['citations'])
    for hypothesis in findings.get('hypotheses', []):
        fields(hypothesis, {'text', 'status'}, {'citations'})
        text(hypothesis['text'], 512)
        if hypothesis['status'] not in ('supported', 'refuted', 'open'):
            raise ValueError('Invalid hypothesis status')
        citations(hypothesis.get('citations', []))
    if not isinstance(findings['uncertainties'], list) or len(findings['uncertainties']) > 8:
        raise ValueError('Invalid uncertainties')
    for item in findings['uncertainties']:
        text(item, 512)
    return findings


def validate_receipt(raw: object, task_id: str) -> dict:
    receipt = unpack(raw, 'WorkspaceReadReceipt')
    if receipt.get('task_id') != task_id or receipt.get('state') != 'SUCCESS':
        raise ValueError('Receipt is not a successful read of this Task')
    source = fields(receipt.get('source'), {'view', 'class', 'path', 'lines'})
    lines = source['lines']
    if not isinstance(lines, list) or len(lines) != 2 or any(type(x) is not int for x in lines) or lines[0] < 1:
        raise ValueError('Invalid receipt line range')
    ref(receipt.get('response_ref'))
    return receipt


def receipt_lines(store, task_id: str, receipt: dict) -> tuple[int, list[str]]:
    content = store.read(task_id, receipt['response_ref'])
    if hashlib.sha256(content).hexdigest() != receipt.get('response_sha256'):
        raise ValueError('Receipt response digest mismatch')
    lines = content.decode('utf-8').split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    return receipt['source']['lines'][0], lines


def verify(verifier: dict, state: dict, store, admitted_receipts: set[str]) -> tuple[str, str, list[str]]:
    """Returns (status, detail, evidence_refs)."""
    task_id = state['task_id']
    findings_ref = state['artifacts'].get(verifier['artifact'])
    if not findings_ref:
        return 'pending', 'Findings artifact absent', []
    try:
        findings = validate_findings(json.loads(store.read(task_id, findings_ref)))
    except OSError as error:
        return 'unknown', f'Findings unreadable: {error}'[:512], [findings_ref]
    except (ValueError, TypeError, UnicodeError) as error:
        return 'failed', f"Findings do not conform to {verifier['schema']}: {error}"[:512], [findings_ref]
    cited = [c for claim in findings['claims'] for c in claim['citations']]
    cited += [c for h in findings.get('hypotheses', []) for c in h.get('citations', [])]
    receipts, refs = {}, [findings_ref]
    for item in cited:
        if item['receipt_ref'] in receipts:
            continue
        if item['receipt_ref'] not in admitted_receipts:
            receipts[item['receipt_ref']] = None
            continue
        try:
            receipts[item['receipt_ref']] = validate_receipt(store.read_json(task_id, item['receipt_ref']), task_id)
            refs.append(item['receipt_ref'])
        except (OSError, ValueError, TypeError) as error:
            return 'unknown', f'Cited receipt unreadable: {error}'[:512], refs
    for predicate in verifier['predicates']:
        match predicate['name']:
            case 'every_claim_cited':
                for index, claim in enumerate(findings['claims']):
                    if not claim['citations'] or not any(receipts.get(c['receipt_ref']) for c in claim['citations']):
                        return 'failed', f'Claim {index} cites no admitted receipt', refs
            case 'quotes_match_receipts':
                for item in cited:
                    receipt = receipts.get(item['receipt_ref'])
                    if receipt is None:
                        return 'failed', 'A citation names a receipt this Task did not admit', refs
                    if receipt['source']['path'] != item['path']:
                        return 'failed', f"Citation path {item['path']!r} differs from its receipt", refs
                    try:
                        start, lines = receipt_lines(store, task_id, receipt)
                    except (OSError, ValueError, UnicodeError) as error:
                        return 'unknown', f'Receipt content unreadable: {error}'[:512], refs
                    first, last = item['lines']
                    if first < start or last >= start + len(lines):
                        return 'failed', f"Cited lines {item['lines']} are outside the receipt's returned lines", refs
                    if item['quote'] not in '\n'.join(lines[first - start:last - start + 1]):
                        return 'failed', f"Quote not present in {item['path']} lines {item['lines']}", refs
            case 'min_cited_receipts':
                matching = {r for r, receipt in receipts.items() if receipt and receipt['operation'] == predicate['operation']
                            and receipt['source']['path'].startswith(predicate.get('path_prefix', ''))}
                if len(matching) < predicate['count']:
                    return 'failed', f"{len(matching)} cited {predicate['operation']} receipt(s); {predicate['count']} required", refs
            case 'conclusion_status_present':
                pass  # the schema requires a supported/unresolved status and statement
            case 'unresolved_requires_uncertainty':
                if findings['conclusion']['status'] == 'unresolved' and not findings['uncertainties']:
                    return 'failed', 'Unresolved conclusion states no remaining uncertainty', refs
    return 'satisfied', f"{len(findings['claims'])} claim(s); {len(cited)} citation(s) verified against admitted receipts", refs
