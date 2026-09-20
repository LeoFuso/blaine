# Increment 8 — semantic human-request carveout / FAIL / STOP

Hypothesis: Qwen expresses a strict, smaller semantic human request; deterministic
code constructs the existing protocol command, which still passes through unchanged
PolicyGate and completion verification. The isolated lowering works in tests, but
the live acceptance flow **failed**. This is a candidate boundary, not an accepted
replacement for existing cognition actions. No Increment 9 or migration began.

## Narrow implementation

The opt-in [SemanticHumanCognition adapter](../../runtime/kernel/semantic_human.py)
accepts this separate semantic contract for human input:

```json
{
  "action": "request_human",
  "purpose": "retention_period",
  "question": "How long should exports be retained?",
  "response": {"kind": "choice", "choices": ["30 days", "90 days"]}
}
```

[SemanticHumanRequest v1](../../runtime/kernel/semantic-human-request-v1.json)
is selected by the adapter binding, identified by `urn:blaine:semantic-human-request:1`.
The model does not emit a version field. Unknown fields/actions, missing intent,
unsupported response kinds, duplicate/oversized choices and unbound purposes fail.
Only bounded **choice** responses are supported; free text would not fit the
existing HumanDecision verifier and was not added.

An explicit application binding maps semantic purpose `retention_period` to the
already accepted request `retention`. Lowering reads that request from the trusted
turn, validates its Task scope, preserves the emitted question/choices exactly,
and constructs the versioned HumanDecisionRequest and CognitiveDecision envelopes.
Policy still requires equality with the accepted request. Different question/choice
semantics are preserved, then denied by policy; they are not rewritten into the
accepted answer. Unbound purpose is rejected rather than interpreted.

| Model-owned semantics | System-owned protocol |
| --- | --- |
| Whether to request human input; exact bound purpose; question; response kind and choices | Contract-version binding and envelopes; Task/origin identity; current turn/revision; accepted request ID/revision; stable operation identity |
| No request identity or authority declaration | Artifact identity/digest/provenance and response verification remain owned by existing runtime/effect/verifier code |

The accepted completion contract still pre-scopes the permitted human question and
response set. This proof does **not** enable dynamically inventing new authorized
requests or changing TaskSpec. Purpose selects an explicit allocation; it is not
a new runtime request-ID generator or semantic guess.

Only this action uses lowering. Other model decisions retain their existing
CognitiveDecision representation and strict validation. The opt-in adapter accepts
either a top-level semantic human action or an existing non-human runtime decision;
it rejects an old human.request command rather than extracting semantic fields.
Default LocalModelCognition, context projection, workflow, contracts, PolicyGate,
human verifier, memory and worker code are unchanged. No tool execution happens
inside either cognition adapter.

## Representation and single source of truth

JSON was selected for the existing strict parser, duplicate-key rejection, compact
wire form and no new dependency. YAML offers authoring convenience but has no
demonstrated Qwen reliability advantage here and would require another parser and
normalization policy. No comparative model benchmark was attempted.

The small declarative JSON schema supplies action/response constants, required
field sets, bounds and uniqueness to the fixed semantic validator. The same schema
is sent as guidance; canonical eligible examples are constructed from accepted
scope and checked by that validator. There is no generic schema interpreter or
code-generation framework. Existing text validation also enforces nonblank UTF-8
byte limits; `x-maxBytes` records those limits. This is partial shared specification,
not a claim that a general JSON Schema engine enforces every application rule.

Such a source could later supply guidance, examples, field validators,
documentation and structural test cases. Domain tests and accepted-scope/authority
checks still need explicit code. Runtime mapping metadata could reference reviewed
lowering functions; a declarative file must not become an executable policy language
or authority store. JSON/schema is preferable now; YAML could be a human authoring
format normalized to that same representation later.

## Tests and live observation

Baseline **48/48** tests passed; **56/56** pass with eight semantic-boundary tests.
Twelve additional retained synthetic controls cover unknown/missing/malformed
semantics and invalid lowered commands. The positive synthetic lowering is admitted
by existing PolicyGate without dispatching an effect. The existing wrong/stale
HumanDecisionResponse, exact completion, no-objective-mutation, bounded projection
and fresh-process tests continue to pass. Synthetic results are explicitly labelled
and are not counted as model inference.

One live attempt used existing local vLLM `Qwen/Qwen3.5-9B` at
`http://127.0.0.1:8000/v1/chat/completions`. All four calls requested and reported
that model. No serving configuration, secrets or other infrastructure changed.

1. Turn 1 returned an existing-format WAIT. Unchanged PolicyGate denied it:
   `Human request must be published before waiting`.
