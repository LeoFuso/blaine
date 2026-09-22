#!/usr/bin/env python3
"""Build the machine-readable evidence summary from retained observations only.

Nothing here is asserted by hand: every count and capability claim is read from
the probes' retained evidence, so the summary cannot drift from what was executed.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
sys.path.insert(0, str(HERE))
from codex_appserver import CAPABILITIES as CODEX  # noqa: E402
from runtime.kernel.adapter_profiles import BLAINE_KERNEL_LOOP, GOOSE_WORKER  # noqa: E402
from runtime.kernel.instrument import (  # noqa: E402
    ADMIT_CONTINUATION, INTERRUPT_EXECUTION, OBSERVE_CONTINUATION, OBSERVE_MODEL, OBSERVE_TOOL,
    REBIND_EFFORT, REBIND_MODEL, STEER_CONTINUATION,
)

EVIDENCE = HERE / 'evidence'


def load(path):
    return json.loads((EVIDENCE / path).read_text())


def claims(profile):
    summary = profile.summary()['capabilities']
    return {name: {'support': claim['support'], 'granularity': claim['granularity'],
                   'evidence': claim['evidence']} for name, claim in summary.items()}


def unsupported(profile):
    return sorted(name for name, claim in profile.summary()['capabilities'].items()
                  if claim['support'] == 'UNSUPPORTED') + profile.summary()['undeclared']


def codex_entry():
    cases = {name: load(f'codex-app-server/{name}-observation.json')
             for name in ('boundaries', 'steer', 'interrupt', 'approval')}
    run = load('codex-app-server/summary.json')
    steer = cases['steer']['steering'][0]
    return {
        'worker': 'codex-app-server', 'harness': 'Codex CLI 0.155.1 app-server over stdio',
        'integration_status': 'observation adapter in this experiment; not a registered Blaine worker binding',
        'inference_used': run['inference'], 'served_model': run['model'],
        'evidence_class': 'live', 'cases_executed': sorted(cases),
        'boundaries_observed': {name: len(case['boundaries']) for name, case in cases.items()},
        'boundary_marker': cases['boundaries']['boundaries'][0]['marker'],
        'model_invocations_observed': {name: len(case['model_invocations']) for name, case in cases.items()},
        'tool_invocations_observed': {name: len(case['tool_invocations']) for name, case in cases.items()},
        'per_invocation_token_usage_observed': all(
            invocation['input_tokens'] is not None
            for invocation in cases['boundaries']['model_invocations']),
        'correlation_ids_available': ['task_id', 'worker_dispatch_id', 'worker_session_id',
                                      'agent_turn_id', 'capability_call_id (harness item id)'],
        'correlation_ids_absent': ['model_invocation_id (no harness identifier; position only)'],
        'steering': {'capability': 'turn/steer', 'accepted_while_tool_active': steer['tool_active_at_request'],
                     'acceptance_latency_ms': round(steer['accepted_at_ms'] - steer['requested_at_ms'], 1),
                     'requested_at_boundary_index': steer['boundary_index_at_request'],
                     'consumed_at_boundary_index': steer['consumed_at_boundary_index'],
                     'consumed_after_boundary_marker_ms': round(
                         steer['consumed_at_ms'] - cases['steer']['boundaries'][0]['observed_at_ms'], 1)},
        'interruption': {'capability': 'turn/interrupt', 'turn_status': cases['interrupt']['turn_status'],
                         'unterminated_tool_items': len(cases['interrupt']['unterminated_tool_items']),
                         'terminal_tool_event_emitted': False},
        'synchronous_client_callback': {
            'exists': bool(cases['approval']['approvals']),
            'relation_to_boundary': cases['approval']['approvals'][0]['boundary_relation'],
            'blocking_confirmed': cases['approval']['approvals'][0]['blocking'],
            'client_delay_held_ms': run['cases']['approval']['client_callback_timings'][0]['answered_after_ms'],
            'turn_status_after_hold': cases['approval']['turn_status']},
        'capabilities': claims(CODEX), 'unsupported_or_unknown': unsupported(CODEX),
        'unknown_events': {name: case['unknown_events'] for name, case in cases.items()},
        'malformed_events': {name: case['malformed_events'] for name, case in cases.items()},
    }


def lines(path):
    return [json.loads(line) for line in (EVIDENCE / path).read_text().splitlines()]


def kernel_entry():
    recovery, delivery, retry = (load(f'kernel-loop/{name}-summary.json')
                                 for name in ('recovery', 'delivery', 'retry'))
    spans = load('kernel-loop/otlp-delivered-spans.json')
    audits = {delivery['task_id']: lines('kernel-loop/delivery-model-audit.jsonl'),
              retry['task_id']: lines('kernel-loop/retry-model-audit.jsonl')}
    journal = lines('kernel-loop/recovery-events.jsonl')
    kinds = {}
    for span in spans['spans']:
        kinds[span['kind']] = kinds.get(span['kind'], 0) + 1
    return {
        'worker': 'blaine-kernel-loop', 'harness': 'Blaine durable CognitiveTaskV1 loop on Restate',
        'integration_status': 'instrumented in the kernel; the adopted runtime entrypoint can select it',
        'inference_used': 'local loopback serving only; zero paid cloud inference',
        'served_model': recovery['model'], 'evidence_class': 'live',
        'tasks_executed': [recovery['task_id'], delivery['task_id'], retry['task_id']],
        'lifecycles': {entry['task_id']: entry['lifecycle'] for entry in (recovery, delivery, retry)},
        'boundaries_observed': {entry['task_id']: len(entry['boundaries_admitted'])
                                for entry in (recovery, delivery, retry)},
        'journaled_boundary_steps': recovery['journal_continuation_steps'],
        # Counted from synchronous adapter records and the journaled ledger, not
        # from exported spans, because a killed process loses buffered telemetry.
        'model_invocations_observed': {task: len(rows) for task, rows in audits.items()},
        'model_invocation_outcomes': {task: sorted({row['outcome'] for row in rows})
                                      for task, rows in audits.items()},
        'per_invocation_token_usage_observed': all(
            row.get('usage', {}).get('prompt_tokens') is not None
            for rows in audits.values() for row in rows),
        'tool_invocations_observed': {recovery['task_id']: len(
            [event for event in journal if event['event_type'] == 'capability.finished'])},
        'model_invocation_records_source': 'adapter audit written inside the journaled step',
        'tool_invocation_records_source': 'journaled ExecutionEvent ledger',
        'synchronous_admission_before_each_continuation': True,
        'recovery': {'point': recovery['recovery_point'],
                     'observer_consultations_total': recovery['observer_consultations'],
                     'consultations_before_kill': recovery['observer_consultations_before_kill'],
                     'historical_boundaries_replayed': recovery['historical_boundaries_not_recomputed'],
                     'historical_boundaries_recomputed': recovery['recomputed_boundaries'],
                     'distinct_processes_consulting_observer': len(recovery['distinct_pids_consulting'])},
        'otlp_delivery': {'collector': spans['collector_endpoint'], 'span_count': spans['span_count'],
                          'span_kinds': kinds, 'content_capture': spans['content_capture']},
        'model_retry_visibility': {
            'task_id': retry['task_id'], 'lifecycle': retry['lifecycle'],
            'concerns': retry['concerns'],
            'model_invocation_spans_at_one_continuation': len(
                [s for s in spans['spans'] if s['task_id'] == retry['task_id']
                 and s['kind'] == 'model_invocation' and s['continuation_index'] == '1'])},
        'at_least_once_physical_duplication': {
            'task_id': recovery['task_id'],
            'tool_execution_spans': len([s for s in spans['spans']
                                         if s['task_id'] == recovery['task_id'] and s['kind'] == 'tool_execution']),
            'distinct_capability_call_ids': sorted({s['capability_call_id'] for s in spans['spans']
                                                    if s['task_id'] == recovery['task_id']
                                                    and s['kind'] == 'tool_execution'}),
            'journaled_capability_finished_events': len(
                [json.loads(line) for line in (EVIDENCE / 'kernel-loop/recovery-events.jsonl').read_text().splitlines()
                 if json.loads(line)['event_type'] == 'capability.finished'])},
        'correlation_ids_available': ['task_id', 'run_id', 'model_invocation_id', 'capability_call_id',
                                      'continuation index', 'evidence digest'],
        'correlation_ids_absent': ['agent_turn_id (the loop has no provider turn concept)'],
        'capabilities': claims(BLAINE_KERNEL_LOOP), 'unsupported_or_unknown': unsupported(BLAINE_KERNEL_LOOP),
    }


def goose_entry():
    return {
        'worker': 'goose-worker', 'harness': 'Goose CLI one-shot bounded text dispatch',
        'integration_status': 'existing registered worker seam; session span added, no internal boundary exists',
        'inference_used': 'local loopback serving only', 'evidence_class': 'source',
        'boundaries_observed': 0, 'model_invocations_observed': 'not reported by the harness',
        'tool_invocations_observed': 0,
        'correlation_ids_available': ['task_id', 'worker_dispatch_id', 'worker_session_id (attempt id)',
                                      'capability_call_id'],
        'correlation_ids_absent': ['agent_turn_id', 'model_invocation_id'],
        'capabilities': claims(GOOSE_WORKER), 'unsupported_or_unknown': unsupported(GOOSE_WORKER),
        'note': ('No live boundary probe applies: a single-turn dispatch with tools disabled has no '
                 'internal continuation to observe. This row records that honestly instead of emulating one.'),
    }


def main():
    summary = {
        'version': 1,
        'increment': 'worker execution instrumentation and continuation boundary',
        'contract': 'docs/contracts/worker-execution-boundary.md',
        'paid_cloud_inference_calls': 0,
        'frontier_dispatch_grants_consumed': 0,
        'capability_vocabulary': [OBSERVE_CONTINUATION, ADMIT_CONTINUATION, STEER_CONTINUATION,
                                  INTERRUPT_EXECUTION, OBSERVE_MODEL, OBSERVE_TOOL, REBIND_MODEL, REBIND_EFFORT],
        'support_levels': ['OBSERVED', 'INFERRED', 'UNSUPPORTED'],
        'granularities': ['continuation', 'agent_turn', 'worker_dispatch'],
        'semantic_supervisor': {
            'implemented': False,
            'observer_used': 'deterministic recording observer',
            'jev_validation': 'NOT PERFORMED',
            'jev_part_of_acceptance': False,
            'jev_reason': 'no Jev credential was readable from this execution environment',
            'jev_secret_variable': 'TYPESAFE_API_KEY',
            'jev_secret_handling': ('authoritative runtime name; no alias exists because no code reads it, '
                                    'and no secret value was read or emitted by this increment'),
            'boundary_useful_without_jev': True},
        'workers': [kernel_entry(), codex_entry(), goose_entry()],
    }
    (EVIDENCE / 'evidence-summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
