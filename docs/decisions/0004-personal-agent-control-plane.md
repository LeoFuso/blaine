# ADR 0004 — Personal Agent as Conversational Control Plane

**Status:** Accepted
**Validation:** Unvalidated
**Date:** 2026-09-14

## Context

The legacy harness made the conversational agent responsible for orchestration and
completion transitions. That couples durable work to transient model turns and
conflicts with Task identity (ADR 0001) and runtime ownership (ADR 0003).
Not every conversation needs an independent execution lifecycle.

## Decision

The Personal Agent answers directly when conversation satisfies intent. Meaningful
independent work becomes a durable Task. The agent forms TaskSpecs, queries runtime
state, submits steering signals, and explains results with evidence.

Restate owns durable execution state. Code enforces lifecycle, retries, timers,
permissions, and budgets. LLMs provide semantic decisions and bounded work;
workers and clients remain replaceable. Agent claims do not establish completion.

## Consequences

The entry point stays small, with five operation skills and shared structural
contracts. Missing bindings produce explicitly unsubmitted drafts or unavailable
reads, never simulated state. Integration must provide authoritative queries,
mutation receipts, and verifiable results. This decision adds no runtime or ACP
implementation and does not extend the runtime spike's validation claims.

## Validation

### Hypothesis

The Personal Agent can act as Blaine's conversational semantic control plane
without owning durable execution state.

It should decide whether an intent is satisfied conversationally, by a
deterministic tool, or by durable work; when durable work is required it should
produce or steer semantic Task requests while leaving lifecycle ownership to the
runtime.

### Validation level

Isolated first, followed by integration.

### Minimal validation

Present representative natural-language requests to the Personal Agent and
observe the semantic decision without requiring real workers.

The initial cases should include:

- a conversational question that requires no Task;
- a deterministic lookup that should select a tool rather than inference;
- small bounded work that should become a simple durable Task;
- a read-only investigation that must preserve mutation restrictions;
- an existing Task status/steering request that must use authoritative runtime
  operations rather than conversation memory;
- a sufficiently ambiguous or consequential request that should require
  clarification or approval.

### Evidence

PASS requires that the Personal Agent:

- preserves the direct-interaction versus durable-work boundary;
- forms the smallest Task specification that preserves intent and constraints;
- does not invent runtime state;
- does not implement retries, timers, waits, or lifecycle state in conversation;
- preserves user authorization and autonomy constraints;
- treats completion as evidence-backed rather than an agent claim.

This validation is pending Milestone 003.

### Not required for validation

- Codex execution;
- a complete SpecKit workflow;
- paid cloud inference;
- GPU scheduling;
- MCP exposure;
- protected-context transformation.

### Reconsider when

Reconsider if semantic routing consistently requires lifecycle knowledge inside
the Personal Agent, or if the direct-interaction versus durable-work boundary is
too unstable to make useful decisions.
