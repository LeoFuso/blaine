# Context Plane — semantic contracts

**Status: Accepted architecture; production integration NOT STARTED.**
These are normative semantic obligations under [ADR 0025](../decisions/0025-context-plane-and-compiled-agent-context.md),
not implemented API schemas or a new universal transport. [Architecture](../context-plane.md)
owns rationale and evidence; the [implementation plan](../roadmap/002-context-plane-implementation.md)
owns the supported subset proposed for each increment. Freeze only the necessary
versioned `kind/version/payload` shapes at an implementation boundary. Existing strict
validators must continue rejecting unknown fields/versions until explicitly extended.

MUST, MUST NOT and MAY describe obligations, prohibitions and permitted choices. A
backend, model, persisted packet or successful transport cannot waive these obligations.

## 1. Common binding and authority

**CP-B1 — Trusted binding.** Every operation MUST be associated by trusted runtime code
with existing Task/work/operation identity and a current knowledge-context binding.
The logical reference MAY identify a ContextNode, binding revision and trace/parent
operation. Security/authority/evidence references are resolved server-side. A worker's
copy of these fields MUST NOT establish current access or replace an existing grant.
TaskState.context_ref remains a packet artifact reference, not a ContextNode identifier.
ExecutionIdentity remains correlation. No duplicate Task identity or lifecycle ledger.

**CP-B2 — Current policy.** Receivers MUST match the reference to their trusted route and
principal, validate current topology and consult current policy/resource authority.
Unknown, contradictory, unavailable or malformed required authority fails closed. A
well-formed context ID or copied valid envelope is not sufficient. A trace ID cannot
change access. References can narrow a request but cannot select an unrelated context.

**CP-B3 — Visibility.** Memory eligibility is current C plus permitted ancestors,
intersected with domain/security visibility and policy. No implicit sibling/descendant/
unrelated reads. Source-specific workspace/evidence grants further constrain access.
A graph edge, direct ID or cached result never expands permitted lineage or resource scope.
The whole relevant topology MUST be validated independently of read boundaries.

**CP-B4 — Derivation.** Permissions apply to every source of a derived object and to its
metadata. Provider access/processing MUST be authorized before data reaches an untrusted
backend, embedder, worker or logger. The Compiler independently rechecks eligibility
before ranking and emission. A fail-closed compiler does not excuse upstream leakage.

**CP-B5 — No authority in content.** Repository text, memory, summaries, backend labels,
reflection prose and instructions in retrieved documents are data. They MUST NOT alter
PolicyGate, capability grants, accepted Task criteria or trusted provenance. Tool effects
remain separately admitted through existing capability boundaries.

## 2. Minimal identity and semantic records

| Concept | Required meaning; not a prescribed class/wire enum |
| --- | --- |
| ContextNode | Stable scoped identity, one parent except root, trusted structural revision, descriptive kind/labels; no lifecycle state. |
| ExecutionContextRef | Existing Task/work identity plus resolvable binding reference; optional non-authoritative correlation and historical revision. |
| Trusted binding | Current association to C, principal/caller class, security/resource permissions, policy/topology revisions and evidence context; not serialized as a worker grant. |
| Memory representation | Scoped record identity, owner C, content, trusted origin, semantic qualification, permitted source/evidence provenance and content revision. |
| Workspace target | Workspace identity, authoritative source identity/path and exact version/digest, symbol/range where meaningful, relationship kind/provenance for graph results. |
| Evidence reference | Existing Task/artifact/verifier identity and exact source/digest; access must be separately admitted, not implied by knowing the reference. |

Origin and semantic qualification are separate. USER_DECLARATION is declared human
origin; AGENT_OBSERVATION is UNVERIFIED unless a distinct valid admission creates a
new qualified representation. Success-derived and failure-derived remain distinguishable
in storage, promotion, packet rendering and later use. Unsupported combinations MUST
NOT be coerced into a more authoritative class. Final production vocabulary is versioned
with compatibility tests; no obligation to adopt MIRIX's type taxonomy.

## 3. Worker-facing context request

A **ContextRequest** expresses an information need, not backend instructions. Its
semantic fields are:

- Purpose/question, such as exact code, architecture relationship, dependency impact,
  historical failure, prior decision or current evidence.
