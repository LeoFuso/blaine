# ADR 0018 — Blaine Local Platform, Durability and Observability Architecture

> Packaging update, 2026-09-21: [ADR 0020](0020-rootless-docker-operator-runtime.md)
> selects rootless Docker under user systemd + linger for the four-container D1
> infrastructure. It supersedes rootful/docker-group operating assumptions and
> narrows container packaging preferences below. Durability, Task ownership and
> observability boundaries remain unchanged; migration acceptance is separate.

> Observability extension, 2026-09-21: [ADR 0021](0021-fleet-observability-control-plane.md)
> accepts Fleet Management as the remote control-plane direction with local bootstrap
> authority. Deployment is STOPPED on Alloy 1.19.2 offline-start behavior; no remote
> activation is implied. Other architectural boundaries below remain unchanged.

**Status:** Proposed for acceptance
**Date:** 2026-09-20
**Scope:** Blaine runtime, local infrastructure, durability, backup, host configuration, ingress and observability

---

## 1. Context

Blaine is intended to be a long-lived, personal-first agentic system running primarily on a dedicated bare-metal Linux workstation.

This machine is not a disposable development environment and is not a temporary precursor to a future cloud deployment.

The expected operating model is:

> **The local bare-metal installation is a real Blaine deployment target.**

The hardware is expected to remain substantially stable for a long period. Blaine will evolve in place together with its databases, semantic memory, artifacts, preferences, local models and operational infrastructure.

Consequently, we optimize for:

* long-term maintainability of one machine;
* straightforward operation;
* inspectability;
* recoverability;
* high-quality dogfooding;
* deep debugging;
* preservation of accumulated knowledge;
* minimal unnecessary abstraction;
* reuse of mature infrastructure instead of custom platform code.

We explicitly do **not** optimize for:

* fleet management;
* Kubernetes deployment;
* multi-node high availability;
* transparent migration between cloud providers;
* ephemeral hosts;
* bit-for-bit reproduction of the entire workstation;
* infrastructure complexity whose primary benefit would only appear at fleet scale.

---

# 2. Decision Summary

Blaine will run as a **long-lived single-node bare-metal platform**.

The platform will use:

* **Linux/systemd** as the runtime process supervisor;
* **Ansible** to maintain the Blaine-owned portion of host configuration;
* **Caddy** as the ingress/reverse-proxy boundary;
* **PostgreSQL** as the primary durable structured store;
* **two Redis instances with deliberately different durability semantics**;
* **ClickHouse** as the local analytical/event database required initially by Langfuse and potentially usable by Blaine analytics later;
* **S3-compatible Object Storage** as a first-class Blaine storage primitive;
* **Restate** for durable execution lifecycle, not durable knowledge;
* **vLLM** for local inference;
* **Langfuse self-hosted locally** for high-fidelity cognitive/LLM observability;
* **Grafana Alloy** as the local telemetry gateway;
* **Grafana Cloud** as the primary operational cockpit;
* **OpenTelemetry/OTLP** as the interoperability backbone for telemetry;
* a Blaine-owned, versioned **ExecutionEvent** model for semantic forensic execution records.

The only storage classes considered **mandatory to back up as Blaine's durable brain** are:

1. **PostgreSQL**
2. **Object Storage**

Everything else is either execution infrastructure, cache, queueing, analytics or observability and must not contain uniquely valuable knowledge unavailable from PostgreSQL or Object Storage.

---

# 3. Core Architectural Invariants

## 3.1 PostgreSQL + Object Storage are the durable brain

The most important durability invariant is:

> **No uniquely valuable long-term Blaine knowledge may exist only in Restate, Redis, ClickHouse, Langfuse, Grafana or another observability/execution subsystem.**

Durable valuable information must eventually exist in one of:

```text
PostgreSQL
    structured knowledge/state

Object Storage
    artifacts/evidence/large immutable objects
```

Conceptually:

