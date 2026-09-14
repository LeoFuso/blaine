---
name: task-list
description: Find existing Tasks and summarize their authoritative state without changing them.
---

# task-list

Read the [operation contract](../../docs/contracts/task-operations.md).
Translate the user's scope into supported filters; query the runtime's Task list.
Show compact entries with ID, objective, state, and mode when useful.
State pagination or coverage limits; fetch further pages when needed to answer.
An empty successful query means no matches within its scope, not no Tasks anywhere.
An unavailable query does not mean an empty list.
Use returned IDs for subsequent status, signal, or result operations. If several
Tasks fit a steering request, ask which one before mutating anything.
Do not use a conversation-maintained list as authoritative inventory.
