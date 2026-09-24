# Track III.2 — Deterministic context semantics PASS

Checkpoint: 2026-09-23. **PASS within isolated deterministic experiment scope.**

Hypothesis: a generic ContextNode tree and trusted context binding can enforce
permitted downward inheritance and local writes without label-specific memory
classes, models, storage services or production runtime integration.

The [experiment and reproduction guide](../../experiments/track-iii-002/README.md)
documents the user's fixed 11-context personal/employer tree, exact oracles,
implementation boundary, results, limitations and proposed III.3. The assignment's
topology and no-cache scope supersede the tentative III.1 experiment details;
[III.1](043-track-iii-1-reference-systems.md) remains a historical research checkpoint.

## Evidence

- **221/221 correct cases PASS**: exact reads for all contexts, root-only visibility,
  downward inheritance, parent/sibling/cousin/unrelated/deep-descendant isolation,
  current-context writes and no upward visibility.
- **121 context/entry direct-ID pairs**, plus an unknown ID: naming a forbidden
  entry does not expose it. Forged scope/context/ancestor/destination parameters,
  fabricated and foreign bindings are rejected without write effects.
- **11 malformed trees rejected**, including missing/self parents, cycles,
  duplicates, multiple parents/roots, missing policy and a cycle behind a read stop.
- **Mutation detected:** wrong sibling inheritance causes **37 failures** in the
  same suite and process exit **1**. Correct implementation then passes again with
  identical results and unchanged source/oracle hashes.
- Labels, input ordering and an additional specialization level do not change the
  rules. A trusted fixture boundary stops inheritance and cannot be reopened by a caller.

Machine evidence: [summary](../../experiments/track-iii-002/evidence/summary.json),
[exact case results](../../experiments/track-iii-002/evidence/results.json),
[mutation](../../experiments/track-iii-002/evidence/mutation-control.json),
[independent verification](../../experiments/track-iii-002/evidence/verification.json),
[reproduction](../../experiments/track-iii-002/evidence/reproducibility.json).

## Decision and limits

**The ContextNode/tree abstraction survives unchanged.** Current-context writes
and direct-ID checks can use runtime-derived lineage without new architectural
memory classes. Tree validity must be checked independently of read permission:
a denied ancestor edge cannot conceal a cycle from validation.

The evaluator is an executable specification, not a production API or security
sandbox. No cache, traversal API, promotion, reflection, memory backend or continuous
ExecutionContext capability is implemented. Cache/traversal safety is deferred.
No runtime, lifecycle, PolicyGate, Completion Contract, worker, routing, D1/D2 or
remote-execution behavior changed. No model, network or database was used.

The [TaskSpec](../../experiments/track-iii-002/request.json) is unsubmitted because
no suitable binding was exposed. This experiment PASS is not a Restate Task state.

Unresolved: production binding issuance, topology/policy revision and revocation,
per-entry security, write idempotency/concurrency, persistence and resource bounds.

Next proposal: [III.3's exact offline continuous-capability experiment](../../experiments/track-iii-002/README.md#exact-proposed-iii3-experiment--not-started),
using fake cognition/worker/verifier callers, a later scoped observation, bounded
responses and an initial-only negative control. **III.3 is not started.** No human
architectural decision is needed to close III.2; starting III.3 requires explicit
authorization.
