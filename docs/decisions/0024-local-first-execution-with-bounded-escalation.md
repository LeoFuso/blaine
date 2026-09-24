# ADR 0024 — Local-first execution with bounded authorized escalation

**Status:** Accepted  
**Validation:** Integration — mechanism validated; no production remote binding provisioned

Supersedes this ADR's own earlier draft, which centred historical restricted
replay and stated an authority invariant that did not match the implemented
system. Both corrections are recorded below rather than hidden.

## Context

A stated success criterion for Blaine is reducing the share of work sent to paid
remote inference that local inference could have completed. Three routing
policies were considered:

```text
Policy A — classifier pre-routing (Jev)
Policy B — deterministic heuristic pre-routing
Policy C — local-first execution with bounded authorized escalation
```

There is not yet enough real execution evidence to justify a classifier, and
classifier agreement is not ground truth: two classifiers disagreeing proves only
disagreement, and a frontier tiebreaker never labels the cases where both agree
and both are wrong. Choosing a pre-router now would optimise a decision nobody
has measured.

The earlier draft proposed obtaining ground truth by replaying completed remote
Tasks under an authority that forbids the remote binding. Two repository facts
undermine that as the primary mechanism. Context providers resolve at execution
time — `MirixContext` performs a live semantic search against a mutable store —
so a later replay does not reproduce the original context, and a failed replay
could reflect memory drift rather than model capability. And the production
runtime wires local cognition and a local worker only, so the population of
remotely-served Tasks is currently empty.

That draft also asserted that authority is never Task data. The implemented
system contradicts it: `TaskSpec` carries `capabilities` and `autonomy.allowed`,
and `policy_gate` decides admissibility from them. Worse, nothing intersects a
top-level Task's requested authority with anything external, so a top-level
Task's authority is entirely self-declared by its request. That is a real gap,
and it is worth closing independently of any routing experiment.

## Decision

### Policy C is the active execution policy

Every eligible Task starts on the local binding and runs the ordinary bounded
Blaine loop. Extra local turns are a cost, not a failure: if local inference
self-corrects under verifier and policy constraints and finally satisfies the
completion contract, that is a successful local execution.

Escalation is reached only through deterministic conditions observable from
existing state. This increment admits two: a local turn budget reached without
satisfying the contract, and a repeated identical verifier rejection. No model is
asked whether it feels stuck, and no escalation predictor is built.

### Capability authority and binding authority are different

```text
A TaskSpec may declare requested capability authority.

Effective capability authority is
    requested capability authority INTERSECT externally granted authority.

A child Task may only narrow effective authority.

Worker, model and provider binding authority is not TaskSpec data. It comes from
trusted execution context and cannot be expanded by cognition.
```

The grant travels in the trusted request envelope, which already carries operator
data the spec does not. A request without a grant remains representable so
existing behaviour is unchanged, and the evidence records whether a Task was
externally bounded, so the remaining gap stays visible instead of implied.

### Escalation is a recommendation; admission is trusted

A deterministic condition produces an escalation recommendation. The trusted
execution boundary decides admissibility from the grant alone. A model may never
choose a provider, invent a binding, widen its grant, or edit a TaskSpec to
obtain remote authority, preserving [ADR 0010](0010-worker-selection-is-capability-and-quality-driven.md)'s
separation between work strategy and concrete worker.

An admitted escalation rebinds cognition for the remainder of the same Task. It
creates no second Task, no new lifecycle owner and no parallel state machine; the
durable runtime keeps owning the lifecycle and the existing CompletionVerifier
keeps owning the outcome.

### Escalation is an outcome, not a diagnosis

`escalated` means local execution required another tier. It does **not** mean the
local model was incapable. The underlying reason may be inadequate context, a
missing capability, a policy denial, a worker or dependency failure, verifier
rejection, or genuine capability limits. This increment records raw provenance
and defers classification to the failure-taxonomy work in Cycle C.

### Routing evidence is authoritative, not telemetry

Each Task retains a routing manifest as a content-addressed artifact, referenced
by an ordinary `artifact.produced` event so it is discoverable from the
append-only event record. OpenTelemetry spans are operational telemetry and may
be lost; nothing a future routing experiment needs may depend on them, and
nothing may depend on durable runtime state, which is retained for seven days.

### Measurement comes from observed outcomes

Routing quality is measured from what execution actually did — completion,
escalation, failure — rather than from a judge or a replay. Restricted replay
remains documented as a possible future technique for counterfactual evidence,
but it is not on the critical path and is not required for acceptance.

