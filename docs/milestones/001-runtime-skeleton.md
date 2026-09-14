# Milestone 001 — Runtime Skeleton

**State: DONE WITH CONCERNS — live spike passed; initial smoke-test process cleanup remains.**

This is the narrow evaluation requested on 2026-09-14. It supersedes the broader
first-slice scope in the ADK document for this milestone only. ADR 0003 remains
Proposed. No client, agent, routing, plugin, or context abstractions are included.

## Shape and contract

`runtime/app.py` exposes `TaskWorkflow` through the Restate Python SDK and
Hypercorn. The caller supplies a stable task ID as the workflow URL key. The
request accepts a nonblank `objective` and optional integer `delay_seconds`
(0–300, default 30). The operation computes word count and a SHA-256 digest of
the exact UTF-8 objective inside `ctx.run_typed`. A durable timer then leaves a
window for crash testing. The result includes the same task ID.

The shared `status` handler reads Restate state while `run` is active. A
`RUNNING` status with `phase: durable-timer` means the operation has returned and
the workflow has reached the checkpoint before its timer. `NOT_FOUND` means no
application state has been written yet (including a just-submitted workflow),
not an authoritative server-level absence check. Completed state contains the
result. Invalid input raises a terminal HTTP 400 error before writing task state;
inspect invocation errors through Restate, not the application status field.

Workflow state, journal, timers, and results belong to Restate. There is no
application ledger. A repeated workflow ID does not create new work; use a new
ID for a new objective. Identity/result retention is governed by Restate's
workflow retention, not a promise of indefinite ID reservation.

## Local setup

From the repository root:

```bash
bash scripts/setup-runtime.sh
```

This uses the existing Python 3.14 in `.local/runtime-venv`, downloads uv 0.12.13
as a binary into `.local/bin`, and installs `restate-sdk==1.0.5` plus
`hypercorn==0.17.3` into that environment. Python downloads are disabled. There
is no need for system pip or `ensurepip`. Source builds are disabled so a missing
compatible wheel fails visibly. **If installation or SDK import reveals Python
3.14 incompatibility, stop and report it; do not install another host Python.**

After the SDK import check, setup downloads the native Restate 1.7.9 Linux x86_64
server into `.local/bin`. All downloads/cache files stay under `.local`, which
is already ignored by Git. No Docker, sudo, shell profile changes, host
configuration changes, or global package installs are involved. Transitive
dependencies are not locked yet; a successful install records their versions
in `.local/runtime-resolved.txt`. The pinned combination installed successfully on Python 3.14.4. Setup requires network access to official GitHub releases and PyPI.

Start in separate terminals at the repository root:

```bash
bash scripts/run-restate.sh
```

```bash
bash scripts/run-runtime.sh
```

Restate persistence is configured under `.local/restate-data` with stable node
name `blaine-local`; the launcher changes to the repository root before loading
the config. The runtime uses loopback port 9080; Restate uses loopback 8080
(ingress), 9070 (admin/UI), and 5122 (fabric). The Restate launcher clears inherited
`RESTATE_*` variables so host settings cannot override this configuration.
Do not pass listener/data overrides to the launcher during this evaluation.

Register once, then submit and inspect:

```bash
curl --fail-with-body http://127.0.0.1:9070/deployments \
  --json '{"uri":"http://127.0.0.1:9080"}'
curl --fail-with-body http://127.0.0.1:8080/TaskWorkflow/example-001/run/send \
  --json '{"objective":"hello world","delay_seconds":30}'
curl --fail-with-body -X POST http://127.0.0.1:8080/TaskWorkflow/example-001/status
curl --fail-with-body http://127.0.0.1:8080/restate/workflow/TaskWorkflow/example-001/attach
```

The final result should contain `task_id: example-001`, `status: COMPLETED`,
`word_count: 2`, and digest
`b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9`.
`attach` waits for completion; status calls go through Restate on 8080, not
directly to the runtime endpoint.

Open <http://127.0.0.1:9070> and select the TaskWorkflow invocation to inspect
its journal. Verify `summarize-objective`, timer, and final result. Journals are
configured for one-day retention for this spike. Serving the UI alone is not
evidence that execution has been inspected.

## Recovery experiment — manual procedure

