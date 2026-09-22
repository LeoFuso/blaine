# Blaine architecture

Blaine is the persistent Personal Agent: a conversational control plane over
durable Tasks, semantic memory, replaceable workers and separately authorized
execution surfaces. This document owns current system architecture and boundaries.
The [roadmap](roadmap/001-blaine-development-roadmap.md) owns implementation status
and sequencing; the [documentation map](README.md) identifies other authorities.

The [Personal Agent Hub design](personal-agent-hub.md) is canonical for workstation
connection and E0–E3. Its client/registration/effect additions are planned, not
claims about the deployed system. [Accepted ADRs](decisions/README.md) explain
architectural choices; [contracts](contracts/README.md) define normative interfaces.

```text
User / interactive client
         |
Personal Agent (BLAINE.md + selected skills)
         |
TaskSpec / transport-neutral controls (D2 ACP binding)
         |
Durable Runtime (currently Restate) -- replaceable workers and verifiers
         |
Task evidence / external sources / workspace capability providers
```

## Ownership

| Layer | Responsibility | Location |
|-------|----------------|----------|
| Personal Agent | Own semantic interpretation/triage, answer directly, create/inspect/steer work, explain evidence | [BLAINE.md](../BLAINE.md) |
| Skills | One contextual procedure per Task operation | [skills convention](../skills/SKILL.md) |
| Contracts | Intent structure and semantic binding requirements | [TaskSpec](contracts/task-spec.md), [operations](contracts/task-operations.md) |
| Policy | Shared safety, context, cloud, and verification guidance | `docs/policies/` |
| Durable Runtime | Durable state, timers, retries, signals, recovery, lifecycle enforcement | Current implementation: Restate; evaluated by ADR 0003 |
| Workers/verifiers | Bounded execution and evidence checks | Replaceable execution adapters; deterministic completion verification |
| Workstation / interactive surface | Local workspace, toolchain and IDE context; scoped capability execution independent of worker selection | [D2 implemented boundary](daily-driver-d2.md); [Hub planned client boundary](personal-agent-hub.md) |
| External applications | Own their resources and expose independently authorized capabilities to Tasks | Existing capability/policy boundary; no ambient authority from a connected surface |

The instruction harness expresses semantic procedures. The transport-neutral
Personal Agent binds controls to durable kernel Tasks; ACP is one client adapter.
Surface/session availability never establishes Task state, completion or approval.
A connected surface supplies only capabilities it implements and the Task is
allowed to use. Worker identity does not determine the execution location.

For the implemented control subset, configuration and evidence limits, read the
[D2 binding guide](daily-driver-d2.md). Current delivery status lives only in the
[roadmap](roadmap/001-blaine-development-roadmap.md); historical proof lives in
[milestones](milestones/README.md) and referenced experiment artifacts.

## Memory and context

Chat is disposable working memory. The Durable Runtime (currently Restate) holds
execution memory. Knowledge and artifact stores hold reusable findings with
provenance; external systems remain
authoritative for their own facts. Context is resolved just in time, with a minimal
permitted packet for cloud work. A worker claiming success does not complete a Task.

## Progressive disclosure and portability

BLAINE.md is a small entry point. Load only the needed skill and its references.
Skills use `skills/<name>/SKILL.md`; external references retain reviewed provenance
in [manifest.md](../skills/manifest.md). No specific loader is assumed.
Recipes can capture repeated deterministic work when justified; they do not replace
runtime durability. Machine paths, credentials, and private settings stay outside
the public repository in ignored local configuration or secure credential stores.

## Interaction example

“Explain this error” may receive a direct answer. “Investigate its cause and retain
evidence” becomes a TaskSpec. The creation receipt supplies identity; later status
queries and signals address that identity across sessions. Results pair recorded
state with deliverables and verification evidence. Closing the client changes none
of the Task's lifecycle by itself.

See [ADR 0004](decisions/0004-personal-agent-control-plane.md) for this boundary,
[ADR 0001](decisions/0001-task-is-the-unit-of-work.md) for Task identity, and
[ADR 0003](decisions/0003-evaluate-restate-as-durable-runtime.md) for runtime evaluation.
