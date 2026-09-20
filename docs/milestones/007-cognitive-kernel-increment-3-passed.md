# Increment 3 — JSON-only adapter correction and acceptance PASS

**2026-09-19 · PASS · Stopped after the requested probe; no Increment 4/MIRIX**

The user authorized one adapter-only correction following the
[3A diagnosis](006-cognitive-kernel-increment-3-model-stop.md#increment-3a--diagnostic-result-supersedes-unresolved-diagnosis-above).
Hypothesis: ordinary generation can make evidence-sensitive decisions while strict
application validation preserves the existing envelope and authority boundaries.

## Exact correction

[model.py](../../runtime/kernel/model.py) no longer sends `response_format` or
other provider-constrained decoding options. It requests ordinary JSON generation
and supplies the existing output schema as **textual guidance** in the system
message, explicitly requiring integer `version: 1` and all envelope fields.
CognitiveTurn content, action vocabulary and inference sampling options remain
unchanged. The same already-running shared Qwen endpoint was used.

The response parser, validation and returned decision are unchanged. No missing
field is filled, repaired or coerced; no COMPLETE fallback exists. Missing/invalid
versions, missing kind, extra fields, unknown actions, malformed JSON, stale
identities and native tool calls remain rejected. Five focused adapter tests pass,
including preservation of a raw INVOKE_CAPABILITY response and rejection without
fallback. No dependencies, serving configuration, kernel, Task/NextAction
contracts, lifecycle, PolicyGate or completion rules changed.

## Original acceptance probe, unchanged

The original [verify-kernel-model.py](../../scripts/verify-kernel-model.py) and its
[probe deployment](../../experiments/kernel-increment-3/probe_app.py) were verified
byte-for-byte unchanged and executed **once** after correction. Exit code: **0**.

| Case | Observed result |
| --- | --- |
| Evidence-sensitive choice | Qwen chose INVOKE_CAPABILITY, then COMPLETE after the artifact result. |
| Premature completion | Qwen requested COMPLETE; unsatisfied verification became its next observation; it wrote evidence and completed through verification. |
| Forbidden effect | Qwen requested `fixture.effect`; policy denied dispatch; Qwen continued with permitted work. Fixture effect rows: **0**. |
| Scripted control | Scripted cognition completed using the same unchanged kernel and input contract. |
| Malformed response | Injected invalid model-response fixture was rejected before capability dispatch; Task FAILED as expected. |
| Unsupported action | Injected unknown action was rejected before capability dispatch; Task FAILED as expected. |

Invalid-output fixtures are deliberate synthetic provider responses, not claims
that Qwen naturally emitted them. All six original assertions passed. The live
Qwen cases used **8 model turns**, **13,037 prompt tokens**, **415 completion
tokens**, and at most **1,795 bytes** per CognitiveTurn. Textual schema guidance
is additional model-input overhead included in recorded request bytes/token usage.

[Machine-readable summary](../../experiments/kernel-increment-3/evidence/json-only-correction/summary.json),
[original probe summary](../../experiments/kernel-increment-3/evidence/json-only-correction/acceptance/summary.json),
[probe transcript](../../experiments/kernel-increment-3/evidence/json-only-correction/acceptance-probe.txt),
[unit tests](../../experiments/kernel-increment-3/evidence/json-only-correction/unit-tests.txt),
[unchanged boundaries](../../experiments/kernel-increment-3/evidence/json-only-correction/unchanged-boundaries.json).

The evidence directory retains actual packets/decisions, model usage, capability
requests, journal/state/result snapshots, verifier findings and exact artifacts.
Before/after source digests establish change scope; AST comparison establishes
that application response handling is unchanged. Earlier failed probes and 3A
raw-response evidence remain preserved separately. Raw runtime data/logs are in
`.local/kernel-program/model-json-only-correction`.

The command executed used the existing pinned sibling installation:

```bash
/home/leofuso/workspace/blaine/.local/runtime-venv/bin/python scripts/verify-kernel-model.py \
  --restate-server /home/leofuso/workspace/blaine/.local/bin/restate-server \
  --output .local/kernel-program/model-json-only-correction
```

**Gate: PASS. Architecture deviations: none.** Probe-owned processes were cleaned
up. Per the latest user instruction, work stopped after this probe and evidence
recording. The original probe's `next_increment: 4` is only its pre-existing roadmap
field; it does not authorize or report any Increment 4 execution. No MIRIX work,
further model investigation or subsequent increment was started.
