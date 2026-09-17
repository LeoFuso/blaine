# ADR 0016 — Agent harnesses are replaceable execution capabilities

**Status:** Accepted
**Validation:** Unvalidated
**Date:** 2026-09-17

## Context

Blaine may execute work using different agent harnesses and coding agents.
Current examples include Goose, Codex, and Junie. These systems have different
execution models, tool ecosystems, model integrations, context-management
strategies, and strengths.

Blaine must be able to use them without making any single harness part of the
core runtime architecture. In particular, the architecture must not assume a
mandatory hierarchy such as:

```text
Blaine
  ↓
Goose
  ↓
Codex
  ↓
Model
```

Goose, Codex, Junie, and future agent harnesses are alternative execution
capabilities. They may be selected directly when appropriate.

This ADR builds on ADR 0010's Worker Selection model and ADR 0015's durable
Task execution and verification model.

## Decision

Agent harnesses are **replaceable execution capabilities**. A harness is capable
of performing Work on behalf of a runtime Task.

Examples include:

```text
Goose
Codex
Junie
FutureAgentHarness
```

No harness is intrinsically the parent, child, or mandatory entry point for
another harness.

```text
                   Runtime Task
                        │
                        ▼
                 Worker execution
                        │
                capability selection
             ┌──────────┼──────────┐
             ▼          ▼          ▼
           Goose      Codex      Junie
```

The execution architecture depends on the capability contract, not a specific
agent implementation.

## Relationship to Worker Selection

This ADR does not redefine Worker Selection. A registered harness or adapter is
a capability available to the execution system. A Worker is the anonymous
execution unit that uses capabilities to perform Work.

```text
Registered capability:
    Codex

Concrete execution:
    Worker uses Codex to perform Work
```

The registered capability may have stable configuration and metadata; the Worker
execution remains ephemeral.

> **Capability identity is not Worker identity.**

Capability requirements describe what Work needs. They are not permission grants
and do not select a harness by themselves. Worker Selection determines eligible
candidates under ADR 0010; runtime policy then enforces the capabilities,
autonomy, and authorization actually granted to an execution.

## Harnesses are peers

Agent harnesses are peer execution capabilities.

- Goose is not required to wrap Codex.
- Codex is not required to execute through Goose.
- Junie is not required to execute through either.

For example:

```text
Work A → Goose
Work B → Codex
Work C → Junie
```

Selection may depend on required capabilities, repository characteristics,
available tools, execution environment, model availability, budget, policy, or
empirical performance. The selection mechanism is outside the scope of this
ADR.

## Harness delegation

A harness may discover that additional work should use another capability. This
does not make one harness an architectural container for another.

```text
Work
  ↓
Goose
  ↓
discovers specialized coding work
  ↓
additional Work / Task
  ↓
Codex
```

> **Delegation occurs through Work or Task coordination, not because Codex is
> structurally a child of Goose.**

Direct invocation of another harness may be useful within a concrete adapter,
but remains an optimization or adapter behavior rather than a domain
architecture requirement.

## Harnesses and models are different concepts

An agent harness is not the same thing as a model.

Examples of harnesses include:

```text
Goose
Codex agent
Junie
```

Examples of models include:

```text
GPT
Claude
Gemini
local models
```

A harness may use one model, select between several models, switch models during
execution, expose model-selection behavior, or delegate decisions to an external
provider.

Blaine does not require the internal model topology of a harness to become part
of the runtime domain model. From the runtime's perspective, a harness performs
Work and produces observable results.

## Providers, funding, and cloud boundaries

Provider, authentication, quota, and funding policies are separate from the
harness abstraction. A capability may use an authorized provider/account,
configured provider, or local inference; these choices may influence selection
but do not redefine Task, Work, Worker, or Completion semantics.

A cloud-hosted harness or externally hosted model is a Cloud Worker under ADRs
0008 and 0009. It therefore receives an explicit Cloud Context Packet. When its
invocation incurs paid cloud usage, it additionally crosses the Paid Cloud
Dispatch Boundary.

Selecting a harness does not authorize provider access, paid usage, or context
egress. An adapter cannot bypass those boundaries merely because its internal
implementation can invoke another model or service.

## Runtime authority

Agent harnesses execute Work. They do not own Task lifecycle.

A harness may return code, files, proposed changes, structured responses,
findings, execution summaries, tool results, or other Artifacts. These outputs
become Artifacts or Evidence available to the runtime; they do not by themselves
transition a Task to completion.

The rules established by ADR 0015 remain authoritative:

```text
Harness executes
      ↓
Artifact / finding
      ↓
Verification
      ↓
Completion Contract
      ↓
Runtime transition
```

> **Harness success is not Task success.**

> **A harness reporting “done” does not complete the Task.**

## Harness sessions are not durable Task state

A harness may maintain conversation history, tool context, planning state, local
checkpoints, or model-specific session information. This state may be useful to
that harness; it is not authoritative durable Task state.

A harness session may disappear and another execution may continue the Task
using persisted runtime state and Artifacts.

> **Task continuity must not depend on harness-session continuity.**

## Internal harness behavior

The runtime avoids modeling an agent harness's internal reasoning lifecycle.

For example, if Goose internally plans, chooses a model, calls tools, reasons,
or replans, these are normally implementation details. Likewise, if Codex or
Junie internally spawn sub-agents, perform planning passes, or manage context
windows, these behaviors do not automatically become Blaine domain concepts.

Only information required for durable execution, policy enforcement,
verification, observability, cost control, security, or recovery crosses the
capability boundary.

