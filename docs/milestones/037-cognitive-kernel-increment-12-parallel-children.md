# Increment 12 — bounded parallel child Tasks

**2026-09-20 — PASS. Stop after this increment; no further development cycle started.**

Hypothesis: the existing Task-scoped workflow can issue several native joined calls
before awaiting them, let each child progress independently, and reconstruct the
same parent/children after interruption without repeating committed work.

## Small runtime extension

`SPAWN_TASK` retains its single `task_spec` form. A mutually exclusive batch form
accepts `task_specs` (2–4 validated TaskSpec envelopes) plus `independent: true`.
This is a bounded extension of the existing internal decision contract; no new
model-facing SemanticDecision vocabulary, decomposition model or routing was added.
Acceptance uses scripted decisions, not inference.

The dispatcher creates every native `ctx.workflow_call` future before awaiting any.
The installed Python SDK **1.0.5** implements this synchronously through
`workflow_call → object_call → do_raw_call → vm.sys_call`; it returns a durable
future. The empirical server is **Restate 1.7.9**. No coroutine pool, external
scheduler, ingress child submission, detached send or new lifecycle engine is used.

Each child receives a versioned internal `ChildTaskRequest` containing its accepted
TaskSpec and a validated parent relationship: parent Task ID, committed decision
identity and child slot. This metadata is system-produced, not inferred by parsing
Task/session IDs. The child key hashes those fields. Single-child IDs retain the
previous derivation (no slot), and standalone TaskSpec requests still work.

Each child stores its own TaskState, spec reference, parent relationship, iteration,
wait, artifacts, verifier and result. The parent stores only relationship/spec/result
references. Fresh child context comes from its own bounded spec and reconstruction;
no inherited transcript or mutable context is shared. Work/session IDs are not Task
IDs. These are native Tasks even when the application process is absent.

The existing `autonomy.child_tasks` ceiling (maximum 4 for the whole allocated tree)
is charged atomically for the batch, including delegated descendant allocations.
Independence is explicit caller intent, not an inferred strategy or a dependency analyzer.
One invalid/excessive grant denies the entire batch before creation. Every child's
allowed capabilities must remain a subset of the parent's effective authority;
each child still has its own PolicyGate. The fixture shares only operation-keyed
SQLite effects and immutable Task-scoped artifacts. No generic shared-resource
scheduler, model-token accounting or concurrency policy platform was introduced.

## Join, outcomes and completion

The dependency is **ALL_TERMINAL**: collect every required outcome before parent
continuation, including truthful failures. This permits reporting a failed child
without hiding it or leaving siblings detached. It is not ANY, quorum, race or
fail-fast cancellation. Success paths require all successful child outcomes in the
scripted acceptance strategy; even then the parent's verifier must independently
pass. A different parent contract is not silently inferred.

While dependent children run or wait, the parent persists WAITING with typed child
IDs, revision and condition, and awaits native futures. No cognitive WAIT proposal
is requested. Child outcomes are consumed in declared slot order, regardless of
physical completion order. The parent resumes only after the join. A malformed or
misaddressed result is rejected, retained as a bounded `invalid_result` boundary
category, and causes parent failure after the other launched children have joined;
it cannot detach them or become successful evidence. This negative control is
synthetic/offline, not claimed as a malformed native Restate response.

Each original bounded TaskResult is stored exactly as an artifact in the parent's
namespace. Batch cognition receives `ChildTaskResults` with child ID, outcome,
TaskResult reference and child completion reference. It does not receive child
transcripts. Failure concerns and partial artifact refs remain in the referenced
TaskResult. The exercised packets are **844–851 bytes**. Single-child observation
remains the existing TaskResult form.

Child artifact refs are never inserted into the parent's artifact map. After
joining, the existing parent CompletionVerifier still reports missing parent
evidence. The parent must execute its own admitted artifact action before its own
contract passes. Neither child success, worker status nor ExecutionEvent can set
parent completion. No CompletionContract/Verifier or PolicyGate authority changed.

## Empirical acceptance

[Machine-readable summary](../../experiments/kernel-increment-12/evidence/summary.json)
and [native evidence](../../experiments/kernel-increment-12/evidence/acceptance/):

