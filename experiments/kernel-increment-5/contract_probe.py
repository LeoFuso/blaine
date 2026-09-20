"""Deterministic contract-fit counterexample; no model or external effects."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import message, validate_spec, validate_result
from runtime.kernel.execution import evaluate


def main():
    out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
    digest = lambda text: hashlib.sha256(text.encode()).hexdigest()
    spec = message('TaskSpec', {'objective': 'Obtain the human decision YES or NO, scoped to request D-1.',
        'completion': [{'criterion': 'Valid scoped human response',
                        'evidence': {'artifact': 'decision', 'sha256': digest('YES')}}],
        'capabilities': ['artifact.write'], 'autonomy': {'allowed': ['artifact.write']}})
    accepted = validate_spec(spec)
    observations = {}
    with tempfile.TemporaryDirectory() as directory:
        store = ArtifactStore(Path(directory))
        for response in ('YES', 'NO'):
            state = {'task_id': 'human-contract-probe',
                     'artifacts': {'decision': store.put('human-contract-probe', response.encode())}}
            observations[response] = evaluate(accepted, state, store)
    assert observations['YES']['payload']['outcome'] == 'satisfied'
    assert observations['NO']['payload']['outcome'] == 'unsatisfied'
    extended = json.loads(json.dumps(spec))
    extended['payload']['completion'][0]['evidence'] = {
        'artifact': 'decision', 'sha256_any_of': [digest('YES'), digest('NO')]}
    try:
        validate_spec(extended)
        raise AssertionError('Unexpected acceptance of unspecified completion contract')
    except ValueError as error:
        extension_error = str(error)
    result = message('TaskResult', {'task_id': 'human-contract-probe', 'outcome': 'FAILED',
        'artifacts': {}, 'completion_ref': None, 'concerns': [], 'decision': 'NO'})
    try:
        validate_result(result, 'human-contract-probe')
        raise AssertionError('Unexpected acceptance of unspecified result field')
    except ValueError as error:
        result_error = str(error)
    summary = {'increment': 5, 'status': 'BLOCKED', 'gate': 'STOP',
        'probe_type': 'deterministic contract-fit counterexample, not a live human interaction',
        'accepted_spec': spec, 'observed_completion': observations,
        'unapproved_alternative_digest_contract': {'accepted': False, 'error': extension_error},
        'unapproved_inline_result_field': {'accepted': False, 'error': result_error},
        'interpretation': 'Existing exact-byte verification cannot express acceptance of either human answer directly. A new trusted response verifier or receipt design needs a narrow semantic decision. Artifact-referenced TaskResult remains a possible representation; inline decision is not currently allowed.',
        'not_proven': ['Human input identity/scope validation', 'duplicate/stale response rejection',
                       'human wait crash/recovery', 'parent receives verified YES/NO'],
        'architecture_impact': 'Local extension required; none applied',
        'llm_calls': 0, 'external_effects': 0, 'runtime_changes': [],
        'decision_required': 'Authorize a narrowly specified scoped human-response verification/result contract before Increment 5 implementation.'}
    (out/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
    print('STOP: contract counterexample reproduced; no runtime semantics changed')


if __name__ == '__main__': main()
