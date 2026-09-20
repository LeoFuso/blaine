# D1 — Long-lived platform foundation: STOP

Observed 2026-09-20 on the Blaine host. This is an accepted bounded repository
foundation, **not Daily Driver acceptance**. No host service was installed,
reconfigured, restarted or enabled. No disk was mounted or modified. No reboot
or cloud backup was performed.

Direction follows [ADR 0018](decisions/0018-local-platform-durability-and-observability.md).
Its header still says “Proposed for acceptance”; the D1 user request explicitly
accepts the listed architectural direction. This pass does not reopen it. D1
specifically defers off-site backup and permits an evidence-based logical
PostgreSQL strategy; the broader ADR's WAL/PITR and off-site recommendations are
not implemented here.

## Baseline and execution boundary

Initial `pwd`: `/home/leofuso/workspace/blaine-platform-d1`; branch
`feature/platform-d1`; clean index/worktree. HEAD and local main both pointed to
`215a86c6366e4d4da9a53b29d6fd763d5fc02de7`, the accumulated Cognitive Kernel
evidence/STOP checkpoint, following `064e0bd` and `ef39182`. No D1-only changes
existed. `git worktree list` also identified main, cognitive-loop, personal-agent
and personal-agent-runtime worktrees. All were read-only during implementation.

Local main subsequently advanced to `f5727f7`, an offline Increment 11 diagnostic
and retained evidence, with no runtime-source edits. D1 does not continue that
increment. Integration is recorded by Git and the final report, not inferred
from this document.

[TaskSpec draft](../infra/task-request.json) follows `task-create`. No callable
Blaine creation binding was available and no Blaine Task was submitted or created.
The explicitly authorized repository pass ran interactively; this document is
not a shadow durable execution ledger.

## Current / target / gap

| Component | Observed current state | Intended state and remaining gap |
|---|---|---|
| Host | Ubuntu 26.04.1, Linux 7.0.0-31; systemd 259.5 | Retain native single-node host. Package/executable Python version discrepancy recorded in version inventory; no upgrades. |
| Blaine | Milestone 001/002 entrypoints and kernel experiments; no current listener or systemd unit | Need one accepted long-lived kernel entrypoint, stable release/data/config paths and deployment registration. Do not promote an experiment or old milestone as the platform. |
| Restate | 1.7.9 binary in main's `.local/bin`; evaluation TOML and development supervisor; no running listener | Versioned native service and persistent path after selecting deployment boundary. Never point a service at a disposable feature worktree. |
| PostgreSQL | Native 18/main, active on loopback 5432, user postgres; pgvector installed | Preserve package ownership. Identify databases/owners and approved backup scope using privileged metadata reads. Local role `leofuso` absent; noninteractive sudo unavailable. |
| Object storage | No S3 service/implementation found. Kernel `ArtifactStore` uses immutable `task_id/sha256` files | Select/deploy S3 implementation and migration boundary separately; actual bucket/version/metadata backup is pending. Local files are transitional protection, not S3 coverage. |
| Redis | Native 8.10.2, loopback 6379; RDB saves, no AOF, noeviction, maxmemory=0 | One existing profile; separate ephemeral vs durable profiles still needed. Do not duplicate or reconfigure the shared MIRIX dependency during D1 STOP. |
| vLLM | Two terminal-owned 0.29.1 development builds; 8000 Qwen/Qwen3.5-9B, 8001 BAAI/bge-m3; `/health` and `/v1/models` return 200 | Explicit service adoption must preserve model arguments, GPU allocation, environment and weights. Health observed, restart/reboot recovery unproven. |
| MIRIX | Terminal-owned API at loopback 8531, package 0.1.0, external checkout | Dependency discovered; no takeover of external checkout. Confirm revision/config and approved owner before supervision cutover. |
| Docker/Compose/Podman | No installed CLI, platform files, running owner or matching service discovered | No container-group mechanism to reuse or replace here. |
| Caddy | No current binary/unit/config/listener discovered | Await stable upstream endpoints and exposure/auth decisions. Do not create an ingress to absent applications. |
| ClickHouse / Langfuse / Alloy | No matching platform units/processes/deployment discovered | Deferred; no expansion into observability deployment. Existing ExecutionEvent and telemetry semantics untouched. |
| Backup | No backup mount, fstab entry or Blaine job discovered | Repository-only partial backup service/timer, native PostgreSQL + kernel artifacts. HDD and S3 acceptance blocked. |

Relevant versions are retained in [infra/versions.json](../infra/versions.json).
“Not discovered” reports bounded inspection, not a claim that private alternate
configurations cannot exist.

## Actual process ownership

