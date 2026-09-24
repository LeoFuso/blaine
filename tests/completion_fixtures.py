"""Synthetic E1.0 Completion Contract fixtures. Neutral names; no secrets or live data."""
import hashlib
import json

from runtime.kernel.contracts import message
from runtime.kernel.human import request_digest

WORKSPACE = '/work/example'
PATH = 'service/src/main/java/example/ExampleService.java'
SOURCE = '\n'.join([
    'package example;',
    '',
    'public final class ExampleService {',
    '    private final Repository repository;',
    '',
    '    public Response handle(Request request) {',
    '        Customer customer = repository.find(request.customerId());',
    '        if (customer == null) {',
    '            throw new IllegalStateException("customer missing");',
    '        }',
    '        return Response.ok(customer.status());',
    '    }',
    '}',
    ''])
SOURCE_SHA = hashlib.sha256(SOURCE.encode()).hexdigest()
OPERATION = 'read_file'


def journal_criterion(criterion_id, predicates, template='investigation@1', invariant=True):
    provenance = {'source': 'task_type', 'ref': template}
    if invariant:
        provenance['invariant'] = True
    return {'id': criterion_id, 'level': 'REQUIRED',
            'requirement': 'Capability journal predicate holds.', 'provenance': provenance,
            'verifier': {'kind': 'capability_journal', 'version': 1, 'predicates': predicates}}


def citation_criterion(criterion_id, predicates, level='REQUIRED'):
    return {'id': criterion_id, 'level': level, 'requirement': 'Findings are cited from admitted evidence.',
            'provenance': {'source': 'task_type', 'ref': 'investigation@1'},
            'verifier': {'kind': 'evidence_citation', 'version': 1, 'artifact': 'findings',
                         'schema': 'InvestigationFindings@1', 'predicates': predicates}}


def human_request(task_id, request_id='accept-findings', responses=('ACCEPT', 'INVESTIGATE_FURTHER', 'REJECT')):
    return message('HumanDecisionRequest', {'task_id': task_id, 'origin_task_id': task_id,
        'request_id': request_id, 'revision': 0, 'question': 'Accept the investigation findings?',
        'allowed_responses': list(responses)})


def human_response(task_id, request, value, response_id='response-1'):
    return message('HumanDecisionResponse', {'task_id': task_id, 'request_id': request['payload']['request_id'],
        'request_revision': request['payload']['revision'], 'request_digest': request_digest(request),
        'response_id': response_id, 'value': value})


def investigation_spec(extra_capabilities=()):
    capabilities = ['workspace.read', 'artifact.write', *extra_capabilities]
    return message('TaskSpec', {
        'objective': 'Investigate why ExampleService returns 500 for this request.',
        'completion': [{'criterion': 'The service source was read exactly.',
                        'evidence': {'artifact': 'source', 'sha256': SOURCE_SHA}}],
        'capabilities': capabilities, 'autonomy': {'allowed': capabilities}})


def lowered_c1():
    return {'id': 'c1', 'requirement': 'The service source was read exactly.', 'level': 'REQUIRED',
            'provenance': {'source': 'user'},
            'verifier': {'kind': 'artifact_digest', 'version': 1, 'artifact': 'source', 'sha256': SOURCE_SHA}}


def semantic_criterion(level='ADVISORY', on_low='unknown', source='task_type', depends=('findings-cited',), **extra):
    provenance = {'source': source, 'ref': 'investigation@1'} if source == 'task_type' else {'source': source}
    verifier = {'kind': 'semantic_review', 'version': 1, 'subject': 'findings.conclusion',
                'question': 'Does the cited evidence support the stated cause without contradiction?',
                'on_low_confidence': on_low, 'depends_on': list(depends), **extra}
    return {'id': 'cause-supported', 'level': level, 'provenance': provenance,
            'requirement': 'The cited evidence supports the stated cause without contradiction.',
            'verifier': verifier}


def investigation_contract(task_id, extra=(), semantic=True):
    criteria = [
        lowered_c1(),
        {**journal_criterion('no-mutation', [{'name': 'operation_classes_subset', 'allowed': ['workspace.read']},
                                             {'name': 'admitted_before_observed'}]),
         'requirement': 'No workspace-mutating capability was admitted or executed.'},
        {**journal_criterion('workspace-scope', [{'name': 'workspace_subset'}]),
         'requirement': "Every workspace operation targeted this Task's workspace."},
        citation_criterion('code-path-inspected', [{'name': 'min_cited_receipts', 'operation': OPERATION, 'count': 1}]),
        citation_criterion('findings-cited', [{'name': 'every_claim_cited'}, {'name': 'quotes_match_receipts'}]),
        citation_criterion('conclusion-explicit', [{'name': 'conclusion_status_present'},
                                                   {'name': 'unresolved_requires_uncertainty'}]),
        *([semantic_criterion()] if semantic else []),
        *extra,
    ]
    return message('CompletionContract', {'task_id': task_id, 'revision': 0, 'previous_ref': None,
        'amendment_ref': None, 'task_type': {'template': 'investigation', 'version': 1},
        'request': 'Investigate why ExampleService returns 500 for this request.', 'criteria': criteria})


def read_action():
    return {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.read',
            'input': {'workspace': WORKSPACE, 'path': PATH, 'artifact': 'source'}}


def investigation_request(task_id, contract=None, extra_capabilities=(), grant=None):
    capabilities = ['workspace.read', 'artifact.write', *extra_capabilities]
    return message('TaskRequest', {
        'task_spec': investigation_spec(extra_capabilities),
        'initial_action': read_action(),
        'grant': grant or {'capabilities': capabilities},
        'contract': contract or investigation_contract(task_id)})


def read_result(task_id, content=SOURCE):
    return message('CapabilityResult', {'operation_id': f'{task_id}/1', 'outcome': 'success',
        'output': {'content': content}, 'artifacts': {}, 'error': None})


def findings(receipt_ref, quote='throw new IllegalStateException("customer missing");', lines=(9, 9),
             status='supported', uncertainties=(), path=PATH):
    return message('InvestigationFindings', {
        'conclusion': {'status': status,
                       'statement': 'A missing customer raises IllegalStateException, mapped to 500.'},
        'claims': [{'text': 'handle() throws when the repository returns no customer.',
                    'citations': [{'receipt_ref': receipt_ref, 'path': path, 'lines': list(lines), 'quote': quote}]}],
        'uncertainties': list(uncertainties)})


def write(name, value):
    content = value if isinstance(value, str) else json.dumps(value, sort_keys=True)
    return {'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write', 'input': {'name': name, 'content': content}}


def decision(packet, action):
    turn = packet['payload']
    return message('CognitiveDecision', {k: turn[k] for k in ('task_id', 'task_revision', 'turn_id')}
                   | {'next_action': action})


def amendment(task_id, operations, from_revision=0, request_id='amend-1', actor=None, reason='Explicit user change.'):
    return message('CompletionContractAmendmentRequest', {
        'task_id': task_id, 'request_id': request_id, 'from_revision': from_revision,
        'operations': operations, 'actor': actor or {'kind': 'user', 'via': 'modify-constraints'},
        'reason': reason})
