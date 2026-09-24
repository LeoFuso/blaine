# Track III.8 — Workspace discovery FAIL

Checkpoint: 2026-09-23. **FAIL under the frozen retrieval/oracle thresholds.**

Combined lexical, semantic and structural discovery found only **one distinct
additional required target per revision**, below the required two. The canonical
identity-normalizer and retry-admission targets did not survive bounded selection.
The [experiment](../../experiments/track-iii-008/README.md) records the complete
protocol, source corpus, tool provenance, raw candidates, packets and limitations.

## Hypothesis and experiment

Broad awareness, narrow consumption means searching the workspace broadly while
loading at most 2048 bytes into a downstream context. Workspace indexes describe
what exists now; learned Memory describes prior experience; repository source and
artifacts remain authoritative. No search hit gains authority through indexing.

Two immutable 24-file synthetic Python snapshots exercise renamed symbols, a moved
implementation, deleted/replacement functions and a changed call path. Revision A
is `sha256:7c732c1b8130ed57b234972207bcea55c0ee6e79e8ffc725418f9009d8721f0b`;
B is `sha256:6ca2bbce0775ec482550b64f226624deb461a08b33e4b048500882e4edf9c6ac`.
These are content-manifest identities, not nested Git commits. Twelve queries and
independent literal oracles were frozen before comparison: four lexical, four
semantic and four structural. Both conditions query the same revision, scope and
source corpus under the same complete-response budget.

- Lexical: deterministic BM25 token matching, identifier splitting and exact-symbol
  priority over authoritative declarations; no deliberate literal-only handicap.
- Semantic: actual local **BAAI/bge-m3**, 1024-dimensional vectors, existing inference
  request helper, deterministic cosine ordering. Five successful retained embedding
  requests produced 62 vectors; two additional requests occurred in an unsuccessful
  initial index build. No cognition or cloud calls.
- Structural: actual **Graphify**, existing clean v0.9.64 carveout checkout at
  `b9cd9570728a5ff3485d2a1e36fe9a1272a368ae`, separate domain/revision extraction,
  temporary cache and socket-denial guard. Bounded adapters expose implementations,
  imports, callers and call paths; source AST revalidation checks relations.

The existing optional ProjectKnowledgeContext provider is instantiated in the
kernel-increment-9 experiment, not default runtime wiring. No deployment adoption
is inferred. Claude Context was intentionally not installed/exercised: its persistent
vector-store requirements are disproportionate here. The generic semantic-search
primitive uses existing local infrastructure without a new database or service.

## Results and controls

The following required-target counts are identical in A and B. Structural queries
have multiple required targets, so their denominator differs from query count.

| Query group | Lexical only | Combined | Distinct additional targets |
| --- | ---: | ---: | ---: |
| Lexical | 4/4 | 4/4 | 0 |
| Semantic | 1/4 | 2/4 | 1 |
| Structural | 8/8 | 8/8 | 0 |

The sole gain is StampBook, the acknowledgement-reuse abstraction. Counting it again
in revision B does not create a second unique gain. Real graph relations provide
context but no additional required target over this strong lexical baseline. The
novelty/reuse motivating identity-normalizer query **fails**. Relevant declarations
exist in broad candidates; finding them somewhere in an index is insufficient.

**584 independent checks, eight failed quality checks.** Those failures are the two
missing final semantic targets per revision, the two gain thresholds and the two
novelty assertions. Default outputs have **zero stale and zero forbidden references**,
zero exact-query losses and maximum **2040 bytes including diagnostics**. The 28
binding/policy/metadata noninterference checks pass. Protected employer-x source is
relevant but absent from personal outputs; removing all foreign indexed objects
leaves caller-visible results byte-identical, including counts and visible revisions.

An initial budget implementation counted only packet payload: ten full envelopes
exceeded 2048 bytes, maximum 2118. The exact budget-only correction and all initial
outputs are retained. No query, oracle, ranking or threshold was changed; utility
failed before and after correction. An earlier Graphify empty-location normalization
error occurred before comparisons and is separately recorded.

- Freshness mutation reuses A's derived index for B without validation: **55 stale
  entry references and five stale edges** become visible. Independent checker exits
  **1**, specifically for stale emission.
- Isolation mutation bypasses scope filtering: **23 protected entry references**
  appear, also caught by 23 independent literal-output findings. Checker exits **1**.
- Safe stale-index exclusion emits no stale/forbidden content, but loses all four B
  exact lexical targets because merged candidates inherit the stale derived verdict.
  This is a conservative fallback defect, not evidence of successful degraded search.
- Restored default output is identical. Retained-vector replay under two hash seeds
  reproduces the measured FAIL; no unsafe variant runs by default.

Evidence: [preregistration](../../experiments/track-iii-008/evidence/preregistration.json),
[results](../../experiments/track-iii-008/evidence/results.json),
[independent checks](../../experiments/track-iii-008/evidence/verification.json),
[controls](../../experiments/track-iii-008/evidence/controls.json),
[summary](../../experiments/track-iii-008/evidence/summary.json),
[reproduction](../../experiments/track-iii-008/evidence/reproducibility.json).

## Decision, limitations and next proposal

Security and authoritative revalidation compose with broad discovery, but this
ranking/packet design does **not** establish sufficient useful narrow consumption.
The accepted principle remains viable; the measured implementation fails its utility
hypothesis. Preserve separate freshness for independently sourced candidates and
budget the complete caller-visible envelope. No production adoption follows.

Costs include parser environments, per-domain extraction, embedding inference,
vector storage in retained files, linear scoring and full-snapshot freshness checks.
Python-only, small and deliberately distractor-heavy sources do not establish
real-repository generalization, incremental refresh, graph completeness, optimal
chunking/ranking or downstream coding utility. Provider logging isolation is untested.
Open questions are ranking/noise handling, fresh lexical fallback, incremental
invalidation and representative corpora.

III.1–III.7 experiment/history files and production runtime contracts remain unchanged.
The [request](../../experiments/track-iii-008/request.json) is unsubmitted; no runtime
Task completion is claimed. No human architectural decision is required to record
FAIL. A separately authorized III.8 follow-up is recommended before gate research.

[Exact III.9 proposal](../../experiments/track-iii-008/README.md#exact-proposed-iii9-experiment--not-started):
after addressing discovery deficiencies, freeze 12 abstraction proposals (four
duplicates, four legitimate additions, four near-match contract mismatches). Compare
no advisory with novelty/simplicity advisory using the same local model/action budget
and current 2 KiB scoped packets. Require at least two fewer duplicate proposals,
zero blocked legitimate additions, no stale/forbidden references and preserved
near-match distinctions. An equivalence-overgeneralization mutation must cause a
caught false block. **III.9 has not started; further work requires authorization.**
