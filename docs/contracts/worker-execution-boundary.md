# Worker execution boundary and instrumentation v1

Constrained by [ADR 0016](../decisions/0016-agent-harnesses-are-replaceable-execution-capabilities.md)
and [ADR 0018](../decisions/0018-local-platform-durability-and-observability.md).
The executable definitions are [`runtime/kernel/instrument.py`](../../runtime/kernel/instrument.py),
the declared profiles [`runtime/kernel/adapter_profiles.py`](../../runtime/kernel/adapter_profiles.py)
and the optional exporter [`runtime/kernel/telemetry_otel.py`](../../runtime/kernel/telemetry_otel.py).
Live evidence lives in the [instrumentation experiment](../../experiments/worker-execution-instrumentation/README.md).

This contract adds an observation and control seam. It does not change Task
lifecycle ownership, authority semantics, initial routing or Completion Contract
semantics, and it introduces no message broker and no vendor tracing dependency.

## The boundary

A **continuation boundary** is the point at which prior model and tool activity
has been incorporated and another model continuation has not yet begun.

```text
model invocation -> model result -> zero or more tool calls -> tool results
    -> CONTINUATION BOUNDARY -> next model invocation
```

It is deliberately **not** a token boundary, not necessarily a user turn, not
necessarily a provider-defined turn, not necessarily a durable Restate step, and
not automatically a supervisor invocation.

`ContinuationBoundary` was chosen over `SamplingBoundary` and `WorkerStep`.
"Sampling" already means token-level decoding configuration on the local serving
path, and "step" imports a foreign harness vocabulary that Blaine does not use.
"Continuation" describes what the boundary precedes, and it maps onto both the
Blaine-owned loop and the observed external harness protocol without renaming
either one's internal concepts.

## Normalized execution identity

`ExecutionIdentity` reuses identifiers Blaine already owns. A level that a Worker
does not expose stays absent; no identity is synthesized to fill a gap.

| Level | Source | Notes |
| --- | --- | --- |
| `task_id` | Restate workflow key | Logical Task identity. |
| `run_id` | `run:` + Restate invocation id | Physical run; not a trace id. |
| `worker_dispatch_id` | `dispatch:` + decision id | Existing frontier dispatch identity. |
| `worker_session_id` | Adapter result (`attempt_id`, harness thread id) | A worker session is not a Task. |
| `agent_turn_id` | Harness turn id when one exists | Absent for one-shot adapters. |
| `model_invocation_id` | `<task_id>/<iteration>` for the owned loop | Reuses the existing decision/turn identity. |
| `capability_call_id` | Existing decision id | Already the capability operation id. |

Continuation position is a `blaine.continuation.index` on the identity's spans and
events rather than a new identifier, so nothing has to be minted or persisted.

## Capability model

An adapter declares `CapabilityClaim(capability, support, granularity, evidence)`.
Support is `OBSERVED`, `INFERRED` or `UNSUPPORTED`; granularity is `continuation`,
`agent_turn` or `worker_dispatch`; evidence is `live`, `fixture`, `protocol`,
`source` or `none`. `AdapterProfile.supports(capability, granularity)` is true only
for a declared, non-`UNSUPPORTED` claim at least that fine, so a turn-granularity
control never satisfies a continuation-granularity request. `require()` raises
`UnsupportedCapability` rather than letting calling code emulate missing behavior.

The capabilities are `continuation.observe`, `continuation.admit`,
`continuation.steer`, `execution.interrupt`, `model.observe`, `tool.observe`,
`model.rebind` and `effort.rebind`.

`INFERRED` never reads as `OBSERVED`, and an `UNSUPPORTED` claim carries no
granularity. A profile's summary lists undeclared capabilities explicitly instead
of implying them.

## Two paths with different semantics

```text
control path      synchronous when required; may affect execution
telemetry path    asynchronous where possible; must not normally affect execution
```

### Control path

