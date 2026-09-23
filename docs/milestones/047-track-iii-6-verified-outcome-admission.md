# Track III.6 — Verified outcome admission and reflection semantics PASS

Checkpoint: 2026-09-23. **PASS within offline deterministic experiment scope.**

Hypothesis: authoritative outcome/evidence can qualify reflection candidates while
worker claims remain untrusted. Success, failure and incomplete work remain distinct;
admission stays in the current context and does not promote knowledge. The
[experiment](../../experiments/track-iii-006/README.md) defines the exact fixtures,
trusted boundary, candidate-support assumptions, results and reproduction commands.

## Evidence

**1122/1122 checks PASS; 958 independent evidence checks PASS.**

- Case A admits VERIFIED_SUCCESS only with a successful envelope, PASS contract,
  PASS mandatory test and PRESENT artifact. Opposite worker claims cannot override
  authoritative evidence. Case B rejects a success claim despite the worker's “done”;
  its FAIL contract/test can support a separate failure-qualified candidate.
- Case D admits VERIFIED_FAILURE with deterministic condition-Q support. Failure
  knowledge cannot pass the success-intent gate. Case C's missing/unknown evidence
  and case F's unrun mandatory platform verifier cannot support success. Separate
  observations remain AGENT_OBSERVATION/UNVERIFIED, including cancelled work.
- Case E's PASS contract and FAIL mandatory test reject as contradictory. Every
  success requirement is independently faulted with FAIL/ABSENT, MISSING, UNKNOWN,
  UNAVAILABLE and NOT_RUN. Removed requirements, foreign/malformed evidence,
  unsupported text, missing support facts and forged status/provenance reject.
- Each verified record has private execution/envelope/evidence/verifier provenance
  and a snapshot digest. Source evidence remains unchanged. Ordinary retrieval
  exposes the scoped candidate and semantic status, never raw logs or private
  evidence references. Human direct declaration remains separate.
- **54 admission scenarios; 708 retrieval exports scanned; zero leaks.** All-context
  reads preserve exact lineage/domain/policy boundaries. Protected case X remains
  employer-x-private; verified status grants no public visibility. Later workers
  retrieve new entries using the same issued execution binding. Parent/sibling/
  unrelated contexts cannot read them; public revision remains unchanged.
- Replay reevaluates current evidence before returning an old receipt. Identical
  inputs return the same record; missing or contradictory evidence rejects. A new
  valid envelope requires a fresh request identity. Existing historical memories
  are not revoked or treated as evidence of current Task state.
- Worker-claim mutation: **141 failed checks, exit 1**, including an actual stored
  VERIFIED_SUCCESS record despite FAIL evidence. Missing-as-pass mutation:
  **55 failed checks, exit 1**, including actual success with a missing mandatory
  test. Correct execution is restored identically. Two fresh hash-seeded runs
  reproduce primary evidence byte for byte.

Evidence: [summary](../../experiments/track-iii-006/evidence/summary.json),
[results and private audits](../../experiments/track-iii-006/evidence/results.json),
[retrieval exports](../../experiments/track-iii-006/evidence/retrieval-exports.json),
[literal scan](../../experiments/track-iii-006/evidence/leakage.json),
[worker-claim mutation](../../experiments/track-iii-006/evidence/worker-claim.json),
[missing-evidence mutation](../../experiments/track-iii-006/evidence/missing-as-pass.json),
[independent checker](../../experiments/track-iii-006/evidence/verification.json),
[reproducibility](../../experiments/track-iii-006/evidence/reproducibility.json).

## Decision and limits

**ContextNode + continuous Memory + SecurityContext + PromotionGate +
VerifiedOutcomeAdmission survives as a conceptual composition.** Work qualification,
candidate support, visibility and promotion authority remain distinct. Memory is
still derived; evidence remains authoritative.

The new experimental VERIFIED_OUTCOME provenance retains separate VERIFIED_SUCCESS
and VERIFIED_FAILURE statuses. III.5's unchanged finite schema rejects that new
class, as explicitly tested without write effects. A future versioned extension
must preserve those statuses before promoting such entries. This is a prototype
compatibility limit, not an architectural conflict or permission to coerce provenance.

The support catalog pairs exact hand-authored statements with explicit trusted facts.
It does not prove arbitrary natural-language entailment, causality or future utility.
A failure can be verified despite a missing success artifact, but success requires
all evidence. An old admitted memory cannot replace a current evidence evaluation.

III.1–III.5 history and experiment sources remain unchanged. No production contracts,
Completion Contracts, Restate, Cognitive Loop, remote execution, MIRIX, database,
LLM reflection, consolidation, automatic promotion, revocation or concurrency were
implemented. The retained [TaskSpec](../../experiments/track-iii-006/request.json) is
unsubmitted; this PASS is not a runtime Task completion claim.

Unresolved: production evidence/envelope authority, evidence completeness, candidate
support validation, promotion schema extension, multi-source outcomes, contradiction
handling, immutable evidence versions, stale-memory presentation and durable replay.
No human architectural decision is required to close III.6.

Next: [the exact III.7 proposal](../../experiments/track-iii-006/README.md#exact-proposed-iii7-experiment--not-started):
12 paired deterministic later Tasks (four matching, four irrelevant, four near-match),
with/without scoped hints, a three-action budget and 2 KiB retrieval. Require at least
two additional verified completions, zero regressions on irrelevant/trap cases,
intact provenance/isolation and a caught failure-as-success mutation. Results would
establish only finite synthetic utility. **III.7 has not started and requires explicit
authorization.**
