# ADR 0001 — Task Is the Unit of Work

**Status:** Accepted  
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
