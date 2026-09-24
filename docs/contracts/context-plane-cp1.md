# Context Plane CP.1 executable subset

This is the opt-in local implementation of [ADR 0025](../decisions/0025-context-plane-and-compiled-agent-context.md),
under the [semantic contract](context-plane.md). It does not replace that contract.
The [milestone](../milestones/055-context-plane-cp1.md) owns measured acceptance and limitations.

## Deployment and trusted binding

The application supplies `ContextPlane(store, LocalContextAuthority(current,
principal=...), MemoryFacade(...))` to `Capabilities(context_plane=..., worker=GooseWorker(...))`
and then uses the existing `create_workflow`. Default constructors remain unchanged.
Keep this option stable for an invocation's lifetime, like other journal-producing
deployment options. This is a hosted, single-principal local route; public ACP
TaskRequest, child/remote intake, legacy ContextProviders and escalation are excluded.
The integration fixture demonstrates the exact assembly in
[`probe_app.py`](../../experiments/context-plane-cp1/probe_app.py).

`current(task_id)` is trusted application code that selects a coherent configured
snapshot. It is not a worker hook. Unknown mappings deny. A snapshot is a closed
`{version:1, kind:"LocalContextBinding", payload:{...}}` with these required fields:

| Fields | Trusted meaning |
| --- | --- |
| `task_id`, `spec_ref`, `principal`, `route` | Existing Task, exact normalized accepted TaskSpec artifact, deployment principal and literal `hosted-local`. All must match. |
| `revision`, `nodes`, `context` | Immutable configured revision, complete bounded tree of `{id,parent,kind}`, current node. All branches validate; kind does not affect visibility. |
| `security_domains`, `policy_domains`, `readable_contexts` | Independent trusted visibility and policy sets. Memory reads intersect these with current/permitted-ancestor lineage. `shared` has no magic meaning: explicit membership is necessary. |
| `workspace_root`, `workspace_paths` | Canonical absolute local root and exact relative resource grants selected by the application after its resource policy. These are independent of Memory lineage, never inferred from filesystem parents. No wildcard grant, traversal, directory enumeration or symlink following. |
| `evidence_refs` | Explicit exact Task-scoped evidence grants, additionally intersected with runtime-admitted artifacts. |
| `memory_entries` | Trusted `{id,context,domain,origin,status,revision,sha256}` metadata. IDs are unique within this configured corpus. Only `USER_DECLARATION/DECLARED` and `AGENT_OBSERVATION/UNVERIFIED` are supported. |
| `initial_need`, `memory_query` | Initial ContextRequest and optional lexical Memory need selected by deployment. `null` disables optional Memory lookup. |

Configuration has the existing 16,384-byte envelope limit, at most 128 nodes,
32 exact workspace paths and 32 Memory entries. It is deployment input, not a mutable
registry, Task ledger or new storage product. Current snapshots are retained privately
in the existing immutable ArtifactStore. A private v1 `ExecutionContextRef` associates
`task_id`, `operation_id` and `binding_ref`; receivers always resolve current application
state. They never load an old snapshot as a grant. `TaskState.context_ref` continues to
name the CognitiveTurn artifact.

This is an application trust boundary, not a sandbox against malicious trusted Python
code. No concurrent administrative mutation within an operation is supported. A changed
binding detected during compilation or before new physical delivery refuses that delivery.
It does not rewrite a committed journal slot. A newly admitted context request can resolve
the new binding; if it was not already admitted and cognition would require stale context,
the bounded workflow stops safely. Automatic recovery/rebinding is outside CP.1.

## Information need and routing

`context.request` is an existing `INVOKE_CAPABILITY` operation under PolicyGate's current
Task capability intersection. It is not a sixth action and does not redefine `add-context`.
Its input is a closed v1 `ContextRequest` envelope:

```json
{"version":1,"kind":"ContextRequest","payload":{"question":"Read the current exact contract","form":"exact-source","locator":"contract.py","base_ref":"artifact://TASK/sha256:DIGEST"}}
```

| Field | Bound |
| --- | --- |
| `question` | Required, nonblank, at most 256 UTF-8 bytes. |
| `form` | Required information form: `exact-source`, `lexical-source`, `current-evidence`, `prior-context`. Runtime selects the provider. |
| `locator` | Optional narrowing hint, at most 256 bytes; required for exact source and evidence. A hidden/unknown ungranted locator has the same DENIED response. |
| `exact` | Optional material literal, at most 256 bytes; required for lexical source and disallowed for prior-context. Missing required literal cannot produce a sufficient packet. |
| `base_ref` | Required by the one delta integration, at most 256 bytes, must match the independently held initial admission. Not allowed in the initial need. |
| `max_bytes` | Optional integer 256..4096; only narrows the active packet and delta ceilings. |

