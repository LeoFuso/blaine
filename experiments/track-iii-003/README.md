# Track III.3 — Memory as a continuous execution capability

**PASS — offline deterministic experiment, 2026-09-23.**

Hypothesis: one trusted ExecutionContext can govern continuous memory access across
execution participants, preserving hierarchical scope, trusted provenance, bounded
responses and distinct availability states. Initial-only retrieval cannot satisfy
later reads of observations recorded during execution.

## Foundations and implementation boundary

[III.2](../track-iii-002/README.md) remains accepted, without repeating its increment.
Its `evaluator.py` is imported **unchanged**, with the retained source digest checked
independently. There are no production imports, dependencies, network/model calls,
database, MIRIX, Restate, Completion Contracts or real workers. These Python
standard-library types are experimental, not production contracts.

The full valid topology is retained in [fixtures.json](fixtures.json):

```text
root
├── personal
│   └── project-a
│       ├── task-a1
│       │   └── work-a1
│       └── task-a2
└── employer-x
    └── project-x
        ├── task-x1
        │   └── work-x1
        └── task-x2
```

Every context initially owns a distinct literal `<context-id>-memory` observation.
Expected visibility sets are literal oracles copied from III.2, not computed by the
capability. Labels never determine behavior. Reads inherit only permitted ancestors;
ordinary writes stay at the current context. A trusted `inherit_parent=false` fixture
switch bounds lineage. **Structure is validated independently of visibility**:
a cycle behind a denied inheritance edge still prevents construction.

[capability.py](capability.py) wraps the accepted ContextTree. Trusted setup issues
an immutable ExecutionContext (`execution-iii3`, `task-a1`) and separate caller
identity tokens for human, cognition, worker and verifier. The same execution object
is used throughout the sequence. Identity registries associate each caller token
with that execution; equal-valued copies and tokens issued by another Memory object
are rejected. This is an application boundary, **not a hostile Python sandbox**.
The harness, constructors, token issuance, internals and availability switch are
trusted. Production authentication, serialized identity and transport confinement
are not implemented.

The caller-facing entry point is `handle(execution, caller, request)`, with closed
request shapes:

```json
{"op":"search","query":"literal substring"}
{"op":"get","entry_id":"root-memory"}
{"op":"recordObservation","entry_id":"new-id","content":"unverified observation"}
{"op":"declare","entry_id":"human-id","content":"explicit declaration","target_context":"project-a"}
```

Search filters permitted entries using literal substring matching, then sorts by ID
and packs whole entries. The caller cannot choose ancestors, readable scopes, caller
class or provenance. Direct-ID retrieval passes through the same lineage check.
There is no traversal API, cache, semantic ranking or initial prompt compilation.
Cache enforcement remains deferred.

## Accepted refinement before III.3: human declarations

Humans can directly declare knowledge into an authorized bounded context. This new
requirement was introduced after III.2; it was **not tested by III.1 or III.2**.
This experiment grants the trusted human token exactly one declaration target:
`project-a`. Cognition/worker observations always target `task-a1` from their binding.
The verifier is read-only. No generalized human authorization system is inferred.

A MemoryEntry has `id`, `context_id`, `content`, `provenance`, `created_by` and
`epistemic_status`. Trusted code assigns provenance and creator from the operation
and issued caller identity:

| Operation | Trusted provenance | Status | Destination |
| --- | --- | --- | --- |
| Human declaration | USER_DECLARATION | DECLARED | Fixed authorized project-a |
| Cognition/worker observation | AGENT_OBSERVATION | UNVERIFIED | Bound task-a1 |

Caller-supplied `provenance`, `source`, `created_by`, `caller_class`, `authority` and
`epistemic_status` fields are rejected before writing. A human declaration originates
at its authorized target; it does not move child knowledge and is **not promotion**.
A declaration can therefore be inherited by both tasks in project-a, while an agent
observation remains visible only at task-a1 and its descendant work-a1.

Neither provenance kind establishes authoritative truth or grants PolicyGate
permissions. Observations remain unverified even when a verifier retrieves them.
No reflection, learning admission, promotion, preference/conflict resolution or
Completion Contract evaluation happens here. Evidence remains authoritative.

## Exact continuous-access sequence

