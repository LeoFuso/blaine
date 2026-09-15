---
name: task-signal
description: Steer an existing Task with continue, approval, rejection, cancellation, context, or constraint changes.
---

# task-signal

Read the [operation contract](../../docs/contracts/task-operations.md) and
[lifecycle/safety policy](../../docs/policies/task-completion-and-lifecycle.md).
Resolve an unambiguous Task ID and query current state, constraints, revision, and
pending decisions before forming the signal. Preserve existing authorization scope.

| Action | Payload and meaning |
|--------|---------------------|
| `continue` | Optional explanation; request resumption when prerequisites are satisfied. Does not grant approval or retry a terminal Task by itself. |
| `approve` | Current decision ID and exact approved action/scope; use the user's explicit authorization, never a generic “continue” as blanket consent. |
| `reject` | Current decision ID, optional reason; declines that proposal, without implicitly cancelling all work. |
| `cancel` | Optional reason; request cancellation. Report pending until runtime confirms effect; cancellation does not undo prior side effects. |
| `add-context` | Context requirements/references using TaskSpec context shape, with provenance and sharing restrictions; not a replacement objective or permission grant. |
| `modify-constraints` | Explicit proposed changes to autonomy, cloud, or completion constraints and optional reason. Show scope; do not silently loosen protections or erase unmet criteria. |

A different objective is normally new work; clarify whether the user intends a new
Task when a constraint change would replace the original outcome.
Submit the signal with request identity and concurrency protection. Report whether
it was accepted, applied, or rejected, including what the runtime still waits for.
On a stale decision or revision, refresh and reconcile intent before resubmission.
Without a binding, present the exact proposed signal as unsubmitted.
