# D1 Grafana Cloud data-plane slice

**PARTIAL — metrics delivery active; restart-durable replay NOT accepted.**
Fleet remains DEFERRED / STOP. The existing native Alloy service remains the only
collector; no `remotecfg`, supervisor, datastore or broker was introduced.

## What is proved and what is not

Alloy 1.19.2 (`becfd489a7bb459c0496893b555fb87a003296b1`) accepts the native
`prometheus.remote_write.grafana_metrics` composition. The actual BWS credential
works for ingestion and Cloud query. A unique synthetic metric reached Grafana.
Local startup/restart and local telemetry work with an unavailable exporter.

**Disk retention is not restart replay.** The first Cloud acceptance test kept
outage samples in the WAL across restart, but those samples did not appear in
Cloud after reconnect, while connected/restored samples did. Do not claim
restart/reboot-durable telemetry delivery from the presence of WAL files.

The installed binary's ELF build metadata pins Prometheus `v0.313.2`. Its WAL
watcher initializes its start timestamp to the current time and sends only later
samples. Replaying existing records reconstructs series/cache but filters those
old samples. A changed remote-write config also creates a new queue even when its
explicit name is unchanged. The first test changed its proxy option at recovery;
the second test kept the exact remote-write config fixed. It proved successful
network recovery for samples generated after the offline restart, but again no
replay of the pre-restart outage samples. The queue drained to zero.
No Alloy replacement, patch, build, experimental replay mechanism or architecture
rewrite is used to hide this limitation. Future durable-restart acceptance needs
a supported native implementation and repeat Cloud readback of pre-restart
outage samples. Current metrics are asynchronous best effort, not durable history.

## Evidence

- [Summary](evidence/summary.json): independent acceptance results and limits.
- [Offline local-only test](evidence/offline.json): exact local config restored;
  two unique samples before restart, same oldest timestamp and three afterward.
- [Cloud test](evidence/cloud.json) and [follow-up query](evidence/cloud-first-followup-query.json):
  real ingestion, offline startup/restart, and failed outage-sample readback.
- [Fixed-config transport test](evidence/transport.json): temporary loopback
  CONNECT fixture pins only the Metrics destination, carries opaque TLS, records
  no traffic and stores no queue. It blocks existing/new connections, restarts
  Alloy with the same config, and restores network transport without a config
  change or restart. Fixture terminates; the normal metrics config is restored.
- [Pinned replay implementation](evidence/replay-source.json): binary dependency
  metadata and exact source references; no upgrade or inferred alternate version.
- Local telemetry counters during the [first offline test](evidence/local-during-outage.json)
  and [Cloud outage](evidence/local-during-cloud-outage.json).
- [Final live service/secret metadata](evidence/live-service-final.json),
  [config validation](evidence/config-validation.json),
  [platform tests](evidence/platform-tests.txt), Ansible staging/idempotency logs.
- [Final D1 preservation](evidence/d1-preserved-final.json): existing object, memory, Task,
  artifact hashes and backup PAUSED; original pre-reboot baseline untouched.

The maintenance TaskSpec is an unsubmitted draft: the accepted kernel has no
host-maintenance execution capability; no fake durable Task was created.

## Configuration, secrets and recovery

Nonsecret destination/identity belong in the versioned
[Alloy fragment](../../infra/alloy/metrics.alloy.inactive), not BWS:
`https://prometheus-prod-40-prod-sa-east-1.grafana.net/api/prom/push`, instance
`3602220`. Despite its staging filename, this fragment is composed into the active
config by the existing helper. The local-only source file is still unchanged.

Only `GRAFANA_CLOUD_METRICS_API_KEY` is sourced from BWS project `blaine-dev`
(`ac68b692-2150-45da-ab69-b4ca0085935a`). The existing helper retrieves the bootstrap
from GNOME Keyring, selects that key through a short-lived BWS child, and sends it
over stdin to the existing protected atomic writer. Root runtime material is
`/etc/blaine/secrets/grafana-metrics.env`, mode 0600, beneath mode 0700 parent.
No BWS/bootstrap value enters Git, documentation, argv or evidence.

```sh
# Explicit bounded maintenance; no credential lookup at normal boot/restart:
python3 /usr/local/lib/blaine/grafana-cloud.py materialize-metrics
sudo -n python3 /usr/local/lib/blaine/grafana-cloud.py activate-metrics
```

[Ansible](../../infra/ansible/grafana-metrics.yml) stages the helper and fragment;
it never retrieves secrets or activates/restarts services itself. The helper
composes existing host/self scrape fanout with native remote-write, validates,
installs `/etc/systemd/system/alloy.service.d/blaine-metrics.conf`, and restarts
Alloy. `/etc/blaine/infra/metrics.enabled` records the optional composition.
Unknown active compositions are refused. Legacy OTLP helper and rootless-host
playbook refuse to overwrite active metrics; reconcile explicitly before applying
local-pipeline changes. Scratch and live staging second runs are idempotent.

Normal enabled native service operation remains user `alloy`, with no sudo,
terminal, BWS login, Fleet registration or Cloud readiness dependency. The local
secret file is a bootstrap input; remote authentication/connectivity is async.
Fleet material remains inactive. No public listener was introduced.

## Bounded storage policy

WAL: `/var/lib/alloy/data/prometheus.remote_write.grafana_metrics/wal`, on the
normal NVMe platform filesystem, never `/srv/blaine-backup`. Truncation every
5 minutes; minimum keepalive 5 minutes; maximum keepalive 1 hour; outgoing sample
age limit 1 hour. Queue capacity 2500 per shard, 1–2 shards, batches up to 500,
deadline 5 seconds, backoff 1–30 seconds, request timeout 10 seconds. HTTP 429
retries are enabled; permanent authentication/4xx failures can discard data.

Time/queue limits are **not a filesystem byte quota**. WAL uses 128 MiB segments;
checkpoint/deletion is segment-based. Unsent aged samples can be lost. Separately,
this version filters pre-watcher-start samples regardless of their retained age.
The composition caps each of two fixed host/self targets to 5000 samples and a
2 MiB body every 30 seconds, target_limit=1: at most 480 MiB/hour of accepted scrape
bodies before WAL encoding/metadata. Over 1 TB filesystem headroom was observed;
short offline-test WAL size grew from 84,865 to 125,942 bytes. Broader targets,
longer retention or arbitrary OTLP-to-remote-write fan-in need a capacity review.
The bounded current stream is not an unlimited spool; no hard-byte-quota claim.

## Other signals and D1.G

Logs and traces remain local-only. Remote logs/durability are not activated;
Loki WAL is experimental and not adopted. The historical inactive OTLP fragment
has an in-memory 1000-request queue with a 60-second retry window, no persistent
storage; this is not a trace durability claim. No extra exporter was activated.

D1.A/B/C/D remain accepted. D1.G has NOT executed and may PASS with Grafana
unreachable. At a later authorized reboot, check local Alloy readiness and host
telemetry first. Cloud reconnection/new sample delivery are supporting evidence
only; do not expect this version to replay unsent pre-reboot samples. Original
object/MIRIX/WAITING Task identities are unchanged. Backup PAUSED; no push/reboot.

References: [remote-write/WAL](https://grafana.com/docs/alloy/latest/reference/components/prometheus/prometheus.remote_write/),
[WAL tools](https://grafana.com/docs/alloy/latest/reference/cli/tools/),
[pinned watcher](https://github.com/prometheus/prometheus/blob/v0.313.2/tsdb/wlog/watcher.go),
[pinned queue replacement](https://github.com/prometheus/prometheus/blob/v0.313.2/storage/remote/write.go).
