---
name: task-status
description: Inspect authoritative progress, waits, and blockers for one existing Task.
---

# task-status

Read the [operation contract](../../docs/contracts/task-operations.md).
Resolve the Task ID; use task-list if the user's reference is ambiguous.
Query current runtime status and report ID, state, meaningful progress, and any
pending decision or blocker. Include observation time when freshness matters.
Do not infer elapsed time, percentages, or ETAs without supporting runtime data.
Separate the runtime's recorded activity from your interpretation of it.
If a user action is required, explain the concrete action and decision reference.
Retrieving deliverables belongs to task-result; changing work belongs to task-signal.
If querying is unavailable, say so; chat memory is not a substitute.
