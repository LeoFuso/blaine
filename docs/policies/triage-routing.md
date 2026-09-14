# Task boundary and scope refinement

The primary direct/durable distinction lives in [BLAINE.md](../../BLAINE.md#task-boundary).
Do not classify every conversation by size or prescribe a worker before intent is clear.

For borderline requests, ask whether producing the answer requires independent
execution, retained evidence, a wait, or continuation outside this conversation.
A deterministic lookup can support a direct answer. A sustained investigation needs
a Task even when it is read-only. Discussing a plan does not authorize its execution.

Resolve references to existing work before creating new work. A follow-up adding
context or changing constraints usually belongs to task-signal, not task-create.
If a mixed request includes both an immediate question and independent work, separate
those outcomes without generating a Task for the conversational portion.

Clarify only missing information that materially affects the objective, target,
permissions, scheduling, or acceptance. Record reasonable assumptions visibly.
Scope verification by risk and affected contracts, not file-count thresholds.
Use [task-create](../../skills/task-create/SKILL.md) to express the resulting contract.
