# ExecutionEvent v1

Constrained by [ADR 0018](../decisions/0018-local-platform-durability-and-observability.md).
The executable typed definition and closed validator are
[`runtime/kernel/events.py`](../../runtime/kernel/events.py). No new dependency is required.

`schema_version: 1` records include event identity/type, timezone-aware occurrence
and recording timestamps, Task/run identity, producer, references, outcome,
classification, bounded metadata and payload references. Step, attempt, parent,
causation and physical trace/span identities are optional when applicable.
Unknown fields, unsupported versions, arbitrary inline payloads, invalid
correlation and SECRET classifications/references are rejected. This is a closed
metadata surface, not a general secret detector or a redaction framework.

The current runtime publishes seven event classes: `task.started`,
`cognition.decided`, `policy.evaluated`, `capability.finished`, `artifact.produced`,
`verifier.evaluated`, `completion.finished`. Cognition events mean a committed
proposal, not admission; the subsequent policy event records authorization.
Successful effects do not imply completion. Only the existing verifier controls it.
A Completion Contract amendment additionally emits `contract.amended` (`applied` or
`rejected`) with the amendment and revision refs; like every event it is forensic,
never contract or lifecycle authority.

`ExecutionEventPublisher.publish(event)` is the backend-independent boundary.
The deployment opts in through `create_workflow(event_publisher=...)`; the default
remains no publisher. Publishers must perform bounded I/O and deduplicate stable
`event_id`. Neither the runtime nor the verifier reads the event sink.

The runtime retains event construction in a Restate step before publishing it in
a separate step. Identical replay therefore retains timestamps and content.
A stable event ID derives from the run and logical step. The local JSONL publisher
locks its file and deduplicates exact records, including a crash after append but
before Restate acknowledges publication. Conflicting reuse is rejected. A damaged
or unavailable sink loses telemetry, not Task authority. Publication exceptions
are reduced to a non-authoritative journal status without capturing exception text.
There is no guarantee of telemetry delivery during sink failure.

A run is scoped to the existing Restate invocation; it is not a trace.
Causation links connect successive recorded semantic observations within that run.
No trace/span or retry attempt is fabricated. The envelope can carry real
correlation when instrumentation provides it. The separate
[worker execution boundary](worker-execution-boundary.md) seam now emits
OpenTelemetry spans for physical execution attempts; those spans and these events
are deliberately different records. A span describes one physical attempt and may
repeat under a durable retry or replay; an ExecutionEvent describes one committed
semantic observation, deduplicated by its stable `event_id`. Neither reads the
other, and populating this envelope's trace/span fields from that seam remains
future work rather than an implemented guarantee. Producer provenance identifies
the recording application component; it does not pretend deterministic/scripted
decisions are model inference.
Worker attempt references are carried when the existing capability result supplies them.

Payload references reuse exact artifacts already persisted by the kernel.
They are classified SENSITIVE by default; inline metadata never includes Task
objectives, raw prompts, capability inputs, human answers, environment/config maps,
or exception messages. Deployment and caller identity fields must also be safe
metadata. No sensitive-data export is introduced.

The JSONL publisher is only an acceptance/local forensic sink. It is not the
selected long-term telemetry backend or a durable knowledge store. It intentionally
has no rotation, retention, analytics or ingestion infrastructure. Existing
filesystem artifacts exercise the future object-store boundary; this increment
neither deploys S3 nor changes the PostgreSQL + Object Storage durability target.
Grafana, Alloy, Langfuse, ClickHouse and OpenTelemetry pipeline work remain separate.

Journal compatibility: keep this instrumentation option and code revision stable
for an in-flight invocation. Enabling new journal-producing code for already-running
old invocations requires the usual compatible deployment/drain strategy. The
acceptance starts fresh invocations and restarts them with identical code/config.
