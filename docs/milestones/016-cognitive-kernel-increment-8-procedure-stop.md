# Increment 8 — procedure context live gate FAIL / STOP

Hypothesis: selected Spec Kit clarification guidance can inform Qwen through the
existing context seam, producing clarification → answer → work → verified
completion without runtime thought-phase states.

The repository contains ADR 0006's optional strategy, but no installed Spec Kit
command assets were found in the targeted locations. One official upstream
[clarification command](https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/clarify.md)
was read. A bounded, explicitly adapted excerpt was packaged as procedure context;
upstream scripts/hooks were neither installed nor executed. This is a selected
procedure excerpt, not a complete Spec Kit CLI integration.

`ProcedureContext` supplies the selected Task with sourced, digest-bound guidance
marked `derived`, grants no authority, and omits it for unrelated Tasks. No
existing runtime, contract, model adapter, lifecycle or verifier was changed.

## STOP REPORT

- **Expected:** real Qwen chooses WAIT for missing retention duration, consumes
  the controlled answer, writes the required artifact, then requests COMPLETE.
- **Observed:** three live Qwen decisions were WAIT → artifact.write → WAIT.
  Turn 2 observed `Retain exports for 30 days.` and successfully wrote exact
  `RETENTION_30_DAYS`. Turn 3 requested another retention wait. The Task remained
  durably WAITING; no COMPLETE or completion evaluation occurred. The experiment
  controller was interrupted after capturing that state and cleaned up only its
  isolated runtime/server. No second answer or additional inference was supplied.
- **Evidence:** the third packet contains the successful CapabilityResult and
  answer artifact reference, but no longer includes the earlier ExternalInput.
  Accepted objective text still describes retention as unresolved. These facts
  identify a concrete context/model counterexample, not its isolated cause.
  Qwen also omitted the requested operational question/reason. The existing
  guidance schema omits the optional reason field that application validation
  accepts; no schema correction was attempted during this stopped gate.
- **Architecture impact:** no implemented deviation. The relevant-context seam
  needs investigation before claiming this multi-turn procedure works. There is
  no evidence that a new runtime phase machine is needed.
- **Attempted:** one small provider, one selected excerpt, one focused test and
  one three-inference live Task. All 37 focused tests pass; they do not override
  the failed live gate. Existing Increment 7 runtime hashes remain unchanged.
- **Unresolved question:** whether the repeated wait is caused by insufficient
  reconstruction of the accepted clarification, stale objective wording, the
  procedure/prompt combination or model behavior. No broad investigation or
  workaround was performed.
- **Exact human decision required:** authorize a narrow Increment 8 prompt/context
  diagnostic using this captured counterexample before any corrective change.
- **Safest next option:** inspect how the accepted clarification is represented
  on later turns and reconcile the small schema-guidance mismatch. Preserve
  Task/lifecycle/completion authority; do not force COMPLETE or inject a scripted
  semantic decision to obtain a pass.

Inference provenance: direct existing JSON-only adapter, three local vLLM
`Qwen/Qwen3.5-9B` responses, captured raw public content/model metadata and strict
validated decisions. This probe used no Goose, auxiliary title calls, MIRIX or
cloud. The external answer was an explicit controlled fixture, not a real user's
approval. No private reasoning is retained.

[Summary](../../experiments/kernel-increment-8/evidence/summary.json),
[counterexample](../../experiments/kernel-increment-8/evidence/counterexample.json),
[actual packets/decisions](../../experiments/kernel-increment-8/evidence/cognition.jsonl),
[raw provider evidence](../../experiments/kernel-increment-8/evidence/wire.jsonl),
[stopped Task state](../../experiments/kernel-increment-8/evidence/stopped-state.json),
[tests](../../experiments/kernel-increment-8/evidence/tests.txt).

Next remains **8**. Increments 9–12 were not started.
