# Durable Cognitive Loop — architecture checkpoint

> Adopted Increment 8 amendment: cognition proposes semantic work; runtime determines
> whether cognition is necessary. After authoritative evidence changes, evaluate the
> unchanged CompletionContract first; complete if satisfied, otherwise suspend for
> an explicit blocking dependency, otherwise derive hard-admissible semantic actions
> and invoke cognition. Known human waits do not need model WAIT; completion does not
> need model COMPLETE. Both old actions remain representable pending scoped vocabulary
> cleanup. This supersedes any older sequencing below that required these proposals.
> [Approval implementation and evidence](../milestones/024-cognitive-kernel-increment-8-passed.md).


**2026-09-19 · Proposed reconciliation for human review · No runtime implementation**

Keep Blaine's existing authority model and introduce **one Cognitive Loop
algorithm, instantiated once per durable Task**. Specialists can successively
own that Task's cognitive turns; independent objectives become child Tasks with
their own loops. Restate preserves execution and enforces transitions through
Blaine code. Models decide semantic behavior. Neither memory nor harness success
establishes authority or completion.

This checkpoint reconciles [BLAINE.md](../../BLAINE.md) (`AGENTS.md` is its
symlink), all [ADRs 0001–0017](../decisions/), the [architecture](../architecture.md),
[TaskSpec](../contracts/task-spec.md), [operations](../contracts/task-operations.md),
current policies, the three carveouts below, and the current runtime/Task code.
Repository baseline: `cb347c2294d55120fd0eb9036c52c3b0af05b7b9`.
**Observed** below means source inspection or explicitly attributed prior
evidence; **proposed** semantics have not been executed or validated here.

## 1. Definition and Task scope

The Cognitive Loop is the repeated selection and execution of the next permitted
action toward an accepted objective, using reconstructed context and observable
results:

```text
observe authoritative Task state, new input, and evidence
  → reconstruct relevant, permitted context
  → bounded cognitive turn by the active specialist
  → structured next action
  → validate and enforce
  → execute
  → persist result and evidence
  → evaluate completion eligibility
  → repeat, wait, or terminate through runtime authority
```

These are execution boundaries, not model thought states. Clarifying,
researching, strategizing, implementing, reviewing, asking a human, and revising
strategy remain semantic choices. The runtime records the accepted decision and
strategy revision; it does not prescribe a `PLAN → IMPLEMENT → REVIEW` graph.
Spec Kit supplies optional procedures, skills, and artifact conventions to the
turn. A deterministic operation needs no additional model reasoning merely
because it executes inside a Task.

Each Task has one logical loop and one active cognitive owner at a time. An
owner is a specialist definition/role, not an immortal worker process. Runtime
identity, objective, policy, and CompletionContract survive worker, harness,
model, and session replacement. Blaine's persistent personal identity also
survives specialist handoffs. Direct conversation remains outside the durable
Task boundary when the response itself satisfies the request.

A child has its own accepted objective, context, completion criteria, policy and
budget allocation, state, and loop. It can fail, wait, or recover independently;
the parent interprets its typed result against the parent's own contract. Child
success does not establish parent success. Parent/child ancestry is durable
coordination metadata, not transcript nesting.

## 2. ACTION, HANDOFF, and SPAWN_TASK

Here **ACTION** means the bounded execution primitive `INVOKE_CAPABILITY`;
`NextAction` is the encompassing five-variant decision vocabulary.

| NextAction | Ownership and smallest semantics | Example |
|---|---|---|
| `INVOKE_CAPABILITY` | Current Task and cognitive owner consume one bounded request/result. No ownership transfer. An agent can itself be a bounded capability. | Read a file, run tests, query MIRIX/project knowledge, post an authorized YouTrack comment, call MCP/API, request a specialist critique. |
| `HANDOFF` | Transfer the next cognitive turn to an eligible specialist **within the same Task**. Persist target, context packet reference, and decision identity before its dispatch. Objective, lifecycle, and authority do not change. | Architecture specialist → Java specialist. |
| `SPAWN_TASK` | Submit a child TaskSpec through normal acceptance with its own CompletionContract, scoped context, policy/budget allocation, and expected typed result. Persist the accepted child identity and dependency. | Research a library independently, return findings and evidence to an implementation Task. |
| `WAIT` | Register an identifiable external input, human decision, dependency, resource condition, or deadline and a durable continuation. A reason alone is insufficient: specify what resolves the wait. | Await approval for a specific action or clarification of one requirement. |
| `COMPLETE` | Submit a candidate result for verification. Only application of the accepted CompletionContract can record `COMPLETED`. | Submit report/artifact references and evidence for acceptance. |

