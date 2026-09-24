# Track III.8R — Narrow consumption and fresh fallback recovery

**2026-09-23 — PASS within the original frozen III.8 corpus and thresholds.**
**III.8 remains FAIL.** This is one separately authorized recovery policy, not a
reinterpretation or replacement of the original result. III.9 has not started.

## Question and failure classification

[III.8](../track-iii-008/README.md) discovered the canonical abstraction in its broad
candidate set but omitted it from the final 2 KiB response. That distinguishes
candidate discovery from useful bounded consumption. It also merged stale derived
contributions with independently fresh lexical hits, then rejected the whole target.
The safe stale-index control consequently lost all four exact lexical results.

This increment tests a generic validation/fusion/selection policy using **exactly
those retained candidates**. Workspace knowledge remains a derived view of current
source; learned Memory remains historical knowledge; repository/artifacts remain
authoritative. No Memory, promotion, provenance, SecurityContext, runtime lifecycle,
Cognitive Loop or production API is changed. The [request](request.json) is an
unsubmitted TaskSpec: no suitable binding is exposed and no runtime Task is claimed.

## Frozen inputs and preregistration

[frozen-assets.json](frozen-assets.json) pins every original III.8 experiment file
at commit `504feced3942e70b52fc1642ef8171d542b045ec`. Both 24-file snapshots, all 12
queries and categories, oracles, required/acceptable/forbidden classifications,
security fixture, protected literals, indexes, vectors and lexical outputs remain
byte-identical. Full revision manifests remain authoritative:

| Asset | SHA-256 (revision identities use the `sha256:` prefix) |
| --- | --- |
| Snapshot A identity | `7c732c1b8130ed57b234972207bcea55c0ee6e79e8ffc725418f9009d8721f0b` |
| Snapshot B identity | `6ca2bbce0775ec482550b64f226624deb461a08b33e4b048500882e4edf9c6ac` |
| Both-snapshot file/hash manifest | `61b19732ce7f35684a6871142e2f5f914642d909c2fc7e1eed821381fea0bbbf` |
| Query manifest | `dfcd606cc33c45c32d4ab466ba460a83be052806c0b2566dfcec31e95dbcbbae` |
| Oracle manifest | `d8c7090283d2fb9de17ccd361654c60b963478357ce33c725b851a4f7f93d1b2` |
| Security fixture | `0020008b2cd13f6823b85b631babb0bff3efddf83de077f64a0c5f10fc374dda` |
| Original results, including lexical baseline | `2b8cd1c566bbda3828fb31bd76e11c1ae96cc525a026a48000cd81e7e0d89751` |
| Recovery policy | `941e8a5ab641828e24e42f6793a0bd52e49c00d76f41e3898a762bfad79095d8` |

The corpus-manifest hash is over compact sorted JSON mapping both-snapshot relative
source paths to file SHA-256 hashes. Snapshot identities use the original per-revision
manifest definition; they are not Git commit IDs.

[policy.json](policy.json) was frozen before implementing the recovery selector.
[POLICY.md](POLICY.md) explains the rationale. [preregistration](evidence/preregistration.json)
pins policy documentation, implementation and checker before the first comparison.
There were **zero post-outcome ranking adjustments and no implementation corrections**.
The first complete run passed. Subsequent runs only check exact reproduction.

Unchanged gates: four lexical/four semantic/four structural queries in both revisions;
at least two distinct additional non-lexical required targets **per revision**; no
lost exact lexical targets; all combined required targets retained; canonical reuse
included; zero stale/forbidden output; total externally visible response at most
2048 bytes; real failing freshness/isolation controls. Recovery adds the fallback
control. The lexical baseline is the original retained packet, not a new renderer.

## One generic recovery policy

The implementation reads no oracle, group-specific selection rule or expected target.

1. **Validate before competition.** Each mechanism's contribution independently
   checks trusted lineage/domain/policy, current path/symbol/line/source hash/text,
   visible revision and applicable AST relations. Invalid contributions do not enter
   the target table, rank lists, fusion or byte competition. A stale semantic hit
   does not invalidate a fresh lexical hit to the same current declaration.
2. **Canonical target deduplication.** Identity is requested visible revision plus
   relative path, symbol and line. Mechanisms contribute provenance to one payload.
3. **Clone-family rank compression.** Replace digit runs in source declaration text
   with `#`, then hash it. Each mechanism assigns ranks by first distinct family;
   repeated members share that rank. This query-independent normalization treats the
   twelve repetitive diagnostic declarations as one family for rank competition.
   It neither deletes targets nor claims behavioral equivalence.
