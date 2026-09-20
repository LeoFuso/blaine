# Increment 3 — Real model adapter, gate NOT PASSED

Historical stop/diagnostic record. The subsequently authorized adapter correction
and passing gate are recorded in [milestone 007](007-cognitive-kernel-increment-3-passed.md).


**2026-09-19 · Increment 3 gate NOT PASSED · Increment 3A diagnosis recorded below**

The user restored the shared services and resumed the program. The previous
[availability stop](005-cognitive-kernel-increment-3-blocked.md) is historical;
Qwen now responds HTTP 200 and advertises `Qwen/Qwen3.5-9B` at the supplied
`http://127.0.0.1:8000/v1`. Increments 1 and 2 were not rerun. Their existing kernel
files still match Increment 2's retained source digests.

## Hypothesis and smallest implementation

The existing local model can select a structured NextAction from the same bounded
CognitiveTurn as scripted cognition, with no lifecycle change.

[LocalModelCognition](../../runtime/kernel/model.py) uses standard-library HTTP,
a configured loopback endpoint and the existing five-action contract. It requests
schema-constrained JSON, rejects malformed/unknown/stale/oversized responses and
native tool calls, then returns a validated CognitiveDecision. It has no Restate
context, capability dispatcher, artifact store or lifecycle handle. No existing
kernel or contract file changed; the new adapter is injected into the same
`create_workflow` factory in an isolated test deployment.