All three execution primitives are independent of parallelism. The initial
kernel can execute both sequences entirely serially:

```text
Task T: Blaine → HANDOFF Architecture → HANDOFF Java → COMPLETE request

Task P: SPAWN research Task C → durable wait → consume C.TaskResult
        → HANDOFF implementation specialist → continue P
```

Spawning also compresses context: C may gather extensive history; P receives a
bounded result, artifact/evidence references, and material uncertainties. It
retrieves supporting source sections only when needed. Neither spawning nor
handoff automatically forwards an ancestor's transcript.

No concrete counterexample requires expanding the vocabulary. A clarification
uses a coordination capability followed by `WAIT`; a strategy revision is
decision metadata accompanying the next action. Technical retry, cancellation,
and terminal failure are runtime policies/operations, not additional model
thought actions. A handoff is not an implicit call/return stack: return to a
previous specialist requires another handoff.

## 3. Smallest v1 contract semantics and wire decision

Contracts describe boundaries; they need not become separate classes/services.

| Contract | Minimum meaning |
|---|---|
| **TaskSpec** | Preserve existing required `objective` and `completion`; retain optional context needs, capabilities, autonomy, cloud policy, mode, and schedule. It contains intent, not runtime identity, a workflow graph, or worker internals. |
| **TaskState** | Runtime-owned identity, accepted spec/revision, lifecycle, active specialist, current decision/action reference, waits/children, applicable policy/budget accounting, and result/evidence references as applicable. Keep phase/strategy separate from lifecycle. |
| **CognitiveTurn input** | Task/revision and turn identity, objective and criteria, active specialist instructions, bounded context with provenance, recent relevant observations/verifier findings, eligible capabilities, and current authority/resource limits. No mandatory full history. |
| **CognitiveDecision / NextAction** | One typed next action for the supplied revision, with its variant payload; optional concise decision explanation and strategy update. No private reasoning transcript required. Invalid or stale decisions cannot dispatch. |
| **Capability request/result** | Stable operation identity, capability and bounded input/context, effective permissions, expected result shape; response distinguishes outcome, receipt/pending effect, artifacts/evidence, errors, continuity, and known/unknown usage. Transport success is not effect confirmation. |
| **TaskResult** | Versioned bounded output tied to Task identity and authoritative outcome, deliverables, criterion/verifier evidence, and unresolved concerns. The accepted request specifies the small domain result shape; failures/cancellation can retain partial artifacts. No child transcript. |
| **CompletionContract** | Existing acceptance criteria resolved to applicable verifiers and required evidence at acceptance. Findings distinguish satisfied, unsatisfied, and unknown against specific artifact/source revisions. Only authorized revisions may weaken/change criteria. |
| **PolicyGate** | Code-owned evaluation of proposed dispatch/transition against accepted authority, state/revision, scopes, budget, and egress. Returns allow, deny, or input/approval required with a reason. An allow is scoped to that operation and policy revision. |

**Decision: cross-boundary data is versioned JSON-compatible typed data.** Use a
small envelope (`version`, `kind`, `payload`); TaskSpec's existing payload meaning
stays intact. JSON Schema is useful for Task acceptance, the action discriminated
union, and worker/child result validation. Reject unknown action kinds and
unsupported versions before effects. Schema validation establishes shape, not
authorization or completion. Native SDK/Pydantic types are implementation aids.

Illustrative envelope only, not a new exhaustive schema:

```json
{
  "version": 1,
  "kind": "CognitiveDecision",
  "payload": {
    "task_id": "T",
    "task_revision": 3,
    "turn_id": "T/7",
    "next_action": {
      "type": "HANDOFF",
      "specialist": "java",
      "context_ref": "artifact:T/context/7"
    }
  }
}
```

Action payloads need only the capability/input, handoff target/context, child
spec/result expectation, wait condition, or completion candidate respectively.
Use references for large artifacts, with source revision/digest where evidence
depends on exact contents. Raw Python objects, SDK agent instances, exceptions,
and provider sessions are not the wire contract. YAML examples in today's docs
are human-readable authoring; any future YAML loader must normalize and validate
the same JSON representation. YAML is not the canonical runtime format.

