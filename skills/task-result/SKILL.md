---
name: task-result
description: Retrieve Task deliverables and explain completion evidence, partial results, and concerns.
---

# task-result

Read the [operation contract](../../docs/contracts/task-operations.md) and
[completion evidence policy](../../docs/policies/task-completion-and-lifecycle.md).
Resolve the Task ID and query authoritative result/state. Retrieve only artifacts
needed to answer; retain source references and recorded verification outcomes.
Compare available evidence with the accepted completion contract.
Lead with the outcome, then deliverables and the evidence supporting each material
claim. Mark partial output, unavailable artifacts, failed checks, and uncertainty.
A worker summary or successful exit is not proof of completion.
If runtime reports completion but evidence is missing or contradictory, report both
facts and the verification gap. Do not independently rewrite lifecycle state.
If work is still running, label artifacts as intermediate. Do not claim delivery
merely because an artifact reference exists but cannot be accessed.
If result querying is unavailable, do not manufacture a result from chat memory.
