# Grafana Fleet and Cloud telemetry

**2026-09-21: Fleet runtime adoption STOPPED on native Alloy 1.19.2 startup safety.**
Existing local Alloy remains active/enabled and its exact accepted configuration
was restored. Fleet is the accepted architectural direction in
[ADR 0021](decisions/0021-fleet-observability-control-plane.md), not an operational
adoption claim. D1.A/B/C/D remain accepted; D1.G has not run; backup is PAUSED.

## Observed state

| Item | Result |
|---|---|
| Collector | Existing `/usr/bin/alloy`, v1.19.2, revision `becfd48`, native service user `alloy` |
| Selected native mechanism | `remotecfg`, 60-second polling, Basic Auth, redirects disabled |
| Fleet URL / instance | `https://fleet-management-prod-015.grafana.net` / `1838998` |
| Proposed stable ID | `blaine-platform`; inactive, not an enrolled/restart-proven Fleet identity |
| Proposed attributes | `environment=blaine-dev`, `host=blaine`, `role=blaine-platform` |
| BWS/Keyring and protected materialization | PASS |
| Fleet authentication/read API connectivity | PASS: ListCollectors and ListPipelines returned HTTP 200 |
| Native config validation | PASS with actual protected credentials; validation only |
| Fleet enrollment / healthy collector in Fleet | NOT ACTIVATED / NOT PROVEN |
| Remote config assignment | NOT EXERCISED; no remote pipeline changed |
| Local telemetry after restoration | PASS: host metrics, five user journal sources, synthetic metric/log/trace persisted |
| Cloud metrics / logs / traces | All INACTIVE / UNVALIDATED |
| OpAMP Supervisor / second OTel Collector / generated installer | NOT ADOPTED / NOT INTRODUCED / NOT RUN |

[Sanitized evidence](../experiments/d1-grafana-fleet/README.md) separates these
claims. No Grafana API credential or rendered secret environment is evidence.

## Why activation is stopped

The installed native implementation calls Fleet registration during initial
configuration evaluation. An unreachable endpoint causes that evaluation to fail
and Alloy to exit. A bounded test using credential-free `http://127.0.0.1:1`
reproduced this with the real service: no local readiness, five automatic restart
attempts, then systemd start-limit failure. No host firewall/DNS change or second
collector was used. The exact prior config was restored and the start limit reset
once; local Alloy recovered. No Blaine runtime service was restarted.