4. **Rank fusion.** Sum exact rational `1/(60 + rank)` across mechanisms. Raw BM25,
   cosine and structural scores never share an arithmetic scale. Sort exact full-
   symbol lexical equality first, explicit structural answers next, then descending
   RRF, best family rank and lexical target identity. No oracle membership is used.
5. **Diversity and bounded consumption.** Visit one target from each family before
   second representatives; exact matches retain priority. Greedily add whole entries
   only when the complete envelope fits. Rejecting a candidate consumes no bytes.
6. **Compact provenance.** One visible source-manifest revision commits the source
   hashes. Entries retain path/symbol, line, first 80 source characters and L/S/G
   provenance. Relations use selected-entry indices. Diagnostics, truncation, status,
   revision and all metadata count toward the same 2048-byte limit.

These rules change representation and selection together. There is no ablation
establishing which individual change caused the gain. Digit-normalized families may
conflate important constant differences; this is not suitable proof of equivalence
for a future NoveltyGate. It is a diversity heuristic tested on a known corpus.

## Mechanism reuse and operational boundary

Original BM25/identifier/exact-symbol candidate lists, local BAAI/bge-m3 cosine
rankings and pinned Graphify v0.9.64 extraction results are reused unchanged. The
adapter revalidates source/AST relations and uses the original trusted ContextTree
binding. No new embedding inference, graph extraction, cognition or network calls
occur. **Zero model invocations; no new dependencies or persistent services.**

Claude Context remains intentionally unnecessary. This increment does not compare
embedding models, replace Graphify or claim production integration. Retained raw
lists and vectors reproduce the accepted mechanisms; no synthetic replacement
ranking is called a fresh semantic-search observation.

## Results

| Revision / query group | Original lexical baseline | Recovered combined | Unique new required targets |
| --- | ---: | ---: | ---: |
| A / lexical | 4/4 | 4/4 | 0 |
| A / semantic | 1/4 | 4/4 | 3 |
| A / structural | 8/8 | 8/8 | 0 |
| B / lexical | 4/4 | 4/4 | 0 |
| B / semantic | 1/4 | 4/4 | 3 |
| B / structural | 8/8 | 8/8 | 0 |

Aggregate required-target instances: lexical **8/8 → 8/8**, semantic **2/8 → 8/8**,
structural **16/16 → 16/16**. The gain is **three distinct targets per revision**:
acknowledgement reuse, retry admission and canonical identity folding. The same
concepts occurring in two revisions are not six independent gains. Literal target
IDs change for the renamed gate/normalizer; the checker exposes exact sets per
revision rather than inflating a cross-revision score.

**1912 independent primary checks PASS.** Zero stale references, zero forbidden
references, zero exact-query losses. Maximum complete response: **2047 bytes**.
Packets select 11–12 distinct targets; target deduplication and diversity do not
increase the byte limit or duplicate source payloads. All final mandatory targets
are present, not merely in unlimited candidates.

**Structural extraction/security/freshness composition: supported within the fixture.**
**Structural incremental retrieval utility: UNPROVEN on this corpus.** The lexical
baseline already covers every structural target. Graph edges are not counted as
extra target gains. A separate structural carveout would require new authorization.

## Canonical abstraction diagnostic

The literal oracle inspection is performed only by the independent checker, after
selection. The selector never sees this diagnostic's target identities.

| Revision | Original broad rank | Lexical / semantic rank | Valid contributions | Fused rank | Diversity selection rank | Entry bytes | Final |
| --- | ---: | --- | --- | ---: | ---: | ---: | --- |
| A | 16 | 15 / 16 | Lexical, semantic | 15 | 4 | 162 | Included |
| B | 16 | 15 / 18 | Lexical, semantic | 15 | 4 | 164 | Included |

The normalizer remains below the repeated telemetry declarations in raw fused target
order. The generic first-family round naturally brings it into the fourth selection
position. Its canonical identity uses the current revision/path/symbol/line; the
renamed A identifier is not exposed as current in B. Full identities, validation,
ranks and bytes are retained in [independent verification](evidence/results-verification.json).

## Fresh fallback and negative controls

Safe stale-index replay requests B while supplying A-derived candidates. Per-mechanism
validation eliminates stale derived contributions before fusion; current lexical
contributions survive. **All four B exact hits are emitted**, with no stale/forbidden
references. The independent fallback report passes **1653 checks**. This fixes the
III.8 observed failure without changing source, query or baseline truth.