`ControlPath.admit(boundary)` runs registered observers synchronously before the
next continuation. Each observer returns a closed assessment: an outcome of
`PROCEED` or `ABSTAIN`, with optional bounded label, probability score, latency
and token counters. Unknown fields, out-of-range scores and free provider payloads
are rejected. This increment admits **no intervention**: `admitted_intervention`
is always null. An outcome that changes execution semantics would additionally
require a declared capability and a durable admission record, which is future work.

An observer is a replaceable participant, never authority. It cannot authorize a
Worker action, complete a Task or widen a grant. Only its outcome becomes a span
attribute; label, detail and score stay in the Task-scoped admission record, so a
supervisor's free text cannot reach the telemetry backend through this seam. A no-op observer is sufficient;
the property that matters is that a future supervisor can participate synchronously.

Failure policy is explicit and tested:

| Condition | `PROCEED_ON_ERROR` (default) | `FAIL_ON_ERROR` |
| --- | --- | --- |
| Observer raises | Recorded failure, execution proceeds | `ControlPathError`; the Task fails |
| Observer exceeds `budget_ms` | Recorded, observer poisoned for the run | `ControlPathError` |
| Poisoned observer at a later boundary | Recorded as `skipped_poisoned` | `ControlPathError` |

A control-path failure is always reported in the admission record and emitted as
`blaine.control.failed`, under either policy. It is never silently discarded.
Under `FAIL_ON_ERROR` the admission step raises, so the durable runtime applies its
standard step retries and then fails the Task; the failure is an execution decision
rather than lost telemetry.
The budget is enforced on a single worker thread; an observer that exceeds it is
abandoned and not consulted again, because a hung synchronous participant must not
hold the boundary open indefinitely.

### Telemetry path

The `Recorder` protocol is the only emission seam: `span`, `event` and `count`.
No vendor type crosses it. `NullRecorder` is the default and performs no work, so
an uninstrumented deployment is unchanged. `SafeRecorder` wraps any recorder so a
telemetry failure becomes a dropped count instead of a Worker failure, while an
exception raised by the instrumented body still propagates normally.

Spans cover operations with duration: `worker_session`, `agent_turn`,
`model_invocation`, `tool_execution`, `verifier`, `boundary_control`. Events cover
point-in-time occurrences, currently `blaine.continuation.boundary` and
`blaine.control.failed`.

Spans are opened **inside** the journaled step that performs the physical work.
A replay that consumes the journal therefore emits no span and never fabricates
inference or a tool execution that did not happen on that attempt. Because a
durable Task suspends and resumes, Blaine does not open one physical span across
its whole lifetime: correlation is by `blaine.*` identity attributes, preserving
the existing separation of logical Task causality from physical tracing causality.

One consequence is observable and intended: a durable at-least-once retry can
produce two `tool_execution` spans for one `capability_call_id`, while the
journaled ExecutionEvent ledger still records exactly one logical
`capability.finished` for it. Spans describe physical attempts; ExecutionEvents
describe committed semantic observations.

## OpenTelemetry modeling

Attribute names follow the OpenTelemetry GenAI semantic conventions —
`gen_ai.operation.name`, `gen_ai.provider.name`, `gen_ai.request.model`,
`gen_ai.response.model`, `gen_ai.response.id`, `gen_ai.response.finish_reasons`,
`gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`,
`gen_ai.usage.cache_read.input_tokens`, `gen_ai.usage.cache_creation.input_tokens`,
`gen_ai.tool.name`, `gen_ai.tool.call.id`, `gen_ai.agent.id` — and span names use
the convention's `<operation> <target>` form. They are plain strings in the kernel,
which imports no OpenTelemetry package. Reasoning effort has no stable GenAI
attribute, so it stays `blaine.model.reasoning_effort` rather than pretending to
be standardized. No standardized provider value exists for a self-hosted
OpenAI-compatible server, so the local serving deployment is named `local.vllm`.

