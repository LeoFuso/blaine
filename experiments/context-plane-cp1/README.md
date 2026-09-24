# CP.1 production acceptance

**PASS — 2026-09-24.** Opt-in hosted local Context Plane through the existing owned
loop and Goose worker. No deployment enablement, push, CP.2 or Track III reopening.

**Final handoff: READY_FOR_PIPELINE.** Normal merge `e9e9196` reconciles CP.1 with
E1.0 at `origin/main f0a3ca5`. See the
[qualification record](evidence/reconciliation/qualification.json),
[CI matrix](evidence/reconciliation/ci-matrix.json) and
[rerun guide/results](evidence/reconciliation/README.md).
333 root tests (22 CP.1), six repeated CI host/readiness tests, and all three native
gates passed. Current Completion Contracts now govern compiled requirements and
admission; authorized amendments invalidate stale worker/handoff context.
No automatic GitHub workflow matches this diff; no push/PR/main merge was performed.

Original pre-E1.0 implementation evidence, preserved unchanged:

- [Acceptance and evidence hashes](evidence/acceptance.json).
- [217 relevant tests](evidence/regressions/summary.json), including 21 deterministic
  CP.1 enforcement tests; full test names/results in the five adjacent logs.
- [Native Restate + real local Goose](evidence/live/summary.json): two physical
  dispatches, one fresh delta, independently verified exact `GOOD` artifact.
- [Worker inputs/results](evidence/live/workers.jsonl),
  [recorded cognition](evidence/live/cognition.jsonl),
  [capability results](evidence/live/capabilities.jsonl),
  [delta](evidence/live/delta.json), [verifier](evidence/live/verification.json).
- [Executable contract](../../docs/contracts/context-plane-cp1.md) and
  [milestone/handoff](../../docs/milestones/055-context-plane-cp1.md).

Native versions: Restate 1.7.9 / SDK 1.0.5, Goose 1.50.1,
local `nvidia/Qwen3.8-27B-NVFP4`. WorkerInput bytes: **2167 → 2150**;
delta **2316**; CognitiveTurn **1869 / 2542 / 2787**; capability results
**427 / 672 / 428**. Whole UTF-8 envelopes, including metadata, were measured.
The worker packets' embedded metrics record considered/selected material and partial
status. Exact material was never truncated. Final smoke includes tested-source hashes.

The native coordinator is deliberately recorded cognition, not a live model. Goose
is real, local, one-shot and tool-free. This proves packet delivery and exact-artifact
completion in the native runtime; it is not a behavioral utility or kill/resume claim.
Memory is a qualified in-process read-only fixture. **Live MIRIX is not qualified or
adopted**; optional absence is explicit. Production writes and storage decisions remain
CP.2. The earlier [initial smoke](evidence/initial-smoke-summary.json) also passed;
the final smoke followed delivery-guard tightening and adds tested-source hashes.

Deterministic controls include whole-tree validation, exact lineage/security/policy
intersection, hidden/unknown locator equivalence, provider forgery/corruption, explicit
empty/denied/unavailable/insufficient states, forged compiler receipts, exact-byte budget
failure, source changes, policy narrowing, admission changes during compilation,
physical cognition/worker delivery rechecks, one-delta enforcement, replay without new
calls and partial replay refusing revoked authority. Deliberately unsafe scope and
artifact-membership controls actually leak forbidden/uncompiled sentinels and are caught.
Negative literal/reference scans cover caller packets, safe status/diagnostics and the
native application's ordinary log. Private deployment snapshots/admissions are not
included in public artifact maps or copied into retained public evidence.

## Reproduce

Use an existing Python environment with `runtime/requirements.txt` installed. These
commands do not install dependencies or reconfigure host services:

```sh
python scripts/verify-context-plane-tests.py --output /tmp/cp1-regressions
python scripts/verify-context-plane-cp1.py \
  --output /tmp/cp1-native-new \
  --restate-server /path/to/restate-server \
  --goose /path/to/goose \
  --model EXISTING_LOCAL_MODEL_ID
```

The native fixture needs local IPC/network permission, an already-serving model at
127.0.0.1:8000 and a fresh output directory. It binds ephemeral loopback ports, runs one
Task with at most two 60-second worker calls, and cleans up only its own app/server
processes. It never starts/reconfigures the model service or uses a cloud endpoint.
Temporary Restate databases, private artifact storage and Goose scratch are excluded
from committed evidence. There is no replacement Task ledger.

An initial broad sandbox test attempt stopped at ACP IPC restrictions and was interrupted;
the bounded relevant suites above then passed with local IPC permission. No platform
suite is claimed. Existing telemetry exporter timeout diagnostics are non-authoritative
and did not fail the kernel suite.

The [implementation TaskSpec draft](task-request.json) is explicitly **not submitted**:
there was no Blaine creation binding in this Codex session. The native smoke Task is a
separate synthetic acceptance Task, not a claim that the implementation request ran in
Blaine's durable execution system.
