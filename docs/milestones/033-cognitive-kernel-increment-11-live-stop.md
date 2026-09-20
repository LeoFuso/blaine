# Increment 11 — one live Codex dispatch, conservative adapter STOP

**2026-09-20 — STOP. Task `frontier-live-binding-001` ended FAILED.**

The user clarified two boundaries: one Blaine worker dispatch is distinct from
internal model calls/transport retries, and Blaine guarantees the exact projected
context delivered to the worker rather than an unobservable final provider prompt.
Internal retries/counts may be UNKNOWN; no second Blaine dispatch, replacement,
fallback, escalation or Task-level repetition of this frontier effect is allowed.
These decisions resolve the previous milestone 032 preflight restriction.

## Preflight and concrete binding

Preflight passed under the clarified semantics. Installed Codex CLI 0.155.1,
configured intent `gpt-6-astra`, built-in OpenAI provider and existing ChatGPT file
authentication were preserved. Prior redacted doctor evidence identifies the
OpenAI/ChatGPT service at `https://chatgpt.com`, with WebSocket transport possible.
The path below the service boundary, effective account and server-resolved model
remain UNKNOWN. No custom provider or retry override was introduced.

The worker ran in a Bubblewrap filesystem with an empty `/probe`, read-only system,
program and fixture mounts, no repository/user documents/personal instructions or
personal MCP configuration. Existing authentication was mounted read-only for the
CLI; Blaine never opened credential values. Shell tool, apps, memories and
multi-agent features were confirmed false. The CLI reports unified_exec true despite
the legacy false setting; this is recorded rather than hidden. No tools or filesystem
exploration were requested, and the worker sandbox remained read-only. Codex may
add bundled system instructions; this does not imply a captured final provider prompt.

One dispatch slot, read scope `projected-context`, empty write scope, scoped human
approval, exact binding/destination and projection digest were granted. The runtime
limit was **60,000 ms**. Blaine owns process-group termination and an out-of-band
cancellation marker; offline tests exercised termination with a local dummy process.
A fsynced exclusive adapter attempt receipt precedes process launch and is never
reset. An unknown response cannot relaunch the worker, including before journal
commit. Existing Restate reservation, journal and settlement code remain in use.
No destructive live recovery experiment was performed.

## Projection and live result

Raw synthetic values: `organization=ORCHID`, `marker=7319`.
Projector: `synthetic-live-v1`, producing ProjectedContext v1.
Exact UTF-8 stdin delivered to the Codex binding:

```json
{"marker":"MASKED_01","organization":"FLOWER"}
```

SHA-256:
`e4dfa3217256de41f4b4036aa046161b727f3db8b6efbfbde5da09ea4f17f183`.

The grant's artifact reference, AuthorizedFrontierRequest v3, recorded stdin and
independent byte/digest checks all agree. Raw values were absent from the worker
input and emitted ExecutionEvents/referenced payloads. The final provider/model
prompt is UNKNOWN; the offline prompt preview is not counted as live observability.

Exactly **one** worker dispatch ran. Worker session:
`01a0bf7b-1f07-78e2-a308-4d09f50217ba`.
Public worker response:

```json
{"organization":"FLOWER","marker":"MASKED_01"}
```

CLI exit code was 0; runtime was **3,623 ms**. The CLI reported **5,112 input tokens,
23 output tokens, 0 cached input tokens**. Model-call count, internal transport-retry
count, monetary cost, exact served account/model and final provider prompt remain
UNKNOWN. One worker execution is not reported as one model request.

## Why this is STOP rather than PASS

The same CLI stream also contained `item.completed` with item type `error`. The
experimental adapter classified it as an unexpected item and rejected the result.
It did not admit a normalized result artifact. The error item's body was not retained
by the capture filter, so the underlying cause cannot be isolated from this evidence.
We do not assume it was an unauthorized tool, harmless warning or model failure.
This capture limitation is explicitly unresolved.

The existing CompletionVerifier therefore reported **unsatisfied: required artifact
missing**, and the Task ended **FAILED**. An offline check confirms the public values
match, but that check neither repairs the rejected worker outcome nor changes Task
state. The frontier ledger retains an unknown outcome and one pending dispatch slot;
no successfully completed effect or settled dispatch is claimed. CLI usage/session
observations remain available separately even though the frontier result was rejected.

No second live call, normalization repair, validation weakening or architecture
change was attempted. No Blaine retry/replacement/fallback/escalation occurred.

## Evidence

- [Summary](../../experiments/kernel-increment-11/evidence/live-authorized/summary.json)
- [Revised preflight](../../experiments/kernel-increment-11/evidence/live-authorized/preflight.json)
- [Isolation checks](../../experiments/kernel-increment-11/evidence/live-authorized/isolation-preflight.json)
- [Accepted authority before dispatch](../../experiments/kernel-increment-11/evidence/live-authorized/acceptance/pre-dispatch.json)
- [Worker-bound exact bytes](../../experiments/kernel-increment-11/evidence/live-authorized/acceptance/worker-input.txt)
- [Public CLI observations](../../experiments/kernel-increment-11/evidence/live-authorized/acceptance/worker-observation.json)
- [Independent runtime/evidence verification](../../experiments/kernel-increment-11/evidence/live-authorized/acceptance/verification.json)
- [Public-value check only](../../experiments/kernel-increment-11/evidence/live-authorized/public-value-check.json)
- [74 ExecutionEvents](../../experiments/kernel-increment-11/evidence/live-authorized/acceptance/events.jsonl)
- [Server journal](../../experiments/kernel-increment-11/evidence/live-authorized/acceptance/journal.json)
- [107 focused tests](../../experiments/kernel-increment-11/evidence/live-authorized/focused-tests.txt)
- [Unchanged production hashes](../../experiments/kernel-increment-11/evidence/live-authorized/integrity.json)

Events reconstruct projection, admission, reservation, capability failure, attempted
settlement and unsatisfied completion. Detailed CLI observations are retained in the
separate worker artifact file; no synthetic successful Task history was manufactured.
The unknown dispatch has one settlement evaluation, **zero settled dispatches** and
one accounting record. All probe runtime/server processes were stopped.

The new code is experiment-only `live/binding.py`, `live/probe.py`, `live/verify.py`
and fixture configuration, plus four offline control tests. Production lifecycle,
PolicyGate, CompletionVerifier, authority, projection, routing and accounting source
hashes match the accepted isolated proof. No new library, host configuration or
credential mutation was introduced. Earlier isolated gates remain passed; the live
gate is not passed and Increment 11 is **not ready to close**.

## Human decision and safest next option

Approve a narrow offline review of the adapter's Codex JSON-event handling and a
secret-safe capture correction for error items. Do not weaken rejection based only
on the correct public answer: the omitted error body is unresolved. Captured events
may support synthetic parser tests, but cannot establish the missing live error's
meaning. Any new live dispatch requires fresh explicit authorization. Do not replay
this live attempt or delete its spent receipt. **Increment 12 remains unstarted.**
