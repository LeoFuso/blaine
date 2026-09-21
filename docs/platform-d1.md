# D1 — Long-lived platform foundation

**Current: D1 IN PROGRESS. D1.A/B/C/D live service adoption PASS; rootless
migration PASS; D1.G host reboot PENDING; backup PAUSED.**

See the [accepted service topology, exact versions, state paths and D1.G procedure](platform-services.md),
[infrastructure foundation](platform-infrastructure.md), and
[rootless migration](platform-rootless-docker.md). Preserved ADR 0019 records the
accepted 131072-token, one-generation inference configuration.

## Ready at login — configured and live-tested; host reboot pending

The linger-enabled user manager owns rootless Docker, infrastructure, generation,
embeddings, MIRIX, Restate and the actual Blaine runtime. All seven user units are
enabled. Native PostgreSQL, Redis and Alloy retain automatic startup. Readiness,
controlled restarts, the same semantic memory and durable Tasks, explicit Task
resume and a preserved human WAITING state passed. A real cognitive Task recalled
MIRIX content and produced independently verified evidence.

This is the configured ready-at-login topology. Automatic recovery across a host
reboot remains unproven until the separately authorized D1.G procedure runs.
Hypercorn needed systemd's bounded termination during the controlled stop; state
recovery passed, but graceful shutdown is not claimed. Current ArtifactStore
remains the actual local immutable store, alongside independently verified object
storage; no nonexistent S3 runtime adapter is implied.

