# Track III.8 — Broad workspace awareness, narrow context consumption

**2026-09-23 — FAIL under the frozen retrieval/oracle thresholds.**

Combined discovery gains only **one distinct required target per revision**, below
the required two, and misses the identity-normalizer/retry-admission oracles in the
bounded packet. Exact lexical retention, source freshness, security isolation and
the corrected full-envelope budget pass. No query, source fixture, oracle, ranking
rule or gain threshold was tuned after observing comparative results.

## Hypothesis and architectural boundary

Search broadly, load narrowly: lexical, semantic and structural discovery should
find current workspace concepts without sending the entire repository to cognition.
Workspace knowledge answers **what exists now**; learned Memory answers **what prior
work taught us**; repository/git/artifacts remain authoritative evidence. Derived
vectors and graph edges are candidates, not truth, completion evidence or authority.

The [III.1 research](../../docs/research/track-iii/001-reference-systems.md) and
[III.7 checkpoint](../../docs/milestones/048-track-iii-7-learned-memory-utility.md)
remain accepted within their original scope. Earlier increments were not rerun or
modified. This experiment reuses III.2's generic tree validation/readable-lineage
primitive, with trusted workspace ownership and domain grants. It does not change
Memory, promotion, provenance, SecurityContext or runtime contracts.

No cognition model judged discovery quality. No production Cognitive Loop, model
routing, Restate, remote execution, reflection, storage or NoveltyGate integration
was added. The [TaskSpec](request.json) is unsubmitted; no runtime Task ID/state is
claimed. FAIL is a completed research result, not a runtime Task failure assertion.

## Frozen source corpus and oracle

The authoritative workspace consists of two checked-in 24-file Python source trees:

| Revision | Content-addressed manifest identity |
| --- | --- |
| [A](workspace/A/) | `sha256:7c732c1b8130ed57b234972207bcea55c0ee6e79e8ffc725418f9009d8721f0b` |
| [B](workspace/B/) | `sha256:6ca2bbce0775ec482550b64f226624deb461a08b33e4b048500882e4edf9c6ac` |

These are immutable workspace snapshots identified by SHA-256 of a canonical
file→source-hash manifest, **not nested Git commit IDs**. [revisions.json](revisions.json)
pins every source byte; [revision-diff.json](revision-diff.json) declares the changes:

- HandleFold → IdentityFold and WindowGate → AttemptFence;
- ParcelSender moves from transport.py to adapters/parcel.py;
- legacy.py/persist is deleted and store.py/checkpoint replaces it;
- dispatch → persist → seal becomes dispatch → checkpoint → seal;
- DeliveryPort, StampBook, seal and configuration literals remain unchanged.

The corpus contains declared interface implementations, imports, direct calls,
a canonical identity transformation, a tempting incomplete quick_handle helper,
a receipt-deduplication component and twelve telemetry helpers with overlapping
vocabulary. The repetitive telemetry is an explicit distractor workload, not a
representative sample of real repositories. No fixture code is executed as an app.

[queries.json](queries.json) freezes exactly **12** primary queries: four lexical,
four semantic and four structural. [oracles.json](oracles.json) separately records
required/acceptable/forbidden targets, revision identities and permitted context.
The oracles predate embedding/ranking comparisons. Required targets are source
identities, not extractor-produced IDs. Repeated appearances of the same target
across queries/revisions do not manufacture additional unique gains.

| Queries | Intended oracle |
| --- | --- |
| L1–L4 | DeliveryPort, retry_ceiling, dispatch, READY_MARKER |
| S1 | Existing canonical identity folding, without its symbol name |
| S2 | Retry admission policy, without its symbol name |
| S3 | Reuse of acknowledgements for repeated submissions |
| S4 | Atomic publication of staged output |
| T1 | Declared DeliveryPort implementations |
| T2 | Direct caller of seal |
| T3 | Modules importing DeliveryPort, represented by their declarations |
| T4 | dispatch-to-seal call path, including the intermediate component |

The predeclared threshold is at least two additional distinct required targets
across semantic/structural queries **in each revision**, zero exact-query losses,
zero stale/forbidden outputs, and a 2048-byte response. Final bounded packets count;
merely including an oracle target in an unlimited index does not pass. The checker
also requires all combined mandatory targets to survive selection.

