# Increment 8 — captured-context diagnostic / STOP

Diagnostic only. No prompt, context policy, procedure provider, kernel, contract,
lifecycle, inference configuration or model behavior changed. No new inference,
live reproduction, service startup or runtime Task submission. Increment 8's
acceptance gate remains **FAIL / STOP**; no later increment started.

## Classification and confidence

**STALE_OBJECTIVE_OR_PROCEDURE_STATE**, specifically the objective's current-tense
claim that retention is unresolved. A concrete context projection gap is also
confirmed: the accepted, durable `ExternalInput` disappears from subsequent
cognition after another operation replaces the latest observation.

The strict **CONTEXT_PROJECTION_DEFECT** category assumes verified human-decision
evidence already exists. That premise does not hold here: this fixture used
generic `WAIT(text)` / `submit_input`, not Increment 5's typed human decision
request/response or child result. Do not claim a verified response was lost.
No `HumanDecisionRequest`, `HumanDecisionResponse`, `TaskResult` or
`CompletionEvaluation` exists in the captured artifact inventory.

**PROMPT_INTERPRETATION_DEFECT** and **MODEL_ACTION_SELECTION_DEFECT** are not
established: the input is not an unambiguous representation of current resolved
state. The trace cannot prove which competing instruction caused Qwen to choose
WAIT. The application dataflow and stale assertion are isolated; the model's
internal causal choice remains unknown. This is sufficient to stop this bounded
diagnostic without more inference, not sufficient to claim a correction passed.

## Per-turn comparison

| Input / output | Turn 1, revision 0 | Turn 2, revision 1 | Turn 3, revision 2 |
| --- | --- | --- | --- |
| Objective | Retention “is unresolved”; wait if blocked; write specified bytes after input; COMPLETE once artifact exists | Identical | Identical |
| Lifecycle supplied to Qwen | Absent | Absent | Absent |
| Runtime at cognition | RUNNING, inferred from source and allow gate | RUNNING after resume, same basis | RUNNING, same basis |
| Procedure | Fixed derived clarification excerpt | Identical | Identical |
| Typed human request / verified response | None | None | None |
| Generic wait resolution | No answer yet | Accepted `ExternalInput`: “Retain exports for 30 days.” | Neither answer nor resolved-wait status projected |
| Current observations | Empty | ExternalInput, including wait ID and revision | Successful artifact.write CapabilityResult |
| Artifact context | TaskSpec reference | Same TaskSpec reference | Same TaskSpec plus answer reference/digest/name |
| Exact answer artifact bytes supplied | No | No; required literal is in objective | No; ref/digest and successful write are supplied |
| Completion criterion | Exact answer digest | Identical | Identical; matches write result digest |
| CompletionEvaluation | None | None | None |
| Allowed capability | artifact.write | Identical | Identical; artifact.read unavailable |
| Other context providers | None | None | None |
| Raw and validated action | WAIT(retention, text) | INVOKE_CAPABILITY artifact.write | WAIT(retention, text) |
| Captured PolicyGate | allow | allow | allow |
| Resulting effect/state | Captured WAITING, promise input/1/retention | One successful exact write | Captured WAITING, new promise input/3/retention |
| Packet bytes / prompt tokens | 2678 / 2484 | 2824 / 2522 | 3346 / 2828 |

Every call has exactly two messages: system instructions/schema guidance and
the current bounded CognitiveTurn. No conversation history accompanies them.
The system guidance changes only its turn/revision constants. The procedure
says to avoid questions already answered and continue once uncertainty resolves;
it does **not** explicitly say retention remains unresolved. The contradictory
current-state assertion is in the unchanged objective.

The raw public Qwen output exactly matches each parsed/validated decision. All
three calls requested and reported `Qwen/Qwen3.5-9B` at
`http://127.0.0.1:8000/v1/chat/completions`, JSON-only generation, temperature 0,
max_tokens 768, enable_thinking false. Completion tokens: 50, 62, 50. No Goose,
MIRIX, embedding service or cloud participated. Input was a controlled fixture,
not an authenticated human approval. Offline parsing/digest checks are
deterministic application work, not new model inference.

## A–F findings

**A — Available in turn 2:** yes, directly in `observations[0]`, scoped to wait
`retention`, revision 0. The input handler validates current wait/type/revision
and bounded text. The receipt establishes acceptance, not human-response
verification or Task completion.

