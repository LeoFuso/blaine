# Blaine architecture

Blaine is a personal agentic work system with a conversational control plane over
durable Tasks. The [product architecture](agentic-development-kit.md) gives the
historical product direction; the [living roadmap](roadmap/001-blaine-development-roadmap.md)
records current sequencing and acceptance. This document maps ownership. Current
[ADRs](decisions/README.md) take precedence over older exploratory topology and
routing examples; Proposed ADRs remain proposals.

```text
User / interactive client
         |
Personal Agent (BLAINE.md + selected skills)
         |
TaskSpec / transport-neutral controls (D2 ACP binding)
         |
Durable Runtime (currently Restate) -- replaceable workers and verifiers
         |
Task evidence / external sources
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

The instruction harness expresses semantic procedures. The [D2 implementation](daily-driver-d2.md)
binds transport-neutral controls to durable kernel Tasks through the official ACP SDK.
Its bounded acceptance includes a workspace fixture; live IntelliJ investigation,
edits and test execution remain D3. Contracts describe intent and guarantees; consult
D2 documentation for the implemented surface and its supported scope.

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