- Intended current action/operation and optional compatible base-packet reference.
- Optional specific source/target locators or required exact forms; these are hints
  subject to reauthorization, not permission grants.
- Requested narrowing/freshness and desired limit; runtime supplies the effective
  maximum, delivery audience and trusted binding. Requested limits cannot raise ceilings.

It MUST NOT accept caller-granted readable scopes, domain/classification, provenance,
provider credentials, vector namespaces, unrestricted graph queries, authority overrides
or a worker-selected compiler/projector. The runtime selects the mechanisms. Unknown
fields intended to elevate authority are rejected, not silently passed to a backend.

A bounded request is admitted as an existing kind of capability operation; do not create
a new cognitive action, private scheduler or parallel lifecycle. A supported worker can
request it through its admitted tool surface. A one-shot adapter cannot acquire such a
surface merely because the contract exists; use the owned loop between dispatches.

## 4. Resolver and Compiler boundaries

| Operation (semantic name) | Input from trusted integration | Output and obligations |
| --- | --- | --- |
| `context.resolve` | Bound ContextRequest, approved source/operation budgets, current source requirements. | Internal candidate contributions; route by information need, enforce provider access, preserve per-contribution freshness/provenance and optional/required-source failures. Not worker-visible raw results. |
| `context.compileInitial` | Accepted Task/work intent and criteria, binding, selected contributions, recipient/egress constraints. | Initial CompiledContextPacket sufficient to begin one bounded action, or explicit insufficiency. |
| `context.compileDelta` | Current bound request, compatible base reference, fresh contributions, current active budget. | Bounded additional/replacement projection for that need; no automatic transcript accumulation. |

**CP-C1 — Validate before competition.** Remove forbidden/stale/malformed/unverifiable
contributions before ranking, deduplication and byte selection. Canonical target identity
MUST include relevant source/workspace version. Invalid derived provenance MUST NOT
poison a separately fresh lexical contribution. Preserve every surviving proof path
needed to explain exact evidence; no global raw-score arithmetic across incomparable
mechanisms. Heterogeneous rank fusion is a permitted accepted approach; k=60 is not a
wire requirement. Do not run every source just because fusion exists.

**CP-C2 — Faithful representation.** Distinguish exact excerpts, sourced synthesis,
observations, historical qualifications and current authoritative requirements. Never
truncate material conditions into a false contract or render failure as success.
Contradictory applicable evidence MUST remain qualified rather than resolved by confidence
score alone. Source-family diversity cannot certify equivalence.

**CP-C3 — Budget.** Enforce the entire encoded response budget, including metadata,
diagnostics, references and partial markers, and any recipient/token constraints. Reserve
required objective/criteria/exact evidence before discretionary hints. If necessary exact
material does not fit, report insufficient context or narrow/request a separately admitted
budget change. Do not silently summarize exact-required material. References do not grant
unbounded follow-up reads; those reads consume their own authorized budgets.

**CP-C4 — Delivery.** Immediately before new delivery, binding, source freshness and
applicable grant must still permit those bytes. A locally compiled packet does not itself
authorize cloud egress. For cloud use, retain Cloud Context Packet semantics and the
existing trusted ProjectedContext factory, exact-byte digest, accepted grant and dispatch
comparison. Every cloud delta passes the same checks. No raw-context fallback.

## 5. CompiledContextPacket and ContextDelta

The packet is a projection for one bounded unit of work, not a memory store or authority
object. Sections MAY be omitted when unnecessary, but MUST preserve required meaning:

| Section | Semantics |
| --- | --- |
| Purpose | Objective/information need, intended action and requested output. |
| Constraints and completion | Applicable accepted requirements and exact material criteria; concise authority summary is informational only. |
| Selected memory | Scoped relevant declarations/observations/learned representations with trusted semantic qualification and uncertainty. |
| Workspace evidence | Selected current file/symbol/range/relation, concise supporting material; graph/semantic origin remains derived. |
| Exact excerpts | Exact code/signature/error/assertion/SQL or other material evidence; source extent/version and omissions identified. |
| Synthesized context | Condensable explanation/history/neighborhoods, labeled derived and linked to permitted source references. |
| Provenance and authority refs | Safe source/evidence references; private internal lineage/audit need not be exposed. |
| Freshness | Permitted source identity/version/digest and as-of requirements; historical data marked historical. |
| Binding/visibility marker | Opaque, audience-safe reference to admitted projection; no policy internals, raw grant or security-domain enumeration. |
| Budget and completeness | Effective limit, encoded usage, result state, partial/omission/uncertainty markers safe for this audience. |