```text
               BLAINE DURABLE BRAIN

        ┌──────────────────────┐
        │      PostgreSQL      │
        │                      │
        │ structured state     │
        │ MIRIX memory         │
        │ preferences          │
        │ learned facts        │
        │ metadata             │
        └──────────────────────┘

        ┌──────────────────────┐
        │    Object Storage    │
        │                      │
        │ artifacts            │
        │ evidence             │
        │ outputs              │
        │ transcripts          │
        │ context snapshots    │
        │ generated files      │
        └──────────────────────┘
```

These two systems receive the strongest backup and restore guarantees.

---

## 3.2 Restate owns execution, not truth

Restate remains responsible for:

* Task execution lifecycle;
* durable invocation state;
* retries;
* timers;
* suspension/resumption;
* pause/resume/cancel;
* crash recovery;
* durable workflow progress.

Restate is **not** a source of long-term Blaine knowledge.

Therefore:

```text
Restate durability
    = survive normal crashes/restarts

Restate backup
    ≠ required disaster-recovery source of truth
```

Catastrophic loss of Restate storage may cause:

* in-flight Tasks to disappear;
* timers to disappear;
* retries to be forgotten;
* work to have to be restarted.

It must **not** cause already-produced valuable knowledge or completed work to disappear.

That work must already have crossed the durability boundary into PostgreSQL, Object Storage, Git or another deliberate deliverable.

---

## 3.3 Observability is never authoritative runtime state

Grafana, Langfuse, ClickHouse telemetry, logs and traces are diagnostic systems.

Blaine correctness must not depend on them.

If:

```text
Grafana Cloud dies
Alloy dies
Langfuse dies
ClickHouse dies
```

Blaine may lose visibility, but runtime authority remains with:

```text
Restate
PolicyGate
Completion Contracts
deterministic verifiers
authoritative evidence/artifacts
```

---

# 4. Target Host Topology

The intended machine looks approximately like this:

```text
┌───────────────────────────────────────────────────────────────┐
│                    BLAINE BARE-METAL HOST                     │
│                                                               │
│                         systemd                               │
│                            │                                  │
│       ┌────────────────────┼────────────────────┐             │
│       │                    │                    │             │
│       ▼                    ▼                    ▼             │
│    Runtime                Data              Operations        │
│                                                               │
│    Blaine              PostgreSQL             Caddy          │
│    Restate             Redis Ephemeral        Alloy          │
│    vLLM/Qwen           Redis Durable          Ansible        │
│    workers             ClickHouse                            │
│    MIRIX               Object Storage         Langfuse       │
│                                                               │
│                           │                                   │
│                           │                                   │
└───────────────────────────┼───────────────────────────────────┘
                            │
                    sanitized telemetry
                            │
                            ▼
                     Grafana Cloud


                 BACKUP / RECOVERY PLANE

        PostgreSQL ─────┬────► secondary storage
                        └────► off-site / S3

        Object Store ───┬────► secondary storage
                        └────► off-site / S3
```

---

# 5. Runtime Supervisor: systemd

`systemd` is the primary runtime control plane.

Typical units may include:

```text
blaine.service
vllm.service
restate.service

postgresql.service

redis-ephemeral.service
redis-durable.service

clickhouse-server.service

object-storage.service

langfuse-web.service
langfuse-worker.service

alloy.service

caddy.service
```

systemd owns:

* boot-time startup;
* shutdown;
* restart policies;
* dependencies;
* service users;
* environment files;
* cgroups;
* CPU/memory resource controls;
* process signals;
* service health;
* journald integration.

We will **not** build a custom Blaine process supervisor.

We will also not use Process Compose as a permanent runtime control plane unless a concrete requirement appears that systemd cannot reasonably satisfy.

---

# 6. Container Policy

Docker Compose is **not** the Blaine platform abstraction.

The machine is not treated as a disposable Compose environment.

Native services are preferred when the software is naturally distributed and operated as a native Linux service.

This is particularly desirable for:

* PostgreSQL;
* Redis;
* ClickHouse;
* Caddy;
* Alloy;
* Restate;
* vLLM;
* Blaine itself.

However:

> Containers are not forbidden.

For software whose upstream deployment model is strongly container-oriented — most notably Langfuse — an OCI image may be used as a **packaging unit**.

