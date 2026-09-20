# D1 infrastructure foundation

Infrastructure acceptance **PASS**: all four containers and native Alloy are healthy;
Docker, stack and Alloy restarts retained synthetic state. See the
[credential-free evidence](../infra/validation-d1-infrastructure.json).
This is the infrastructure slice of D1, following the user-directed backup pause.
It does not change Cognitive Kernel semantics or continue Increments 11/12.
The explicit D1 request selects a small systemd-owned Compose stack over the ADR's
earlier Podman packaging preference. The accepted architecture remains systemd process ownership, Restate Task ownership,
and PostgreSQL + S3-compatible storage as Blaine's durable brain. ExecutionEvent
remains semantic forensic evidence. Observability is never runtime authority.

## Selected implementations and compatibility

Selection checked against current official sources on 2026-09-20:

| Component | Selected version | Reason / compatibility |
|---|---|---|
| Docker Engine / CLI | 29.8.1 | Official Ubuntu resolute apt packages, no Desktop or convenience installer |
| Compose plugin | 5.5.1 | Official Docker apt package; sudo administration, no group/login prerequisite |
| containerd / Buildx | 2.3.5 / 0.37.1 | Explicit official package pins |
| SeaweedFS | 4.47 | Apache-2.0, maintained release dated September 14, single-process `weed mini` |
| ClickHouse | 26.4.5.143 | Langfuse v4 requires >=25.12 and recommends 26.4; single-node, UTC |
| Langfuse Web / Worker | 4.38.0 | Matching release pair; upstream schema/migrations unchanged |
| PostgreSQL | existing 18.6 | Reused native cluster; dedicated database/role `blaine_langfuse`, UTC per database |
| Redis | existing 8.10.2 | Reused native instance; DB 15 and `blaine-langfuse` prefix, existing noeviction/RDB |
| Alloy | 1.19.2 | Official Grafana apt package and package service identity |
| Bitwarden CLI | 2026.9.0 | Official binary, published SHA256 checked; operator-local executable |

