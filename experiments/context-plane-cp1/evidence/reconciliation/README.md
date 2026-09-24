# CP.1 / E1.0 final qualification

**READY_FOR_PIPELINE — 2026-09-24.** Tested production merge:
`e9e9196f344104897208088953442d7d23651631`, merging
`f0a3ca50ef7a392cd9e1f64251b407f66950b721` into CP.1
`b0f782ae2b9199e74f3f17151009219d47de4c8e` with both parents preserved.
The subsequent handoff commit changes only documentation/evidence. No push, PR,
merge into main, deployment enablement or CP.2 work occurred.

[qualification.json](qualification.json) owns commands, source hashes, per-file test
counts, failure classifications and retention details. [ci-matrix.json](ci-matrix.json)
owns the reinspection of all three actual GitHub workflows and their invoked scripts.
No changed branch/PR path matches an automatic workflow. The shared client build and
alpha release are not CP.1 gates; full client builds were not run. GitHub upload and
release actions need runner identity/permissions if those workflows are invoked.

| Final check | Result | Evidence |
| --- | --- | --- |
| Accepted full root discovery | 333 tests PASS, zero skips | [All test names/results](regressions.txt) |
| CP.1 within root discovery | 22 tests PASS | `test_kernel_context_plane` in the root log |
| E1.0 within root discovery | 39 contract + 19 workflow + 3 regression-coverage tests PASS | Root log |
| Exact `client/ci.sh` host/readiness command | 6 tests PASS; duplicates of root coverage | [Log](ci-host-tests.txt) |
| Native CP.1 Restate + Goose | 1 Task, 2 physical dispatches, 1 delta, 15 checks PASS | [Summary](native/summary.json), [worker packets/results](native/workers.jsonl), [current contract](native/contract.json), [evaluation](native/verification.json) |
| Native E1.0 acceptance | 9 Tasks; 8 runtime + 2 server SIGKILLs; no duplicate effects; PASS | [Rerun summary](e1-native-summary.json) |
| Native parallel children | 12 Tasks; 3 runtime + 3 server SIGKILLs; PASS | [Rerun summary](parallel-native-summary.json) |
| Working and branch whitespace | PASS | Qualification command record |

Counts are not additive: CP.1, E1.0 and host/readiness are subsets of the 333 root
tests. The three final native gates exercised 22 Tasks in total; expected FAILED
negative fixtures are required successes of their acceptance checks. Earlier runs
are not counted again. The root suite covers kernel, PolicyGate, evidence, frontier,
child/human, D2/ACP, remote reads and worker compatibility. Historical Increment
1/2/5 entrypoints remain non-gating per the integrated E1.0 regression classification;
their replacement property coverage and native gates were executed.

## Reproduction

From repository root, use an existing environment with `runtime/requirements.txt`.
Set `PYTHON` to its interpreter, `RESTATE_SERVER` to the existing pinned server,
`GOOSE` to the existing local worker, and `SCRATCH` to a fresh writable directory.
Validated versions: Python 3.14.4, Restate 1.7.9, SDK 1.0.5, Goose 1.50.1.
The already-serving model is `nvidia/Qwen3.8-27B-NVFP4` on loopback port 8000.
Do not start a model or call cloud cognition. Native fixtures clean up their own
processes; their output directories must not already exist.

```sh
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" scripts/verify-context-plane-tests.py --output "$SCRATCH/regressions"
python3 -m unittest tests.test_host_connection tests.test_direct_readiness -v
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" scripts/verify-context-plane-cp1.py --output "$SCRATCH/native" --restate-server "$RESTATE_SERVER" --goose "$GOOSE" --model nvidia/Qwen3.8-27B-NVFP4
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" experiments/personal-agent-hub/e1-0/accept.py --output "$SCRATCH/e1" --evidence "$SCRATCH/e1-evidence" --restate-server "$RESTATE_SERVER"
PYTHONDONTWRITEBYTECODE=1 "$PYTHON" scripts/verify-kernel-parallel.py --output "$SCRATCH/parallel" --restate-server "$RESTATE_SERVER"
git diff --check
git diff origin/main...HEAD --check
```

The regression script executes the accepted broad suite:
`python -W ignore::ResourceWarning -m unittest discover -s tests -p 'test_*.py' -v`.
Its full discovery includes E1.0 and supplies the repository's expected test import
path. An optional package-qualified invocation failed imports; no import or test
assertion was weakened to accommodate it. Use discovery as shown.

## Reconciliation and limits

The Compiler projects exact current contract criteria plus the runtime's immutable
reference/revision. The worker admission rejects an older revision; it grants no
scope. `context.request` is a governed TARGET_READ, admitted and observed in E1.0's
journal. Caller class/authority fields remain invalid. The new integration test
uses E1.0's actual amendment handler and ordered peek/replay fixture: initial worker
revision 0, authorized rebind, stale delivery refusal, fresh delta revision 1, and
completion against revision 1. It also exposed and now prevents a pre-amendment
handoff packet from reaching the next cognition.

The native CP.1 smoke keeps contract revision 0 and changes exact source DRAFT→GOOD;
it verifies current contract projection and v2 completion legality, not native
mid-execution amendment. Its packets measure 2,428 and 2,411 bytes; delta 2,577 bytes,
all below the unchanged 4,096-byte bounds. Each packet considers four source/Memory
candidates, selects three, reports `partial:true` and `truncated:false`. Exact criteria
and source survive; optional Memory is bounded. Amendment/replay is deterministic
integration evidence, and native E1.0 separately exercises the accepted amendment
mechanism. No general CP.1 crash/concurrent revocation guarantee is claimed.

Resolved failures remain visible under [failures](failures/): the exhaustive operation
class assertion needed the new TARGET_READ, the added handoff/amendment test exposed
stale reconstruction, and an optional focused command used the wrong test import
path. The final full suite and all native gates passed after the production fix.
The passing root log retains non-gating telemetry exporter timeout diagnostics.

Portable public CP.1 packets, current contract and evaluation are retained verbatim;
only the Goose executable's machine path is normalized in its audit log. The root
test log normalizes the checkout path; one failure log also strips trailing whitespace.
Raw and retained hashes identify these changes.
E1.0/parallel reruns retain compact result summaries rather than another copy of their
large historical artifact archives. Temporary server databases, binding snapshots,
process IDs, ports and scratch configuration are not committed. Earlier CP.1 and E1.0
acceptance evidence is unchanged.

Next: human review/push/PR for CP.1. Merge CP.1 into main before a separately authorized
CP.2 worktree. **CP.2 — Governed declared/observed writes is NOT STARTED.** No learning,
reflection, promotion, declassification, semantic retrieval, Graphify or distributed
context transport is included.
