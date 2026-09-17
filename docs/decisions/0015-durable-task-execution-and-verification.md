# ADR 0015 — Durable Task execution and verification

**Status:** Accepted
**Validation:** Unvalidated
**Date:** 2026-09-17

## Context

Blaine is intended to execute autonomous work that may span multiple model calls,
tools, processes, machines, failures, waits, retries, and periods of time.

A model response cannot be treated as authoritative evidence that work has
completed. A model may:

- misunderstand an objective;
- stop prematurely;
- incorrectly report success;
- produce incomplete artifacts;
- lose context;
- fail during a later step; or
- succeed at an intermediate action while the overall objective remains incomplete.

Similarly, a model session is not an appropriate owner of durable execution
state.

Blaine therefore needs a durable execution model in which runtime state,
verification, and completion are enforced independently from model
self-assessment.

Restate is the current selected durable execution foundation and remains
authoritative over durable lifecycle and coordination.

## Decision

Runtime work uses four distinct concepts:

1. **Task** — a durable objective.
2. **Work** — concrete activity performed toward that objective.
3. **Worker** — an anonymous execution unit that performs Work.
4. **Artifact / Evidence** — observable results used to determine whether the
   Task has progressed or completed.

The Durable Runtime, currently implemented by Restate or code executing under
its durable runtime contract, owns the lifecycle of a Task.

A Worker or model may produce outputs and assessments. It may not unilaterally
declare a Task complete.

> **A model response is never sufficient evidence of Task completion.**

## Task

A Task is a durable runtime objective.

Examples include:

```text
Interpret a human response and update a Card.

Implement an approved code change.

Verify whether a Story's acceptance criteria have been delivered.

Read Slack messages and notify the human if action is required.

Investigate a technical question and produce a report.
```

A Task may or may not correspond to a Card.

A Task is defined by its objective and the completion conditions that allow the
runtime to determine whether the objective has actually been satisfied.

A Task may survive:

- individual model sessions;
- Worker executions;
- process restarts;
- machine failures;
- retries;
- waits; and
- human interaction.

## Work

Work is concrete activity performed toward a Task.

Examples include:

- retrieving a comment;
- reading repository context;
- invoking a model;
- modifying source code;
- running a compiler;
- executing tests;
- inspecting a diff;
- calling an API;
- updating a Card;
- evaluating an artifact; and
- requesting human input.

Work is a conceptual unit, not necessarily a persisted domain entity. The
runtime should not create a durable object for every action merely because it
can be named.

Some Work may correspond to a function call, model session, child Task, or
durable workflow. Those are implementation decisions.

## Worker

A Worker is an **anonymous unit of execution**, analogous to a worker thread.

A Worker receives Work, executes it using available capabilities, produces
results, and may then disappear. It may use:

- local models;
- cloud models;
- Codex;
- Goose;
- shell tools;
- browsers;
- compilers;
- tests;
- APIs;
- repositories;
- external services; or
- deterministic code.

Workers have no durable business identity. A concrete Worker execution may have
an operational identifier for tracing, logging, observability, cancellation,
correlation, or retries. That identifier is runtime metadata.

**Clarification:** anonymous refers to an execution attempt, not to a concrete
Worker implementation or capability adapter. Worker Selection may use registered
capability and quality information under ADR 0010; that information does not
become a Task lifecycle identity.

> **Persist the Task, not the Worker.**

The same Task may involve any number of independent Worker executions.

## Artifacts

Workers produce Artifacts. An Artifact is any result that may contribute to Task
progress or verification.

Artifacts are not limited to files. Examples include:

- source code;
- a diff;
- a commit;
- a branch;
- a document;
- a report;
- a Card update;
- a comment;
- an API response;
- a database change;
- test results;
- compiler output;
- benchmark results;
- notification delivery;
- structured model output; or
- a recorded human decision.

Artifacts provide observable consequences of execution. They are addressable
evidence and reusable context, not authoritative lifecycle state.

## Evidence

Evidence is information used to determine whether a Task's required conditions
are satisfied. An Artifact may itself be Evidence; Evidence may also be derived
from independent inspection.

For example:

```text
Task:
Implement feature X.

Artifacts:
- source diff
- tests

Evidence:
- project compiles
- required tests pass
- expected behavior is observable
```

Another example:

```text
Task:
Process Leonardo's response to CARD-87.

Artifacts:
- updated Card specification

Evidence:
- the unresolved question has been answered
- the answer is reflected in the canonical Card state
```

## Completion Contract

A Task has a Completion Contract appropriate to its objective. The contract
defines what must be true before the runtime may consider the Task complete.

The contract may be:

- deterministic;
- artifact-based;
- test-based;
- externally observable;
- human-approved;
- supported by model-evaluated verification findings; or
- a combination of these.

A model-evaluated finding is evidence for a verifier and runtime transition; a
model's completion assertion alone is never sufficient.

For example:

```text
Task:
Modify API implementation.

Completion Contract:
- code change exists
- project compiles
- relevant tests pass
- requested behavior is present
```

Or:

```text
Task:
Interpret a human comment.

Completion Contract:
- the comment has been interpreted
- it actually resolves the outstanding question
- the resulting decision is reflected in the Card
```