## 4. Existing runtime and verified Restate baseline

**Observed repository pins:** Server **1.7.9** in
[setup-runtime.sh](../../scripts/setup-runtime.sh), Python **restate-sdk 1.0.5** in
[requirements.txt](../../runtime/requirements.txt). The setup script reuses an
existing binary rather than enforcing its version. This checkout has no local
runtime binary/venv to inspect; these are repository pins, not a claim about a
currently running host. No service was started for this review.

[app.py](../../runtime/app.py) journals an objective summary and waits on a timer.
[interactive.py](../../runtime/interactive.py) adds one named promise and a
shared `proceed` handler; any nonblank message completes that fixture.
[task.py](../../runtime/task.py) validates only objective/delay and computes a
digest/word count. [acp_agent.py](../../runtime/acp_agent.py) supports create,
status, and continue commands; ACP cancellation does not cancel a durable Task.
Neither fixture implements full TaskSpec acceptance, cognitive decisions,
handoff/spawn, policy gates, or evidence-based completion. Its `NOT_FOUND` also
means state not yet initialized, not authoritative absence.

[Milestones 001](../milestones/001-runtime-skeleton.md) and
[002](../milestones/002-intellij-acp-durable-task.md) record recovery and
session-independence evidence. Those experiments were not rerun here and do not
validate the proposed kernel. Both apps name `TaskWorkflow` but use separate
spike deployments/configuration; retain them as fixtures rather than changing
live journal semantics in place.

**Official documentation/source checked on 2026-09-19:** the native primitives
below remain documented. SDK v1.0.5 resolves to source
`ad4ea7c0a60b5745681a809fe57656bec0939c38` (also upstream `main` at inspection).
Its [Context API][sdk-context] includes `run_typed`, Workflow calls, promises,
`signal`/`resolve_signal`, and cancellation. The [Server 1.7.9 protocol][protocol]
contains named signals. This establishes source support; repeated-signal ordering,
deduplication and cancellation still need integration evidence on the pinned pair.
The optional OpenAI integration exists in that SDK but is **not installed by the
repository requirements**; its extra declares `openai-agents>=0.6.1`, not a tested
locked integration stack. [SDK dependencies][sdk-deps]

## 5. Blaine → Restate primitive → reason / limitation

