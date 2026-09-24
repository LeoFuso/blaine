# Contract index

These documents define normative interfaces and invariants within their stated
version/scope. They do not certify that every described operation is implemented.
The [D2 binding guide](../daily-driver-d2.md) identifies the supported subset and
rejects unsupported inputs. The [roadmap](../roadmap/001-blaine-development-roadmap.md)
owns delivery status; [architecture](../architecture.md) owns current boundaries.

| Contract | Authority |
| --- | --- |
| [TaskSpec](task-spec.md) | Conversational intent and constraints; not runtime state or an execution graph. |
| [Task operations](task-operations.md) | Create/status/list/signal/result semantics and binding guarantees. |
| [Task examples](task-examples.md) | Illustrative applications of TaskSpec; not a separate schema or authority grant. |
| [Frontier dispatch](frontier-dispatch.md) | Paid-worker authority, context projection and dispatch evidence. |
| [ExecutionEvent](execution-event.md) | Versioned forensic metadata; never Task lifecycle authority. |
| [Worker execution boundary](worker-execution-boundary.md) | Continuation boundary, adapter capability honesty, synchronous control and asynchronous telemetry; never Task authority. |
| [Context Plane](context-plane.md) | Accepted semantic contracts for trusted binding, Memory/workspace/evidence access, Resolver, Compiler, packets/deltas, promotion and verified learning; production schemas/integration NOT STARTED. |
| [Completion Contract v1](completion-contract.md) | **Implemented in the kernel (E1.0 PASS); E1 end-to-end pending.** Durable revisioned criteria, provenance, verifier taxonomy, amendments, capability journal and completion legality. |
| [E1 workspace capability](workspace-capability.md) | **Design, not implemented.** IDE-delegated read-only workspace authority, IntelliJ MCP provider, operation/receipt schemas, capability relay, E1 acceptance. |

[Lifecycle/evidence](../policies/task-completion-and-lifecycle.md) and
[local-first/context](../policies/local-first-and-context.md) policies apply across
these interfaces. Executable validators are linked by the relevant contract or
binding guide. The research checkpoint still contains some kernel contract
rationale; see the [documentation map's deferred cleanup](../README.md#bounded-reconciliation-and-deferred-cleanup)
rather than infer that all research prose is normative.

Proposed Hub handshake, registration and remote-effect wire schemas are not yet
implemented contracts. Their requirements and decision gates live in the
[Hub design](../personal-agent-hub.md); implementation slices should freeze only
the required versioned contracts here, preserving existing Task ownership.
