# Track III.8R — Narrow consumption and fresh fallback recovery PASS

Checkpoint: 2026-09-23. **PASS on the original frozen III.8 corpus and thresholds.**
**III.8 remains FAIL.** This milestone records one explicitly authorized recovery,
not a revision of milestone 049 or its retained experiment. III.9 remains unstarted.

## Hypothesis and frozen boundary

III.8's canonical target existed in broad discovery but was omitted from the bounded
packet. Separately, stale merged contributions suppressed independently fresh lexical
hits. The [follow-up](../../experiments/track-iii-008r/README.md) tests selection and
fresh fallback using unchanged repository snapshots, 12 queries, oracles, security,
candidate lists, lexical baseline and 2048-byte complete-response budget.

[Asset hashes](../../experiments/track-iii-008r/frozen-assets.json) pin all original
III.8 files at `504fece`, including source revisions A
`sha256:7c732c1b8130ed57b234972207bcea55c0ee6e79e8ffc725418f9009d8721f0b`
and B `sha256:6ca2bbce0775ec482550b64f226624deb461a08b33e4b048500882e4edf9c6ac`.
Original evidence remains byte-identical. No query/oracle/source/threshold changed.

The [policy](../../experiments/track-iii-008r/POLICY.md) and parameters were frozen
before comparison; implementation/checker hashes were registered before execution.
**One policy, zero post-outcome ranking adjustments, no implementation corrections.**

## Recovery policy

- Validate each mechanism contribution independently before ranking/fusion/budget
  competition. Remove invalid contributions; preserve independent fresh lexical hits.
- Deduplicate current revision/path/symbol/line targets and combine provenance.
- Compress ranks of repetitive source-text families using a query-independent hash
  after decimal digit normalization. Select one family representative per round.
  This is a diversity heuristic, not semantic equivalence or a reuse verdict.
- Fuse ranks using exact rational RRF, **k=60**, without mixing raw numeric scales.
  Exact whole-symbol lexical matches have priority, then structural answers, then
  fused ranks with deterministic ties. No oracle identities enter selection.
- Render one scoped revision, path/symbol/line, 80-character source excerpts, compact
  mechanism provenance and entry-index relations. Count the complete envelope,
  including diagnostics and truncation metadata, against **2048 bytes**.

Reuse is literal: original BM25, BGE-M3 cosine lists and actual Graphify v0.9.64
extraction results. **No new inference/extraction/network calls, dependencies or
persistent services.** Claude Context remains unnecessary. Runtime contracts and
previous increments are unchanged; this does not integrate workspace discovery.

## Results and evidence

Counts are identical in both revisions:

| Required targets | Original lexical baseline | III.8R combined |
| --- | ---: | ---: |
| Exact lexical | 4/4 | 4/4 |
| Semantic | 1/4 | 4/4 |
| Structural | 8/8 | 8/8 |

**Three unique additional required targets per revision**, exceeding the unchanged
minimum of two. These are the same three concepts across revisions, not six distinct
conceptual gains. Aggregate required-target instances: lexical 8/8 → 8/8; semantic
2/8 → 8/8; structural 16/16 → 16/16. Structural incremental retrieval utility remains
**UNPROVEN**; extraction, freshness and security composition remain supported within
the fixture. Extra edges do not count as new required targets.

**1912 independent primary checks PASS.** Zero stale references, forbidden references
or exact-query losses. Maximum complete response **2047 bytes**. The canonical target
had original broad rank 16 in each revision; it now has fused rank 15, diversity
selection rank 4 and is included (162/164 entry bytes). Target-level deduplication
preserves the appropriate renamed identity and current revision.

The safe stale-index control retains **all four fresh B exact hits**, passes **1653
checks**, and emits no stale/forbidden references. Required controls cause real defects:

| Mutation | Observable defect | Checker |
| --- | --- | --- |
| Reuse A-derived data for B without validation | 134 stale entries and five stale edges | Exit 1 |
| Bypass isolation | 24 protected references, independently found in 24 literal scans | Exit 1 |
| Select stale merged targets, invalidate late, no refill | All four fresh B exact hits lost | Exit 1 |

Default output after mutations is identical. Two hash-seeded reproductions match
retained evidence byte-for-byte. No unsafe variant is active by default.

Evidence: [preregistration](../../experiments/track-iii-008r/evidence/preregistration.json),
[results](../../experiments/track-iii-008r/evidence/results.json),
[independent checks and canonical diagnostic](../../experiments/track-iii-008r/evidence/results-verification.json),
[controls](../../experiments/track-iii-008r/evidence/controls.json),
[summary](../../experiments/track-iii-008r/evidence/summary.json),
[reproduction](../../experiments/track-iii-008r/evidence/reproducibility.json).

## Implications, limits and recommendation

Broad awareness/narrow consumption now satisfies the original hypothesis **within
this corpus**. Validation must preserve per-mechanism provenance before fusion;
stale evidence must not suppress independently fresh evidence. Shared metadata and
source diversity recover useful final coverage without relaxing authority or budget.

This recovery was informed by known III.8 failures; it is not unseen-corpus validation.
Several generic changes were evaluated together, so individual causal contributions
are unmeasured. Digit normalization may group implementations whose constants matter;
80-character snippets may be inadequate for later cognition. No downstream coding
benefit, general ranking optimality, incremental freshness, large/multilingual
repository performance or production readiness is established. Open questions are
family diversity, snippet usefulness, index maintenance and representative workloads.
The [TaskSpec](../../experiments/track-iii-008r/request.json) remains unsubmitted.

**Recommendation:** III.9 may now be separately authorized as a bounded advisory
experiment. The [exact proposal](../../experiments/track-iii-008r/README.md#interpretation-and-recommendation)
uses 12 abstraction proposals (four duplicate, four legitimate, four near-match),
paired advisory-off/on with the same local model, three-action budget and 2 KiB
current scoped packets. Require at least two fewer duplicate proposals, zero blocked
legitimate additions, preserved near-match distinctions and zero stale/forbidden
references; catch a false-equivalence mutation. Do not use source-family similarity
as authority to block changes. **III.9 has not started.** No human architectural
decision is required to close III.8R; further execution requires authorization.