Only use the following on the spike processes. Stop the foreground instances
first. Check that the listed ports are free; do not kill unrelated services.
Use a single shell so `$!` refers to the processes launched here. The launchers
use `exec`, so these PIDs identify the actual server/runtime processes.

```bash
mkdir -p .local/evidence
ss -ltnp '( sport = :8080 or sport = :9070 or sport = :9080 or sport = :5122 )'
bash scripts/run-restate.sh > .local/evidence/restate.log 2>&1 &
restate_pid=$!
bash scripts/run-runtime.sh > .local/evidence/runtime.log 2>&1 &
runtime_pid=$!
```

Wait for successful startup in the logs, register the deployment if this is
the first start, and verify listeners are loopback-only. Do not force-register
or change code/deployment between the crash and restart. Preserve the data
directory throughout. Recovery consists of restarting the same binary and
runtime against that directory; no cleanup, replay from a client, or restore is
part of the test.

### Runtime process crash

Choose a fresh ID (record its value and the invocation ID returned by `/send`):

```bash
task_id="runtime-crash-$(date +%s)"
curl --fail-with-body "http://127.0.0.1:8080/TaskWorkflow/$task_id/run/send" \
  --json '{"objective":"hello world","delay_seconds":120}' \
  > .local/evidence/runtime-send.json
curl --fail-with-body -X POST "http://127.0.0.1:8080/TaskWorkflow/$task_id/status" \
  > .local/evidence/runtime-before.json
cat .local/evidence/runtime-before.json
```

Repeat the status query until it shows `RUNNING`, `durable-timer`, the correct
ID, and `operation_result`. If it has already completed, use a fresh task.
Record the pending invocation and journal in the Restate UI, then:

```bash
kill -KILL "$runtime_pid"
wait "$runtime_pid" || true
bash scripts/run-runtime.sh >> .local/evidence/runtime.log 2>&1 &
runtime_pid=$!
curl --fail-with-body --max-time 180 \
  "http://127.0.0.1:8080/restate/workflow/TaskWorkflow/$task_id/attach" \
  > .local/evidence/runtime-after.json
cat .local/evidence/runtime-after.json
```

Require the same task ID and expected result without resubmission. Inspect the
journal for the recorded operation and timer. A deterministic result alone does
not prove that the operation was skipped on replay. Do not claim exactly-once
external side effects: this spike has none.

### Restate process crash

Keep the runtime running. Submit another fresh ID with a 120-second timer and
capture its running checkpoint as above, using `server-*` evidence filenames:

```bash
task_id="server-crash-$(date +%s)"
curl --fail-with-body "http://127.0.0.1:8080/TaskWorkflow/$task_id/run/send" \
  --json '{"objective":"hello world","delay_seconds":120}' \
  > .local/evidence/server-send.json
curl --fail-with-body -X POST "http://127.0.0.1:8080/TaskWorkflow/$task_id/status" \
  > .local/evidence/server-before.json
cat .local/evidence/server-before.json
```

Require `RUNNING` / `durable-timer` before proceeding. Record the pending
invocation in the UI, then:

```bash
kill -KILL "$restate_pid"
wait "$restate_pid" || true
bash scripts/run-restate.sh >> .local/evidence/restate.log 2>&1 &
restate_pid=$!
```

Wait for Restate readiness in its log. Without re-registering or resubmitting:

```bash
curl --fail-with-body --max-time 180 \
  "http://127.0.0.1:8080/restate/workflow/TaskWorkflow/$task_id/attach" \
  > .local/evidence/server-after.json
cat .local/evidence/server-after.json
du -sh .local/restate-data
```

Require the original task ID and expected result. Inspect the recovered journal
and retain before/after responses, logs, invocation IDs, and UI evidence.
This tests process-crash persistence, not power loss, disk loss, replication,
backups, or recovery across code/schema upgrades.

Stop only these processes after collecting evidence; retain their data:

```bash
kill -TERM "$runtime_pid" "$restate_pid"
wait "$runtime_pid" "$restate_pid" || true
```

## Live evaluation — 2026-09-14

Setup succeeded: uv 0.12.13, Python 3.14.4, restate-sdk 1.0.5,
Hypercorn 0.17.3, and native Restate 1.7.9. No runtime application change was
needed. Resolved dependencies are recorded in `.local/runtime-resolved.txt`.

The reproducible live harness is `scripts/verify-runtime.py`. Run it with:

