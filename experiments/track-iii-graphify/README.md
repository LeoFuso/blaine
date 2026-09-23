# Track III.G — Graphify structural utility

**PASS on the frozen bounded corpus. Classification: ADAPT / ON-DEMAND.**
III.G closes an explicit open research question; III.10 remains the planned sequence
close. III.8 remains historically FAIL, III.8R remains PASS. No production integration,
model calls, embeddings, persistent service or unrestricted agent-facing MCP was added.
The retained [TaskSpec](request.json) is unsubmitted; no durable runtime binding is claimed.

## Hypothesis and registration

Can real Graphify contribute useful structural knowledge beyond three bounded source
exploration operations, without becoming authoritative? III.8/8R could not answer
this: lexical search already covered all eight structural targets. This carveout uses
real production Java and typed, graph-shaped questions, including long call chains,
reverse heritage neighborhoods and deliberately unsupported relationships.

[Protocol](PROTOCOL.md), [queries](queries.json), [source-derived oracles](oracles.json),
[security overlay](security.json), [corpus freeze](evidence/corpus-freeze.json) and
[implementation/index registration](evidence/preregistration.json) precede comparison.
Exactly 20 questions: five each DIRECT, MULTI_HOP, IMPACT, TRAP; ten per repository.
Query manifest SHA-256: `3ca265a6bf43afb3de3bd325c22c74019195b005563074afb58347e41a233d93`.
No query, oracle, budget, selector or threshold was changed after outcomes.

The gate requires at least three additional **unique repository/target identities**
with Graphify or combined over lexical, zero lost mandatory direct targets in combined,
zero additional trap false conclusions, zero stale/forbidden output, complete packets
at most 2048 bytes, and at least three multi-hop/impact questions with equal-or-better
coverage in fewer exploration requests. Actual stale and inferred-trust mutations must
be caught. The isolation mutation is explicitly optional in the frozen protocol.

## Repositories and source authority

