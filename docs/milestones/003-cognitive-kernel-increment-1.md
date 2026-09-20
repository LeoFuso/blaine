# Increment 1 — Durable Cognitive Kernel

**2026-09-19 · Implemented and empirically validated · Stop before Increment 2**

Implements the [approved checkpoint](../research/cognitive-loop-checkpoint.md)
with the user's Increment 1 clarifications: scripted cognition, explicit same-Task
handoff, one typed wait, exact artifacts and external completion enforcement.
No architecture correction was required. The checkpoint's broader child/model
validation sequence is intentionally deferred by those clarifications. Existing
ADRs, older runtime fixtures and development infrastructure remain unchanged.

## Contracts and enforcement

[Contracts](../../runtime/kernel/contracts.py) use Python `TypedDict` plus explicit
boundary validators, following the repository's dictionary/`ValueError`
convention. Every wire message has `{version: 1, kind, payload}`. No modeling
dependency or YAML runtime format was added. Unknown fields/versions and invalid
shapes are rejected; JSON serialization rejects nonfinite numbers.

| Contract | Implemented minimum |
| --- | --- |
| TaskSpec | Objective, 1–8 completion criteria, required capabilities and explicit `autonomy.allowed` grants. Task identity comes from the Workflow key. Each criterion requires a named artifact with an accepted SHA-256 digest. Unsupported criteria are rejected at acceptance. Requirements alone grant no authority. |
| TaskState | Identity/revision, lifecycle, iteration, active specialist, accepted spec reference, committed decision identity/reference, context/current observation references, identifiable wait, admitted artifacts, completion/result references. |
| CognitiveTurn | Intent/criteria, identity/revision/iteration, specialist instructions, current observation, bounded sourced context, eligible capabilities and limits. No transcript or private reasoning. |
| CognitiveDecision | One typed NextAction and matching Task/revision/turn identity; optional short operational reason. Four executable variants; `SPAWN_TASK` is typed and explicitly denied as reserved for Increment 2. |
| CapabilityRequest/Result | Stable operation identity `Task/iteration`, bounded typed input; success/failure, output, artifact references and error. Fixture effects include an effect receipt. |
| CompletionContract/Evaluation | Accepted exact-byte requirements; independent verifier returns satisfied, unsatisfied or unknown per criterion. Missing evidence is unsatisfied; unreadable/corrupt evidence is unknown. Only a satisfied COMPLETE evaluation permits COMPLETED. |
| TaskResult | Task identity, authoritative outcome, bounded artifact and completion-evidence references, unresolved concerns. No history forwarding. |

The [PolicyGate and verifier](../../runtime/kernel/execution.py) enforce current
revision/turn, capability grants/input shape, two eligible specialists and
completion. Denial becomes a durable observation and does not call the capability.
The cognitive adapter receives data and returns a decision; it receives no
execution context, dispatcher or tool handle. These are trusted application
components, not a sandbox for arbitrary Python plugins.

Bounds are deliberately fixed for this increment: 16 turns, 16 named artifacts,
4 KiB artifact text, 16 KiB serialized context/decision envelope, at most three
attempts per durable step. Turn exhaustion/terminal execution failure produces
FAILED, never verified completion. Technical transport recovery remains Restate's
responsibility. There is no cloud budget scheduler or generic policy language.

## Native runtime and storage mapping

| Blaine concern | Implementation |
| --- | --- |
| One loop per Task | `CognitiveTaskV1` Workflow keyed by Task ID; one main handler owns transitions. [workflow.py](../../runtime/kernel/workflow.py) |
| Committed semantic choice | `ctx.run_typed("cognitive/N", ...)` journals the decision before admission/effects. Replay consumes the recorded output. Decision artifacts/state retain its identity. |
| Same-Task HANDOFF | Explicit owner transition plus newly reconstructed, persisted specialist packet. Next turn consumes that exact packet; accepted spec and identity stay fixed. No SDK agent-session sharing. |
| Capability execution | Policy admission followed by `run_typed`; stable operation identity. Three capabilities: `artifact.write`, `artifact.read`, `fixture.effect`. |
| WAIT/resume | State records wait ID, expected text input, revision and iteration-qualified promise name. Shared `submit_input` checks the bounded input against that wait and resolves its one-shot promise. Main resumes with the input as an observation. |
| State/status | Main uses `ctx.set`; shared `status` reads authoritative state. Uninitialized state is UNAVAILABLE. |
| Completion | Durable verifier output, exact evidence references and retained TaskResult. Workflow retention is seven days; indefinite archival is not claimed. |

[ArtifactStore](../../runtime/kernel/artifacts.py) stores immutable exact bytes
under a controlled filesystem root, publishes atomically and validates digests
on every read. References are `artifact://TASK/sha256:DIGEST`. Cross-Task/path
escape reads are rejected. Restate state contains small operational data and
references; its journal also necessarily retains bounded durable-step outputs.
The fixture's SQLite table is solely the external deterministic effect and its
idempotency receipt, **not** Task state, artifact storage or semantic memory.
Replay-safe filesystem writes and the atomic fixture receipt cover response-loss
retries; they do not establish exactly-once behavior for arbitrary future APIs.

## Empirical evidence

Pinned versions actually executed: **Restate server 1.7.9**, **Python SDK 1.0.5**,
Python 3.14.4. No dependency changes. The existing matching installation in the
sibling `blaine/.local` directory supplied executables; all experiment data belongs
to this checkout.

Portable evidence is in
[experiments/kernel-increment-1/evidence](../../experiments/kernel-increment-1/evidence/):