## Existing tooling and implementation choices

[tooling.json](evidence/tooling.json) records inspected source hashes and decisions.

**Graphify was exercised for real**, using the existing clean checkout at
`b9cd9570728a5ff3485d2a1e36fe9a1272a368ae` (the retained v0.9.64 carveout pin) and its
existing Python 3.12 environment. This is not a claim about the newer v0.9.66 pin
studied in III.1 or current upstream HEAD. `extract(paths, root=..., parallel=False)`
runs separately for each domain/revision, with temporary caches and the existing
Python socket-denial guard. No Graphify LLM extraction, watcher, server, assistant
hook or package installation runs.

Blaine already has [ProjectKnowledgeContext](../../runtime/kernel/project_knowledge.py),
an optional bounded Graphify navigation provider that checks source digests. Its
repository instantiation was found in the kernel-increment-9 experiment, not the
default runtime wiring. Presence in the codebase does not mean default runtime
workspace search adoption. This increment does not audit or reconfigure deployment.

**Semantic discovery uses real local BAAI/bge-m3**, confirmed at loopback port 8001,
through the existing infra/inference/accept.py request helper. Each top-level AST
declaration (including class bodies) is embedded; query text uses the same 1024-
dimensional model. Separate domain batches prevent mixed-domain indexing calls.
In-memory dense cosine scores are rounded to eight decimals and stably tie-broken.
No vector database, sparse index or new persistent service is introduced.

**Claude Context is intentionally not executed/adopted.** The pinned III.1 study
identified AST chunking/hybrid retrieval as useful abstractions but Milvus/Zilliz as
an extra operational dependency. This experiment tests generic semantic code search
with available local embeddings; it does not claim Claude Context compatibility or
reproduce its hybrid implementation.

Five successful retained embedding requests produced **62 vectors** (25 declarations
per revision, plus 12 queries). Two earlier requests preceded a Graphify normalization
error, for **seven embedding POSTs total**. No Qwen/cloud cognition was invoked.

## Baseline, combined discovery and validation

The lexical baseline is case-folded OR-token BM25 over authoritative declaration
text plus identifiers. It splits camel case/underscores, removes a fixed stopword
list and prioritizes exact full-symbol matches. It can retrieve multiple declarations
from multiple files; it is not deliberately restricted to literal full sentences.

The combined path consults the same lexical candidates, dense semantic scores and
real Graphify relationships. Normalization maps graph nodes to source declarations;
Graphify imports_from edges are refined using current source import names. Bounded
relationship lookup supports inheritance, imports, callers and call paths up to four
edges. This small fixture adapter is not a replacement graph engine. “Implements”
means declared inheritance here, not proof of behavioral contract satisfaction.

Selection reserves highest priority for exact symbols and explicit relation answers,
then interleaves semantic/lexical ranks, with reciprocal-rank fusion (`k=20`) only
breaking ties. Whole entries are greedily admitted into one compact packet. No
oracle information participates in retrieval or ordering. Raw candidates reach
**24 declarations / 17968 serialized bytes**; selection meaningfully excludes data.

Before rendering, each derived result must match the **visible source-manifest
revision**, current symbol/path, source digest and source text. Structural assertions
are additionally checked against Python AST calls, imports or bases. A revision stamp
alone does not certify an edge. Revisions exposed to callers hash permitted source
files only; they are not global activity counters.

The packet contains source target, line, digest, a short source excerpt, discovery
mechanisms and selected relations. Its envelope also has scoped selected-count/partial
status diagnostics. The complete caller-visible envelope, including diagnostics,
is capped at **2048 bytes**. The model does not receive entire files or raw graphs.

## Security and freshness controls

Trusted binding is personal-task under personal; source ownership comes from trusted
prefix→ContextNode/domain mappings. employer-x is a sibling domain. The actual rule
is lineage ∩ domain grant ∩ policy. Caller knowledge of its IDs grants no access.
The protected HiddenSender intentionally matches the canonicalization query and the
DeliveryPort vocabulary. Relevance never expands visibility.

Lexical statistics, semantic ranking and graph traversal operate on allowed records
and endpoints, not globally ranked results filtered only at rendering. Raw derived
indexes remain partitioned administrative evidence. Private source paths, names,
snippets, vector hits, graph relationships and rejected counts do not enter normal
outputs. Missing/malformed policy returns UNAVAILABLE/DENIED without contents.