**Content capture is off by default.** Prompts, completions, tool arguments and
tool results may contain secrets, credentials, repository contents or large
payloads. Only metadata remains observable by default: identities, model and
provider, token counts, finish reason, tool name and status, exit codes, durations,
an output digest and an evidence digest. Capture is enabled only by explicit
deployment configuration.

`blaine.continuation.evidence_digest` is a stable fingerprint of the admitted
artifact set, so progress between boundaries is observable without content.

## Durability rules

Telemetry is not durable Task state. Model request start/completion, tool
start/completion, boundary observation, token accounting and latency remain
telemetry-only and are never written into Restate state.

An **admitted control decision is durable**. `Instrumentation.admit` executes in a
journaled step, so recovery replays the historical admission instead of consulting
an observer again for a boundary that was already decided. Live evidence: after
SIGKILL following a journaled boundary admission, the replacement process
recomputed zero historical boundaries. The journal gains a `continuation/<n>` entry
only when instrumentation is enabled; the default deployment's journal, spans and
behavior are unchanged, and no model invocation is turned into a workflow step to
obtain durability.

Events that change future execution semantics — an execution binding change, an
interrupt or cancellation, an admitted intervention, a requested human decision —
belong to durable state or the existing ExecutionEvent ledger, not to the
telemetry path. This increment admits none of them at a boundary.

## Failure and backpressure behavior

| Condition | Defined behavior |
| --- | --- |
| Exporter or Collector unavailable | Batched export fails in the background; execution continues; spans are lost |
| Recorder raises | `SafeRecorder` increments `blaine.telemetry.dropped`; execution continues |
| Local buffer full | The SDK's batch processor drops spans and the dropped counter is exposed |
| Malformed or unknown provider event | Counted by the adapter; never copied and never promoted to a capability |
| Partial provider metadata | Absent counters stay absent rather than being estimated or zero-filled |
| Shutdown with buffered telemetry | Bounded flush on a daemon thread; it reports whether the buffer drained, and undelivered spans are lost |
| Process killed mid-run | Buffered spans are lost; the journaled ledger and the Task outcome are unaffected |

Observability is never a correctness dependency: an unavailable backend cannot fail
an otherwise valid Task. A control-path event that would change execution semantics
is never dropped — there is no such event in this increment, and adding one
requires the durable admission path above.

## Why no message broker

The control path must affect the immediately following continuation, so it is a
synchronous in-process call; a queue would make it unable to do its only job. The
telemetry path already has a standard asynchronous carrier in the OpenTelemetry
batch processor and OTLP, whose destination is deployment configuration. Kafka,
NATS, Redis Streams, RabbitMQ or a new generic event bus would add an operational
dependency, a second delivery semantics to reason about and a failure mode that
could reach Task correctness, in exchange for nothing either path needs. The
SDK's internal batching queue is an implementation detail of the exporter, not a
Blaine architectural primitive.

## Backend independence

Blaine emits OTLP. The Worker abstraction has no Grafana, Tempo, Loki, Prometheus,
Langfuse or Phoenix dependency, and none of those names appears in the kernel.

```text
Blaine -> OpenTelemetry / OTLP -> Collector -> external destinations
```

The exporter module is optional: when the OpenTelemetry SDK is absent it returns
`NullRecorder`, so a deployment without it keeps exactly today's behavior. Nothing
requires Langfuse, and no dashboard is part of this contract.

## Derivable measurements

The emitted metadata is sufficient to derive Task and worker-session duration,
model invocations per Task or session, tool call counts, tool latency and failure
rate, model and provider per invocation, reasoning effort where exposed, input,
output and cached token usage where exposed, retries, steering and interruption
occurrences, completion attempts and rejections, artifact changes, continuations
between meaningful evidence changes, and future supervisor invocation count,
latency and outcome. Deriving a semantic conclusion such as "equivalent repeated
tool calls" is left to a later analytics or supervisor layer, which has the
correlated evidence it needs; the telemetry layer does not infer it.
