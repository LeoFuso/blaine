# Milestone 001 — executed commands and evidence

Current evaluation: 2026-09-14, Bash, repository
`/home/leofuso/workspace/blaine-runtime-spike`.
This supersedes the earlier implementation session's network-blocked results.
Only the six requested public architecture/milestone documents were read;
BLAINE.md and policy documents were not consulted in this evaluation.

## Setup and initial smoke test

Executed:

```bash
mkdir -p .local/evidence
bash scripts/setup-runtime.sh > .local/evidence/setup.log 2>&1
bash scripts/run-restate.sh > .local/evidence/restate.log 2>&1
bash scripts/run-runtime.sh > .local/evidence/runtime.log 2>&1
curl --fail-with-body -s http://127.0.0.1:9070/deployments \
  --json '{"uri":"http://127.0.0.1:9080"}' > .local/evidence/deployment.json
curl -s --fail-with-body http://127.0.0.1:9070/query \
  --json '{"query":"select * from sys_invocation limit 1"}' \
  > .local/evidence/query-probe.json
```

Setup and discovery passed. Downloads, venv, uv cache, and Restate data are all
repository-local. The default-port services were started in separate execution
tool sessions. Tool interrupts ended those sessions but left their listeners
alive; subsequent sandbox commands cannot see their PIDs. The recovery harness
therefore uses a separate repository-local data directory and loopback ports.

## Live experiments

Executed the harness, with early failures retained in the appended log:

```bash
.local/runtime-venv/bin/python scripts/verify-runtime.py \
  >> .local/evidence/verification.log 2>&1
```

The exact HTTP calls, assertions, process lifecycle, and SQL are in that script.
It runs the happy path (5-second timer), runtime SIGKILL (120-second timer),
and Restate SIGKILL (120-second timer), in sequence. Each recovery retains the
same task/invocation, binaries, configuration, deployment, and data directory.
Only the happy-path duplicate-identity check attempts a second run, and that
request must return HTTP 409. Recovery tasks are submitted exactly once.
The harness stops all processes it owns in `finally`, retaining their data.

Diagnostics resolved while building the harness:

- Listener preflight uses SO_REUSEADDR to avoid treating TIME_WAIT as a listener.
- Shared status requests have no body and no Content-Type, matching discovery.
- Admin SQL requests explicitly accept JSON rather than binary Arrow.
- Duplicate workflow invocation returns 409, rather than automatically attaching.
- In-process Hypercorn serving makes the runtime PID the actual process under test.

Before/after JSON files retain status, result, invocation details, full journal
entries, and SIGKILL/restart PID records. `summary.json` is written only after
all three experiments succeed. Earlier tracebacks in `verification.log` are
harness diagnostics, not passing acceptance evidence.

## Project checks

Executed:

```bash
.local/runtime-venv/bin/python -m unittest discover -s tests -v \
  > .local/evidence/tests.log 2>&1
.local/runtime-venv/bin/python -m compileall -q runtime tests scripts/verify-runtime.py
bash -n scripts/setup-runtime.sh scripts/run-restate.sh scripts/run-runtime.sh
git diff --check
git status --short
```

Four unit tests passed; compilation, shell syntax and whitespace checks passed.
Additional persisted-journal comparisons and final listener/data inspection are
recorded under `.local/evidence`. Git's existing AGENTS.md deletion and unrelated
state were preserved. Nothing was staged, committed, or pushed.