If this is required, the preferred model is:

```text
systemd
   ↓
Podman / Quadlet
   ↓
Langfuse OCI image
```

rather than making Docker Compose responsible for the entire Blaine platform.

The distinction is intentional:

> **Use containers where they solve packaging. Do not introduce container orchestration where it solves no problem we currently have.**

---

# 7. Host Configuration: Ansible

Ansible will maintain the **Blaine-owned portion of the machine**.

Its purpose is not to reproduce the workstation from bare metal.

Its purpose is:

> **Keep the long-lived Blaine host understandable, convergent and resistant to configuration drift.**

Ansible may manage:

* Blaine-specific packages;
* service users/groups;
* directories;
* file permissions;
* systemd unit files;
* systemd timers;
* PostgreSQL configuration relevant to Blaine;
* Redis configurations;
* ClickHouse configuration;
* Caddy configuration;
* Alloy configuration;
* backup configuration;
* exporter configuration;
* service versions;
* deployment/update procedures.

It should **not initially manage**:

* BIOS;
* firmware;
* disk partitioning;
* the entire desktop/workstation;
* OS installation;
* every package installed by the user;
* NVIDIA drivers unless a concrete need appears;
* kernel lifecycle unless a concrete need appears.

The goal is:

```text
repo knows how Blaine is configured
```

not:

```text
repo fully recreates Leonardo's computer
```

---

# 8. Dependency and Version Management

The Blaine repository should know, at a useful level, which infrastructure versions constitute a known-good installation.

This is analogous to dependency management in a build system.

A version manifest may contain:

```text
Python
Blaine
Restate
vLLM
PostgreSQL
Redis
ClickHouse
Langfuse
Alloy
Caddy
Object Storage implementation
```

This does not imply that every host dependency must be pinned or automatically installed.

The objective is:

> **Know which meaningful versions produced the currently known-good Blaine installation.**

Version changes should be deliberate and reviewable.

---

# 9. PostgreSQL

PostgreSQL is the most important structured persistent system in Blaine.

It contains or may contain:

* Blaine persistent application state;
* MIRIX semantic memory;
* learned preferences;
* structured knowledge;
* durable metadata;
* Langfuse relational metadata where applicable.

A single PostgreSQL instance is preferred.

Logical isolation should be achieved through separate databases/users rather than separate physical PostgreSQL servers.

Example:

```text
PostgreSQL
├── blaine
│    └── user: blaine
│
└── langfuse
     └── user: langfuse
```

We explicitly prefer:

> one well-operated PostgreSQL instance

over:

> multiple PostgreSQL instances created merely for architectural purity.

Operational isolation may be added later if actual workloads prove it necessary.

---

# 10. Redis: Two Deliberate Durability Profiles

Blaine will deliberately operate two Redis instances.

They represent different semantics, not arbitrary duplication.

## 10.1 Redis Ephemeral

Purpose:

```text
cache
memoization
recomputable derived state
temporary indexes
deduplication hints
probabilistic structures that are cheap to rebuild
```

Expected characteristics:

```text
persistence: disabled or minimal
eviction: allowed
loss: acceptable
```

Example:

```text
maxmemory-policy allkeys-lru
```

If the instance disappears, Blaine reconstructs the relevant state.

---

## 10.2 Redis Durable

Purpose:

```text
queues
Langfuse/BullMQ
valuable ephemeral coordination
expensive-to-reconstruct probabilistic structures
operational state where restart continuity matters
```

Expected characteristics:

```text
AOF/RDB enabled as useful
noeviction
persistent volume
```

This Redis is durable for **operational recovery**, but it still does not become a long-term source of unique Blaine knowledge.

There should be no information whose permanent loss would meaningfully erase Blaine's learned state and which exists only in Redis.

---

# 11. ClickHouse

One local ClickHouse server is sufficient initially.

Initial need:

```text
Langfuse analytical/tracing workload
```

Logical isolation:

```text
ClickHouse
├── langfuse
└── blaine_observability   # reserved/future
```

Blaine-owned schemas must not be placed inside Langfuse-managed databases.

