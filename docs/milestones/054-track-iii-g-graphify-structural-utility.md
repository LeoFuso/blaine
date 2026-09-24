# Track III.G — Graphify structural utility PASS

Checkpoint: 2026-09-23. **PASS within the frozen two-repository corpus.**
Architectural classification: **ADAPT / ON-DEMAND**. III.10 remains the planned
Track III sequence close; III.G is a complementary research carveout resolving the
open question of incremental structural retrieval utility. III.8 remains FAIL and
III.8R remains its separate PASS. No production integration or further work started.

## Hypothesis and actual mechanism

III.8/8R exercised real Graphify's extraction/freshness/security composition but their
lexical baseline already found 8/8 structural targets. They could not establish
incremental value. III.G freezes 20 source-oracled questions: five direct relationships,
five multi-hop, five impact/reachability, five ambiguity traps, ten per repository.
Questions distinguish imports/calls, inheritance/implementation, package identity and
structural connection/runtime impact. No cognition model judges correctness.

Primary pins:

- Spring Kafka: `fff33914d4e450a33e17195e11a79937c3505605`.
- Jackson Databind: `c59ce26302bb9cfdc8084ffee1e1318ad1db3d99`.
- Graphify 0.9.64: `b9cd9570728a5ff3485d2a1e36fe9a1272a368ae`.
- Query SHA-256: `3ca265a6bf43afb3de3bd325c22c74019195b005563074afb58347e41a233d93`.

[Experiment](../../experiments/track-iii-graphify/README.md),
[protocol](../../experiments/track-iii-graphify/PROTOCOL.md),
[corpus freeze](../../experiments/track-iii-graphify/evidence/corpus-freeze.json) and
[oracles](../../experiments/track-iii-graphify/oracles.json) preserve registrations.
Earlier A revisions are pinned separately for genuine checkout-transition freshness.
Source archives retain unmodified Java and license notices. A limited independent
Java source parser plus inspected source witnesses supplies authority, not Graphify.

A gets three source operations: batched exact-token search, full start-file read,
frontier search. B gets one structural capability request using native Graphify
extraction, directed build, BFS/path routines. C combines the same A+B evidence and
costs four requests. All share source revalidation, security overlay, typed answers,
canonical deduplication and <=2048-byte whole-packet consumption. No query-specific
selection, oracle hints or outcome-driven tuning. Source facts are not fed wholesale
to lexical exploration; only statements in actually retrieved windows/files qualify.

## Results by repository

Cells count required targets in final packets; traps count correct abstentions.

| Repository / group | A lexical | B Graphify | C combined |
| --- | ---: | ---: | ---: |
| Spring direct | 7/7 | 7/7 | 7/7 |
| Spring multi-hop | 2/2 | 1/2 | 2/2 |
| Spring impact | 12/16 | 14/16 | 13/16 |
| Spring traps | 2/2 | 2/2 | 2/2 |
| Jackson direct | 3/3 | 3/3 | 3/3 |
| Jackson multi-hop | 2/3 | 2/3 | 3/3 |
| Jackson impact | 6/21 | 13/21 | 13/21 |
| Jackson traps | 3/3 | 3/3 | 3/3 |

Graphify alone adds **eight distinct required targets**, combined adds **nine** over
lexical: one combined gain on Spring, eight on Jackson. The gate was at least three.
Combined loses zero baseline direct targets and adds no false trap conclusions.
Eight multi-hop/impact queries attain equal-or-better required coverage in one B
request versus three A operations, exceeding the gate of three queries.

This is not local latency improvement: total measured query time across ten questions
per corpus is A/B/C 0.122/0.340/0.461 seconds Spring, 0.693/1.380/2.069 seconds Jackson.
Graph materialization/source validation costs remain real. Combined alone completes
Jackson's long deserialization path; Graphify alone misses that path and Spring's
registration chain. It is not a general replacement for source exploration.

All normal primary packets have **zero stale, forbidden or unsupported emitted
references**, zero oracle false positives and **maximum 1995 bytes** including metadata
and diagnostics. Broad candidates are not counted as hits unless selected. Additional
provenance makes C's S-I1 packet fit one fewer target than B; this was retained unchanged.

## Confidence, freshness and operational cost

