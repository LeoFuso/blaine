# ADR 0025 — Blaine Context Plane and compiled agent context

**Status:** Accepted

**Validation:** Partially Validated

**Date:** 2026-09-23

## Context

Blaine executes durable, bounded, evidence-driven work. Tasks outlive sessions and
workers; context must survive those boundaries without turning serialized metadata
into authority. Track III established bounded hierarchy/security/provenance/learning
semantics and useful historical/workspace retrieval. III.8 failed its final-packet
utility gate; the separate III.8R recovery passed. III.G established corpus-dependent
structural utility after III.8's lexical baseline saturated its structural questions.
Research is complete enough for architectural decisions, not production-readiness claims.

Existing cloud packets, ContextProvider/CognitiveTurn, worker.run, Evidence/Completion
Contracts, PolicyGate and Restate ownership already provide relevant boundaries. A new
unrestricted RAG surface or replacement orchestration system would undermine them.

## Decision

Accept the [Context Plane architecture](../context-plane.md) and
[normative semantic contracts](../contracts/context-plane.md). Blaine owns:

- One generic ContextNode tree: current/permitted-ancestor reads, current writes,
  no implicit upward flow; labels do not create different memory architectures.
- Trusted ExecutionContext reference resolution; lineage ∩ security ∩ policy plus
  resource permissions. Metadata and derived representations are protected like content.
- Continuous governed Memory, trusted origin and success/failure qualification,
  separate human declarations, verified outcome admission and explicit PromotionGate.
- A **Context Resolver** that routes information needs to appropriate governed sources,
  and a **Context Compiler** that validates, canonicalizes, selects and faithfully
  renders bounded initial packets and deltas. These need not be deployed services.
- **Broad Context Plane, compiled narrow agent context.** Workers normally receive
  prepared projections and ask for bounded additional needs, not raw MIRIX/Graphify/
  vector access. Exact material evidence survives condensation; references do not grant
  access. Context deltas do not accumulate into an unbounded transcript.

Repository/files and runtime evidence remain authoritative. Memory and indexes remain
derived. Reflection admission does not promote. Worker claims do not establish success.
Current trusted policy/topology wins for new access/delivery; replayed historical
observations remain historical, not grants for new physical work. Existing Restate
journal semantics must be preserved, not bypassed or rewritten to refresh authority.

MIRIX remains a candidate/current substrate behind Blaine-owned contracts; it does not
own hierarchy, security, learning qualification or lifecycle. Lexical is the cheap
exact default; local BGE-M3 is the first replaceable semantic implementation candidate.
Graphify is **ADAPT / ON-DEMAND** behind `workspace.structure`, not unrestricted MCP or
always-on retrieval. Novelty/simplicity is advisory; hard similarity-based blocking is
not justified. Atomic lifecycle ideas, agent-skills evaluation and Ponytail simplicity
principles are mechanism adaptations, not product/runtime adoption. Claude Context and
OmniRoute remain unadopted product candidates/references with the limits in the spec.

Explicit budgets and heterogeneous rank fusion are architectural mechanisms; 2 KiB,
RRF k=60 and source-family normalization are experimental choices, not universal protocol
constants or evidence of semantic equivalence. Route before combining; more sources can
reduce useful final coverage when provenance consumes the budget.

Accept the [bounded production plan](../roadmap/002-context-plane-implementation.md) as
proposed sequencing. Recommend CP.1, one opt-in local worker path with trusted binding,
read-only Memory facade, exact/lexical resolution, deterministic initial compilation and
one owned-loop delta. At acceptance, implementation was **NOT STARTED** and required
separate authorization. On 2026-09-24, separately authorized
[CP.1 passed](../milestones/055-context-plane-cp1.md) within the opt-in local boundary;
later phases remain unstarted and separately gated.

## Relationship to existing decisions

No accepted ADR is superseded. Preserve Task/lifecycle ownership (0001/0003/0015), paid
cloud authority and mandatory Cloud Context Packets (0008/0009), protocol neutrality
(0012), replaceable harnesses (0016), platform storage/observability constraints (0018
and its later amendments), Hub identity/workspace consent (0022), and secret ownership
(0023). The existing exact-byte FrontierContextProjector/grant boundary remains required
for cloud packets and deltas. Compiler output alone grants no egress.