ClickHouse may later become the natural home for high-volume Blaine analytical data such as:

```text
ExecutionEvents
model behavior analytics
decision patterns
capability statistics
longitudinal task analytics
```

This should happen only after dogfooding demonstrates a real need.

ClickHouse is not initially part of Blaine's critical backup boundary.

---

# 12. Object Storage Is a First-Class Blaine Primitive

Blaine requires an Object Storage abstraction independently of Langfuse.

Conceptual interface:

```text
ArtifactStore / ObjectStore

put()
get()
exists()
metadata()
delete()
```

The local implementation should expose an S3-compatible API.

The exact implementation may be MinIO or another appropriate local S3-compatible service.

Possible buckets/namespaces:

```text
blaine-artifacts
blaine-evidence
blaine-context
blaine-worker-transcripts
blaine-deliverables

langfuse-events
langfuse-media
```

Object Storage is used for:

* large artifacts;
* exact evidence;
* generated files;
* context snapshots when preservation is required;
* raw model payloads when permitted;
* worker transcripts;
* large connector responses;
* binary outputs;
* immutable forensic payloads.

Large content should generally be referenced from telemetry/events rather than duplicated into every log/span.

---

# 13. API Gateway / Edge: Caddy

Caddy will provide the local ingress/reverse-proxy boundary unless a later requirement justifies a heavier API gateway.

Caddy owns:

* stable service endpoints;
* reverse proxying;
* TLS where useful;
* host/path routing;
* network-facing access control;
* access logging.

Examples:

```text
blaine.local
langfuse.local
objects.local
```

Services should not each invent their own external exposure model.

Caddy does **not** own business authority.

The boundary remains:

```text
Caddy
  → network access

PolicyGate
  → semantic authority
```

PolicyGate continues to decide whether Blaine is authorized to perform an action.

A future Kong/Envoy/APISIX-class gateway should only be introduced if concrete requirements appear such as:

* sophisticated external auth;
* multi-tenant API management;
* advanced quotas;
* service mesh behavior;
* complex traffic shaping.

Those problems do not currently exist.

---

# 14. Observability Goal

The core requirement is:

> **When Blaine behaves strangely, a developer must be able to answer “what exactly happened and why?” using captured evidence rather than inference or guesswork.**

For a Task we eventually want to reconstruct:

* Task creation;
* lifecycle transitions;
* Restate invocations;
* retries/resumes;
* context resolution;
* evidence selection;
* MIRIX queries/results;
* project/graph retrieval;
* model selection;
* provider/runtime identity;
* model configuration;
* prompts/messages/context packets where permitted;
* raw model output;
* parsed decisions;
* validation results;
* PolicyGate decisions;
* capability calls;
* external calls;
* worker/session lifecycle;
* Codex/Goose/Multica transcripts;
* artifact production;
* human decisions;
* critic/verifier results;
* Completion Contract evaluation;
* failures;
* timeouts;
* recovery;
* final Task outcome.

This is not “add logging”.

It is a forensic execution subsystem.

---

# 15. Blaine ExecutionEvent

OpenTelemetry will not define Blaine's semantic execution model.

Blaine owns a versioned append-oriented `ExecutionEvent` contract.

Conceptually:

```text
ExecutionEvent
├── event_id
├── event_type
├── schema_version
│
├── occurred_at
├── recorded_at
│
├── task_id
├── run_id
├── step_id
├── attempt_id
│
├── trace_id
├── span_id
│
├── parent_event_id
├── causation_event_id
│
├── producer
│   ├── kind
│   ├── component
│   ├── component_version
│   └── code_revision
│
├── references
│   ├── model_call_id
│   ├── capability_call_id
│   ├── worker_session_id
│   ├── artifact_ids
│   ├── human_decision_id
│   └── restate_invocation_id
│
├── outcome
├── payload
├── payload_refs
│
└── sensitivity/redaction metadata
```

Example event families:

```text
task.*

context.*

evidence.*

memory.*

model.*

policy.*

capability.*

connector.*

worker.*

artifact.*

human_decision.*

critic.*

verifier.*

completion.*

failure.*
```