[Docker's Ubuntu installation](https://docs.docker.com/engine/install/ubuntu/),
[Langfuse ClickHouse requirements](https://langfuse.com/self-hosting/deployment/infrastructure/clickhouse),
[Langfuse release Compose](https://github.com/langfuse/langfuse/blob/v4.38.0/docker-compose.yml),
[Alloy package installation](https://grafana.com/docs/alloy/latest/set-up/install/linux/).

A bounded object-store comparison favored SeaweedFS:

| Candidate | Assessment |
|---|---|
| SeaweedFS | Maintained Apache-2.0 project; broad S3 API and `weed mini` designed for one node. One image/process contains metadata, volume, filer and S3. Disable unused WebDAV, Admin UI, Iceberg and Lance listeners. Only S3 is published. Selected. |
| Garage | Lightweight self-contained AGPLv3 implementation; valid alternative, but oriented toward multi-zone replication and has a documented narrower S3 surface. Extra layout/key management provides little benefit here. |
| MinIO community | Upstream repository archived; does not meet this pass's active-maintenance requirement. Not selected despite historical Langfuse examples. |
| RustFS | Active Apache-2.0 alternative. SeaweedFS provides an established single-node path and the required S3 surface without introducing a newer store for Blaine's authoritative artifacts. |

Sources: [SeaweedFS release](https://github.com/seaweedfs/seaweedfs/releases/tag/4.47),
[mini deployment](https://github.com/seaweedfs/seaweedfs/wiki/Quick-Start-with-weed-mini),
[Garage](https://garagehq.deuxfleurs.fr/),
[Garage S3 compatibility](https://garagehq.deuxfleurs.fr/documentation/reference-manual/s3-compatibility/),
[MinIO upstream](https://github.com/minio/minio), [RustFS upstream](https://github.com/rustfs/rustfs).
This is a local packaging choice, not a distributed-cluster design. Langfuse's
single-container ClickHouse deployment has community support, not its managed-cloud
support guarantees; D1 accepts the explicitly requested single-node topology.

## Service ownership and network

```text
systemd
├── docker.service → containerd
├── blaine-infra.service → Compose project blaine-infra
│   ├── object-storage (SeaweedFS)
│   ├── clickhouse
│   ├── langfuse-web
│   └── langfuse-worker
├── alloy.service (native package, alloy user)
├── postgresql@18-main.service (existing native)
└── redis-server.service (existing native)
```

The Compose owner starts after Docker and native dependencies, waits for container
health, stops gracefully, and participates in controlled Docker restarts via
`PartOf=docker.service`. Container `unless-stopped` policies handle process exits.
No unit in this deployment becomes a dependency of Task correctness.

| Component | Host address | Persistent data/config |
|---|---|---|
| Object Storage | 127.0.0.1:8333 | `/srv/blaine/infra/objects` (all mini metadata, filer and volumes) |
| ClickHouse | 127.0.0.1:8123 HTTP, :9000 native | `/srv/blaine/infra/clickhouse/data`, `/srv/blaine/infra/clickhouse/logs` |
| Langfuse Web | 127.0.0.1:3000 | PostgreSQL metadata, Redis queues/cache, ClickHouse observations, S3 events/media |
| Langfuse Worker | 127.0.0.1:3030 | Same dependencies; no unique container-local durable data |
| Alloy | 127.0.0.1:12345 HTTP, :4317 OTLP gRPC, :4318 OTLP HTTP | `/etc/alloy/config.alloy`, `/etc/default/alloy`, `/var/lib/alloy/data`, `/var/lib/alloy/telemetry` |
| PostgreSQL | 127.0.0.1:5432 | existing `/var/lib/postgresql/18/main`, `/etc/postgresql/18/main` |
| Redis | 127.0.0.1/[::1]:6379 | existing `/var/lib/redis`, `/etc/redis/redis.conf` |
| Compose | no listener | `/etc/blaine/infra/compose.yaml`; systemd unit `/etc/systemd/system/blaine-infra.service` |
| Docker | local Unix socket | `/var/lib/docker`, `/var/lib/containerd`; infrastructure data uses explicit bind mounts |

Langfuse uses host networking with upstream-supported `HOSTNAME=127.0.0.1`, avoiding
changes to native database exposure. Storage containers use a private Docker bridge
and only loopback host ports. There are no anonymous volumes for retained data.
The root filesystem supplies the new state paths; the Samsung backup filesystem
is not used. Docker's normal bridge rules were installed; no broad firewall redesign.

Buckets are `blaine-artifacts`, `langfuse-events`, and `langfuse-media`. Independent
Blaine and Langfuse keys have bucket-scoped permissions; a separate provisioning key
creates buckets. A future backup must consistently capture **PostgreSQL + Blaine
Object Storage**, including SeaweedFS metadata and volume data together. Copying
only volume blobs is not a complete object-store backup. Backup implementation and
physical acceptance remain paused for their own bounded pass.

## Secrets and local telemetry

Actual secrets live only under `/etc/blaine/secrets` (root directory 0700):
`infrastructure.json`, `langfuse.env`, `clickhouse.env` are 0600; the mounted
`object-storage.json` is 0400 for the image's UID 1000 behind the root-only parent.
The SeaweedFS data leaf is also UID 1000; ClickHouse uses its upstream UID 101.
No keys are committed or printed by normal diagnostics. `docker inspect` without
field selection, rendered Compose configuration, and raw container logs can expose
credentials; use health-only commands and the sanitized acceptance artifact.

Alloy runs as package user `alloy`, with supplemental `systemd-journal` and umask
0077. State/telemetry directories are 0700. It collects selected host metrics,
self-metrics, allowlisted Docker/infra/Alloy journal units, and loopback OTLP.
Journal bodies remain potentially sensitive local diagnostics, not unrestricted
labels. No application/personal cognitive traffic was connected.

Local OTLP JSON files rotate at 20 MiB with three backups and three-day retention.
This is a bounded diagnostic baseline, not a query backend or backup. The file
exporter is explicitly `public-preview` in Alloy 1.19.2; that stability flag is
captured in the package environment. Remote export is absent from active config.

Grafana Cloud is **CONFIGURED FOR FUTURE ACTIVATION**, not connected. The
[activation runbook](platform-grafana-cloud.md) covers account setup, scoped token,
Bitwarden placeholders, operator materialization, activation and delivery checks.
Missing cloud values never affect the local collector. No cloud model call occurs.

## Reproducible deployment and acceptance

`infra/bootstrap-packages.py` installs explicit official apt package versions. It
refuses conflicting runtimes and unowned existing Docker data; it does not remove
packages, upgrade the host, change groups, or reboot. `infra/ansible/infrastructure.yml`
captures package intent, directories, Compose, systemd, Alloy and operator scripts.
The prior backup play remains separate and unchanged.

```sh
sudo python3 infra/bootstrap-packages.py
sudo ansible-playbook -i infra/ansible/inventory.ini infra/ansible/infrastructure.yml
sudo python3 /usr/local/lib/blaine/infrastructure-secrets.py
sudo docker compose -f /etc/blaine/infra/compose.yaml pull --quiet
sudo systemctl daemon-reload
# Use a Python environment containing boto3; see versions/evidence for acceptance tools.
sudo /path/to/validation-python infra/accept-infrastructure.py
sudo ansible-playbook -i infra/ansible/inventory.ini infra/ansible/infrastructure.yml -e blaine_activate=true
```

Review native unit drift before a daemon reload. First-time acceptance starts stores,
creates isolated buckets and synthetic state, starts the systemd stack and Alloy,
then verifies Langfuse v4 OTLP ingestion via the v2 Observations API. It restarts the
stack, Docker and Alloy and reads the persistent synthetic state again. It refuses
a Docker restart if unrelated running containers are present. It never invokes the
physical backup script, deletes backup data, calls models, or reboots.

Safe offline convergence:

```sh
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/infrastructure.yml --syntax-check
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/infrastructure.yml -e blaine_prefix=/tmp/blaine-d1-infra-scratch
# Repeat: expected changed=0.
python3 -m unittest discover -s tests/platform -v
```

The existing PostgreSQL test fixtures need permission to create local Unix sockets;
run those tests outside a sandbox denying sockets. They do not touch live PostgreSQL
or the physical backup volume. Systemd and container health alone are insufficient:
the retained acceptance artifact must show synthetic persistence and roundtrip checks.

## Remaining boundaries

Backup remains **PAUSED**: known Samsung volume and historical contents preserved,
fail-closed safeguards retained, no accepted physical PostgreSQL generation/restore,
and the earlier PostgreSQL/systemd execution failure deferred. The timer stays
disabled/inactive. This is not an infrastructure blocker.

Full-machine reboot recovery is **PENDING**. Cloud/off-site backup, full recovery,
public ingress, extensive dashboards and real cognitive instrumentation are deferred.
Blaine/Restate still need an accepted stable long-lived deployment; terminal-owned
vLLM and MIRIX were not adopted or restarted. Redis's separate ephemeral/durable
profiles and stronger queue recovery remain future work. These are Daily Driver
gaps beyond this infrastructure acceptance slice.

Seventeen platform tests pass; scratch Ansible converges to changed=0 and both
final live applies report changed=0. Compose, Alloy (local and inactive cloud) and
systemd validation pass. The Langfuse synthetic trace/generation roundtrip proves
its PostgreSQL authentication, Redis queue processing, S3 persistence and ClickHouse
query path. Local Alloy evidence includes host/self metrics, journal records and
synthetic metrics/logs/traces. Native PostgreSQL and Redis retained their original
process IDs throughout this slice. No Blaine Task creation binding was available;
the updated TaskSpec remains a draft, not a submitted runtime Task.

## Temporary privilege cleanup

`/etc/sudoers.d/90-blaine-d1-codex` was removed at finalization. Host `visudo -c`
passed before and after removal. `sudo -K` succeeded; the subsequent `sudo -n true`
failed with exit 1 (interactive authentication required). No replacement sudoers
rule was created. The running platform does not depend on this temporary privilege.
The implementation commit is `48b077d`, integrated into local main by fast-forward;
final cleanup evidence is recorded in the subsequent Git commit. No push occurred.

**PASS applies to this infrastructure slice.** Grafana Cloud remains configured
for future activation; backup remains paused, reboot recovery pending, and the
Daily Driver ownership gaps listed above remain open.