The contract expresses required guarantees without unnecessarily prescribing the
internal reasoning process.

## Runtime authority

The Durable Runtime is authoritative over Task lifecycle.

The fundamental rule is:

```text
Model proposes.
Workers execute.
Verifiers evaluate.
Runtime transitions.
```

A model may state, “The task is complete.” That statement is an output, not a
lifecycle transition.

Verifiers produce findings from applicable evidence. The runtime applies those
findings and any required deterministic checks to the Completion Contract, then
records the resulting lifecycle transition. It does not infer completion from a
model declaration.

## Execution and verification

Tasks support explicit verification where their objective requires it.

```text
        EXECUTE
           │
           ▼
       Artifact(s)
           │
           ▼
         VERIFY
         /    \
      pass    fail
       │        │
       ▼        ▼
   COMPLETE   more Work
```

Verification may invoke:

- deterministic code;
- tests;
- external systems;
- independent model sessions;
- a different model;
- human input; or
- multiple complementary checks.

The mechanism matches the risk and semantics of the Task. Verification need not
be performed by the Worker or model that produced the Artifact; independent
verification is often desirable.

## Example — processing a Card comment

Suppose a Card contains an unresolved question:

```text
Should the implementation preserve the old fallback behavior?
```

The human responds with a comment. A Task may be created:

```text
Objective:
Process the new human response and resolve the Card question.
```

Its execution may conceptually involve:

```text
retrieve comment
      │
      ▼
retrieve Card context
      │
      ▼
Worker interprets response
      │
      ▼
proposed Card update
      │
      ▼
VERIFY
      │
      ├── Does the response actually answer the question?
      ├── Is the interpretation consistent with the response?
      └── Is the decision represented in canonical Card state?
      │
      ▼
apply / correct / request clarification
      │
      ▼
verify resulting Card
      │
      ▼
Task complete
```

The model that interpreted the comment does not control completion.

## Example — implementing code

A Task may have the objective:

```text
Implement authentication behavior defined by CARD-142.
```

Work may include:

```text
inspect repository
read relevant code
select implementation strategy
modify source
compile
run tests
inspect failures
fix issues
review diff
```

The Completion Contract might require:

```text
- required code exists
- compilation succeeds
- relevant tests pass
- acceptance criteria are satisfied
```

A coding agent returning “Done.” does not satisfy the Task by itself.

## Card verification as a Task

Card lifecycle is independent from runtime Task lifecycle. After implementation
Tasks related to a Card finish, another Task may have the sole objective:

> **Verify whether this Card has actually been delivered.**

For example:

```text
Story Card acceptance criteria:
A
B
C
```

Verification produces:

```text
A ✓
B ✓
C ✗
```

The verification Task may complete successfully even though the Card remains
open. Its successful outcome is that the Card was correctly evaluated and
criterion C remains unsatisfied. Further runtime Tasks or downstream Cards may
then be created as appropriate.

> **Task success describes completion of the Task objective, not necessarily
> completion of the project Card that motivated it.**

## Waiting and human interaction

A Task may become unable to continue without external input, including human
clarification, approval, credentials, permission, or completion of another
dependency.

The Durable Runtime may wait, receive a signal, or otherwise persist the
required continuation state. The model does not need to remain alive during the
wait. When the input arrives, a new Worker or model session may continue work.

This is a core reason durable Task state lives outside individual agent
sessions.

## Restate

Restate is the durable runtime foundation for Task execution. Its role includes,
as appropriate:

- durable lifecycle;
- state persistence;
- retries;
- timers;
- signals;
- waiting;
- recovery;
- idempotent coordination;
- long-running execution;
- orchestration of Work; and
- invocation of Workers or child Tasks.

This ADR does not require every Task to map one-to-one to a single Restate
Workflow. A Task might use a Restate Workflow, a Restate handler, multiple
coordinated Workflows, a Workflow that creates child Tasks, or other Restate
primitives. The exact mapping is an implementation concern.

What is not optional is the runtime authority model:

> **Durable execution state is owned by the runtime, not inferred from model
> conversation state.**

## Runtime state

Runtime state is necessary where it represents execution guarantees. Examples
include:

```text
execute
verify
wait
retry
complete
```

These examples describe what the system must guarantee or coordinate; they do
not require a public Task-state taxonomy. The runtime should not persist a
detailed representation of model reasoning.

For example, the following normally do not become durable lifecycle states:

```text
thinking
analyzing
planning
reflecting
choosing a model
considering alternatives
reading context
```

These are execution behavior.

> **The runtime controls lifecycle, not thought.**

State is introduced only where durability, recovery, authority, coordination, or
observability requires it.

## Model contract

Models and agents participating in Task execution operate under the Durable
Runtime's authority. They may:

- propose next actions;
- produce artifacts;
- inspect context;
- propose strategy revisions;
- identify blockers; and
- suggest that completion criteria appear satisfied.

They must not be treated as authoritative sources for:

- durable lifecycle state;
- successful completion;
- retry guarantees;
- durable timers;
- waiting semantics;
- side-effect completion; or
- execution ownership.