This model must remain independent of Grafana, Langfuse or any particular backend.

---

# 16. Physical Trace Causality vs Blaine Logical Causality

Blaine has durable workflows. A Task may:

```text
run
pause
lose the process
wait for a human
resume hours later
run elsewhere
```

A single continuously active trace is not an adequate semantic representation.

Therefore we distinguish:

## Runtime trace causality

OpenTelemetry:

```text
trace_id
span_id
parent_span_id
span links
```

## Blaine durable logical causality

```text
task_id
run_id
event_id
causation_event_id
step_id
attempt_id
```

A Task Run may therefore contain several physical trace segments.

Span Links may connect related segments, while the Blaine ExecutionEvent graph retains the authoritative logical causal chain.

We must not force:

```text
task_id == trace_id
```

or:

```text
run_id == trace_id
```

These identifiers serve different purposes.

---

# 17. OpenTelemetry

OpenTelemetry is the interoperability backbone for:

* traces;
* metrics;
* log correlation;
* context propagation;
* OTLP transport;
* ecosystem integrations.

It is not:

* Blaine's authoritative event model;
* Blaine's lifecycle state;
* Blaine's durable knowledge store.

Blaine application code should avoid coupling domain semantics unnecessarily to backend-specific telemetry concepts.

OpenTelemetry provides transport and operational correlation.

`ExecutionEvent` provides Blaine semantics.

---

# 18. Grafana Alloy

Alloy is the single local telemetry gateway.

It receives or scrapes telemetry from:

```text
Blaine
Restate
vLLM
PostgreSQL/exporter
Redis
ClickHouse
Langfuse
Caddy
GPU
Linux host
systemd/journald
```

Inputs may include:

```text
OTLP
Prometheus endpoints
journald
host metrics
```

Alloy handles:

* collection;
* normalization;
* redaction;
* filtering;
* routing;
* export to Grafana Cloud.

Individual services should not each require bespoke Grafana Cloud integration.

---

# 19. Grafana Cloud

Grafana Cloud is the primary operational cockpit.

It should become the normal answer to:

> “What is happening on the Blaine machine?”

The goal is explicitly **not** to operate Blaine by keeping several terminals open with `tail -f`.

Grafana should eventually show:

## Host

```text
CPU
RAM
disk
network
temperature
```

## GPU

```text
GPU utilization
VRAM
temperature
power
clocks
PCIe traffic
```

## vLLM

```text
requests running
requests waiting
TTFT
tokens/sec
KV cache utilization
prompt/generation tokens
latency
errors
```

## Runtime

```text
Blaine Tasks
Restate retries
worker activity
capability latency
PolicyGate denials
Codex escalations
human intervention
```

## Data services

```text
PostgreSQL
Redis ephemeral
Redis durable
ClickHouse
Object Storage
```

## Operational health

```text
systemd service status
Caddy traffic
Langfuse health
backup age
backup failures
```

Grafana Cloud receives primarily operational and sanitized telemetry.

It should not casually receive:

```text
complete private source code
complete prompts
complete semantic memories
credentials
private documents
full sensitive tool payloads
```

---

# 20. Langfuse

Langfuse runs **locally**.

Reason:

The highest-density sensitive material is likely to exist in:

* model prompts;
* context packets;
* semantic memory retrieval;
* model responses;
* critic inputs;
* tool payloads;
* generated reasoning artifacts;
* potentially private source code/documents.

Langfuse is the specialized cognitive observability UI.

It should answer questions such as:

```text
What exactly did Qwen receive?

What did it return?

Which model/version/configuration was used?

Why did it choose COMPLETE?

Which memories were retrieved?

How many tokens were used?

What did the critic see?

How did Qwen compare with another model?
```

Grafana should still receive the operational span:

```text
model.invoke
duration = ...
status = ...
model = ...
tokens = ...
```

while Langfuse may retain richer local content.

The desired split is:

```text
Grafana Cloud
    whole-system operational visibility

Langfuse Local
    cognitive/model-level deep inspection
```

---

# 21. Model Call Observability

