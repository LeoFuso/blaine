# Track III.1 — Reference systems for hierarchical context and verified learning

Research checkpoint: **2026-09-23 — PASS (source research only).**

Sufficient repository and current upstream evidence exists to specify III.2.
This does not validate hierarchy enforcement, memory quality, isolation, or a
production integration. **III.2 is proposed, unstarted, and requires explicit
authorization.** No runtime changes or dependency adoption accompany this report.

Blaine is a **durable, bounded, evidence-driven execution system that learns from
verified work**. The useful external mechanisms are bounded retrieval, explicit
memory provenance, staged reflection/consolidation, and measurable workflow
quality. Their upstream execution and security assumptions cannot simply become
Blaine's assumptions.

## Accepted refinement before III.3 — 2026-09-23

This addendum records a newly accepted requirement; the III.1 research and III.2
results did not test it. Humans may directly declare knowledge, preferences,
constraints and procedures into an explicitly authorized bounded context. Trusted
code assigns USER_DECLARATION provenance from the human caller boundary. Agent
writes receive AGENT_OBSERVATION provenance; arbitrary payload fields cannot forge
human origin or elevate authority. Human declaration is an authorized direct write,
**not promotion** of knowledge from a child. Both kinds use the same generic tree
and visibility rules; neither makes memory authoritative evidence or grants execution
permissions. No full preference/conflict system is implied.