The entire request must fit 1,024 bytes. Scope, domain, backend, credentials, provenance,
projector, receipt and other unknown fields reject. Source reads are confined exact reads
or deterministic literal search over the granted file list. CP.1 preserves whole files
up to a 16,384-byte read ceiling, then applies the smaller recipient limit; it does not
invent a truncated excerpt of a material contract. Large exact requirements explicitly
fail as insufficient. Evidence requires both current resource grant and admitted Task
artifact membership. No semantic/index/graph routing exists.

The read-only Blaine `MemoryFacade.search/retrieve` filters IDs from trusted metadata
before provider processing, then validates exact returned IDs, content digests and closed
row shape. The only qualified CP.1 transport is `ReadOnlyCorpus`, an in-process,
deployment-owned corpus with no global search/statistics, network, embedding or logging.
Unknown metadata, unexpected rows, changed content or provider errors fail safely.
Legacy MIRIX headers/tags cannot qualify it; live MIRIX stays disabled on this path.
Optional Memory unavailability is explicit and does not suppress valid current source.

## Compilation, admission and delivery

Resolver emits internal candidates; Compiler revalidates permission/freshness before
selection. Mandatory objective, exact completion criteria, accepted constraints and
required exact source/evidence precede optional Memory. No LLM summary or ranking occurs.
Current source and artifact bytes have narrowly stated provenance; historical Memory is
qualified and explicitly not completion evidence or authority.

The existing WorkerInput v1 shape remains unchanged: Task ID, objective, up to four
`{source,content}` entries; 4,096 total encoded UTF-8 bytes; source 256 bytes; content
2,048 bytes. Structured requirements/provenance are rendered as compact JSON in those
existing content fields. Compiler validation never relaxes the worker validator.
Metrics include eligible candidates/bytes considered, selected candidates/bytes,
whole-envelope output bytes, limit, partial status and `truncated:false`.

The owning workflow journals a **private admission**, including Task, compilation
operation, exact packet digest/ref, accepted spec, current binding fingerprint, selected
source versions and retained snapshot ref. It does not put this admission in the public
artifact map or accept one from a caller. The initial compile uses the existing Task
identity plus `context-initial` step; the delta uses the admitted decision/operation ID.
`worker.run` receives the independently held admission via a trusted Python argument,
checks the current dispatch operation, exact packet digest, current binding and all
selected source bytes immediately before delivery. A same-shaped model-authored artifact,
caller receipt or successful PolicyGate decision alone cannot satisfy these checks.

The first bounded worker observation permits exactly one successful context request.
The request re-resolves current authority and sources, writes a bounded v1 ContextDelta
and compiles a replacement active WorkerInput. No old worker result, prior source text or
transcript is concatenated. A second delta and duplicate successful packet dispatch deny.
Failures remain bounded by the existing loop/step limits. Goose remains one-shot and
tool-free; this is an owned-loop capability between processes, not a mid-call Goose tool.

ContextDelta carries `base_ref`, compilation `operation`, `replaces:"all-context"`,
`active_ref`, freshly compiled `context`, `status`, `limit_bytes`, `output_bytes`.
Both delta and active WorkerInput independently fit 4,096 bytes, including metadata.
The capability result contains only safe refs/status/metrics and fits 4,096 bytes;
CognitiveTurn retains its 16,384-byte bound. The 2 KiB research constant is not used.

Failures use the existing CapabilityResult `failure` with a safe `output.status`:
DENIED, UNAVAILABLE, INVALID_CONTEXT, STALE, EMPTY or INSUFFICIENT_CONTEXT. No partial
source content accompanies a failed required lookup. Optional unavailability may instead
yield partial SUCCESS. Empty lookup does not establish global absence. Raw artifact reads
are refused on this opt-in context path; fresh context/evidence goes through the Resolver.
The independent exact-artifact CompletionEvaluation is unchanged.

## Retained boundaries

No change to legacy MIRIX, frontier exact-byte authorization, D2 workspace initial-action
authorization, remote consent, child results or default worker execution. General Restate
kill/resume/revocation races remain CP.8. Remote propagation remains CP.9. Production writes,
learned admission, promotion, declassification, semantic search and Graphify are absent.
Implementation acceptance does not enable this slice in an existing hosted deployment;
deployment still requires explicit review of the retained evidence.