> **The runtime controls lifecycle, not thought.**

## Capability contract

The contract between runtime and harness remains deliberately small. Conceptually,
the runtime provides:

```text
Work outcome and required capability / quality
Selected permitted context
Constraints and autonomy limits
Expected output and completion criteria
Applicable policy and authorization state
```

and receives:

```text
Artifacts
Findings
Execution metadata
Potential blockers
```

For external execution, selected context must already satisfy the applicable
egress process; a Cloud Context Packet is the relevant bounded context artifact.

This is a conceptual boundary, not a requirement to introduce one universal
interface immediately. Adapters should emerge from concrete integration needs.

## Replaceability

No core Task semantics may depend on Goose-, Codex-, Junie-, or
provider-specific lifecycle concepts. Adding or replacing a harness must not
require redefining:

- Task;
- Work;
- Worker;
- Artifact;
- Evidence;
- Completion Contract;
- Card; or
- runtime lifecycle.

Harness-specific configuration belongs at the capability or adapter boundary.

## Failure

Failure of a harness execution is a Work execution result, not automatically
Task failure. The runtime may retry the same harness, use another harness,
request reselection to another eligible capability, perform different Work,
wait, request input, or fail the Task according to the Task's runtime policy.

Likewise, a successful harness invocation may still require further Work and
Verification.

## Example

Consider a Task to implement and verify a repository change. The runtime might
execute:

```text
Task
 │
 ├── Work: inspect architecture
 │      ↓
 │    Goose
 │
 ├── Work: implement repository changes
 │      ↓
 │    Codex
 │
 ├── Work: independent review
 │      ↓
 │    Junie
 │
 └── Verification
        ↓
     compiler / tests / verifier
```

Alternatively, one harness may perform all Work. Both are valid; the Task
lifecycle and Completion Contract remain unchanged.

## Non-goals

This ADR does not decide:

- which harness should be the default;
- whether Goose, Codex, or Junie performs better;
- how capability selection is scored;
- exact adapter interfaces;
- how provider quotas are balanced;
- whether a harness may internally use another agent; or
- how Restate maps individual harness invocations to handlers or Workflows.

These should be decided from implementation requirements and empirical evidence.

## Relationship to other decisions

### Worker Selection

ADR 0010 determines how execution capabilities are matched to Work. This ADR
clarifies that agent harnesses are such capabilities and that their stable
registration is distinct from ephemeral Worker identity.

### Durable Task execution and verification

ADR 0015 remains authoritative over Task lifecycle. Harnesses produce Artifacts
and findings; Verifiers evaluate applicable evidence; the runtime applies those
findings to the Completion Contract and records lifecycle transitions.

### Cloud dispatch and context egress

ADRs 0008 and 0009 remain authoritative for paid cloud authorization, provider
allowlists, context egress, and Cloud Context Packets. Harness selection cannot
bypass them.

### Cards

Cards represent human project coordination. Harnesses operate in the execution
plane. A Card need not identify or persist the harness or Worker that performed
individual Work unless it is useful for observability.

## Consequences

This decision allows Blaine to:

- use Goose without depending structurally on Goose;
- invoke Codex directly when appropriate;
- use Junie independently;
- add future agent harnesses;
- compare harness performance empirically;
- route Work according to capability, policy, cost, or availability;
- survive harness-session loss;
- change providers without changing Task semantics; and
- avoid treating agent frameworks as the runtime itself.

The central principles are:

> **Agent harnesses are execution capabilities, not architectural parents.**

> **Harnesses are peers unless a specific execution chooses to delegate.**

> **Capability identity is not Worker identity.**

> **Models, harnesses, and providers are separate concepts.**

> **Harness sessions do not own durable Task state.**

> **Harness output is evidence, not lifecycle authority.**

> **The runtime remains authoritative over Task completion.**

## Validation

### Hypothesis

Blaine can execute equivalent bounded Work through two independent harness
capabilities without changing Task semantics, granting either harness lifecycle
authority, or allowing a selected cloud harness to bypass cloud policy.

### Validation level

Integration, followed by an end-to-end Task using a real harness when one is
available.

### Minimal validation

Construct two harness adapters with distinct invocation mechanisms. Route the
same bounded Work to each through Worker Selection, capture their outputs as
Artifacts or findings, and verify the result through the same Completion
Contract.

Demonstrate that one harness can run directly without routing through the other.
Have one harness report success without sufficient verification evidence and
confirm that the Task remains incomplete. Interrupt one harness session and
resume the same Task with the other adapter.

Use a fake cloud-classified adapter to demonstrate that it receives a prepared
Context Packet and that a direct paid-dispatch bypass is rejected before any
external invocation.

### Evidence

PASS requires demonstrating that:

- either harness can execute the same Work without changing Task or Card
  lifecycle semantics;
- no harness is a mandatory parent of another;
- outputs are retained as Artifacts or findings rather than completion claims;
- the Completion Contract and runtime, not a harness result, control Task
  completion;
- a lost harness session can be replaced without losing durable Task state; and
- selected cloud-classified execution cannot bypass context-egress or paid-cloud
  dispatch enforcement.

### Not required for validation

- a production provider account or paid tokens;
- final harness-scoring policy;
- a universal adapter interface;
- SpecKit execution;
- MCP exposure;
- GPU scheduling; or
- a production Card provider.

### Reconsider when

Reconsider if independent harness integrations require incompatible core Task
semantics, if the capability boundary cannot preserve required policy and
verification controls, or if a supposedly replaceable harness becomes a de facto
durable lifecycle dependency.