| Probe | Result and retained evidence |
| --- | --- |
| Repository unit suite | 23 passed, including 12 new kernel tests for contracts, policy, artifact integrity/isolation, effect idempotency and context authority/bounds. `unit-tests.txt` |
| 1: multi-turn | Write → read exact previous result → verified COMPLETE. `multi-*`, actual packets in `cognition.jsonl` |
| 2: premature completion | COMPLETE rejected as unsatisfied; missing criterion appears in next turn; write → successful verification. `premature-*` |
| 3: HANDOFF | Coordinator → specialist within one Task. Explicit decision/owner/context persistence; no prior transcript. `handoff-*`, `recovery-handoff-*` |
| 4: WAIT | Durable typed wait; stale revision rejected with HTTP 409; matching input observed in next turn. `wait-*`, `recovery-input.json` |
| 5: denial | Requested fixture effect excluded by policy; no dispatch/effect, durable denial observation, subsequent permitted write completes. `denial-*`, `capabilities.jsonl`, `effects.json` |
| 6: crash/recovery | Three runtime SIGKILLs and one server SIGKILL; all affected Tasks recover and complete. `process-events.json`, journal snapshots, `replay-checks.json` |

Seven sequential Tasks executed **23 cognitive turns**, each committed turn
called exactly once. Largest observed context packet: **1,562 bytes** (16 KiB
ceiling). All **90 retained artifacts** were reread and digest-verified.
[summary.json](../../experiments/kernel-increment-1/evidence/summary.json)
records assertions; actual packets, decisions, receipts, verifier findings,
status snapshots, submission IDs and exact artifact bytes are retained alongside
it. Journal snapshots preserve raw server entries, not just application messages.

Recovery cut points were:

1. After `recovery/3`'s HANDOFF decision committed, before ownership transition:
   kill runtime, restart, release the test barrier. No new routing decision.
2. After owner `specialist` and its context packet committed, before turn 4:
   kill runtime again. State references survive; the next specialist receives
   the exact committed packet. Earlier artifact contents are absent from it.
3. While that same Task awaits input: kill Restate, restart with the same data
   and deployment, submit matching input, reach verified completion.
4. After `response-loss/1`'s fixture effect commits, before its `run_typed` result
   reaches Restate: kill runtime, restart. Two execution attempts produce one
   effect row and the same receipt. Cognition still runs once.

The separately journaled `recovery/1` effect has one attempt and one row across
all restarts. The offline replay verifier compares invocation IDs, raw bytes and
append timestamps for every captured pre-crash journal entry against the final
journal. It verifies that the handoff decision was already recorded, that the
response-loss capability result was absent before the kill and present afterward,
and that the persisted handoff packet equals the actual next-turn input.

## Reproduction and limits

With the repository's pinned setup available:

```bash
.local/runtime-venv/bin/python -m unittest discover -s tests -v
.local/runtime-venv/bin/python scripts/verify-kernel.py \
  --restate-server .local/bin/restate-server \
  --output .local/kernel-probe/new-run
```

The probe requires free loopback ports 38080/39070/39080/35122, refuses an existing
output directory and owns/cleans up its processes. It never adopts running host
services. Its deployment-only barriers/audit instrumentation live in
[probe_app.py](../../experiments/kernel-increment-1/probe_app.py); ordinary kernel
handlers expose neither crash barriers nor model-selected scripts. `status` is a
bodyless POST; `run/send` and `submit_input` accept JSON. This controlled test
binding trusts its local caller's grants; it is not the Personal Agent or a
production authorization gateway.

Raw logs and persisted Restate data remain under `.local/kernel-probe/run-4`.
Earlier probe-client failures are retained under `run-1`–`run-3`: readiness used an
empty-body health response, a body was incorrectly sent to a no-input handler,
and the SQL endpoint needed `Accept: application/json`. These required test-client
corrections, not architectural changes. Sandbox socket restrictions also stalled
the first unit attempt; the suite passed with local socket access.

Validation covers process crashes on one host using unchanged code and retained
storage. It does not prove power-loss durability, production authentication,
upgrade compatibility, cancellation, arbitrary external effect deduplication or
indefinite retention. No such implementation was added.

## Preserved seams and exact next increment

- **MIRIX / Project Knowledge:** the bounded `ContextProvider` callable in
  [context.py](../../runtime/kernel/context.py) contributes sourced, revisioned,
  explicitly derived content/unknowns. It cannot replace Task state, grants or
  verification. Adding selective retrieval does not change the loop.
- **Child Tasks:** typed `SPAWN_TASK` and compressed `TaskResult` remain explicit.
  Add joined child acceptance/call/result handling at the existing dispatcher.
- **Personal Agent:** a future authorized binding submits TaskSpec and maps
  status/input/result operations; conversation never owns execution state.
- **YouTrack / Codex / Goose:** future bounded capability or cognitive adapters
  attach at dispatch/`CognitiveAdapter`, subject to policy and independent evidence.
  Worker identity remains separate from the same-Task specialist role.

**Next: Increment 2 — one sequential joined `SPAWN_TASK`.** Parent submits an
independent child TaskSpec/loop, durably awaits its bounded TaskResult and resumes.
No detached or parallel lifetime. Stop here before implementing it.

Development-work request record: implement only Increment 1 and retain all
required verification/recovery evidence, as authorized in this conversation.
No pre-existing binding was available to submit that development request; this
record is **not submitted**. The seven fixture Tasks above were actually submitted
to Restate, and their runtime identities/receipts are retained.
