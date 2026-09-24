# Track III.4 — Bounded security context isolation PASS

Checkpoint: 2026-09-23. **PASS within offline deterministic experiment scope.**

Hypothesis: trusted security-domain/policy checks intersect structural lineage across
raw memory, derived representations, graph paths, cache fixtures and diagnostics.
The [experiment guide](../../experiments/track-iii-004/README.md) gives the exact
model, topology, fixtures, surface, limitations and reproduction commands.

## Evidence

**1259/1259 checks PASS; 1335 independent evidence checks PASS.**

- Nine generic ContextNodes; two private domains (personal and employer-x), plus
  explicitly public shared knowledge. Same-domain ancestor inheritance remains
  usable. Private records deliberately placed at the structural root do not become
  globally readable. Public inheritance can also be denied by explicit policy.
- All **324 context/object direct-ID pairs** match literal expectations, covering
  12 initial raw entries and 24 derived objects. Descendant, sibling, unrelated and
  cross-domain contents remain inaccessible. Domain/classification/provenance and
  arbitrary scope/target metadata cannot confer authority.
- Continuous human/cognition/worker/verifier sequences use one binding per execution.
  Human declarations stay domain-private with trusted USER_DECLARATION provenance;
  observations stay local, AGENT_OBSERVATION and UNVERIFIED. Human origin does not
  grant public access. Declaration remains distinct from promotion.
- Summaries, embedding/index stubs, graph nodes/edges, artifact/tool stubs and their
  source metadata require permission to every source. Graph neighbors expose only
  permitted relationships and endpoints. Synthetic cache reuse checks context,
  domain, policy, revision and source permissions.
- Eleven policy/binding fault variants deny or report unavailable across seven
  operations, without write effects. Structure remains independently validated,
  including a cycle behind a closed inheritance edge.
- Denied/empty/unavailable results remain distinct without protected details.
  Scoped diagnostics/counts and paired hidden-data removal tests show no tested
  enumeration leakage. **618 serialized caller-result bundles scanned; zero leaks.**
  Maximum response **1441 bytes**, within the inherited **2048-byte** cap.
- Structural-only mutation: **177 failed checks, 165 leaking bundles, exit 1**.
  Query-only cache mutation: **6 failed checks, 2 leaking bundles, exit 1**.
  Correct execution after controls is identical. Two hash-seeded reproductions match.

Retained evidence: [summary](../../experiments/track-iii-004/evidence/summary.json),
[expected/actual results](../../experiments/track-iii-004/evidence/results.json),
[audience-separated exports](../../experiments/track-iii-004/evidence/observables.json),
[literal scan](../../experiments/track-iii-004/evidence/literal-leakage.json),
[independent verification](../../experiments/track-iii-004/evidence/verification.json),
[reproducibility](../../experiments/track-iii-004/evidence/reproducibility.json).

## Decision and limits

**ContextNode + continuous Memory + SecurityContext survives conceptually unchanged.**
Lineage is necessary but insufficient: each access path must intersect trusted domain
classification and policy. Provenance is orthogonal. No label-specific memory class
or production lifecycle change was needed. III.2/III.3 sources remain unchanged.

One additional finding: globally unique caller-chosen write IDs could reveal hidden
record existence through collision behavior. Experimental writes now namespace local
keys under the trusted destination. A paired test with/without a hidden foreign
record returns identical receipts. This refines the experiment's ID surface, not
Blaine's production contracts.

A visibility-scoped append-only cache revision also prevents foreign/sibling writes
from exposing activity through invalidation; visible writes still invalidate stale
results. This is a fixture rule, not production cache versioning.

The private shared-root records are defensive stress fixtures, not authorized upward
flow or declassification. Mixed-source graph edges require all source permissions.
Harness reports containing fixtures/attacker requests/mutant leaks are administrative
evidence; only the audience-separated output projection is a caller-visible artifact.

Limits: trusted labeling/issuance and fixture internals, finite corpus, no hostile
Python sandbox, real authentication, providers, production cache, safe external log
system, concurrency, persistence, replay, retention or revocation. Real source-label
completeness and provider egress remain open. The experiment proves no general
semantic secrecy or semantic declassification capability.

No production/runtime changes, dependencies, real secrets, promotion, declassification,
reflection, verified-learning or Completion Contract/Restate integration occurred.
The [TaskSpec](../../experiments/track-iii-004/request.json) is unsubmitted; no suitable
runtime binding was exposed and experiment PASS is not a runtime Task state.

Next: [III.5's exact proposed synthetic promotion/declassification admission experiment](../../experiments/track-iii-004/README.md#exact-proposed-iii5-experiment--not-started),
with hand-authored candidates, explicit authority/provenance, fail-closed scanner
availability, destination leakage oracles and a failing control. **III.5 is not
started.** No human architectural decision is needed to close III.4; starting III.5
requires explicit authorization.
