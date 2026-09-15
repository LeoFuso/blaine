# ADR 0003 — Evaluate Restate as the Durable Runtime

**Status:** Accepted
**Validation:** Validated

**Date:** 2026-09-14

## Context

Blaine needs execution state that survives:

- agent turns;
- process failures;
- application restarts;
- waits;
- retries;
- scheduled execution;
- human interaction.

LLM context and agent sessions must not be the authoritative source of task execution state.

An earlier direction considered implementing a custom task ledger and orchestration loop, potentially backed by SQLite.

That would require Blaine to implement concerns such as:

- durable state;
- retries;
- timers;
- scheduling;
- recovery;
- signals;
- workflow lifecycle;
- observability.

These concerns are not unique to Blaine.

## Decision

Evaluate Restate as Blaine's durable execution kernel.

The evaluation will be performed through a minimal runtime spike before Restate is accepted as an architectural dependency.

Restate is expected to own execution lifecycle and durable workflow state.

It is not intended to become Blaine's long-term knowledge or context store.

## Alternatives

Alternatives considered include:

- a custom SQLite-backed task ledger and scheduler;
- Temporal;
- in-memory orchestration;
- agent/session-owned lifecycle.

## Evaluation Criteria

The spike should evaluate:

- operational simplicity on a single self-hosted machine;
- durable execution and recovery;
- stable Task identity;
- long-running workflows;
- retries and timers;
- signals and queries;
- pause/resume/cancel behavior where applicable;
- observability;
- local/self-hosted operation;
- developer ergonomics;
- independence from specific agents and models.

## Consequences

If the evaluation succeeds, Restate may replace the custom execution ledger and workflow loop previously considered for Blaine.

Execution state and knowledge state remain separate concerns.

If Restate introduces disproportionate complexity or fails important requirements, this ADR will be rejected and alternatives reconsidered.

## Validation Result

Milestone 001 successfully verified local Restate execution, persistent workflow state,
stable task identity, status queries, and durable operations/timers through automated
tests and live workflow execution. Both Blaine runtime process and Restate process
crash recovery passed: original tasks completed after restart without resubmission.

See [Milestone 001 — Runtime Skeleton](../milestones/001-runtime-skeleton.md#live-evaluation--2026-09-14)
for evidence and limitations, including untested failure modes and lifecycle features,
no proof of exactly-once external effects, and the outstanding initial smoke-test
process cleanup concern.

## Validation

### Hypothesis

Restate can own Blaine's durable Task execution state, waits, signals, recovery,
and result continuity without requiring an application-managed shadow ledger.

### Validation level

Integration and end-to-end.

### Minimal validation

Run a workflow that persists state, waits durably for external input, survives
relevant process/session loss, resumes from the same durable identity, and
retains its completed result.

### Evidence

Validated across Milestones 001 and 002.

Observed evidence includes:

- workflow state surviving runtime/process interruption;
- Restate recovery preserving durable execution;
- a named durable wait for user input;
- status inspection while the workflow was waiting;
- session-independent external signalling;
- retrieval of the completed result after service restart.

No application-level task ledger was required for these properties.

### Not required for validation

- Personal Agent reasoning;
- SpecKit integration;
- cloud workers;
- GPU scheduling;
- context catalog;
- MCP exposure.

### Reconsider when

Reconsider if representative Blaine workflows require lifecycle semantics that
Restate cannot express cleanly, or its operational cost/complexity becomes
disproportionate for a personal single-host system.