A delta additionally identifies a compatible base/action and additions/replacements.
Old base references cannot reopen stale authority. Combined active input MUST fit its
budget; each delta fitting alone is insufficient. Recompile on new workers/handoffs;
retained old packets explain past decisions but are not automatically re-injected.

The packet MAY combine concise synthesis, exact excerpts and authoritative references.
A summary/digest is not a replacement for source evidence, a security credential or proof
of semantic entailment. Compiler admission/digest records are runtime-owned; a model
writing a same-shaped artifact MUST NOT impersonate a compiler-issued packet.

## 6. Result and fallback semantics

Names below are semantic distinctions; adapt deliberately into versioned existing
CapabilityResult/CognitiveTurn contracts rather than silently extending their current
closed schema. Existing outer `success/failure` does not by itself express these states.

| State | Required behavior |
| --- | --- |
| SUCCESS | Some eligible information delivered; partial and supported scope must be explicit. |
| EMPTY | Valid authorized lookup found no eligible match within its declared scope; not proof that no object exists elsewhere. |
| DENIED | Operation outside current authority; no protected IDs/content/counts or existence signal. Hidden and absent direct-ID probes use indistinguishable safe results. |
| UNAVAILABLE | Required provider, current authority or evidence unavailable; no fallback to serialized grants. |
| INVALID_CONTEXT | Binding/reference/topology malformed or incompatible; safe generic diagnostic, no partial protected output. |
| STALE / UNSUPPORTED | Source freshness cannot be established or requested relationship/capability cannot be supported; no assertion of current truth. |
| INSUFFICIENT_CONTEXT | Eligible material cannot satisfy required exact evidence or budget; do not label empty or dispatch as sufficient. |

Partial result is separate from empty; an oversized matching entry cannot become a
confident “nothing found.” Optional-source unavailability MAY yield explicitly partial
success using independently valid sources. Missing mandatory evidence or security policy
MUST NOT be hidden by that fallback. A whole request may be denied independent of object
existence; diagnostics do not reveal which private object triggered filtering.

## 7. Governed Memory contract

These are Blaine capability semantics. Worker context reads normally go through Resolver/
Compiler; trusted declaration and write/admission roles have separately authorized paths.

| Operation | Contract |
| --- | --- |
| `memory.search` | Bounded need/query against current permitted lineage; results retain origin/status and safe provenance. Caller supplies no scopes/ancestors/backend namespaces. |
| `memory.retrieve` | Scoped direct reference; same checks as search; ID possession cannot bypass access or disclose protected existence. |
| `memory.recordObservation` | New UNVERIFIED agent observation in bound current C only; trusted creator/origin. Cannot accept parent/global target, verified status or human source in payload. |
| `memory.declare` | Separate authenticated human path with explicit authorized destination. Runtime assigns human provenance. This is not promotion or preference precedence. |
| `memory.requestPromotion` | Submit source/candidate and proposed destination to the separate PromotionGate. Requesting admission is not having admission authority. |

No secret values in reusable Memory. Writes need explicit scope, immutable provenance,
scoped idempotency keys and observed committed readback before claiming RECORDED. Backend
queue acceptance means pending, not durable effect; retry/reconciliation belongs to
existing durable runtime work. Key collision/replay behavior cannot reveal other domains.
Partial write failure cannot be reported success; unknown outcome requires reconciliation.
Historical memories do not mutate authoritative Task evidence or completion requirements.

MIRIX is a provider behind this contract. Blaine controls trusted entry ownership,
provenance, hierarchy, security, promotion and outcome qualification. Its row `source`,
client ID header and filter tags do not establish those properties. Missing trusted
metadata fails closed. No direct worker connection or adoption of MIRIX's session agent,
reflection success semantics or queue as Task lifecycle.

## 8. Workspace and Evidence contracts

