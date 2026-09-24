# Track III.4 — Bounded security context isolation

**PASS — offline deterministic experiment, 2026-09-23.**

Hypothesis: structural lineage intersected with trusted security-domain visibility
and explicit policy can govern every supported memory access path, including
synthetic derived representations, graph relationships, cached results and diagnostics.
Shared ancestry, human provenance and knowledge of an ID cannot supply authority.

## Foundations and bounded implementation

The accepted [III.2 tree](../track-iii-002/README.md) and [III.3 continuous
capability](../track-iii-003/README.md) remain foundations, not increments rerun here.
[security.py](security.py) imports III.3's experimental Memory/ExecutionContext/Caller,
which imports III.2's ContextTree. Both prior source files are byte-identical to the
accepted versions, with hashes independently checked. Tree validation still checks
all structure before reads; a cycle hidden behind a denied inheritance edge rejects
construction. Labels never grant authority, including relabeling all nodes `trusted`.

This is a Python standard-library, single-process evaluator. Trusted fixture loading,
identity issuance, internals and fault switches are outside its caller surface.
It is not a hostile-code sandbox or production authentication implementation. There
are no new dependencies, real models, workers, services, databases, embeddings,
MIRIX, Graphify, Claude Context or production runtime imports/integration.

## Topology, classification and effective visibility

[fixtures.json](fixtures.json) retains the exact nine-node tree:

```text
root
├── personal
│   └── project-personal
│       ├── task-personal-a
│       └── task-personal-b
└── employer-x
    └── project-x
        ├── task-x-a
        └── task-x-b
```

The two private domains are **personal** and **employer-x**. `public` is an explicit
shared classification/realm, not a third employer. Context-to-domain assignments
are trusted metadata separate from node labels and parent edges. Each issued
ExecutionContext is registered with its domain; callers cannot submit a domain.
The experiment captures that binding and rejects contradictory later metadata;
this is a fault case, not an implemented revocation protocol.

There are 12 initial raw entries and 24 synthetic derived records. The root contains:

- `global-engineering-memory`, explicitly PUBLIC/public and readable under each
  fixture domain's public grant.
- `personal-root-private` and `x-root-private`, deliberately PRIVATE and domain-bound.
- `x-policy-denied`, domain employer-x but explicitly denied by policy.

**Private root entries are defensive stress fixtures**, not promotion or permission
to write private material into a global context. They prove that even if private
records are structurally ancestral to everyone, security classification still
blocks disclosure. Their ownership is explicit trusted setup. Ordinary writes
cannot create public records or target root. This does not relax the research's
recommendation that a shared root contain only shareable operational knowledge.

Every other context has a distinct domain-private literal record. Protected strings
include synthetic internal host, class, ticket, table and repository identifiers.
No real organization, repository, credentials or proprietary data are used.

For raw entry E and issued binding C:

```text
readable(E, C) =
    E.context_id in permitted_lineage(C)
    AND E.domain in trusted_policy.grants[bound_domain(C)]
    AND E.id not in trusted_policy.deny_ids
```

PUBLIC requires domain public; PRIVATE requires a known private domain. Unknown or
contradictory classification is invalid, not a default-public record. All topology
is validated independently of these filters. Policy grants are a small closed
fixture schema: a domain may permit itself and/or public, never another private
domain. This is not a general PolicyGate implementation or policy authoring language.
Removing the public grant demonstrably suppresses otherwise ancestral public data.
A trusted closed inheritance edge still excludes ancestors even when their domain
would be allowed.

Literal expected sets cover each context and all **324 context/object direct-ID
pairs** (9 contexts × 36 initial objects). Effective sets preserve same-domain
ancestors while excluding descendants, siblings and unrelated branches. Root is
not an aggregate view. Knowing an ID does not widen lineage or domain authority.

## Caller surface and continuous provenance

`exchange(execution, caller, request)` returns a response plus a small diagnostic
projection. Its closed request shapes accept:

