# Current Blaine observability inventory

Observed live on 2026-09-21 (America/Sao_Paulo; evidence timestamps are UTC).
The Grafana metrics slice is **CONCLUDED and ACCEPTED as best-effort asynchronous
transport**. Technical experiment result remains PARTIAL: process-restart replay
failed; lossless durable delivery is not claimed. The original evidence and commit
`254e09b` are unchanged. This limitation does not block D1.G.

**OBS-001 — Durable telemetry transport across Alloy restart** was created as
[YouTrack NCP-3](https://leofuso.youtrack.cloud/issue/NCP-3), Upstream / Backlog.
Its problem, evidence, desired properties, candidate investigations and non-goals
are recorded there. This is future investigation, not an active implementation or
runtime Task. No additional Grafana credential action is required.

## Collection and delivery actually observed

The unchanged Alloy 1.19.2 / becfd48 config has exactly two Prometheus scrapes:
`host` (`prometheus.exporter.unix.host`) and `alloy` (self metrics), every 30 seconds.
Both feed local OTLP processing/file output and native Cloud remote-write. Cloud
`up` returns 1 for `integrations/unix` and `integrations/self`. Destination is
`https://prometheus-prod-40-prod-sa-east-1.grafana.net/api/prom/push`, instance
`3602220`. Only the API key is in BWS/protected local material; no secret is evidence.

Common host-series labels are `environment="blaine-dev"`, `host="blaine"`,
`instance="blaine"`, `job="integrations/unix"` (Cloud also returned `asserts_env`).
CPU adds `cpu` and `mode`; disk/network add `device`; filesystems add `device`,
`fstype`, `mountpoint`; systemd adds `name`, `state`, `type`.

| Area | Exact metric names observed |
|---|---|
| CPU | `node_cpu_seconds_total`; `node_load1`, `node_load5`, `node_load15` |
| RAM | `node_memory_MemAvailable_bytes`, `node_memory_MemTotal_bytes` |
| Swap | `node_memory_SwapTotal_bytes`, `node_memory_SwapFree_bytes` |
| Filesystem | `node_filesystem_avail_bytes`, `node_filesystem_size_bytes`, `node_filesystem_free_bytes` |
| Disk I/O | `node_disk_read_bytes_total`, `node_disk_written_bytes_total` |
| Network | `node_network_receive_bytes_total`, `node_network_transmit_bytes_total` |
| systemd | `node_systemd_unit_state`, `node_systemd_units`, `node_systemd_system_running` |

Observed snapshot: CPU about 2.16% across 32 logical CPUs; memory used about 27.94%;
46,003,961,856 bytes available; host swap used 1,329,029,120 bytes. These are host
values, not inference-cgroup memory or evidence of a new resource regression.
Filesystem percentages below use available space, so include reserved-block effects.
Network includes physical and virtual interfaces: inspect `device`, do not sum
all interfaces indiscriminately and double-count bridge traffic.

## systemd coverage limitation

Cloud metrics cover the **system manager**, including `alloy.service`, PostgreSQL,
Redis and `user@1000.service`. They do not expose the five nested user services:
`blaine-generation`, `blaine-embedding`, `blaine-mirix`, `blaine-restate`,
`blaine-runtime`. An explicit Cloud query returned zero series for those names;
all five were independently observed active/running via `systemctl --user`.
The user manager being active is not proof its children are healthy. No continuous
Task-success monitor exists. `state="active"` is an activation state, not an API
readiness check or necessarily a running process (oneshot units can be active).
At observation, system-level failed-unit count was 0; the failed-unit list being
empty is an expected result, not a missing-metric error.

## GPU and vLLM

**GPU hardware telemetry: NOT CONFIGURED.** There is no NVIDIA/DCGM exporter in
the active Alloy scrape graph, no hardware-GPU series in its host exporter or
Cloud, and no corresponding exporter in the observed native/container inventory.
NVIDIA persistence/power/suspend services are not telemetry exporters. Utilization,
physical VRAM used/free, temperature, power, clocks and PCIe statistics are not
continuously exported to Grafana. No GPU exporter was installed.

vLLM **does** expose local metrics at `http://127.0.0.1:8000/metrics` (generation)
and `http://127.0.0.1:8001/metrics` (embeddings). Neither is scraped by Alloy, and
Cloud returned no `vllm:.*` series. The installed vLLM supports OTLP tracing via
`--otlp-traces-endpoint` and optional `--collect-detailed-traces`; both current
services omit those options (config and live argv inspected). OTel capability
is present, trace sending is not configured. See [local evidence](../experiments/d1-observability-closure/evidence/vllm-otel.json)
and [official options](https://docs.vllm.ai/en/latest/cli/serve/). Useful names present include:

- `vllm:num_requests_running`, `vllm:num_requests_waiting` (concurrency/queue).
- `vllm:kv_cache_usage_perc` (KV cache, 1 = 100%; not total GPU VRAM).
- `vllm:prompt_tokens_total`, `vllm:generation_tokens_total` (counts; rates can
  derive token throughput, but no such Cloud pipeline is configured).
- `vllm:e2e_request_latency_seconds`, `vllm:time_to_first_token_seconds`,
  `vllm:inter_token_latency_seconds`, `vllm:request_queue_time_seconds`
  (histogram families with `_bucket`, `_sum`, `_count`).

Gauges/counters carry `engine` and `model_name`; histogram buckets also carry `le`.
Estimated per-GPU FLOP/byte application counters are not hardware utilization sensors.

## Logs

**Cloud logs: INACTIVE.** `loki.source.journal` reads journald, forwards through
`otelcol.receiver.loki.local` and the local batch processor to
`/var/lib/alloy/telemetry/local.json` (20 MiB rotation, three backups, three days).
No `loki.write` or remote OTLP exporter is loaded.

System-unit filters include Docker, blaine-infra and Alloy. User-journal filters
select UID 1000 plus Docker, blaine-infra and all five adopted Blaine services.
Generation, embedding and MIRIX journal counters were positive; Restate/runtime
counters were zero since the current collector start. Those sources are wired,
but zero means no observed records in this interval, not proof of a broken source.
Runtime structured execution events also live in
`~/.local/share/blaine/runtime/data/events.jsonl`; that file is **not** scraped by
the current Alloy config. Future Cloud logs need a separately scoped exporter,
credentials and backend readback; nothing was enabled here.

```sh
journalctl --user -u blaine-runtime -u blaine-restate --since '30 minutes ago'
journalctl --user -u blaine-generation -u blaine-embedding -u blaine-mirix
```

## Traces

**Cloud traces: INACTIVE.** Alloy exposes OTLP/gRPC `127.0.0.1:4317` and OTLP/HTTP
`127.0.0.1:4318` (HTTP traces path `/v1/traces`), batches and writes locally.
Observed HTTP receiver accepted-spans and local sent-spans counters were positive.
Retained files contained 55,649 spans / 929 trace IDs with `service.name="worker"`
and Langfuse/Redis/ClickHouse-related attribute names. The producer's name alone
is not proof of Blaine Task tracing; this inventory does not attribute those spans
to the Blaine worker adapter. No remote Tempo/OTLP exporter is loaded.

The deployed Blaine entrypoint and model/memory/workflow/event-sink code match the
repository and contain no OTel instrumentation or trace-context propagation found
by the inspection. Its five service processes have no OTEL-prefixed environment
variables. The real cognitive Task
`task-c07a288d19a208d0e791c192c26d60cd3e0ad520e2a2bedbdd53810a365a8708`
has eight structured events; none has `trace_id`/`span_id`. No matching Task was
found in retained spans. **An end-to-end Task → MIRIX → Qwen → Artifact trace is
NOT PROVEN / not currently accepted.** Durable Task/events/artifact evidence exists;
that is not distributed tracing. Local files rotate, so their current absence
alone cannot prove that no historical span ever existed.

## Useful Grafana PromQL

Every query below was executed against the actual Hosted Metrics backend; full
sanitized responses are in the [query evidence](../experiments/d1-observability-closure/evidence/cloud-queries.json).
No hypothetical GPU/vLLM/user-unit Cloud query is presented as working coverage.

**Total CPU utilization %** — validated: 1 series.

```promql
100 * (1 - avg by (instance) (rate(node_cpu_seconds_total{environment="blaine-dev",host="blaine",mode="idle"}[5m])))
```

**CPU utilization % by logical core** — validated: 32 series.

```promql
100 * (1 - avg by (instance,cpu) (rate(node_cpu_seconds_total{environment="blaine-dev",host="blaine",mode="idle"}[5m])))
```

**Load average, 1 minute** — validated: 1 series.

```promql
node_load1{environment="blaine-dev",host="blaine"}
```

**Load average, 5 minutes** — validated: 1 series.

```promql
node_load5{environment="blaine-dev",host="blaine"}
```

**Load average, 15 minutes** — validated: 1 series.

```promql
node_load15{environment="blaine-dev",host="blaine"}
```

**Used memory % (MemAvailable basis)** — validated: 1 series.

```promql
100 * (1 - node_memory_MemAvailable_bytes{environment="blaine-dev",host="blaine"} / node_memory_MemTotal_bytes{environment="blaine-dev",host="blaine"})
```

**Available memory, bytes** — validated: 1 series.

```promql
node_memory_MemAvailable_bytes{environment="blaine-dev",host="blaine"}
```

**Used swap, bytes** — validated: 1 series.

```promql
node_memory_SwapTotal_bytes{environment="blaine-dev",host="blaine"} - node_memory_SwapFree_bytes{environment="blaine-dev",host="blaine"}
```

**Filesystem used/unavailable %** — validated: 3 series.

```promql
100 * (1 - node_filesystem_avail_bytes{environment="blaine-dev",host="blaine",fstype!~"tmpfs|devtmpfs|overlay|squashfs"} / node_filesystem_size_bytes{environment="blaine-dev",host="blaine",fstype!~"tmpfs|devtmpfs|overlay|squashfs"})
```

**Filesystem available bytes** — validated: 3 series.

```promql
node_filesystem_avail_bytes{environment="blaine-dev",host="blaine",fstype!~"tmpfs|devtmpfs|overlay|squashfs"}
```

**Physical disk read bytes/s** — validated: 3 series.

```promql
rate(node_disk_read_bytes_total{environment="blaine-dev",host="blaine",device=~"nvme.*|sd[a-z]+"}[5m])
```

**Physical disk write bytes/s** — validated: 3 series.

```promql
rate(node_disk_written_bytes_total{environment="blaine-dev",host="blaine",device=~"nvme.*|sd[a-z]+"}[5m])
```

**Network receive bytes/s, by interface** — validated: 7 series.

```promql
rate(node_network_receive_bytes_total{environment="blaine-dev",host="blaine",device!="lo"}[5m])
```

**Network transmit bytes/s, by interface** — validated: 7 series.

```promql
rate(node_network_transmit_bytes_total{environment="blaine-dev",host="blaine",device!="lo"}[5m])
```

**Failed system units, count** — validated: 1 series.

```promql
sum(node_systemd_unit_state{environment="blaine-dev",host="blaine",state="failed"})
```

**Failed system-unit list (empty when none)** — validated: 0 series.

```promql
node_systemd_unit_state{environment="blaine-dev",host="blaine",state="failed"} == 1
```

**Selected system-service active state (1 active, 0 otherwise)** — validated: 5 series.

```promql
node_systemd_unit_state{environment="blaine-dev",host="blaine",name=~"alloy.service|postgresql.*|redis.*|user@1000.service",state="active"}
```

## Next steps — increase coverage, not transport durability

**Overall Blaine observability coverage remains PARTIAL.** Closing the accepted
best-effort transport does not mean the observability rollout is complete. Per the
human's follow-up, the next coverage slice should maximize useful initial coverage
and explicitly map source → local Alloy → Cloud. These are planned work, not
activated pipelines or extra completed acceptance claims. OBS-001 stays separate.

| Priority | Source / point of emission | Intended route to validate | Acceptance / current gap |
|---|---|---|---|
| First | Generation `127.0.0.1:8000/metrics` and embeddings `127.0.0.1:8001/metrics` | Existing Prometheus endpoints → Alloy scrape → local output + current Cloud remote-write | Endpoints verified; absent from current scrape graph. Query both models' queue, tokens, cache and latency in Cloud; preserve bounded cardinality/input. No inference rebuild needed to consume existing metrics. |
| First | NVIDIA hardware | Supported hardware exporter, selected after compatibility check → Alloy → Cloud | Currently NOT CONFIGURED. Validate GPU utilization, physical VRAM, temperature, power, clocks and supported PCIe stats; do not substitute KV-cache metrics. |
| First | Five Blaine user services | User-manager service state + actual readiness signals → Alloy → Cloud | System-level exporter misses these units. Prove each unit's state and supported API readiness independently; `user@1000` or exporter `up` is insufficient. |
| Next | Restate, MIRIX and actual Blaine runtime | Inventory native metrics endpoints first; consume existing endpoints where supported, define bounded instrumentation only where absent → Alloy → Cloud | Endpoint/metric coverage not yet accepted. Include durable execution/failures/waits where supported, without treating MIRIX as Task state or forcing WAITING to look unhealthy. |
| Next | PostgreSQL, Redis, ClickHouse and object storage | Inventory native endpoints or existing Alloy integrations → Alloy → Cloud | Generic host/systemd metrics do not measure database, queue or storage operation. Validate service-specific health, errors, saturation and throughput; credentials remain externally materialized. |
| Next | Rootless Docker and Langfuse Web/Worker | Inventory daemon/container/application emissions and existing local OTLP metrics → Alloy → Cloud where appropriate | Container process existence and local worker spans are not application metric coverage. Avoid duplicate collection; document labels, rates and useful failure signals. |
| Separate subsequent work | Logs and traces | Existing journald/OTLP collection → scoped Cloud destinations after explicit acceptance | Still inactive remotely. Blaine/vLLM trace emission and context propagation require their own proof; collector reception is not an end-to-end Task trace. |

For each source, record endpoint/protocol, owner, metric names/labels, scrape or
push interval, local receiver, Cloud destination, cardinality/storage bounds and
actual Cloud query proof. Retain local bootstrap independence. This table is the
coverage backlog requested by the human, not authorization to implement it in
this closure task. Do not fold these gaps into the durability-only OBS-001.

## Closure and next operational step

Current acceptance: live delivery PASS; temporary network buffering/retry PASS;
same-process reconnect/drain PASS; Cloud-independent Alloy startup PASS;
process-restart replay NOT GUARANTEED / FAIL; lossless transport NOT CLAIMED.
The 1h WAL retention / 5m cleanup is bounded retention, not a hard disk quota.
OBS-001 carries the optional future durability investigation; the current task is closed.

The next observability work is the coverage slice above, starting with the two
already-working vLLM endpoints, GPU and user-service coverage. Independently, the
next prepared platform acceptance is to obtain explicit human authorization for
the **single D1.G reboot**,
then follow [the existing runbook](platform-services.md#d1g--later-human-authorized-reboot-procedure).
Do not reboot as part of this closure. Cloud availability does not gate D1.G.
Backup stays PAUSED. No configuration change, restart, install, reboot or push
was performed during this inventory.

## Platform status

| Component | Status | Current meaning |
|---|---|---|
| Infrastructure foundation | PASS | Accepted foundation; readiness/state verified |
| Rootless Docker | PASS | Adopted; full host reboot remains D1.G |
| D1.C inference | PASS | Generation + embeddings accepted/running |
| D1.D MIRIX | PASS | Retained semantic memory verified |
| D1.B Restate | PASS | Durable Task identity/state retained |
| D1.A Blaine runtime | PASS | Actual runtime accepted; resume/WAITING proofs retained |
| Local metrics | PASS | CPU/RAM/disk/network/system-manager metrics; user-unit gap documented |
| Grafana Cloud metrics | PASS, best-effort | Slice concluded/accepted; restart replay unguaranteed |
| GPU hardware metrics | INACTIVE | NOT CONFIGURED; vLLM metrics are local only |
| Local logs | PASS | Allowlisted journals wired; execution JSONL separate |
| Grafana Cloud logs | INACTIVE | No remote log exporter loaded |
| Local traces | PARTIAL | OTLP reception/file output active; no proven end-to-end Blaine Task trace |
| Grafana Cloud traces | INACTIVE | No remote trace exporter loaded |
| Fleet Management | DEFERRED / STOP | Native startup safety failure preserved |
| OBS-001 | DEFERRED | NCP-3 created, Upstream/Backlog; no implementation |
| D1.G | PENDING REBOOT | Prepared; requires separate human authorization; Cloud-independent |
| Backup | PAUSED | Timer disabled/inactive |