[III.3's milestone](../../milestones/044-track-iii-3-continuous-memory-capability.md)
records the bounded test of this refinement. The historical proposals and statuses
below remain the III.1 checkpoint; the [roadmap](../../roadmap/001-blaine-development-roadmap.md#track-iii--hierarchical-context-memory--verified-learning)
owns current sequencing.

## III.4 isolation clarification — 2026-09-23

[III.4](../../milestones/045-track-iii-4-bounded-security-context-isolation.md)
provides a bounded executable check of structural lineage intersected with trusted
security-domain visibility and policy. Shared ancestry and human provenance grant
no cross-domain visibility. All supported derived/graph/cache/diagnostic paths must
preserve source permissions, including identifiers and counts. Private root records
are adversarial fixtures to test independent enforcement, not a relaxation of the
shared-root recommendation below. Ordinary writes cannot create global knowledge.
This checkpoint does not establish production security or declassification; historical
III.1–III.3 results and their limits remain unchanged.

## III.5 admission clarification — 2026-09-23

[III.5](../../milestones/046-track-iii-5-promotion-declassification-admission.md)
tests explicit immediate-parent promotion, separate from ordinary writes and human
declaration. Cross-domain admission requires trusted source/candidate/destination-
bound approval and fail-closed deterministic checks; generation and semantic
abstraction remain separate. Promotion preserves origin and epistemic status rather
than asserting verification. Destination receipts are a safe projection of private
audit, and replay must revalidate security before returning a previous admission.
Identifiers/collision behavior and revision/activity metadata obey the same security
boundary as content. These are finite synthetic results, not real DLP or verified
learning; historical III.1–III.4 checkpoints retain their original scope.

## 1. Scope, method and evidence

Hypothesis III.1: existing systems contain separable mechanisms that can support
generic hierarchical knowledge without replacing Blaine's lifecycle, authority,
or completion boundaries. The bounded research inspected repository contracts,
implementation seams, historical evidence, and public upstream source. It did not
install or execute upstream products, invoke models through Blaine, query deployed
services, or rerun historical experiments.

Evidence notation throughout:

- **SRC:** observed implementation at the pinned commit; source inspection is not
  an executed integration or a complete security audit.
- **DOC:** upstream documentation describes behavior; not independently measured.
- **CLAIM:** upstream benchmark/product claim; not a Blaine result.
- **INFERENCE:** architectural interpretation or recommendation from this review.
- **HIST:** previously retained Blaine evidence, with its original scope.

The [source manifest](../../../experiments/track-iii-001/evidence/source-manifest.json)
records full commits, source URLs, file hashes, dates and clean temporary checkouts.
The [review record](../../../experiments/track-iii-001/evidence/review.json)
separates research acceptance from mechanical document checks. No benchmark
improvement is claimed. Reproduce source observations by fetching the manifest's
commits and inspecting the named functions/files; no product installation is needed.

The [TaskSpec draft](../../../experiments/track-iii-001/request.json) is
**unsubmitted**. No suitable creation binding for this research was exposed in
this session. D2's documented bounded binding is not a general research executor.
There is no runtime Task ID or claimed Restate completion state; this is the
user-authorized workspace deliverable, following the existing carveout convention.

| Reference | Current source inspected | Identity / evidence limit |
| --- | --- | --- |
| Atomic Agent / Atomic Chat | `17d7d87a08c559c63b37e0ae0589eaff3e631b80` | Agent v0.6.3 source; [Atomic Chat](https://atomic.chat/) is product context, not evidence of identical internals across its apps. |
| MIRIX | `8cb06a62bbb7c478beb33dd4f2815696a72df482` | Canonical [Mirix-AI/MIRIX](https://github.com/Mirix-AI/MIRIX), [documentation](https://docs.mirix.io/). Docs distinguish current memory-service main from legacy desktop-agent. Same commit as Blaine's prior carveout. |
| Graphify | `a5957aa6ef51c9be8d054de9783d25046c187f3f` | v0.9.66, newer than Blaine's v0.9.64 carveout; old probe results are not fresh execution evidence. |
| Claude Context | `6fc318b4e3ce58e2898b00a9c3538ead9e24dee5` | Core library and MCP source, not a deployed retrieval comparison. |
| agent-skills | `bcab6a1b8503100e8618c3b4e32cc78de43de769` | Workflow documents plus evaluation runner; no skills installed or behavioral evals run. |
| Ponytail | `e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156` | v4.10.0 rules, hooks, review skill and benchmark method. Read as research, not activated instructions. |
| OmniRoute | `18bbb101980c639cfabdc5663213836d917c3269` | Provider, quota, fallback, accounting and logging source; no provider calls or routing adoption. |

### Repository baseline and reconciliation

Baseline: `b172dd646712c1b1fde4453a779320b96eefe523`, branch
`feature/track-iii-context-memory`; initial worktree clean.

| Inspected authority / evidence | Consequence for Track III |
| --- | --- |
| [README](../../../README.md), [architecture](../../architecture.md), [roadmap](../../roadmap/001-blaine-development-roadmap.md), [ADR index](../../decisions/README.md), [milestone index](../../milestones/README.md) | Add a bounded research track; preserve program ownership and historical outcomes. |
| ADRs [0001](../../decisions/0001-task-is-the-unit-of-work.md), [0003](../../decisions/0003-evaluate-restate-as-durable-runtime.md), [0015](../../decisions/0015-durable-task-execution-and-verification.md); [kernel history](../../milestones/cognitive-kernel-progress.md), [cognitive checkpoint](../cognitive-loop-checkpoint.md) | Task, Work, Worker and evidence differ. ContextNode labels do not redefine their lifecycle semantics. Kernel 1–12 remains closed. |
| ADRs [0007](../../decisions/0007-tools-before-model-inference.md), [0008](../../decisions/0008-paid-cloud-crosses-single-dispatch-boundary.md), [0009](../../decisions/0009-cloud-context-packet.md), [0010](../../decisions/0010-worker-selection-is-capability-and-quality-driven.md), [0011](../../decisions/0011-local-inference-is-a-scheduled-shared-resource.md) | Deterministic discovery first; bounded packets; resource suitability, cost and authority stay distinct. |
| ADRs [0013](../../decisions/0013-protected-context-transformations.md), [0014](../../decisions/0014-project-knowledge-is-retrieval-first.md) | Proposed directions, not validated security or retrieval implementations. Pseudonymization is not declassification. |
| [Frontier dispatch](../../contracts/frontier-dispatch.md), [worker boundary](../../contracts/worker-execution-boundary.md), [ExecutionEvent](../../contracts/execution-event.md), [completion policy](../../policies/task-completion-and-lifecycle.md) | Exact projected bytes remain bound to authority. Identity/telemetry cannot confer grants or completion; no generic DLP is currently proven. |
| [MIRIX carveout](../mirix-carveout.md), [Increment 4](../../milestones/009-cognitive-kernel-increment-4-passed.md), [memory adapter](../../../runtime/kernel/memory.py), [context reconstruction](../../../runtime/kernel/context.py), [workflow](../../../runtime/kernel/workflow.py) | HIST: bounded semantic recall, absent-memory fallback and source conflict precedence passed. SRC: retrieval participates in per-iteration reconstruction, already more than start-only injection; adapter is read-only, loopback, semantic-only, limit two. No generic hierarchy, promotion, or worker-query contract is established. |
| [Graphify carveout](../graphify-carveout.md), [Increment 9](../../milestones/025-cognitive-kernel-increment-9-passed.md), [project provider](../../../runtime/kernel/project_knowledge.py) | Source hashes gate bounded navigation; source matching does not prove graph claims. Memory, graphs and evidence are distinct. |
| [D2](../../daily-driver-d2.md), [Hub E0–E3](../../personal-agent-hub.md), [services](../../platform-services.md), [routing ADR 0024](../../decisions/0024-routing-ground-truth-from-restricted-replay.md) | Preserve remote capability boundaries and adopted MIRIX/Qwen/BGE services. ADR 0024 is proposed and separates measured completion from model judgments about routing. |

The checked-in roadmap names Track A/B, D1–D7, E0–E3 and post-v0 Cycles A–E;
it does not define programs literally named Track I/II. Track III does not rename
them or infer their status. The user-referenced kernel/resource-allocation,
worker-execution and remote-execution concerns retain their existing owners.
Track III overlaps future Context Compilation/Project Knowledge questions without
authorizing their implementation or becoming a new Daily Driver prerequisite.
No proven invariant conflict was found. This is a research decision, so no new
accepted implementation ADR is manufactured.

## 2. Problem and accepted invariants

Small packets alone can hide canonical abstractions and encourage duplicate
helpers. Unbounded recall can leak proprietary information, overwhelm a model,
or repeat a failed strategy as established knowledge. Conversation-derived
learning can mistake a plausible reply for a successful outcome.

Preserve these boundaries:

1. Durable work outlives conversations, models, workers, processes, machines and
   human delays. Restate owns state, waits, timers, retries, resume and cancellation.
2. Models make bounded semantic decisions; workers execute; PolicyGate owns
   authority. A memory, skill, graph edge or routing preference grants nothing.
3. Evidence and deterministic Completion Contracts determine completion.
   Artifacts and current authoritative sources outrank memory.
4. Memory is derived operational knowledge. Hypothesis, failure, verified result
   and generalized lesson must remain distinguishable.
5. Knowledge inherits downward within permitted lineage. Ordinary writes stay
   local to the current context; upward flow is explicit, gated promotion.
6. Security labels survive every derivation. Secrets are never reusable memories.

## 3. Generic bounded ContextNode hierarchy

Accepted conceptual shape, **not a frozen wire schema**:

```text
ContextNode(id, parent_id, kind/labels/metadata, security_context, policy_refs)
```

There is one tree. Every non-root node has exactly one parent; the root has none.
Cycles, multiple parents, missing parents and ambiguous identity are invalid.
Labels such as project, epic, card, task, work, attempt, experiment or initiative
are descriptive. The memory engine must never branch on these labels. Arbitrary
additional specialization levels are permitted. Runtime Task identity can refer
to a node without making that node an execution-state owner.

```text
root (explicitly shareable common knowledge only)
├── personal
└── employer-x
    └── project-a → epic → card → task → work → attempt
```

For context C, the candidate read set is C and its ancestors; the **effective**
read set is the subset permitted by trusted security and policy evaluation.
Tree membership is necessary but insufficient for access. No implicit descendant
or sibling read, including direct-ID fetch, graph expansion, cache hit, summary,
deduplication, vote, profile lookup or index statistics. A parent cannot search
its descendants just because it owns a broader label. Root is not an aggregate
search view over the organization branches.

Default write destination is C. Ordinary write APIs cannot target a parent or
sibling. Promotion is a separate authorized operation creating a derived record
at the parent, with explicit provenance and admission; it need not delete the
child's original. Reaching a grandparent requires separately governed steps,
not bypassing the intermediate parent. Retrieval may prefer closer, more
specialized records **after** authorization and relevance checks. Proximity is
neither truth nor authority; contradictory records retain their status and sources.

## 4. Security boundaries and declassification

Employer knowledge cannot reach personal work via their common root. Shared
ancestor knowledge must itself be explicitly eligible for both domains; a write
under an employer branch does not change the root. Unknown or incompatible
policy fails closed. Hierarchical links do not grant cross-domain access.

The future boundary must cover memory text, embeddings, lexical/semantic indexes,
project graphs, prompt/context caches, summaries, traces, LLM observability,
artifacts, tool outputs and provider logs. Partition keys and access controls
must apply before retrieval, neighbor expansion and ranking; filtering only the
final prompt cannot prevent earlier disclosure to an index or embedding provider.
Identifiers, result counts and provenance links can leak too.

Credentials, tokens, passwords, private keys, cookies and authentication headers
may be used transiently by an authorized capability. They cannot be persisted as
reusable memory, embedded, or passed into reflection. A credential-provider
reference can be retained under appropriate policy, never its secret value.
This does not relocate Blaine's credential storage into the Memory Plane.

Cross-domain promotion requires an explicit **abstraction/declassification**
boundary in addition to ordinary promotion authorization. For example, a lesson
about separating variable behavior from selection policy may be useful outside
an employer; its internal classes, tickets, URLs and implementation are not.
The generalized lesson should also require checking for an existing canonical
abstraction before creating one.

Future III.5 admission must combine semantic abstraction with deterministic
secret scanning, organization/project/repository identifiers, hostnames/internal
URLs, ticket patterns, source/class/package identifiers where feasible, and
exact/near-exact source-text leakage checks. Record source digests, transformation
and scanner versions, bounded evidence, destination and policy decision. A clean
scan is necessary evidence, not proof that confidential meaning disappeared.
Uncertainty, missing provenance, unavailable scanners or unapproved destination
must deny promotion. No raw fallback and no automatic approval from an LLM.

Private provenance remains in the source domain. The destination can receive a
permitted opaque receipt; copying a private repository URL into an otherwise
sanitized lesson would defeat declassification. Revocation, deletion, cache
invalidation and downstream derived-record retention need later experiments.
Neither text redaction nor pseudonymization alone proves this boundary.

## 5. Memory as a runtime capability

Proposed ExecutionContext composition: existing Task/execution identity, trace
context, knowledge-context reference, security context, authority reference and
evidence/provenance references. This is a future integration concept, not a
replacement TaskSpec or a mutable worker-selected security object.

Trusted runtime code resolves readable lineage and current policy. Consumers
submit a bounded query/purpose and optional narrowing; they cannot supply an
arbitrary tenant, scope list or parent. Reads return bounded sourced records with
context identity, revision, epistemic status and freshness/uncertainty. Writes
record observations in C. These semantics must cover cognition, worker tools,
verifiers when useful, resumed Tasks and authorized remote workers.

Continuous capability does not mean a background poll or injecting everything on
every turn. Use just-in-time search and compact pointers, then fetch permitted
detail on demand. Count result bytes, calls, graph hops and inference costs;
cache only under a scope/policy/content-version key. Failures distinguish empty
results from unavailable retrieval or denied access. A quality fallback may use
an authorized lexical search; it must never relax security.

Restate remains the owner of durable scheduling and replay. Future reflection or
consolidation work needs durable identity, idempotent admission and explicit
evidence readback; an in-process callback is not its lifecycle. On resume, retained
receipts explain prior decisions while current policy must reauthorize new reads.
III.10 must settle snapshot versus live lineage and revocation semantics. The
existing exact-byte frontier projection still governs all outbound memory content.

## 6. Verified-learning lifecycle

```text
execution → scoped observations → evidence → deterministic Completion Contract
  → verified outcome → scoped reflection → candidate memories → promotion gate
  → optional abstraction/declassification → parent knowledge
  → later consolidation into reusable lessons/procedures → utility feedback
```

Working observations include hypotheses, attempted approaches, failures,
recoveries, decisions and open questions. They are useful within C without being
trusted reusable conclusions. Future candidate records should bind the exact
Task/outcome, criterion/verifier version, artifacts/digests, observation sources,
context/security policy, reflection model/prompt version and uncertainty.

Verified success means the accepted criteria were satisfied; it does not prove
that every strategy mentioned in a transcript caused success. Reflection remains
a fallible inference. Failed experiences can become explicitly failure-labeled
candidates with verified failure evidence. Cancelled, incomplete or unverified
work cannot increment success merely because a worker replied. A verified child
result does not imply parent completion or automatic child-to-parent learning.

Utility feedback must distinguish surfaced, inspected, used, verified helpful,
harmful and unknown. Recall counts and model votes can guide ranking; they cannot
change truth, security classification, Completion Contracts or execution policy.
Consolidation retains source relationships and conflicting evidence. Eviction of
a derived index entry must not silently erase authoritative completion evidence.
III.7 must compare later Tasks with/without eligible lessons against the same
criteria, including regressions, failed advice and negative transfer.

## 7. Mechanism-level comparative study

Classification meanings: **ADOPT** a design/evaluation practice; **ADAPT** a useful
mechanism whose assumptions must change; **REIMPLEMENT BEHIND BLAINE CONTRACT**
for a provider-neutral capability with Blaine enforcement; **OBSERVE** pending
measured benefit; **REJECT** the stated behavior within Blaine. None means install
a package in III.1, and none is a whole-product verdict.

### 7.1 Atomic Agent / Atomic Chat

**SRC:** hot-path recall combines user text and tool observations; the agent loop
refreshes memory before execution and between steps. This contradicts older
`MEMORY.md` wording about once-per-turn-only retrieval. Its older non-goals also
omit mechanisms now present in source. Treat the current call sites as evidence,
not either document as an unconditional implementation inventory. [Loop][atomic-loop],
[provider][atomic-context], [older document][atomic-old]

| Mechanism and evidence | Blaine disposition / cost |
| --- | --- |
| SRC: bounded BM25 recall, deduplicated pointer index and optional bounded BFS expansion; explicit ID drill-down. | **ADAPT:** strong fit for just-in-time consumption; recheck authorization on every edge and ID. Ranking is not verification. [Provider][atomic-context] |
| SRC: optional embeddings blend BM25 with brute-force cosine in JavaScript; a corpus ceiling skips cosine, unavailable embeddings fall back to lexical results. | **OBSERVE:** useful measured fallback idea, not a reason to adopt SQLite or linear vector scans for Blaine. Embedding generation/cache/model changes add cost. [Hybrid recall][atomic-hybrid] |
| SRC: profile facts have supersession history, pinned/contextual rendering and vote fields. | **ADAPT:** versioned preferences/facts may help, but no global profile bypass; even pinned facts obey lineage and security. History is not independent evidence of truth. [Profile store][atomic-profile] |
| SRC: async reflection produces facts/notes; optional link generation follows it. Notes retain session/source/time metadata. | **ADAPT:** observations and candidate extraction, restricted to permitted evidence. **REJECT:** turn-end inference as verified learning or fire-and-forget as durable completion. [Reflection][atomic-reflection], [link decorator][atomic-links] |
| SRC: linked/tagged eligible episodes are clustered; cold-path LLM distillation creates lessons and optional advisory procedures, archives parents and retains parent IDs. The job uses an in-process interval and explicitly documents incomplete link rewiring. | **ADAPT:** staged consolidation and inspectable ancestry. **REIMPLEMENT BEHIND BLAINE CONTRACT:** durable orchestration, bounded retries and admission. Do not copy its scheduler. [Consolidator][atomic-consolidator] |
| SRC: vote events, bounded scores/decay and retention caps; utility eviction orders vote score, recall count, last recall and update age. | **OBSERVE:** assess feedback bias and negative transfer before enabling. Repeated recall rewards exposure; it does not establish usefulness. Audit-log eviction is not Blaine evidence retention. [Votes][atomic-votes], [notes][atomic-notes] |
| SRC: lesson success is incremented when the turn reason is reply/finish. | **REJECT:** that positive signal is weaker than Blaine's deterministic outcome. Attribute utility only against criterion-scoped evidence. [Loop][atomic-loop] |
| SRC: heuristic-gated optional query rewriting memoizes a result per session/message/history slice, including timeout fallback, to avoid repeating the call at every refresh. | **OBSERVE:** evaluate referential-query recall versus added latency/model dependence; keep the original query and scope immutable. [Rewriter][atomic-rewriter] |
| DOC: separate bounded prompt channels for profile, lessons, procedures, index and recalled notes. | **ADAPT:** explicit per-channel and aggregate budgets; measure selection loss as well as token reduction. [Guide][atomic-guide] |

**SRC security counterexample path:** the default provider passes working-directory
scope to base recall/index, but link expansion hydrates `store.get(id)` without
that scope; lesson/procedure lookups also lack that argument in this provider.
This inspection demonstrates an absent check at those paths, not an executed
exploit. **INFERENCE:** project filtering cannot serve as Blaine's security
boundary. Consolidation, dedup and global profile state also require scrutiny.
The SQLite deployment, native bindings, extra model calls and provider-bound
reflection are operational choices, not automatically reusable architecture.
The guide explicitly notes that configured remote providers receive memory in
prompts. Parent IDs are useful provenance but do not bind Blaine verifier receipts.
[Provider][atomic-context], [guide][atomic-guide], [consolidator][atomic-consolidator]

### 7.2 MIRIX

**DOC/SRC:** current main is an independently usable memory service; its Meta
Memory Agent and specialized memory agents do not require adopting a chat agent.
It supplies core, episodic, semantic, resource, procedural and Knowledge Vault
representations, field-specific searches and ingestion APIs. These are content
types, **not** ContextNode hierarchy levels. **HIST:** Blaine has exercised local
PostgreSQL/pgvector, Redis, Qwen and BGE-M3 persistence and bounded semantic recall;
this review makes no new service-health claim. [Docs](https://docs.mirix.io/),
[API][mirix-api], [Blaine carveout](../mirix-carveout.md)

**SRC:** client read scopes are passed separately to shared SQL/Redis filter
builders; an empty scope list denies in the SQL helper, whereas `None` omits the
scope filter. Generic `filter_tags.scope` is deliberately ignored there. The API
also accepts a client-ID header path without the API-key lookup performed in its
key path. Thus useful scoping machinery exists, but it is not proof of end-to-end
tenant isolation, authorized lineage, or safe direct access by untrusted workers.
Do not emulate a hierarchy by letting the model compose filter tags. [Filter
builder][mirix-filter], [identity resolver and search routes][mirix-api]

**SRC:** session distillation reads sealed conversation sessions, generates pending
experiences with learn/avoid status, and explicitly has no external success oracle.
The curator uses pending experiences and bounded edit budgets to evolve procedural
skills. Session-tag routing distinguishes task/conversation ingestion; MIRIX's task
session is not a Blaine durable Task or Completion Contract. Ordinary extraction,
procedural distillation and asynchronous queued writes have different completion
semantics. [Distiller][mirix-distiller], [curator][mirix-curator], [API][mirix-api]

**ADAPT** existing storage/search and explicit experience states, rather than
inventing a second memory product. **REIMPLEMENT BEHIND BLAINE CONTRACT** lineage
resolution, write admission, verified-outcome reflection, promotion, declassification
and durable scheduling/readback. **REJECT** the Knowledge Vault secret-value path
for reusable memory: its ORM stores a string value, not a credential isolation
boundary. **OBSERVE** automated skill evolution pending verified-learning evidence.
[Vault schema][mirix-vault], [distiller][mirix-distiller]

Costs include the already adopted database/cache/model services, memory-agent
inference, separate queue state, persisted agent configuration, indexing and
retention coordination. Scope needs validation across every search method,
direct fetch, core block and cache. Existing historical findings include incomplete
configuration APIs, provenance gaps and successful agent exits despite failed
child writes; retain those limitations rather than assuming a queue acceptance
or finish signal is a committed memory. [Prior source/probe review](../mirix-carveout.md)

### 7.3 Graphify

**SRC:** deterministic extraction, cross-file resolution, NetworkX graph building,
query serving and watch/update are separable from its assistant hooks and optional
semantic extraction. It is structural workspace navigation, not verified
operational memory. No vector database is needed for this structural path.
[Extraction][graph-extract], [build][graph-build], [serving][graph-serve]

**HIST:** Blaine's v0.9.64 carveout demonstrated deterministic extraction and
retained freshness/provenance counterexamples. **SRC at v0.9.66:** the clustered
builder still selects Graph/DiGraph, includes origin fallback inference, and has
separate raw-list edge deduplication. Distinct relationships can collapse in a
simple graph path; a source-location-shaped value is not proof of derivation.
Do not declare old update counterexamples fixed or reproduced from a version bump.
[Build][graph-build], [historical experiment](../graphify-carveout.md)

**ADAPT** structural candidate discovery and file/symbol navigation; **REJECT**
graph authority over source. Require source-byte hashes, extractor/version and
derivation metadata, explicit stale/unknown output, bounded traversal and domain
partitioning. Existing Blaine navigation already excludes missing/mismatched
source digests. **OBSERVE** broader deployment until III.8 demonstrates benefit.
Costs include parser coverage, heuristic resolution, stale partial indexes,
watchers, per-project caches and optional model egress; global output/cache state
deserves isolation review. Graph links never extend readable ContextNode lineage.
[Watch/update][graph-watch], [paths][graph-paths],
[Blaine provider](../../../runtime/kernel/project_knowledge.py)

### 7.4 Claude Context

**SRC:** hybrid retrieval embeds the query, searches dense and sparse fields, and
combines results using reciprocal-rank fusion (`k=100` in the inspected core).
Milvus supplies BM25 sparse-vector machinery alongside dense storage. AST-aware
splitting keeps selected syntactic units, refines oversized chunks and falls back
to a LangChain splitter for unsupported languages or parse errors. AST chunks are
not compiler-level semantic understanding. [Core][claude-core],
[Milvus adapter][claude-milvus], [splitter][claude-splitter]

**SRC:** file hashes/Merkle snapshots identify added, changed and removed files;
the MCP synchronization manager defaults to periodic background synchronization
and a filesystem lock. This provides incremental machinery, not proof that a
result matches current worktree bytes at consumption time. Return revision/digest
and re-read evidence before acting. [Synchronizer][claude-sync], [MCP sync][claude-mcp-sync]

**REIMPLEMENT BEHIND BLAINE CONTRACT** a generic `code.semantic_search` capability;
**ADAPT** hybrid lexical/semantic retrieval and AST-aware chunking after a measured
need. **OBSERVE** the product as a provider candidate. Its Milvus/Zilliz storage
adds an operational system beside Blaine's PostgreSQL/pgvector. Embedding model,
dimension, preprocessing and index version must be compatible; BGE-M3's existing
deployment does not prove drop-in compatibility or retrieval quality here.
There are local-provider options, including an Ollama adapter, but using one is
not evidence of Blaine's vLLM path working. [Adapters][claude-embedding], [Milvus][claude-milvus]

**SRC security cost:** core search logs query text, codebase path and initial
embedding components. Collection naming and a caller filter expression do not
constitute runtime authority. **INFERENCE:** isolate or remove sensitive logging,
enforce server-derived scopes, govern embedding egress, and apply retention to
snapshots/chunks/vectors/logs. Do not use raw-source injection or a shared cloud
index by default. [Search implementation][claude-core]

### 7.5 agent-skills

**DOC:** descriptive routing metadata, focused SKILL.md bodies and supporting
references enable progressive disclosure. Shared repository-root references make
whole-package installation different from copying one skill directory.
**SRC/DOC:** evaluation separates structural checks, deterministic lexical routing
proxies (stemmed TF-IDF, positive and negative cases, description collisions), and
opt-in behavioral execution/transcript grading. Negative cases can require the
intended owner to outrank the wrong skill. [Anatomy][skills-anatomy],
[evaluation method][skills-evals], [runner][skills-runner]

**ADOPT** this separation of structural, routing and behavioral evidence; **ADAPT**
workflow contracts to Blaine's authority and completion rules. A workflow should
declare when to apply, exclusions, inputs, evidence expectations and permissions;
its text cannot grant capabilities. Learned procedures remain candidates until
versioned evaluation and admission, not self-installed instructions.

Costs/limits: behavioral runners invoke a model and grant executor tools in
throwaway repositories; model grading remains semantic evidence, not deterministic
Task completion. Lexical routing performance is not actual model routing accuracy.
Upstream reports stochastic skill invocation and measured plugin behavior; those
are **CLAIM/DOC**, not this track's results. Do not import a whole catalog, permission
mode or model-specific execution harness. [Runner][skills-runner], [evals][skills-evals]

### 7.6 Ponytail

**DOC/SRC:** its decision ladder checks need, existing code, standard library,
native features and installed dependencies before writing more code. It includes
root-cause/caller discovery and exceptions for security and explicit requirements.
Session hooks can inject a persistent persona; the review skill emits localized
complexity findings and replacements. [Core skill][pony-skill], [hook][pony-hook],
[review skill][pony-review]

**ADAPT** the ladder into a future bounded Simplicity Critic. **REJECT** always-on
personality, minimum-line-count as the optimization target, and blanket rejection
of single-implementation interfaces. An interface may express a real security,
testing or provider boundary. The critic should explain a concrete duplicate,
unnecessary dependency, scope expansion or speculative framework with evidence,
and allow justified abstractions.

**DOC/CLAIM:** its agentic benchmark separates correctness/safety checks from LOC
proxies and model-judged overengineering/completeness. This is useful experimental
discipline, not proof that its prompts reduce Blaine's architectural entropy.
Later evaluate both needless abstractions caught and legitimate abstractions
wrongly blocked; retain correctness/security as independent gates.
[Benchmark method][pony-benchmark]

### 7.7 OmniRoute

**SRC:** provider attempt execution, quota/reset-window scoring, circuit breakers
with persisted state, fallback decisions, usage normalization and event forwarding
are substantial plumbing mechanisms. They solve provider availability/account
selection problems. They do not establish which model can satisfy a Blaine Task's
criteria. [Attempt path][omni-attempt], [quota scoring][omni-quota],
[circuit breaker][omni-breaker]

**SRC/DOC:** usage can be upstream-reported or locally estimated, with estimation
markers in the accounting path; cost depends on pricing information. Telemetry
includes a best-effort dashboard bridge, while call-log artifacts can retain
pipeline payloads. **INFERENCE:** provider readiness/quota are observations with
age and confidence, not guaranteed budget or semantic suitability. Every hidden
retry/fallback must remain visible or UNKNOWN to Blaine accounting.
[Usage][omni-usage], [usage guide][omni-guide], [telemetry][omni-telemetry],
[call logs][omni-logs]

**OBSERVE** as a provider-plumbing candidate; **ADAPT** health/quota/usage concepts
only behind explicit contracts. **REJECT** delegation of workload/model suitability
or PolicyGate to the router, and unrestricted fallback to another model/provider.
A later integration must preserve approved destination, exact context bytes,
retry-domain limits, deadlines and data policy on every attempt. Optional context
handoff/compression paths must not alter Blaine's authorized packet silently.
Costs include a gateway service, SQLite state, credentials, price/quota freshness,
provider churn, logs and nested retry complexity. No adoption comparison against
existing plumbing was run. [Attempt path][omni-attempt],
[Blaine frontier contract](../../contracts/frontier-dispatch.md)

## 8. Workspace knowledge and broad discovery

| Plane | Question / authority | Proposed use |
| --- | --- | --- |
| Repository/git/artifacts/test outputs | What exists or actually happened? Authoritative within their scope/revision. | Verify consequential claims and completion. |
| Lexical discovery (`rg`, git, native tools) | Where is this name, text or change? | First broad deterministic search. |
| Semantic workspace retrieval | Where is related behavior expressed differently? Derived. | Candidate source locations, then read bounded source. |
| Structural workspace knowledge | How are symbols/components related? Derived. | Expand candidate neighborhoods under limits and source freshness checks. |
| Hierarchical Memory Plane | What did prior verified work teach us? Derived. | Scoped lessons, failures, preferences and procedures with provenance. |

**Broad discovery, narrow consumption:** enumerate/search broadly within the
authorized workspace and readable lineage; compile a small packet of current
source/evidence plus eligible lessons. Do not search unauthorized domains first
and filter the packet later. Missing/stale search coverage is explicit uncertainty,
not evidence that no equivalent abstraction exists.

Future Novelty Gate: before a significant class/interface/helper/service/wrapper,
search lexical names, semantic behavior, structural relations and inherited
lessons for an equivalent concept. Record candidate reuse locations and reasons
for reuse/rejection. Future Simplicity Critic: assess the resulting proposal for
duplication, unnecessary abstraction/dependency and expansion beyond scope.
These gates produce evidence/recommendations under existing authority; neither
can silently change completion criteria. III.9 should measure false positives
on legitimate security/provider boundaries as carefully as duplicate helpers.

## 9. Track III sequence and open risks

Each increment follows hypothesis → bounded research/experiment → retained
evidence → PASS/FAIL/BLOCKED → scoped architecture decision. No interesting
mechanism becomes a dependency just by appearing here.

| Increment | Question and minimum useful proof | Status |
| --- | --- | --- |
| III.1 | Which mechanisms fit existing Blaine boundaries? Pinned comparative source research. | PASS, this report |
| III.2 | Does generic tree visibility work? Pure deterministic evaluator against literal expected sets. | Proposed, not started |
| III.3 | Can ExecutionContext expose continuous bounded read/write operations? Isolated caller/adapter contract. | Future |
| III.4 | Are all representations and query paths isolated? Adversarial domain/access/cache/index tests. | Future |
| III.5 | Is promotion/declassification fail-closed and auditable? Synthetic leakage corpus and admission receipts. | Future |
| III.6 | Can verified outcomes feed reflection safely? Success/failure/unverified/cancelled evidence fixtures and durable admission. | Future |
| III.7 | Do lessons/procedures improve later work? Paired outcome evaluation, negative-transfer and utility controls. | Future |
| III.8 | Does combined workspace discovery improve awareness with smaller packets? Lexical baseline versus semantic/structural additions, freshness and recall measures. | Future |
| III.9 | Can Novelty/Simplicity gates reduce duplication without blocking warranted design? Labeled duplicate and legitimate-abstraction cases. | Future |
| III.10 | Does lineage survive children, durable waits/resumes and remote boundaries? Existing lifecycle integration with narrowing and revocation tests. | Future |

III.8 can later inform III.9 independently of lesson-quality experiments. III.4/5
are required before real cross-domain data/promotion; III.10 is required before
claiming durable distributed enforcement. III.2's mock scope checks certify none
of those later integration properties.

Unresolved questions and costs:

- **Topology and lifecycle:** who creates contexts; mapping/reuse across Tasks;
  immutable versus versioned parents; deletion/reparenting; snapshot versus current
  policy on resume. III.2 assumes immutable fixtures, not a production answer.
- **Storage enforcement:** MIRIX facade, separate per-domain instances, database
  policies or another partition boundary? No multi-tenant security proof yet.
  Duplicate indexes, caches and background services increase isolation/backup work.
- **Retrieval quality:** scope-distance weighting, conflict resolution, hybrid
  tuning, multilingual/code embeddings, stale indexes and empty-result semantics.
  No accuracy/latency/token-savings benchmark was run.
- **Provenance and retention:** protected receipts, revocation of promoted lessons,
  deletion through embeddings/graphs/caches/backups, and preserving evidence after
  short-lived runtime journals expire. Popularity/decay must not erase audit truth.
- **Learning validity:** verified outcome versus causal credit; unsafe advice from
  successful Tasks; contradictory and outdated lessons; prompt injection in stored
  observations; model-generated procedural policy changes.
- **Declassification:** who can approve it, supported identifier dictionaries and
  languages, near-match thresholds, semantic leakage and false-negative limits.
  A scanner plus an LLM is not a proven confidentiality guarantee.
- **Operations:** inference/embedding budgets, shared GPU contention, worker queues,
  scope-safe observability, runtime/provider retry ownership and measured adoption
  benefit. Health does not imply capability or successful completion.

## 10. Exact proposed III.2 experiment

**Authorization required; not implemented or run in III.1.**

Hypotheses:

- **H2.1:** effective visibility is exactly C plus permitted ancestors for every
  valid node; changing labels cannot change it.
- **H2.2:** ordinary writes affect only C and cannot increase any ancestor's,
  sibling's or other domain's observable knowledge.
- **H2.3:** runtime-derived lineage cannot be widened by query parameters, direct
  IDs, linked records, rank scores, cached results or caller-supplied scope claims.
- **H2.4:** invalid/unknown tree or policy fails closed with a bounded reason;
  arbitrary additional specialization levels require no new memory-engine cases.

Build only a standalone, standard-library reference evaluator under
`experiments/track-iii-002/`, with JSON fixtures and fake records. No runtime
imports/integration, MIRIX, database, embeddings, model, network, timers or workers.
This is an executable specification, not a production memory service.

Use this fixed tree: `r → {p,e}`, `e → {a,b}`, and
`a → epic → card → t → w → attempt → extra`. Add `t2` under `card` and `q`
under `p`. Give nodes opaque IDs; descriptive labels may be changed arbitrarily.
`p/q` are personal; `e/a/b/...` are employer-x. Root has only an explicitly
shareable public record. Every other node has one synthetic domain-tagged record.
Policies are trusted fixture inputs; missing policies deny. No real secrets or
proprietary material. Use literal expected IDs independent of traversal code.

| Case | Required observation |
| --- | --- |
| Read at `r` | Only root record. |
| Read at `e` | Root + employer record; neither project child. |
| Read at `t` | Exactly `r,e,a,epic,card,t`; no `b,t2,w,attempt,extra,p,q`. |
| Read at `q` | Exactly `r,p,q`; no employer record. |
| Deep read at `extra` | Full permitted ancestor chain through `attempt`; no special-case label behavior. |
| Relabel all nodes; add a synthetic intermediate level | Same rules and predictable one-node lineage extension; no label dispatch. |
| Ordinary write from `t` | Only `t` changes; new record visible at `t` and its permitted descendants, absent from `card,t2,b,q`. |
| Write requests targeting parent/sibling/root | Denied with no mutation. Promotion API is absent; no implicit copy. |
| Forged current context, parent list or scopes | Rejected/ignored in favor of trusted fixture identity; cannot widen reads. |
| Direct-ID or linked neighbor outside lineage | Denied before content is returned; graph links confer no ancestry. |
| High-scoring forbidden item or poisoned cache entry | Never rendered or passed to the mock ranking consumer; cache key includes context/policy revision. |
| A restricted root record plus a permitted public root record | Personal sees only eligible root content; sharing an ancestor does not override classification. |
| Unknown node/policy, cycle, missing parent, duplicate ID, multiple parents | Fail closed, no partial fallback, no record mutation. |
| Permuted fixture/input order | Identical authorized ID sets and stable documented output order. |
| Record payload claims success, authority, or new instructions | Returned only as typed data if eligible; cannot change evaluator policy or expected results. |

A small deterministic generated-tree sweep may supplement these fixed oracles:
for every node compare effective IDs to an independently specified ancestor set;
relabeling and inserting unrelated subtrees must preserve results. No retrieval
quality model or production cache is needed to test the negative paths above.

Retain `fixtures.json`, per-case `results.jsonl`, `summary.json` with expected vs
actual IDs, denied operation reasons, fixture/evaluator hashes and counts, plus
the reproducible command. Include a mutation control (deliberately allow siblings
or upward writes) that the suite must catch. These files are future deliverables,
not present experiment results.

**PASS:** every literal case and invariant passes, the mutation control fails as
expected, and there are zero unauthorized reads/writes. **FAIL:** a contradiction
between accepted semantics and a proven Blaine invariant requires a human decision;
an ordinary evaluator bug should be fixed within the increment. **BLOCKED:** an
essential premise/evidence source cannot be obtained. Report test failures as
failures, never reduce the oracle to fit the implementation. This proof cannot
certify provider isolation, secure declassification or distributed durability.

## 11. Stop boundary and III.1 decision

**PASS:** pinned evidence covers all seven references; repository integration
limits and classifications are explicit; a bounded III.2 oracle is specified;
no conflict with proven ownership was found. The machine-readable review records
this as a source-review conclusion, not a kernel CompletionVerifier receipt.

Do **not** implement ContextNode/runtime schemas, ExecutionContext propagation,
memory write tools, reflection jobs, promotion/declassification, security scanners,
Novelty/Simplicity gates, graph/vector deployment, provider routing, skills
installation, learned policy, or III.2's evaluator in this increment. Do not change
Kernel, Restate lifecycle, PolicyGate, Completion Contracts, worker execution,
D1/D2 or remote-execution behavior. Do not rerun live MIRIX seeding or past probes.

No human architectural decision is needed to close III.1. Explicit authorization
is needed to start the III.2 experiment above. Storage choice, declassification
authority and durable lineage revision policy remain later decisions.

<!-- Commit-pinned primary sources. Full provenance is in source-manifest.json. -->

[atomic-loop]: https://github.com/AtomicBot-ai/atomic-agent/blob/17d7d87a08c559c63b37e0ae0589eaff3e631b80/src/agent/agent-loop.ts
[atomic-context]: https://github.com/AtomicBot-ai/atomic-agent/blob/17d7d87a08c559c63b37e0ae0589eaff3e631b80/src/memory/memory-context-provider.ts
[atomic-old]: https://github.com/AtomicBot-ai/atomic-agent/blob/17d7d87a08c559c63b37e0ae0589eaff3e631b80/MEMORY.md
[atomic-hybrid]: https://github.com/AtomicBot-ai/atomic-agent/blob/17d7d87a08c559c63b37e0ae0589eaff3e631b80/src/memory/embeddings/hybrid-recall.ts
[atomic-profile]: https://github.com/AtomicBot-ai/atomic-agent/blob/17d7d87a08c559c63b37e0ae0589eaff3e631b80/src/memory/profile-store.ts
[atomic-reflection]: https://github.com/AtomicBot-ai/atomic-agent/blob/17d7d87a08c559c63b37e0ae0589eaff3e631b80/src/memory/reflection/reflection-runner.ts
[atomic-links]: https://github.com/AtomicBot-ai/atomic-agent/blob/17d7d87a08c559c63b37e0ae0589eaff3e631b80/src/memory/links/link-aware-reflection.ts
[atomic-consolidator]: https://github.com/AtomicBot-ai/atomic-agent/blob/17d7d87a08c559c63b37e0ae0589eaff3e631b80/src/memory/consolidator/consolidator-job.ts
[atomic-votes]: https://github.com/AtomicBot-ai/atomic-agent/blob/17d7d87a08c559c63b37e0ae0589eaff3e631b80/src/memory/voting/vote-store.ts
[atomic-notes]: https://github.com/AtomicBot-ai/atomic-agent/blob/17d7d87a08c559c63b37e0ae0589eaff3e631b80/src/memory/memory-store.ts
[atomic-rewriter]: https://github.com/AtomicBot-ai/atomic-agent/blob/17d7d87a08c559c63b37e0ae0589eaff3e631b80/src/memory/retrieve/rewriter-aware-recall-provider.ts
[atomic-guide]: https://github.com/AtomicBot-ai/atomic-agent/blob/17d7d87a08c559c63b37e0ae0589eaff3e631b80/MEMORY_GUIDE.md
[mirix-api]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/rest_api.py
[mirix-filter]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/database/filter_tags_query.py
[mirix-distiller]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/services/session_experience_distiller.py
[mirix-curator]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/services/skill_experience_curator.py
[mirix-vault]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/orm/knowledge_vault.py
[graph-extract]: https://github.com/Graphify-Labs/graphify/blob/a5957aa6ef51c9be8d054de9783d25046c187f3f/graphify/extract.py
[graph-build]: https://github.com/Graphify-Labs/graphify/blob/a5957aa6ef51c9be8d054de9783d25046c187f3f/graphify/build.py
[graph-serve]: https://github.com/Graphify-Labs/graphify/blob/a5957aa6ef51c9be8d054de9783d25046c187f3f/graphify/serve.py
[graph-watch]: https://github.com/Graphify-Labs/graphify/blob/a5957aa6ef51c9be8d054de9783d25046c187f3f/graphify/watch.py
[graph-paths]: https://github.com/Graphify-Labs/graphify/blob/a5957aa6ef51c9be8d054de9783d25046c187f3f/graphify/paths.py
[claude-core]: https://github.com/zilliztech/claude-context/blob/6fc318b4e3ce58e2898b00a9c3538ead9e24dee5/packages/core/src/context.ts
[claude-milvus]: https://github.com/zilliztech/claude-context/blob/6fc318b4e3ce58e2898b00a9c3538ead9e24dee5/packages/core/src/vectordb/milvus-vectordb.ts
[claude-splitter]: https://github.com/zilliztech/claude-context/blob/6fc318b4e3ce58e2898b00a9c3538ead9e24dee5/packages/core/src/splitter/ast-splitter.ts
[claude-sync]: https://github.com/zilliztech/claude-context/blob/6fc318b4e3ce58e2898b00a9c3538ead9e24dee5/packages/core/src/sync/synchronizer.ts
[claude-mcp-sync]: https://github.com/zilliztech/claude-context/blob/6fc318b4e3ce58e2898b00a9c3538ead9e24dee5/packages/mcp/src/sync.ts
[claude-embedding]: https://github.com/zilliztech/claude-context/blob/6fc318b4e3ce58e2898b00a9c3538ead9e24dee5/packages/core/src/embedding/ollama-embedding.ts
[skills-anatomy]: https://github.com/addyosmani/agent-skills/blob/bcab6a1b8503100e8618c3b4e32cc78de43de769/docs/skill-anatomy.md
[skills-evals]: https://github.com/addyosmani/agent-skills/blob/bcab6a1b8503100e8618c3b4e32cc78de43de769/evals/README.md
[skills-runner]: https://github.com/addyosmani/agent-skills/blob/bcab6a1b8503100e8618c3b4e32cc78de43de769/scripts/run-evals.js
[pony-skill]: https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/skills/ponytail/SKILL.md
[pony-hook]: https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/hooks/ponytail-activate.js
[pony-review]: https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/skills/ponytail-review/SKILL.md
[pony-benchmark]: https://github.com/DietrichGebert/ponytail/blob/e3ba2aa6f1e6f0bc4d69eb09c9f0d0a93af56156/benchmarks/agentic/README.md
[omni-attempt]: https://github.com/diegosouzapw/OmniRoute/blob/18bbb101980c639cfabdc5663213836d917c3269/open-sse/services/combo/executeTargetAttempt.ts
[omni-quota]: https://github.com/diegosouzapw/OmniRoute/blob/18bbb101980c639cfabdc5663213836d917c3269/open-sse/services/combo/quotaScoring.ts
[omni-breaker]: https://github.com/diegosouzapw/OmniRoute/blob/18bbb101980c639cfabdc5663213836d917c3269/src/shared/utils/circuitBreaker.ts
[omni-usage]: https://github.com/diegosouzapw/OmniRoute/blob/18bbb101980c639cfabdc5663213836d917c3269/open-sse/utils/usageTracking.ts
[omni-guide]: https://github.com/diegosouzapw/OmniRoute/blob/18bbb101980c639cfabdc5663213836d917c3269/docs/guides/USAGE_QUOTA_GUIDE.md
[omni-telemetry]: https://github.com/diegosouzapw/OmniRoute/blob/18bbb101980c639cfabdc5663213836d917c3269/open-sse/handlers/chatCore/telemetryHelpers.ts
[omni-logs]: https://github.com/diegosouzapw/OmniRoute/blob/18bbb101980c639cfabdc5663213836d917c3269/src/lib/usage/callLogArtifacts.ts