```json
{"op":"search","kind":"RAW","query":"literal substring"}
{"op":"get","id":"global-engineering-memory"}
{"op":"neighbors","id":"global-node"}
{"op":"cached","query":"cached-query"}
{"op":"debug"}
{"op":"recordObservation","id":"local-key","content":"unverified observation"}
{"op":"declare","id":"local-key","content":"human declaration","target_context":"project-x"}
```

Search accepts RAW or one of the documented synthetic representation kinds. Unknown
operations/fields are denied. Domain, security_domain, classification, kind metadata,
source, provenance, creator, context, scopes and policy forgeries cannot grant access.
Copied execution/caller objects and tokens issued by another capability are rejected.

For each private domain, one execution binding travels through human, cognition,
worker and verifier. A trusted human declares at its one fixed project target.
Cognition records a local observation; worker queries afresh, sees it and records
another; verifier retrieves both and the human declaration. No memory-result handoff
blob is used. Agent writes remain current-context PRIVATE/AGENT_OBSERVATION/UNVERIFIED.
The human path assigns PRIVATE/USER_DECLARATION/DECLARED at the authorized project;
it is not child-to-parent promotion and does not grant global visibility or truth.
Human wrong-target requests, agent declarations and verifier writes are denied.
Later reads at every context prove inheritance of declarations to both project tasks,
and absence of local observations from parents, siblings and the other domain.

**Write IDs are destination-scoped**: the request ID is a local key, and stored ID
is `<trusted-target>::<local-key>`. Fixture IDs reserve this separator. This small
experimental API refinement avoids a global collision oracle: writing a key identical
to a hidden foreign record cannot reveal whether that foreign record exists. The
paired test uses the explicitly public/caller-known `opaque-collision-key` identifier
with a protected payload, then removes the hidden record. Both writes produce
identical local receipts. No protected content or source metadata is copied. This
is not a production identifier design; sensitive direct-lookup IDs remain in the
literal leakage manifest and are never echoed by denials.

## Derived representations and graph boundary

Derived records carry source IDs and literal stub payloads, not independently
selectable public/private labels. They are readable **only when every source entry
is readable**. Source IDs, payload, provenance references and graph endpoints are
returned only after this check. Missing sources or inconsistent graph endpoint
source sets reject construction. No source content is transformed or declassified.

Kinds: SUMMARY, EMBEDDING_STUB, SEMANTIC_INDEX_STUB, GRAPH_NODE, GRAPH_EDGE,
ARTIFACT_STUB and TOOL_OUTPUT_STUB. These represent enforcement contracts, not real
indexes, embeddings, graphs or tools. Reads and direct IDs cover every kind.

The graph contains same-domain edges, a personal-visible node linked to an
employer-protected node, and a global node linked to an employer-protected node.
An edge depends on the union of its endpoints' sources. One-hop neighbor queries
return only permitted edges and endpoints. The mixed personal/employer edge is
unreadable from either single-domain binding. A personal caller sees no edge,
endpoint ID or count from the global-to-employer relationship; employer work can
read that relationship legitimately. Multi-hop traversal is not an exposed API.

## Synthetic cache, diagnostics and policy faults

The cache is a list of fixture envelopes containing query, context, domain, policy
version, content revision and result IDs. No production cache, worker, TTL or store
is built. Lookup selects by query **and context/domain/policy**, checks revision,
and reauthorizes every referenced raw/derived object before packing it. A foreign
or sibling binding finds no matching fixture and gets EMPTY. A matching envelope
with foreign contents or stale revision gets DENIED. Unavailable policy never
falls back to cached contents or structural ancestry.

The append-only fixture revision counts only post-setup writes readable by that
binding. Foreign-domain and sibling writes leave the cached response unchanged;
a visible current-context write invalidates the old fixture. A global revision
counter would leak unrelated activity through stale-cache status. This is not a
production freshness, deletion, revocation or anti-rollback protocol.

Responses retain III.3's complete compact UTF-8 JSON budget of **2048 bytes**; maximum
observed here is **1441 bytes**. Whole-entry selection and partial indication are
inherited unchanged. III.3's overflow experiment is not repeated. Diagnostics are
a separate fixed projection of status, returned count and partial flag. They do
not contain request text, requested IDs, paths, raw cache contents or errors.
`debug` counts only permitted raw and derived records, not global index totals.

