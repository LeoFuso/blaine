# ADR 0026 — Completion Contract is a durable, revisioned Task primitive

**Status:** Proposed
**Validation:** Unvalidated
**Date:** 2026-09-23

## Context

[ADR 0015](0015-durable-task-execution-and-verification.md) established that a
Task completes only by satisfying its Completion Contract, never by model
assertion. The kernel implements a narrow form: `TaskSpec.completion` criteria with
exact-digest or typed-human evidence, frozen in the immutable accepted TaskSpec,
evaluated verifier-first after every effect.

E1 read-only investigation Tasks, and later E2/E3 coding Tasks, expose the gaps:

- investigations produce findings whose correctness no digest can know in advance;
- repository conventions, Task-type defaults, memory and models all want to
  contribute criteria, with very different authority;
- users legitimately change requirements mid-Task, and some requirements turn out
  to be impossible — today either case requires a new Task;
- nothing deterministic records which capabilities a Task actually ran, so
  "no workspace mutation" can only be asserted, not verified.

The risk on the other side is a plan-like or DSL-like contract that cognition can
rewrite until the Task passes.

## Decision

Make the Completion Contract a first-class, durable, revisioned Task artifact,
specified in [Completion Contract v1](../contracts/completion-contract.md):

1. **Separate from plan and authority.** The contract says what must be
   demonstrated; plans stay mutable cognition; authority stays in the trusted
   grant and PolicyGate. A criterion never grants authority.
2. **Criteria carry identity, level, provenance and a verifier.** Levels are only
   `REQUIRED` and `ADVISORY`. Only `user`, `operator_rule`, `task_type` and
   `parent_task` provenance may create REQUIRED criteria; `project`, `memory` and
   `model` provenance are ADVISORY (or bind a verifier for a higher criterion).
3. **Closed verifier taxonomy** extending the existing two kinds:
   `artifact_digest`, `human_response`, `capability_journal`, `evidence_citation`,
   `capability_result`, `change_set` (reserved) and `semantic_review`.
4. **Deterministic-first.** A model is never the authoritative verifier of a fact a
   deterministic verifier can check; semantic review cannot override deterministic
   verdicts and resolves low confidence to `unknown` or a human request.
5. **Explicit amendments only.** Revisions are retained artifacts with actor,
   provenance and reason. Waiving, rebinding or superseding a REQUIRED criterion
   requires an explicit human action. Cognition may add ADVISORY criteria and may
   *request* a REQUIRED change only through the existing human-decision path.
6. **Capability journal.** Each Task keeps a hash-chained, artifact-backed record of
   PolicyGate admissions, denials and observed outcomes, appended before dispatch.
   It is Task evidence, not telemetry and not a cross-Task ledger.
7. **Completion legality is one deterministic function** over the current contract
   revision, a fresh evaluation, the journal and waiver references.

Storage reuses what exists: artifacts in the content-addressed store, references
and counters in Restate Task state, evaluations as extended `CompletionEvaluation`
artifacts. The v0 `TaskSpec.completion` form lowers into revision 0 unchanged.

## Alternatives considered

- **Keep the contract inside the immutable TaskSpec.** Simplest, and safe against
  silent change, but makes every legitimate change a new Task and loses Task
  identity, evidence and human context across the change.
- **Let cognition maintain the contract as part of its plan.** Rejected: the model
  could drop a failing criterion to reach COMPLETED, which ADR 0015 forbids.
- **A general acceptance DSL or scriptable verifier.** Rejected: becomes arbitrary
  execution and a second workflow engine; the closed taxonomy covers E1–E3.
- **Mandatory semantic critic on every Task.** Rejected: cost without evidence of
  need, and it would blur deterministic authority.
- **Derive "no mutation" from ExecutionEvents.** Rejected: events are forensic,
  lossy by design and explicitly never lifecycle authority.

## Consequences

- "Why is this Task COMPLETED?" is answerable from `TaskResult.completion_ref`
  through the evaluation, contract revision, journal and evidence artifacts.
- Investigations can complete honestly with an `unresolved` conclusion; truth
  judgements go to advisory semantic review or the user.
- Contract changes keep the same Task; each change is visible and attributable.
- Requires new kernel code: contract artifact and revision state, evaluation v2,
  journal append on the single dispatch path, three verifiers, an amendment
  handler with revision compare-and-set, and new event types. These are new
  journal-producing code paths and deploy as a new Restate deployment.
- Operator-rule storage and promotion tooling are deferred until a first real rule.

## Validation

### Hypothesis

A revisioned, provenance-bearing contract with a closed verifier set lets E1
investigation Tasks complete only on deterministic provenance and scope evidence,
keeps completion stable across crash, retry and model change, and prevents
cognition from weakening REQUIRED criteria — without a DSL or a second engine.

### Validation level

Integration (kernel + Restate + artifacts), then end-to-end inside E1 acceptance.

### Minimal validation

Kernel fixture Tasks with scripted cognition: (a) a v0 TaskSpec produces the same
verdicts as today; (b) an investigation contract completes only after cited
findings exist; a fabricated quote fails it; (c) scripted cognition tries to
remove a REQUIRED criterion and is denied; a human waiver then passes it with a
visible `waived` status; (d) SIGKILL at contract retention, at amendment
application and after evidence admission recovers the same revisions and
verdicts; (e) a synthetic journal with an unadmitted execution fails
`capability_journal`.

### Evidence

Retained contracts, amendments, evaluations, journals and TaskResults whose chain
reproduces each verdict offline; zero COMPLETED Tasks with an unsatisfied REQUIRED
criterion; identical refs across replay; negative cases rejected with reasons.

### Not required for validation

Operator-rule store, MIRIX-driven candidate rules, `change_set`, paid semantic
review, natural-language contract synthesis, UI for amendments.

## Reconsider when

Real Tasks repeatedly need criteria the taxonomy cannot express without a
semantic verifier doing deterministic work; amendments become routine enough that
human-only waivers are the dominant friction; or the journal cost per operation
becomes material for high-volume read Tasks.
