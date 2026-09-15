---
name: task-create
description: Translate requests for durable work into a TaskSpec and submit through an available binding.
---

# task-create

Read the [TaskSpec contract](../../docs/contracts/task-spec.md) and
[operation boundary](../../docs/contracts/task-operations.md).

1. Apply BLAINE.md's Task boundary. A discussion, explanation, or short supplied-text
   transformation needs no Task. A follow-up to existing work may need a signal instead.
2. Extract outcome, scope, required context, capabilities, constraints, cloud policy,
   and observable completion criteria. Separate user facts from assumptions.
3. Default to interactive mode and the contract's conservative cloud/sharing defaults.
   Include scheduling only for timed work. Use [examples](../../docs/contracts/task-examples.md)
   if helpful; do not force the request into a coding template.
4. Clarify missing targets, consequential permissions, or ambiguous scheduling.
   Do not ask again for authorization already granted within the same scope.
5. Form the smallest complete TaskSpec. Context requirements describe what must be
   resolved, not everything retrieved. Check criteria can be verified independently
   of a worker saying it succeeded.
6. Submit via an available creation binding. Report the returned ID and actual state.
   Without a binding, show the draft and explicitly say no Task has been created.

Do not add workflow graphs, retry plans, or worker-specific lifecycle instructions.