The release also contains remote-config cache and polling recovery paths. Those
do not establish offline initial startup: the observed registration failure
precedes a successful initial load. See the [installed-release source](https://github.com/grafana/alloy/blob/v1.19.2/internal/service/remotecfg/remotecfg.go)
and [failure evidence](../experiments/d1-grafana-fleet/evidence/startup-failure.json).
Thus a plain native enrollment would violate the explicit local-first requirement.
No custom supervisor, sidecar retry controller, binary patch or upgrade was added.

Before activation, a reviewed supported implementation must pass offline startup
and reconnection. Then validate enrollment, the same collector ID across restart,
a bounded remote assignment and unchanged local pipelines. A Grafana UI change
alone does not fix the current STOP.

## BWS to protected runtime material

The existing [materializer](../infra/grafana-cloud.py) now supports Fleet fields
through **BWS 2.1.0**, reusing its atomic root-only writer:

1. As the operator, retrieve the bootstrap token from GNOME Keyring using the
   established `service=leofuso-lab`, `credential=bws-access-token` attributes.
   The helper captures it; it is not printed or persisted.
2. Read project `blaine-dev`, ID `ac68b692-2150-45da-ab69-b4ca0085935a`, through a
   short-lived BWS child environment. Select exactly the three unique keys
   `GRAFANA_CLOUD_FM_URL`, `GRAFANA_CLOUD_FM_INSTANCE_ID`, `GRAFANA_CLOUD_FM_API_KEY`.
3. Validate the exact Fleet endpoint/instance and reject environment injection,
   missing fields and duplicate keys. Metrics/Logs instance IDs are not accepted.
4. Pass only these fields over stdin to the bounded privileged writer. The result
   is `/etc/blaine/secrets/grafana-fleet.env`, `root:root 0600`, beneath a root-only
   0700 directory. The BWS bootstrap never reaches this file or systemd.

Materialization was performed and verified. The file is **not referenced by the
active Alloy unit**, and the Fleet fragment remains inactive. Therefore no secret
was loaded into the running collector and no enrollment is implied.

```sh
# Explicit operator maintenance/rotation, not a boot requirement:
python3 /usr/local/lib/blaine/grafana-cloud.py materialize-fleet
# Metadata only; never cat/source the file for diagnostics:
sudo stat -c '%U:%G %a %n' /etc/blaine/secrets/grafana-fleet.env
```

Future accepted activation can use the established systemd EnvironmentFile pattern
so boot/restart reads protected local material without Keyring/BWS/network login.
The current `activate-fleet` action explicitly refuses activation until the native
startup gate is resolved. The legacy interactive `bw` OTLP helper is retained for
compatibility; it is not the selected Fleet secret source or a new runtime login
dependency. Future telemetry credentials should extend this BWS path.

[Ansible staging](../infra/ansible/grafana-fleet.yml) installs only the reviewed
helper and [inactive native fragment](../infra/alloy/fleet.alloy.inactive). It does
not fetch secrets, activate/restart Alloy, modify its unit or change remote pipelines.
Scratch mode uses `/tmp/blaine-d1-fleet-*`; the real stage requires bounded host
maintenance privilege. Normal Alloy operation remains under user `alloy`, with
no sudo or open terminal. Temporary sudoers authorization was left untouched.

## Fleet and telemetry are separate

BWS contains the three Fleet keys, but no Grafana telemetry ingestion credentials.
The active collector has no Cloud exporter or Cloud activation marker. No separate
Prometheus/Loki exporters or redundant unified OTLP exporter were introduced.

Existing Grafana-generated remote defaults reference:

| Product | Destination | Product instance |
|---|---|---|
| Hosted Metrics | `https://prometheus-prod-40-prod-sa-east-1.grafana.net/api/prom/push` | `3602220` |
| Hosted Logs | `https://logs-prod-024.grafana.net/loki/api/v1/push` | `1796781` |
| Fleet Management | Fleet base URL above | `1838998` |

The metric/log defaults require `GCLOUD_RW_API_KEY`, which is not materialized.
They were inspected but **not changed or assigned**. Before enrollment, reconcile
these automatic matchers so Blaine does not inherit unintended exporters. The
proposed host-only exclusions were not applied after the startup STOP was found.
No Tempo/OTLP destination or trace ingestion credential was established. Do not
reuse the Fleet instance ID as a telemetry username or assume its token has write
scopes. The existing inactive unified OTLP fragment can remain the simple delivery
option once actual endpoint/username/scoped credentials are available and reviewed.

Later delivery acceptance needs independent backend readback of a unique metric,
log and trace. Local HTTP acceptance, exporter counters, Fleet API authentication
and configuration visibility are not substitutes. Dashboard collector-health
telemetry and remote alerting remain unaccepted. No Task-success monitor was added.

## Recovery and later D1.G

The active local file still exactly matches `infra/alloy/config.alloy`. Its protected
pre-test copy is `/etc/blaine/infra/alloy-pre-fleet.alloy`. No ongoing fallback
service is required because the unsafe remote block is not activated. Fleet can
be unreachable without affecting the restored local startup configuration.

The [D1.G procedure](platform-services.md#d1g--later-human-authorized-reboot-procedure)
retains the original object, MIRIX memory and WAITING Task identities. The fresh
[read-only D1 preservation check](../experiments/d1-grafana-fleet/evidence/d1-preserved.json)
passed; it did not replace the original baseline or execute a reboot. At the future
human-authorized reboot, verify local Alloy readiness and host telemetry. Fleet
reconnect is supporting evidence **only if separately accepted and activated by
then**; it must never gate Blaine correctness or mask a local recovery failure.

Official references: [native `remotecfg`](https://grafana.com/docs/alloy/latest/reference/config-blocks/remotecfg/),
[Collector API](https://grafana.com/docs/grafana-cloud/observe-and-act/send-data/fleet-management/api-reference/collector-api/),
[Pipeline API](https://grafana.com/docs/grafana-cloud/observe-and-act/send-data/fleet-management/api-reference/pipeline-api/).
