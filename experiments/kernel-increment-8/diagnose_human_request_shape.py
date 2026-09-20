"""Audit captured shape guidance and run synthetic boundary controls; no network."""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime.kernel.contracts import encode, message
from runtime.kernel.execution import policy_gate
from runtime.kernel.model import LocalModelCognition, SYSTEM, decision_schema

BASE = Path(__file__).with_name('evidence') / 'verified-resolution'
OUT = BASE.parent / 'human-request-shape-diagnostic'
MARKER = 'Required output JSON Schema (guidance only; emit an instance, not the schema):\n'


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2) + '\n')


def main():
    OUT.mkdir(exist_ok=True)
    wire = [json.loads(line) for line in (BASE / 'acceptance/wire.jsonl').read_text().splitlines()]
    decisions = [json.loads(line) for line in (BASE / 'acceptance/cognition.jsonl').read_text().splitlines()]
    gates = [json.loads(line) for line in (BASE / 'acceptance/policy.jsonl').read_text().splitlines()]
    spec = json.loads((BASE / 'acceptance/procedure-spec.json').read_text())['payload']
    assert len(wire) == len(decisions) == len(gates) == 16
    captures = []
    for w, c, g in zip(wire, decisions, gates):
        packet = json.loads(w['request']['messages'][1]['content'])
        turn = packet['payload']
        sent = w['request']['messages'][0]['content']
        assert sent == SYSTEM + '\n' + MARKER + encode(decision_schema(turn)).decode()
        assert packet == c['packet']
        raw = json.loads(w['raw_response_safe']['choices'][0]['content'])
        assert raw == c['decision']
        assert set(raw['payload']['next_action']['input']) == {'request', 'version'}
        assert g['gate']['outcome'] == 'deny'
        captures.append({'turn_id': turn['turn_id'], 'raw_equals_parsed': True,
            'guidance_matches_current': True, 'policy': g['gate'],
            'requested_model': w['request']['model'], 'response_model': w['raw_response_safe']['model'],
            'endpoint': w['endpoint'], 'response_id': w['raw_response_safe']['id']})
    packet = decisions[0]['packet']
    turn = packet['payload']
    state = {'task_id': turn['task_id'], 'revision': turn['task_revision'],
             'iteration': turn['iteration'], 'lifecycle': 'RUNNING', 'artifacts': {}}
    request = spec['completion'][0]['evidence']['request']
    malformed_request = copy.deepcopy(request); malformed_request['unexpected'] = True
    cases = [('valid', {'request': request}, 'allow'),
             ('extra_input_version', {'request': request, 'version': 1}, 'deny'),
             ('extra_input_unknown', {'request': request, 'unexpected': True}, 'deny'),
             ('extra_input_kind', {'request': request, 'kind': 'CapabilityInput'}, 'deny'),
             ('missing_request', {}, 'deny'), ('version_only', {'version': 1}, 'deny'),
             ('null_request', {'request': None}, 'deny'),
             ('extra_request_field', {'request': malformed_request}, 'deny'),
             ('missing_request_version', {'request': {k: v for k, v in request.items() if k != 'version'}}, 'deny'),
             ('null_input', None, 'adapter_rejected'), ('list_input', [], 'adapter_rejected'),
             ('string_input', 'request', 'adapter_rejected')]
    controls = []
    for name, value, expected in cases:
        raw = message('CognitiveDecision', {k: turn[k] for k in ('task_id', 'task_revision', 'turn_id')} | {
            'next_action': {'type': 'INVOKE_CAPABILITY', 'capability': 'human.request', 'input': value}})
        before = copy.deepcopy(raw)
        synthetic = {'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(raw)}}]}
        parsed, gate = None, None
        try:
            parsed = LocalModelCognition(transport=lambda _: synthetic)(packet)
            assert parsed == before
            gate = policy_gate(parsed, state, spec)
            assert parsed == before
            outcome = gate['outcome']
        except ValueError:
            outcome = 'adapter_rejected'
        assert raw == before and outcome == expected
        controls.append({'case': name, 'source': 'synthetic provider response, not inference',
            'raw_decision': before, 'parsed_decision': parsed, 'policy': gate,
            'expected': expected, 'observed': outcome, 'input_unchanged': True,
            'effect_dispatched': False})
    schema = json.loads(wire[0]['request']['messages'][0]['content'].split(MARKER)[1])
    action = next(a for a in schema['properties']['payload']['properties']['next_action']['anyOf']
                  if a['properties'].get('capability', {}).get('const') == 'human.request')
    assert set(action['properties']['input']['properties']) == {'request'}
    assert action['properties']['input']['additionalProperties'] is False
    previous = json.loads((BASE / 'source-integrity.json').read_text())['after']
    current = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in previous}
    assert current == previous
    tests = (OUT / 'tests.txt').read_text()
    assert 'Ran 48 tests' in tests and tests.rstrip().endswith('OK')
    save('controls.json', controls)
    save('guidance.json', {'exact_first_provider_request': wire[0]['request'],
        'raw_response_safe': wire[0]['raw_response_safe'], 'human_request_action_schema': action,
        'valid_version_locations': ['$.version', '$.payload.next_action.input.request.version'],
        'invalid_observed_location': '$.payload.next_action.input.version', 'capture_checks': captures})
    save('source-integrity.json', {'all_preexisting_behavior_files_unchanged': True, 'sha256': current})
    save('summary.json', {'increment': '8 human.request shape diagnostic', 'status': 'STOP',
        'classification': 'MODEL_ACTION_SERIALIZATION_BEHAVIOR', 'classification_scope':
            'Observed shape violation despite explicit schema; not a general model-quality claim or proof of internal cause.',
        'required_shape_explicit': True, 'version_forbidden_in_input': True,
        'contract_schema_gate_agree_on_input_keys': True,
        'prose_observation': 'No dedicated human.request concrete example; top-level version instruction and nested request version could be overgeneralized, but that is an unproven model interpretation, not an ambiguous schema.',
        'other_guidance_differences': 'Schema string bounds are broader than runtime byte/identifier/nonblank/uniqueness checks, and accepted-request equality is enforced by policy. None admits input.version or accounts for this rejected field.',
        'captured_live_calls_inspected': 16, 'new_live_calls': 0, 'guidance_changed': False,
        'validation_changed': False, 'projection_changed': False, 'focused_tests_passed': 48,
        'synthetic_controls_passed': len(controls), 'synthetic_negative_controls': len(controls)-1,
        'effects_dispatched': 0, 'acceptance_rerun': False, 'increment_8_gate': 'REMAINS_FAILED',
        'next_increment': 8, 'next_decision': 'Whether to authorize a separately bounded serialization-guidance experiment despite the already-correct schema; do not weaken validation or advance.'})
    print(json.dumps({'status': 'STOP', 'classification': 'MODEL_ACTION_SERIALIZATION_BEHAVIOR',
                      'controls_passed': len(controls), 'new_inference': 0, 'behavior_changed': False}))


if __name__ == '__main__':
    main()