| Blaine concept | Restate primitive | Reason / limitation |
|---|---|---|
| One Task-scoped loop | **Proposed v1:** one `Workflow`, keyed by Task ID, with one main `run` | Run-once identity and durable continuation fit the existing spike. Shared handlers stay callable during execution/retention. This is a v1 mapping, not the definition of Task. [Workflows][services] |
| TaskState / active owner | Workflow `ctx.get`/`ctx.set`; main handler is sole writer | Shared handlers read state and deliver input; they cannot mutate state. Semantic owner is explicit data, not a process pointer. [State][state] |
| Observation/context/model turn | Bounded `ctx.run_typed` for nondeterministic reads or inference | Persist the actual output used for decisions. Replay reuses committed results; later turns can deliberately refresh context. Do not wrap the entire loop in one run step or call Restate Context APIs inside it. [Durable steps][steps] |
| `INVOKE_CAPABILITY` | Local bounded operation in `run_typed`, or `service_call` to a capability handler | A service call is already durable; do not wrap it in `run`. External effects need idempotency/reconciliation where effect succeeds before its result is journaled. A subprocess is not automatically a durable worker. [Calls][calls], [recovery][recovery] |
| `HANDOFF` | Journal decision; update active specialist/context in the same Workflow; dispatch next turn | No special Restate server handoff primitive. The OpenAI integration supplies an SDK-specific durable handoff pattern; a remote service call alone does not define cognitive ownership. [Handoffs][multi-agent], [SDK implementation][sdk-runner] |
| `SPAWN_TASK` | New Task-keyed Workflow via `workflow_call` or `workflow_send` | Child acceptance, identity and output remain explicit. Proposed v1 awaits one child via `workflow_call` and catches its terminal outcome; this permits independent child recovery without concurrent semantic work. [Calls][calls] |
| Child wait/result | Await durable call result; sends may retain invocation ID and attach later | v1 uses a joined child; normal call-graph cancellation cascades. Detached sends survive parent cancellation and require an explicit child cancellation/ownership policy. Do not infer lifecycle independence from a send receipt. [Calls][calls], [cancellation][invocations] |
| Human/steering input | Shared handler validates input; `ctx.signal` to main invocation, or named workflow promise for one-shot input | Signals can queue repeated deliveries; promises resolve once per name. Repeated promise waits require distinct IDs. Blaine still validates actor, request ID, wait ID, revision and authority; resolving a primitive is not semantic approval. [External events][events] |
| Timed/resource wait | `ctx.sleep`, durable call/promise/signal, optionally `restate.select` with a timer | Runtime suspends/resumes; no conversational timer or polling ledger. A timeout does not establish that an external effect stopped. [Timers][timers] |
| Technical failure/retry | Restate retry policy, `RunOptions`, `TerminalError` | Bound retries; return evidence for semantic replanning. Default infinite retries must not silently spend an unbounded budget. A handled capability failure need not terminate its Task. [Errors][errors] |
| Task cancellation | Authorized binding → cancellation by invocation ID; adapter cleanup and durable outcome handling | Cooperative, asynchronous, surfaced at await points; in-flight run effects may finish. Calls propagate cancellation; sends are detached. `kill` bypasses compensation. ACP turn cancellation is separate. [Cancellation][invocations] |
| Recovery/replay | Invocation journal + stable deployment/code and persisted decisions | Reconstruct execution from recorded operations, not chat. Uncommitted nondeterministic work can rerun. Keep compatible deployed code and specialist definitions available; deployment replacement must respect journal compatibility. [Recovery][recovery], [versioning][versioning] |
| Completion / TaskResult | Blaine verifiers and gate, followed by state write and Workflow result | Restate completion means a handler ended; Blaine completion means the contract passed. The two must be deliberately connected in code. |
| Retained evidence/results | Small runtime references plus durable artifacts; explicit workflow/journal retention | Workflow state/promises expire after configured postcompletion retention (default 24h). Existing `default-journal-retention = "1 day"` is not an archival policy or workflow-retention setting. Archive result/evidence and define lookup/expiry semantics. [Retention][configuration] |

These are native handlers, journaled operations, state, calls, signals/promises,
and timers. No Temporal Activity abstraction or thought-state machine is needed.

## 6. What the official OpenAI Agents handoff pattern actually guarantees

The current [Restate multi-agent guide][multi-agent] and its
[pinned example][example] use an intake Agent with `handoffs`, `DurableRunner`,
`RestateSession`, and a **Virtual Object keyed by conversation**. That example is
evidence for durable routing, not a mandate to make Blaine session-scoped.

| Question | Verified mechanism and Blaine consequence |
|---|---|
| How is routing durable? | The model emits the handoff selection in its response. `RestateModelWrapper.get_response` journals that response through `run_typed("call LLM", ...)`, including output/tool calls. The SDK processes the recorded selection. [Runner source][sdk-runner] |
| Crash after a committed selection? | Handler/SDK code replays using recorded model responses and durable tool results, reconstructing the selected specialist instead of asking the router again. An unfinished/uncommitted call can execute again. The source does not implement an atomic, separate server-side “handoff transaction.” |
| What about callbacks and tools? | The handoff wrapper invokes `on_invoke_handoff` and wraps returned agent tools; it does not independently journal arbitrary callback effects. Tool functions must place external work behind durable operations or calls. Filters/hooks must be deterministic or consume journaled inputs. [Tool/handoff source][sdk-functions] |
| Where is the active/last agent retained? | During a run it is reconstructed by replay. The example writes `result.last_agent.name` to `last_agent_name` **after the run returns**, then reloads it for the next invocation. It does not maintain a live active-owner checkpoint at every handoff. Blaine should persist its own accepted specialist transition before the next turn. [Example][example], [OpenAI result semantics][oai-results] |
| What context moves? | The example shares conversation context automatically. `RestateSession` loads/stores the `items` history, buffers additions, and is flushed by the runner. It supplies persistence, not per-specialist minimization. [Session source][sdk-session] |
| Can it be filtered? | OpenAI explicitly supports filtered handoff history/structured metadata. The Restate wrapper preserves other handoff fields when replacing its invocation callback. This is a possible adaptation seam, not demonstrated minimum-context enforcement. [OpenAI orchestration][oai-orchestration], [wrapper][sdk-functions] |

