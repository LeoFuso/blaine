"""Transport-neutral bounded human decisions; validation is entirely deterministic."""
import hashlib
from runtime.kernel.contracts import fields, identifier, text, unpack, encode


def validate_request(raw):
    request = fields(unpack(raw, 'HumanDecisionRequest'),
        {'task_id', 'origin_task_id', 'request_id', 'revision', 'question', 'allowed_responses'})
    for name in ('task_id', 'origin_task_id', 'request_id'):
        identifier(request[name])
    text(request['request_id'], 64)
    if type(request['revision']) is not int or request['revision'] < 0:
        raise ValueError('Invalid human request revision')
    text(request['question'], 512)
    choices = request['allowed_responses']
    if not isinstance(choices, list) or not 1 <= len(choices) <= 8:
        raise ValueError('Expected bounded response set')
    for choice in choices:
        text(choice, 80)
    if len(set(choices)) != len(choices):
        raise ValueError('Duplicate allowed response')
    return request


def request_digest(raw):
    validate_request(raw)
    return hashlib.sha256(encode(raw)).hexdigest()


def validate_response(raw, accepted_request, task_id):
    request = validate_request(accepted_request)
    response = fields(unpack(raw, 'HumanDecisionResponse'),
        {'task_id', 'request_id', 'request_revision', 'request_digest', 'response_id', 'value'})
    identifier(response['response_id'])
    if (request['task_id'] != task_id or response['task_id'] != task_id or
            response['request_id'] != request['request_id'] or
            type(response['request_revision']) is not int or
            response['request_revision'] != request['revision'] or
            response['request_digest'] != request_digest(accepted_request)):
        raise ValueError('Response does not match accepted Task/request revision and digest')
    if not isinstance(response['value'], str) or response['value'] not in request['allowed_responses']:
        raise ValueError('Response is outside the allowed set')
    return response


def human_requirement(spec, request_id):
    matches = [c['evidence'] for c in spec['completion']
               if c['evidence'].get('verifier') == 'human_response' and
               c['evidence']['request']['payload']['request_id'] == request_id]
    if len(matches) != 1:
        raise ValueError('Expected one accepted human request')
    return matches[0]
