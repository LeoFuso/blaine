# D1 platform operations and recovery gates

**Fleet slice, 2026-09-21: activation STOPPED.** Native Alloy 1.19.2 registration
failure prevents offline initial startup. Local Alloy was restored and verified;
D1.A/B/C/D and all prepared D1.G identities remain accepted/unchanged. See the
[Fleet findings and BWS runbook](platform-grafana-cloud.md). No reboot occurred.

**2026-09-21:** infrastructure-only full-host reboot recovery is **PASS** for the
rootful foundation. [Rootless migration](platform-rootless-docker.md) is **PASS**;
user systemd + linger owns the stack and the legacy system owner is disabled. That runbook contains the
current operator topology, namespace storage rules, normal operations and rollback limits.
The historical backup instructions below remain paused. Rootless reboot and
full D1.G remain pending; no reboot is authorized by documenting these gates.

For current inference/MIRIX/Restate/Blaine operations, retained-state evidence,
known shutdown limits and the exact later reboot procedure, use the
[service operations runbook](platform-services.md). All five adopted units are
enabled; no manual terminal or root is needed for normal runtime operation.

Read the [current infrastructure foundation](platform-infrastructure.md),
[roadmap D1 gates](roadmap/001-blaine-development-roadmap.md#d1), and
[historical backup checkpoint](platform-d1.md) first. Commands below
are a runbook; recording them does not mean host deployment was executed.

**LIVE BACKUP ACCEPTANCE = PAUSED**. Keep `blaine-partial-backup.timer`
**disabled/inactive** (confirmed at checkpoint). Real systemd backup fails during
PostgreSQL identity switching; no live backup PASS or physical restore is claimed.
Offline tests and physical volume safeguards exist. SeaweedFS Object Storage is
now deployed, but complete PostgreSQL + Blaine Object Storage backup remains
unproven. Next D1 work is long-lived service adoption; backup remains paused.

All host mutation, backup, restore and reboot commands below are **future runbook
reference only**, suspended during this pause. Do not run them to close this
session. Resume backup in a later bounded pass before attempting live proof.

## Scope and backup contract

The durable Blaine brain is **PostgreSQL + S3-compatible object storage**.
Restate, Redis, ClickHouse and telemetry cannot be the only repository of
long-term knowledge. Restate's disk remains necessary for normal execution
recovery, but is not the brain's disaster-recovery source of truth.

The deployed SeaweedFS store is not covered by this backup implementation.
D1 provides an explicitly
named `partial-backup` of selected PostgreSQL databases and the **existing kernel
file artifact format**, not a generic copy of an imaginary S3 data directory.
Every manifest/status says `complete_durable_brain: false`. Setting the explicit
coverage value `postgresql-and-kernel-artifacts-only` accepts only that limited
scope. It cannot turn the result into S3 coverage. Keep the timer disabled until
physical destination and source coverage are accepted.

PostgreSQL strategy: native `pg_dump --format=custom --create` per explicitly selected
database, plus `pg_dumpall --globals-only --no-role-passwords`. This suits the
observed single-node PostgreSQL 18 installation and permits simple isolated
restore; no HA or PITR requirement was established for this bounded pass.
Database dumps retain ownership, ACLs, schema and extension declarations;
required extension binaries (including pgvector) must exist on the recovery
host. Role passwords are deliberately excluded and must be recovered/reissued
through the existing secret mechanism. Tablespace directories, server config,
extension packages and all other machine dependencies require separate review.
Do not treat a database dump as full machine reproduction.

Each database has its own consistent snapshot. Multiple database dumps and
artifact copies are **not an atomic cross-store snapshot**. Before using the
partial backup operationally, quiesce relevant writers at an approved boundary
and establish which roots/databases belong together; no shutdown hooks or task
lifecycle changes were invented. RPO is up to the daily interval after successful
accepted deployment; outage/backlog increases it. RTO is not measured.
See PostgreSQL's [backup guidance](https://www.postgresql.org/docs/18/backup.html)
and [global objects documentation](https://www.postgresql.org/docs/18/app-pg-dumpall.html).

Artifact strategy: preserve each selected root's label and `task_id/sha256` key
with exact bytes. Verify content against the filename hash. Reject unexpected
layouts, symlinks, special files and nested filesystems; a concurrent temporary
artifact file makes the operation fail safely. Current kernel metadata is in
the key/reference itself. This does **not** preserve S3 bucket policies,
versions/delete markers, tags, retention, encryption keys or implementation
metadata. Those must be covered by the actual implementation's export/restore
strategy before full brain acceptance. Redis cache/queue data and telemetry are
not swept into these snapshots.

## Fail-closed destination and retention

The example configuration now names the explicitly authorized UUID but has empty database/root selection and
`UNCONFIGURED` coverage. No executable live configuration is shipped.

Before any destination write, the script requires:

1. An existing absolute mount path without any symlink component.
2. `findmnt --mountpoint` identifying exactly that mount with the configured UUID.
3. A writable ext4 or XFS filesystem root, not a bind of a subdirectory.
4. A filesystem device different from `/`.
5. A directory descriptor pinned before and checked after validation. All backup
   writes are relative to that pinned directory; a detached mount cannot redirect
   the job to the underlying root-directory path.
6. An existing, same-filesystem `blaine` subtree, owned by the backup identity
   with private permissions. Its descriptor becomes the working directory before
   using `blaine-partial-backups`. No configurable relative paths or symlinks can
   redirect the operation into the historical tree.
7. A writable filesystem and available capacity for twice the selected database
   storage/artifact bytes plus `min_free_bytes` (default 1 GiB). The PostgreSQL
   estimate uses `pg_database_size` through the same local peer connection.
   Available capacity and the estimate enter status/manifest evidence. This is
   a conservative preflight estimate, not a reservation against concurrent writes.

An absent mount, blank/wrong UUID or unsafe path returns nonzero. The mount
directory itself is never created by the **backup** script or Ansible. Mount/fstab
preparation is a separate, explicitly authorized operator command below. Only local status/journal may be written when a disk
is absent; **no backup payload is written to the root filesystem as fallback**.
The physical missing-mount negative test passed in a private namespace; the
host mount stayed intact. Hot-detach and positive backup acceptance remain unproven. Plaintext local snapshots are mode 0700
under a 0077 umask; physical-access protection/encryption is an operator decision.

The owned `blaine/blaine-partial-backups/` namespace holds independent generations.
Default retention is the latest **7 verified generations**, configurable from
1–365. Chronology comes from creation timestamps, not random suffixes. A new
generation is published only after checksums, PostgreSQL archive-catalog checks
and filesystem flushes. Retention first validates every candidate; corruption
stops deletion. Foreign and `.incomplete-*` directories are never automatically
pruned. Failed attempts remain for explicit inspection/removal and may consume
space. Insufficient space produces failure, not deletion of last good backups.
No encryption, remote sync, cloud credentials or off-site destination is added.

## Authorized existing-volume preparation

The physical target is now the Samsung SSD 850 EVO 500GB, ext4 UUID
`2415dac3-9d47-470f-8e00-2766bfbb821e`. Device enumeration and labels are not
authority. Existing historical Linux backups must remain untouched. The stable
mount covers the filesystem root; only its new `blaine` subtree is managed.

The user already ran [prepare-volume.py](../infra/backup/prepare-volume.py) with
local sudo authentication. Preparation passed; do not rerun it during the pause.

It verifies one matching UUID and ext4, rejects conflicting mount/fstab entries,
mounts at `/srv/blaine-backup` with `noatime,nodev,nosuid,noexec`, and requires the
four expected historical directories. Before/after fingerprints cover all
historical entries except the dedicated `blaine` subtree, including regular
file bytes, inode/ownership/mode/timestamps, extended attributes and symlinks.
The filesystem root's metadata necessarily changes when adding the new subtree;
the historical entries must not. No history filename/content listing is printed.
Each pass reads the historical bytes and can take several minutes.

The persistent entry is:

```fstab
UUID=2415dac3-9d47-470f-8e00-2766bfbb821e /srv/blaine-backup ext4 nofail,noatime,nodev,nosuid,noexec,x-systemd.device-timeout=10s 0 0
```

No fsck/format/repair command is included. Existing fstab bytes are retained and
backed up locally before replacement; a conflicting entry causes STOP. The
script does not reload systemd or start services. Review pending manager drift
before deployment. `nofail` lets the host boot without the volume; the backup's
own guard still fails if it is absent. Its service orders after the generated
mount unit but does not implicitly mount a missing disk when invoked manually.

Preparation evidence is written to
`/var/lib/blaine-backup/volume-preparation.json`; the aggregate-only copy at
`/run/blaine-d1-volume-result.json` lets the interactive session inspect the result
without elevated access. Preparation PASS is not physical-backup PASS. The
subsequent acceptance must use actual source selection, produce/verify a
generation, restore that same generation in isolation, compare the historical
fingerprint again, and record capacity before/after the backup.

## Physical backup acceptance — PAUSED

The attempted runner is retained as [inert evidence](../infra/backup/paused/README.md),
not an executable acceptance entrypoint. The first attempt installed the scripts,
units and root-only `/etc/blaine/backup.json`. It selected all non-template local
PostgreSQL 18 databases and five explicit retained kernel artifact roots under
main's Increment 11 evidence: acceptance, live-authorized acceptance, projection
acceptance, revised acceptance and revised instrumentation counterexample. Those
five roots are not complete host artifact coverage or S3 coverage. Nothing is
claimed protected by a successful live generation yet.

The real private-namespace missing-mount test passed without changing the host
mount. Systemd backup then failed during PostgreSQL identity switching through
runuser; the synthetic database was handled by cleanup. The second attempt's
fixed SELECT 1 probes failed for both runuser (exit 1) and setpriv (exit 127),
reporting Operation not permitted. No physical generation or restore passed.
No new diagnostics or live experiments were run for the pause checkpoint.

The setpriv/public-cwd attempt was removed from maintained executable code and
preserved in a patch. The runner is archived as text and is not deployed by
Ansible. Maintained code uses the previous runuser path, whose live service
execution remains failing. **The installed host copy retains the attempted
variant**; no deployment/reconciliation occurs during the pause. Review that
drift before a future resumption, keeping the timer disabled/inactive until
successful physical backup and isolated restore acceptance.

Evidence: [volume preparation](../infra/volume-preparation-d1.json),
[first physical STOP](../infra/physical-first-attempt-d1.json),
[identity probe results](../infra/backup/paused/pg-probes.json).
`infra/validation-d1-physical.json` retains historical pre-acceptance test evidence;
its PENDING status and hashes are not the current acceptance result.

Remaining proof requires producing and verifying a physical generation, restoring
that exact generation into an isolated PostgreSQL cluster and artifact directory,
checking contents, and recording historical fingerprints/capacity before and
after. [restore-generation.py](../infra/backup/restore-generation.py) passed with
an ordinary-user scratch generation; its root path and live physical generation
remain unproven. No backup-success report may substitute offline proof for this.

## Ansible and local configuration

[host.yml](../infra/ansible/host.yml) is one play, with no role framework. It checks
native tools, creates four directories, and copies the reviewed script, example
configuration and two systemd files. It does not install or upgrade host packages,
adopt current services, create users, change Redis/PostgreSQL, reload systemd,
enable a timer or configure storage. Observed dependencies are versioned in
[versions.json](../infra/versions.json); this is not a fully locked installation.
Native package ownership is retained. Any future version upgrade needs its own
review and evidence.

Reproduce the verified scratch staging, using an available ansible-core 2.20.0:

```bash
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/host.yml --syntax-check
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/host.yml \
  -e blaine_prefix=/tmp/blaine-d1-stage
# Repeat: expected recap changed=0.
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/host.yml \
  -e blaine_prefix=/tmp/blaine-d1-stage
systemd-analyze verify infra/systemd/blaine-partial-backup.service \
  infra/systemd/blaine-partial-backup.timer
```

Observed scratch recaps: first `ok=6 changed=3 failed=0`; second
`ok=6 changed=0 failed=0`. Root ownership, systemd sandboxing and live service
behavior are not proven by scratch staging. `--check --diff` can review host
changes before an explicitly approved host apply:

```bash
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/host.yml \
  --become --ask-become-pass --check --diff
```

After the host deployment boundary is approved, apply the same command without
`--check --diff`. A human creates `/etc/blaine/backup.json` from the example with
root:root mode 0600, selected UUID, database allowlist and actual artifact roots.
This machine configuration stays outside Git. PostgreSQL uses local peer
authentication via the maintained runuser path (live execution failing); no new database password is required or copied.
Existing secrets remain in their local mechanisms. Do not paste configuration
values or raw database diagnostics into telemetry.

Review the already-pending PostgreSQL/Redis unit drift before an approved
`sudo systemctl daemon-reload`. The D1 play deliberately does not reload the
manager, because that would also apply those unrelated on-disk definitions.

## Backup now, status and verification

Future reference only: resume the bounded backup pass and reconcile installed
code before configuration, installation and mount acceptance:

```bash
sudo python3 /usr/local/lib/blaine/backup.py preflight
sudo systemctl start blaine-partial-backup.service
sudo systemctl status blaine-partial-backup.service --no-pager
sudo journalctl -u blaine-partial-backup.service -n 50 --no-pager
sudo python3 /usr/local/lib/blaine/backup.py status
sudo python3 /usr/local/lib/blaine/backup.py verify --generation "$GENERATION"
systemctl list-timers blaine-partial-backup.timer --no-pager
```

Timer activation is deferred until a later successful live acceptance. It must
remain disabled/inactive now. The configured schedule is daily at 03:30 in the host timezone, persistent for missed runs.
Systemd owns execution, timeout and process-group shutdown; `Restart=no` avoids
retry storms. PostgreSQL ordering is `After=postgresql@18-main.service`, not a
claim of readiness or permission to restart the database. A failed dependency
is exposed by the actual dump. No observability service is required.

`/var/lib/blaine-backup/status.json` records last operation/backup attempt, last
successful **partial** backup, generation, destination, result/failure reason,
and verification time/status. `status` computes age. Preflight/verify never
advance last successful backup. Lock contention fails without clobbering the
active operation. If killed by systemd or power loss, the record may remain
`running`; reconcile it with unit/journal state and check the incomplete
generation. Missing/unparseable configuration may be diagnosable only in journal.
Local evidence is sufficient; Grafana is not needed and never gains authority.

## Isolated restore proof

Run as an ordinary user with PostgreSQL 18 + pgvector available:

```bash
python3 -m unittest discover -s tests/platform -v
```

The fixture creates two private temporary clusters, separate socket directories,
no TCP listeners, and different bootstrap roles. It creates synthetic ACME SQL
data, a vector and a kernel artifact; dumps globals/database and copies the
object; restores into the second cluster; checks row, vector, original owner,
key/hash and exact binary content; confirms the source remains intact; tests
retention and intentional corruption; stops both clusters and cleans scratch
data. It uses the actual `ArtifactStore` and native PostgreSQL tools. It calls
the snapshot engine directly; the production CLI has **no test/mount bypass**.

The automated proof passed. It proves machinery on scratch storage, not the
HDD, S3, live source coverage or a production generation's recoverability.
Catalog/checksum verification alone never records a successful restore test.

To drill an accepted real generation later: copy only that trusted, verified
snapshot into a private scratch area; provision an isolated PostgreSQL 18
cluster with a distinct bootstrap superuser and required extensions/tablespace
paths; stop if any target points to live storage. Use its Unix socket exclusively:

```bash
# All variables must refer to the newly created isolated cluster/snapshot.
test -n "${SCRATCH_SOCKET:?}" && test -n "${SNAPSHOT:?}"
psql -X -h "$SCRATCH_SOCKET" -p 15432 -U d1restore -d postgres \
  -v ON_ERROR_STOP=1 -f "$SNAPSHOT/postgres/globals.sql"
pg_restore -h "$SCRATCH_SOCKET" -p 15432 -U d1restore \
  --create --exit-on-error -d postgres "$SNAPSHOT/postgres/${SOURCE_DATABASE:?}.dump"
```

Check agreed SQL invariants and `ArtifactStore.read()` for selected retained
references in a copied scratch artifact root. Record generation, checks and
outcomes separately from `status.json`; then shut down/delete only the scratch
cluster. Global SQL and dumps are trusted sensitive backup inputs, never fetched
from an untrusted source. Complete Object Storage restore remains unproven until the deployed storage
implementation and its metadata/version semantics are covered and verified.

## Future full D1.G / rootless reboot acceptance — separate authorization required

The pre-infrastructure reboot sketch is superseded by the [D1.G gate](roadmap/001-blaine-development-roadmap.md#d1).
Prepare a reviewed acceptance profile after actual service adoption, using current
unit names, durable paths, readiness endpoints and recovery procedures from the
infrastructure/service documentation. Do not assume proposed units or public ingress
exist. Private Daily Driver acceptance does not require Caddy.

Record a healthy baseline, deployment revisions, Restate registration, synthetic
Task state, semantic-memory evidence, a synthetic PostgreSQL row and a bounded
Object Storage object's hash. Review recovery readiness and explicitly record the
paused backup limitation before requesting a reboot window. This runbook neither
unpauses backup nor grants reboot authorization.

Only with **explicit human reboot authorization**, perform the controlled reboot.
Require a changed boot ID, required services returning under their owners, the same
Task remaining queryable/recoverable, memory and synthetic SQL/object evidence
intact, and inference readiness. Preserve failed-unit/log evidence. Do not hide a
service failure by starting a second terminal-owned runtime. Missing core service,
registration, state or artifact is STOP. Full-host acceptance remains pending.

## Remaining work after this session

Backup work is PAUSED, including identity-switch debugging, physical backup and
restore acceptance. No further authentication or host action is requested now.
The SSD is already prepared and its historical data preservation was verified
at preparation. A later bounded backup pass must reconcile attempted installed
code, establish successful service execution, and complete physical generation,
restore and final history/capacity evidence. S3-backed complete-brain protection
must now cover the deployed Blaine Object Storage as well as PostgreSQL.

The next D1 workstream focuses on Blaine, Restate, vLLM and MIRIX service ownership;
backup is not its blocker. Runtime/storage integration and reboot acceptance retain their
own boundaries. Cloud/off-site backup remains deferred. This checkpoint installs
nothing, changes no disks, performs no reboot and pushes nothing.
