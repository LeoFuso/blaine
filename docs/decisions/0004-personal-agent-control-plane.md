# ADR 0004 — Personal Agent as Conversational Control Plane

**Status:** Accepted  
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
