# Context Plane — bounded production implementation plan

**Status: CP.1 PASS (2026-09-24); CP.2–CP.9 NOT STARTED.**
2026-09-23 consolidation under [ADR 0025](../decisions/0025-context-plane-and-compiled-agent-context.md).
[Architecture](../context-plane.md) and [semantic contracts](../contracts/context-plane.md)
are accepted direction. Track III research is COMPLETE, including the retained III.8
FAIL and separate III.8R recovery PASS. This plan is not III.11 or another experiment.
Production work needs separate authorization; the [main roadmap](001-blaine-development-roadmap.md#current-next)
continues to own prioritization relative to Hub E0–E3 and other programs.

The authorized CP.1 implementation is complete within its opt-in hosted/local boundary.
[Milestone and handoff](../milestones/055-context-plane-cp1.md),
[executable subset](../contracts/context-plane-cp1.md), and
[retained acceptance](../../experiments/context-plane-cp1/evidence/acceptance.json)
record 217 passing relevant tests (21 CP.1) and a native Restate/local Goose smoke.
The implementation request has an unsubmitted TaskSpec draft because no creation binding
was available; the separate synthetic native acceptance Task completed with exact evidence.

**Current production state:** deployment-selected ContextPlane on existing Capabilities /
create_workflow / GooseWorker; trusted local Task/spec/principal/resource binding; separate
Resolver and deterministic Compiler; qualified read-only configured Memory corpus; confined
exact/lexical sources and admitted evidence; private compiler admissions; one fresh replacement
delta; current authority/source checks before physical delivery. Default deployments and
unaffected paths retain their behavior. Implementation acceptance is not deployment approval.

**Blockers:** none for bounded CP.1. Live MIRIX remains unqualified/disabled on this path;
headers/tags are not proven processing isolation or trusted provenance. Whole-file exact
requirements must fit unchanged WorkerInput field/envelope limits, otherwise insufficiency
is explicit. General concurrency/revocation/restart guarantees remain CP.8.

**Next bounded increment:** CP.2 — Governed declared/observed writes, requiring separate
authorization. Review and merge CP.1 first, then use a fresh CP.2 branch/worktree. First
qualify existing MIRIX and Blaine-owned entry metadata in approved storage. Its acceptance
boundary is trusted human declaration vs UNVERIFIED current-context observation, isolated
read methods/metadata, scoped idempotency, committed readback, response-loss/restart evidence
and provenance-preserving migration. CP.2 is not started here. No reflection/learning,
semantic search, Graphify, promotion, declassification or remote propagation is included.

## 1. Repository baseline and dependency choices

This section retains the pre-CP.1 seam analysis. The current implemented subset and its
limits are recorded above and in the executable contract; later phases remain proposals.

The kernel already reconstructs CognitiveTurn through bounded ContextProviders. It
journals context/model/effect observations in Restate, admits actions through PolicyGate,
retains exact Task-scoped ArtifactStore bytes and independently evaluates completion.
`worker.run` consumes a bounded WorkerInput artifact and invokes an existing adapter.
The local Goose adapter is one-shot, no-profile, tool-free; do not invent continuation
callbacks or raw MIRIX/Graphify access for it. The owned Cognitive Loop can ask for
additional information between worker dispatches using an admitted capability operation.

The current optional MirixContext is semantic read only. It has no Track III hierarchy,
trusted per-entry provenance or write admission. ProjectKnowledgeContext is an optional
source-digest navigation provider, not a deployed structural service. Frontier projection
is an exact-byte authority boundary, not a complete Context Compiler. E0/Hub identity
and remote workspace consent remain their own prerequisites; no implicit host checkout.

Reuse these seams. Do not create a universal event bus, context daemon, extra database,
second scheduler, new worker, new inference client or parallel TaskState. Freeze only
wire shapes needed by one slice. No broad migration of existing Tasks or providers.

<a id="2-exact-next-increment-cp1--local-governed-context-projection-and-one-delta"></a>
## 2. CP.1 — Local governed context projection and one delta

**Completed: PASS.** The scope and acceptance below are the authorization boundary,
preserved for review; measured results live in the linked milestone/evidence above.

**Hypothesis:** one real Blaine-owned local execution path can receive a useful initial
compiled projection and one fresh delta, preserving current authority, source fidelity
and existing deterministic completion semantics, without exposing raw knowledge backends.

**Boundary:** opt-in hosted/local `create_workflow → context.reconstruct / admitted
capability → Capabilities.worker.run → existing GooseWorker` path. One explicitly
configured local workspace and a small read-only governed Memory corpus, one Task binding,
multiple hierarchy/security fixtures for enforcement tests. No external/cloud worker,
remote read route, production promotion or generated reflection. Not a new public ACP
surface. The public TaskSpec.context concept stays separate from the narrower executable
TaskSpec until this slice freezes any required compatible binding extension.

### CP.1a — Freeze the smallest executable subset

Before coding, map the semantic contract to versioned request/result fixtures and the
existing envelopes. Reuse Task/turn/operation/dispatch IDs. Retain the existing five
cognitive actions; a context request is an `INVOKE_CAPABILITY`, not a sixth action.
Propose one closed `context.request` capability with information need, optional safe
locator/base reference and narrowing, admitted by the existing PolicyGate mechanism.
It carries no caller-selected scopes/domain/backend/projector/provenance.

Use deterministic recorded-cognition and recording-worker fixtures for contract tests;
no model is needed to prove enforcement. Retain current `CognitiveTurn`, `ContextItem`
semantics and existing receiver bounds. Do not increment every schema speculatively.

### CP.1b — Trusted local reference and lineage resolver

Use trusted application/deployment binding issuance tied to the accepted Task route.
Keep a validated, revisioned immutable topology/policy/entry-metadata snapshot in the
existing deployment/artifact boundary for this bounded slice. It is a small configured
input, not a production mutable registry or new Task ledger. Use existing immutable
artifact references where snapshots need retention, with current selection owned by
trusted integration rather than model-written artifacts. Missing issued mapping denies.

First slice assumes no concurrent administrative mutation within an operation; resolve
one coherent snapshot at entry and check it again before physical delivery. Changes
between operations must narrow/recompute access. If identity/version changed during
compilation, refuse delivery and request a fresh admitted operation. Do not claim a
cross-process atomic transaction or instantaneous revocation; those need CP.8 evidence.
Generic ContextNode validity and lineage do not depend on Task/work labels.

### CP.1c — Read-only Memory and exact/lexical source providers

Create the Blaine Memory read facade (`search`, `retrieve`) with independent binding,
entry ownership, provenance and safe-result validation. Feed its results into the
Resolver, not an agent-facing MIRIX client. Reuse MirixContext transport where eligible;
do not treat client headers or filter_tags as proven isolation.

Start with a separately configured, explicitly owned corpus whose permitted entry IDs,
context/domain, provenance/status and source/content version are trusted inputs. Validate
returned IDs/content against that metadata, and prove the provider's actual processing/
query scope before enabling it. Unknown scope/provenance is UNAVAILABLE/DENIED; an
incomplete legacy row does not become globally inherited knowledge. A conforming fixture
transport can prove the facade deterministically, but is not live MIRIX adoption.
Acceptance must report live adapter qualification separately. If MIRIX cannot satisfy
the small corpus boundary, leave it disabled and retain the gap; do not install another
memory product or claim live integration passed. CP.1's core projection can work with
permitted authoritative sources when optional Memory is explicitly unavailable.

Use current exact evidence and a confined local lexical/source reader for the workspace
need. Keep root, path, source version/digest and scope trusted; no remote workspace scan
or widening of D2's exact `workspace.read` initial-action semantics. Do not add semantic
workspace search or Graphify to make this first compiler useful. No writes/declarations,
backfills, migration, reflection or persistent memory index are required.

### CP.1d — Deterministic Resolver/Compiler and admitted initial packet

Route explicit needs to exact evidence, lexical source or governed Memory. Preserve
mandatory current intent/criteria and exact material excerpts, then select optional
context. No LLM summary/ranking and no always-fan-out pipeline. Encode safe provenance
and incomplete/denied/unavailable distinctions within the selected existing envelope.
Use recipient limits, not a new universal 2 KiB constant.

Compile an initial WorkerInput into the existing Task artifact boundary. On the opted-in
path, `worker.run` must require an independently held compiler admission bound to Task,
operation, current binding and exact packet digest. A model-authored artifact with matching
fields or a forged receipt cannot substitute for that record. Implement issuance using
existing runtime-owned admission/artifact mechanisms, not a self-asserted JSON flag.
Current membership in state.artifacts alone is insufficient proof of compiler provenance.

Keep the existing worker adapter shape where faithful packing fits: four context entries,
4096 total encoded bytes, per-field bounds. Criteria/provenance can be rendered compactly
inside existing context content, but cannot be silently dropped. If that shape genuinely
cannot preserve required semantics, stop and review one versioned WorkerInput extension;
do not hide a new format in a permissive validator or relax budgets after failures.

### CP.1e — One continuous information-need delta

After a bounded first work/observation, owned cognition submits a context request for
one precise source/evidence need. Resolver re-queries current sources with the binding;
Compiler produces a bounded delta and recompiled active packet for the next local
worker dispatch. The second worker does not receive the complete previous result/history.
The initial and active-after-delta inputs are each bounded, including all metadata.

This tests continuous resolution through the real owned loop. It does **not** claim
that the existing Goose process requested a tool mid-call. A worker-declared NeedContext
result/tool callback would require a separately versioned adapter capability later.
Public user `add-context` controls are also not redefined as this worker capability.

### CP.1f — Delivery guard, acceptance and stopping point

Do not redesign the Restate loop. Journal newly resolved packets and observations through
the existing step/artifact seam. Before any new physical provider/worker delivery on this
path, resolve current authority; an old journaled packet or admission is not sufficient.
A changed binding invalidates pending delivery rather than silently changing bytes or
re-running an already committed model step. New resolution uses a new admitted operation.
General restart/revocation races remain CP.8, but no first-slice opt-in path may knowingly
reuse stale authority merely because durability integration is later.

**Deterministic acceptance:**

1. Exact permitted sets for current/ancestor reads; sibling/descendant/unrelated/domain
   exclusions; public ancestor allowed only by explicit classification/policy. Malformed
   topology behind a denied boundary rejects. Labels do not alter behavior.
2. Forged context, scope, domain, provenance and packet/receipt fields do not change
   access. Hidden and unknown IDs have equivalent safe responses and no collision leak.
3. Initial packet preserves exact required criteria, signature/assertion/source excerpt,
   provenance and uncertainty; a relevant optional Memory record appears only if its
   trusted provider metadata qualifies. Fake/provider-supplied authority is rejected.
4. One admitted information-need request returns a fresh delta after a permitted source
   changes; forbidden/stale data cannot reappear from the previous packet. Unavailable
   optional Memory is explicit, unavailable current authority denies. Required missing
   evidence blocks sufficient-packet delivery. Empty differs from denied/unavailable.
5. Exact UTF-8 whole-envelope budgets pass for CognitiveTurn, capability result, delta,
   WorkerInput and active combined input. Over-budget exact requirements cause explicit
   insufficiency, not silent criterion trimming or transcript growth.
6. A model-created same-shaped WorkerInput cannot impersonate compiler issuance. Old
   digest/current-policy mismatch refuses fresh dispatch. A deliberate unsafe control
   trusting a serialized scope or compiler flag must produce an actual caught violation.
7. Through the existing runtime and worker.run seam, a recording worker receives only
   the admitted bytes; deterministic CompletionEvaluation still requires exact evidence.
   A worker claiming success without evidence leaves the Task incomplete. Replay consumes
   historical observations without duplicate model calls/effects and cannot grant new reads.
8. Negative literal/reference scans cover caller packets, diagnostics and ordinary logs;
   private audit stays separate. A fresh lexical contribution survives stale derived input.
9. Existing kernel lifecycle, child results, human resolution, policy denial, artifact
   integrity, frontier exact-byte authorization and D2/remote-read behavior remain unchanged
   outside the explicit opt-in path. Run relevant regression suites, not all platform work.

After deterministic acceptance, one separately permitted bounded local Goose smoke through
this same path may validate real packet delivery and an exact-artifact Completion Contract.
Record model/adapter version, input bytes and verifier output; no cloud or general behavioral
improvement claim. If no live adapter is available, report that integration gate incomplete,
not fake cognition as live evidence. Starting CP.1 does not authorize host reconfiguration.

**Stop:** reject missing trusted scope/issuer/source support; do not fall back to legacy raw
retrieval. Leave optional backends disabled if unqualified. A need for new multi-tenant
storage, broad schema migration, remote transport or a general policy engine exceeds CP.1.
No production writes, learned admission, promotion, secret transformation, persistent
cache, vector service, Graphify or remote-worker propagation. Enabling the slice requires
explicit review of retained evidence; implementation completion is not deployment approval.

## 3. Subsequent bounded phases

Each row requires separate authorization and its own narrow evidence. Order is a dependency
proposal, not a promise to implement every mechanism. CP.4/6/7 are workload-driven optional
branches; CP.8 is required before claiming general durable Context Plane integration.

| Phase / dependency | Objective and production boundary | Deterministic acceptance | Regressions protected / explicit non-goals |
| --- | --- | --- | --- |
| **CP.2 — Governed declared/observed writes**; CP.1 | Qualify existing MIRIX substrate plus Blaine-owned persistent entry metadata; trusted human declaration and current-context observation; scoped idempotency/readback through existing durable work. Decide registry schema in existing approved storage. | Human origin only from trusted path; agent always UNVERIFIED/local; all read methods and metadata isolated; pending queue ≠ committed write; response-loss retry produces one record or explicit unknown; schema migration and restart retain provenance. | Preserve existing Memory reads, Task lifecycle and evidence ownership. No second memory product/Task ledger, reflection, promotion, preference precedence or automatic ingestion of conversations. |
| **CP.3 — Outcome-qualified local knowledge**; CP.2 | Feed trusted CompletionEvaluation/evidence into VerifiedOutcomeAdmission; initially reviewed or exactly supported candidates in current C. | Missing/unknown/contradictory evidence cannot support success; verified failure retained as failure; outcome alone cannot verify unsupported text; worker-success and missing-as-pass mutations fail; replay checks current evidence. | Human declarations remain separate; no parent visibility or success from Task FAILED alone. No LLM reflection, arbitrary entailment, consolidation, utility or automatic promotion. |
| **CP.4 — Semantic workspace routing**; CP.1 | Add replaceable semantic adapter using existing local BGE-M3 only for conceptual needs; validate before rank fusion and preserve lexical fallback. | Frozen conceptual/exact/trap workloads; final-packet useful gain, exact non-regression, stale/forbidden zero, incompatible embedding/index rejected; raw scores not directly combined; cost and insufficient-context states retained. | Existing exact lookup stays default; no all-source fan-out, Milvus, new persistent service, Claude Context product adoption, code-equivalence claim or parameter tuning to test oracles. |
| **CP.5 — Same-domain PromotionGate**; CP.2+3 | Add explicit immediate-parent admission with compatible learned provenance/status and private audit/projected receipt; separate operation authority. | No upward ordinary write; authorized route creates distinct parent representation; source immutable; failure/unverified never upgraded; replay revalidates current policy; destination IDs/revisions scoped. | Preserve current-context learning and existing parent TaskResult delivery. Cross-domain promotion remains disabled; no autonomous abstraction or automatic promotion. |
| **CP.6 — Structural on-demand adapter**; CP.1, demonstrated workload | Wrap pinned/evaluated Graphify behind bounded workspace.structure; preserve typed relations and accurate overload identity or abstain. | Current source/edge support, bounded traversal and output, stale/inferred-trust mutations; negative relation cases; explicit partial graph scope; measure useful final targets and cost against lexical on target workload. | No raw MCP or always-on graph, graph authority, inferred-as-fact coercion, replacement graph engine or unproven incremental-update claim. Keep lexical fallback. |
| **CP.7 — Workspace advisory compilation**; CP.1 plus justified CP.4/6 providers | Add novelty/contract candidates and generic simplicity advice with exact material distinctions to packet compilation. | Frozen duplicate/legitimate/near-match cases, deterministic decision verifier, no false-equivalence regressions, corrupt-contract mutation caught, packet/security/freshness preserved. Any behavioral claim additionally requires paired real local-model evidence. | No hard creation gate, minimum-LOC objective, semantic-equivalence verdict, learned-memory oracle hints or automatic scope expansion. |
| **CP.8 — Durable context access and resume hardening**; CP.1, plus each enabled write/admission path | Integrate current policy/topology/binding resolution with existing Restate handoff/wait/resume/retry boundaries; define snapshot consistency and current admission outside historical observations. | Kill/resume at compilation, admission and physical delivery; changed policy/topology denies old access; same-state replay has no duplicate effects/model calls; evidence readback and scoped idempotency survive response loss; stale packet/provenance/scope mutations fail. | Preserve journal history, cancellation/waits/child results and exact frontier grants. No second lifecycle engine, global activity counter, claim of retroactively erasing already delivered bytes or remote authentication. |
| **CP.9 — Remote-worker propagation**; CP.8 + applicable Hub E0/E1 identity/consent acceptance | Carry references over existing authorized transport; receiving side independently binds route/workspace/current authority and recompiles/retrieves. | Real second-machine cases with wrong principal/workspace/session generation, revoked grants and replay; out-of-scope reads rejected by Hub PolicyGate (for IDE-delegated workspaces the client is a bridge, not a guard; [ADR 0027](../decisions/0027-ide-delegation-is-workspace-authority.md)); no missing/foreign metadata leaks; independent completion evidence intact. | No new authentication system, implicit host workspace copy, automatic route migration, session-as-Task identity or widening grants because worker moved. |

**Cross-domain declassification production admission is deferred, not a scheduled default
phase.** Before enabling it, decide approvers, exact approval binding, transformation
quality/support, scanner coverage, audit visibility and residual semantic-leakage risk.
Use III.5 fail-closed composition; do not mistake its literal fixtures for real DLP.
Generated reflection, consolidation, utility/voting/decay, caches, retention/correction
and dynamic topology administration likewise need measured demand and scoped plans.

## 4. Human decisions and defaults

| Question | Current accepted/proposed default | Decision point |
| --- | --- | --- |
| Start and prioritize production work? | CP.1 authorized and PASS; CP.2 is next, not started. Other track priorities unchanged. | Separate authorization for CP.2; review CP.1 evidence before deployment enablement. |
| First issuer and snapshot ownership? | Trusted single-host application binding, immutable configured snapshot, existing Task/artifact identities; no caller issuance. | Confirm exact local configuration/administration boundary in CP.1 preflight; stop if it requires production multi-principal auth. |
| Durable entry metadata / MIRIX scope qualification? | Reuse existing substrate; Blaine-owned metadata is required, tags are not ACLs. Unqualified provider stays unavailable. | CP.2 storage/atomicity design; no new store silently chosen in CP.1. |
| Remote and concurrency guarantees? | Do not claim them from III.10. Refuse detected stale authority at local delivery now. | CP.8 consistency/revocation model; CP.9 existing Hub trust boundary. |
| Budgets and ranking parameters? | Preserve actual receiver caps; deterministic first slice; profile by workload later. | Each slice freezes budgets/quality gates before evaluation. No universal 2 KiB or eternal RRF constant. |
| Learned statement support and conflicts? | Only explicitly supported forms/reviewed candidates; preserve uncertainty/conflicts. | CP.3 and later correction/retention design; no arbitrary automatic entailment. |
| Cross-domain promotion approvers/risk? | Disabled pending validated authority and transformation/check policy. | Separate human architecture/security decision before enabling. |
| Always-on Graphify or hard novelty blocking? | Neither is justified; on-demand/advisory only. | Reconsider only with separately authorized evidence, not product popularity. |

No unresolved conflict prevents architecture consolidation PASS. These decisions gate
future expansion, not permission to silently fill unknowns during implementation.

## 5. Historical acceptance of the architecture consolidation

Documentation-only review must confirm: historical evidence unchanged; exact result
claims match retained summaries; concepts classified; contract owners do not move;
initial/delta and egress semantics consistent; every implementation phase has boundary,
acceptance/regression/non-goal criteria; current gaps named; local links and whitespace
valid. No production tests, model calls or old experiments need to run to accept prose.
That consolidation proposed **CP.1 — Local governed context projection and one delta**.
CP.1 was subsequently authorized and completed as recorded at the top of this document;
the original architecture/research evidence remains unchanged.