| State | Interpretation |
| --- | --- |
| SUCCESS_WITH_RESULTS | Authorized selected records or scoped debug counts. |
| EMPTY | No permitted matches, neighbors or matching scoped cache fixture. |
| DENIED | Unauthorized/invalid request, unknown or hidden direct ID, invalid policy/binding, stale/unsafe cache envelope. |
| UNAVAILABLE | Policy unavailable or capability intentionally faulted. |
| RECORDED | Authorized write receipt with trusted provenance and destination. |

Denials and unavailability return no records, receipt or identifying reason detail.
The distinct statuses are sufficient for this experiment without exposing private
identifiers. Normal reads, direct IDs, graph neighbors, cache, debug and both write
paths are exercised under **11 policy/binding faults**: unavailable policy, malformed
policy, unknown grant, contradictory cross-domain grant, missing/unknown/malformed
context domain, contradictory issued binding, contradictory classification, and
missing/unknown entry domain. All fail closed; faulted writes leave storage unchanged.

Paired full/reduced-store checks remove hidden records and relationships. Debug
counts, forbidden direct lookup, protected-content search and graph results remain
identical. Thus tested counts/enumeration and denial behavior do not reveal whether
that hidden data exists. Timing, traffic shape and real external logs remain outside
this finite experiment.

## Literal oracle, controls and results

**1259/1259 checks PASS.** Independent JSON verification: **1335 checks PASS**.
All **618 caller-visible output bundles** (response plus diagnostic) pass literal
scanning: **zero protected cross-domain literal hits**. The [literal manifest](fixtures.json)
includes protected IDs, payload canaries and provenance creator strings. Public
outputs are scanned against both private domains; each private audience is scanned
against the other. Compact and pretty JSON exports are scanned; the independent
verifier recomputes matches without importing the implementation or runner.

[evidence/observables.json](evidence/observables.json) is the complete per-audience
external-result export. The full test report additionally holds trusted harness
fixtures, attacker requests, expected values and deliberate mutant leaks. Those
mixed-domain administrative artifacts are **not caller-visible projections** and
must not be treated as production-safe telemetry. The scanner does not pretend a
file deliberately containing both domains' test inputs is itself domain-isolated.

The unchanged-oracle suite runs in isolated subprocesses under two runner-only
mutations:

| Mutation | Detected result |
| --- | --- |
| Structural-only reads ignore domain grants | **177 failed checks**, **165 leaking output bundles**, exit **1**. In particular personal gets x-root-private through shared ancestry. |
| Cache lookup uses query alone and skips binding/source reauthorization | **6 failed checks**, **2 leaking output bundles**, exit **1**. Foreign/forged cache contents leak; sibling reuse, staleness and visible-write invalidation also violate contract. |

These controls fail through actual forbidden payloads and the independent literal
oracle, not crashes. Neither unsafe variant is installed in security.py. Correct
execution afterward matches its first result exactly. Two fresh hash-seeded runs
reproduce retained primary evidence byte for byte. Hashes support reproducibility,
not authenticity, policy signatures or formal proof.

## Evidence and reproduction

Python 3.10+, standard library only, from repository root:

```bash
python3 experiments/track-iii-004/probe.py --output /tmp/blaine-iii4-reproduction
python3 experiments/track-iii-004/verify.py /tmp/blaine-iii4-reproduction
```

Individual controls intentionally exit 1:

```bash
python3 experiments/track-iii-004/probe.py --variant structural-only --output /tmp/blaine-iii4-structural
python3 experiments/track-iii-004/probe.py --variant query-only-cache --output /tmp/blaine-iii4-cache
```