**Reconciliation:** unrestricted native history sharing conflicts with Blaine's
minimum-sufficient context rule, but handoff itself does not. A handoff packet
must carry objective, criteria, critical evidence, uncertainty and constraints
for the receiving specialist. Revalidate retrieval/egress permissions and prevent
session history or provider continuation from silently restoring excluded data.
For v1, explicit Task-level handoff followed by a fresh bounded turn is the
simplest harness-neutral choice. Native SDK handoffs can later implement that
contract only after filtering, policy interception and replay tests pass.

The Restate example's prose suggests a main agent continues after all subagents
return; its OpenAI code instead returns the final specialist's output. Treat this
as illustrative multi-framework wording, not call/return or parallelism semantics.
OpenAI's [own distinction][oai-orchestration] is ownership transfer for handoffs
and retained manager ownership for agents-as-tools. Neither creates a Blaine child
Task automatically.

## 7. Policy and enforcement points

1. **Acceptance:** validate/normalize TaskSpec, resolve verifiable criteria,
   record authority and policy revision, and assign stable identity. Capability
   requirements never grant permissions. YouTrack's approved Downstream envelope
   can supply authority under ADR 0017; a comment or model interpretation cannot
   invent it.
2. **Before inference/retrieval:** enforce source scopes, freshness expectations,
   worker suitability, sharing and context budget. Retrieved memory is data, not
   instructions that can expand authority.
3. **Before every effect or transfer:** validate action/revision, target
   eligibility, mutation scope, authorization, child budget allocation, and
   context egress. Cloud selection, cloud authorization and permitted content are
   separate gates. Reapply limits to every retry and nested harness/provider call.
4. **Across recovery and signals:** persist decisions and stable operation IDs;
   deduplicate external input and reconcile uncertain effects. Main handler
   serializes accepted steering and action admission. Specify when revocation
   takes effect; input received during an already-dispatched operation cannot
   retroactively prevent that effect.
5. **Before completion:** verify required criteria against actual versioned
   artifacts/effects and record findings. Missing/contradictory evidence returns
   an observation for another turn or a justified wait. A review finding may use
   a model, but code applies the contract and required independent checks.

Child policies may narrow inherited authority; they cannot mint new permissions
or duplicate the parent's remaining budget. Budget reservations/accounting must
cover child and retry usage. Missing usage (as observed in Multica) is unknown,
not zero. Hard enforcement belongs in dispatch credentials, tool access, sandbox
and runtime code, not only in the prompt. Approval binds a concrete action and
scope; it is not a permanent grant to whichever agent next owns the Task.

## 8. Capability seams and retained research conclusions

| Seam | Smallest useful boundary and evidence |
|---|---|
| Context resolution | Resolve stated needs into a permitted packet with source/version, observation-versus-inference, exact evidence where needed, and known gaps. Use files/search first; substantial preparation may itself be a child Task. No universal context platform is required for v1. |
| Memory | MIRIX query/ingestion is a capability. The [MIRIX report](mirix-carveout.md) records local persistent Core/Episodic/Semantic memory, but also unsupported elaboration, scope defects and failed writes hidden by agent-level success. Verify material writes; memory is neither enforcement nor credentials nor Blaine's identity owner. Its later live checkpoint takes precedence over stale source-only “PG18 unverified” rows in that report. |
| Project knowledge | Git/source is authority; Graphify/SCIP are derived retrieval aids. The [Graphify report](graphify-carveout.md) establishes a useful deterministic seam with freshness/provenance/relationship-loss counterexamples. Recheck source for consequential claims; index confidence is not proof. No new SCIP evaluation is implied. |
| Worker/harness | Bounded request → observable result through Codex, Goose or future adapters. The [Multica report](multica-carveout.md) validates standalone execution/resume but exposes silent fresh-session fallback, auto-approval behavior and incomplete interruption/accounting results. Reuse only behind explicit authority, continuity and effect-reporting semantics. No extraction or adoption follows here. |
| Capability routing | Select sufficient eligible implementations by required capability/quality, then enforce resource and authority constraints. A specialist role, worker attempt, harness, model and provider are distinct. Sequential specialists are first-class. |
| Human coordination | YouTrack reads/comments/updates are capabilities; prompts/procedures supply conventions. Code enforces actor/envelope authority. Card ownership/status is not a worker lock or Task completion. |
| Verification/artifacts | Preserve addressable outputs and independently observed effects; verifiers consume criteria plus evidence. Artifact storage may start as controlled files with digests, not a new service. |

