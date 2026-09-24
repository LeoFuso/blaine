#!/usr/bin/env python3
"""One real authenticated Jev invocation against the isolated candidate boundary.

Exactly one provider call is made by default. It classifies a synthetic worker
binding's suitability through the existing routing seam, so the proof exercises
the integration Blaine would actually use rather than a bare connectivity check.

The credential is supplied by the operator's environment and read only by the
SDK. This probe checks presence, never the value, and retains no provider
diagnostic text. It consumes no frontier dispatch grant, runs outside Task
lifecycle, and changes no routing default: Jev stays a candidate.
"""
import argparse, json, sys, time
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from jev_provider import (  # noqa: E402
    API_KEY_ENV, DEFAULT_MODEL, DESTINATION, JevBoundaryObserver, JevProvider,
    JevUnavailable, JevWorkloadClassifier, ShadowClassifier, credential_present,
)
from runtime.kernel.frontier import WorkerBinding  # noqa: E402
from runtime.kernel.instrument import ContinuationBoundary, ExecutionIdentity, validate_assessment  # noqa: E402
from runtime.kernel.worker_routing import ScriptedClassifier, Workload, select  # noqa: E402

# Neutral synthetic bindings. No real deployment, account or destination is used.
BINDINGS = (
    WorkerBinding('candidate-local', 'synthetic-family', 'synthetic-local', 'synthetic-small',
                  'http://127.0.0.1:8000/v1', False, ('code',), 1),
    WorkerBinding('candidate-remote', 'synthetic-family', 'synthetic-remote', 'synthetic-large',
                  'https://provider.invalid/v1', True, ('code',), 3),
)
RANKS = {'candidate-local': 0, 'candidate-remote': 2}
WORKLOAD = Workload(('code',), 3)


def preflight() -> dict:
    report = {'credential_variable': API_KEY_ENV, 'credential_present': credential_present(),
              'default_model': DEFAULT_MODEL, 'destination': DESTINATION, 'sdk_installed': False,
              'sdk_version': None}
    try:
        import typesafe_sdk
        report['sdk_installed'] = True
        report['sdk_version'] = getattr(typesafe_sdk, '__version__', None)
        from typesafe_sdk import constants
        report['sdk_credential_variable'] = constants.API_KEY_ENV
        report['sdk_default_model'] = constants.DEFAULT_MODEL
        report['sdk_default_base_url'] = constants.DEFAULT_BASE_URL
    except ImportError:
        pass
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--include-boundary', action='store_true',
                        help='add one further call exercising the continuation-boundary observer')
    arguments = parser.parse_args()
    out = arguments.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    checks = preflight()
    summary = {'version': 1, 'increment': 'isolated Jev provider candidate',
               'preflight': checks, 'authenticated_calls_attempted': 0,
               'frontier_dispatch_grants_consumed': 0, 'task_lifecycle_involvement': 'none',
               'routing_default_changed': False, 'status': 'NOT_ATTEMPTED', 'calls': []}
    if not checks['credential_present'] or not checks['sdk_installed']:
        summary['status'] = 'BLOCKED'
        summary['reason'] = ('credential absent from the environment' if not checks['credential_present']
                             else 'the official SDK is not installed')
        (out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
        print(json.dumps(summary, indent=1))
        return 1

    provider = JevProvider()
    metadata = []
    classifier = JevWorkloadClassifier(provider, RANKS, record=metadata.append)
    # Shadow mode proves the accepted routing outcome is untouched while the
    # candidate observes. Only the remote binding is classified, so exactly one
    # authenticated call happens unless a boundary call is explicitly requested.
    shadow = ShadowClassifier(ScriptedClassifier(RANKS), classifier)
    began = time.monotonic()
    try:
        summary['authenticated_calls_attempted'] += 1
        decision = shadow.assess(WORKLOAD, BINDINGS[1])
        observation = shadow.observations[0]
        summary['calls'].append({
            'call': 'routing_suitability', 'outcome': 'ANSWERED' if observation['candidate_suitability'] else 'FAILED',
            'binding_id': BINDINGS[1].binding_id,
            'state_sent': {'required_capabilities': sorted(WORKLOAD.capabilities),
                           'minimum_quality': WORKLOAD.minimum_quality,
                           'binding_capabilities': sorted(BINDINGS[1].capabilities),
                           'binding_quality': BINDINGS[1].quality},
            'accepted_suitability': observation['accepted_suitability'],
            'candidate_suitability': observation['candidate_suitability'],
            'candidate_reason': observation.get('candidate_reason'),
            'agreement': observation['agreement'],
            'candidate_failure': observation['candidate_failure'],
            'applied_to_routing': False,
            **({'model': metadata[0]['model'], 'latency_ms': metadata[0]['latency_ms'],
                'usage': metadata[0]['usage'],
                'cost_observability': metadata[0]['cost_observability']} if metadata else {})})
        summary['accepted_assessment'] = asdict(decision)
        summary['status'] = 'FAILED' if observation['candidate_failure'] else 'AUTHENTICATED'
        if observation['candidate_failure']:
            summary['reason'] = observation['candidate_failure']
    except Exception as error:  # a probe failure is recorded, never hidden
        summary['status'] = 'FAILED'
        summary['reason'] = getattr(error, 'category', type(error).__name__)

    if arguments.include_boundary and summary['status'] == 'AUTHENTICATED':
        summary['authenticated_calls_attempted'] += 1
        boundary = ContinuationBoundary(ExecutionIdentity('synthetic-task', 'run:synthetic'), 2,
                                        'tool_results', model_invocations=2, tool_invocations=1,
                                        last_tool_outcome='success')
        assessment = JevBoundaryObserver(provider).inspect(boundary)
        validate_assessment(assessment, 'jev-boundary-observer')
        summary['calls'].append({'call': 'continuation_boundary', 'outcome': assessment['outcome'],
                                 'label': assessment.get('label'), 'score': assessment.get('score'),
                                 'latency_ms': assessment.get('latency_ms'),
                                 'model': assessment.get('model'),
                                 'input_tokens': assessment.get('input_tokens'),
                                 'output_tokens': assessment.get('output_tokens'),
                                 'detail': assessment.get('detail'),
                                 'intervention_admitted': False})

    # The accepted routing outcome is recomputed without the candidate to show
    # that shadow observation cannot have changed it.
    allowed = {binding.binding_id: {'outcome': 'allow'} for binding in BINDINGS}
    accepted_only = select(WORKLOAD, BINDINGS, ScriptedClassifier(RANKS), allowed)
    summary['accepted_routing_without_candidate'] = {
        'outcome': accepted_only['outcome'], 'selected_binding': accepted_only['selected_binding']}
    summary['probe_runtime_s'] = round(time.monotonic() - began, 2)
    (out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    print(json.dumps(summary, indent=1))
    return 0 if summary['status'] == 'AUTHENTICATED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
