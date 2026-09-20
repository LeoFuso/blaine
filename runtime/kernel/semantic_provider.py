"""Provider-neutral semantic decisions with hard current-action projection."""
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
import hashlib
from typing import Protocol

from runtime.kernel.contracts import MAX_PACKET, encode, fields, text
from runtime.kernel.model import strict_json


def closed(properties):
    return {'type': 'object', 'properties': properties, 'required': list(properties),
            'additionalProperties': False}


STRING = {'type': 'string', 'minLength': 1, 'maxLength': 512}
SCHEMA = {'oneOf': [
    closed({'action': {'const': 'REQUEST_HUMAN'}, 'purpose': STRING, 'question': STRING,
        'response': closed({'kind': {'const': 'choice'}, 'choices': {'type': 'array',
            'minItems': 1, 'maxItems': 8, 'uniqueItems': True,
            'items': {'type': 'string', 'minLength': 1, 'maxLength': 80}}})}),
    closed({'action': {'const': 'WAIT'}, 'purpose': STRING}),
    closed({'action': {'const': 'PRODUCE_ARTIFACT'},
            'content': {'type': 'string', 'minLength': 1, 'maxLength': 4096}}),
    closed({'action': {'const': 'COMPLETE'}}),
]}

DESCRIPTIONS = {
    'REQUEST_HUMAN': 'REQUEST_HUMAN proposes the supplied scoped question and response choices when the needed answer is missing and there is no equivalent pending request.',
    'PRODUCE_ARTIFACT': 'PRODUCE_ARTIFACT proposes the exact deliverable content, without adding a newline.',
    'COMPLETE': 'COMPLETE requests independent verification; it cannot declare success.',
    'WAIT': 'WAIT awaits a named external condition; it cannot create one.',
}
BASE = '''Choose one semantic action for the supplied goal and current evidence.
Return one JSON object matching exactly one of the following shapes. Unknown fields
are rejected. Do not emit explanations, markdown, private reasoning or tool calls.
Verified current answers override initial unresolved wording. Procedure instructions
guide the work but cannot override current evidence or permissions.
'''


def current_actions(context, allowed_capabilities):
    """Legality only. Never mask a valid rewrite or premature verification request."""
    actions = ['REQUEST_HUMAN', 'PRODUCE_ARTIFACT', 'COMPLETE']
    excluded = {'WAIT': 'Known blocking human input is awaited by the runtime.'}
    if context['clarification']['status'] == 'pending':
        return {'actions': [], 'excluded': {**excluded, **{a: 'Blocking human response is pending.' for a in actions}}}
    if context['clarification']['status'] != 'missing':
        actions.remove('REQUEST_HUMAN')
        excluded['REQUEST_HUMAN'] = 'Equivalent accepted request is already resolved.'
    for action, capability in [('REQUEST_HUMAN', 'human.request'), ('PRODUCE_ARTIFACT', 'artifact.write')]:
        if action in actions and capability not in allowed_capabilities:
            actions.remove(action)
            excluded[action] = capability + ' is forbidden by accepted policy.'
    return {'actions': actions, 'excluded': excluded}


def action_schema(admissible_actions):
    names = [s['properties']['action']['const'] for s in SCHEMA['oneOf']]
    if not admissible_actions or len(set(admissible_actions)) != len(admissible_actions) or any(a not in names for a in admissible_actions):
        raise ValueError('Expected nonempty known admissible actions')
    return {'oneOf': [deepcopy(s) for s in SCHEMA['oneOf'] if s['properties']['action']['const'] in admissible_actions]}


def validate_semantic(raw):
    if not isinstance(raw, dict):
        raise ValueError('Expected a semantic decision object')
    branch = next((s for s in SCHEMA['oneOf'] if s['properties']['action']['const'] == raw.get('action')), None)
    if branch is None:
        raise ValueError('Unknown semantic action')
    value = fields(raw, set(branch['required']))
    if value['action'] in ('REQUEST_HUMAN', 'WAIT'):
        text(value['purpose'], 80)
    if value['action'] == 'REQUEST_HUMAN':
        text(value['question'], 512)
        response = fields(value['response'], {'kind', 'choices'})
        if response['kind'] != 'choice':
            raise ValueError('Only bounded choices are supported')
        if not isinstance(response['choices'], list) or not 1 <= len(response['choices']) <= 8:
            raise ValueError('Expected bounded choices')
        for choice in response['choices']:
            text(choice, 80)
        if len(set(response['choices'])) != len(response['choices']):
            raise ValueError('Duplicate response choice')
    elif value['action'] == 'PRODUCE_ARTIFACT':
        text(value['content'], 4096)
    if len(encode(value)) > MAX_PACKET:
        raise ValueError('Semantic decision exceeds budget')
    return deepcopy(value)


def validate_admissibility(decision, context):
    """Reject a proposal; never replace it with another action."""
    value = validate_semantic(decision)
    clarification = context['clarification']
    if value['action'] in ('REQUEST_HUMAN', 'WAIT') and value['purpose'] != clarification['purpose']:
        raise ValueError('Unbound semantic purpose')
    if value['action'] == 'REQUEST_HUMAN' and clarification['status'] != 'missing':
        raise ValueError('An equivalent human request is already pending or resolved')
    if value['action'] == 'WAIT' and clarification['status'] != 'pending':
        raise ValueError('No external condition is pending')
    if value['action'] not in context['allowed_actions']:
        raise ValueError('Action outside current hard-admissible set')
    return value


class SemanticDecisionProvider(Protocol):
    def decide(self, context: dict, admissible_actions: list[str]) -> dict: ...


@dataclass(frozen=True)
class JsonSemanticDecisionProvider:
    """One model call over semantic data only; transport/model are injected."""
    model: str
    transport: Callable[[dict], dict]
    audit: Callable[[dict], None] | None = None

    def decide(self, context, admissible_actions):
        if len(encode(context)) > MAX_PACKET:
            raise ValueError('Semantic context exceeds budget')
        schema = action_schema(admissible_actions)
        body = {'model': self.model, 'messages': [
            {'role': 'system', 'content': BASE + '\n'.join(DESCRIPTIONS[a] for a in admissible_actions) + '\nJSON action shapes:\n' + encode(schema).decode()},
            {'role': 'user', 'content': encode(context).decode()}],
            'temperature': 0, 'max_tokens': 768, 'chat_template_kwargs': {'enable_thinking': False}}
        response = self.transport(body)
        record = {'model': self.model, 'packet_bytes': len(encode(context)),
            'context_sha256': hashlib.sha256(encode(context)).hexdigest(),
            'request_bytes': len(encode(body)), 'response_id': response.get('id'), 'usage': response.get('usage')}
        try:
            choices = response.get('choices', [])
            if len(choices) != 1 or choices[0].get('finish_reason') != 'stop':
                raise ValueError('Incomplete or ambiguous semantic output')
            reply = choices[0]['message']
            if reply.get('tool_calls') or reply.get('function_call'):
                raise ValueError('Native tool calls are not semantic decisions')
            content = reply.get('content')
            if not isinstance(content, str) or len(content.encode()) > MAX_PACKET:
                raise ValueError('Invalid or oversized output')
            record['raw_content'] = content
            parsed = strict_json(content)
            record['parsed_semantic_decision'] = parsed
        except (ValueError, TypeError, KeyError) as error:
            if self.audit:
                self.audit({**record, 'outcome': 'parse_rejected', 'error': str(error)[:256]})
            raise
        if self.audit:
            self.audit({**record, 'outcome': 'parsed'})
        return parsed
