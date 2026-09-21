# D1 rootless Docker migration

**Migration acceptance: PASS, 2026-09-21. Rootless reboot acceptance: PENDING.**
Blaine now runs its four infrastructure containers under `leofuso`'s rootless
Docker and user `blaine-infra.service`. Both user services are enabled, linger
is enabled, and the legacy system owner is disabled/inactive. Normal operations
were verified in a fresh process without docker-group membership; access to the
rootful socket was denied. Existing login/user-manager processes can retain
cached supplemental groups until a new session or the later authorized reboot.

System Docker remains installed and running, **unused by Blaine**. Its four old
Blaine containers and one stopped hello-world container are retained. Nothing
requires disabling or uninstalling that daemon to close this migration.

**Infrastructure-foundation full-host reboot: PASS, 2026-09-21, rootful topology.**
The earlier boot ID changed from `55f6e9ad-7915-472d-aaf5-7c9d689c3747` to
`4e64cd04-43eb-45ef-b493-15fb67cc8072`, with automatic healthy recovery and zero
failed units. This migration performed no reboot. **D1.G remains incomplete**:
Blaine, Restate, vLLM and MIRIX live service/recovery adoption has since passed;
see [current services and D1.G evidence](platform-services.md). Backup remains PAUSED.

## Active topology and ownership

[ADR 0020](decisions/0020-rootless-docker-operator-runtime.md) records the decision.

```text
machine boot
├── native PostgreSQL 18, Redis, Alloy (system services)
└── user@1000.service (linger)
    ├── docker.service (rootless; /run/user/1000/docker.sock)
    └── blaine-infra.service (user; Compose project blaine-infra-rootless)
        ├── SeaweedFS        127.0.0.1:8333
        ├── ClickHouse      127.0.0.1:8123 / :9000
        ├── Langfuse Web    127.0.0.1:3000
        └── Langfuse Worker 127.0.0.1:3030
```

| Material | Location / ownership |
|---|---|
| Versioned desired state | `infra/compose/rootless.yaml`, `infra/systemd/user/blaine-infra.service`, Ansible |
| Runtime config | `~/.config/blaine/infra`, operator-owned 0700, files 0600 |
| Runtime secrets | `~/.config/blaine/secrets`, operator-owned 0700; files 0600, S3 config 0400 |
| SeaweedFS metadata/filer/volumes | `~/.local/share/blaine/infra/objects`, host UID/GID 1000, parent 0700 |
| ClickHouse data and logs | `~/.local/share/blaine/infra/clickhouse/{data,logs}`, host UID/GID 100100, parents 0700 |
| Docker image/container state | `~/.local/share/docker` |
| Retained legacy source | `/srv/blaine/infra`; ownership, links and data preserved |
| Protected host/rollback config | `/etc/blaine`, root:root 0700; original secret modes retained |
| Native data | Existing PostgreSQL, Redis and Alloy paths; no database/queue migration |

Observed namespace mapping: UID/GID 0 maps to host 1000; namespace 1..65536 maps
to host 100000..165535. SeaweedFS uses namespace UID 0 with all capabilities
dropped. It invokes `weed` directly with upstream mini/FIPS settings; the image
wrapper's chown/su-exec failed the initial scratch attempt. ClickHouse retains
namespace UID/GID 101, mapped to host 100100. Do not widen leaf permissions for
host-shell convenience. Never chown the legacy source to test compatibility.

Langfuse retains host networking and `HOSTNAME=127.0.0.1`. The installed Docker
29.8.1 rootless runtime empirically reaches native loopback dependencies. Recheck
this behavior on upgrades; do not assume it on another version. User systemd
cannot order directly against system-manager units: preflight checks dependency
TCP readiness, Compose waits for application health, and systemd bounds retries.
The later real reboot must still validate startup ordering.

