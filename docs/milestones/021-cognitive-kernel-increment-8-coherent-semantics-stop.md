# Increment 8 — coherent semantic boundary / live gate FAIL / STOP

The new boundary successfully produced and executed one valid human request from
real Qwen semantic output. It removed the observed hybrid serialization in this
run. The full gate failed because the next semantic decision repeated the request
while it was pending. Preconditions rejected that proposal without another effect.

## Implemented boundary

`SemanticDecisionProvider.decide(context) -> decision` receives only semantic data.
The [provider module](../../runtime/kernel/semantic_provider.py) defines one closed
four-action vocabulary: REQUEST_HUMAN(question, purpose, choice response),
WAIT(purpose), PRODUCE_ARTIFACT(content), COMPLETE. All other fields/actions fail.
The semantic contract is pinned by this opt-in binding; the model emits no version.
Only existing bounded choices are supported, not a new free-text response contract.

The [Blaine bridge](../../runtime/kernel/semantic_bridge.py) projects the current
trusted CognitiveTurn and exact artifact evidence into goal, clarification,
deliverable status, selected procedure instructions and admissible actions. It
does not forward runtime envelopes, Task/request/turn identities, provenance refs,
digests, capability transport names or policy internals. The full internal packet
and provenance remain in the evidence store/audit; this is presentation separation,
not loss of enforcement evidence. No chat history is retained.

The probe accepts a semantic-only objective **at initial Task creation** and uses
a [semantic procedure excerpt](../../experiments/kernel-increment-8/speckit-semantic-clarification.md)
with the same clarification intent. It does not heuristically rewrite an arbitrary
objective or change the accepted objective during execution. All captured model
goals equal the accepted immutable TaskSpec objective. This narrow projection is
not yet a general sanitizer for arbitrary repository text or procedures.

### Admissibility is validation, not lifecycle control

For this controlled transport, a request is **pending** when the accepted scoped
request artifact has been published, with exact bytes/digest verified, and no
current verified response exists. This external obligation precedes the runtime
WAIT that registers durable suspension. The bridge does not claim an external
notification was delivered or an authenticated human read the request.

- REQUEST_HUMAN requires missing information with no equivalent pending/resolved
  request. Pending/resolved duplicates are rejected before lowering.
- WAIT requires an already pending request for the exact semantic purpose. Missing
  or resolved conditions are rejected. WAIT never creates a request or substitutes
  for REQUEST_HUMAN.
- PRODUCE_ARTIFACT supplies exact content for the explicitly bound deliverable.
  COMPLETE still only requests existing independent verification.

Current state comes from existing accepted scope, artifact references and verified
resolution projection. No second answer store, pending ledger or lifecycle phase
was added. Request/question/choice semantics are not repaired. Lowering supplies
only system-owned metadata and explicit bindings, then unchanged PolicyGate admits
or denies the RuntimeCommand. The provider cannot mutate the trusted context to
make a proposal admissible; it receives an isolated copy.

## Tests and live evidence

Baseline **56/56** tests passed; **65/65** now pass. Nine new tests cover state
preconditions, exact publication evidence, rejection of hybrid/runtime-owned fields,
missing/malformed intent, semantics preservation, unchanged PolicyGate rejection,
independent completion, context isolation and replacement by another `decide`
implementation. Existing HumanDecision negative controls, no-objective-mutation,
fresh-process reconstruction and exact artifact tests remain intact. Synthetic
controls are labelled separately; they are not live model evidence.

One live attempt made four calls to the existing shared local vLLM endpoint
`http://127.0.0.1:8000/v1/chat/completions`; each request/response identifies
`Qwen/Qwen3.5-9B`. Exact provider messages contain none of the excluded runtime
forms/identifiers checked by the probe. No cloud, other model or repair model was
used. Shared serving configuration, secrets and infrastructure were untouched.

| Stage | Qwen output | Blaine result |
| --- | --- | --- |
| Turn 1: missing clarification; REQUEST_HUMAN available, WAIT unavailable | Valid REQUEST_HUMAN | Semantic validation and admissibility pass; exact question/choices lowered into the accepted HumanDecisionRequest; PolicyGate allows; request published once |
| Turn 2: status pending; WAIT available, REQUEST_HUMAN absent from allowed actions | Valid-shape REQUEST_HUMAN again | Semantic validation passes; admissibility rejects duplicate before lowering |
| Two existing durable-step retries of turn 2 | Same semantic REQUEST_HUMAN | Same rejection; no substitute WAIT and no duplicate publication |

There were **zero hybrid outputs**, four valid semantic shapes, one admitted
decision, one lowered command and one capability effect. The existing retry limit
then ended the Task FAILED. Policy audit repeats for the committed first decision
during replay are not additional model decisions or effects.