[Persistent synthetic identities and read-only post-reboot verifier](platform-services.md#d1g--later-human-authorized-reboot-procedure)
are ready. No reboot, push, backup unpause or timer enable occurred in this pass.
The following backup material is historical and does not override this status.

## Historical backup checkpoint (pause still active)

The following inventory and “next” statements describe the earlier backup slice,
before infrastructure bring-up. They do not override current infrastructure evidence
or the roadmap. Historical permission records are not standing authorization.

**LIVE BACKUP ACCEPTANCE = PAUSED** — user-directed checkpoint, 2026-09-20.
Backup investigation and live acceptance are paused for a later bounded pass.
The next D1 workstream focuses on missing infrastructure; backup is not its
blocker. No infrastructure installation is started by this checkpoint.

The design and offline tests exist. Physical disk safeguards were exercised,
but real systemd backup execution fails during PostgreSQL identity switching.
There is no accepted physical backup generation or live restore result. Complete
durable-brain backup was also incomplete because Object Storage was then absent.
Object Storage has since been deployed; its backup remains unproven.
The backup timer is confirmed **disabled and inactive** and must remain so.
This is **not Daily Driver acceptance**.

## Resumed physical-volume slice

The user subsequently identified and authorized the **Samsung SSD 850 EVO 500GB**,
ext4 UUID `2415dac3-9d47-470f-8e00-2766bfbb821e`. It replaces the unidentified-HDD
boundary for this slice. The user reports about 458 GiB usable, 419 GiB free and
16 GiB of valuable historical Linux backups; these capacity/content figures are
user-supplied until privileged inspection succeeds. Preserve existing `home`,
`inventory`, `shell`, `system` and all other historical entries exactly.

Only `/blaine` on that filesystem is authorized for Blaine writes. Existing D1
generations move conceptually beneath it as
`/srv/blaine-backup/blaine/blaine-partial-backups`; no existing on-disk D1
generation has been moved. Mounting, persistent UUID configuration and bounded
partial backup/restore are authorized; formatting, filesystem repair, historical
deletion, repartitioning and UUID changes remain forbidden.

At resume, D1 was clean at `5ad9309` and was fast-forwarded to current main
`9563e2b` before edits. The disk was observed unmounted and fstab unchanged.
The root command `sudo -n true` failed with interactive authentication required.
The user then ran the bounded preparation command with local authentication.
Volume preparation **passed**: the authorized UUID is mounted read/write with
`noatime,nosuid,nodev,noexec`, its UUID-based fstab entry is installed, and the
private `blaine` subtree exists. [Preparation evidence](../infra/volume-preparation-d1.json)
records 353,132 unchanged historical entries and 15,436,679,146 regular-file
bytes. Their before/after fingerprint is identical. Capacity is 491,106,508,800
bytes, with 449,654,718,464 bytes available before subtree creation and
449,654,714,368 afterward (4 KiB used). These are now host-observed values.

The first physical attempt installed the partial backup scripts, units and local
configuration, and passed the missing-mount negative test in a private namespace.
It failed at PostgreSQL identity switching before producing a generation.
[Attempt evidence](../infra/physical-first-attempt-d1.json) records STOP.
The synthetic database was handled by the runner's cleanup. A second attempt's
controlled probes failed for both runuser and setpriv; it did not reach backup.

The speculative setpriv/public-working-directory change and its runner are
[preserved as inert evidence](../infra/backup/paused/README.md), not promoted as a
proven implementation. Maintained code retains the original runuser path, still
unproven in this service. The installed host copy retains the attempted variant;
this checkpoint does not deploy/reconcile it, restart services or modify disks.
No final physical backup capacity/fingerprint or physical restore proof exists.

The reviewed [volume preparation command](../infra/backup/prepare-volume.py)
checks UUID/type/mount conflicts, mounts with `noatime`, fingerprints all
historical regular bytes and metadata, creates only the `blaine` subtree, checks
the fingerprint again, and adds a nonconflicting persistent fstab entry. It
records only aggregate history evidence. This prepares the volume; it does not
claim a physical backup or restore has occurred. The backup implementation now
requires that subtree and checks a reserve plus estimated source size before
generation writes. S3 and broader platform gaps below remain unchanged.

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

## Initial inventory / target / gap

This inventory describes the initial D1 observation. The resumed-volume and
paused status above supersede its backup observations; other components were
not reinspected during this pause.

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
| Backup (updated) | Authorized SSD mounted; partial scripts/units installed; service failed; timer disabled/inactive | LIVE BACKUP ACCEPTANCE = PAUSED. PostgreSQL + five selected kernel artifact roots are intended partial coverage; no accepted live generation. S3 absent. |

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
| D1 partial backup (prepared) | systemd oneshot + daily persistent timer, installed, **timer disabled/inactive**; After native PostgreSQL cluster and backup mount; no implicit mount, no retries | root, 0077; `/etc/blaine/backup.json`; `/var/lib/blaine-backup`; journal. Local peer auth intended; maintained runuser and attempted installed setpriv both failed identity probes. | Script guard + checksums/catalog; 2h job bound, 30s stop then group termination. Live execution failed; acceptance paused. |

Initial read-only `systemctl cat` reported PostgreSQL and Redis unit files changed on
disk relative to the loaded manager. A global daemon reload may apply unrelated
changes. D1 therefore does not even schedule an automatic reload in Ansible.
The prior authenticated acceptance compared PostgreSQL/Redis process and
execution settings across its reload without restarting either service. This
pause performs no reload; future deployment must review drift again.

Systemd owns **process/service lifecycle**. Restate owns **Task/workflow
lifecycle**. The backup timer schedules an operational job, not a second Task
runtime. There is no new Blaine platform target claiming absent services are up.
Desired boot ordering is local filesystems → native stores → Restate/application
and inference → ingress, with real readiness checks at each boundary. Telemetry
is independent and cannot block core startup. No arbitrary startup sleeps or
blanket one-unit-per-technology scaffold was added.

## Initial physical storage discovery (historical)

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

At initial discovery no HDD had been selected. The user subsequently selected
and authorized the existing sda1 SSD by UUID, preserving its historical contents.
Preparation and capacity evidence above supersede the initial mount status.
Other filesystems were not selected or changed.

## Acceptance classification

**IMPLEMENTED AND VERIFIED**: offline subtree/UUID/root-filesystem/space guards,
PostgreSQL/custom-format and kernel artifact fixture backup/restore, retention,
corruption detection, same-generation scratch restore, unit validation and Ansible
scratch convergence. Physical volume preparation preserved all 353,132 historical
entries with identical full fingerprints; the real private-namespace missing-mount
test failed closed. See [pause validation](../infra/validation-d1-paused.json).

**IMPLEMENTED BUT REQUIRES LIVE-HOST PROOF**: a successful systemd backup,
verification and isolated restore of that physical generation, final backup
capacity/history evidence, and root service identity. These are PAUSED. The
installed attempted variant needs review/reconciliation before resumption.

**DOCUMENTED / DEFERRED**: missing long-lived Blaine/Restate/inference service
ownership, Redis profiles, S3 deployment and complete-brain backup, Caddy and
observability, PITR, cloud/off-site protection and reboot acceptance. Missing
infrastructure is the next D1 workstream; no installation occurs in this pass.

**UNKNOWN**: cause of the service identity-switch failure (not investigated
further); complete artifact source coverage; whole-platform reboot behavior.
No successful live protection or Daily Driver readiness is claimed.

**STOP**: backup paused at the user's direction. No more identity/PAM/service
investigation, physical backup/restore, disk operations or new infrastructure
installation in this session. The [runbook](platform-operations.md) records future
acceptance gates without authorizing their execution during this pause.