| Corpus | A, earlier freshness revision | B, primary comparison revision |
| --- | --- | --- |
| [Spring Kafka](https://github.com/spring-projects/spring-kafka) | `7d71e8d3765a6139188bc84c5e6560a02e85a97c` | `fff33914d4e450a33e17195e11a79937c3505605` |
| [Jackson Databind](https://github.com/FasterXML/jackson-databind) | `b12300930e69cd050345878375bdb730c3632bac` | `c59ce26302bb9cfdc8084ffee1e1318ad1db3d99` |

[Repository manifests](repositories.json) pin URL, commit and SHA-256 of every tracked
file. Aggregate B checkout hashes: Spring
`79db120c1ea1947b28b9ace6feea4a75d8603dc32183d40aac151c137c0807b9`, Jackson
`459c24e8bff589bd431ace71116f9232090a00b6f571715d008de3a07c51a252`.
The retained source archives contain unmodified main Java and root license notices;
full Git clones are disposable `/tmp` inputs, not committed repositories. Tests,
auxiliary modules, dependencies and build execution are excluded. B has 354 Spring
and 575 Jackson Java files. The independent parser excludes Jackson's module-info
unit from package-bearing source facts. These pins are evaluated as snapshots, not
claims about the latest upstream release. Jackson here uses `tools.jackson` packages.

Oracle truth came from declarations, explicit imports and source-supported static
receiver/call relationships, before comparative queries. [Source review](evidence/source-oracle-review.json)
retains literal witness windows. `source.py` uses tree-sitter Java independently of
Graphify to validate witnesses and candidate relationships. It is a limited fixture
validator, not Java compilation or a replacement graph service. Reflection, virtual
runtime effects, unresolved external types and ambiguous overloads are not proven.
Both methods can receive credit for an alternative supported path to the required
endpoint. Impact means plausible structural connection, never proven runtime effect.
Negative traps mean absence of the specified typed relation in this bounded scope.

## Mechanisms and equal boundaries

Real [Graphify](https://github.com/Graphify-Labs/graphify) **0.9.64**, commit
`b9cd9570728a5ff3485d2a1e36fe9a1272a368ae`, is the same pin exercised by III.8.
[Configuration](graphify.json) and [installed packages](evidence/packages.json) record
its actual environment. Java extraction covers classes, interfaces, enums, records,
annotations, methods/constructors, imports and calls. The native raw graph distinguishes
EXTRACTED and INFERRED. We use `extract(..., parallel=False)`, directed
`build_from_json`, native `_bfs` and `_shortest_path_text`. No clustering or semantic
extraction runs. A socket-denial guard is active. No server or network query is needed.

- **A — lexical/source:** one batched repository-wide `rg` search for named endpoints
  with four context lines, one full start-file read, one batched frontier search.
  All permitted source facts whose statements appear in those windows are eligible;
  the full-file read exposes all that file's facts. No oracle names enter the planner.
- **B — Graphify:** one structural capability request, native directed traversal/path
  calls at the query's depth, maximum eight. Raw graph edges must pass revision,
  source/symbol/relationship and security validation before traversal/competition.
- **C — combined:** the same A and B outputs, joined without additional discovery.
  C costs four requests, not one. Native library calls are recorded separately.

All conditions share typed-path assembly, canonical target deduplication, shortest-hop
then canonical-ID ordering, and whole-answer packet selection. Shared node references
include file, symbol, source line and revision. Confidence and discovery provenance
remain visible. The entire compact UTF-8 JSON, including diagnostics/partial marker,
is bounded to 2048 bytes. `exports.json` contains caller packets; raw indexes, rejected
candidates and metrics are internal research/audit material, not caller output.

The 2500-node/10000-edge guard checks the native traversal result before consumption;
it is not a preemptive CPU/memory limiter inside Graphify. No evaluated query exceeded
it. The source-validation inventory is precomputed for both conditions; graph access
does not get free authority from that inventory. Its construction/source-read costs
are recorded separately. The experiment compares a fixed reasonable lexical planner,
not optimal human planning or Graphify against every alternative static analyzer.

## Results

Numbers are required targets present in the **final packet**, not unlimited candidates.
Trap cells count correct abstentions; all other cells count required target hits.

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
| Both direct | 10/10 | 10/10 | 10/10 |
| Both multi-hop | 4/5 | 3/5 | 5/5 |
| Both impact | 18/37 | 27/37 | 26/37 |
| Both traps | 5/5 | 5/5 | 5/5 |

Unique additional targets: **B +8; C +9**. Combined adds **one on Spring, eight on
Jackson**. Counts deduplicate targets repeated across queries. Zero baseline targets
are lost by C, including all ten mandatory direct targets. B independently misses
Spring's overloaded registration call chain. Neither A nor B alone completes Jackson's
seven-hop deserialization path, but their validated fragments compose in C.

Eight multi-hop/impact queries meet the exploration reduction criterion:
S-M1, J-M1, J-M3, S-I1, S-I2, S-I3, J-I1, J-I2: three A requests versus one B request,
with equal-or-better final required coverage. This is a reduction in exploration
round trips, **not measured local wall-time improvement**. Source revalidation still
costs work. Summed local query times over each repository's ten questions:

| Repository | A | B | C |
| --- | ---: | ---: | ---: |
| Spring | 0.122 s | 0.340 s | 0.461 s |
| Jackson | 0.693 s | 1.380 s | 2.069 s |

A exposes source windows from 138/1134 file occurrences across Spring/Jackson queries;
these are not that many full-file reads or unique files. B's candidate-answer source
validation references 32/37 file occurrences; initial snapshot validation additionally
reads 354/574 package-bearing files. Latencies include per-query graph materialization;
this is not a tuned warm graph service benchmark.

All normal primary packets: **zero stale, zero forbidden, zero unsupported emitted
relations, zero oracle false positives; maximum 1995 bytes**. Some valid neighborhoods
remain partial. Combined provenance occupies more bytes: S-I1 fits six targets in C
versus seven in B. No selector adjustment was made to recover this loss relative to B.

## Extracted, inferred and uncertainty

| B raw edges | EXTRACTED | INFERRED | Source-supported EXTRACTED | Source-supported INFERRED |
| --- | ---: | ---: | ---: | ---: |
| Spring | 14307 | 786 | 4506 | 595 |
| Jackson | 38698 | 5832 | 12848 | 3999 |

[Validation evidence](evidence/validation.json) separately records unresolved nodes,
ambiguous overloads, unsupported relations, forbidden paths and valid edges by
confidence. Exclusions are conservative: they do not all prove upstream errors.
EXTRACTED also requires source validation; it is not authority. B's selected J-M3
answer uses one validated INFERRED call alongside three EXTRACTED calls. Other B
answers use EXTRACTED edges. This does not demonstrate that inferred calls uniquely
outperform the baseline: A already answers J-M3. Per-class contributions remain
separate in [summary](evidence/summary.json).

A concrete Java limitation is overload identity: Graphify merges same-name methods
into `.method()` nodes. For `createKafkaConsumer`, an INFERRED call at line 436 in the
Map overload is attached to a node located at line 339, the four-argument overload.
Treating this as a precise source fact produces an unsupported call. The normal adapter
rejects ambiguous identities; it does not repair Graphify with invented edges.

## Freshness, security and mutations

The native refresh exercised is a **full graph rebuild using the retained content
parse cache**, not incremental graph maintenance. Both A/B checkouts are real upstream
commits; source was never edited to make extraction succeed. Spring adds a KafkaAdmin
import/dependency; Jackson removes AnnotatedMethod's UnreflectHandleSupplier import and
MethodHolder structure and introduces current invocation helpers.

After proper B refresh: zero stale packet references. Validated graph deltas are
Spring +44/-0 edges and Jackson +78/-35. Source-supported deltas are +55/-0 and +109/-50,
respectively; these sets differ because extraction/resolution is incomplete. B's Spring
import packet includes the new KafkaAdmin relation but omits seven other current imports
under the byte budget; Jackson's current import packet has no missing internal import.
These are bounded-consumption misses, not stale answers. A-as-B with normal validation
returns no derived answers rather than claiming stale knowledge is current.

A fixed synthetic security overlay protects selected upstream public paths without
changing their code. In particular, the protected Spring adapter is genuinely relevant
to S-I1's neighborhood. Its raw nodes/edges never reach normal caller packets. Counts
of rejected objects remain internal; diagnostics disclose neither paths nor counts.

| Control | Observed externally | Independent checker |
| --- | --- | --- |
| A graph reused as B without validation | 16 stale node references across two packets, including Jackson's removed import relation | Exit 1 |
| INFERRED accepted as source authority | One wrong-overload call to checkBootstrap | Exit 1 |
| Optional isolation bypass | Protected candidate enters internal pool but is omitted by bounded selection | Exit 0; no emitted leak; **inconclusive** |

The optional non-killed mutation is retained honestly, not claimed as isolation proof.
Normal isolation follows the source/path/literal checks. No unsafe variant is default.
[Mutation process evidence](evidence/mutation-controls.json) includes exit/stdout/stderr;
[checks](evidence/verification.json) independently recompute source validity, targets,
bytes and thresholds rather than trusting evaluator summaries.

## Operational cost

| Cost | Spring A | Spring B cached rebuild | Jackson A | Jackson B cached rebuild |
| --- | ---: | ---: | ---: | ---: |
| Native extraction | 1.559 s | 1.010 s | 3.712 s | 2.274 s |
| Directed graph build | 0.227 s | 0.223 s | 0.589 s | 0.602 s |
| Whole collection subprocess | 3.410 s | 2.862 s | 7.081 s | 5.752 s |
| Peak RSS before source archive work | 101448 KiB | 113160 KiB | 176560 KiB | 205316 KiB |

B compact raw graph JSON is 8,684,989 bytes Spring and 21,024,857 bytes Jackson;
retained gzip sizes are 288,860 and 667,218 bytes. Native parse caches total 14,026,302
and 27,162,736 bytes after B. The built directed graphs have 4732/13724 and 10617/39161
nodes/edges. These sizes describe the experimental raw-index/cache representation;
we did not measure a deployed Graphify server or its production graph store.
All extraction subprocesses exit 0, stderr empty, zero failed sources. Whole collection
includes compression, source validation and archival work as well as native indexing.
No performance PASS threshold was invented after measurement.

## Integrity, reproduction and limitations

The first comparison completed all 60 rows, then a mutation predicate raised TypeError
because Python `and` returned None/string instead of boolean. Explicit `bool` conversion
fixed only unsafe control dispatch; primary results were retained unchanged. A checker
also accidentally demanded that the explicitly optional isolation control leak. It was
aligned with the frozen protocol; its initial FAIL report is retained. Both original
preregistered code versions, corrected hashes and reasons are in
[execution errata](evidence/execution-errata.json). Neither correction changes ranking,
queries, budgets, oracle outcomes or mandatory utility gates.

**2067 independent checks pass.** A separate integrity replay re-derives source facts
from all four retained source archives and reproduces all 60 packet/answer sets exactly
under another hash seed: **127 checks pass**. Original timing evidence is not replaced.
This proves deterministic fixture behavior, not general Java correctness.

Using the recorded Python environment (with tree-sitter Java):

```sh
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" experiments/track-iii-graphify/check.py
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" experiments/track-iii-graphify/check.py --control stale
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" experiments/track-iii-graphify/check.py --control inferred
```

The first exits 0; the latter two deliberately exit 1. Retained checking needs neither
Graphify nor Git checkouts, though `source.py` imports tree-sitter. To reproduce extraction,
use the pinned checkout locations from repositories.json/graphify.json and
`collect.py` under `PYTHONPATH=experiments/graphify-carveout/offline`; collection skips
completed artifacts. Exact child commands are retained in each invocation.json. Run
`verify_retained.py` with those checkouts and the same offline guard to reproduce
selection without overwriting primary results. `run.py` refuses completed overwrite.
The package manifest records versions; no new dependency is added to Blaine.

## Architectural conclusion

**ADAPT / ON-DEMAND.** Graphify now has evidence of incremental structural retrieval
utility, strongest for Jackson's inherited impact neighborhoods. It remains incomplete
for overloaded call chains; combined retrieval is useful, but local elapsed query time
is higher and source validation requires independent engineering. These results justify
considering bounded `workspace.structure.query/neighbors/path` behind Blaine authority,
not always-on adoption or unrestricted Graphify MCP exposure.

Source remains authoritative. Typed edges, precise identities, fresh revision binding,
security before traversal and compact evidence paths are necessary at that boundary.
This does not validate arbitrary runtime impact, optimal search, dynamic dispatch,
semantic equivalence, other languages, concurrency, update latency at scale, or a
production authentication/declassification system. Only two library repositories and
one fixed lexical planner were evaluated; corpora were not sampled randomly.

No human decision is needed to close this bounded PASS. A separately authorized final
Track III architecture consolidation should decide whether on-demand structural access
is worth its overload-resolution, freshness and validation costs, define unsupported/
partial states and ownership, and compare an integration proposal with lexical fallback.
Do not begin that consolidation or production integration under this carveout.
