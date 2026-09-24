# Track III.3 — Continuous memory capability PASS

Checkpoint: 2026-09-23. **PASS within offline deterministic experiment scope.**

Hypothesis: one trusted ExecutionContext can expose bounded memory throughout
execution while preserving hierarchy, provenance and caller authority. The
[experiment](../../experiments/track-iii-003/README.md) records the exact fixture,
sequence, interface, controls, limitations and reproduction instructions.

## Evidence

**394/394 checks PASS; 158 independent evidence checks PASS.**

- Trusted human declares at authorized project-a with USER_DECLARATION provenance.
  Cognition reads inherited entries and that declaration, then writes an UNVERIFIED
  AGENT_OBSERVATION at task-a1. Worker receives the same execution binding, queries
  afresh, sees cognition's observation and records another. Verifier queries and
  sees all seven permitted entries. No prior memory-result blob is handed off.
- All 11 original visibility sets and 121 direct-ID pairs pass. Current/ancestor
  reads and local writes preserve parent, descendant, sibling, cousin and unrelated
  isolation. A cycle behind a denied inheritance edge is still rejected.
- Provenance/source/identity/authority fields cannot forge human authority. Agents
  cannot select parent/sibling/unrelated write targets or arbitrary read scopes.
  Fabricated and foreign bindings fail; verifier writes and unauthorized human
  targets are denied without storage effects.
- Whole-envelope compact UTF-8 responses stay within **2048 bytes**, maximum observed
  **1757 bytes**. Overflow selection is deterministic and unaffected by forbidden
  records. Oversized permitted entries yield a partial result, distinct from EMPTY.
- SUCCESS_WITH_RESULTS, EMPTY, DENIED and UNAVAILABLE are distinct. Faulted writes
  have no effects; recovery is explicit. RECORDED is a separate write receipt.
- Frozen initial-only retrieval fails **2** unchanged-oracle checks (worker/verifier)
  with exit **1**. Trusting caller provenance fails **4** checks with exit **1**, with
  the forged persisted record retained as evidence. Correct execution afterward is
  identical; two hash-seeded reproductions match retained evidence byte for byte.

Machine evidence: [summary](../../experiments/track-iii-003/evidence/summary.json),
[results/trace](../../experiments/track-iii-003/evidence/results.json),
[initial-only control](../../experiments/track-iii-003/evidence/initial-only.json),
[provenance mutation](../../experiments/track-iii-003/evidence/forged-provenance.json),
[verification](../../experiments/track-iii-003/evidence/verification.json),
[reproduction](../../experiments/track-iii-003/evidence/reproducibility.json).

## Decision and limits

**The generic ContextNode/tree and continuous ExecutionContext capability model
survive.** III.2's evaluator is imported unchanged. Human declarations are an accepted
refinement introduced before III.3: direct authorized writes with trusted provenance,
not child-to-parent promotion. This requirement was not tested in III.1/III.2.
The [research addendum](../research/track-iii/001-reference-systems.md#accepted-refinement-before-iii3--2026-09-23)
records it without changing those historical results.

Readable observations remain unverified; declarations establish provenance, not
truth or PolicyGate permissions. Evidence remains authoritative. The human path
has exactly one fixture-authorized target; this is not a preference or policy system.

The model assumes trusted issuance and confinement of the caller-facing surface;
it is not a sandbox against code accessing Python internals. Real authentication,
concurrency, persistence, durability, revocation, observability isolation, caching,
retention and conflict/supersession semantics remain unresolved. An oversized entry
exposes a future pagination/chunking decision. Full security is not claimed.

No production/runtime integration or new dependency was introduced. No MIRIX,
database, model, semantic retrieval, reflection, promotion, declassification,
Completion Contract, Restate, routing, worker or remote-execution change occurred.
The [TaskSpec](../../experiments/track-iii-003/request.json) remains unsubmitted:
no suitable runtime binding was exposed, and experiment PASS is not a Task state.

Next: the [exact proposed III.4 isolation experiment](../../experiments/track-iii-003/README.md#exact-proposed-iii4-experiment--not-started)
uses synthetic domain-tagged representations, fake retrieval/cache/graph/diagnostic
paths, literal allow/deny matrices and a leak mutation. **III.4 is not started.**
No human architectural decision is required to close III.3. Starting III.4 requires
explicit authorization.