Alloy includes separate journal sources restricted to UID 1000 and the two
rootless units; the service-adoption pass added the five exact Blaine user units. Collection counters and persisted log records passed. Alloy
was restarted once for that configuration; PostgreSQL and Redis kept their process
identities. No cloud exporter was activated. See the
[journal component contract](https://grafana.com/docs/alloy/latest/reference/components/loki/loki.source.journal/).

## Accepted evidence

- [Full isolated candidate](../experiments/d1-rootless-docker-adoption/evidence/full-candidate.json)
  and [automatic candidate Docker recovery](../experiments/d1-rootless-docker-adoption/evidence/candidate-docker-restart.json).
- [Offline copy fingerprints](../experiments/d1-rootless-docker-adoption/evidence/offline-copy.json):
  all bytes, modes, relative links and entry counts matched; mappings changed only
  on the new copy. Both source and copy were checked while the stores were stopped.
- [Cutover acceptance](../experiments/d1-rootless-docker-adoption/evidence/cutover-acceptance.json):
  all four containers healthy, seven original S3 objects, two original ClickHouse
  synthetic rows and the original Langfuse trace's two observations retained;
  new synthetic ingestion succeeded.
- [User stack restart](../experiments/d1-rootless-docker-adoption/evidence/rootless-stack-restart.json)
  and [Docker restart](../experiments/d1-rootless-docker-adoption/evidence/rootless-docker-restart.json):
  healthy recovery and retained identities; no manual Compose start hid failure.
- [Fresh identity without docker group](../experiments/d1-rootless-docker-adoption/evidence/operator-without-docker-group.json),
  [Alloy journal proof](../experiments/d1-rootless-docker-adoption/evidence/alloy-rootless-journal.json),
  [final host](../experiments/d1-rootless-docker-adoption/evidence/accepted-host.json),
  [protected-source/secret checks](../experiments/d1-rootless-docker-adoption/evidence/accepted-host-protected.json).
- [Validation](../experiments/d1-rootless-docker-adoption/evidence/validation.json),
  [current summary](../experiments/d1-rootless-docker-adoption/evidence/summary.json),
  [earlier reboot](../experiments/d1-infrastructure-reboot/evidence/result.txt).

The full candidate used alternate ports, separate copied secret files, fresh
SeaweedFS/ClickHouse state, native database `blaine_rootless_candidate_20260921`,
and a separate user Redis process on port 16379. It never consumed the live queue
or wrote the live database. Candidate containers and Redis are stopped; their
state and the isolated candidate database remain retained. No historical data was
deleted. The original STOP checkpoint and failed first storage attempt are preserved.

## Normal operation and convergence

```sh
systemctl --user status docker blaine-infra
systemctl --user restart blaine-infra
docker --context rootless ps
BLAINE_STATE_DIR="$HOME/.local/share/blaine/infra" \
BLAINE_SECRET_DIR="$HOME/.config/blaine/secrets" \
docker --context rootless compose -f "$HOME/.config/blaine/infra/compose.yaml" config --quiet
```

Keep the daemon explicit for Docker mutations. Never render live Compose config,
inspect container environment, or print raw credential-bearing logs. Langfuse
shutdown can consume its 60-second stop window; allow the user unit's bounded
stop/start timeouts to finish before diagnosing a restart as failed.

User convergence requires no sudo:

```sh
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/infrastructure.yml --syntax-check
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/infrastructure.yml \
  -e blaine_prefix=/tmp/blaine-d1-rootless-scratch
# The default stages files only. Activation on an accepted host is explicit:
ansible-playbook -i infra/ansible/inventory.ini infra/ansible/infrastructure.yml \
  -e blaine_activate=true
```

Activation requires `migration-accepted.json` with PASS and the legacy system
owner disabled/inactive. Scratch activation fails closed. The user play enables
Docker and the stack, validates secrets/Compose without rendering values, and
restarts the stack only when staged runtime files changed. Accepted user and host
second convergence runs both returned `changed=0`.

Bounded host administration uses the separate play:

```sh
sudo ansible-playbook -i infra/ansible/inventory.ini infra/ansible/rootless-host.yml \
  -e blaine_rootless_accepted=true
```

It checks prerequisites/linger and requires the active accepted four-container
rootless stack before disabling the old owner or removing only docker-group
membership. It restores private root-owned host config and pins the retained
rollback unit to `--context default`. Alloy convergence refuses unknown or
cloud-activated config rather than overwriting it. Merge future journal changes
into a cloud composition explicitly if that activation is later performed.

The guarded `infrastructure-rootful.yml` is legacy reference only. Do not replay
its bootstrap or the old rootful acceptance script against the migrated host.
Rootless setup on a new host still requires reviewed package installation,
subordinate IDs and `dockerd-rootless-setuptool.sh install` as the operator.
Existing rootless extras/uidmap versions are recorded in `infra/versions.json`.
No NOPASSWD or sudoers change is part of this operating model.

## Recovery and retained state

The original source is a pre-cutover snapshot. **It is now stale** because the
accepted rootless stack has processed new synthetic writes. Never simply restart
the legacy stack on that old copy: quiesce writers and reconcile all later S3,
ClickHouse, native PostgreSQL and Redis relationships first. Preserve both trees;
use a new offline copy with inverse namespace mapping and compare content before
an explicitly selected rollback. Stop for review if consistency cannot be proven.

For ordinary repair, prefer the accepted rootless user service and its current
state. Never start a second supervisor or stack to mask failed ownership. The
legacy daemon/package and stopped containers remain available for a considered
recovery, not for automatic operation. Backup remains PAUSED and no complete
PostgreSQL + Object Storage disaster-recovery proof is implied by migration copies.

## Remaining acceptance: separately authorized reboot

**No root-action handoff remains. The machine is ready for the rootless reboot
acceptance window, but no reboot has been authorized or performed by this work.**

Before an explicitly authorized reboot, refresh
[accepted state](../experiments/d1-rootless-docker-adoption/evidence/accepted-state.json)
if useful traffic has changed it, record the current boot ID, and verify:

```sh
cat /proc/sys/kernel/random/boot_id
loginctl show-user leofuso -p Linger
systemctl --user is-enabled docker blaine-infra
systemctl is-enabled blaine-infra       # expected disabled; exit 1 is normal
systemctl --user is-active docker blaine-infra
```

Only with separate explicit human authorization perform the host reboot. Afterward,
require a different boot ID, no manual service starts, active/enabled user units,
healthy native services, no rootful duplicate and a fresh session without the
rootful docker group. As the operator, verify the retained baseline:

```sh
uv run --no-project --python 3.13 --with boto3==1.42.70 python \
  infra/rootless/accept-running.py \
  --baseline experiments/d1-rootless-docker-adoption/evidence/accepted-state.json \
  --output experiments/d1-rootless-docker-adoption/evidence/rootless-reboot.json
```

Also record system/user unit states and both daemon inventories using bounded
sudo only for the legacy daemon. A later rootless reboot PASS is still narrower
than D1.G's pending Blaine/Restate/vLLM/MIRIX adoption. Do not resume inference,
unpause backup, delete retained candidate/source state, or push as part of reboot
acceptance without the corresponding authorization.
