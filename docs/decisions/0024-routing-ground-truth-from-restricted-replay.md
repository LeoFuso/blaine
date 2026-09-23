# ADR 0024 — Routing ground truth comes from a restricted replay, not a judge

**Status:** Proposed  
**Validation:** Unvalidated

## Context

A stated success criterion for Blaine is reducing the share of work sent to paid
remote inference that local inference could have completed. Measuring that needs
ground truth: for a given Task, would the local binding have sufficed?

Three tempting answers are worse than they look.

**Comparing outputs** asks whether the local model wrote something similar to the
remote one. That is subjective, needs a judge, and rewards imitation rather than
success.

**Using a frontier model as a tiebreaker** only fires when two classifiers
disagree, so it never labels the cases where both agree and both are wrong —
precisely the shared-bias failure that matters most. It is also circular: routing
decides when to spend on the expensive model, so grading that decision with the
expensive model inverts the economics being optimized.

**Trusting a suitability classifier** puts the prediction before the measurement.
Until the outcome is known, there is nothing to tell the classifier it was right.

Blaine already owns a better instrument. Completion is decided by a deterministic
CompletionVerifier against an explicit contract, so "did this Task succeed" is
answerable without opinion. The loop also lets a weaker model recover across
iterations under policy and verifier constraints, which means extra turns are a
cost rather than a failure.

Timing favours deciding now. The production runtime currently wires local
cognition and a local worker only; the frontier path exists in experiments. The
ratio this ADR wants to measure therefore has no denominator yet, and the remote
path can be born measurable instead of being instrumented afterwards.

## Decision

Ground truth for "could this have been local" is **the verdict of a restricted
replay Task**, not a judge and not an output comparison.

A replay is an ordinary Task. It reuses the original retained TaskSpec and its
CompletionContract unchanged, and it is created with an authority grant that
forbids the remote binding. The existing CompletionVerifier decides it. The
comparison is the pair of verdicts.

The invariants are:

- **Iterations are cost, not failure.** A replay that needs more turns and still
  satisfies the contract counts as a success, because recovering under policy and
  verifier constraints is the architecture working as intended. Only failing the
  contract, exhausting the turn limit or being cancelled counts as failure.
- **Binding and authority are operator data, never Task data.** A Task cannot
  select, widen or inherit its own binding. The operator or the replay harness
  chooses, so no Task can escalate itself to paid inference.
- **A replay never affects the Task it replays.** It is a separate Task with its
  own identity, lifecycle, authority and artifacts. It is sampled, asynchronous
  and low priority, and its failure is not the original's failure.
- **Replays target remotely-served Tasks.** Replaying a locally-served Task
  reveals nothing that was not already observed.
- **No new ledger.** The comparison row is the two verdicts plus the observed
  turn and token counts, joined through the retained spec identity and the
  existing ExecutionEvent evidence.

This ADR decides how the number is obtained. It deliberately does **not** decide
the routing policy that the number should produce. A bare error-rate threshold
would be wrong: a local failure costs its spent turns and then the escalation, so
the decision rule belongs to cost-to-success routing, with its own evidence.

## Consequences

The share of remote work that local inference would have completed becomes
measurable without paying a judge, and the measurement improves as the local
model improves, because it re-runs rather than re-scores.

Replay closes the counterfactual gap that history alone cannot: a Task's outcome
is only observed for the arm that ran. Replaying the remote arm locally answers
the question that matters for cost, and it distinguishes a binding that was
necessary from one that was merely used.

The costs are real. Every replay spends local GPU time and wall-clock, so
replays must be sampled rather than exhaustive. A replay cannot recover a Task
whose inputs were not retained, and it cannot reproduce an effect whose external
state has since changed, so Tasks with non-reproducible side effects are outside
its scope and must be excluded rather than silently mismeasured.

The measurement is also only as honest as the failure taxonomy beneath it. A
local replay that failed because its context was inadequate must not be recorded
as a capability limit; without that distinction the ratio will understate what
local inference can do.

Making authority a first-class per-Task input is the one architectural change
this requires. It is bounded, and it is the same input the frontier contract
already defines; today it exists only as an experiment fixture.

## Validation

### Hypothesis

For a Task served remotely, re-running its retained TaskSpec under an authority
that forbids the remote binding yields a verdict that is a truthful answer to
"local inference would have sufficed", without any judge.

### Validation level

`Integration`.

### Minimal validation

Take a small number of retained TaskSpecs whose original run completed with a
remote binding. Create one replay Task each with the remote binding denied.
Record both verdicts, the turns and the token usage. No new classifier, no
routing change and no policy change.

### Evidence

PASS requires that each replay is an independent Task with its own verdict from
the unchanged CompletionVerifier; that no replay altered its original Task; that
no replay obtained the remote binding; and that replays needing more turns but
satisfying the contract are recorded as successes rather than failures. A
resulting ratio is an observation, not an adoption decision.

### Not required for validation

A routing policy, a suitability classifier, a learned model, a dashboard, a
frontier reference labeler, exhaustive replay of every Task, or any change to
Task lifecycle, authority semantics or Completion Contract semantics.

## Reconsider when

Work arrives whose success is genuinely not expressible as a CompletionContract,
so a verdict cannot be computed and a reference labeler becomes the only
instrument; replay cost outgrows its value on a saturated GPU; or measured
failure attribution shows that context quality, not model capability, dominates
the gap, in which case the effort belongs in context compilation rather than
routing.