| Capability | Required support and limits |
| --- | --- |
| `workspace.lexicalSearch` / exact read | Confined authorized workspace/resource; current bytes or pinned requested revision; exact/token/symbol results, safe paths and bounded excerpts. Source result is authoritative only for its actual bytes/time, not for inferred runtime behavior. |
| `workspace.semanticSearch` | Conceptual candidates; record embedding/chunk/index identity and validate source before emission. No arbitrary collection/filter expression from a worker. Local BGE-M3 is replaceable. |
| `workspace.structure.query/neighbors/path` | Typed edges, exact symbol identities including overload ambiguity, depth/work/output bounds, extraction/inference provenance, source-supported relation checks and current revision. All visited/emitted endpoints/edges obey security. Absence in an incomplete graph is not proof of no dependency. |
| `evidence.retrieve` / current Task read | Existing runtime/ArtifactStore/verifier authority and admitted refs. Preserve exact evidence/version; distinguish worker assertions from trusted verifier findings. No generic cross-Task read bypass. |

All workspace indexes are derived. Known commit with changed worktree bytes, deleted
source, incompatible extractor/index, unresolved overload or unsupported relation cannot
count as current supported context. Fresh lexical/source fallback is allowed only within
current authority. Index completeness and runtime impact MUST NOT be inferred from an
EXTRACTED label. Cache/index keys and observable revisions are visibility-scoped; no
unscoped global-count diagnostics. Index updates do not become Task completion evidence.

## 9. Promotion and verified learning contracts

**CP-P1 — PromotionGate.** Validate trusted request/source/current binding, immediate-parent
route, exact candidate, actor authority and destination policy. Create a distinct
representation, leaving source content, origin, semantic status and domain unchanged.
Same-domain eligibility does not imply cross-domain declassification. An unverified
hypothesis stays unverified; a verified failure cannot become successful guidance.

Cross-domain requests require separately approved exact candidate/source/destination,
required transformations/checks and fail-closed scanner outcomes. Return a safe destination
receipt; keep source identity, raw evidence and scanner findings in private audit.
Repeat requests revalidate current requirements before returning a prior success. No
unavailable-check bypass, implicit approval from a model or human-origin exemption.

**CP-L1 — VerifiedOutcomeAdmission.** Input authoritative current outcome/evidence plus
reflection candidate and explicit support basis. Success requires every accepted success
requirement. Supported failure can be failure-qualified; incomplete observations remain
unverified; contradiction rejects qualification. Unsupported candidate claims do not
inherit verification simply because the Task completed.

Every admitted success/failure has private authoritative evidence linkage and a safe
retrieval projection. Output is a current-context learned representation, not parent
knowledge or a changed Task result. Human declaration is a separate path. Replays validate
current evidence; same immutable inputs can reproduce results, changed evidence cannot
be overridden by remembered success. Promotion then remains optional and separately gated.

## 10. Durability, observability and compatibility

References/checkpoints MAY carry historical revision/trace facts. New physical reads,
deliveries and effects MUST resolve current trusted policy/topology/authority, including
on a physical retry. Restate replay of already committed observations remains historical
and MUST NOT be rewritten or spuriously re-executed. Recompilation after invalidation
uses a newly admitted operation, not a silent replacement for bytes already bound to a
grant. Complete implementation needs fault tests for the existing journal/dispatch seams.

Use existing operation identities, Task-scoped immutable artifacts and admission records.
No shadow scheduler/Task database; remote route identity and local workspace consent
remain Hub responsibilities. Snapshot/action atomicity is not established by a Python
object, digest, trace ID or retained receipt.

Observability MUST separate private decision audit, safe caller diagnostics and telemetry.
No raw source, queries, embeddings, private provenance, policy details or backend responses
by default. Counts/digests/freshness markers need the same boundary as content. Telemetry
failure cannot affect correctness; enforcement cannot depend on a best-effort telemetry
record. Do not leak denial reasons through exception text. Quality metrics measure
verified work/required evidence, not memory recall counts or agent praise.

First-slice adapter encodings MUST preserve these meanings inside existing receiver
limits. Unsupported operations explicitly report unsupported/unavailable; a provider
method existing is not proof of a conforming production capability. This contract does
not authorize implementation, enable a new capability or change existing wire versions.
