# Completion Contract v1 — design contract

**Status: DESIGN, not implemented (2026-09-23).** Decision rationale:
[ADR 0026](../decisions/0026-completion-contract-is-a-durable-task-primitive.md).
First consumer: [E1 workspace capability](workspace-capability.md). The current
kernel implements the v0 subset described in [Current baseline](#current-baseline);
nothing here claims that the v1 additions run.

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

## Current baseline

Implemented today (`runtime/kernel/contracts.py`, `execution.py`, `workflow.py`):

- `TaskSpec.completion` is a list of 1..8 `{criterion, evidence}` items. Evidence
  is either an exact artifact digest `{artifact, sha256}` or a typed human decision
  `{artifact, verifier: "human_response", request}`.
- The accepted TaskSpec is retained immutably (`TaskState.spec_ref`) before any effect.
- `evaluate()` runs after acceptance and after every effect/outcome (verifier-first
  progression, [milestone 024](../milestones/024-cognitive-kernel-increment-8-passed.md)).
  Satisfied → `COMPLETED`; a model `COMPLETE` only requests the same evaluation.
- Every evaluation is retained as a `CompletionEvaluation` artifact
  (`TaskState.completion_ref`); the `TaskResult` links the final one.
- Capability authority is envelope data (`grant`), never TaskSpec data, so a
  model-written specification cannot widen its own authority.

Gaps that v1 closes: criteria have no stable identity, provenance or level; every
criterion is implicitly required; only two verifier kinds exist; the contract is
frozen inside the TaskSpec, so any legitimate change requires a new Task; there is
no deterministic record of which capabilities actually ran; and an evaluation
does not say which contract revision or evidence set it judged.

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
     "provenance": {"source": "task_type", "ref": "investigation@1"},
     "verifier": {"kind": "capability_journal", "version": 1,
                  "predicate": "operation_classes_subset", "allowed": ["workspace.read"]}}
  ]}}
```

| Field | Rule |
| --- | --- |
| `id` | Identifier, unique within the contract, stable across revisions. Evaluations, amendments and results refer to it. |
| `requirement` | Bounded human-readable statement (≤512 bytes). Descriptive only; the verifier decides. |
| `level` | `REQUIRED` or `ADVISORY`. Only REQUIRED criteria gate COMPLETED. No other priority levels. |
| `provenance` | `{source, ref?, actor?}`; see [provenance](#provenance-and-precedence). Mandatory. |
| `verifier` | `{kind, version, …params}` from the closed [taxonomy](#verifier-taxonomy). `unbound` is allowed only under the [refinement rule](#creation). |

Limits: 1..16 criteria; a contract artifact ≤16 KiB (`MAX_PACKET`). Criterion
**status is never stored in the contract**; it is a property of an evaluation.

### Backward compatibility

A v0 `TaskSpec.completion` list lowers deterministically into revision 0: item *n*
becomes id `c{n}`, level `REQUIRED`, provenance `{source: "user"}` for top-level
intake or `{source: "parent_task"}` for a child, and verifier `artifact_digest` or
`human_response` from its evidence shape. Existing D2 requests and kernel fixtures
therefore keep their exact meaning. New intake may supply a CompletionContract in
the trusted `TaskRequest` envelope (next to `grant`); the TaskSpec keeps its
human-readable `completion` summary. Because E1 Tasks are cognition-driven, the
envelope's `initial_action` becomes optional when a `contract` and `grant` are
present; today it is mandatory for every `TaskRequest`.

## Provenance and precedence

Criteria enter from a small set of sources. The source decides whether a criterion
may be REQUIRED without further confirmation.

| Source | Examples | May create REQUIRED? | May waive/downgrade REQUIRED? |
| --- | --- | --- | --- |
| `user` | "Do not change the public API", "make the tests pass", an explicit acceptance request | Yes | Yes, through an explicit human amendment |
| `operator_rule` | A promoted, versioned rule for a project or task type (e.g. "every coding Task in project ORCHID runs `./gradlew check`") | Yes | No; the operator retires the rule, then a human amendment may waive it for one Task |
| `task_type` | Blaine-owned, versioned template defaults (`investigation@1`, `implementation@1`) | Yes, for template-declared invariants | Only by human amendment |
| `parent_task` | Criteria a parent writes for a child TaskSpec | Yes, binding the child only | No (parent cannot weaken its own contract through a child) |
| `project` | Checked-in AGENTS.md, repository instructions, canonical build/test commands | **No** — ADVISORY, or used to *bind a verifier* for a user/operator criterion | No |
| `memory` | MIRIX suggestion from prior behavior | **No** — ADVISORY or candidate only | No |
| `model` | Quality checks proposed by cognition | **No** — ADVISORY only | No |

Rationale for the two "No" rows: repository text and memory are untrusted context,
not policy (see the Hub [security table](../personal-agent-hub.md#security-boundaries)).
A malicious or stale repository instruction cannot make a Task impossible or add
authority. Project instructions become REQUIRED only after an operator promotes
them into an `operator_rule` (see [memory](#memory-and-learning)). They are still
valuable immediately in two bounded ways: as ADVISORY criteria, and as the concrete
*binding* for a higher-provenance criterion (the user said "tests pass"; the
checked-in instructions say which command runs them). A binding chosen from
project text is recorded with `binding_provenance: project`.

**Precedence on conflict:** `user` > `operator_rule` > `task_type` > `parent_task`
> `project` > `memory` > `model`. A conflicting lower-precedence criterion is kept
in the contract with `superseded_by: <id>` and never evaluated as REQUIRED, so the
conflict stays visible. A conflict between two REQUIRED criteria of equal top
precedence is a clarification question for the user before Task creation.

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
| `capability_journal` | Predicates over the Task's own capability journal: allowed operation classes, workspace scope, no unadmitted execution, required operation present | Yes | New | E1 |
| `evidence_citation` | A structured result artifact conforms to its schema and every claim cites admitted receipts; quoted spans match receipt content | Yes (provenance, not truth) | New | E1 |
| `capability_result` | A specific admitted capability result satisfies a structured predicate (exit code, test report counts, HTTP status, state field) | Yes | New, specified; E1 does not need it | E2 |
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

## Creation

```text
user request / signal
  → Personal Agent interpretation (semantic)
  → contract synthesis: task-type template + user criteria + operator rules
                        + advisory suggestions (project, memory, model)
  → deterministic validation (shape, provenance rules, verifier kinds, limits)
  → trusted TaskRequest envelope {task_spec, contract, grant}
  → workflow retains contract revision 0 before the first effect
