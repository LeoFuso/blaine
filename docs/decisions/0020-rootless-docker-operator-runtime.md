# ADR 0020 — Rootless Docker for the Blaine operator runtime

Date: 2026-09-21

Decision status: **Accepted**. Validation status: **Partially Validated**.

Integration/migration acceptance **PASS, 2026-09-21**: isolated full candidate,
byte-verified offline copy, retained source identities, Langfuse ingestion, user
stack/Docker restarts, operator access without the rootful docker group and
idempotent desired-state convergence passed. Rootless boot recovery still awaits
an explicitly authorized reboot; it is not inferred from the earlier rootful reboot.

## Context and decision

The healthy D1 foundation runs under system Docker and a system Compose unit.
Adding `leofuso` to the rootful `docker` group and making non-secret config
`root:docker` was considered and tried. Access to that daemon is root-equivalent;
it is rejected as the long-lived operator model. The original uncommitted change
is retained as migration evidence, not as the new desired state.

Use Docker rootless as `leofuso`, managed by `systemctl --user`. Enable linger
for boot-time user-manager ownership. Root remains necessary for bounded package,
native-service, protected-source migration and account administration. Normal
container operations use the rootless socket without sudo or docker-group access.
No sudoers change, NOPASSWD grant, package removal, or reboot is part of adoption.

Systemd remains the supervisor; Compose describes the four-container deployment.
PostgreSQL, Redis and Alloy remain native system services. Restate remains the
owner of durable Tasks. This narrows ADR 0018's packaging/operating assumptions;
its durability and observability boundaries remain in force. ADR 0019 is unchanged.

## Desired state and security

Versioned config is materialized under `~/.config/blaine/infra`; secrets live in
`~/.config/blaine/secrets` (0700, files 0600 or 0400, operator-owned). Keep secrets
out of Git and rendered Compose output. `/etc/blaine` remains protected host or
legacy rollback material, with no docker-group permission dependency.

New persistent state is under `~/.local/share/blaine/infra`. Never repurpose or
recursively chown the live `/srv/blaine/infra` tree. Current mapping is namespace
UID/GID 0 → host 1000; namespace 1..65536 → host 100000..165535. SeaweedFS runs as
namespace UID 0 with all capabilities dropped, so its private config and data
remain operator-owned. Invoke `/usr/bin/weed -logtostderr=true` directly, preserving
`GODEBUG=fips140=on`: the image wrapper attempts recursive chown and `su-exec`
when namespace UID is 0, which fails under dropped capabilities. The failed first
scratch attempt is retained; no extra capabilities were added. ClickHouse retains namespace UID/GID 101 → host 100100.
Recheck both maps on every host; these numbers are observations, not portable IDs.

The installed Docker 29.8.1 rootless host-network probe reached native loopback
PostgreSQL and Redis. Retain Langfuse's `HOSTNAME=127.0.0.1` host networking on this
verified runtime. Storage publishes only localhost ports. Re-probe after Docker
upgrades; do not infer compatibility on older versions or change native database
exposure to compensate for a failed probe.

User units cannot order against system-manager PostgreSQL/Redis units. The user
stack preflight probes native dependency TCP readiness, Compose waits for application
health, and systemd retries failed starts within a bounded start limit. A later
real boot must prove this ordering. Staging installs no cutover marker and does
not start or enable the stack. Linger is a separate host bootstrap action.

## Migration and rollback

Prove a distinct candidate on alternate ports and separate storage before stopping
the rootful owner. Full Langfuse validation must use isolated PostgreSQL and Redis
state as well as S3 and ClickHouse; sharing a live queue or database would invalidate
the isolation. Storage-only synthetic tests are insufficient for cutover.

After full candidate PASS, quiesce writers, stop only the rootful Blaine stack,
copy complete state coherently and map ownership on the copies. Preserve native
database/queue relationships and capture object identities, byte hashes and
ClickHouse synthetic rows before/after. Do not copy a running store and call it
consistent. Retain the stopped source, legacy config and explicit default-context
unit. Disable the old owner only after rootless acceptance, then remove docker
group membership without affecting other supplemental groups.

Before new writes, rollback can stop the rootless stack and restart the preserved
rootful owner. After new writes, the old copy is stale: quiesce and reconcile those
writes or stop for an explicit recovery decision. Never silently discard them.
Leave system Docker installed; disabling its daemon requires a fresh inventory of
all workloads and accepted rollback. An observed stopped hello-world container
does not authorize deleting it.

## Validation

Hypothesis: all four services can preserve data and private network behavior under
user systemd ownership, without rootful Docker access during normal operation.

Level: integration, followed by a separately authorized real reboot.

Minimum proof: rootless security options/socket; private secret metadata; image
users and namespace maps; S3 identity/content and scoped access; ClickHouse rows;
Langfuse Web/Worker health and synthetic ingestion roundtrip; native dependency
health; automatic recovery after controlled Docker and stack restarts; no rootful
duplicate; linger and enablement; later changed boot ID with no manual starts.

See [migration evidence and current limitations](../platform-rootless-docker.md).
The prior infrastructure-only reboot is PASS for the **rootful** topology. It
does not prove rootless reboot recovery or D1.G.

Reconsider when networking cannot preserve private native dependencies, namespace
storage cannot retain identities with a reversible copy, or automatic user-manager
startup fails acceptance. Stop rather than widening secret permissions, exposing
native databases, granting rootful daemon access, or transforming live ownership.

Backup remains PAUSED. Qwen/inference adoption and ADR 0019 implementation remain
outside this migration. No inference benchmark or public ingress is required.

References: [Docker rootless operation](https://docs.docker.com/engine/security/rootless/tips/),
[Docker rootless limitations](https://docs.docker.com/engine/security/rootless/troubleshoot/).
