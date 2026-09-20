# Increment 11 — offline worker event-boundary diagnostic STOP

**2026-09-20 — STOP: version-matched exec event semantics remain unverified.**

This is an offline diagnostic, not another frontier execution. Starting branch
`feature/durable-cognitive-loop` was clean at `215a86c`. No other development
writer was found. No credential values were inspected and no provider/model call
was made. Milestone 033, its evidence and its unresolved reservation are unchanged.
Increment 11 remains STOPPED; Increment 12 remains unstarted.

## Retained facts and their limits

The public subsequence retained in `worker-observation.json` is:

1. `thread.started`: session `01a0bf7b-1f07-78e2-a308-4d09f50217ba`.
2. `item.completed`, `agent_message`: the expected projected-value JSON.
3. `turn.completed`: CLI-reported input 5,112, output 23, cached input 0.

A separate list contains `unrequested_item:error`. Source inspection establishes
that this label is produced by an `item.completed` whose item type is `error`.
Its position relative to the three retained events is UNKNOWN. So are its item ID,
body, category/code, terminality and relation to any provider or transport problem.
The filter never checked whether the original item even contained those fields.
Do not manufacture a fourth positioned event or a missing diagnostic message.

CLI exit was 0; timeout and cancellation were false; stderr length was zero.
There is no retained raw stdout stream to recover the missing information from.
The public values match the expected result, but that does not prove overall
worker success. Effective served model/account, internal model-call/retry counts
and final provider prompt remain UNKNOWN. This diagnostic does not reinterpret
those observability limits as new authority requirements.

## What the adapter actually does

| Input | Retention | Admission effect in the current adapter |
|---|---|---|
| `thread.started` | Last thread ID plus ordered public record | Requires a truthy session |
| `turn.completed` | Selected integer usage fields | Not required; not checked as a terminal success condition |
| `item.completed/agent_message` | Bounded text, without item ID or phase | Exactly one message required; later strict result JSON normalization |
| `item.completed/reasoning` | Omitted | Ignored; private reasoning is not retained |
| Other completed item, including `error` | Only `unrequested_item:<type>` in a separate list | Rejects |
| Top-level `error` or `turn.failed` | Kind and a fixed omission label | **Does not itself reject** |
| Other event, including started/updated content | Omitted | Ignored |
| Non-JSON line | `non_json_cli_output` label | Rejects |
| JSON with a non-object shape | May raise before observation persistence | No structured diagnostic guaranteed |

There is no warning/diagnostic/recoverable-error classification. Error item names
are not mapped to a proven upstream terminal state. Intermediate and final message
phases are not distinguished. Only the selected public events preserve order.

The exact rejection predicate in `live/binding.py` is nonzero exit, timeout,
cancellation, nonempty `unexpected`, message count other than one, or absent
session. For the historical run, **nonempty `unexpected` is the rejecting term**;
the other recorded checks pass. The exception occurs before `normalize()` and
before creation of `worker-normalized-result.json`.

Thus the rule is not simply “any error means terminal failure”: completed unknown
items reject, whereas top-level failure-shaped events do not reject by themselves.
Failing closed on the historical unclassified item was justified. Calling that
item a proven terminal worker failure would not be justified. Nor is this predicate
a sufficient general worker-success protocol.

## Local upstream evidence and STOP boundary

The installed package identifies Codex CLI 0.155.1 for Linux musl. Static help was
read in an empty, network-disabled Bubblewrap environment without credentials.
The installed executable contains `ThreadErrorEvent`, `TurnFailedEvent` and the
event names above. Those symbols corroborate distinct shapes; they do not define
their terminality, recovery semantics or legal coexistence with a final result.

No version-matched `exec --json` semantic source/schema documentation was found in
the bounded local package/cache inspection. An app-server schema is not evidence
that the different exec protocol has identical semantics. No online lookup,
provider execution, account inspection or broad reverse engineering was used.

Consequently final-result + error coexistence is **UNKNOWN**, not established as
either always legal or always terminal. There is no locally supported fixture for
“explicitly non-terminal error plus independent terminal success.” A synthetic
`terminal: false` field cannot create upstream semantics or authority.

This triggers the requested STOP before changing result acceptance. Neither a
non-terminal-error exception nor a new inferred terminal-success rule was added.

## Where information was lost

`CodexBinding.dispatch` held stdout in memory, then projected it into a narrow
public list. For the error item it appended only its type label to `unexpected`;
the entire item, event offset, ID and potential diagnostic fields were discarded.
For top-level errors it substituted a constant message. Other event kinds and
private reasoning were omitted; stderr retained only a byte count (zero here).

