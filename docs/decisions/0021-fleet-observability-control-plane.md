# ADR 0021 — Fleet Management as the remote observability control plane

**Status:** Accepted
**Validation:** Partially Validated; deployment STOP on Alloy 1.19.2
**Date:** 2026-09-21

## Context

The operator explicitly selects Grafana Cloud Fleet Management to govern mutable
observability configuration. This extends ADR 0018's operational cockpit direction;
it does not introduce a multi-host platform or change durable ownership. The
existing native Alloy service remains the collector. Fleet connectivity and
telemetry ingestion are different capabilities with different credentials/IDs.

## Decision

Git/Ansible own local bootstrap, essential local telemetry, secret references and
host recovery. Fleet is the accepted remote observability control-plane direction,
using Alloy's native `remotecfg` mechanism as an augmentation. Fleet availability
must not gate local collector startup or any Blaine runtime dependency.

BWS is the secret source of truth; GNOME Keyring holds the operator's machine-account
bootstrap credential. Extend the existing protected runtime materializer. An
unlocked interactive vault is not a runtime requirement. API keys never enter Git,
configuration literals, evidence or shell arguments.

The supplied OpAMP `/v1/opamp` configuration is considered but **not adopted** for
D1. No Supervisor, generated installer, second collector, runtime replacement or
custom substitute supervisor is selected. Essential local pipelines stay local.
Future `grafana.fleet.read`, `.propose_config` and `.apply_config` capabilities
require explicit policy/audit boundaries and are **deferred**, not implemented.
Remote pipeline write authority must be governed because it changes code/config
executed within the collector's permissions; it is not unrestricted host authority.

## Validation

Integration evidence proves BWS/Keyring access, Fleet HTTP authentication/read APIs,
protected materialization and native syntax validation. A bounded unavailable-
endpoint test disproved the required offline-start property on installed Alloy
1.19.2: registration failure during initial configuration evaluation exits Alloy,
even with all essential pipelines locally defined. The package's restart policy
then exhausted its start limit. Exact original config was restored; the limit
was reset once and local readiness/three-signal persistence passed again.

**Operational Fleet adoption is STOPPED.** No collector was enrolled into live
Fleet, no remote pipeline was changed/exercised and no Cloud telemetry delivery
is claimed. The fixed proposed ID `blaine-platform` has not been proved as an
enrolled identity across restart. Syntax PASS is not operational acceptance.

[Evidence](../../experiments/d1-grafana-fleet/evidence/summary.json),
[runbook](../platform-grafana-cloud.md),
[official native mechanism](https://grafana.com/docs/alloy/latest/reference/config-blocks/remotecfg/),
[exact release implementation](https://github.com/grafana/alloy/blob/v1.19.2/internal/service/remotecfg/remotecfg.go).

## Consequences and reconsideration

Local observability remains accepted and independent. D1.A/B/C/D and prepared
D1.G identities remain unchanged. D1.G can test the local foundation without Fleet.
Before promoting native Fleet, demonstrate safe offline initial load and recovery
with a reviewed supported implementation, then repeat enrollment, identity,
remote-assignment and outage acceptance. Do not work around this STOP by silently
introducing a new supervisor or upgrading/replacing the collector in this slice.
No UI operation or ingestion token alone fixes this runtime behavior.

## Independent data-plane decision — 2026-09-21

Grafana Cloud ingestion and Fleet configuration are separate planes. Select
native `prometheus.remote_write` for asynchronous metrics, with Alloy as local
collection/processing and bounded transport boundary. Cloud is a best-effort sink,
never Task/artifact authority or a boot prerequisite. No local metrics database,
second collector or queue service is added. Local Git/Ansible bootstrap remains
authoritative. Nonsecret destinations/instance IDs belong in versioned config;
BWS holds only new secret values, materialized locally for noninteractive restart.

Operational acceptance is PARTIAL: the installed collector started offline,
retried, preserved local output and retained samples through restart. Cloud
readback passed for live metrics. Pending pre-restart samples remained in the WAL
but failed upstream readback: the pinned watcher filters samples older than its
startup. Restart-durable delivery is NOT accepted; disk presence is not replay.
Retention/queue/input limits are explicit, but are not a hard filesystem quota. See [data-plane evidence](../../experiments/d1-grafana-cloud-data-plane/README.md).
This does not weaken the Fleet STOP. Fleet reconsideration still requires native
offline startup, later reconnect and local config continuity. D1.G does not depend
on either Cloud availability or a future governed Fleet capability.

## Operational closure — accepted best-effort semantics

The human accepts the current data plane and closes this slice. Grafana Cloud is
a **best-effort asynchronous observability sink**. Live delivery, bounded temporary
network buffering/retry, same-process reconnect/drain and Cloud-independent local
startup are PASS. Replay across Alloy process restart is NOT GUARANTEED / FAIL;
lossless durable transport is NOT CLAIMED. The technical experiment remains PARTIAL,
not an indefinitely open adoption task. Historical evidence in commit `254e09b`
is unchanged. D1.G remains independent of Cloud and of stronger telemetry durability.

[OBS-001 / YouTrack NCP-3](https://leofuso.youtrack.cloud/issue/NCP-3) is the explicit
Upstream/Backlog follow-up. It records future native Alloy fixes, stable persistent
queues, `prometheus.write.queue` only when mature, or explicit bounded-loss acceptance
if stronger durability is unjustified. No local Prometheus/Mimir/Loki/Tempo is to
be introduced merely to solve it. No investigation is implemented in this closure.
See [current coverage and verified queries](../platform-observability-inventory.md).
