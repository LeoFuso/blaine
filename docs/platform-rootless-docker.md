# D1 rootless Docker migration

**Migration: STOP at bounded sudo authentication. Rootful Blaine remains active.**
Basic rootless Docker and the synthetic storage-only candidate **PASS**; that
evidence is separate from full candidate acceptance. No full candidate, data migration or cutover is claimed.
Linger is currently **no**, and `leofuso` remains in the rootful docker group.
The installed rootful daemon and old stack are still required by Blaine.

**Infrastructure-foundation full-host reboot: PASS, 2026-09-21.** The recorded
boot ID changed from `55f6e9ad-7915-472d-aaf5-7c9d689c3747` to
`4e64cd04-43eb-45ef-b493-15fb67cc8072`. Docker, the infrastructure owner, Alloy,
PostgreSQL and Redis recovered automatically with zero failed units and healthy
containers. This is rootful foundation evidence, not rootless reboot evidence.
**D1.G remains incomplete**: Blaine, Restate, vLLM and MIRIX adoption is pending.

## Decisions and files

[ADR 0020](decisions/0020-rootless-docker-operator-runtime.md) selects the normal
operator's rootless daemon, user systemd and linger. ADR 0019 remains unchanged;
inference work and backup remain paused.

| Component | Desired ownership/location | Current migration state |
|---|---|---|
| Docker | `leofuso`, `/run/user/1000/docker.sock`, user `docker.service` | Already installed, enabled, active; rootless security verified |
| Compose | `~/.config/blaine/infra/compose.yaml` | [rootless template](../infra/compose/rootless.yaml); staged, inactive |
| Secrets | `~/.config/blaine/secrets`, 0700; files 0600/0400 | Empty staged destination; root copy pending |
| SeaweedFS | `~/.local/share/blaine/infra/objects`, namespace UID 0 | Scratch tested; live source unchanged |
| ClickHouse | `~/.local/share/blaine/infra/clickhouse/{data,logs}`, namespace UID 101 | Scratch tested; live source unchanged |
| Stack owner | user `blaine-infra.service` | Staged, disabled; requires cutover marker |
| Native services | system PostgreSQL, Redis, Alloy | Active; unchanged |
| Legacy stack | system `blaine-infra.service`, `/srv/blaine/infra` | Healthy and active; rollback source not migrated |

The mapped ClickHouse leaves are private to host UID 100100. Do not chmod them
to make the operator's host shell traverse them. Use explicit rootless container
operations with the correct namespace identity when inspection is necessary.
Only the two empty scratch leaves were chowned during compatibility testing.

## Evidence and reproducible staging

- [Sanitized preflight](../experiments/d1-rootless-docker-adoption/evidence/preflight.json)
- [Storage compatibility](../experiments/d1-rootless-docker-adoption/evidence/storage-candidate.json)
- [Reboot evidence](../experiments/d1-infrastructure-reboot/evidence/result.txt)
- [Migration summary](../experiments/d1-rootless-docker-adoption/evidence/summary.json)
- [Validation record](../experiments/d1-rootless-docker-adoption/evidence/validation.json)

`infra/ansible/infrastructure.yml` now stages user-owned rootless files as the
operator. It rejects `blaine_activate=true`; convergence is not cutover permission.
The former play is retained as `infrastructure-rootful.yml`, refuses live use by
default, and never grants docker-group membership. It is rollback/reference
material, not the current operating model. Native Alloy desired config remains
versioned under `infra/alloy`; migration staging intentionally does not reconfigure
working native services. Host backup staging remains separate and unexecuted.

```sh
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/infrastructure.yml --syntax-check
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/infrastructure.yml \
  -e blaine_prefix=/tmp/blaine-d1-rootless-scratch
# Repeat the same scratch command: changed=0 expected.
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/infrastructure.yml
```

Do not run that user play with sudo. `rootless-host.yml` records prerequisite
package/subordinate-ID checks and linger enablement for bounded host provisioning.
It does not alter sudoers, add group access, stop a daemon, or perform cutover.

The [storage probe](../infra/rootless/accept-storage.py) uses existing image versions,
a distinct project, ports 18333/18123/19000, private synthetic secrets and new state.
It writes and re-reads an S3 object and a ClickHouse row across Compose restart
and automatic Docker restart recovery. It retains stopped containers and data. The initial SeaweedFS wrapper failed its
ownership/privilege switch; the corrected direct binary invocation passed without
adding capabilities or widening permissions. Both attempts are retained in evidence.
It refuses to restart Docker when any rootless container is already running.
This is **not Langfuse or original-data migration acceptance**.

## Exact next root actions

