# ADR 0003 — Evaluate Restate as the Durable Runtime

**Status:** Accepted

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
