# Worker execution instrumentation and continuation boundary

**2026-09-22 — PASS within the evidence below, with one honest negative result.**
User-directed increment, not a roadmap-scheduled item. It adds an observation and
control seam; it does not change Task lifecycle ownership, authority semantics,
initial routing or Completion Contract semantics, and it claims no workstream status.

Normative definitions live in the [worker execution boundary contract](../contracts/worker-execution-boundary.md);
live evidence lives in the [instrumentation experiment](../../experiments/worker-execution-instrumentation/README.md).

## What was asked and what came back

The question was whether Blaine can expose the finest safe model-continuation
boundary each Worker Adapter genuinely provides, observe it densely and cheaply,
and hold it synchronously where the adapter really supports that.

For the Blaine-owned durable loop the answer is yes on all three counts. For the
Codex app-server the answer is yes for observation, steering and interruption, and
**no** for synchronous continuation admission. That negative result is recorded as
an `UNSUPPORTED` capability rather than emulated by a fabricated boundary.

## Evidence

Zero paid cloud inference calls and zero frontier dispatch grants were consumed.
Both live probes drove real harnesses against the adopted loopback Qwen
deployment, so the Codex agent loop ran without a provider-account call.

| Claim | Observation |
| --- | --- |
| Boundaries are observable in the owned loop | Two continuation boundaries per live Task, journaled as `continuation/1` and `continuation/2` |
| A synchronous observer precedes each continuation | Deterministic observer consulted before every cognition call, in `boundary_control` spans at continuation index 0 and 1 |
| An admitted decision survives process death | After SIGKILL following a journaled admission, zero historical boundaries were recomputed and only one process id ever consulted the observer |
| Telemetry reaches a real Collector | 26 spans delivered by OTLP to the native Alloy receiver, with real token usage and `finish_reasons` |
| Telemetry is not a correctness dependency | An unroutable Collector added no execution latency and failed no Task; a raising recorder only incremented a dropped counter |
| Codex boundaries are observable | `thread/tokenUsage/updated` fires exactly once per model invocation with that invocation's own token breakdown |
| Codex steering is consumed at the boundary | `turn/steer` accepted in 0.4 ms mid-tool, consumed 0.4 ms after the next boundary marker |
| Codex interruption is real and lossy | `turn/interrupt` ended the turn as `interrupted`; the in-flight tool item received no terminal event |
| Codex has a blocking callback, in the wrong place | A 3000 ms client delay held tool approval with `activeFlags: ["waitingOnApproval"]`; that point is before a tool runs, not before the next model continuation |
| Codex rebinding is coarser than a continuation | `model` and `effort` are accepted by `turn/start` only, so both are `agent_turn` granularity |

187 offline tests pass, 41 of them new, and they start no harness and perform no
inference. They cover unchanged behavior when instrumentation is disabled,
correlation of model and tool spans, causal boundary ordering, exporter-failure
isolation, non-blocking export, synchronous observer execution, the explicit
control-failure policy, capability honesty, and the structural guarantee that an
observer's credentials and free-text fields never reach telemetry. The 41 platform
tests also pass unchanged.

## Two findings retained because they are true

**Buffered telemetry is lost on SIGKILL.** The killed process's spans never
reached the Collector while its journaled ExecutionEvents and the Task outcome were
unaffected. This is the intended asymmetry, not a defect to hide.

**A durable at-least-once retry duplicates a physical span.** Two `tool_execution`
spans exist for one `capability_call_id`. The content-addressed artifact write is
idempotent, the Task completed with correct exact artifacts, and the journaled
ledger still recorded one logical `capability.finished`. Spans describe physical
attempts; ExecutionEvents describe committed semantic observations.

One live Task is retained as **FAILED**: the local model returned non-JSON at the
second continuation and the pre-existing validator rejected it three times. That
is existing local-model behavior rather than an instrumentation regression, and it
demonstrates retry visibility — three model invocation spans at one continuation.

## What was deliberately not built

No message broker and no generic event bus. No supervisor, escalation policy,
dynamic model switching or effort switching. No intervention outcome: a control
observer can only `PROCEED` or `ABSTAIN`, and `admitted_intervention` is always
null. No Codex worker binding was registered and no adopted service was changed.
No dashboard was built. No vendor tracing dependency entered the Worker
abstraction: the kernel imports no OpenTelemetry package, and an absent SDK
degrades to the inert default recorder.

The optional Jev validation was **not performed** and is not part of this
acceptance. It was never a success criterion, and the boundary is fully useful
without it: the demonstrated observer is deterministic and the seam accepts any
replaceable participant.

One naming discrepancy is recorded for whoever attempts that validation later.
The inspected integration path expects the environment variable `TYPESAFE_API_KEY`,
while the existing secret is currently stored under the name `JEV_API_KEY`. Neither
variable was readable from this increment's execution environment, and no secret
was read, renamed, moved or emitted here. Reconciling the two names is a separate
operational decision, not part of this merge.

## Limits

Capability claims apply to Codex CLI 0.155.1 and the protocol observed here; they
must be revalidated on upgrade. The Codex adapter is an observation adapter in the
experiment, not a registered Blaine worker binding. The Goose seam's row is source
evidence: a single-turn dispatch with tools disabled has no internal continuation
to observe, and that is recorded rather than emulated. Local-model decision
quality is unchanged and remains variable. Selective semantic supervision,
steering policy, model switching and effort switching are explicitly out of scope.