ADRs 0013 and 0014 retain their historical Proposed status. This ADR adopts the needed
fail-closed egress and retrieval-first principles within its scope, not their complete
unvalidated transformation/training schemes. Historical Spotify-inspired context/catalog
ideas are refined into resolver/compiler responsibilities; no external product behavior
is asserted. No experiment, milestone or earlier PASS/FAIL is rewritten.

## Alternatives considered

- Direct worker access to every knowledge backend: rejected for scope, authority,
  observability and budget bypasses.
- Initial-only prompt injection: rejected as the complete capability model; III.3
  requires later participants to resolve post-start knowledge.
- One generic RAG service always consulting every source: rejected as the default;
  routing, source authority and compilation have different responsibilities/costs.
- Lexical only forever: insufficient for demonstrated conceptual/graph-shaped needs;
  it remains the default/fallback rather than being discarded.
- Always-on Graphify or hard NoveltyGate: unsupported by bounded evidence and known
  representation/overload limitations.
- Productionizing all Track III features together: rejected in favor of one local
  read/projection slice before writes, learning, promotion and distributed propagation.

## Consequences

Workers receive less, more intentional context while additional access stays continuous
and governed. Backend replacement need not redefine Blaine semantics. False success,
private provenance and stale authority have explicit admission boundaries. Compilation
adds cost and can lose useful material; measure final Task quality/exact evidence,
not merely candidate recall or compression. Source validators, snapshot consistency,
storage metadata and durable admission are real implementation work, not solved by
recording this ADR. Provider logs and metadata require explicit confinement.

## Validation

### Hypothesis

Blaine can supply useful minimal projections from broad governed sources without
weakening lifecycle, evidence, authority or security across bounded execution boundaries.

### Validation level

**Partially Validated:** isolated deterministic Track III semantics, paired synthetic
local-model utility and two-repository Graphify retrieval. The subsequently authorized
CP.1 local production integration now passes within its retained fixture/smoke boundary.
Broader end-to-end validation remains outstanding; no general authentication/concurrency/DLP
or distributed durability claim follows from those results.

### Minimal validation and evidence

Historical evidence and its limits are tabulated in [architecture section 3](../context-plane.md#3-evidence-and-what-it-does-not-prove).
The consolidation checks document coherence and compatibility, not new experimental
outcomes. CP.1's [acceptance gates](../roadmap/002-context-plane-implementation.md#cp1f--delivery-guard-acceptance-and-stopping-point)
require the real kernel/worker dispatch seam with deterministic fixtures, preserved exact
criteria, current-binding checks, one fresh delta, caught forged-admission/scope control,
bounded complete output and unchanged independent completion. A bounded live adapter
smoke is separately identified; a fixture is not mislabeled live evidence.

### Consolidation review

Documentation review passed on 2026-09-23: 352 local links/anchors resolved; result claims
were checked against retained summaries; 5,103 tracked experiment, runtime, test,
infrastructure and historical milestone files matched baseline `db8b2a4` byte-for-byte
(the milestone navigation index is intentionally updated). Whitespace checks passed.
No experiment was rerun, no model was called and no production implementation changed.
This validates the consolidation deliverable, not the unstarted production slice.

### Not required for initial validation

Automatic reflection, semantic entailment, production declassification, new databases,
Graphify always-on, semantic search everywhere, remote authentication, new lifecycle
machinery, cloud cognition or modification of historical Track III evidence.

## Reconsider when

Representative production work loses material evidence or quality under compilation;
source routing costs exceed measured utility; backend scope/provenance cannot be enforced;
current-authority checks cannot compose with existing durability/dispatch without a
new architectural decision; or a needed worker cannot consume the contract honestly.
Reconsider the bounded implementation, not silently weaken policy or replace source
truth with memory. New evidence may change provider/parameters but not grant authority
to untrusted payloads. Architecture consolidation alone is not deployment approval.
