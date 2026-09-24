# Completion Contract v1

**Status: IMPLEMENTED in the kernel (E1.0 PASS, 2026-09-24); E1 end-to-end pending.**
Decision rationale (Accepted / Partially Validated):
[ADR 0026](../decisions/0026-completion-contract-is-a-durable-task-primitive.md).
First consumer: [E1 workspace capability](workspace-capability.md). What runs, and
the precise choices implementation made, are in [Implementation status](#implementation-status-e10)
and [E1.0 clarifications](#e10-implementation-clarifications); evidence is in
[`experiments/personal-agent-hub/e1-0`](../../experiments/personal-agent-hub/e1-0/README.md).
No live workstation, IDE or provider path uses it yet (E1.A–E).

A Completion Contract states **what evidence must exist before a Task may become
COMPLETED**. It is durable Task data, separate from the plan and from cognition.

```text
Plan                  how the Task currently intends to get there   mutable, cognition-owned, not persisted as lifecycle
Completion Contract   what must be demonstrated before COMPLETED    durable, revisioned, amendable only explicitly
Effective authority   which effects the Task may perform            trusted envelope + PolicyGate (not in the contract)
```

A contract never grants authority. A criterion such as "tests pass" does not
authorize running tests; authority comes from the trusted grant, user constraints
and PolicyGate ([ADR 0024](../decisions/0024-local-first-execution-with-bounded-escalation.md),
[workspace capability](workspace-capability.md#effective-authority)). Conversely,
authority invariants such as READ_ONLY are enforced by PolicyGate; the contract
only requires *evidence* that they held.

## Implementation status (E1.0)

Before E1.0 the kernel implemented a v0 subset: `TaskSpec.completion` as 1..8
`{criterion, evidence}` items (exact digest or typed human decision), frozen in the
immutable TaskSpec, evaluated verifier-first, with the final `CompletionEvaluation`
linked from `TaskResult`. Criteria had no identity, provenance or level; nothing
recorded which capabilities actually ran; any change needed a new Task.

E1.0 implements this contract in the kernel, reusing the workflow, `ArtifactStore`,
PolicyGate and the human-decision boundary:

| Area | Implementation |
| --- | --- |
| Contract model, validation, v0 lowering, amendments, evaluation v2, legality | `runtime/kernel/completion.py` |
| Capability journal, `kernel@1` operation classes, `EffectiveAuthority` (E1.0 form) | `runtime/kernel/journal.py` |
| `evidence_citation@1` with `InvestigationFindings@1` | `runtime/kernel/citation.py` |
| `semantic_review@1` interface and deterministic admission (no model shipped) | `runtime/kernel/review.py` |
| Contract/authority retention before effects, journal on the single dispatch path, `settle()` as the only path to COMPLETED, `amend_contract` handler, amendment admission | `runtime/kernel/workflow.py` |
| Contract-fixed human requests in PolicyGate; v1 `evaluate()` kept as a projection of the same verifiers | `runtime/kernel/execution.py` |
| Current contract and admitted read receipts in cognition packets | `runtime/kernel/context.py` |

Verifier kinds implemented: `artifact_digest`, `human_response`, `capability_journal`,
`evidence_citation`, `semantic_review`, plus `unbound`. `capability_result` (first
consumer E2) and `change_set` (reserved) are rejected at validation, so no contract
can depend on a verifier that does not run.

## Model

```text
Task (Restate workflow state)
  spec_ref            immutable accepted TaskSpec (intent)            existing
  grant               trusted effective-authority envelope            existing
  contract_ref        current CompletionContract revision artifact    new
  contract_revision   integer, 0 at acceptance                        new
  journal_head/length capability journal hash-chain head              new (see below)
  completion_ref      latest CompletionEvaluation artifact            existing
  artifacts           admitted evidence references                    existing
```

The contract, amendments, evaluations, journal entries and evidence are immutable
artifacts in the existing content-addressed `ArtifactStore`. Restate state holds
only references and counters. No new store, table or ledger is introduced.

### CompletionContract

```json
{"version": 1, "kind": "CompletionContract", "payload": {
  "task_id": "task-…",
  "revision": 0,
  "previous_ref": null,
  "amendment_ref": null,
  "task_type": {"template": "investigation", "version": 1},
  "criteria": [
    {"id": "no-mutation",
     "requirement": "No workspace-mutating capability was admitted or executed.",
     "level": "REQUIRED",
     "provenance": {"source": "task_type", "ref": "investigation@1", "invariant": true},
     "verifier": {"kind": "capability_journal", "version": 1,
                  "predicates": [{"name": "no_target_effect"}, {"name": "admitted_before_observed"}]}}
  ]}}
```

| Field | Rule |
| --- | --- |
| `id` | Identifier, unique within the contract, stable across revisions. Evaluations, amendments and results refer to it. |
| `requirement` | Bounded human-readable statement (≤512 bytes). Descriptive only; the verifier decides. |
| `level` | `REQUIRED` or `ADVISORY`. Only REQUIRED criteria gate COMPLETED. No other priority levels. |
| `provenance` | `{source, ref?, actor?, invariant?, designation_ref?, source_digest?, confirmed_from?}`; see [provenance](#provenance-and-precedence). Mandatory and never changed by an amendment. `invariant` only for `task_type`; `ref` and `source_digest` required for `operator_rule` and `project_policy`, plus `designation_ref` for `project_policy`. |
| `verifier` | `{kind, version, …params}` from the closed [taxonomy](#verifier-taxonomy). `unbound` is allowed only under the [refinement rule](#creation). |

Limits: 1..16 criteria; a contract artifact ≤16 KiB (`MAX_PACKET`). Criterion
**status is never stored in the contract**; it is a property of an evaluation.

### Backward compatibility

A v0 `TaskSpec.completion` list lowers deterministically into revision 0: item *n*
becomes id `c{n}`, level `REQUIRED`, provenance `{source: "user"}` for top-level
intake or `{source: "parent_task"}` for a child, and verifier `artifact_digest` or
`human_response` from its evidence shape. Existing D2 requests and kernel fixtures
therefore keep their exact meaning.

Lowering is deterministic kernel code, run at intake before any cognition. It is
one-to-one and verbatim: the requirement text is byte-identical, order is kept,
near-duplicates are not merged, and each verifier carries exactly the item's
evidence fields. No model summarizes, improves, merges, weakens or reinterprets an
intake criterion, and an envelope contract (below) must carry every lowered
criterion unchanged — the same id, text, level, provenance and verifier, with no
supersession. The summary-only TaskSpec form for contract Tasks is future E1.D work.

New intake may supply a CompletionContract in
the trusted `TaskRequest` envelope (next to `grant`); the TaskSpec keeps its
human-readable `completion` summary. Because E1 Tasks are cognition-driven, the
envelope's `initial_action` becomes optional when a `contract` and `grant` are
present; today it is mandatory for every `TaskRequest`.

## Provenance and precedence

Criteria enter from a small set of sources. Whether a source may create a REQUIRED
criterion follows the existing authority order — Blaine-owned invariants, operator
policy, the Task's user, then derived context — and the Context Plane's source-trust
model: availability of a source is not authority, and content never confers
authority by itself ([CP-B5](context-plane.md#1-common-binding-and-authority)).

| Source | Authority tier | Examples | May create REQUIRED? |
| --- | --- | --- | --- |
| `task_type` (invariant) | Blaine-owned | Authority-evidence criteria declared invariant by a versioned template: `no-mutation`, `workspace-scope` | Yes, always present for that template |
| `task_type` (default) | Blaine-owned | Template quality defaults: findings cited, conclusion explicit | Yes |
| `operator_rule` | Operator policy | A versioned rule held by Blaine for a project or task type, authored or promoted by the operator (e.g. "every coding Task in ORCHID runs the full check profile") | Yes |
| `project_policy` | Operator policy | A structured rule from a **designated** project policy source (see [trusted project policy](#trusted-project-policy)): canonical build must pass; public API compatibility preserved; required integration suite passes | Yes |
| `user` | Task user | "Do not change the public API", "make the tests pass", an explicit acceptance request | Yes |
| `parent_task` | Delegated | Criteria a parent writes for a child TaskSpec | Yes, binding the child only |
| `repository` | Derived context | Ordinary repository evidence: README or documentation prose, AGENTS.md text that is not designated policy, source comments, user-generated files | **No** — ADVISORY, or a proposed verifier *binding* |
| `memory` | Derived context | Governed Memory results, including retrieved human declarations and verified-outcome learning | **No** — ADVISORY or candidate |
| `model` | Derived context | Quality checks proposed by cognition, or a model's interpretation of any policy prose | **No** — ADVISORY only |

Why the derived rows cannot create REQUIRED criteria: they are data under the Context
Plane, not policy. A malicious or stale README cannot make a Task impossible or add
authority, and a retrieved preference does not alter accepted Task constraints
([Context Plane Memory](../context-plane.md#8-memory-plane-and-trusted-provenance)).
Repository text remains useful immediately: as ADVISORY criteria, and as a proposed
*binding* for a higher-provenance criterion (the user said "tests pass"; the
repository says which command runs them). Such a binding is recorded with
`binding_provenance: repository` and, for a REQUIRED criterion, follows the
`bind` amendment rules below. A memory or model suggestion becomes binding only by
being confirmed by the user for this Task (`user` provenance) or adopted as an
`operator_rule` or `project_policy` for future Tasks.

### Trusted project policy

`project_policy` exists so a project can carry governed, canonical completion
rules without every rule becoming a Blaine-held operator rule — and without
arbitrary repository content acquiring authority.

- **Designation, not content, confers trust.** A policy source is authoritative
  only when the operator has designated it for that project through a trusted
  declaration path: the Context Plane's authenticated human-declaration semantics
  (`USER_DECLARATION` with an explicit destination) bound to the project's
  workspace/ContextNode, naming the exact source locator (for example one
  repository file). The designation is operator policy; the file is its current
  content. A file that merely claims to be policy is ordinary `repository` text.
- **Structured rules only.** A REQUIRED criterion comes from a machine-readable
  rule entry that names its requirement and verifier binding (e.g.
  `canonical-build` → `capability_result` on the declared build profile). Prose in
  a designated source (a definition-of-done paragraph) is interpreted by a model
  and therefore enters as ADVISORY `model` provenance, unless the user confirms it.
- **Pinned per Task.** Contract synthesis records the designation reference and
  the exact source revision/digest it read. A later edit to the policy file does
  not silently change a running Task: tightening arrives as an amendment with
  `project_policy` actor; weakening applies only to future Tasks or through a
  policy exception. Concretely (E1.0): `operator_rule` and `project_policy`
  criteria must carry `ref` (rule identity) and `source_digest` (the exact version);
  no amendment operation changes a criterion's provenance, so every revision and
  the evaluation chain behind `TaskResult.completion_ref` name the version that
  created the criterion; an edited rule can only enter a running Task as a new
  criterion with a new id (a tightening amendment), never by replacing the pinned
  one; and a policy exception must name exactly `{rule: ref, digest: source_digest}`
  of the pinned criterion — an exception naming the edited version is refused.
- **Scope.** A designation applies only to Tasks whose relevant workspace is that
  project. It grants no capability; a rule requiring a build does not authorize
  running it (effective authority still decides).

Storage and tooling for designations and operator rules are not chosen here; E1
needs neither. The first real rule (expected in E2/E3) selects the smallest store
consistent with Context Plane metadata ownership.

### Precedence and conflicts

**Precedence on conflict:** `task_type` invariant > `operator_rule` = `project_policy`
> `user` > `task_type` default > `parent_task` > `repository` > `memory` > `model`.
A conflicting lower-precedence criterion is kept in the contract with
`superseded_by: <id>` and never evaluated as REQUIRED, so the conflict stays
visible. A user request that conflicts with operator policy ("skip the integration
suite") does not silently override it: the policy criterion stays REQUIRED and the
user is told that a [policy exception](#amendments) is needed. Two conflicting
REQUIRED criteria of the same tier are a clarification question before Task creation.

Authority invariants are not negotiable through precedence. A user criterion that
would require a write in a READ_ONLY Task does not widen authority; the Task cannot
satisfy it and must surface that, not act.

## Verifier taxonomy

A criterion must say how Blaine knows it holds. Seven kinds cover E1–E3; each has
a version so its semantics can evolve without silently changing old evaluations.

| Kind | Verifies | Deterministic? | Status | First consumer |
| --- | --- | --- | --- | --- |
| `artifact_digest` | A named artifact exists with an exact SHA-256 | Yes | **Existing** (`evaluate`) | D2 |
| `human_response` | A scoped typed HumanDecision was answered within its allowed set | Human judgement, deterministic admission | **Existing** | Kernel inc. 5 / D2 |
| `capability_journal` | Predicates over the Task's own capability journal: no target effect ("no mutation"), allowed operation classes, workspace scope, no unadmitted execution, required operation present | Yes | New | E1 |
| `evidence_citation` | A structured result artifact conforms to its schema and every claim cites admitted receipts; quoted spans match receipt content (the Context Plane's exact-excerpt semantics) | Yes (provenance, not truth) | New | E1 |
| `capability_result` | A specific admitted capability result satisfies a structured predicate (exit code, test report counts, HTTP status, state field); typical binding for project-policy build/test rules | Yes | New, specified; E1 does not need it | E2 |
| `change_set` | The admitted diff touches only allowed paths / preserves listed signatures | Yes | Reserved | E2 |
| `semantic_review` | A bounded model judgement over cited evidence (completeness, consistency, clarity) | No | New | E1 (advisory) |

Kinds deliberately absent: a generic "script" verifier (a verifier must not become
arbitrary execution), and a "worker says done" verifier. New kinds require a
contract revision of this document, not model output.

### Deterministic-first rule (adopted)

> If a criterion can be verified deterministically, a model is never its
> authoritative verifier.

Test exit codes, file hashes, API responses, structured state and diff scope are
checked directly. This is [ADR 0007](../decisions/0007-tools-before-model-inference.md)
applied to verification, and it is also the only way a verdict survives replay
and model switches unchanged. Challenge considered: some "deterministic" checks
are weak proxies (a passing test suite that does not exercise the requested
behavior). The answer is not to let a model override the check, but to add a
second criterion — a stronger deterministic probe, a `semantic_review` on
coverage, or a human acceptance — each recorded separately. Weakness of one
verifier is visible as a missing criterion, not hidden inside another.

Contract validation enforces the rule mechanically where it can: a `semantic_review`
criterion must not target a fact another criterion in the same contract verifies
deterministically (same `subject`), and its evaluation reads deterministic results
as fixed inputs.

### Semantic review

`semantic_review` exists for properties with no deterministic proof: investigation
completeness, internal consistency of a conclusion with its cited evidence,
contradiction detection, clarity. Contract shape:

```json
{"kind": "semantic_review", "version": 1, "subject": "findings",
 "question": "Does the cited evidence support the stated cause without contradiction?",
 "on_low_confidence": "unknown"}
```

- Runs only after every deterministic criterion it depends on has a verdict; it
  receives those verdicts and the cited evidence as a bounded packet, never the
  producer's persuasive reasoning ([local-first policy](../policies/local-first-and-context.md#minimal-worker-packet)).
- Returns `satisfied | unsatisfied | unknown | request_human` with rationale that
  cites evidence refs. Output is retained as an artifact; the model call is a
  journaled Restate step, so replay reuses it.
- It cannot change a deterministic verdict. If it contradicts one, the
  deterministic verdict stands and the contradiction is recorded as a concern.
- Low confidence yields `unknown` (default) or `request_human` (when the criterion
  says so), never an invented `satisfied`.
- Default level is ADVISORY. It may be REQUIRED only with `user` or
  `operator_rule` provenance, and then `on_low_confidence` must be `request_human`,
  so a REQUIRED semantic criterion always has a path to a human decision instead
  of blocking forever or passing on weak confidence.
- Local inference first; paid cloud only under the Task's cloud policy and budget.
  It is never mandatory for every Task.

### Human verification

Human acceptance reuses the existing `human.request` capability, `HumanDecisionRequest`
/ `HumanDecisionResponse` contracts, the runtime-owned wait and the
`submit_human_response` handler. There is no parallel human system. A `human_response`
criterion's request is part of the contract, so its question and allowed answers
are fixed before the wait. While waiting, the Task is `WAITING` with blocking
dependency `human_response`; identity, contract revision, journal, evidence and
cognition context are unchanged, and the matching response resumes the **same**
Task. Use it for visual approval, product judgement, ambiguous business decisions,
genuinely subjective output, and as the escalation target of REQUIRED semantic
reviews.

## Evaluation and evidence linkage

`CompletionEvaluation` v2 extends the existing artifact:

```json
{"version": 2, "kind": "CompletionEvaluation", "payload": {
  "task_id": "task-…", "contract_ref": "artifact://task-…/sha256:…", "contract_revision": 1,
  "evidence_digest": "sha256:…", "journal_head": "artifact://task-…/sha256:…", "journal_length": 14,
  "outcome": "unsatisfied",
  "criteria": [
    {"id": "no-mutation", "level": "REQUIRED", "verifier": "capability_journal@1",
     "status": "satisfied", "evidence_refs": [], "journal_range": [0, 14],
     "detail": "14 entries; admitted classes ⊆ {workspace.read}; 1 denial (workspace.write)"},
    {"id": "cause-supported", "level": "REQUIRED", "verifier": "evidence_citation@1",
     "status": "pending", "evidence_refs": [], "detail": "findings artifact absent"}]}}
```

Criterion status values:

| Status | Meaning | Gates COMPLETED if REQUIRED? |
| --- | --- | --- |
| `satisfied` | Verifier accepted admitted evidence | passes |
| `pending` | Required evidence not yet present | blocks |
| `failed` | Evidence exists and contradicts the criterion (deterministic) | blocks |
| `unknown` | Verifier could not decide (error, low semantic confidence) | blocks |
| `waiting_human` | A human decision for this criterion is outstanding | blocks |
| `waived` | A human amendment waived it, with reference | passes |

The overall `outcome` keeps its v1 values for compatibility: `satisfied` iff every
REQUIRED criterion is `satisfied` or `waived`; otherwise `unknown` if any REQUIRED
criterion is `unknown`/`waiting_human`, else `unsatisfied`. ADVISORY results never
change the outcome; non-satisfied ADVISORY results become `TaskResult.concerns`.

The audit chain is fully reference-based:

```text
TaskResult.completion_ref
  → CompletionEvaluation (contract revision, evidence digest, journal head)
      → per criterion: verifier kind@version → status
          → evidence_refs: artifacts (capability receipts, findings, human response)
          → journal_range: capability journal entries (admission + outcome)
  → CompletionContract revision N → amendment → … → revision 0
```

Evidence attaches to criteria only through evaluations. Raw logs stay in the
artifact store; evaluations carry references and small details (≤512 bytes per
criterion). A receipt may support several criteria and is counted once because
it is identified by content digest and `operation_id`.

## Capability journal

The deterministic record of what the Task was allowed to do and actually did.
It is the evidence source for `capability_journal` criteria and for completion
legality. It is not telemetry (ExecutionEvents remain non-authoritative) and not a
second Task ledger: it records only this Task's capability admissions and
outcomes, is written only by the workflow, and is read only through the Task.

Each entry is an immutable artifact linked by digest:

```json
{"version": 1, "kind": "CapabilityJournalEntry", "payload": {
  "task_id": "task-…", "seq": 7, "previous_ref": "artifact://…",
  "phase": "admitted",
  "decision_id": "task-…/5", "operation_id": "task-…/5",
  "capability": "workspace.read", "operation_class": "workspace.read",
  "provider": "intellij-mcp", "operation": "search_text", "workspace_id": "wsp-…",
  "request_digest": "sha256:…", "authority_ref": "artifact://…", "contract_revision": 1}}
```

- The capability-specific target identity (E1: `workspace_id`) is recorded so
  scope predicates need no other source.
- `phase` is `denied` (PolicyGate refused; nothing dispatched), `admitted`
  (appended **before** dispatch), or `observed` (outcome and receipt ref appended
  after the result is admitted, or `uncertain` when a result cannot be admitted).
- The workflow appends in journaled steps, so replay reproduces identical refs.
  `TaskState.journal_head`/`journal_length` advance with the Task state.
- Structural invariant (tested): the only dispatch path for `INVOKE_CAPABILITY`
  appends `admitted` first. A dispatch without a preceding admission is a kernel
  defect, which is why an `observed` entry without an `admitted` predecessor makes
  every `capability_journal` criterion `failed`.
- `authority_ref` points to the compiled effective-authority artifact in force,
  so a verifier can recompute whether each admission was legal at that time.

### No mutation: internal versus target effects

A capability's operation class has one effect scope in the reviewed classification
(`kernel@1` in E1.0; `intellij-mcp@1` extends it in E1.C):

| Scope | Meaning | Kernel classes | Examples |
| --- | --- | --- | --- |
| `INTERNAL_EFFECT` | Changes only the Task's own durable state | `task.*` (`artifact.write`/`read`, `human.request`, `text.stats`) | Task state, journal entries, artifacts and evidence, human requests, completion evaluations, local computation, semantic-review packets |
| `TARGET_READ` | Observes a target without changing it | `workspace.read`, `external.read` | File read, index search, issue read |
| `TARGET_EFFECT` | May change state outside the Task | `external.effect`, `worker.run`, `workspace.write`, `workspace.exec`, and every unclassified class | Workspace file mutation, process or terminal execution, external API, database or remote-system change |

A "no mutation" criterion means **no unauthorized TARGET_EFFECT**. It is expressed
with the `capability_journal` predicate `no_target_effect {allowed?}`: it fails when
an admitted journal entry's class is a TARGET_EFFECT outside `allowed` (default:
none). INTERNAL_EFFECT and TARGET_READ never violate it, so a read-only Task can
always create its own evidence, journal and result; a denied proposal never
violates it either (prevention worked). An admitted effect outside effective
authority is additionally a journal authority violation for every criterion and
for legality. Unreviewed classes are treated as TARGET_EFFECT, never as harmless.
`operation_classes_subset` remains a scope predicate (which external classes a
Task may use at all); internal classes are outside it.

## Creation

```text
user request / signal
  → Personal Agent interpretation (semantic)
  → contract synthesis: task-type template + user criteria + operator rules
                        + designated project policy (pinned) for the relevant workspace
                        + advisory suggestions (repository, memory, model)
  → deterministic validation (shape, provenance rules, verifier kinds, limits)
  → trusted TaskRequest envelope {task_spec, contract, grant}
  → workflow retains contract revision 0 before the first effect
```

- **A contract exists before any effect.** The workflow retains revision 0 in the
  same pre-effect step sequence that already retains the TaskSpec. A Task without
  a valid contract is rejected at intake, exactly as an invalid TaskSpec is today.
- **Sources come from the Context Plane.** Relevance (which workspace/project) is a
  Context Plane resolution; the trust class of each discovered source (designated
  policy, ordinary repository evidence, memory) comes from its trusted provenance,
  not from its content. Synthesis never re-derives trust.
- **Trivial Tasks need no ceremony.** A task-type template plus the objective yields
  a complete contract with no user question (e.g. `investigation@1` contributes
  no-mutation, scope and citation criteria automatically).
- **Ambiguity.** Ask the user before creation only when a missing answer changes
  scope, safety or the intended result (BLAINE.md interaction rules). Never ask
  merely to confirm a generated contract; the contract is inspectable at any time.
- **Refinement while reading.** A REQUIRED criterion may carry
  `verifier: {kind: "unbound"}` only when the Task's effective authority contains
  no mutating operation class. The Task may run read-only work; completion is
  illegal while any REQUIRED criterion is unbound; binding it is an amendment. A
  Task with any mutating authority must start with every REQUIRED criterion bound.
- Synthesis happens outside the workflow (Personal Agent, before submission). The
  submitted request, including the contract, is covered by the existing request
  digest, so a retried submission cannot carry a silently different contract.

## Amendments

Completion criteria change only through an explicit, retained amendment.

```json
{"version": 1, "kind": "CompletionContractAmendment", "payload": {
  "task_id": "task-…", "from_revision": 1, "to_revision": 2,
  "from_ref": "artifact://…", "operations": [
    {"op": "waive", "id": "tests-pass", "reason": "Upstream CI outage; operator accepts manual evidence"}],
  "actor": {"kind": "user", "via": "human_response", "ref": "artifact://…"},
  "provenance": "user", "reason": "…"}}
```

Operations: `add`, `bind` (replace an `unbound` or ADVISORY verifier), `rebind`
(change a REQUIRED criterion's verifier), `waive`, `elevate` (ADVISORY → REQUIRED),
`supersede`. A REQUIRED criterion leaves the evaluated set only by being satisfied,
superseded, rebound or waived by an actor whose authority covers its source.
Admission rules, enforced deterministically:

| REQUIRED criterion's source | `add` / `elevate` | `bind` | `rebind` / `supersede` / `waive` for this Task |
| --- | --- | --- | --- |
| `task_type` invariant | Template at intake | Template | **Nobody.** It changes only with the authority it evidences (a different Task with different effective authority) or a reviewed template revision |
| `operator_rule`, `project_policy` | Operator policy at intake; `project_policy`/`operator_rule` actor when the policy tightens mid-Task | Operator policy | Only a **policy exception**: an explicit human decision through the operator path that names the rule id and pinned digest. Ordinary `modify-constraints` text is not enough. Changing the policy itself happens outside the Task and affects future Tasks |
| `user`, `task_type` default | User | User; cognition may **propose** | User, through an explicit human action (signal or HumanDecision) |
| `parent_task` | Parent at child creation | User | User; never the child's or parent's cognition |
| any | never cognition, a worker, memory or repository text directly | | |

In the single-owner personal deployment the same person is operator and user, but
a policy exception remains a distinct, typed and retained act (`actor.kind =
operator`, `exception_for: {rule, digest}`), so the result shows that policy was
set aside rather than satisfied.

ADVISORY criteria may be added by cognition as `model` provenance without human
action; they cannot block completion, so the Task cannot make itself impossible.

- **User changes requirements:** `modify-constraints` signal → amendment with
  `actor.kind = user`. The request carries the expected `from_revision`; a stale
  revision is rejected (compare-and-set). It cannot touch invariant or policy
  criteria.
- **Evidence shows a criterion impossible:** cognition may not drop it. It raises
  a `human.request` asking to `waive`, `amend` or `fail`, typed as a policy
  exception when the criterion is policy-sourced; the Task waits as usual. The
  answer produces the amendment or a FAILED outcome with the evidence retained.
- **Project policy adds a mandatory verifier:** at intake from the pinned designated
  source, or mid-Task as a tightening amendment with `actor.kind = project_policy`.
- **Human waives a requirement:** `waive` with the human action ref; the criterion
  stays in the contract and evaluates `waived`, visible in the result.

Cognition can propose an amendment only as a `human.request`; a model output that
attempts to change the contract directly is rejected by validation and recorded
as a PolicyGate denial.

**Runtime mechanism.** Restate's workflow main handler is the single writer of
Task state. Amendments arrive through a shared handler (`amend_contract`) that
validates shape and actor, then resolves the one-shot durable promise
`contract/{from_revision + 1}`. The main loop checks that promise at each iteration
boundary and whenever it resumes from a wait, applies the amendment in a journaled
step, retains the new revision, and re-runs evaluation before the next cognition.
One-shot promise naming by revision gives compare-and-set: of two concurrent
amendments to the same revision, only the first resolves. Implementation check
(done, E1.0): `DurablePromise.peek()` works in the workflow main handler of the
pinned SDK 1.0.5 against restate-server 1.7.9 and is journaled; a second `resolve`
fails with a catchable `409 promise was already completed` while `peek` returns the
winner, which is how the handler recognises an identical retry. A human `WAITING`
Task additionally races its input promise against `contract/{n}` with
`restate.select`, so an amendment can end that wait (see
[clarifications](#e10-implementation-clarifications)). Each amendment emits an
ExecutionEvent (`contract.amended`, outcome `applied` or `rejected`) for forensics only.

### Amendment actor is binding-owned

Amendment authority is never read from the requested change. The binding that
authenticated the principal (for the Personal Agent, the user's private session;
for policy, the operator or policy-synchronisation path) establishes the actor and
submits an envelope, like the grant in a `TaskRequest`:

```json
{"version": 1, "kind": "CompletionContractAmendmentSubmission", "payload": {
  "actor": {"kind": "user", "via": "modify-constraints", "binding": "personal-agent"},
  "amendment": {"version": 1, "kind": "CompletionContractAmendmentRequest", "payload": {
    "task_id": "task-…", "request_id": "…", "from_revision": 1,
    "operations": [{"op": "waive", "id": "tests-pass", "reason": "…"}], "reason": "…"}}}}
```

The amendment content has no actor or authority field; content that carries one is
rejected, so text from a user message, model or file cannot claim or upgrade an
actor. Content may only *name* things the kernel then checks: `exception_for`
(the pinned rule an exception sets aside, valid only with an operator
`policy_exception` actor) and `response_ref` (an accepted human response, valid only
with a `human_response` actor and verified against the Task). The retained action
is the whole submission, and legality rechecks that each waiver's recorded actor is
the one its retained action carries. This is the human-response boundary's trust
model: the binding delivers and vouches for the principal; the kernel validates
scope and authority deterministically.

## Completion legality

The workflow may set `lifecycle = COMPLETED` only when a single deterministic
function over retained artifacts returns true:

1. The evaluation was computed against the **current** contract revision and the
   current evidence digest and journal head (no stale evaluation).
2. Every REQUIRED criterion is `satisfied` or `waived`, and no REQUIRED criterion
   is `unbound`.
3. No REQUIRED deterministic criterion is `failed` (implied by 2; stated because a
   later ADVISORY or semantic result can never mask it).
4. No `human_response` wait for any criterion is outstanding.
5. The capability journal is well-formed and contains no execution outside the
   effective authority recorded in its `authority_ref`s. PolicyGate denials are
   allowed (prevention worked) but are always listed in the result, never hidden.
6. Every waiver references a retained human action whose authority covers the
   criterion's source (a policy exception for `operator_rule`/`project_policy`);
   no `task_type` invariant is waived.

A model `COMPLETE` proposal, a worker exit, a write acknowledgement or a process
exit code is neither necessary nor sufficient. "Why is this Task COMPLETED?" is
answered by `TaskResult.completion_ref` alone, following the audit chain above.

A Task that cannot satisfy its contract ends `FAILED` (turn budget, explicit human
`fail`, terminal capability error, terminal invariant violation) with the last
evaluation attached; it is never relabelled complete with concerns.

### Terminal versus remediable

A `failed` REQUIRED criterion blocks COMPLETED but does not, by itself, end the
Task. It is **remediable**: later evidence may pass it (a failing test is fixed; a
bad citation is rewritten), or the user may waive or rebind a user criterion. The
Task keeps working within its turn budget.

A criterion is a **terminal invariant violation** only when all hold, and then the
Task ends `FAILED` immediately (`Invariant criteria failed: …`), with that
evaluation as its `completion_ref`:

1. it gates completion (REQUIRED, not superseded);
2. nobody may change it within the Task (a `task_type` invariant); and
3. its failure is monotonic — no later evidence can undo it. In E1.0 that is a
   `capability_journal` failure: the journal is append-only, so a prohibited target
   effect that was admitted stays admitted.

The same journal failure on a user criterion is not terminal (the user may waive
it); a failed digest, citation or test criterion is never terminal. The rule is
`completion.terminal()`; evaluations list terminal criteria in `irrecoverable`.

## Crash, retry and replay

| Event | Guarantee | Mechanism |
| --- | --- | --- |
| Process restart / crash recovery | Same contract revision, journal and evaluations | All are artifacts written in journaled `ctx.run` steps; Restate replays refs |
| Submission retry | No second or different contract | Contract is inside the digested request; D2 identity rules reject changed input |
| Provider or model failure / model switch | Contract unchanged | Contract is not cognition state; escalation rebinding (Policy C) does not touch it |
| Workstation disconnect | Contract and evidence unchanged; pending operation waits | See [E1 disconnect semantics](workspace-capability.md#disconnect-and-reconnect) |
| Duplicate capability result | Counted once | One-shot promise per operation; journal entry per `operation_id`; digest-addressed receipts |
| Amendment replay | Applied once | Revision-named one-shot promise; journaled application step |

Minimum durable representation: `contract_ref`, `contract_revision`,
`journal_head`, `journal_length` added to `TaskState`, plus artifacts. Journal
compatibility follows the existing rule: new journal-producing code is a new
Restate deployment; in-flight Tasks are not replayed against changed code.

## Memory and learning

```text
governed Memory (any origin)   →  ADVISORY criterion, provenance memory, with memory id
verified outcomes, repeated    →  candidate rule (retained artifact: pattern, supporting Tasks)
human adoption                 →  operator_rule, or a structured rule in a designated project policy
operator_rule / project_policy →  may contribute REQUIRED criteria to future contracts
```

- Memory reaches synthesis only through Context Plane resolution; results keep
  their trusted origin and semantic qualification (declaration, unverified
  observation, verified success/failure). None carries authority, including a
  retrieved `USER_DECLARATION` preference.
- Candidate rules are built offline from Completion Contract evaluations and
  results, and from learned representations admitted by the Context Plane's
  [VerifiedOutcomeAdmission](context-plane.md#9-promotion-and-verified-learning-contracts)
  (e.g. "three accepted ORCHID coding Tasks all ran the check profile and the user
  rejected one that did not"). A verified-failure representation can motivate a
  rule but never counts as success guidance. Candidates change nothing until adopted.
- Adoption is an explicit human act, following ADR 0024's pattern: history,
  measurement, proposal, evaluation, then human promotion. It is distinct from the
  Context Plane PromotionGate, which moves knowledge between contexts and grants no
  policy authority. Rules are versioned and referenced by id and digest in
  criterion provenance, so old contracts remain interpretable after a rule changes.

## E1.0 implementation clarifications

Choices the accepted text left open, made at the narrowest boundary and validated by
the E1.0 evidence. None changes a decision in ADR 0026.

**Intake and representation**

- Lowered v0 criteria are numbered from one: item *n* of `TaskSpec.completion` is
  `c{n}` (`c1` is the first). A child's lowered criteria carry
  `{source: parent_task, ref: <parent task id>}`.
- An envelope contract must contain every lowered `TaskSpec.completion` criterion
  unchanged (same id, level, provenance and verifier) and may add more. The TaskSpec
  is still validated by its v0 rules; a summary-only TaskSpec form for contract
  Tasks is left to E1.D intake. A child contract is always lowered, never supplied.
- `TaskRequest` accepts `{task_spec, initial_action?, grant?, contract?}`;
  `initial_action` may be absent only when both `contract` and `grant` are present.
- A contract needs at least one REQUIRED criterion that is not superseded.
- `operator_rule` provenance, like `project_policy`, requires `ref` and a pinned
  `source_digest` (Memory and learning: rules are referenced by id and digest), so
  a policy exception can name exactly what it sets aside. The kernel checks the
  shape of `designation_ref`; checking the designation itself belongs to contract
  synthesis through Context Plane provenance, exactly as the grant is trusted
  envelope data. No designation or rule store exists yet (Operator-rule storage row).
- Deterministic verifiers may declare an optional `subject`. The deterministic-first
  rule is enforced on declared subjects: a `semantic_review` whose `subject` equals a
  deterministic criterion's `subject` is rejected. An `evidence_citation` over the
  `findings` artifact does not implicitly claim the subject `findings`.
- `human_response` may declare `accept` (a subset of the allowed responses). With
  `accept`, another allowed answer evaluates `failed`; without it, any allowed answer
  satisfies, which is the v0 meaning.
- `semantic_review` may declare `depends_on` (deterministic criterion ids). With
  `on_low_confidence: request_human` it must also carry a contract-fixed
  HumanDecisionRequest (`request`, `artifact`, optional `accept`) so the escalation
  question and answers exist before any wait.
- `capability_journal` parameters are a `predicates` list:
  `no_target_effect {allowed?}`, `operation_classes_subset {allowed}`,
  `admitted_before_observed`, `workspace_subset`, `observed_operation_present {operations}`.
- `evidence_citation@1` implements schema `InvestigationFindings@1` and predicates
  `every_claim_cited`, `quotes_match_receipts`, `min_cited_receipts {operation, count,
  path_prefix?}`, `conclusion_status_present`, `unresolved_requires_uncertainty`.
  `ExplanationFindings@1` and `LocationFindings@1` (and their predicates) arrive with
  the E1.D templates and are rejected until then.

**Journal and authority**

- The kernel classification `kernel@1` maps the existing capabilities to operation
  classes: `artifact.write`/`artifact.read` → `task.artifact.*`, `human.request` →
  `task.human.request`, `text.stats` → `task.compute`, `youtrack.read` →
  `external.read`, `workspace.read` → `workspace.read`, `worker.run` → `worker.run`,
  `fixture.effect` → `external.effect`; anything else is `unclassified`. Effect
  scopes are in [No mutation](#no-mutation-internal-versus-target-effects): an
  investigation may write its own `findings` artifact without breaking
  `no-mutation`. "Mutating authority" (for `unbound`) means any TARGET_EFFECT or
  unclassified capability.
- E1.0 retains an `EffectiveAuthority` artifact (`classification: kernel@1`,
  capabilities, operation classes, workspaces, `externally_bounded`) compiled from
  the existing TaskSpec ∩ grant; for the D2 exact-path read its workspace is the
  accepted intake root. E1.C extends the same artifact with delegation and
  constraint provenance and `intellij-mcp@1`.
- Journal entries record `provider`/`operation` (`kernel`/capability name; the D2
  read is `acp-client`/`read_file`). An `observed` entry's `receipt_ref` is the
  retained capability observation, or for the D2 read a `WorkspaceReadReceipt`
  written when the ACP client result is admitted (`source.view: acp_text_file`, the
  whole returned text as the line range). Denials are journaled whenever the denied
  proposal names a capability; malformed proposals and non-capability actions stay
  `PolicyDecision` observations only.
- Admitted receipts are projected into cognition packets as evidence references
  (`content.name: receipt`, operation, path and lines, never new authority), so
  later turns can cite what the Task admitted.

**Evaluation and legality**

- `CompletionEvaluation` v2 criterion entries also carry `gating` (REQUIRED and not
  superseded) and, when present, `superseded_by`, `waiver_ref` and `journal_range`.
  The payload adds `concerns`, `irrecoverable` and `legality {legal, blockers}`: the
  legality decision is retained with the evaluation it judged, and is recomputable
  offline by `completion.legality`. `unbound` reports `pending` and is always a
  legality blocker.
- A waived criterion stays in the contract with
  `waiver {revision, actor {kind, via, ref, response_ref?, exception_for?}, reason}`;
  `actor.ref` is the retained amendment request (the human action). Legality
  rechecks the authority matrix and that the action is retained.
- A gating task-type **invariant** `capability_journal` criterion that is `failed`
  can never recover (append-only journal, unwaivable), so the Task ends `FAILED`
  immediately; every other failed criterion is remediable
  ([terminal versus remediable](#terminal-versus-remediable)).
- ADVISORY non-passing results, waivers, supersessions, PolicyGate denial counts and
  semantic contradictions become `TaskResult.concerns` (still at most 8).
- `semantic_review` runs, as journaled steps, only when its `depends_on` criteria are
  `satisfied`/`failed`/`waived` and no retained review matches the current revision
  and evidence digest. No reviewer deployed, adapter errors and malformed outputs are
  retained as `SemanticReviewFailure` and evaluate `unknown` (or `waiting_human` under
  `request_human`). High-confidence `unsatisfied` evaluates `failed`. A `satisfied`
  verdict while a dependency `failed` evaluates `unknown` with a concern; the
  deterministic verdict stands. The reviewer's `evidence_refs` must come from its packet.

**Amendments**

- The signal is a binding envelope `CompletionContractAmendmentSubmission {actor
  {kind, via, binding}, amendment}` around `CompletionContractAmendmentRequest
  {task_id, request_id, from_revision, operations[1..8], reason, exception_for?,
  response_ref?}` ([binding-owned actor](#amendment-actor-is-binding-owned)).
  Actor channels: `user` via `modify-constraints` or `human_response`; `operator`
  via `policy_exception` or `policy_update`; `project_policy` via `policy_update`.
  The Personal Agent binding exposes `amend` and always establishes
  `user`/`modify-constraints`; no operator or policy binding exists yet. Cognition
  has no path to the handler: a model output that tries to change the contract is
  an unknown NextAction and is denied by PolicyGate.
- `amend_contract` answers `SUBMITTED` or `ALREADY_SUBMITTED` (identical retry),
  `400` malformed (including authority fields inside the content), `403` authority not covering the criterion's source, `409` stale
  revision, already-amended revision, or terminal Task. A receipt means submitted,
  not applied; `contract_revision` shows application.
- Application is at every iteration boundary and, for a human `WAITING` Task, as soon
  as the amendment arrives. If the waited-for criterion is no longer gating (waived,
  superseded, rebound away from that request) the wait is withdrawn
  (`HumanWaitWithdrawn`) and a late response is rejected; otherwise the Task keeps
  waiting on the new revision. Workspace, text and child waits apply amendments when
  they resume.
- The handler validates against the same immutable revision the main handler
  applies, so a rejection at application is a defect path: it is retained as
  `CompletionContractAmendmentRejection`, the revision number stays closed and the
  Task continues on its current revision.
- Not implemented in E1.0: cognition adding ADVISORY `model` criteria, and cognition
  raising a typed "waive / amend / fail" `human.request` for an impossible criterion.
  Neither has a consumer before E1.D; the human path above covers user waivers.

## Non-goals

No workflow DSL, plan schema, priority scale beyond REQUIRED/ADVISORY, generic
script verifier, second completion engine, or model-owned completion. Plans,
strategies and Work Strategy revisions stay outside the contract
([Task operations](task-operations.md#work-strategy-handoff)).
