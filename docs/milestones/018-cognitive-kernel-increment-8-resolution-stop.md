# Increment 8 — verified clarification projection implemented; live gate FAIL / STOP

The authorized correction reuses Increment 5's accepted HumanDecisionRequest /
HumanDecisionResponse artifacts. No second answer store or conversation history
was added. Increment 8 remains unverified end to end; Increment 9 was not started.

## Scoped implementation

[Context reconstruction](../../runtime/kernel/context.py) selects human criteria
from the accepted TaskSpec and applies the **existing** deterministic verifier
to each. Only a satisfied criterion yields a bounded, versioned
`HumanDecisionResolution` context item: Task identity, originating Task identity,
request identity/revision, resolved value, verified status and exact response ref.
The verifier checks runtime accepted-input provenance, request scope/version/value
and artifact digest. Reconstruction rechecks the artifact; projection is not a
new authority or persisted state mechanism.

Human artifacts that are stale, unrelated or unaccepted are not projected as
resolutions. A bounded context instruction makes verified current resolutions
take precedence over initial unresolved wording, without mutating the objective
or granting completion/side-effect authority. Normal artifacts retain their
existing reference projection. Existing packet/item limits remain enforced.

The live fixture now accepts a scoped retention request with two allowed answers,
uses `human.request`, typed WAIT and `submit_human_response`, and still requires
the exact answer artifact independently. Existing policy requires publication
before waiting, so clarification expands to two decisions. Expected sequence:
`human.request → WAIT → artifact.write → COMPLETE`. The question is carried by
the accepted request, replacing the previous fixture's optional `reason` check;
the cognition adapter and its guidance schema are unchanged. The procedure's
Blaine binding names this existing typed path instead of generic ExternalInput.
The newly submitted objective is immutable throughout a run and retains its
initial unresolved wording so current resolution must be distinguishable.

The probe includes an experiment-only checkpoint to kill/restart its isolated
runtime after the artifact write, plus seven invalid-input controls. Neither
checkpoint nor live input controls were reached in this failed run.

## Evidence

Baseline: **37/37 tests passed**. With seven projection tests: **44/44 passed**,
including the existing HumanDecision positive and negative controls. New tests
cover no invented resolution; projection after a subsequent capability observation;
wrong Task/request/revision/digest/version/value, malformed, unaccepted and corrupt
responses; an independently valid unrelated decision excluded; a fresh subprocess
reconstructing from exact persisted artifacts; and response-only completion being
unsatisfied until the exact deliverable exists. These are deterministic tests,
not live inference or authenticated human interaction.

The single live attempt made **16** JSON-only calls to existing local vLLM,
`http://127.0.0.1:8000/v1/chat/completions`, requesting and reporting
`Qwen/Qwen3.5-9B`. Each returned the same capability-input shape error:

```json
{"type":"INVOKE_CAPABILITY","capability":"human.request",
 "input":{"request":"<valid versioned HumanDecisionRequest>","version":1}}
```

Here the string is illustrative; captured requests contain the actual request
object. Only `request` is allowed inside `input`; its extra sibling `version`
is invalid. Raw provider content matches the parsed decisions. The existing
envelope validator accepts an object-valued capability input; the unchanged
capability-specific PolicyGate rejects its extra field with `Invalid object fields`.
No output repair, field stripping or fallback occurred. All **16** policy decisions
denied dispatch, **zero** capabilities executed, and Task `procedure` reached
`FAILED` at the existing 16-turn bound, with no artifacts, wait or completion
evaluation. The controller then timed out waiting for the initial WAIT and cleaned
up its isolated runtime/server. No shared service/configuration changed.

No human answer was submitted. The resolution projection was therefore **not
exercised by live cognition**, and live restart/completion checks remain
**UNVERIFIED**. This failure precedes the original post-artifact context issue;
it does not establish that the projection correction failed or passed that issue.
Prompt tokens: 41,761; completion tokens: 1,757; largest packet: 3,367 bytes.
No MIRIX, embedding provider, worker harness or cloud inference participated.

## STOP REPORT

- **Increment:** 8, authorized verified-resolution correction.
- **Expected:** publish scoped clarification, wait, validate response, retain its
  projection across a capability and fresh runtime, then independently complete.
- **Observed:** malformed capability inputs were repeatedly denied before the
  first human interaction; Task FAILED. Unit controls passed; live gate failed.
- **Architecture impact:** local context projection only. Task/NextAction
  contracts, workflow/lifecycle, PolicyGate, completion verifier, cognition adapter,
  memory and worker code are unchanged, confirmed by source hashes.
- **Attempted:** one scoped projection implementation, seven tests, one bounded
  live acceptance attempt; no corrective retry after the failure.
- **Unresolved question:** how to obtain a valid `human.request` input from the
  unchanged local cognition path without repair or weaker validation. The extra
  field is observed directly; why Qwen repeated it is not established.
- **Human decision required:** authorize a narrow capability-input guidance
  diagnostic/correction at that model-output boundary, preserving strict validation,
  followed by another Increment 8 gate. Current authorization excludes expanding
  the projection fix into adapter/prompt redesign.
- **Safest next option:** that bounded correction; keep this implementation as
  test-backed but not live-accepted. Do not begin Increment 9.

## Retained artifacts and changed files

[Machine-readable summary](../../experiments/kernel-increment-8/evidence/verified-resolution/summary.json),
[tests](../../experiments/kernel-increment-8/evidence/verified-resolution/tests.json),
[first raw counterexample](../../experiments/kernel-increment-8/evidence/verified-resolution/counterexample.json),
[live probe summary](../../experiments/kernel-increment-8/evidence/verified-resolution/acceptance/summary.json),
[captured terminal state](../../experiments/kernel-increment-8/evidence/verified-resolution/acceptance/stopped-state.json),
[terminal result](../../experiments/kernel-increment-8/evidence/verified-resolution/acceptance/stopped-result.json),
[journal](../../experiments/kernel-increment-8/evidence/verified-resolution/acceptance/stopped-journal.json),
[source integrity](../../experiments/kernel-increment-8/evidence/verified-resolution/source-integrity.json).
The acceptance directory also retains complete sent packets, safe raw provider
responses, policy records, exact artifacts, versions and process logs. No private
reasoning is retained. Earlier counterexample evidence remains unchanged.

Changed implementation/experiment files: `runtime/kernel/context.py`, new
`tests/test_kernel_resolution.py`, `scripts/verify-kernel-procedure.py`,
`experiments/kernel-increment-8/probe_app.py` and `speckit-clarification.md`.
Also added this milestone, evidence and the progress-index update. No other
runtime file changed.