No WAIT was accepted, no human answer was submitted and no deliverable, verified
response, live restart, later reconstructed resolution or completion evaluation
was reached. Those acceptance stages remain **UNVERIFIED**. The experiment stopped
and cleaned up its isolated runtime/server. No retry with adjusted guidance followed.

Usage: 2,766 prompt tokens, 308 completion tokens, largest semantic packet 1,376
bytes. These measurements describe this four-call run, not a model benchmark.

## STOP REPORT

- **Increment:** 8, coherent semantic decision boundary.
- **Expected:** REQUEST_HUMAN → pending WAIT → verified response → artifact →
  reconstructed resolution/evidence → COMPLETE → independent verification.
- **Observed:** first request succeeded; subsequent duplicate requests were
  rejected despite explicit pending state and available WAIT. Task FAILED.
- **Classification:** SEMANTIC_ADMISSIBILITY_VIOLATION, not hybrid serialization.
- **Architecture impact:** authorized opt-in provider/context/lowering seam only.
  Existing kernel, contracts, PolicyGate, completion, memory, worker and resolution
  projection files are unchanged, verified by hashes.
- **Attempted:** one coherent vocabulary/projection, local precondition checks,
  nine tests, one four-call live gate. No action substitution or output repair.
- **Unresolved question:** why this provider repeats REQUEST_HUMAN when the current
  context says pending. The trace establishes the invalid choice, not its internal
  cause or a universal model limitation. Rejected adapter proposals are retried by
  existing runtime semantics; no new semantic-feedback lifecycle was introduced.
- **Human decision required:** authorize or decline a separately bounded action-
  selection/admissibility-feedback experiment. Any proposed feedback path must be
  reviewed for scope; it is not implemented here.
- **Safest next option:** retain the working isolation and strict checks; review
  the captured pending-state counterexample before further model work. No Increment
  9 or general migration was started because this gate failed.

## Required answers

1. **Did removing the mixed vocabulary solve the live failure?** It removed hybrid
   output in all four calls and enabled one real admitted request, but the full
   acceptance flow failed on duplicate semantic action selection.
2. **Did preconditions remove WAIT/REQUEST_HUMAN ambiguity?** They made admissibility
   explicit and enforceable. Premature WAIT is rejected in tests; the live duplicate
   request was blocked. They did not make Qwen choose WAIT correctly.
3. **Is the provider independent of RuntimeCommand?** Yes within this opt-in
   boundary: its method receives/returns only semantic objects. Protocol construction
   and authority stay in the separate bridge/runtime. Other deployments retain their
   previous adapters; this is not a system-wide migration.
4. **Could a Jev-like provider replace Qwen without changing runtime semantics?**
   The interface permits that; a different deterministic fixture provider passed
   the replacement test. No Jev-like model was integrated or empirically validated.
5. **What requires Qwen rather than a smaller model?** Nothing in this experiment
   establishes such a requirement. State preconditions are deterministic. Interpreting
   genuinely ambiguous requirements may require stronger semantic reasoning, but
   this fixed-question fixture cannot compare provider capability. No smaller-model
   quality claim or routing decision is justified by these results.

## Retained evidence and change scope

[Summary](../../experiments/kernel-increment-8/evidence/coherent-semantics/summary.json),
[joined actor-boundary records](../../experiments/kernel-increment-8/evidence/coherent-semantics/boundary-results.json),
[exact semantic guidance/contexts](../../experiments/kernel-increment-8/evidence/coherent-semantics/guidance.json),
[raw provider evidence](../../experiments/kernel-increment-8/evidence/coherent-semantics/acceptance/wire.jsonl),
[semantic validation/lowering](../../experiments/kernel-increment-8/evidence/coherent-semantics/acceptance/semantic.jsonl),
[effect and exact request artifact](../../experiments/kernel-increment-8/evidence/coherent-semantics/acceptance/capabilities.jsonl),
[terminal state](../../experiments/kernel-increment-8/evidence/coherent-semantics/acceptance/stopped-state.json),
[synthetic controls](../../experiments/kernel-increment-8/evidence/coherent-semantics/controls.json),
[tests](../../experiments/kernel-increment-8/evidence/coherent-semantics/tests.json),
[source hashes](../../experiments/kernel-increment-8/evidence/coherent-semantics/source-integrity.json).
Unreached response/resolution/completion stages are explicitly null in the joined
evidence; no claims are substituted for them. No private reasoning is retained.

New: `semantic_provider.py`, `semantic_bridge.py`, semantic procedure excerpt and
`tests/test_kernel_semantic_provider.py`. Updated only the Increment 8 probe binding,
initial fixture wording, evidence assertions and progress records. Existing runtime
files—including the previous experimental adapters—were not modified.