## 9. Boundary map

These are responsibility boundaries, **not a service decomposition**.

| Boundary | Owner / retained responsibility |
|---|---|
| Human Coordination | YouTrack is already selected by ADR 0017; human-facing Cards and decision envelopes. |
| Personal Agent / Semantic Identity | Blaine interprets intent and presents results; persistent semantic context supports continuity. MIRIX remains a candidate memory implementation. |
| Cognitive Loop | One algorithm selecting the next action from observations/context through bounded semantic turns. |
| Task / Delegation | Durable objective and acceptance; same-Task handoff versus child Task identity/results. |
| Context Resolution and Economy | Just-in-time selection, provenance, compression and specialist-specific packets; permissions survive derivation. |
| Capability / Worker Routing | Suitability and quality selection; resource allocation stays separate from semantic requirements. |
| Durable Execution and Enforcement | Restate plus Blaine code: lifecycle, journal, recovery, waits, retries, policy and completion transitions. |
| Worker / Harness Execution | Replaceable Codex/Goose/future execution, with operational attempt IDs and optional session reuse. |
| Artifact / Evidence / Completion | Addressable results, verifiers and accepted CompletionContract; worker assertions alone are insufficient. |
| Long-term Knowledge | Git/source and authoritative external systems; derived project knowledge; MIRIX personal/semantic memory with provenance. No shadow execution ledger. |
| Development Infrastructure | Process Compose/SecretSpec candidates; PostgreSQL, Redis, shared vLLM and future ingress. Supervision/readiness/secrets do not determine Task lifecycle. See [infrastructure research](devenv-carveout.md). |

## 10. ADR reconciliation and remaining decisions

No accepted ADR requires replacement of the fundamental architecture. The
following is a proposed disposition; **no ADR is edited or superseded here**.

| Existing ADR | Proposed disposition | Reconciliation |
|---|---|---|
| 0001 — Task unit | Keep unchanged; complement | One loop per Task makes session independence concrete. |
| 0002 — IntelliJ ACP | Keep unchanged | First client choice does not constrain loop ownership. |
| 0003 — Restate evaluation | Amend | Decision still says evaluate before adoption, while validation and ADR 0015 select it. Record accepted foundation and bounded evidence; do not imply every cancellation/recovery case passed. |
| 0004 — Personal Agent | Complement | Entry triage remains; semantic decisions also occur within the durable Task after conversation ends. |
| 0005 — Work Strategy | Amend | Strategy labels already are not lifecycle states. Clarify one shared loop, with procedures/strategy metadata instead of separate mandatory workflow families. |
| 0006 — Spec Kit | Amend | Optional phases remain cognitive procedure; “runtime controls workflow position/phase acceptance” must mean recording decisions and enforcing explicit gates, not choosing the next reasoning phase. |
| 0007 — Tools first | Keep unchanged | Applies to observations, capabilities and verification inside the loop. |
| 0008 — Cloud dispatch | Keep unchanged; complement | Enforce across turns, handoffs, child allocation and nested adapters. |
| 0009 — Context packets | Keep unchanged; complement | Retain mandatory cloud packet; generalize minimum-sufficient specialist context locally too. |
| 0010 — Worker selection | Complement | Distinguish specialist ownership from bounded capability invocation; no parallelism requirement. |
| 0011 — Local resource scheduler | Keep unchanged as Proposed | Scheduling remains independent of thought and delegation. |
| 0012 — Protocol neutrality | Complement | Versioned JSON semantic contracts across adapters; no new transport framework. |
| 0013 — Protected context | Keep unchanged as Proposed | Do not promote speculative transformation machinery into a v1 prerequisite. Enforce currently applicable sharing restrictions. |
| 0014 — Project knowledge | Keep unchanged as Proposed/Deferred; complement | Preserve source authority and distinct derived knowledge/memory seams; carveout findings do not validate the whole ADR. |
| 0015 — Execution/verification | Amend and complement | Its mapping flexibility permits the v1 Workflow choice. Replace ambiguous “runtime may change strategy/use a different model” with semantic proposal versus enforced execution. Add explicit same-Task cognitive ownership without giving workers lifecycle authority. |
| 0016 — Replaceable harnesses | Complement | Private harness subagents stay implementation details; an explicit Blaine HANDOFF/SPAWN crossing this boundary follows the Task contract. |
| 0017 — Human coordination | Keep unchanged; complement | Carry approved envelope into enforceable authority; preserve Blaine/Wolf distinction and Card/Task separation. |