[boundaries.json](evidence/boundaries.json) records 28 additional checks: fabricated
and foreign bindings, policy faults, and paired removal of hidden index records.
All 24 combined caller outputs remain byte-identical with those hidden records
removed. This covers the tested existence/count/revision side channel; it is not a
production authentication or embedding-service telemetry guarantee.

The safe stale-index control supplies A-derived indexes while requesting B. Derived
hits are explicitly excluded, with zero stale emissions. **A limitation remains:**
merging lexical and derived contributions before freshness rejection can discard a
valid lexical candidate with the stale contribution. All four exact hits disappear
from that control's B combined packets. This is fail-closed behavior, not a usable
fallback or utility PASS. Per-mechanism validation before fusion is future work;
the experiment was not retuned to remove this finding.

## Results and interpretation

Both revisions have identical required-target totals:

| Query group | Lexical-only | Combined | Additional distinct required targets |
| --- | ---: | ---: | ---: |
| Lexical | 4/4 | 4/4 | 0; no exact losses |
| Semantic | 1/4 | 2/4 | 1: StampBook |
| Structural | 8/8 | 8/8 | 0 |

Structural target totals exceed query counts because some queries require multiple
components. The same StampBook gain across revisions is **one unique target**, not
two gains. Structural relations are correctly discovered but add no oracle targets
beyond this lexical baseline. We do not turn extra graph metadata into target credit.

The S1 canonical normalizer and S2 retry policy exist in the broad candidate set but
not the final packet. In A, they rank 16th and 14th in dense search; telemetry and
other components outrank them. The novelty/reuse motivating case therefore **fails**.
S3's StampBook ranks first semantically versus 13th lexically and becomes a valid gain.
S4 was already a lexical hit. These observations explain failure without changing
the workload or implying semantic search is universally inferior.

Final primary outputs: **zero stale references, zero forbidden references, zero exact
losses; maximum complete envelope 2040 bytes** (payload maximum 1967). The independent
checker reports **584 checks, eight failures**: four final-coverage failures, two gain
threshold failures and two novelty failures. Remaining checks pass. This is **FAIL**,
not BLOCKED: both real mechanisms ran and the predeclared utility target was missed.

## Corrections, mutations and restoration

Both corrections are retained, not hidden:

1. Before any comparison, Graphify emitted an unresolved external node with an empty
   source_location. Integer normalization failed. The first registration, failure
   and two completed embedding calls are in [index-build-attempt-1.json](evidence/index-build-attempt-1.json).
   The empty-location parsing correction changed no source/query/oracle/threshold.
2. The initial comparison capped only the packet payload and omitted diagnostics:
   ten envelopes exceeded 2048 bytes (maximum 2118). The complete initial evidence
   and implementation are retained under [initial-payload-only](evidence/initial-payload-only/).
   [budget-correction.json](evidence/budget-correction.json) and its
   [exact patch](evidence/budget-correction.patch) record the two-line envelope fix.
   The checker verifies that it is the only post-registration discovery-code change.
   No embeddings or ranking rules changed. Utility remained FAIL before and after.

Negative controls use the final unchanged oracles and fixed vectors:

- **Freshness mutation:** A-derived indexes reused for B without revalidation emit
  **55 stale entry references and five stale relations**. These include old moved/
  deleted targets and the obsolete call path. Independent checker **exits 1**.
- **Isolation mutation:** bypassing prefiltering exposes **23 protected references**
  in caller outputs, plus 23 literal-scan findings. Independent checker **exits 1**.
- Correct behavior after both controls reproduces primary results byte for byte.
  Mutations are isolated non-default runner variants. The normal comparison still
  fails utility; “restored” does not mean that its research threshold passed.

## Evidence and reproduction

Python standard library suffices to replay retained indexes/vectors. The real live
collector additionally uses the already installed Graphify environment and local BGE
service. No dependency installer is part of the experiment.

```bash
python3 experiments/track-iii-008/discover.py --output /tmp/blaine-iii8-results.json
python3 experiments/track-iii-008/verify.py  # expected exit 1: retained utility FAIL
python3 experiments/track-iii-008/check_boundaries.py
python3 experiments/track-iii-008/verify.py evidence/freshness.json --control --output /tmp/iii8-freshness-check.json  # exit 1
python3 experiments/track-iii-008/verify.py evidence/isolation.json --control --output /tmp/iii8-isolation-check.json  # exit 1
```

