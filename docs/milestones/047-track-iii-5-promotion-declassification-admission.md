# Track III.5 — Promotion and declassification admission PASS

Checkpoint: 2026-09-23. **PASS within offline deterministic experiment scope.**

Hypothesis: explicit promotion admission can broaden visibility while preserving
source security/provenance, requiring additional approval and fail-closed checks at
security boundaries. Generation is separate; every candidate is hand-authored.
The [experiment](../../experiments/track-iii-005/README.md) documents exact fixtures,
semantics, results, limits and reproduction.

## Evidence

**560/560 checks PASS; 512 independent evidence checks PASS.**

- Same-domain child → immediate parent promotion succeeds only on a permitted route
  with trusted SYSTEM_PROMOTION_SERVICE authority. Agents and humans have no automatic
  promotion authority. Sibling, descendant, self, unrelated, missing, skipped-parent
  and unapproved-parent destinations reject. Ordinary observation writes remain local;
  human direct declaration remains a separate authorized operation.
- Cross-domain employer-x → root admits a safe hand-authored candidate only with
  approval bound to exact source, destination and candidate, plus all required clean
  scans. Raw protected copies, including human-declared copies, reject. Human origin
  does not declassify content.
- Nine scanner categories cover synthetic token, organization/domain, project/repository,
  host/URL, ticket, class/package/source, database/table, protected literal and normalized
  eight-token source fragments. **54 scanner/fault combinations** fail closed: unavailable,
  crash, malformed, unknown, synthetic timeout and cannot evaluate. No real DLP claim.
- Source snapshots and direct-read visibility remain identical. Destination receives
  a new representation; UNVERIFIED stays UNVERIFIED and human-origin data remains
  identifiable. Private source/creator/hash/approval/match details stay in private audit.
  Later participants can read newly admitted ancestors through the same execution binding.
- **114 complete destination-visible exports scanned; zero protected literal hits.**
  Records, receipts, provenance, IDs, diagnostics and visibility-scoped revisions are
  included. Source lookup/promotion probes cannot distinguish hidden from absent IDs.
  Foreign local-key collisions and private activity do not change public admission IDs
  or visible revisions; an actual public admission legitimately increments visible state.
- Identical replay returns the same receipt without duplicate effects; changed request
  content rejects. Replay rechecks scanners and fails when a required scanner becomes
  unavailable. Rejected replay remains rejected without effects.
- Fail-open mutation: **42 failed checks, exit 1**, with actual public admission of a
  synthetic token and **two leaking exports**. Correct execution afterward is identical.
  Two fresh hash-seeded runs reproduce retained primary artifacts byte for byte.

Evidence: [summary](../../experiments/track-iii-005/evidence/summary.json),
[results/audits](../../experiments/track-iii-005/evidence/results.json),
[destination exports](../../experiments/track-iii-005/evidence/destination-exports.json),
[literal scan](../../experiments/track-iii-005/evidence/leakage.json),
[mutation](../../experiments/track-iii-005/evidence/fail-open.json),
[independent verification](../../experiments/track-iii-005/evidence/verification.json),
[reproducibility](../../experiments/track-iii-005/evidence/reproducibility.json).

## Decision and limits

**ContextNode + continuous Memory + SecurityContext + PromotionGate survives without
changing the accepted conceptual model.** Admission changes visibility, not truth or
verification status. Gate authority is distinct from ordinary writes and human origin.
The existing parent-by-parent rule remains: the cross-domain source is an initial
employer-x fixture, not an implicit task-x → root jump.

Replay must revalidate the gate before returning a stored success. Public receipts
must be deliberately projected; private audit structures cannot be serialized directly
to destinations. Metadata is subject to the same boundary as content: identifiers
are destination-scoped, and only legitimately visible changes affect visible revisions.

III.2–III.4 sources and all production runtime contracts remain unchanged. No LLM,
real scanner service, database, MIRIX, embedding, Graphify, reflection, verified learning,
Completion Contract, Restate or remote-execution integration was added. The retained
[TaskSpec](../../experiments/track-iii-005/request.json) is unsubmitted; experiment PASS
is not a runtime Task completion state.

This is a finite gate-composition proof under trusted labels, token issuance and
hand-authored approvals. It does not establish semantic abstraction correctness,
complete DLP, malicious-code confinement, production approval authority, source
completeness, cryptographic audit, concurrent/durable idempotency or revocation.
Same-domain admissibility of unverified hypotheses is explicitly fixture policy.

Next: [the exact proposed III.6 synthetic verified-outcome admission experiment](../../experiments/track-iii-005/README.md#exact-proposed-iii6-experiment--not-started),
using authoritative synthetic outcome/evidence envelopes, hand-authored reflection
candidates, failure/unverified distinctions and a worker-success forgery mutation.
**III.6 has not started.** No human architectural decision is required to close III.5;
starting III.6 requires explicit authorization.