Every meaningful model invocation should eventually expose a stable `model_call_id`.

Captured metadata should include, where available:

```text
provider
runtime
requested model
resolved model
model/version/digest

temperature
top_p
top_k
seed
max tokens
response format
structured schema hash
constrained decoding mode

prompt/context artifact references
raw-response artifact reference

parsed result
validation result

input tokens
output tokens
cache usage
latency
TTFT
estimated/actual cost

retry/error
```

Sensitive exact in/out should remain local or in controlled Object Storage according to classification rules.

---

# 22. Producer Provenance

Every meaningful result should identify its producer.

Examples:

```text
Qwen local inference
Codex/OpenAI cloud inference
embedding model
MIRIX
Restate
deterministic Blaine application code
PolicyGate
external connector
worker
human
```

This allows later analysis such as:

```text
Qwen COMPLETE decisions rejected by validation

PolicyGate denial rate by capability

Qwen → Codex escalation rate

critic disagreement by model/version

retrieval usefulness by memory source
```

---

# 23. Service Telemetry

Where possible, use existing observability integrations rather than writing custom instrumentation.

Expected examples:

```text
vLLM
    Prometheus metrics
    OTel traces

Restate
    Prometheus metrics
    OTel traces

PostgreSQL
    server/exporter metrics
    DB spans emitted by Blaine client instrumentation

Redis
    server/client metrics
    spans emitted by client instrumentation

ClickHouse
    metrics

GPU
    NVIDIA/DCGM metrics

Linux
    host/systemd/journald metrics/logs

Langfuse
    application traces + dependency metrics
```

A crucial distinction is retained:

> Server health and client-side behavior are different signals.

For example:

```text
PostgreSQL metrics
    tell us what the DB is doing.

Blaine DB spans
    tell us how Blaine experienced a particular query.
```

We want both.

---

# 24. Sensitive Data and Redaction

Telemetry should support at least the conceptual classifications:

```text
NORMAL
SENSITIVE
SECRET
```

## NORMAL

Operational metadata that may leave the host.

## SENSITIVE

Potentially:

* private source;
* documents;
* PII;
* semantic memories;
* model context.

May be retained locally and exported only according to explicit policy.

## SECRET

Examples:

* API keys;
* access tokens;
* passwords;
* private keys;
* raw credentials.

These should never be persisted in observability systems.

“Full debugging mode” does not override SECRET handling.

Grafana Cloud receives sanitized telemetry.

Langfuse local may receive richer SENSITIVE model data but still must redact SECRET values.

---

# 25. Backup Policy

The critical backup boundary is intentionally narrow.

## MUST BACK UP

### PostgreSQL

Because it contains Blaine's evolving structured brain.

Recommended protection:

```text
base backup
+
continuous WAL archive
+
Point-In-Time Recovery
```

A PostgreSQL-specific mechanism such as pgBackRest is preferred over generic filesystem copying.

Backups should exist on:

```text
independent local storage
+
off-site/S3
```

---

### Object Storage

Because it contains:

```text
artifacts
evidence
valuable worker outputs
preserved context
deliverables
large durable payloads
```

The object store should similarly have:

```text
local independent copy
+
off-site/S3 copy
```

The primary Object Storage instance is not considered a backup of itself.

---

# 26. Systems Without Mandatory Disaster-Recovery Backup

## Restate

No mandatory backup.

Loss means loss/restart of in-flight execution, not loss of Blaine's brain.

## Redis Ephemeral

No backup by definition.

## Redis Durable

Persistence is useful for operational continuity.

No requirement that it contain permanently unique Blaine knowledge.

## ClickHouse

Initially analytics/observability.

Loss is unfortunate but not correctness-threatening.

## Langfuse

Diagnostic/cognitive observability system.

Loss of historical Langfuse views must not destroy authoritative Blaine knowledge.

## Grafana Cloud

Operational observability, not durability.

---

# 27. Backup Operations Must Be Observable

Backups should not be silent cron jobs.

They should expose:

```text
last_success_timestamp
last_failure_timestamp
duration
bytes
backup_age
offsite_sync_status
```