At B, Spring raw edges comprise 14307 EXTRACTED / 786 INFERRED; Jackson 38698 / 5832.
Source validation supports 4506/595 and 12848/3999, respectively. Other edges are
reported separately as unresolved, ambiguous, unsupported or forbidden; exclusion is
not automatically proof of an upstream false positive. A selected Jackson path uses
one source-validated INFERRED call, but that question already succeeds lexically.
Neither confidence label is authority.

Real Java overload merging creates a concrete hazard: an INFERRED call from one
createKafkaConsumer overload is attached to the location of another. Normal validation
rejects the ambiguous node. Treating the inferred relation as a source fact yields an
incorrect direct-call assertion. This is a real upstream relation, not an injected edge.

A→B uses **full graph rebuild with retained content parse cache**, not claimed
incremental graph update. Spring gains a KafkaAdmin dependency; Jackson removes an
AnnotatedMethod import/holder structure. Refreshed packets emit zero stale references.
Seven current Spring imports are omitted by packet budget; Jackson's current import
packet has no missing internal import. Missing coverage is reported, not called stale.

| Measured cost | Spring | Jackson |
| --- | ---: | ---: |
| Initial native extraction + directed build | 1.786 s | 4.301 s |
| B cached extraction + full rebuild | 1.233 s | 2.876 s |
| B retained compressed raw index | 288860 bytes | 667218 bytes |
| B compact raw JSON | 8684989 bytes | 21024857 bytes |
| Parse cache after B | 14026302 bytes | 27162736 bytes |
| B peak RSS before archive work | 113160 KiB | 205316 KiB |

No extraction failures/warnings or operational services; whole subprocess timings,
commands, node/edge counts, source-validation overhead and package versions are retained.
There is no arbitrary retrospective performance gate. These are fixture-process costs,
not a deployed graph service benchmark.

## Controls and independent evidence

- Stale A graph used as B: 16 stale node references across both packets, including a
  removed Jackson import; independent checker exits 1.
- INFERRED-as-authority: one unsupported wrong-overload call; checker exits 1.
- Optional isolation bypass: a protected candidate reaches the internal candidate set
  but packet selection omits it. No external leak occurs; this mutation is inconclusive.
  Normal source/path/literal checks independently prove the tested security boundary.

The checker records **2067 passing checks**. A separate replay records **127 passing
checks**, re-deriving source facts from all four source archives and reproducing all 60
packets/candidate-answer sets byte-identically. Timing measurements are not asserted
identical. [Summary](../../experiments/track-iii-graphify/evidence/summary.json),
[verification](../../experiments/track-iii-graphify/evidence/verification.json),
[mutations](../../experiments/track-iii-graphify/evidence/mutation-controls.json) and
[reproduction](../../experiments/track-iii-graphify/evidence/reproduction.json) are retained.

Execution corrections are explicit: unsafe predicate truthiness caused a TypeError
after primary comparison; explicit boolean conversion fixed controls only. The initial
checker also mistakenly required an optional isolation mutation to leak. It was aligned
with the predeclared mandatory controls. Original code pins, initial FAIL report and
corrected hashes remain in [errata](../../experiments/track-iii-graphify/evidence/execution-errata.json).
Primary evidence, gates, queries, oracles and selection remain unchanged.

## Architectural implication and limits

Graph-shaped workload now demonstrates incremental structural retrieval utility,
strongest on Jackson's impact neighborhoods. **ADAPT / ON-DEMAND** follows from that
benefit alongside overload limitations, incomplete paths, source-validation cost and
slower local queries. Consider an implementation behind bounded Blaine
`workspace.structure.query/neighbors/path`; do not expose unrestricted Graphify MCP
or treat a graph edge as authoritative. Security, revision and source support remain
requirements on content and metadata alike.

The fixed lexical planner is not optimal human exploration. The source validator is
not a complete Java compiler; dynamic dispatch, reflection and runtime impact remain
unproved. No other language, scale, concurrency, incremental-update or production
security claim follows. A precomputed validator inventory itself has cost and could
support other implementations; Graphify was not compared against every static analyzer.

No human decision is required to close III.G. Recommend separately authorized final
Track III architecture consolidation, including on-demand structural capability,
unsupported/partial-result contracts, overload precision, freshness ownership and
cost-aware lexical fallback. Production adoption/integration priorities require human
architectural review. Nothing beyond this carveout is started.
