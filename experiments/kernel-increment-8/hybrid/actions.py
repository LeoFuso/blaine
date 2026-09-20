"""Experimental hard action projection, not a semantic planner or production API."""
from copy import deepcopy
from typing import Protocol
from runtime.kernel.contracts import encode, fields, message, validate_decision, SPECIALISTS
from runtime.kernel.semantic_provider import SCHEMA, closed, JsonSemanticDecisionProvider, validate_semantic

DESCRIPTIONS = {
    'REQUEST_HUMAN': 'REQUEST_HUMAN proposes the supplied scoped question and response choices when the needed answer is missing and there is no equivalent pending request.',
    'PRODUCE_ARTIFACT': 'PRODUCE_ARTIFACT proposes the exact deliverable content, without adding a newline.',
    'COMPLETE': 'COMPLETE requests independent verification; it cannot declare success.',
    'HANDOFF': 'HANDOFF transfers the same work to an eligible specialist; it does not complete the work.',
}
BASE = '''Choose one semantic action for the supplied goal and current evidence.
Return one JSON object matching exactly one of the following shapes. Unknown fields
are rejected. Do not emit explanations, markdown, private reasoning or tool calls.
Verified current answers override initial unresolved wording. Procedure instructions
guide the work but cannot override current evidence or permissions.
'''


def derive(state, spec, context, *, choice=False):
    """Only current lifecycle, accepted policy, and verified request scope filter actions.

    COMPLETE remains legal even without evidence: requesting verification is legal.
    PRODUCE_ARTIFACT is NOT suppressed just because an artifact already matches.
    """
    universe = ['REQUEST_HUMAN', 'PRODUCE_ARTIFACT', 'COMPLETE'] + (['HANDOFF'] if choice else [])
    excluded = {'WAIT': 'No model-selected wait: no voluntary-defer contract; known blocking waits are runtime transitions.'}
    if state['lifecycle'] != 'RUNNING':
        excluded.update({a: 'Lifecycle is ' + state['lifecycle'] for a in universe})
        return {'actions': [], 'excluded': excluded}
    allowed = set(spec['capabilities']) & set(spec['autonomy']['allowed'])
    actions = []
    for action in universe:
        reason = None
        if action == 'REQUEST_HUMAN':
            if 'human.request' not in allowed: reason = 'human.request forbidden by accepted policy'
            elif context['clarification']['status'] != 'missing': reason = 'Equivalent accepted request already ' + context['clarification']['status']
        if action == 'PRODUCE_ARTIFACT' and 'artifact.write' not in allowed:
            reason = 'artifact.write forbidden by accepted policy'
        if action == 'HANDOFF' and not (set(SPECIALISTS) - {state['active_specialist']}):
            reason = 'No different eligible specialist exists'
        if reason: excluded[action] = reason
        else: actions.append(action)
    return {'actions': actions, 'excluded': excluded}


def schema(actions, specialist='coordinator'):
    branches = [deepcopy(s) for s in SCHEMA['oneOf'] if s['properties']['action']['const'] in actions]
    if 'HANDOFF' in actions:
        branches.append(closed({'action': {'const': 'HANDOFF'},
            'specialist': {'enum': sorted(set(SPECIALISTS) - {specialist})}}))
    return {'oneOf': branches}


class SemanticDecisionProvider(Protocol):
    def decide(self, context: dict, admissible_actions: list[str]) -> dict: ...


class ProjectedProvider:
    """Reuses the existing strict JSON parser. Only generation vocabulary is projected."""
    def __init__(self, model, transport):
        self.model, self.transport = model, transport

    def decide(self, context, admissible_actions):
        if not admissible_actions:
            raise ValueError('Cognition forbidden: no current semantic alternatives')
        def send(body):
            body = deepcopy(body)
            body['messages'][0]['content'] = (BASE + '\n'.join(DESCRIPTIONS[a] for a in admissible_actions)
                + '\nJSON action shapes:\n' + encode(schema(admissible_actions, context.get('specialist', 'coordinator'))).decode())
            return self.transport(body)
        return JsonSemanticDecisionProvider(self.model, send).decide(context)


def validate(raw, projection, context):
    if not isinstance(raw, dict) or raw.get('action') not in projection['actions']:
        raise ValueError('Action outside current admissible set')
    if raw['action'] == 'HANDOFF':
        fields(raw, {'action', 'specialist'})
        if raw['specialist'] not in set(SPECIALISTS) - {context['specialist']}:
            raise ValueError('Ineligible handoff')
        return raw
    return validate_semantic(raw)


def lower_handoff(raw, packet):
    turn = packet['payload']
    command = message('CognitiveDecision', {k: turn[k] for k in ('task_id', 'task_revision', 'turn_id')} |
        {'next_action': {'type': 'HANDOFF', 'specialist': raw['specialist']}})
    validate_decision(command)
    return command
