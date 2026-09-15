# ADR 0006 — SpecKit is an optional structured-work strategy

**Status:** Accepted
**Validation:** Unvalidated

## Context

Some work benefits from explicit requirements, clarification, planning,
decomposition, implementation, and convergence. Other work does not.

Applying a full specification workflow to every request would make Blaine
bureaucratic and expensive. Avoiding structured specification entirely would
make large, ambiguous, or high-blast-radius changes harder to reason about and
verify.

GitHub Spec Kit provides useful specification-driven development semantics and
artifacts. Blaine also requires one authoritative owner for durable workflow
state.

The current Durable Runtime implementation is Restate, but workflow semantics
must not depend on Restate specifically.

## Decision

SpecKit-style development is an optional structured-work strategy.

The Personal Agent, through semantic triage, decides whether a request deserves
this strategy.

SpecKit is not Blaine's Durable Runtime and is not authoritative for Task
lifecycle state.

A SpecKit-style strategy may use phases such as:

- specification;
- clarification when required;
- technical planning;
- task decomposition;
- analysis or quality checks when justified;
- implementation;
- convergence or final verification.

Not every phase is mandatory.

Blaine may skip, combine, repeat, or introduce phases when the actual work
requires it.

The Durable Runtime remains authoritative for:

- current workflow position;
- durable waits;
- external signals;
- retries and recovery;
- pause/resume;
- cancellation;
- phase acceptance;
- Task completion.

Restate is the current implementation of this Durable Runtime role.

SpecKit artifacts are inputs and outputs of workflow phases, not a second Task
ledger.

## Relationship to semantic triage

ADR 0005 decides how much process an intent deserves.

A request may remain direct interaction, direct tool usage, simple durable work,
investigation, structured/spec-driven work, or composed work.

Only requests whose ambiguity, blast radius, dependent deliverables,
verification needs, or architectural consequences justify specification
discipline should use a SpecKit-style strategy.

`SPEC_DRIVEN` means structured specification and planning proportional to the
work.

It does not mean every SpecKit phase must run, and it does not imply a particular
worker, model, or cloud provider.

## Workflow semantics

A representative structured workflow may contain:

SPECIFY -> CLARIFY? -> PLAN -> TASKS -> ANALYZE? -> IMPLEMENT -> VERIFY/CONVERGE

These are semantic work phases, not runtime lifecycle states.

A semantic phase may cause runtime states such as waiting for user input, but
those states remain owned by the Durable Runtime.

## Phase execution

A phase may be performed by deterministic tools, local inference, one or more
workers, a paid cloud worker when policy permits, or the user when semantic
authority belongs to the user.

The workflow strategy specifies the required outcome of the phase, not the
concrete worker used to produce it.

Cloud-capable workers may participate in specification or planning as well as
implementation.

Worker selection is a separate decision.

## Artifacts

Structured workflows should produce durable, inspectable artifacts where useful.

Examples include:

- requirements/specification;
- clarifications and decisions;
- technical plan;
- task decomposition;
- implementation changes;
- verification evidence;
- unresolved concerns.

Artifacts should be addressable independently of the conversation that produced
them.

Artifacts are evidence and context. They are not authoritative lifecycle state.

The Durable Runtime decides whether a phase is accepted or incomplete.

## Human gates

Structured work may expose genuine user decisions as durable waits.

Examples include:

- ambiguous requirements;
- approval before consequential mutation;
- architectural trade-offs;
- scope changes;
- acceptance of a materially different plan.

The Personal Agent should not ask for approval merely because a new phase begins.

## Composed work

Some objectives are too broad for one specification workflow.

In those cases Blaine should prefer decomposition into independently manageable
Tasks or workflows rather than an indefinitely expanding specification.

A parent objective may coordinate several spec-driven Tasks while each child
retains its own objective, constraints, completion contract, and evidence.

## Boundaries

SpecKit-style work does not:

- replace the Durable Runtime;
- create a second authoritative lifecycle;
- force every development request through specification;
- imply a particular model or worker;
- bypass Task autonomy or cloud policy;
- treat artifact existence as proof that a phase is complete;
- require conversation state to survive;
- require Blaine to adopt a SpecKit-specific workflow engine.

Blaine may reuse SpecKit commands, templates, artifacts, or conventions where
useful without making SpecKit itself part of the runtime architecture.

## Consequences

Large development work gains explicit requirements and inspectable intermediate
artifacts.

Human decisions can occur at meaningful durable gates instead of inside one long
model session.

Cloud workers can contribute to planning or specification without becoming the
workflow owner.

The same Durable Runtime can execute SpecKit-style work as well as research,
monitoring, simple Tasks, and other non-development workflows.

The implementation must prevent artifact state, model claims, and runtime state
from becoming competing sources of truth.

## Validation

### Hypothesis

SpecKit-style phases and artifacts can provide useful structure for complex
development work while Blaine's Durable Runtime remains the sole authority over
workflow lifecycle.

A structured workflow must be resumable across worker or session boundaries.

### Validation level

Isolated first, followed by integration.

### Minimal validation

Construct a fixture structured-development workflow using stub workers.

Exercise at least:

1. SPECIFY producing a specification artifact;
2. clarification causing a conceptual durable wait;
3. user input satisfying the clarification;
4. PLAN producing a planning artifact;
5. TASKS producing bounded implementation work;
6. IMPLEMENT producing a candidate result;
7. VERIFY/CONVERGE deciding whether the outcome satisfies the requested work.

At least one worker or session boundary should occur between phases.

Lifecycle state must remain separate from generated artifacts.

No real codebase or cloud worker is required.

### Evidence

PASS requires demonstrating that:

- phase artifacts survive worker/session replacement;
- workflow position is controlled by the runtime harness;
- replacing a worker does not lose workflow position;
- clarification can pause and resume work;
- worker claims do not advance phases without accepted evidence;
- missing or invalid artifacts remain detectable;
- optional phases may be skipped;
- no concrete model name is required by the workflow definition;
- the same runtime boundary could host a non-SpecKit workflow.

A later integration validation should repeat the important durability properties
using Blaine's real Durable Runtime.

### Not required for validation

- Codex;
- paid cloud inference;
- a real application repository;
- IntelliJ;
- MCP;
- GPU scheduling;
- Cloud Context Packets;
- protected-context transformation;
- implementing the complete SpecKit product or workflow engine.

### Reconsider when

Reconsider this decision if:

- SpecKit-style artifacts add ceremony without improving complex work;
- separating SpecKit semantics from runtime state proves unnatural;
- representative workloads consistently need a different specification model;
- SpecKit implementation details leak into generic Blaine Task semantics;
- simpler structured-work patterns provide equivalent quality with less
  complexity.