**Supersede: none recommended.** Complement through two small future ADRs:
(a) Task-scoped Cognitive Loop and the five actions/contracts, including JSON;
(b) native Restate kernel mapping, recovery/effect semantics and result retention.
Amendments above should reference those decisions after human review.

Concrete unresolved points and contradictions to carry forward:

- **Procedure versus lifecycle:** ADRs 0005/0006/0010 and the Spec Kit sequence
  diagram still foreground phase workflows. ADR 0015 explicitly forbids thought
  states. Reconcile language and tests around semantic choices plus hard gates.
- **Policy compilation:** current TaskSpec autonomy/completion are prose. Define
  which initial capabilities/criteria can be bound to enforceable checks;
  unsupported checks need explicit human verification or rejection, not fabricated
  deterministic authority.
- **Cancellation and ancestry:** approve v1 joined-child cascading cancellation;
  independent lifetime via detached send remains a later explicit policy. Prove
  adapter cancellation and effect reconciliation before real mutations.
- **Retention and upgrades:** choose concrete Task-result retention/archival and
  compatible deployment lifetime before long-lived production use. One logical
  loop need not mean one forever-growing invocation; rollover is deferred until
  measured need, while preserving Task identity and decisions.
- **Steering:** define deduplication, stale-revision rejection, approval expiry,
  and the admission point for policy changes during execution. Primitives alone
  do not settle these semantics.
- **Native handoff adoption:** pin a tested OpenAI Agents dependency and prove
  context filtering/policy interception before using native handoffs as Blaine
  ownership transfer. The first kernel need not depend on that integration.
- **Documentation drift, not redesign:** Milestone 001 still calls ADR 0003
  Proposed; the ADR is now Accepted/Validated. The older refactor plan's fixed
  six-state taxonomy is not current lifecycle authority. Existing YAML examples
  do not establish a wire-format decision. Leave these documents unchanged here.

## 11. Smallest executable Cognitive Kernel to implement next

After architectural review, implement a separate, versioned Task Workflow slice
using the pinned Python stack. Its main handler should accept a minimal TaskSpec,
maintain TaskState, reconstruct a small file-backed context packet, obtain and
journal one typed decision, gate it, dispatch one of the five actions, retain
evidence, and apply a deterministic CompletionContract. Shared status/input
handlers expose authoritative state and durable steering. Bound turns, attempts,
and child creation through policy; exhausting a bound records a justified
failure/wait rather than false completion.

Use a scripted decision adapter first to challenge lifecycle guarantees, then
one bounded local model adapter to demonstrate semantic choice. Add two simple
specialist definitions, one read capability, one fixture artifact-producing
capability, a verifier, and one sequential child Task. Persist accepted handoff
owner/context explicitly. Gate denial becomes an observation or approval wait;
it never executes the denied action. A failed COMPLETE request retains missing
criteria and returns them to the next turn.

This slice needs no native OpenAI handoff dependency, paid provider, real YouTrack
mutation, MIRIX/Graphify integration, generic scheduler, new UI, or service per
boundary. These remain concrete capability adapters to add only when needed.
The kernel dispatches effects; a cognitive decision adapter must not bypass it
by executing unrestricted tools during decision generation.

## 12. Proposed validation sequence and stop condition