| Artifact | Evidence |
| --- | --- |
| [fixtures.json](fixtures.json) | Topology, domains/policy, protected literals, global entry, derived sources, expected visibility and collision fixture. |
| [results.json](evidence/results.json) | Expected/actual checks, actual visibility matrix, requests, responses, diagnostics, binding identities and final scoped writes. |
| [observables.json](evidence/observables.json) | Complete audience-separated response/diagnostic exports. |
| [literal-leakage.json](evidence/literal-leakage.json) | Literal oracle verdict and scanned-output count. |
| [structural-only.json](evidence/structural-only.json), [query-only-cache.json](evidence/query-only-cache.json) | Same oracles under unsafe variants, retained payload leaks and scan findings. |
| [restored.json](evidence/restored.json), [summary.json](evidence/summary.json) | Correct restoration, subprocess exits, source hashes and final stop boundary. |
| [verification.json](evidence/verification.json), [reproducibility.json](evidence/reproducibility.json) | Independent verification and byte comparisons. |
| [documentation-checks.json](evidence/documentation-checks.json) | Local documentation, source-import and changed-file checks. |
| [request.json](request.json) | Unsubmitted TaskSpec; no runtime Task identity/state claimed. |

## Implications, limitations and unresolved questions

**ContextNode + continuous Memory + trusted SecurityContext survives conceptually
unchanged.** Effective access needs explicit domain/policy intersection at each
supported path, not a special memory hierarchy per workload or a change to lifecycle.
Human provenance and unverified status are orthogonal to security. Ordinary writes
remain local; promotion/declassification remain absent. The local-key namespace and
visibility-scoped fixture revision address identifier collision and cache-invalidation metadata side channels without changing production
contracts.

No production Cognitive Loop, PolicyGate, Completion Contract, Restate, routing,
worker, D1/D2 or remote-execution behavior changed. No preference system, retention,
revocation, reflection, lessons, secret scanner or semantic abstraction was built.

The finite proof covers enumerated synthetic representations and trusted source
attribution. It does not establish isolation in real MIRIX/index/embedding/graph
providers, mixed-source attribution completeness, external diagnostic infrastructure,
side channels outside returned metadata, hostile code confinement, authentication,
persistence, concurrency, replay, retention, revocation or distributed binding safety.
A malicious trusted loader that mislabels private text as public is outside this
model; payload meaning is not classified semantically. Filtering after a real
external provider has already received raw content would be too late.

Open decisions: production label authority and cryptographic binding; explicit
multi-domain permissions; derivation/source completeness; provider egress checks;
safe observability sinks; policy versions across resume; identifier namespaces;
revocation/invalidation; and human authorization/declaration conflicts. None requires
a human architectural decision to accept this bounded increment.

## Exact proposed III.5 experiment — not started

Hypothesis: explicit promotion admission can be fail-closed and auditable for a
bounded synthetic corpus, without treating a clean scan or model assertion as proof
of safe cross-domain abstraction.

1. Keep the synthetic tree/domains. Prepare candidate child-to-parent records with
   literal source/destination, trusted provenance, policy and approval fixtures.
   Separate same-domain promotion from cross-domain declassification; human direct
   declaration remains a different operation.
2. Use **hand-authored synthetic abstraction candidates**, including safe general
   lessons, raw copies, near-copies and hidden identifiers in content/provenance.
   Include synthetic host/repository/ticket/class/package identifiers and secret-like
   test tokens, never real secrets. Do not rely on a live LLM for the oracle.
3. Evaluate a proposed admission gate against literal outcomes: destination authority,
   complete source provenance, required deterministic scanner results and explicit
   declassification approval. Uncertain abstraction, unknown policy, missing evidence,
   unavailable scanners and forged approval must reject without destination writes.
4. Check source-private provenance stays private; destinations receive only an
   authorized opaque receipt and approved generalized content. Verify exact source
   and destination snapshots and no implicit ordinary-write promotion.
5. Inject an isolated fail-open or missing-provenance-scanner mutation; unchanged
   oracles and destination leakage scans must fail. Restore correct execution.
6. Retain corpus, decisions, gate/scanner versions, bounded receipts, before/after
   state, literal leakage scans and control exits. PASS would establish only this
   finite admission protocol, not general semantic declassification correctness.

No runtime/model/backend adoption is implied. **III.5 is not started and requires
explicit authorization.**