```bash
.local/runtime-venv/bin/python scripts/verify-runtime.py
```

It uses dedicated loopback ports 18080 (ingress), 19070 (admin), 19080
(runtime), and 15122 (fabric), with `.local/restate-verification-data` and
its generated config in `.local/evidence/restate-verification.toml`.
These isolate the experiments from the initial launcher smoke test on default
ports. The harness owns subprocess PIDs, sends SIGKILL to the process under
test, waits for termination, restarts the same executable/configuration, and
attaches to the original task without resubmission or re-registration.
The runtime uses Hypercorn's in-process `serve` API, as does `runtime/app.py`,
so the killed PID owns the actual listener rather than a worker supervisor.

Evidence is retained in `.local/evidence`: setup and service logs, deployment
metadata, listener addresses, task responses, crash PIDs, and before/after
`sys_invocation` / `sys_journal` queries through Restate's admin API. The query
client explicitly requests JSON; without `Accept: application/json`, it can
receive Arrow. A no-input status handler requires no body or Content-Type.
A second call to a used workflow key returns HTTP 409; attaching still returns
the original result.

| Acceptance criterion | Actually verified |
| --- | --- |
| Restate runs locally | PASS — native 1.7.9, deployment discovered |
| Repository-local persisted state | PASS — on-disk data retained across SIGKILL |
| Minimal TaskWorkflow discovery | PASS — Workflow run and Shared status handlers |
| Stable task identity | PASS — same IDs in state/results; duplicate run rejected with 409 |
| Objective accepted and operation executed | PASS — hello world, two words, expected SHA-256 |
| Status while running and after completion | PASS — durable-timer checkpoint and COMPLETED result |
| Runtime crash recovery | PASS — SIGKILL, new PID, original task completed without resubmission |
| Restate crash recovery | PASS — SIGKILL, same data, original deployment/task recovered |
| Execution inspection | PASS — admin SQL invocation/journal APIs, before and after |
| Project checks | PASS — four unit tests, compilation, shell syntax, TOML and whitespace |

All three journals retained the original six entries, including the named Run,
its successful completion, and Sleep command, with unchanged bytes and append
timestamps. Completed journals contain nine entries, adding timer completion,
completed state, and output. `journal-checks.json` records the comparisons.
This demonstrates recorded progress survived; it does not independently count
operation function executions or prove exactly-once external effects.

Both recovery tasks used 120-second durable timers. The harness recorded
SIGKILL exit status and new PIDs, then obtained the expected original result
through attach and status. Its owned listeners were absent after cleanup.
`summary.json` and `verification.log` contain the final passing outcomes.

Browser UI interaction was not exercised; actual execution was inspected via
Restate admin tooling APIs. Power/disk loss, replication, upgrades, cancel,
signals, ACP, and IntelliJ integration were not tested or claimed.

The initial default-port launcher processes outlived the execution tool's
interrupt and became inaccessible from subsequent sandbox PID namespaces.
They must not be confused with the PID-owned recovery instances. Their
listeners and retained data are recorded separately; shutdown remains a concern.
No unrelated Git state was changed; AGENTS.md remains absent and unstaged.
No commit, push, host package/configuration change, or Docker use occurred.

## Sources checked

- [Official SDK package and Python 3.14 wheels](https://pypi.org/project/restate-sdk/)
- [Python workflows and shared handlers](https://docs.restate.dev/develop/python/services)
- [Durable steps](https://docs.restate.dev/develop/python/durable-steps)
- [Timers](https://docs.restate.dev/develop/python/durable-timers)
- [Serving through Hypercorn](https://docs.restate.dev/develop/python/serving)
- [HTTP invocation and attaching to workflows](https://docs.restate.dev/services/invocation/http)
- [Native Restate installation](https://docs.restate.dev/installation)
- [Server 1.7.9 release](https://github.com/restatedev/restate/releases/tag/v1.7.9)
- [Server configuration](https://docs.restate.dev/server/configuration)
- [Listener configuration](https://docs.restate.dev/server/networking)
- [uv installation](https://docs.astral.sh/uv/getting-started/installation/)

These are references retained from the implementation session. Live conclusions
above are based on local execution evidence. ADR 0003 remains Proposed; this
spike does not evaluate the full ADR scope or the IntelliJ/ACP milestone.
