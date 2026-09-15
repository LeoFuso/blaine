# ADR 0001 — Task Is the Unit of Work

**Status:** Accepted  
**Validation:** Validated
**Date:** 2026-09-14

## Context

Agent sessions and conversations are transient.

A model turn may end before the requested outcome is complete, and a process may terminate successfully even when required work remains.

Blaine needs work to survive:

- agent turns;
- model changes;
- process restarts;
- retries;
- waits;
- human interaction;
- background execution.

Using an agent session as the authoritative representation of work would couple task lifecycle to model and harness behavior.

## Decision

A Task is the authoritative unit of work in Blaine.

A Task has its own identity and lifecycle independent from any agent session used to execute it.

Agent sessions, model calls, subprocesses, and worker attempts are execution details belonging to a Task.

A worker completing a turn or exiting successfully does not by itself mean that the Task is complete.

Task completion must be determined by the task's completion contract and available evidence.

## Consequences

Blaine must maintain task state outside LLM context.

Tasks may span multiple:

- agent sessions;
- workers;
- retries;
- machines or processes;
- human interactions.

Agent state may be discarded or recreated without losing the identity or lifecycle of the Task.

This also allows development and non-development workloads to share the same execution model.

## Validation

### Hypothesis

A durable Task can remain the authoritative unit of work independently of the
conversation, agent process, or client session that created it.

### Validation level

End-to-end.

### Minimal validation

Create a durable Task, allow its originating conversational session to disappear,
then inspect and continue the same Task from a new session using its stable
runtime identity.

### Evidence

Validated by Milestones 001 and 002.

Evidence includes:

- durable workflow state surviving process interruption;
- a Task reaching `WAITING_FOR_USER`;
- termination of the originating ACP session;
- retrieval of the same Task by ID from a new ACP session;
- continuation of that Task from the new session;
- the Task reaching `COMPLETED`.

The conversation/session was disposable while the Task remained authoritative.

### Not required for validation

- Personal Agent semantic reasoning;
- cloud workers;
- MCP;
- SpecKit;
- model routing;
- context preparation.

### Reconsider when

Reconsider if future workloads require durable work whose identity or lifecycle
cannot be represented independently of a conversational session.