Grafana should eventually display something like:

```text
BACKUPS

PostgreSQL      ✓ 2h ago
Object Storage  ✓ 4h ago

PITR archive    healthy
Off-site S3     healthy

Last restore test  ✓
```

A backup strategy without periodically tested restore is incomplete.

Restore drills should be performed occasionally against scratch locations/databases.

---

# 28. API and Service Exposure

Not every service should be exposed directly.

Preferred model:

```text
external/local clients
       │
       ▼
     Caddy
       │
       ├── Blaine
       ├── Langfuse UI
       └── intentionally exposed services
```

Infrastructure services such as:

```text
PostgreSQL
Redis
ClickHouse
Restate internals
```

should normally remain bound to localhost or otherwise private unless a concrete reason requires exposure.

---

# 29. Repository Ownership of Infrastructure

The Blaine repository should contain enough information to answer:

> How is the Blaine-owned portion of this machine configured?

Suggested structure:

```text
infra/
├── ansible/
│   ├── host.yml
│   ├── roles/
│   │   ├── postgres/
│   │   ├── redis/
│   │   ├── clickhouse/
│   │   ├── object-storage/
│   │   ├── restate/
│   │   ├── alloy/
│   │   ├── caddy/
│   │   ├── langfuse/
│   │   └── backup/
│   │
│   └── vars/
│       └── versions.yml
│
├── systemd/
├── config/
├── backup/
└── docs/
```

This is not an attempt to build a Blaine operating system.

It is a way to keep important operational knowledge out of:

```text
someone's memory
random /etc files
shell history
```

---

# 30. Host Health Check

A useful future operational command is:

```text
blaine host check
```

or an equivalent Ansible health/check playbook.

It should be able to validate things such as:

```text
PostgreSQL reachable
MIRIX DB reachable

Redis ephemeral running
Redis durable persistence configured

ClickHouse running

Object Store reachable

Restate healthy

vLLM sees GPU

Langfuse reachable

Alloy exporting

Grafana endpoint reachable

Caddy healthy

latest PostgreSQL backup acceptable

Object Storage off-site copy healthy
```

This is useful operational tooling.

It does not need to become another orchestration framework.

---

# 31. Explicitly Rejected / Deferred Approaches

## Kubernetes

Rejected for current architecture.

The system is one permanent machine and does not require cluster orchestration.

---

## NixOS migration

Deferred.

Changing the operating system has substantial cost and currently lacks a sufficiently strong benefit.

---

## devenv as a platform dependency

Not adopted.

It may later be introduced to solve a specific development/toolchain problem, but “machine reproducibility” alone is not enough justification.

---

## Full machine reproduction from Git

Not a goal.

The target is:

```text
inspectable
maintainable
recoverable
version-aware
```

not:

```text
fully reproducible workstation image
```

---

## Docker Compose as platform supervisor

Rejected.

The permanent bare-metal host already has systemd.

Containers may still be used narrowly for software whose upstream packaging strongly benefits from OCI.

---

## Process Compose

Not currently required.

systemd covers permanent service lifecycle, while custom dev supervision is not a current architectural requirement.

---

## Separate PostgreSQL instances for observability purity

Rejected.

Logical isolation is sufficient until actual operational evidence proves otherwise.

---

## Separate Redis instances merely for observability purity

Rejected.

Two Redis instances **are** justified, but because they have incompatible durability/eviction semantics:

```text
ephemeral
durable/noeviction
```

not because Langfuse must be physically isolated from Blaine.

---

## Local Prometheus/Mimir requirement

Not required initially.

Alloy can scrape Prometheus-format metrics and export them to Grafana Cloud.

Mimir is unnecessary for this single-node topology.

---

## Elasticsearch/Kibana

Deferred.

There is currently no demonstrated forensic-search need that justifies adding another substantial storage platform.

---

## Custom observability UI

Rejected for now.

Grafana + Langfuse + Restate UI should be dogfooded first.

A Blaine-specific UI should only be built when repeated workflows show a concrete need.

---

# 32. Failure Philosophy

A core design principle is:

