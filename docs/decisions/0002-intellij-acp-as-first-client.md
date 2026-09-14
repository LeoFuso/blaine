# ADR 0002 — IntelliJ ACP as the First Interactive Client

**Status:** Accepted  
**Date:** 2026-09-14

## Context

Blaine is intended to support interactive agentic work throughout the day.

Development is a major workload, and IntelliJ is already the primary environment for that work.

Building a custom chat interface, editor, diff viewer, or task UI would duplicate mature tooling before demonstrating a real need.

IntelliJ supports custom agents through the Agent Client Protocol (ACP), allowing Blaine to expose its own behavior while remaining independent from the IDE.

## Decision

IntelliJ, through ACP, will be the first interactive client for Blaine.

The Blaine Agent will expose an ACP-compatible interface that can:

- receive user intent;
- create and inspect Tasks;
- report task progress;
- request clarification or approval;
- return task results.

The IntelliJ client is not the owner of task execution state.

Closing IntelliJ or ending an ACP session must not terminate durable Tasks.

## Consequences

The first user experience can reuse IntelliJ rather than requiring a custom frontend.

Blaine remains headless and client-independent.

Additional clients may be added later, such as:

- CLI;
- web UI;
- messaging interfaces;
- mobile clients;
- other ACP-compatible environments.

A custom UI should only be built after existing clients expose a concrete unmet need.