1. Human declares “Prefer constructor injection in this project.” directly at
   project-a, receiving trusted USER_DECLARATION provenance.
2. Capture the initial read after that declaration, before agent observations.
3. Cognition queries through the capability: four current/ancestor entries plus
   the declaration. It records “Hypothesis H selected for investigation.” at task-a1.
4. Worker receives the same execution binding, **no previous memory-result blob**.
   A fresh query returns those five entries plus the cognition observation. Worker
   records “Attempt A produced an observation, not verified success.” at task-a1.
5. Verifier queries through the same binding and receives all seven permitted
   entries, including both post-start observations. Forbidden descendants, siblings
   and employer-branch contents remain absent.

The operation trace retains exact requests, responses, identities, delivery mode and
UTF-8 response byte sizes. Targeted post-start reads prove both observation inheritance
to work-a1 and absence from ancestors/siblings/employer branch. Larger descendant
read sets can exceed the cap: targeted reads distinguish visibility from selection.

## Response contract and 2 KiB budget

Every response has `status`, `entries`, `partial`, `reason` and `receipt`. The budget
is **2048 bytes of the complete compact JSON envelope**, encoded as UTF-8 with
sorted keys, literal Unicode and no separator whitespace. It is not a token budget,
content-only limit or bound on the pretty-printed evidence file/transport headers.

| State | Meaning |
| --- | --- |
| SUCCESS_WITH_RESULTS | Permitted matches exist; bounded selection returned, possibly partial. |
| EMPTY | Valid available search has no permitted matching entries. |
| DENIED | Invalid binding/request, forbidden direct ID, operation or target. No content or receipt returned. |
| UNAVAILABLE | Trusted harness faults the capability; valid requests receive no content and writes have no effects. |
| RECORDED | Write-only acknowledgment; bounded metadata receipt, without content echo. |

Unknown and forbidden direct IDs share the same denial. Searching for content that
exists only outside scope yields EMPTY, not an existence disclosure. Binding and
request/role checks precede availability checks; the experiment does not promise a
universal priority ordering for all backend denials while unavailable.

Twelve permitted multibyte records overflow the budget. Stable ID order and whole
entry selection return `budget-00`, `budget-01`, `budget-02` with `partial=true`;
repetition is identical. Adding/removing a sibling's otherwise matching record
leaves the result identical: forbidden entries never become fillers or influence
selection. An oversized permitted entry returns SUCCESS_WITH_RESULTS with no entries
and `partial=true`, explicitly distinct from EMPTY. Pagination, content chunking,
semantic ranking and useful production handling of that case remain future choices.
The algorithm reserves the longer `false` spelling when packing the partial field.
Input-size limits bound query/ID/content fields; no global store/CPU bound is claimed.

## Results and controls

**394/394 checks PASS**, including per-call response bounds, all 11 exact original
visibility sets and all **121 context/entry direct-ID pairs**. Checks cover current,
ancestor, descendant, sibling, cousin and unrelated isolation; post-start write
visibility; provenance and attempted elevation; parent/sibling/unrelated write-target
forgeries; scope/ancestor parameters; cloned/foreign bindings; verifier write denial;
human wrong-target denial; faulted reads/writes and recovery; deterministic overflow;
and structure validation behind a read boundary. Maximum observed response: **1757
bytes**. The independent evidence checker passes **158 checks**.

[probe.py](probe.py) runs the same expected-value suite in isolated subprocesses:

- **Initial-only control: 2 failures, exit 1.** All sequence reads use the frozen
  initial snapshot. Worker and verifier miss the expected post-start observations.
  This proves insufficiency for this sequence, not universal superiority of live
  retrieval for every workload.
- **Forged-provenance mutation: 4 failures, exit 1.** A runner-only subclass trusts
  the caller's USER_DECLARATION field. Tests detect the incorrect receipt and
  persisted forged record through storage invariants; the control does not merely
  crash. Its later clean-store checks also expose the retained corruption.

No mutation is installed in capability.py. Correct execution runs again afterward
and produces identical full evidence. Controls do not change expected oracles.
Two fresh runs under different Python hash seeds reproduce all retained main JSON
artifacts byte for byte. Source hashes support reproducibility, not authentication.

## Evidence and reproduction