| Scenario | Independently terminal children | Parent | Evidence |
|---|---|---|---|
| A then B | COMPLETED / COMPLETED | COMPLETED | Both waited independently; A completed while B remained waiting |
| B then A | COMPLETED / COMPLETED | COMPLETED | Same slot-ordered projection and exact `A+B` parent output |
| Deterministic failure | COMPLETED / FAILED | FAILED | Wrong child artifact fails its unchanged verifier; truthful result returned |
| Child authority denial | COMPLETED / FAILED | FAILED | Forbidden fixture effect never invoked; policy denial and failure observable |

There are **12 real Tasks: 4 parents and 8 children**, exactly **8 native child
creation calls**, **7 committed fixture effects**, and zero duplicate child calls,
capability executions, cognitive turns or terminal events. Parent cognition while
waiting is **zero** in every case. All cognition is scripted; model/cloud calls are
zero. Successful parents take 2 turns. Failure controls terminate at the existing
16-turn bound using rejected COMPLETE proposals, without re-dispatch or escalation;
this is not a new automatic recovery strategy or new failure policy.

The A/B case SIGKILLs and restarts both the application runtime and Restate at:

1. both children created, effects committed, both waiting;
2. A completed, B still waiting, parent waiting;
3. all outcomes joined, parent held at a test-only durable pre-continuation barrier.

Each snapshot is identical after fresh processes start; cognition counts are
unchanged. Before/after native journal prefixes retain invocation IDs, indices,
raw entries and original append timestamps. Final capability audits contain one
execution per operation ID. The completed A evidence survives; the final parent
effect and completion occur once. Duplicate child input and unrelated parent input
are rejected. No custom deduplication store was added.

**410 ExecutionEvents** record creation, parent suspension, observed child outcomes,
resume, policy/effects and independent verification. Added families are
`task.child_created`, `task.child_observed`, `task.suspended`, `task.resumed`, with
explicit parent/child references. Child terminal events have their own Task/run
identities. Logical identity is not fabricated trace identity. Events are optional
forensics; Task state never reads them as authority.

## Validation, scope and limits

- 8 focused offline topology tests pass: explicit relationship, stable IDs, batch
  bounds/allocation/authority, reversed order, failure, malformed/stale results,
  waiting, independent completion and single-child compatibility.
- Full focused Cognitive Kernel suite: **122 tests passed**.
- Native independent verifier checks journal call counts, every artifact digest,
  all child and parent contracts, outcome order, suspension snapshots, restart
  preservation, effect audits and event uniqueness.
- Historical frontier/projection and live-001/live-002 evidence is unchanged;
  their offline verifiers retain the accepted PASS/STOP outcomes.
- Increment 10 historical verification passes against its recorded source hashes
  materialized from `f95b27b`; its source-pinning check intentionally rejects the
  changed current workflow/events files. Historical evidence and that verifier were
  not rewritten. Current topology/authority behavior is covered by this increment.
- `git diff --check` passes. No model/provider calls, secret inspection, installations,
  platform/D1 edits or unrelated-worktree changes.

The probe uses fresh isolated deployments and tests recovery under one fixed
workflow implementation. It does not claim that old suspended journals can be
hot-upgraded across this dispatcher change. No Task cancellation contract or
cascading cancellation is introduced. No Worker Session architecture, Multica,
DAG/DSL, builder/critic, debate, context compiler, project graph, Jev, learned
routing, automatic escalation, UI or frontier change was implemented.

**Architecture impact:** the authorized local extension to bounded parallel Task
topology; no new authority/storage/lifecycle owner and no unresolved contradiction.
No broad ADR is needed. Exact next action: stop and report; this is the last defined
increment, not authorization for another development cycle.

Reproduce local-only native acceptance with a fresh output directory:

```bash
.local/runtime-venv/bin/python scripts/verify-kernel-parallel.py \
  --restate-server .local/bin/restate-server --output /tmp/blaine-parallel-fresh
```

Verify preserved evidence offline:

```bash
.local/runtime-venv/bin/python experiments/kernel-increment-12/verify.py \
  experiments/kernel-increment-12/evidence/acceptance
```