| Order | Smallest validation | Required observable evidence |
|---|---|---|
| 1 | Contract/policy fixtures | Invalid versions/actions and stale decisions rejected; prose criteria bound to explicit verifier/human gate; denied effects never reach fake adapters; budget/permission cannot expand through handoff/spawn. |
| 2 | Sequential kernel with scripted decisions | All five actions exercised; same Task ID across two handoffs; child has distinct identity/spec/loop; parent receives only bounded TaskResult; at most one semantic execution active in the scenario. |
| 3 | Completion adversarial cases | Worker says done with missing evidence: Task remains incomplete. Add verified evidence: completion succeeds. A Card-verification Task can succeed while reporting the Card incomplete. |
| 4 | Real Restate crash/replay | Kill endpoint/server after journaled decision, after owner transition, during child wait and human wait, and after effect but before recorded response. Compare decision/child IDs and recorded results; effect counter/idempotency receipt establishes duplicates or reconciliation, not journal length alone. |
| 5 | Input/cancellation/retention | Duplicate/stale approvals, repeated signals or successive promise waits, cancel during capability/child wait, detached-send control, client loss, and result expiry. Distinguish request accepted from effect/cancellation completed; verify cleanup and partial evidence. |
| 6 | Context and replaceability | Specialist excludes irrelevant/restricted sentinel data yet retains necessary evidence; parent excludes child history. Replace session/adapter without losing Task state. Native handoff, if evaluated, must meet the same tests and replay without fresh routing. |
| 7 | Local semantic choice | A small task set produces different valid action sequences from evidence using the same loop. Policy blocks attempted overreach; failed verification causes semantic revision. Record packets, decisions, artifacts, verifier findings and costs/limits. |

Architecture review precedes that sequence. This session stops with this
checkpoint; it has run no kernel, integration experiment, or new carveout.
Document validation checks only its links, JSON examples, requirement coverage
and change scope. These checks are not runtime validation.

### Reviewable request record — not submitted

No durable Task creation binding is exposed in this session. The following draft
records the authorized work, not a runtime Task identity or state:

```json
{
  "version": 1,
  "kind": "TaskSpec",
  "payload": {
    "objective": "Reconcile Blaine's existing architecture and current official Restate semantics in one reviewable Cognitive Loop checkpoint.",
    "autonomy": {
      "allowed": ["Read repository and official documentation/source", "Write one architecture checkpoint"],
      "forbidden": ["Implement runtime or Cognitive Kernel", "Edit ADRs", "Run new carveout experiments"]
    },
    "completion": [
      {
        "criterion": "Cover loop and Task semantics, execution primitives, contracts/JSON, native Restate mapping, enforcement, seams, boundaries, ADR reconciliation, next kernel and validation sequence.",
        "evidence": "This artifact with repository and official source references, explicit proposals and unresolved decisions."
      },
      {
        "criterion": "Leave implementation and ADRs unchanged.",
        "evidence": "Workspace change-scope inspection."
      }
    ]
  }
}
```

[services]: https://docs.restate.dev/develop/python/services
[steps]: https://docs.restate.dev/develop/python/durable-steps
[state]: https://docs.restate.dev/develop/python/state
[calls]: https://docs.restate.dev/develop/python/service-communication
[events]: https://docs.restate.dev/develop/python/external-events
[timers]: https://docs.restate.dev/develop/python/durable-timers
[errors]: https://docs.restate.dev/develop/python/error-handling
[invocations]: https://docs.restate.dev/services/invocation/managing-invocations
[recovery]: https://docs.restate.dev/foundations/key-concepts
[versioning]: https://docs.restate.dev/services/versioning
[configuration]: https://docs.restate.dev/services/configuration
[multi-agent]: https://docs.restate.dev/ai/patterns/multi-agent
[example]: https://github.com/restatedev/ai-examples/blob/60d1eda2e5f3aae96db2efeba498e52367a01648/openai-agents/tour-of-agents/app/multi_agent.py
[sdk-context]: https://github.com/restatedev/sdk-python/blob/ad4ea7c0a60b5745681a809fe57656bec0939c38/python/restate/context.py
[sdk-runner]: https://github.com/restatedev/sdk-python/blob/ad4ea7c0a60b5745681a809fe57656bec0939c38/python/restate/ext/openai/runner_wrapper.py
[sdk-functions]: https://github.com/restatedev/sdk-python/blob/ad4ea7c0a60b5745681a809fe57656bec0939c38/python/restate/ext/openai/functions.py
[sdk-session]: https://github.com/restatedev/sdk-python/blob/ad4ea7c0a60b5745681a809fe57656bec0939c38/python/restate/ext/openai/session.py
[sdk-deps]: https://github.com/restatedev/sdk-python/blob/ad4ea7c0a60b5745681a809fe57656bec0939c38/pyproject.toml
[protocol]: https://github.com/restatedev/restate/blob/v1.7.9/service-protocol/dev/restate/service/protocol.proto
[oai-orchestration]: https://developers.openai.com/api/docs/guides/agents/orchestration
[oai-results]: https://developers.openai.com/api/docs/guides/agents/results