The observation serializer preserved exactly that already-reduced dictionary.
Result normalization and ExecutionEvent publication did not cause the initial loss.
The generic exception then crossed `frontier.invoke`, whose deliberate
exception-text suppression left `unknown_provider_outcome`. It did not import the
separate CLI observation's session/usage into the rejected result. Those observations
remain available separately and must not be invented in the accounting ledger.

## Reservation and Task failure

One dispatch slot was reserved before the effect. `invoke` marks the invocation
as provider-invoked/unknown before calling the adapter and leaves it unknown on
exception. `settle(..., 'unknown')` returns the unchanged budget. That is consistent
with the accepted contract: no reexecution, no refund claiming non-execution and
no settlement claiming verified success. One pending slot and one accounting
record are expected. No new lifecycle/settlement seam was found.

The live probe's scripted controller subsequently proposed COMPLETE without
redispatching. Missing result evidence kept verification unsatisfied; the existing
16-turn bound produced FAILED. These were scripted turns, not extra LLM calls.
The runtime did not equate a worker error item directly with Task terminality.

## Offline characterization and changes

Only diagnostic machinery, new evidence, this report and the progress index changed.
The live adapter, production kernel, contracts and historical evidence are unchanged.

Twelve characterization tests exercise eleven **synthetic** streams with mocked
process creation and a network-connect guard. They demonstrate:

- completed-shaped clean input is accepted by the current adapter;
- failure-shaped input without a result is rejected;
- valid text plus top-level `turn.failed` or `error` is currently accepted;
- a message without any terminal event is currently accepted;
- unknown completed error items remain rejected, even with an invented non-terminal flag;
- malformed JSON is rejected; a non-object event can lose the whole observation;
- placing an error before versus after the message yields identical retained event lists;
- private synthetic diagnostic text is not retained;
- nonzero exit rejects; the historical independent verifier still yields STOP/FAILED.

These are tests of **current behavior, including defects**, not acceptance tests
certifying safe worker completion. No fixture is counted as live inference or a
real upstream guarantee. Safe diagnostic text retention is not claimed solved.

Focused pre-change controls: 20 frontier tests and 3 worker tests passed. The
broader 107-test kernel suite and independent offline verifiers are also rerun;
their current results are retained alongside this diagnostic.

## Smallest next decision and proposed correction

Obtain version-matched upstream exec event definitions and their semantic comments
as an approved local source (or explicitly authorize a narrow official source
lookup). Establish terminal-success, terminal-failure and non-terminal diagnostic
semantics before changing acceptance. This is the next human decision.

Then, within the adapter only, a proposed correction should:

1. Validate bounded event shapes and preserve one sequence index across all events.
2. Retain only allowlisted structural kinds, IDs, bounded counts and documented
   error codes/categories; distinguish explicit upstream terminality from UNKNOWN.
3. Omit free-form error detail unless a safe retention policy permits it. Record
   omission/truncation reasons; arbitrary error strings may contain secrets or
   unprojected context. Do not dump stdout, stderr, headers or environment objects.
4. Record result presence, protocol terminal state, process outcome and precise
   normalization rejection reasons separately. A correct result is not terminal proof.
5. Require documented success conditions, reject documented failures, and retain
   unresolved cases as unknown. Never let a model-supplied flag establish terminality.

No second live probe is justified **yet**. After a reviewed adapter correction and
offline protocol fixtures, request fresh authorization for one new dispatch ID in
the same sterile projected synthetic context. Keep the historical receipt spent;
do not replay, repair or settle the original attempt. No fallback/escalation/retry.

## Evidence

- [Machine-readable diagnosis and synthetic cases](../../experiments/kernel-increment-11/evidence/offline-event-diagnostic/diagnosis.json)
- [Local package/protocol inspection](../../experiments/kernel-increment-11/evidence/offline-event-diagnostic/local-protocol.json)
- [Historical and unchanged implementation hashes](../../experiments/kernel-increment-11/evidence/offline-event-diagnostic/integrity.json)
- [Characterization tests](../../experiments/kernel-increment-11/evidence/offline-event-diagnostic/characterization-tests.txt)
- [Offline validation](../../experiments/kernel-increment-11/evidence/offline-event-diagnostic/validation.json)
- [Diagnostic source](../../experiments/kernel-increment-11/offline-event-diagnostic/diagnose.py)

**STOP. Historical Increment 11 is not closed. No production normalization change,
new live dispatch or Increment 12 work is authorized by this diagnostic.**
