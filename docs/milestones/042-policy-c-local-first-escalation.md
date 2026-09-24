# Policy C — local-first execution with bounded authorized escalation

**2026-09-23 — COMPLETE. [ADR 0024](../decisions/0024-local-first-execution-with-bounded-escalation.md)
is Accepted for its mechanism; no production remote binding is provisioned.**

| Component | Status |
| --- | --- |
| Implementation | COMPLETE |
| Local execution | LIVE |
| Escalation detection | LIVE |
| Authority enforcement | LIVE |
| Escalation evidence | LIVE |
| Remote escalation path | IMPLEMENTED |
| **Remote binding** | **NOT PROVISIONED** |

The work began as an attempt to make a classifier useful and found the prior
question: nobody had measured whether remote work was necessary. This increment
answers that by making local-first execution the active policy and retaining the
evidence a smarter router would later have to beat. No classifier and no
heuristic routes anything.

Evidence: [live probe and report](../../experiments/policy-c-local-first/README.md).

## What Policy C does

Every eligible Task starts on the local binding and runs the ordinary bounded
loop. Extra turns are a cost, not a failure: a Task that self-corrects under
verifier and policy constraints and finally satisfies its completion contract
completed locally, however many turns it needed.

Escalation is reached only through deterministic conditions computed from state
Blaine already keeps: a local turn budget reached, or a repeated verifier
rejection. Reaching a condition produces a **recommendation**. Only the trusted
boundary admits it, and admission requires both that the external grant names an
escalation binding and that the deployment actually provides that binding. A
grant naming a binding the deployment does not implement is refused rather than
silently substituted.

An admitted escalation rebinds cognition for the remainder of the same Task. It
creates no second Task, no scheduler and no new lifecycle owner, and the
unchanged CompletionVerifier still decides the outcome.

## The authority gap this closed

`TaskSpec` carries `capabilities` and `autonomy.allowed`, and nothing intersected
them with anything external, so a top-level Task's authority was entirely
self-declared by its request. Effective capability authority is now the request
intersected with a grant carried in the trusted envelope, a child may only
narrow, and binding authority never appears in a TaskSpec at all.

This is worth more than the routing work that motivated it. A request without a
grant stays representable so existing behaviour is unchanged, and the routing
record states whether the Task was externally bounded, so the remainder of the
gap is visible instead of assumed. The Personal Agent intake now supplies grants.

## A correction found during validation

The first repetition signal digested only the verifier's outcome shape. Against a
static completion contract that shape is identical on every refusal, so any
unfinished Task looked stuck at the third turn and the turn budget was
unreachable. The signature now includes the admitted evidence, so a repeat means
the Task was refused and produced nothing new, while a Task still changing its
evidence is working and answers to the turn budget instead. Tests cover both
paths; the first version's expectations were wrong, not its behaviour.

## Evidence and reporting

Each Task retains a routing record as a content-addressed artifact, referenced by
an ordinary `artifact.produced` event. It carries policy identity, whether the
Task was externally bounded, effective capabilities, initial and final binding,
local and total turns, escalation reason, admission and iteration, completion and
result references, context packet references and concerns.

Nothing a routing experiment needs depends on OpenTelemetry, which is lossy, or
on durable runtime state, which is retained for seven days.
[`scripts/routing-report.py`](../../scripts/routing-report.py) derives counts,
rates and medians from that evidence, states its sampling rule and denominators,
and reports `INSUFFICIENT_SAMPLE` deterministically rather than narrating a
finding. A model may explain the report; it never computes it.

An escalation record says local execution required another tier. It is **not** a
claim that the local model was incapable; raw provenance is retained so the Cycle
C failure taxonomy can attribute causes later.

## Validation

241 kernel tests pass, 20 of them new, plus 57 platform tests, with no regression
in the 221 that existed before. They cover externally bounded authority, a child
unable to expand it, a specification unable to carry a binding, local start,
local completion without touching the escalation adapter, both deterministic
conditions, denial without a grant, denial without an authorized binding, denial
when the deployment lacks it, admission with it, continuation inside the same
Task, the verifier still owning the outcome, evidence retention, and the report.

One live probe ran against real Restate and the adopted local Qwen deployment
with zero paid provider calls: the Task completed locally under an external
grant, never escalated, retained its routing record, and the deterministic report
read it back and reported the sample as insufficient.

## What remains future work

Policy B (deterministic heuristic pre-routing) and Policy A (Jev) are unstarted,
and a valid outcome is that neither earns its complexity. Controlled downgrade
sampling, needed so a future router cannot become trivially conservative by
recommending remote for everything, is documented and unimplemented. Cost to
successful completion belongs to C4. Failure classification belongs to C1; this
increment retains provenance and classifies nothing.

## Current production behaviour

No deployment configures an escalation binding, so the trusted boundary resolves
every recommendation to `denied_binding_unavailable`:

```text
local execution -> escalation condition -> trusted admission
                -> no provisioned remote binding -> denied_binding_unavailable
```

That denial is the expected deployment state, not a defect in Policy C. It is
recorded in the routing record rather than hidden, and the first deployment to
provision a remote binding can use the denial count as one signal that the
binding became reachable.

No live local-to-remote execution has been demonstrated. The live acceptance
showed local completion under an external grant with no paid provider call, and
the admission path was exercised against a fixture escalation adapter.

## Thresholds are experimental defaults

The local turn budget of 8 within a 16-turn ceiling, and the repetition threshold
of 3, are plausible starting values rather than measured ones. They are ordinary
module constants, and both are recorded in every routing record so evidence
gathered under one setting remains interpretable after it changes. Revising them
is a deliberate configuration change informed by observed outcomes, not an
architectural decision.

The report's `MINIMUM_REPORTING_SAMPLE` of 20 is a guardrail against reading too
much into a handful of Tasks. It is **not** a statistical significance threshold,
and no confidence interval or hypothesis test is implied.
