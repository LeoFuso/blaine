# Increment 2 — Joined sequential child Tasks

**2026-09-19 · Hypothesis:** a native joined Restate call can run an independent
Task-scoped loop, survive a parent-wait crash and return a bounded TaskResult
without forwarding child history or establishing parent completion.

## Small implementation

`SPAWN_TASK` now passes through the existing PolicyGate and dispatcher. The child
uses the same `CognitiveTaskV1` algorithm under a distinct deterministic key:
`child-<sha256(parent ID, committed decision ID)>`. Its supplied TaskSpec is
validated normally; it starts at revision zero with fresh context/observations.
The parent records the accepted child spec reference, child identity and typed
wait, then directly awaits `ctx.workflow_call(run, key=child_id, arg=child_spec)`.
It stores the returned TaskResult as one observation. No ingress submission,
separate activity abstraction, detached send or parallel scheduler is involved.

The existing `autonomy` gains optional `child_tasks` (0–4, default zero). Before
dispatch, the runtime charges one unit plus any allocation delegated to that
child. Allocations are not replenished on return. Descendant grants must be a
subset of the parent's effective authority. This bounds the complete descendant
tree while keeping capability requirements separate from authority. Context
reports the remaining allocation; TaskState keeps small child/result references.

TaskResult now has explicit boundary validation: matching child identity,
COMPLETED/FAILED outcome, at most 16 digest-addressed artifact refs, verifier
reference for completion, bounded concerns, no extra fields/history and an 8 KiB
ceiling. Terminal child call failure is a failed result observation. Parent
completion still uses only the parent's accepted contract and admitted artifacts.
Text input cannot resolve a wait for a child TaskResult.

The native API was checked in installed SDK **1.0.5** (`Context.workflow_call`)
and the [official service communication documentation](https://docs.restate.dev/develop/python/service-communication).
The empirical server is **1.7.9**. The call itself is durable and is not wrapped
in `run_typed`; Restate records its result and replays it. No dependencies changed.

## Evidence and gate

[Machine-readable evidence](../../experiments/kernel-increment-2/evidence/summary.json)
and [unit transcript](../../experiments/kernel-increment-2/evidence/unit-tests.txt):

- **27 unit tests passed**: earlier behavior plus child authority/allocation,
  deterministic identity and bounded result validation. The previous reserved
  SPAWN test now asserts conservative denial without child allocation.
- Parent and child have exactly **two main invocations**, distinct specs/state
  and **4 parent / 5 child turns**. Two internal child effects and its intermediate
  observations are excluded from the parent packet.
- The child returns **516 bytes**, compared with **7,117 bytes** of cumulative
  child turn inputs. Parent turn 2 observes exactly that TaskResult; its first
  COMPLETE remains **unsatisfied**. It must produce its own exact artifact.
- While the parent awaited the child and the child awaited typed input, the probe
  SIGKILLed/restarted the runtime and then Restate. Both TaskStates were identical
  after restart. Exactly one child was created; committed child turns/effects
  were not repeated. The original journal IDs/bytes/timestamps were preserved.
- Child and parent each reached independently verified COMPLETED. All copied
  artifacts were digest-checked. `results.json`, `journals-before/after.json`,
  `before-crash.json`, `after-restart.json`, `invocations.json`, `cognition.jsonl`
  and `process-events.json` preserve observable evidence.

Reproduce with the pinned Python/server installation:

```bash
.local/runtime-venv/bin/python -m unittest discover -s tests -v
.local/runtime-venv/bin/python scripts/verify-kernel-children.py \
  --restate-server .local/bin/restate-server --output .local/kernel-program/new-child-run
```

Earlier seven-scenario live regression evidence is retained separately under
`experiments/kernel-increment-2/evidence/regression/`. See the
[progress index](cognitive-kernel-progress.md) for the final gate status.

**Architecture deviations: none.** This extends the approved delegation seam.
Fresh isolated deployments were used; upgrading suspended older journals is not
claimed. Child-to-parent result compression does not automatically grant the
parent permission to read arbitrary child files. No detached/parallel execution,
real model, memory or external worker was added here.

**Exact next increment after this gate passes:** 3 — use the already running
shared local Qwen through the same CognitiveAdapter seam, with no inference
installation/configuration change. Stop if that existing service is unavailable.