Where a model performs a durable action, it does so through runtime-exposed
capabilities whose semantics are enforced outside the model.

## Failure and retry

A failed Worker execution does not necessarily mean the Task has failed. The
runtime may retry, invoke another Worker, change strategy, use a different
model, wait for a dependency, request human input, or create additional Work.

Likewise, successful Work does not necessarily mean the Task has completed. The
runtime applies the Completion Contract to available evidence.

## Work decomposition

A Worker may discover additional work while executing a Task. That work may
remain internal to the Task or justify creation of child Tasks.

```text
Task
  │
  ├── Work
  ├── Work
  ├── Child Task
  └── Work
```

Any child Task has its own objective, TaskSpec, Completion Contract, and durable
acceptance through the normal Task boundary. Parent/child coordination is an
execution choice, not a requirement to persist every Work item.

The architecture avoids formalizing every reasoning step or implementation action
as a Task. Tasks exist where durable objective boundaries are useful.

## Conceptual model

```text
                     TASK
              durable objective
                     │
                     │ coordinates
                     ▼
              ┌─────────────┐
              │    WORK     │
              └──────┬──────┘
                     │
                     ▼
                  WORKER
             anonymous executor
                     │
                     ▼
                 ARTIFACT
                     │
                     ▼
               VERIFICATION
                     │
              ┌──────┴──────┐
              │             │
            fail           pass
              │             │
              ▼             ▼
          more Work      COMPLETE
```

Restate owns the durable path through this lifecycle. Models participate inside
it; they do not own it.

## Relationship to Cards

Cards belong to the human coordination plane. Tasks belong to the execution
plane.

```text
Card ──0..N──► Task
Task ──0..1──► Card
```

A Task may have no Card. A Card may require many Tasks. A completed Task may
leave its Card incomplete. A Card may be reviewed by a separate Task whose
purpose is to determine whether the Card itself can be considered done.

This ADR defines neither a Card provider nor a Card lifecycle. Card state remains
canonical in its owning coordination system.

## Relationship to existing decisions

This ADR refines, rather than supersedes, existing boundaries:

- ADR 0001 establishes the Task as the durable unit of work; this ADR defines
  the execution vocabulary and evidence path inside that boundary.
- ADR 0003 establishes Restate as the durable runtime foundation.
- ADR 0006 establishes that workflow artifacts are not lifecycle authority.
- ADR 0010 retains authority for capability and quality eligibility; a Worker
  execution remains replaceable regardless of its selected implementation.

## Consequences

This decision provides:

- durable execution independent of model sessions;
- explicit separation between project coordination and runtime work;
- artifact-based completion;
- verification independent of model self-assessment;
- recovery after process or machine failure;
- freedom to use different models and Workers during one Task;
- support for long-running and asynchronous work;
- strong execution guarantees without rigidly modeling reasoning; and
- clear authority boundaries between probabilistic intelligence and deterministic
  runtime control.

The central principles are:

> **Task is the durable unit of execution.**

> **Work is activity performed toward a Task.**

> **Workers are anonymous execution units.**

> **Artifacts are outcomes; evidence proves required conditions.**

> **A model response never completes a Task by itself.**

> **Completion requires satisfaction of the Task's Completion Contract.**

> **Models propose; the runtime decides lifecycle transitions.**

> **The runtime controls lifecycle, not thought.**

> **Persist the Task, not the Worker.**

## Validation

### Hypothesis

A durable Task can coordinate replaceable Workers and independent verification
without treating a Worker result, model assertion, Artifact, or conversation
state as sufficient completion evidence.

### Validation level

Integration, followed by end-to-end validation with a realistic Task.

### Minimal validation

Construct a fixture Task with explicit completion criteria. Have one Worker
produce a candidate Artifact and assert completion without sufficient evidence.
Use deterministic verification plus an independent verifier finding to show that
the runtime retains the Task as incomplete. Supply the missing evidence, verify
it, and confirm that the runtime then records completion.

Create a second, Card-associated verification Task that finds one unsatisfied
criterion. Confirm that this Task completes with an evidenced incomplete-Card
result while the Card remains open. Interrupt a Worker or session during a
durable wait, then resume the same Task with a replacement Worker.

### Evidence

PASS requires demonstrating that:

- a Worker or model `DONE` assertion alone cannot complete a Task;
- Artifacts and verifier findings are addressable in the Task result;
- the runtime records incomplete, waiting, and complete transitions from the
  applicable Completion Contract and evidence;
- a replacement Worker can resume the same durable Task identity;
- a Card-verification Task can complete successfully while reporting that its
  Card remains incomplete; and
- session loss or Worker replacement does not become the source of Task state.

### Not required for validation

- a production Card provider;
- paid cloud execution;
- a particular model or Worker implementation;
- SpecKit execution;
- MCP exposure;
- GPU scheduling; or
- a public Task state beyond the states already justified by runtime behavior.

### Reconsider when

Reconsider if representative objectives cannot express verifiable Completion
Contracts without treating model self-assessment as authoritative, or if the
Durable Runtime cannot preserve the required evidence and transition semantics
without creating a competing lifecycle ledger.
