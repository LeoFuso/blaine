# Personal Agent Task Operations

Bindings expose authoritative operations over durable Tasks.

This document defines the semantic boundary visible to the Personal Agent.
Transport, Restate invocation details, retries, idempotency, concurrency control,
and recovery belong to bindings/runtime rather than the agent's reasoning context.

The Personal Agent never reconstructs current Task state from conversation memory.

The [Daily Driver D2 binding](../daily-driver-d2.md) implements bounded create,
inspection/result/artifact retrieval, typed human/external response, and native
cancellation over the current kernel. ACP is its first private transport; it
does not yet implement all prospective actions or listing below.

## Create

Input:

- [TaskSpec](task-spec.md)

Returns:

- Task ID;
- accepted specification;
- current authoritative state;
- rejection reason when creation was not accepted.

A submitted request is not proof that creation succeeded.

## Work Strategy handoff

TaskSpec remains the durable intent contract. Work Strategy is derived execution
metadata, not a required TaskSpec field or a place for workflow steps or plans.

The Personal Agent / Semantic Triage authors the initial Work Strategy. At Task
creation, Blaine records the current strategy alongside the Task's durable
execution state.

The Durable Runtime is authoritative for which strategy is currently recorded,
but it does not make the semantic judgment that produced that strategy.

When later evidence warrants a change, the Personal Agent or workflow may propose
a revision. Any required policy or user approval is applied before the revision
becomes current. The resulting strategy must be recorded durably; conversation
memory is never authoritative for it.

## Status

Input:

- Task ID.

Returns:

- current authoritative state;
- current activity when available;
- waits or blockers;
- available progress and evidence references.

## List

Returns matching Tasks with enough information to identify them, including:

- Task ID;
- objective;
- current state.

Supported filters are binding-specific.

## Signal

Input:

- Task ID;
- semantic action;
- optional action payload.

The initial semantic actions are:

- `continue`;
- `approve`;
- `reject`;
- `cancel`;
- `add-context`;
- `modify-constraints`.

Returns whether the requested signal was accepted or rejected and the authoritative
resulting state when available.

Not every signal is valid in every runtime state.

`modify-constraints` is also the route for user-originated Completion Contract
amendments; waiving or rebinding a required criterion is only possible through an
explicit human action ([Completion Contract amendments](completion-contract.md#amendments)).
The kernel implements this as the `amend_contract` workflow handler (E1.0): the
binding submits a `CompletionContractAmendmentSubmission` whose actor it
established from its authenticated principal, wrapping the requested change (which
names the expected `from_revision` and carries no authority field). It answers
`SUBMITTED`/`ALREADY_SUBMITTED` or rejects (400 malformed or authority in content,
403 authority, 409 stale or already amended). The Personal Agent binding exposes
this as its `amend` operation and always establishes the user actor; it can never
submit operator or policy authority. The ACP command grammar does not expose `amend`
yet, so in chat the agent must still say such a change is not submitted.

### Target-effect controls (E2.0)

`cancel_effect {operation_id}` asks the kernel to stop one target effect that is
awaiting approval or running. The receipt (`REQUESTED` / `ALREADY_REQUESTED`) is not
proof that anything stopped; the effect's journal outcome says what happened, and
only a cancellation before dispatch proves the effect did not happen. Effect
approvals use the ordinary human-decision response. Task-level `cancel` runs the
same effect stop and reconciliation before the Task ends CANCELLED; it is not
rollback, and the result names every effect's actual outcome
([Task cancellation](target-effects.md#task-cancellation)). No Personal Agent or ACP
binding exposes `cancel_effect` or effect approvals yet ([target effects](target-effects.md)).

## Result

Input:

- Task ID.

Returns:

- authoritative state;
- deliverable references;
- completion criteria and available evidence/verifier outcomes;
- unresolved concerns;
- explicit partial or absent result when appropriate.

Missing or contradictory evidence remains visible even when runtime state reports
completion.

## Binding guarantees

Bindings/runtime, not the Personal Agent, own technical execution guarantees,
including:

- authoritative state reads;
- transport retries and recovery;
- request identities;
- idempotency and deduplication;
- concurrency/revision handling;
- validation of authorization and runtime-state compatibility.

The Personal Agent operates on semantic intent and authoritative results rather
than implementing these mechanisms itself.
