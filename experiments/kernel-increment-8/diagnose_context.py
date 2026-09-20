"""Offline audit of the retained three-turn counterexample. No inference or effects."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime.kernel.contracts import encode, validate_decision
from runtime.kernel.model import strict_json

EVIDENCE = Path(__file__).with_name('evidence')
OUT = EVIDENCE / 'context-diagnostic'


def read(name):
    return json.loads((EVIDENCE / name).read_text())


def rows(name):
    return [json.loads(line) for line in (EVIDENCE / name).read_text().splitlines()]


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(name, data):
    (OUT / name).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def main():
    # Capture existing inputs/source integrity, excluding this audit's own output.
    paths = sorted(set(ROOT.glob('runtime/kernel/*.py')) |
                   set(ROOT.glob('tests/test_kernel*.py')) |
                   set(ROOT.glob('scripts/verify-kernel*.py')) |
                   {p for p in EVIDENCE.rglob('*') if p.is_file() and OUT not in p.parents} |
                   {EVIDENCE.parent / 'probe_app.py', EVIDENCE.parent / 'speckit-clarification.md'})
    before = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in paths}
    cognition, wire, model, policy = [rows(n + '.jsonl') for n in ('cognition', 'wire', 'model', 'policy')]
    capabilities = rows('capabilities.jsonl')
    assert len(cognition) == len(wire) == len(model) == len(policy) == 3
    artifacts, inventory = {}, []
    for path in sorted((EVIDENCE / 'artifacts/procedure').iterdir()):
        data = path.read_bytes()
        assert digest(data) == path.name
        try:
            value = json.loads(data)
        except json.JSONDecodeError:
            value = None
        ref = 'artifact://procedure/sha256:' + path.name
        artifacts[ref] = value
        inventory.append({'ref': ref, 'bytes': len(data), 'digest_valid': True,
                          'kind': value.get('kind') if isinstance(value, dict) else 'exact_bytes'})
    external = [(ref, value) for ref, value in artifacts.items()
                if isinstance(value, dict) and value.get('kind') == 'ExternalInput']
    assert len(external) == 1
    assert not any(x['kind'] in ('HumanDecisionRequest', 'HumanDecisionResponse',
                               'TaskResult', 'CompletionEvaluation') for x in inventory)
    stopped = read('stopped-state.json')['payload']
    assert stopped['completion_ref'] is None and stopped['lifecycle'] == 'WAITING'
    assert not stopped.get('human_responses') and not stopped['children']
    assert artifacts[stopped['observation_ref']] == capabilities[0]['result']
    OUT.mkdir(exist_ok=True)
    table = []
    for index, (c, w, m, p) in enumerate(zip(cognition, wire, model, policy), 1):
        packet, decision = c['packet'], c['decision']
        turn = packet['payload']
        messages = w['request']['messages']
        assert [x['role'] for x in messages] == ['system', 'user']
        assert json.loads(messages[1]['content']) == packet
        raw = w['raw_response_safe']['choices'][0]['content']
        assert strict_json(raw) == decision == m['decision']
        parsed = validate_decision(strict_json(raw))  # Pure validation, no adapter/provider call.
        assert all(parsed[k] == turn[k] for k in ('task_id', 'task_revision', 'turn_id'))
        assert digest(raw.encode()) == m['content_sha256'] and m['outcome'] == 'validated'
        assert w['raw_response_safe']['id'] == m['response_id']
        assert p['decision_id'] == turn['turn_id'] and p['gate']['outcome'] == 'allow'
        assert packet in artifacts.values() and decision in artifacts.values()
        observations = turn['observations']
        direct = [x for x in observations if x['kind'] == 'ExternalInput']
        procedure = [x for x in turn['context'] if isinstance(x['content'], dict)
                     and x['content'].get('classification') == 'procedure']
        execution = [x for x in capabilities if x['request']['payload']['operation_id'] == turn['turn_id']]
        record = {
            'turn_id': turn['turn_id'], 'objective_as_sent': turn['objective'],
            'lifecycle': {'present_in_prompt': False, 'at_cognition': 'RUNNING',
                          'basis': 'Source reconstruction plus captured allow gate; not a per-turn status snapshot'},
            'procedure_instructions': procedure,
            'human_decision_request': {'typed_request': None, 'mechanism': 'generic WAIT / text',
                'prior_wait_resolved': index > 1, 'resolution_visible_directly': bool(direct),
                'basis': 'wait-state.json, input-receipt.json, retained ExternalInput and workflow source'},
            'human_response_directly_present': direct,
            'verified_human_decision_response_or_result': None,
            'durable_external_input_for_audit_only': {'ref': external[0][0], 'value': external[0][1]}
                if index > 1 else None,
            'authoritative_context_as_sent': [x for x in turn['context'] if x['authority'] in ('task', 'artifact')],
            'completion_criteria_as_sent': turn['completion'],
            'completion_evaluation_as_sent': [x for x in observations if x['kind'] == 'CompletionEvaluation'],
            'capability_results_as_sent': [x for x in observations if x['kind'] == 'CapabilityResult'],
            'other_context_sources': [x for x in turn['context'] if x not in procedure and x['authority'] not in ('task', 'artifact')],
            'exact_cognitive_packet': packet, 'exact_provider_request': w['request'],
            'provider_endpoint': w['endpoint'], 'raw_provider_response_safe': w['raw_response_safe'],
            'parsed_validated_decision': decision, 'captured_validation': m,
            'offline_validation': 'PASS: same strict parser and application validator; no inference',
            'captured_policy_gate': p['gate'], 'effect_execution_after_decision': execution,
        }
        save(f'turn-{index}.json', record)
        table.append({'turn': index, 'revision': turn['task_revision'],
            'observation_kinds': [x['kind'] for x in observations],
            'direct_answer': bool(direct), 'verified_human_response': False,
            'artifact_sources': [x['source'] for x in turn['context'] if x['authority'] == 'artifact'],
            'action': parsed['next_action'], 'packet_bytes': len(encode(packet)), 'usage': m['usage']})
    assert table[1]['direct_answer'] and not table[2]['direct_answer']
    assert table[2]['observation_kinds'] == ['CapabilityResult']
    assert capabilities[0]['result']['payload']['output']['sha256'] == cognition[2]['packet']['payload']['completion'][0]['evidence']['sha256']
    assert all(c['packet']['payload']['objective'] == cognition[0]['packet']['payload']['objective'] for c in cognition)
    assert all('reason' not in c['decision']['payload'] for c in cognition)
    after = {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in paths}
    assert before == after
    save('integrity.json', {'inputs_and_behavior_files_unchanged': before == after,
                          'sha256': before, 'artifact_inventory': inventory})
    save('summary.json', {
        'increment': '8 diagnostic', 'status': 'DIAGNOSTIC_COMPLETE_STOP',
        'acceptance_gate': 'REMAINS_FAILED', 'new_model_calls': 0, 'live_reproductions': 0,
        'classification': 'STALE_OBJECTIVE_OR_PROCEDURE_STATE',
        'classification_detail': 'Confirmed stale objective assertion; procedure itself says not to repeat answered questions.',
        'context_projection_finding': 'Durable accepted ExternalInput is omitted after observation_ref advances to CapabilityResult. No verified HumanDecisionResponse was created, so category 1 as strictly defined is not fully established.',
        'model_causality': 'Not isolated: missing resolution plus stale assertion explain a plausible WAIT; matching artifact digest and COMPLETE instruction also support COMPLETE. No model defect or inevitable WAIT established.',
        'A_answer_available_turn_2': True,
        'B_absent_turn_3': 'Only latest observation is projected; generic text answer is not retained in Task artifact map or a resolved-decision field.',
        'C_verified_replacement': False,
        'D_stale_objective': True,
        'E_artifact_visible_turn_3': 'Successful CapabilityResult and answer ref/digest; exact bytes and human provenance are absent.',
        'F_explainable_without_model_defect': 'Yes, as a plausible response to incomplete/conflicting context; unique internal cause cannot be inferred.',
        'turn_diff': table,
        'secondary_issue': 'Objective/procedure request reason but sent guidance schema excludes reason; application validator accepts it. No causal link to WAIT established.',
        'boundary': 'Durable accepted input/artifacts -> bounded Context Reconstruction -> cognition; initial objective vs current resolved clarification.',
        'smallest_proposed_correction': 'Project a bounded scoped resolution/value with exact source and validation status beyond the next observation. Distinguish initial uncertainty from current resolved context without mutating accepted intent. Reuse the existing typed human-response path if independently verified human authority is required.',
        'correction_applied': False,
        'next': 'Human review/authorization of a bounded context correction; remain at Increment 8.'})
    print(json.dumps({'status': 'DIAGNOSTIC_COMPLETE_STOP', 'turns_verified': 3,
                      'artifacts_verified': len(inventory), 'new_model_calls': 0,
                      'behavior_and_captured_inputs_unchanged': True, 'evidence': str(OUT.relative_to(ROOT))}))


if __name__ == '__main__':
    main()