Reporting stays deterministic. Code owns counts, rates, breakdowns, joins,
sampling metadata and sample sufficiency. A model may interpret a vague question,
select the relevant comparison, explain limits and propose hypotheses from failure
records, but it never performs the arithmetic and never decides that a sample is
sufficient.

## Consequences

Blaine becomes useful now: authorized work is attempted locally by default and
escalates only through a bounded trusted mechanism. The baseline needed to judge
whether a smarter pre-router earns its complexity accumulates as a side effect of
normal operation, with no experiment to run and no paid provider call.

Closing the authority gap is worth more than the routing work that motivated it.
Until a grant is supplied, a top-level request still declares its own authority;
that is now visible in evidence rather than silently assumed.

The costs are honest. Local-first spends local turns before escalating, so an
unavoidable escalation costs more than it would under a perfect pre-router — that
cost is precisely the quantity a future policy must beat. Escalation counts will
overstate local incapability until failure provenance is classified. And a ratio
without its sampling rule is meaningless, so every reported number carries the
population it was drawn from.

## Validation

### Hypothesis

Blaine can attempt authorized work locally by default, escalate through a bounded
trusted mechanism that cognition cannot influence, and retain enough authoritative
evidence to decide later whether smarter pre-routing is justified.

### Validation level

`Integration`.

### Minimal validation

Synthetic bounded fixtures on the ordinary Task lifecycle. No paid provider call
is required, because no property here depends on a specific provider.

### Evidence

PASS requires that a top-level Task's effective authority is the intersection of
its request with an external grant; that a model-generated child cannot expand
it; that a model cannot obtain a remote binding by any route; that an eligible
Task starts locally and a locally completed Task never invokes remote inference;
that a deterministic condition produces an escalation recommendation which the
trusted boundary denies without authority and admits with it; that an admitted
escalation continues inside the same Task under the unchanged CompletionVerifier;
that routing evidence survives in authoritative storage; and that a deterministic
report derives local-completion and escalation metrics from that evidence and
reports an insufficient sample explicitly.

**Every criterion above is met**, by the twenty controls in
[`tests/test_kernel_routing.py`](../../tests/test_kernel_routing.py) and one live
run against real Restate and the adopted local serving deployment recorded in
[milestone 042](../milestones/042-policy-c-local-first-escalation.md). No paid
provider call was required, as this section's minimal-validation scope states.

Two limits are part of the acceptance rather than exceptions to it. **No
production deployment provisions a remote binding**, so admission was
demonstrated against a fixture escalation adapter and production currently
resolves every recommendation to `denied_binding_unavailable`; that denial is the
expected deployment state, observable in the routing record, and not a defect.
And whether the retained fields are *sufficient* to decide a future routing
question cannot be proven before evidence accumulates: the mechanism that retains
them is accepted here, the sufficiency of what it retains is not yet tested.

### Not required for validation

A classifier, a heuristic pre-router, controlled downgrade sampling, historical
replay, a failure taxonomy, an analytics database, a dashboard, a scheduler, or
any Jev call.

## Future work

**Policy B — deterministic heuristic pre-routing.** A cheap baseline that any
learned or external classifier must beat. The heuristic is not defined here: it
should be derived from real Policy C escalation evidence, not invented in advance.

**Policy A — classifier pre-routing.** Jev is integrated, authenticated and
unadopted. Adoption requires evidence that it improves routing against both
Policy C and Policy B. Its existence is not a reason to place it in the runtime
path, and a use case must not be invented for it.

**Controlled exploration.** Once a pre-router recommends remote, following that
recommendation produces no evidence about whether local would have sufficed, so a
router can become trivially conservative. A future bounded downgrade sample must
be randomized or explicitly defined, recorded, bounded, low-risk, distinguishable
from normal routing, and unable to change policy automatically.

**Intended future metrics.** Local under-classification is escalations over Tasks
routed local; remote over-classification is estimated from downgraded samples
completing locally. Neither replaces cost to successful completion, which belongs
to C4 and must include local turns, elapsed time, compute and escalation cost.

**A valid outcome is no smart router.** If Policy A ≈ Policy B ≈ Policy C, or the
improvement does not justify the complexity, Blaine keeps local-first escalation.
The decision is measured benefit, never the availability of a component.

Evidence may question the current policy. It never grants authority to deploy a
replacement: history, measurement, proposal, evaluation, then human promotion.

## Reconsider when

Real escalation evidence shows a class of Tasks whose escalation is predictable
and frequent enough that spending local turns on them is wasteful; a workload
arrives whose success cannot be expressed as a completion contract, so verdicts
stop being computable; or local serving capacity changes enough that the cost of
a local attempt no longer dominates the cost of a remote one.