```bash
python3 experiments/track-iii-003/probe.py --output /tmp/blaine-iii3-reproduction
python3 experiments/track-iii-003/verify.py /tmp/blaine-iii3-reproduction
```

Python 3.10+; standard library only. Individual controls intentionally exit 1:

```bash
python3 experiments/track-iii-003/probe.py --variant initial-only --output /tmp/blaine-iii3-initial
python3 experiments/track-iii-003/probe.py --variant forged-provenance --output /tmp/blaine-iii3-forged
```

| Artifact | Contents |
| --- | --- |
| [fixtures.json](fixtures.json) | Hierarchy, initial records, binding/callers, literal expected sets and overflow inputs. |
| [results.json](evidence/results.json) | Every expected/actual check, operation trace, stored sequence records and byte counts. |
| [initial-only.json](evidence/initial-only.json) | Frozen-read control with identical oracles and failed later reads. |
| [forged-provenance.json](evidence/forged-provenance.json) | Unsafe runner variant, forged persisted record and failures. |
| [restored.json](evidence/restored.json) | Correct run after both isolated controls. |
| [summary.json](evidence/summary.json) | Verdict, counts, subprocess exits, source hashes and stop boundary. |
| [verification.json](evidence/verification.json) | Independent JSON consistency checks; no capability/probe imports. |
| [reproducibility.json](evidence/reproducibility.json) | Two hash-seeded runs and retained-file comparisons. |
| [documentation-checks.json](evidence/documentation-checks.json) | Local links, JSON, whitespace and change-boundary checks. |
| [request.json](request.json) | Unsubmitted TaskSpec; no runtime Task ID or lifecycle state claimed. |

## Implications, limitations and unresolved questions

The **generic tree and ExecutionContext + continuous Memory capability model survive**.
Human declarations require a distinct trusted write operation, not a separate memory
architecture. Readability does not establish verification. Continuous queries can
expose new scoped observations without rebuilding the initial context packet.
No changes to production architecture or ownership were necessary.

The proof is finite and deterministic, not distributed security or a performance
benchmark. It does not establish authentication, tenant isolation outside the modeled
surface, secret handling, policy revisions/revocation, persistence, concurrent
visibility, idempotency/retries, source authenticity, durable handoff, remote execution,
cache enforcement, retention, observational side channels or retrieval usefulness.
Harness traces deliberately contain all synthetic fixtures, including forbidden
records in negative-control evidence; they are **not a production-safe logging design**.

Open questions: how production issues/authenticates caller identities; how human
write authority is granted; conflicting declarations and observations; live versus
snapshot reads under policy revisions; lineage revocation; large-entry pagination;
trace/index/cache partitioning; provenance receipts across durable handoff. No new
human architectural decision is needed to close this bounded increment.

## Exact proposed III.4 experiment — not started

Hypothesis: a trusted security-domain binding can isolate every represented content
path, including derived representations and diagnostics, without caller-selected
scope or reliance on semantic declassification.

Use an offline synthetic harness with the same personal/employer topology and two
trusted domain bindings. Represent text, embeddings, semantic-index results, graph
nodes, context-cache entries, summaries, artifacts, tool outputs and trace/LLM-
observability events as **tagged synthetic records and fake sinks**, not real services.
Use distinct per-domain canaries and public-root records with explicit trusted policy.

1. Define a literal allow/deny matrix for each domain, context and representation;
   reject missing/unknown labels and invalid topology before any read/export.
2. Exercise scoped lookup, direct IDs, graph-neighbor expansion, stale/foreign cached
   responses and diagnostic emission. Assert exact returned and sink-written records.
3. Attempt forged domain/context/provenance labels and cross-domain derived records;
   require deterministic denial, no content leakage and no unintended sink effects.
4. Make the fake policy resolver unavailable; fail closed across all tested paths.
5. Run an isolated wrong-domain cache-key or unfiltered-trace mutation; the same
   oracle must detect the specific forbidden canary. Restore and rerun correctly.
6. Retain matrix, all paths, denial receipts, sink snapshots, control exits and hashes.

PASS requires every enumerated path to satisfy the literal matrix and the mutation
to fail. This would prove a bounded isolation contract, not real vector/index/log
product security. No real secrets, providers, production integration, promotion or
declassification; III.5 remains separate. **III.4 requires explicit authorization
and has not started.**