> **Infrastructure failure may interrupt execution, but it should not erase Blaine's accumulated brain.**

Examples:

### Restate disappears

In-flight Tasks may need to restart.

Existing knowledge survives.

### Redis disappears

Operational continuity may be reduced.

Knowledge survives.

### ClickHouse disappears

Analytics/history may be lost.

Knowledge survives.

### Langfuse disappears

Deep model telemetry may be lost.

Knowledge survives.

### Grafana disappears

Visibility is temporarily reduced.

Knowledge survives.

### PostgreSQL disappears without recoverable backup

Unacceptable.

### Object Storage disappears without recoverable backup

Unacceptable.

That distinction determines where engineering effort goes.

---

# 33. Dogfooding Philosophy

Dogfooding should happen against the actual long-lived installation.

We should not maintain:

```text
temporary dev topology
+
different "real" topology
```

unless a real requirement emerges.

The machine itself is the laboratory.

That means:

* real Restate;
* real local inference;
* real PostgreSQL;
* real artifacts;
* real telemetry;
* real backup;
* real recovery behavior.

This increases the value of every Task executed because it exercises the platform we actually intend to keep.

---

# 34. Minimal Implementation Order

This ADR describes the target architecture. It does not require implementing every component simultaneously.

A sensible order is:

### Phase 1 — Durable foundation

```text
PostgreSQL
Object Storage
systemd ownership
basic backup
```

### Phase 2 — Runtime

```text
Blaine
Restate
vLLM
Redis profiles
```

### Phase 3 — Operational visibility

```text
Alloy
Grafana Cloud
host/GPU metrics
service metrics
traces/logs
```

### Phase 4 — Cognitive visibility

```text
ClickHouse
Langfuse local
model-call instrumentation
```

### Phase 5 — Host convergence

```text
Ansible
version manifest
systemd/config ownership
host checks
backup automation
```

### Phase 6 — Forensic Blaine observability

```text
ExecutionEvent v1
artifact references
correlation model
Task Inspector dashboards
longitudinal analysis
```

Implementation order may move based on immediate dogfooding needs.

The architectural boundaries should remain.

---

# 35. Expected Final Operational Experience

Normal operation should look like this:

```text
Grafana
    → Is the machine healthy?
    → Is the GPU saturated?
    → Is vLLM slow?
    → Are Tasks failing?
    → Is PostgreSQL under pressure?
    → Are retries increasing?
    → Are backups healthy?

Langfuse
    → Why did Qwen make this decision?
    → What prompt/context did it receive?
    → What did the critic see?
    → What model/config was used?

Restate UI
    → What is currently executing?
    → What is suspended/retrying?

Blaine/ExecutionEvents
    → What exactly happened semantically
      throughout this Task?

PostgreSQL + Object Storage
    → What valuable knowledge/work survives
      regardless of the above systems?
```

Terminals remain useful for repair and development.

They are not the primary observability UI.

---

# 36. Final Position

This architecture deliberately avoids both extremes.

It does **not** treat the Blaine workstation as an unstructured hobby machine whose configuration exists only in shell history.

It also does **not** turn one personal bare-metal server into a miniature cloud platform.

The chosen approach is:

> **native where native is simple, standard infrastructure where standard infrastructure already solves the problem, declarative enough to understand and maintain the host, and strict about what information must survive.**

The durable core is intentionally small:

```text
PostgreSQL + Object Storage
```

The execution platform is:

```text
systemd + Restate + Blaine + vLLM
```

The local data platform is:

```text
PostgreSQL
Redis Ephemeral
Redis Durable
ClickHouse
Object Storage
```

The operational plane is:

```text
Ansible
Caddy
Alloy
Grafana Cloud
```

The cognitive observability plane is:

```text
Langfuse Local
```

And the semantic forensic layer remains owned by Blaine itself:

```text
ExecutionEvent + Artifact References
```

This gives Blaine a platform that is durable enough to evolve for years, observable enough to dogfood aggressively, simple enough to run on one machine, and modular enough that individual infrastructure choices can be replaced without redefining what Blaine is.
