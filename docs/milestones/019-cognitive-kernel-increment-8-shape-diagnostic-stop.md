# Increment 8 — human.request shape diagnostic / STOP

**Classification: MODEL_ACTION_SERIALIZATION_BEHAVIOR.** The captured input shape
guidance is explicit and agrees with the capability-specific validator. The user's
stop condition therefore applies. No generation guidance, validation, projection,
contract, lifecycle or other runtime behavior was changed. No live inference or
acceptance rerun occurred. Increment 8 remains failed; Increment 9 did not start.

## Findings from the actual sent guidance

1. **Required input shape:** the `human.request` action schema supplies an object
   with `properties: {request: ...}`, `required: [request]` and
   `additionalProperties: false`. Thus `input` may contain only `request`.
   This schema was present in all 16 captured provider requests and matches the
   current generated guidance exactly, including its surrounding system text.
2. **Version locations:** `version: 1` is required on the outer CognitiveDecision
   and on `input.request`, the nested HumanDecisionRequest envelope. It is not
   allowed on `input`. All 16 raw responses include the extra `input.version`;
   raw provider content and parsed decisions match. The model may have generalized
   the envelope pattern, but the trace cannot prove where that duplication came from.
3. **Examples/prose:** there is no dedicated concrete human.request example in
   the short action examples. The prose explicitly introduces *top-level* envelope
   fields before “Always emit version:1”; its artifact.write example has an
   unversioned input. The complete schema then specifies the human.request shape.
   Repeated versioned envelopes could influence model serialization, but that
   possibility is not evidence that all nested objects were instructed to carry
   version. Absence of a short example does not make the supplied schema ambiguous.
4. **Contract/guidance/validator agreement:** PolicyGate's
   `fields(value, {'request'})` rejects the same unexpected input field forbidden
   by the schema. `validate_request` expects version/kind/payload on the request
   envelope. No field-placement inconsistency accounts for the failure.

The guidance is not a complete substitute for application enforcement: its generic
string limits are broader than runtime identifier, byte-length, nonblank and
allowed-response uniqueness checks; policy also requires equality with the accepted
request. These existing differences do not permit `input.version` or cause this
field rejection. They were not changed or investigated beyond this direct comparison.

The decision validator validates the invocation envelope and object-valued input;
capability-specific validation occurs in PolicyGate before dispatch. Therefore
`outcome: validated` in the model audit is **not** proof of capability admission.
The retained gate records correctly deny all 16 requests. This is not an adapter
repair/default issue and does not reopen the accepted clarification projection.

## Deterministic controls

**48 focused tests pass**, including the prior 44 and four new shape-boundary tests.
An offline evidence audit also retained **12 explicit synthetic controls**:
one valid input admitted by policy and eleven negative inputs rejected either by
the adapter's envelope checks or the capability-specific gate. Cases cover extra
`input.version`, arbitrary unknown fields, missing request, null request, unknown
request-envelope fields, missing request version and non-object inputs.

Object inputs are passed through unchanged before policy rejection; non-object
inputs fail before a decision returns. No fields are stripped, added or coerced,
and no fallback or effect is executed. These injected provider responses are
**deterministic boundary tests, not live Qwen inference**. Source hashes confirm
all preexisting runtime and Increment 8 probe/procedure files remain unchanged.

## STOP REPORT

- **Increment:** 8, human.request output-shape diagnostic.
- **Expected:** current explicit input schema is followed; only `request` occurs
  inside human.request input.
- **Observed:** existing Qwen evidence violates that schema with `input.version`
  on all 16 turns; strict policy denies every effect. No new model call was made.
- **Architecture impact:** none. The accepted projection implementation remains.
- **Attempted:** captured-guidance/schema/validator comparison, offline raw/parsed
  equality checks, focused synthetic controls and regression tests.
- **Unresolved question:** why Qwen repeatedly serializes the extra field despite
  correct guidance. This is a bounded observed behavior, not a general conclusion
  about model quality or a reason to weaken validation.
- **Human decision required:** whether to authorize a separate, bounded concrete
  serialization-example experiment despite the already-correct schema. The present
  instruction explicitly requires STOP in this situation.
- **Safest next option:** preserve this evidence and the strict contract pending
  that decision. No correction or original live gate rerun is claimed.

## Evidence and changed files

[Summary](../../experiments/kernel-increment-8/evidence/human-request-shape-diagnostic/summary.json),
[exact guidance, schema branch and raw output](../../experiments/kernel-increment-8/evidence/human-request-shape-diagnostic/guidance.json),
[synthetic controls](../../experiments/kernel-increment-8/evidence/human-request-shape-diagnostic/controls.json),
[48-test results](../../experiments/kernel-increment-8/evidence/human-request-shape-diagnostic/tests.txt),
[unchanged-source hashes](../../experiments/kernel-increment-8/evidence/human-request-shape-diagnostic/source-integrity.json).
Original live provenance remains local vLLM `Qwen/Qwen3.5-9B` at
`http://127.0.0.1:8000/v1/chat/completions`; this diagnostic called no provider.

Added only [offline audit](../../experiments/kernel-increment-8/diagnose_human_request_shape.py),
[regression tests](../../tests/test_kernel_human_shape.py), evidence and this
milestone/progress update. No runtime or serving configuration changed.