2. Turn 2 returned the semantic action fields **inside** an old
   `CognitiveDecision.payload.next_action.input` for capability `human.request`.
   The same mixed format occurred on all three existing durable-step attempts.
   The opt-in adapter rejected it; it did not extract or rewrap the nested fields.
3. The Task reached FAILED. One decision was committed; its policy audit appears
   three times during replay. These are not three new WAIT decisions. Turn 2 never
   returned an accepted command from the adapter. Total live model calls: four.

There were **zero accepted live semantic actions, zero live lowerings, zero effects,
zero human responses and zero completion evaluations**. The planned runtime restart
and post-artifact live resolution check were not reached. The probe cleaned up its
isolated processes. Prompt/completion tokens: 10,020 / 611; largest packet: 3,387 bytes.
No additional live attempt or corrective change followed the failure.

The trace shows that the model blended the two output representations. It does
not prove the broader semantic/runtime separation is unworkable, nor that YAML or
a larger model would fix it. The current mixed-format presentation did not pass.

## STOP REPORT and answers

- **Increment:** 8 semantic/runtime boundary carveout.
- **Expected:** top-level semantic request → strict validation → deterministic
  lowering → existing admitted effect → verified response → durable resolution →
  artifact → COMPLETE → independent verification.
- **Observed:** premature WAIT was denied, then mixed semantic/runtime output was
  rejected. Task FAILED before any effect. Full flow remains unproven.
- **Architecture impact:** authorized, opt-in adapter experiment only; no existing
  authority, lifecycle, contract, completion or projection semantics changed.
- **Attempted:** strict choice-only semantic schema, fixed lowering, tests and one
  four-call local acceptance attempt. No extraction/repair or relaxed fallback.
- **Unresolved question:** whether a bounded revision to the mixed output
  presentation can reliably separate the semantic human action from unchanged
  runtime actions. Resolving this is a new live experiment, not an automatic fix.
- **Human decision required / safest next option:** authorize or decline that
  bounded presentation experiment. Preserve strict rejection; do not migrate all
  actions or begin Increment 9 to bypass this gate.

1. **Did separation solve the actual failure?** No; deterministic lowering passed
   its controls, but live Qwen output never satisfied the new top-level contract.
2. **Who owns fields?** Model: action/purpose/question/response semantics. Code:
   accepted scope binding, IDs/revisions, version envelopes and effect provenance.
3. **Was semantic information invented?** No. Positive synthetic lowering preserves
   all semantic input; live lowering never ran. Missing intent is rejected.
4. **YAML or JSON/schema?** JSON/schema now; YAML could author the same specification
   later. Neither representation has proven this live flow reliable yet.
5. **Other candidate beneficiaries?** Protocol-heavy capability invocations and
   SPAWN_TASK specifications could benefit, but this is a design hypothesis—not
   authorization or evidence for migrating them.
6. **What can remain direct?** COMPLETE and HANDOFF's simple action/target selection,
   and already reliable small capability/WAIT forms, can retain their current
   contracts. Their metadata ownership can be reviewed separately; no migration
   is needed merely to keep them operating now.

## Evidence and files

[Summary](../../experiments/kernel-increment-8/evidence/semantic-lowering/summary.json),
[exact model-facing guidance](../../experiments/kernel-increment-8/evidence/semantic-lowering/guidance.json),
[raw provider responses](../../experiments/kernel-increment-8/evidence/semantic-lowering/acceptance/wire.jsonl),
[boundary rejections](../../experiments/kernel-increment-8/evidence/semantic-lowering/acceptance/semantic.jsonl),
[model/decision records](../../experiments/kernel-increment-8/evidence/semantic-lowering/acceptance/model.jsonl),
[policy](../../experiments/kernel-increment-8/evidence/semantic-lowering/acceptance/policy.jsonl),
[terminal state](../../experiments/kernel-increment-8/evidence/semantic-lowering/acceptance/stopped-state.json),
[synthetic lowering input/output](../../experiments/kernel-increment-8/evidence/semantic-lowering/synthetic-lowering.json),
[negative controls](../../experiments/kernel-increment-8/evidence/semantic-lowering/negative-controls.json),
[tests](../../experiments/kernel-increment-8/evidence/semantic-lowering/tests.json),
[source integrity](../../experiments/kernel-increment-8/evidence/semantic-lowering/source-integrity.json).
Safe public outputs only; no private reasoning retained.

New files: semantic adapter/schema and `tests/test_kernel_semantic_human.py`.
Changed existing implementation files: only Increment 8 `probe_app.py` (opt-in
adapter) and `scripts/verify-kernel-procedure.py` (boundary assertions/audits and
early stop on terminal failure). TaskSpec and the desired acceptance sequence are
unchanged. Also added evidence, this milestone and the progress-index update.