| Control | Actual defect | Independent checker |
| --- | --- | --- |
| Freshness bypass | 134 stale entry references and five stale edges | Exit 1: no-stale-emission |
| Isolation bypass | 24 protected references, also 24 independent literal-scan findings | Exit 1: no-forbidden-emission |
| Late merged invalidation | All four required B lexical hits suppressed after provisional selection; no refill | Exit 1: four exact-retention failures |

The stale count includes unchanged declarations falsely presented with stale derived
provenance, as well as renamed/moved/deleted targets and obsolete edges. Literal
scan findings and protected references are not counted as separate unique leaks.
The fallback mutation demonstrates loss of valid knowledge even without content
leakage. Mutants are isolated, non-default variants; default output after all three
controls is byte-identical to the first result.

## Evidence and reproduction

All retained administrative artifacts use synthetic protected data. Only each
record's `output` object is caller-visible; raw candidate/audit evidence is not a
cross-domain response. The checker scans complete output, including diagnostics.

| Artifact | Purpose |
| --- | --- |
| [frozen-assets](frozen-assets.json), [preregistration](evidence/preregistration.json) | Original corpus and policy/code identity before evaluation. |
| [results](evidence/results.json) | Exact raw lists, per-contribution validation, dedup identities, ranks, reservations, omissions and final packets. |
| [independent verification](evidence/results-verification.json) | Source/AST checks, baseline comparison, per-query metrics, gains, canonical diagnostic and scans. |
| [safe fallback](evidence/stale-safe-verification.json) | All exact lexical hits survive stale derived data. |
| [controls](evidence/controls.json) | Actual failing checker exits and defects for all three mutations. |
| [summary](evidence/summary.json) | III.8R PASS while III.8 stays FAIL; III.9 unstarted. |
| [reproduction](evidence/reproducibility.json), [documentation checks](evidence/documentation-checks.json) | Two hash-seed byte-identical runs, unchanged original assets and repository validation. |

```bash
python3 experiments/track-iii-008r/check.py experiments/track-iii-008r/evidence/results.json --output /tmp/iii8r-check.json
python3 experiments/track-iii-008r/check.py experiments/track-iii-008r/evidence/stale-safe.json --control --output /tmp/iii8r-fallback-check.json
# Each mutation checker must exit 1:
python3 experiments/track-iii-008r/check.py experiments/track-iii-008r/evidence/freshness.json --control --output /tmp/iii8r-freshness-check.json
python3 experiments/track-iii-008r/check.py experiments/track-iii-008r/evidence/isolation.json --control --output /tmp/iii8r-isolation-check.json
python3 experiments/track-iii-008r/check.py experiments/track-iii-008r/evidence/fallback.json --control --output /tmp/iii8r-late-check.json
# Reproduce all results into a new directory; runner refuses overwrite:
python3 experiments/track-iii-008r/run.py --output /tmp/iii8r-independent-replay
```

The checker imports neither selector nor the original discovery implementation. It
reconstructs authoritative source and relations using AST, verifies all original
asset hashes, checks exact raw lists, recomputes rank scores and oracle coverage,
scans complete outputs and calculates thresholds rather than trusting summary fields.

## Interpretation and recommendation

The original broad-awareness/narrow-consumption hypothesis is satisfied **on this
frozen synthetic corpus by this one recovery policy**. This does not retroactively
make III.8 PASS, establish universal retrieval quality, prove downstream cognition
benefit or justify automatic production retrieval. No post-outcome ranking changes
occurred. Real source snapshots remain authoritative; indexes cannot grant authority.

Validation belongs before competition, with provenance-specific validity retained
until fusion. Invalid derived evidence must not invalidate fresh source evidence.
Compact shared metadata and diversity can recover candidate coverage under a small
budget, but an 80-character excerpt is not proof of downstream task adequacy. The
known corpus contains unusually repetitive telemetry; broader clone diversity,
constant-sensitive families, languages, repository sizes, incremental invalidation
and snippet usefulness remain unresolved. Costs include per-contribution validation,
family normalization, fusion and source-state checks; no new operational service.

**Recommendation regarding III.9:** the bounded discovery prerequisite is now met;
III.9 may be separately authorized as an advisory experiment, not production blocking.
Retain the exact proposal: 12 changes (four duplicates, four legitimate additions,
four meaningful near-match contract mismatches), paired no-advice/advice conditions
with the same local model, three-action allowance and 2 KiB current scoped packets.
Require at least two fewer duplicates, zero blocked legitimate additions, preserved
near-match distinctions and zero stale/forbidden references. A superficial-similarity
as-equivalence mutation must cause a caught false block. Do not treat source-family
normalization as evidence that two abstractions have equivalent contracts.

**III.9 has not started.** No human architectural decision is required to close
III.8R; starting the proposed next experiment requires explicit authorization.