```

- **A contract exists before any effect.** The workflow retains revision 0 in the
  same pre-effect step sequence that already retains the TaskSpec. A Task without
  a valid contract is rejected at intake, exactly as an invalid TaskSpec is today.
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
`supersede`. Admission rules, enforced deterministically:

| Operation on a REQUIRED criterion | Allowed actors |
| --- | --- |
| `add`, `elevate` | user, operator rule, task-type template upgrade applied at intake only |
| `bind` | user, operator rule; cognition may **propose** (see below) |
| `rebind`, `waive`, `supersede` | user only, through an explicit human action (signal or HumanDecision) |
| any | never cognition, a worker, memory, or repository text directly |

ADVISORY criteria may be added by cognition as `model` provenance without human
action; they cannot block completion, so the Task cannot make itself impossible.

- **User changes requirements:** `modify-constraints` signal → amendment with
  `actor.kind = user`. The request carries the expected `from_revision`; a stale
  revision is rejected (compare-and-set).
- **Evidence shows a criterion impossible:** cognition may not drop it. It raises
  a `human.request` asking to `waive`, `amend` or `fail`; the Task waits as usual.
  The answer produces the amendment or a FAILED outcome with the evidence retained.
- **Repository policy adds a mandatory verifier:** only via a promoted operator
  rule; applied at intake, or as an amendment with `actor.kind = operator_rule`
  when the rule is promoted while the Task runs.
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
amendments to the same revision, only the first resolves. Implementation check:
confirm non-blocking promise inspection (`peek`) in the pinned Restate Python SDK;
if unavailable, admit amendments at the next durable wait only and document it.
Each amendment emits an ExecutionEvent (`contract.amended`) for forensics only.

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
6. Every waiver references a retained human action.

A model `COMPLETE` proposal, a worker exit, a write acknowledgement or a process
exit code is neither necessary nor sufficient. "Why is this Task COMPLETED?" is
answered by `TaskResult.completion_ref` alone, following the audit chain above.

A Task that cannot satisfy its contract ends `FAILED` (turn budget, explicit human
`fail`, terminal capability error) with the last evaluation attached; it is never
relabelled complete with concerns.

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
memory suggests          →  ADVISORY criterion, provenance memory, with MIRIX memory id
repeated evidence        →  candidate rule (retained artifact: pattern, supporting Tasks)
human promotion          →  operator_rule (versioned, reviewable, revocable)
operator_rule            →  may contribute REQUIRED criteria to future contracts
```

- MIRIX output reaches synthesis only through the existing bounded `derived`
  context seam (`runtime/kernel/memory.py`); it carries no authority.
- A candidate rule is produced offline from retained evaluations and results
  (e.g. "three accepted ORCHID coding Tasks all ran `./gradlew check` and the user
  rejected one that did not"). It changes nothing until promoted.
- Promotion is an explicit human act, following ADR 0024's pattern: history,
  measurement, proposal, evaluation, then human promotion. Rules are versioned and
  referenced by id and digest in criterion provenance, so old contracts remain
  interpretable after a rule changes.
- Storage of operator rules is deliberately not designed here; E1 needs none. The
  first real rule (expected in E3) should choose the smallest reviewable store.

## Non-goals

No workflow DSL, plan schema, priority scale beyond REQUIRED/ADVISORY, generic
script verifier, second completion engine, or model-owned completion. Plans,
strategies and Work Strategy revisions stay outside the contract
([Task operations](task-operations.md#work-strategy-handoff)).
