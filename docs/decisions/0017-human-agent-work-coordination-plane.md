# ADR 0017 — Human–Agent Work Coordination Plane

**Status:** Accepted
**Validation:** Partially Validated
**Date:** 2026-09-18

## Context

Blaine needs a durable place for human/project coordination without making that
place the runtime ledger for autonomous execution. YouTrack is the selected
system for that coordination. Its Cards must remain understandable to people
while runtime Tasks, Work, and Workers retain the lifecycle and authority
defined by ADRs 0001 and 0015.

The coordination model also needs to distinguish human-governed discovery and
decision-making from delivery that has already been authorized within an
explicit outcome and decision envelope.

## Decision

YouTrack is the **Human–Agent Work Coordination Plane**. Cards are human/project
coordination artifacts, not runtime Tasks. Runtime Task, Work, and Worker
lifecycle does not belong in YouTrack.

The Card Plane has two separate work/coordination planes. Upstream and
Downstream are not sequential states of the same Card.

| Plane | Purpose | Lifecycle |
|---|---|---|
| **Upstream** | Human-governed discovery, planning, discussion, and decision-making. | `Backlog` → `In Progress` → `Needs Decision` → `Done` |
| **Downstream** | Autonomous delivery within an explicitly approved outcome/decision envelope. | `Backlog` → `In Progress` → `Blocked` → `Done` |

A Downstream Card entering `Backlog` is already authorized for autonomous
execution within that envelope. It does not require another per-Card approval.
Material product, architecture, scope, permission, cost, or risk decisions may
block Downstream work and cause a new or reopened Upstream discussion.
Ordinary execution difficulties remain Downstream concerns.

Relationships between Upstream and Downstream Cards are loose, informative, and
potentially N:N. They are not structural lifecycle dependencies. Completing an
Upstream Card is an organizational outcome and does not depend on completion of
related Downstream deliverables.

Card types are assigned by plane as follows:

| Plane | Card types |
|---|---|
| Upstream | `Task`, `Subtask` |
| Downstream | `Story`, `Task`, `Bug`, `Subtask` |

`Epic` represents a milestone and is not inherently part of either plane.

When used, `Assignee` means current coordination ownership—“who has the ball.”
It must never represent an ephemeral Worker or a runtime lock. Blaine is the
persistent Personal Agent identity. Wolf is a separate autonomous execution
authority; neither is to be conflated with the other or with ephemeral Workers.

Comments preserve deliberation and history. For active work, the Card
description represents consolidated current truth.

The exact YouTrack UI, board, and field configuration is implementation detail
and may remain incomplete.

## Consequences

Human coordination can be visible and durable without making YouTrack the
authority for runtime execution. Downstream autonomy is clear at the plane and
envelope boundary, while consequential changes return to human-governed
Upstream discussion. Card relationships can provide traceability without
creating hidden execution dependencies or requiring a single Card to move
through both planes.

The existing runtime boundary remains authoritative: a Card may motivate or
record work, but runtime Task completion still requires the Task's completion
contract and evidence. UI configuration, browser automation, and the details of
linking Cards to runtime work remain outside this ADR.

## Validation

### Hypothesis

YouTrack can support durable human/project coordination for Blaine while
preserving the separation between Card coordination and runtime Task execution,
and while making approved Downstream autonomy distinguishable from Upstream
decision-making.

### Validation level

`End-to-end`.

### Minimal validation

Use YouTrack through OAuth and MCP with Blaine's persistent identity to read and
update representative Cards, and inspect whether the resulting coordination
record remains distinct from runtime Task/Work/Worker state.

### Evidence

The dogfooding experiment established that:

- OAuth and MCP access worked;
- Blaine could read and update Cards under its own persistent identity; and
- the Card coordination path was usable for the intended experiment.

This is partial validation only. Full Personal Agent dogfooding is paused, and
browser automation is explicitly parked for now. The experiment exposed missing
Personal Agent continuity/memory and harness delegation/capability-selection
concerns. Those findings are follow-up work, not part of this ADR's scope.

### Not required for validation

- complete Personal Agent continuity or memory;
- browser automation;
- final YouTrack UI or board configuration;
- runtime Task/Work/Worker lifecycle in YouTrack; or
- Multica carveout work.

## Reconsider when

Reconsider if YouTrack cannot represent the two coordination planes without
making Card state a proxy for runtime lifecycle, if approved Downstream work
cannot be distinguished from work awaiting human decisions, or if the loose
Upstream/Downstream relationship model fails to support traceability without
introducing structural dependencies.