| Process | Starts / restarts / ordering | Identity, paths, config, logs | Health / shutdown |
|---|---|---|---|
| PostgreSQL | Enabled `postgresql.service` groups `postgresql@18-main.service`; package cluster manager starts it. External Restart=no; postmaster handles backend failures. After network/local mounts. | Actual postgres user; `/var/lib/postgresql/18/main`; `/etc/postgresql/18/main`; `/var/log/postgresql/postgresql-18-main.log` + journal. | `pg_lsclusters`, `pg_isready`; pg_ctlcluster fast shutdown, 1h stop timeout. Group active/exited alone is not database health. |
| Redis | Enabled `redis-server.service`; package unit Restart=always; after network. | redis:redis; `/var/lib/redis`; `/etc/redis/redis.conf`; `/var/log/redis/redis-server.log` + journal. | `redis-cli PING`; SIGTERM, package TimeoutStopSec=infinity. Existing unlimited recovery semantics are documented, not silently altered. |
| Qwen vLLM | Human terminal; parent terminal scope, no dedicated service/restart ordering | leofuso; `/home/leofuso/workspace/vllm-lab/.venv`; cwd same project; CLI + uninspected environment; terminal logs. Port 8000, model length 32768, GPU fraction .80. | HTTP health 200; terminal/process signals; graceful timeout/boot recovery not established. |
| Embedding vLLM | Separate human terminal; same ownership gap | Same project/user; port 8001, model length 8192, GPU fraction .10; terminal logs. | HTTP health 200; same unproven shutdown boundary. |
| MIRIX | Human terminal (`scripts/start_server.py`), no dedicated service | leofuso; `/home/leofuso/workspace/mirix`; external venv; local config/environment not read for secrets; terminal logs. | Listener observed at 8531; semantic health and shutdown timeout not established. |
| Evaluation Restate/Blaine | `scripts/dev.py` starts detached children, records PID + kernel identity, no boot/restart manager; older direct shell entrypoints also exist | Invoking user, repository cwd; `.local/002` logs/PID files and evaluation config/data. No live process at inventory. | Existing script probes deployments/TCP with bounded timeout; SIGTERM then bounded SIGKILL. Evaluation only. |
| D1 partial backup (prepared) | systemd oneshot + daily persistent timer, **not installed or enabled**; After native PostgreSQL cluster, no automatic mount or service start, no retries | root, 0077; `/etc/blaine/backup.json`; `/var/lib/blaine-backup`; journal. runuser uses existing PostgreSQL peer auth. | Script guard + checksums/catalog; 2h job bound, 30s stop then group termination. Actual host execution unproven. |

Read-only `systemctl cat` reported PostgreSQL and Redis unit files changed on
disk relative to the loaded manager. A global daemon reload may apply unrelated
changes. D1 therefore does not even schedule an automatic reload in Ansible.
This drift must be reviewed before deployment.

Systemd owns **process/service lifecycle**. Restate owns **Task/workflow
lifecycle**. The backup timer schedules an operational job, not a second Task
runtime. There is no new Blaine platform target claiming absent services are up.
Desired boot ordering is local filesystems → native stores → Restate/application
and inference → ingress, with real readiness checks at each boundary. Telemetry
is independent and cannot block core startup. No arbitrary startup sleeps or
blanket one-unit-per-technology scaffold was added.

## Physical storage discovery

`lsblk`/filesystem metadata, `findmnt`, `df` and `/etc/fstab` were inspected.
The table records filesystem identities, **not permission to use them**.

| Device at observation | Hardware / filesystem identity | Mount / decision |
|---|---|---|
| sda, sda1 | Samsung SSD 850 EVO 500GB, 465.8 GiB, ROTA=0; ext4 UUID `2415dac3-9d47-470f-8e00-2766bfbb821e` | Unmounted; existing filesystem/data disposition unknown. Not an identified HDD. |
| sdb, sdb1 / sdb2 | Samsung SSD 860 EVO 1TB, 931.5 GiB, ROTA=0; NTFS UUIDs `2CE06B02E06AD19E`, `77C3A6753AEF78AE` | Unmounted; existing filesystems, contents not inspected. Not an identified HDD. |
| nvme0n1 | PNY CS3140 8TB SSD, ROTA=0 | Primary multi-partition disk; never selected for backup. |
| nvme0n1p5 | ext4 `e27c0914-140f-4409-ba48-93e18783eafd` | Root; about 117 GiB used, 1.3 TiB available at observation. |
| nvme0n1p1 | vfat `F2B2-3A87` | EFI, not backup. |
| nvme0n1p3 / p4 | NTFS `AE7C3B657C3B280B`, `F000A11600A0E4B6` | Existing unmounted filesystems; p2 reserved. |

No physically attached HDD can be uniquely identified. `/srv` is empty; fstab
contains only root, EFI and swap. `/srv/blaine-backup` is a configurable proposed
convention, not a created or mounted destination. No `/dev/sdX` selection,
partition probing for contents, filesystem repair, format or wipe occurred.

## Acceptance classification

**IMPLEMENTED AND VERIFIED**: inventory and ownership; strict missing-mount and
identity rejection; PostgreSQL/custom-format plus actual kernel artifact fixture
backup/restore; corruption detection; bounded retention; disabled unit syntax;
Ansible scratch convergence. See [validation](../infra/validation-d1.json).

**IMPLEMENTED BUT REQUIRES LIVE-HOST PROOF**: physical mount positive path and
hot detach behavior; root/runuser access to selected live databases/artifacts;
host Ansible ownership/modes; systemd sandbox, timer/failure journal and timeout
behavior; actual backup capacity/duration; restore of a real selected snapshot.

**DOCUMENTED / DEFERRED**: native application/Restate/vLLM/MIRIX adoption; Redis
profiles; S3 deployment, metadata/version preservation and complete-brain
restore; Caddy; observability deployment; PITR; off-site/cloud protection;
authorized physical-disk preparation and reboot acceptance.

**UNKNOWN**: which HDD the user intends and why it is not visible; existing
unmounted filesystem contents; live database names/owners; complete artifact
root selection; exact model weight and MIRIX deployment revisions; behavior of
the whole platform across reboot.

**STOP boundaries**: uniquely identify the HDD and decide existing-data handling;
select the real S3 and long-lived runtime deployment boundaries; review service
cutovers and pending systemd configuration drift. Ordinary implementation and
isolated validation are complete for this slice. The [operations guide](platform-operations.md)
contains the reviewable next actions. No machine readiness claim is made.
