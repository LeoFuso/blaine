# Worker decomposition and review

This policy informs bounded planning inside a Task. Runtime owns dispatch,
coordination, attempts, waits, and recovery; the Personal Agent does not execute an
orchestration loop in conversation. Workers remain replaceable capability adapters.

Keep tightly coupled work together. Propose decomposition only when independent
units, distinct capabilities, or context limits justify its coordination cost.
Parallelism is optional; task size alone does not mandate it. If coupling is unclear,
request bounded discovery before choosing a decomposition.

Readers may share sources, subject to their access limits and source freshness.
Concurrent writers need isolated workspaces or clearly exclusive ownership; never
allow conflicting writes to the same files. Preserve unrelated user work.

Independent review is useful when a wrong judgment has material consequences.
Give reviewers criteria and evidence; ask for specific gaps, not generic confidence.
Bound revision work by scope and budget. Report stalled criteria to runtime rather
than looping indefinitely or declaring a lifecycle transition yourself.

Use [local/context policy](local-first-and-context.md) for worker packets and
[completion policy](task-completion-and-lifecycle.md) for evidence assessment.