The model request includes only the current packet and short interface
instructions. No full session history is sent. Audit records preserve packet and
request byte counts, validated decisions, response IDs and reported usage; private
reasoning is neither requested nor retained. Per-request options were fixed at
768 output tokens, temperature zero and `enable_thinking=false`; no vLLM serving
configuration was changed. The JSON response-format mechanism was checked against
[official vLLM structured-output documentation](https://docs.vllm.ai/en/latest/features/structured_outputs/).
No additional software or SDK was installed.

## Evidence and bounded attempt

[Four new focused unit tests passed](../../experiments/kernel-increment-3/evidence/unit-tests.txt):
validated output and unchanged packet boundary; malformed/unsupported/stale/native
tool-call rejection; input size/local-endpoint bounds; preservation of five action
variants. This does not establish live semantic competence.

The live harness was prepared for differing-evidence selection, premature
completion, forbidden capability denial, a scripted control, and injected invalid
model responses. It stops on a failed case. **Only the first live case ran**:
produce the exact `answer` artifact, then request completion once durable evidence
shows it exists.

- **Attempt 1:** Qwen returned COMPLETE on all 16 turns. Fifteen turn packets
  contained an unsatisfied CompletionEvaluation reporting missing evidence. No
  capability was invoked. The runtime rejected completion and ended FAILED at
  its existing turn bound.
- **One local correction:** interface instructions originally named capability
  inputs without showing the five concrete NextAction shapes. The prompt was
  clarified to show those shapes and the envelope. No semantic state machine,
  forced decision, schema narrowing or lifecycle change was introduced.
- **Attempt 2:** the same failure repeated: 16 COMPLETE requests, 15 packets with
  missing-evidence observations, no effect, and FAILED at the bound. Further
  prompt/schema trials were stopped as announced.

Across both attempts: **32 actual model calls**, **19,038 prompt tokens** and
**1,982 completion tokens** reported by Qwen. Context was at most **1,156 bytes**.
Each attempt retains actual packets/decisions, usage, TaskSpec/submission/state,
exact digest-checked artifacts, verifier finding and TaskResult. Fixture effect
row count was zero in each run. Both owned Restate/runtime process sets were
cleaned up; shared inference was not started/stopped or reconfigured.

[Summary](../../experiments/kernel-increment-3/evidence/summary.json),
[attempt 1](../../experiments/kernel-increment-3/evidence/first-attempt/summary.json),
[attempt 2](../../experiments/kernel-increment-3/evidence/second-attempt/summary.json),
[restored availability](../../experiments/kernel-increment-3/evidence/availability-resumed.json).
Raw local Restate data/logs remain in `.local/kernel-program/model-1` and `model-2`.
The retained system prompt and source digests identify the final attempted adapter.

## STOP REPORT

**Increment:** 3 — real model-driven CognitiveTurn.

**EXPECTED:** Qwen selects at least two legitimate actions from differing evidence
and completes the small exact-artifact task through the unchanged kernel.

**OBSERVED:** the Qwen/adapter path emitted only COMPLETE in two bounded runs,
even after unsatisfied verification became an observation. The kernel correctly
refused completion. Clarifying the action interface did not resolve it.

**IMPACT:** Increment 3 is BLOCKED / live gate NOT PASSED. Real structured output,
completion enforcement and usage capture were observed. Evidence-based action
selection failed. The forbidden-action, scripted-control and invalid-response
live cases were not reached; invalid-response unit checks passed. No claims are
made for those unexecuted live cases. Increments 4–12 remain NOT STARTED, including
MIRIX despite its reported restored availability.

**ARCHITECTURE IMPACT: None observed.** The problem is local to unvalidated
model/adapter behavior. It is not yet known whether constrained decoding/schema
interaction, prompt presentation or model behavior explains the repeated action.
Do not infer that Qwen is generally incapable or redesign Task semantics.

**SMALLEST NEXT DECISION REQUIRED:** approve a narrowly bounded diagnostic of this
recorded packet and model adapter, keeping the kernel and serving configuration
unchanged. A minimal next experiment would compare the same packet under the
current schema and JSON-only output with the same application validator, to
separate constraint behavior from semantic choice. At that stop this experiment had **not run**; the authorized 3A result is recorded below.

**SAFEST NEXT OPTION:** retain the validated scripted kernel and sequential child
Tasks. Resume at Increment 3 only; no MIRIX or later work until this gate passes.

The reproducible command for the attempted live gate is:

```bash
.local/runtime-venv/bin/python scripts/verify-kernel-model.py \
  --restate-server .local/bin/restate-server --output .local/kernel-program/new-model-run
```

That command currently reproduces an **unpassed gate**, not a validated model
integration. Existing matching executables from the sibling Blaine checkout were
used for these attempts, without installation or mutation of that environment.

## Increment 3A — diagnostic result (supersedes unresolved diagnosis above)

**Classification A: CONSTRAINED_DECODING_DEFECT, for action selection.**
The latest user instruction limited this follow-up to diagnosis only. The adapter,
kernel, contracts, PolicyGate, verifier and serving configuration remain unchanged.
No acceptance probe was rerun and Increment 4 was not started.

Exactly **four model calls**: two primary states × two modes × one sample, with
identical per-state CognitiveTurn packets, system/user messages, inference options
and application validation. The only wire-request difference was the presence
of `response_format` for the current constrained mode. JSON-only used ordinary
generation with the same instruction to return CognitiveDecision JSON; no provider
JSON grammar was substituted. The diagnostic submitted no Tasks and dispatched
no capabilities. Its local setup artifacts supplied exact verifier evidence.

| Fixture / previous evaluation | Constrained raw action | JSON-only raw action | Application validation |
| --- | --- | --- | --- |
| Artifact missing / unsatisfied | COMPLETE | INVOKE_CAPABILITY (`artifact.write`, exact expected content) | Constrained passes shape validation; JSON-only rejected: missing `version` |
| Exact artifact exists / satisfied | COMPLETE | COMPLETE | Constrained passes shape validation; JSON-only rejected: missing `version` |

This controlled contrast isolates the provider-constrained path as the cause of
the observed loss of evidence-sensitive action choice in these fixtures. It does
**not** establish the internal decoder/schema mechanism or a general vLLM defect.
JSON-only demonstrates that the model can distinguish the two states, but is
**not yet a valid replacement adapter**: both outputs omit the required envelope
`version` even though it appears in the prompt. Validation was not weakened, no
field was filled in, and no fallback was applied.

Adapter integrity controls prove that a valid raw INVOKE_CAPABILITY is returned
unchanged and unknown/malformed actions fail. Missing-version output also fails.
The five focused model tests pass. Source inspection finds no default-to-COMPLETE
path; constrained raw responses already contain COMPLETE before parsing.

Inspection of the **actual sent messages** confirms criteria, available write
capability, prior verifier evaluation and exact evidence state are present. The
objective says to write when missing and request COMPLETE when evidence exists.
The system prompt describes COMPLETE as a verification request and says to respond
to missing-evidence findings. Explicit “do not repeat a rejected COMPLETE” wording
is absent, but the identical JSON-only prompt produces the expected semantic
actions. No prompt rewrite was performed during this diagnostic.

[Machine-readable diagnostic](../../experiments/kernel-increment-3/evidence/diagnostic/summary.json)
contains the results and scope. Per-case files retain exact input/request objects,
the provider's raw content string before parsing, normalized provider metadata,
parsed decision or rejection, raw action, completion-evidence state and
`effect_dispatched: false`. Private reasoning fields were excluded before storage.
`integrity.json`, `prompt-inspection.json`, `unit-tests.txt` and source digests retain
the controls and unchanged-boundary checks. Reproduction script:
[diagnostic/run.py](../../experiments/kernel-increment-3/diagnostic/run.py).

**STOP:** diagnostic cause isolated; original Increment 3 gate remains NOT PASSED.
The next human decision is whether to authorize an adapter-only correction that
preserves strict versioned-envelope validation, followed by the original acceptance
probe. Keep the validated scripted kernel available; no MIRIX work yet.