The collector `build_index.py --live` refuses to overwrite the retained indexes.
Fresh collection requires a separate authorized evidence location; it is not a byte-
reproducibility promise for embedding inference. [reproducibility.json](evidence/reproducibility.json)
checks deterministic replay under two hash seeds using retained vectors and graphs;
it makes no new model/service calls. The independent checker imports neither indexer
nor discovery code, and recomputes source identities, oracle coverage, leakage and
threshold results rather than trusting summary fields.

| Artifacts | Evidence |
| --- | --- |
| [protocol](protocol.json), [queries](queries.json), [oracles](oracles.json), [security](security.json) | Frozen contracts and literal expectations. |
| [preregistration](evidence/preregistration.json), [tooling](evidence/tooling.json) | Input/source pins and actual integration inspection. |
| [indexes](evidence/indexes.json), [raw Graphify](evidence/graphify-raw.json), [vectors](evidence/vectors.json), [embedding requests](evidence/embedding-requests.json) | Real derived representations and provider provenance. |
| [results](evidence/results.json), [verification](evidence/verification.json) | Raw per-mechanism candidates, selected/omitted targets, source revalidation, packets and independent metrics. |
| [controls](evidence/controls.json), [freshness](evidence/freshness.json), [isolation](evidence/isolation.json), [safe stale-index](evidence/stale-safe.json) | Real emitted defects, checker exits and conservative fallback limitation. |
| [summary](evidence/summary.json), [restored](evidence/restored.json), [documentation checks](evidence/documentation-checks.json) | FAIL decision, restored evidence and repository checks. |

Administrative artifacts intentionally include synthetic protected fixtures and
mutant leaks. Only each result's output object is the caller-visible projection.
No real proprietary data or secret values were indexed.

## Implications, limits and unresolved questions

Broad retrieval composes with trusted lineage, security filtering and source
revalidation, but **this ranking/packet design did not demonstrate sufficient narrow-
consumption relevance**. Candidate presence is insufficient; useful coverage must
survive selection. Preserve per-mechanism freshness so an obsolete derived hit does
not invalidate independently fresh lexical evidence. Budget complete response bytes,
including metadata. No production dependency adoption follows from this experiment.

Costs: parser environment/cache management, cross-file resolver correctness, embedding
inference, 1024-dimensional vectors, linear cosine scans, full-snapshot freshness
checks and per-domain indexing. The corpus is small, Python-only and distractor-heavy;
complete snapshot rejection is conservative, not incremental refresh. Source/AST
revalidation does not prove general program semantics or relationship completeness.
No production provider logging isolation, large-repository cost, optimal chunking,
ranking, multilingual quality or downstream coding utility was demonstrated.

Open: chunk representation, duplicate/noise handling, ranking selection, preserving
fresh lexical fallback, incremental index invalidation and broader corpus validity.
No accepted Blaine invariant requires redesign. A separately authorized III.8 follow-up
is recommended before relying on this candidate discovery for NoveltyGate decisions.

## Exact proposed III.9 experiment — not started

After resolving the III.8 discovery deficiencies in separately authorized work,
freeze 12 proposed abstraction changes: four duplicates of existing concepts, four
legitimate new abstractions, four near-match cases with a meaningful contract
mismatch. Pin the repository revision and independent human-authored reuse/allow
oracles before evaluation.

Compare no advisory gate with a bounded novelty/simplicity advisory using current,
scoped discovery packets (2 KiB) and the same local model/action allowance. Advice
may identify a reusable concept, allow a justified addition or request review; it
must not claim production authority to block edits. Measure duplicate proposals
avoided, legitimate additions incorrectly blocked, unsupported dependency/scope
expansion and evidence references. Require at least two fewer duplicate proposals,
zero blocked legitimate additions, zero stale/forbidden references and preserved
near-match distinctions. A mutation that treats superficial similarity as equivalence
must cause a caught false block. Retain paired evidence and independent checks.

This is a proposal, not authorization or implementation. **III.9 has not started.**
No human architectural decision is needed to record III.8's FAIL; deciding on a
revised III.8 experiment or later work requires explicit authorization.