**B — Absent in turn 3:** [context reconstruction](../../runtime/kernel/context.py)
reads only `state.observation_ref`. After the write,
[the workflow](../../runtime/kernel/workflow.py) replaces it with CapabilityResult.
The original ExternalInput still exists as exact artifact
`artifact://procedure/sha256:9181893b4e0be7c407371f89626a7f6400f3f80f59b1c9c97706670f57f88328`.
It is not in the current artifact map or a retained resolution field. Providers
receive objective/specialist/budget, not this previous input. The answer is lost
from projection, not deleted from storage.

**C — Verified replacement:** none. The resulting answer artifact is worker/model
output, with no request binding or human verifier. Its exact bytes were already
specified in the initial objective, so their presence cannot independently prove
that the human chose 30 days. TaskState has no human_responses and no children.

**D — Stale representation:** yes, the identical objective says “A material
acceptance detail is unresolved: retention duration.” No explicit scoped
resolution replaces that claim. The procedure is static guidance, not an updated
specification; preserving accepted intent need not mean treating initial
uncertainty as current fact forever.

**E — Write visible:** yes. Turn 3 includes success, operation_id `procedure/2`,
answer ref and SHA-256 `f20deb1acab1f5eb7cc13323ed47bfd4f4c53092739aaa8755dc16d4db968a42`,
matching its completion criterion. The retained bytes are `RETENTION_30_DAYS`.
Only the offline audit checked those bytes in this diagnostic. The live Task
never requested COMPLETE, so no live CompletionEvaluation occurred.

**F — WAIT explainable without assuming model defect:** yes, plausibly from the
stale unresolved assertion plus absent resolution. But the same packet also
contains the successful write and “Once the artifact exists, request COMPLETE.”
Do not claim WAIT was necessary or that missing evidence alone forced it. There
is no captured operational reason explaining the choice, and no private reasoning
was retained or needed. Both waits are distinct iteration-qualified promises;
this is not evidence of an old promise being incorrectly replayed.

Secondary observed mismatch: objective/procedure request a question in `reason`,
while the sent guidance schema excludes that optional field. Application validation
accepts it. All three outputs omit it. The probe's later reason assertion would
also fail; no causal connection between that mismatch and repeated WAIT is proven.

## Smallest proposed correction — not applied

The implicated boundary is **durable accepted input/artifact → Context
Reconstruction → bounded CognitiveTurn**, including separation of accepted intent
from current clarification status. There is no evidence requiring a different
Task lifecycle, completion rule, memory architecture or thought-phase machine.

Project one bounded, scoped resolved clarification with its value, source/digest
and actual validation status into subsequent relevant turns. Distinguish the
initial ambiguity from that current resolution while preserving accepted intent.
Do not forward full transcripts, force COMPLETE, or rewrite the accepted TaskSpec
as a substitute for context reconstruction.

The answer does not need to remain verbatim in every prompt. A verified durable
response representation containing the resolved value, Task/request/revision
binding, exact artifact reference and verification status is sufficient. Retain
exact original bytes for audit; a bare unreadable reference is insufficient to
communicate the decision. If independently verified human authority is intended,
reuse the existing Increment 5 typed response path. Do not relabel generic text
or the model-written answer as a verified HumanDecisionResponse. This captured
fixture proves only a scoped accepted text answer.

Separately, any authorized correction should reconcile guidance for the already
supported optional `reason` field with the original probe's question requirement.
Neither correction is implemented by this diagnostic.

## Evidence and stop decision

[Machine-readable summary and diff](../../experiments/kernel-increment-8/evidence/context-diagnostic/summary.json),
[turn 1](../../experiments/kernel-increment-8/evidence/context-diagnostic/turn-1.json),
[turn 2](../../experiments/kernel-increment-8/evidence/context-diagnostic/turn-2.json),
[turn 3](../../experiments/kernel-increment-8/evidence/context-diagnostic/turn-3.json)
contain separate requested categories, exact sent messages and safe raw outputs.
[Integrity inventory](../../experiments/kernel-increment-8/evidence/context-diagnostic/integrity.json)
records unchanged source/captured inputs and all ten verified artifact digests.
[Offline audit](../../experiments/kernel-increment-8/diagnose_context.py) verifies
packet/request equality, raw/parsed decision equality, strict validation, policy
records, artifact inventory and the observations above. It passed once with zero
model calls. It does not execute the kernel or its effects.

**Expected:** resolved clarification remains available and procedure continues.
**Observed:** latest-observation replacement removes it; stale unresolved assertion
remains; successful artifact evidence is present; Qwen selects WAIT.
**Architecture impact:** local context/fixture representation issue; no change applied.
**Human decision required:** authorize the bounded clarification-projection and
guidance correction, explicitly selecting generic accepted text or the existing
verified human-response path for this fixture. **Safest next option:** that narrow
correction plus the original Increment 8 gate, not more unchanged model sampling.
