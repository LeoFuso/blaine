# D1 platform operations and recovery gates

Read the [D1 inventory and STOP boundaries](platform-d1.md) first. Commands below
are a runbook; recording them does not mean host deployment was executed.

## Scope and backup contract

The durable Blaine brain is **PostgreSQL + S3-compatible object storage**.
Restate, Redis, ClickHouse and telemetry cannot be the only repository of
long-term knowledge. Restate's disk remains necessary for normal execution
recovery, but is not the brain's disaster-recovery source of truth.

No S3 implementation is deployed or selected here. D1 provides an explicitly
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
the key/reference itself. This does **not** preserve future S3 bucket policies,
versions/delete markers, tags, retention, encryption keys or implementation
metadata. Those must be covered by the actual implementation's export/restore
strategy before full brain acceptance. Redis cache/queue data and telemetry are
not swept into these snapshots.

## Fail-closed destination and retention

The example configuration has an empty UUID, empty database/root selection and
`UNCONFIGURED` coverage. No executable live configuration is shipped.

Before any destination write, the script requires:

1. An existing absolute mount path without any symlink component.
2. `findmnt --mountpoint` identifying exactly that mount with the configured UUID.
3. A writable ext4 or XFS filesystem root, not a bind of a subdirectory.
4. A filesystem device different from `/`.
5. A directory descriptor pinned before and checked after validation. All backup
   writes are relative to that pinned directory; a detached mount cannot redirect
   the job to the underlying root-directory path.

An absent mount, blank/wrong UUID or unsafe path returns nonzero. The mount
directory itself is never created by the script or Ansible. No mount command or
fstab update is executed. Only local status/journal may be written when a disk
is absent; **no backup payload is written to the root filesystem as fallback**.
Actual mount/detach acceptance still requires the physical disk; simulated
identity tests are not physical proof. Plaintext local snapshots are mode 0700
under a 0077 umask; physical-access protection/encryption is an operator decision.

The owned `blaine-partial-backups/` namespace holds independent generations.
Default retention is the latest **7 verified generations**, configurable from
1–365. Chronology comes from creation timestamps, not random suffixes. A new
generation is published only after checksums, PostgreSQL archive-catalog checks
and filesystem flushes. Retention first validates every candidate; corruption
stops deletion. Foreign and `.incomplete-*` directories are never automatically
pruned. Failed attempts remain for explicit inspection/removal and may consume
space. Insufficient space produces failure, not deletion of last good backups.
No encryption, remote sync, cloud credentials or off-site destination is added.

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
authentication via runuser; no new database password is required or copied.
Existing secrets remain in their local mechanisms. Do not paste configuration
values or raw database diagnostics into telemetry.

Review the already-pending PostgreSQL/Redis unit drift before an approved
`sudo systemctl daemon-reload`. The D1 play deliberately does not reload the
manager, because that would also apply those unrelated on-disk definitions.

## Backup now, status and verification

Only after configuration, installation and mount acceptance:

```bash
sudo python3 /usr/local/lib/blaine/backup.py preflight
sudo systemctl start blaine-partial-backup.service
sudo systemctl status blaine-partial-backup.service --no-pager
sudo journalctl -u blaine-partial-backup.service -n 50 --no-pager
sudo python3 /usr/local/lib/blaine/backup.py status
sudo python3 /usr/local/lib/blaine/backup.py verify --generation "$GENERATION"
# After a successful manual backup AND isolated restore of that generation:
sudo systemctl enable --now blaine-partial-backup.timer
systemctl list-timers blaine-partial-backup.timer --no-pager
```

The timer is daily at 03:30 in the host timezone, persistent for missed runs.
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
from an untrusted source. S3 restore remains blocked until the actual storage
implementation and metadata/version semantics exist.

## Future reboot acceptance — not authorized or executed

This sequence is blocked on actual service adoption, S3 deployment, a verified
physical backup and an operator-approved reboot window. Do not reboot merely to
test the current inventory: Restate/Blaine/ingress are absent and model services
remain terminal-owned.

First write a local, reviewed acceptance profile under ignored
`machine-config/`: exact systemd unit names for Blaine, Restate, both inference
services, the object store and Caddy; expected loopback/ingress URLs; database
connection and S3 client configuration **paths**, not secrets in this repository.
Use the actual provider's supported S3 client after selection. No live S3 client
configuration or provider-specific command can honestly be supplied yet.

Before reboot, create a uniquely named synthetic row in a dedicated acceptance
database and a uniquely keyed synthetic object using that approved local S3
client. Record the SQL value, object SHA-256, service deployment revision and
boot ID in the local acceptance packet. Do not use a live business table. Back
up and restore-test these values using the accepted complete-brain mechanism.
The partial D1 mechanism alone cannot satisfy this gate.

With that local profile loaded, run the exact service/readiness checks:

```bash
test -n "${BLAINE_UNIT:?}" && test -n "${RESTATE_UNIT:?}"
test -n "${QWEN_UNIT:?}" && test -n "${EMBEDDING_UNIT:?}"
test -n "${OBJECT_UNIT:?}" && test -n "${CADDY_UNIT:?}"
systemctl is-enabled postgresql.service redis-server.service \
  "$RESTATE_UNIT" "$BLAINE_UNIT" "$QWEN_UNIT" "$EMBEDDING_UNIT" "$OBJECT_UNIT" "$CADDY_UNIT"
systemctl is-active postgresql@18-main.service redis-server.service \
  "$RESTATE_UNIT" "$BLAINE_UNIT" "$QWEN_UNIT" "$EMBEDDING_UNIT" "$OBJECT_UNIT" "$CADDY_UNIT"
pg_isready -h /var/run/postgresql -p 5432
redis-cli -h 127.0.0.1 PING
curl --fail --silent --show-error --max-time 10 "${RESTATE_ADMIN_URL:?}/deployments"
curl --fail --silent --show-error --max-time 10 "${BLAINE_READINESS_URL:?}"
curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8000/health
curl --fail --silent --show-error --max-time 10 http://127.0.0.1:8001/health
curl --fail --silent --show-error --max-time 10 "${INGRESS_READINESS_URL:?}"
cat /proc/sys/kernel/random/boot_id
```

Confirm Restate registration points at the accepted Blaine deployment, not just
an HTTP 200, and verify one bounded synthetic model call using the accepted model
profile. Record synthetic SQL/object values and backup freshness. Only then,
with **separate explicit reboot authorization**, the operator may execute
`sudo systemctl reboot`.

After reconnecting, run the same checks, require a different boot ID, read the
same SQL row and retrieve/hash the same S3 object, check one bounded inference
call, and inspect `systemctl --failed` and `journalctl -b -u UNIT` for each core
unit. A diagnostic telemetry outage alone does not fail core authority. Missing
core service, registration, state or object is STOP; do not start a duplicate
development supervisor to hide a boot failure. Preserve evidence and investigate
that unit before another reboot attempt. Entire-host acceptance is still pending.

## Smallest remaining human decisions

Identify/connect the intended HDD by physical model/serial and filesystem UUID;
review any existing contents without destructive operations. If preparation is
needed, approve the exact device and bounded operation separately before any
partitioning, formatting, repair or overwrite. D1 has not selected a candidate.
Then approve source inventory and the runtime/S3 service cutover, review systemd
drift, deploy/stage configuration, prove manual backup and isolated restore,
and finally authorize the reboot window. Cloud/off-site backup remains deferred.