`sudo -n true` failed. The migration specification forbids interactive prompting by
the agent and requires an exact handoff. Run these in a normal interactive terminal
from the inspected repository checkout:

```sh
cd /home/leofuso/workspace/blaine
sudo /usr/bin/python3 infra/rootless/bootstrap-secrets.py \
  > experiments/d1-rootless-docker-adoption/evidence/root-bootstrap.json
sudo loginctl enable-linger leofuso
loginctl show-user leofuso -p Linger
```

The first command inventories protected source ownership/modes without printing
names or contents of stored objects; it copies exactly four secrets into the
operator's 0700 secret directory after dropping root for destination writes.
It preserves source files and modes, refuses conflicting destination files, and
prints only sanitized metadata. It performs no database change, source-data copy,
service stop or cutover. The second enables user-manager boot persistence.
Review [the exact helper](../infra/rootless/bootstrap-secrets.py) before running.
These commands remove the current blocker; they do **not** complete migration.
Resume the migration after them so actual source inventory can determine the next
coherent copy and native candidate-isolation steps. No recurring sudo grant needed.

## Remaining candidate and cutover gates

1. Observe root-bootstrap output and verify destination secret ownership/modes.
   Recheck all actual mounts, effective image UIDs/GIDs, namespace maps and source
   symlinks. Full privileged source metadata was unavailable at this checkpoint.
2. Prepare an isolated Langfuse database and Redis instance/namespace with no live
   worker queue consumption. Preserve SALT/ENCRYPTION_KEY and other identities in
   the final migration. The candidate env file must reference candidate S3 and
   ClickHouse ports and isolated native dependencies; merely changing web ports
   does not isolate a Langfuse candidate. Retain all three bucket access scopes.
3. Prove all four healthy containers, native dependency access, S3 bytes and scoped
   permissions, ClickHouse rows, and a real synthetic Langfuse ingestion roundtrip.
   Confirm candidate responses originate from candidate processes on alternate
   ports. If any acceptance fails, stop and leave rootful healthy.
4. Capture live object keys/hashes, ClickHouse synthetic rows, Langfuse project/trace
   identities and database relationships. Inventory writers, then deliberately
   quiesce them and stop only rootful Blaine using its system owner. Copy all
   SeaweedFS metadata/filer/volumes and ClickHouse state while stopped. Preserve
   source state and native database/Redis relationships. Apply mappings only to
   copied data and verify the copies; never destructively chown `/srv`.
5. Materialize final config/secrets and the cutover marker only after full candidate
   PASS. At the bounded cutover, reload user systemd and start the rootless stack.
   Validate all old identities/content and ingestion; exercise the user stack and
   Docker restarts. Verify no rootful duplicate is providing the responses.
6. Only after rootless acceptance, disable the old system owner and enable the new
   user owner. Record both states. Remove just `leofuso`'s docker-group membership
   (`sudo gpasswd -d leofuso docker`), preserving all other groups. Old sessions may
   retain the supplemental group until a new login; prove operations from a fresh
   session without it. Restore `/etc/blaine` host config to root-owned private
   access at that boundary, without changing secret permissions.
7. Keep system Docker installed. A fresh inventory must decide whether unrelated
   running or stopped workloads exist before any daemon disablement; no such
   disablement has been performed. Ensure the old Blaine unit cannot start a
   duplicate stack. Keep a documented rollback route.

Normal operations after accepted cutover:

```sh
systemctl --user status docker blaine-infra
docker --context rootless ps
BLAINE_STATE_DIR="$HOME/.local/share/blaine/infra" \
BLAINE_SECRET_DIR="$HOME/.config/blaine/secrets" \
docker --context rootless compose -f "$HOME/.config/blaine/infra/compose.yaml" config --quiet
```

Before every Docker mutation, verify the explicit context endpoint and rootless
security options. Never render live Compose config or inspect container environment.
The legacy unit in Git pins `--context default`; it has not been replaced on host.

## Rollback and next reboot

Before accepting new writes, stop the rootless owner, remove its activation marker,
keep the new copies, and restart the preserved rootful owner. Never run both final
stacks on the same ports. After rootless accepts new writes, the source is stale:
quiesce and reconcile data before rollback; do not discard intervening writes.

**A new reboot still needs separate explicit human authorization.** The machine is
not yet ready for rootless reboot acceptance because migration is stopped before
full candidate/cutover. After all gates pass, record the boot ID, enabled linger
and user units, disabled legacy owner, all health and retained identities. Only
then request a reboot window. After the authorized reboot, require a new boot ID,
automatic user daemon/stack startup without manual starts, healthy native services,
identical retained S3 bytes/ClickHouse rows/Langfuse records and no duplicate owner.
Report rootless reboot PASS separately from the remaining full D1.G service gates.
