# Increment 10 — ExecutionEvent v1

**Status:** PASSED — 2026-09-20.

## Architectural constraint

[ADR 0018 — Blaine Local Platform, Durability and Observability Architecture](../decisions/0018-local-platform-durability-and-observability.md)
is mandatory for this increment and future work. Its complete supplied text is
recorded, with only the numbered ADR title adapted to the existing convention.
The recorded proposed status is preserved. No platform deployment is implied.

## Hypothesis and gate

A backend-independent, versioned ExecutionEvent publisher can expose semantic
Task/run causality without changing Restate lifecycle, PolicyGate authority or
CompletionContract verification. JSONL is only an acceptance/local forensic sink.

The gate requires a real Task, strict line-by-line event validation, provenance,
logical causality, exact artifact references, independent final-result verification,
replay without false duplicate effects, and correctness with telemetry unavailable.
SECRET payloads must not enter event records. Existing artifact storage is reused;
S3, Grafana, Alloy, Langfuse, ClickHouse and host configuration remain out of scope.

## Continuity

Increments 8 and 9 remain passed. The supplied development workload resolves
[the earlier missing-workload stop](026-cognitive-kernel-increment-10-workload-stop.md).

## Implemented and validated

Versioned closed JSON-compatible ExecutionEvent v1, backend-independent publisher,
optional production workflow emission, and an isolated JSONL acceptance/local
forensic sink. See [contract](../contracts/execution-event.md). No alternate
observability architecture or infrastructure was introduced.

The implementation worker inspected the existing runtime and produced the scoped
code/tests. A real Restate parent `execution-events` delegated independent
verification to a child Task, consumed its bounded TaskResult, handed off within
the same parent, and published the exact checked implementation manifest. The
fresh verification worker ran the actual focused suite. Its exit was not completion:
the unchanged digest verifier independently evaluated both Tasks' artifact evidence.
The independent offline verifier then checked events, artifacts and server journals.
Cognition was scripted; no result is claimed as live Qwen/Goose inference.

Results: **87 focused tests passed** (78 baseline); **28 schema-valid events**,
7 event classes, maximum record 1,294 bytes. Worker packet: 882 bytes. Child result:
688 bytes. Parent cognitive packets: 990, 1,678 and 1,114 bytes; no child transcript.
There was one verification worker execution, no model calls or model token usage.

The application was SIGKILLed after publication/fsync of the committed worker
capability event and before the publication step acknowledged completion. Restart
retained the capability result and event identity; the sink held one record, and
the worker did not execute again. A separate real Task completed with every
publisher call failing. No cognition/effects followed satisfied verification.

The first offline verifier used a TaskState field name against CognitiveTurn;
that probe-only lookup was corrected from `active_specialist` to `specialist`
after inspecting persisted evidence. No criterion or runtime behavior was changed.
The final retained live run includes available worker attempt references and the
compatibility COMPLETE path's verifier instrumentation.

## Evidence and reproducibility

- [Gate summary](../../experiments/kernel-increment-10/evidence/summary.json)
- [Independent verification](../../experiments/kernel-increment-10/evidence/acceptance/verification.json)
- [ExecutionEvent JSONL](../../experiments/kernel-increment-10/evidence/acceptance/events.jsonl)
- [Recovery](../../experiments/kernel-increment-10/evidence/acceptance/recovery.json)
- [Authority source comparison](../../experiments/kernel-increment-10/evidence/authority-regression.json)
- [Focused tests](../../experiments/kernel-increment-10/evidence/focused-tests.txt)

Run `experiments/kernel-increment-10/probe.py --output <fresh-directory>
--restate-server <existing-server-binary>` using the existing runtime Python.
Then run `experiments/kernel-increment-10/verify.py <directory>/evidence`.
The verifier can also read the retained repository acceptance directory directly.
The probe owns only isolated localhost processes and cleans them up.

## Architectural impact and limits

PolicyGate, CompletionVerifier, Task/NextAction contracts, cognition adapter,
HumanDecision, artifact, context and worker implementations remain byte-identical
to the pre-increment snapshots. Workflow additions publish observations only.
Events do not authorize effects or completion and are not a Task-state store.
The source-of-truth ADR remains proposed as supplied; this bounded gate does not
validate the full target platform. No trace/span was available or fabricated.
SECRET-class records/references and unrestricted metadata are rejected; this is
not a complete redaction system. Publishers must be bounded and delivery may be
lost during outage. Existing in-flight journals require compatible deployment;
this probe validates fresh instrumented invocations and same-code replay.

**Next increment:** 11, cloud/frontier routing seam, subject to its existing safe
provider/configuration and authority gates. No cloud call is authorized by a
semantic preference or by an event record.
