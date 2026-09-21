# D1 rootless Docker adoption — 2026-09-21

**Migration PASS. Rootless reboot acceptance PENDING.** The four-container stack
runs under operator rootless Docker and enabled user systemd, with linger. The
rootful owner is disabled/inactive; system Docker remains installed and unused.
Seven original S3 objects, two ClickHouse synthetic rows and the original Langfuse
trace's two observations survived cutover and controlled restarts. New ingestion,
fresh operator access without the docker group, and rootless Alloy journals pass.

Read [the runbook and separate reboot gate](../../docs/platform-rootless-docker.md),
[ADR 0020](../../docs/decisions/0020-rootless-docker-operator-runtime.md),
[current summary](evidence/summary.json), [validation](evidence/validation.json),
[accepted host](evidence/accepted-host.json), and [reboot baseline](evidence/accepted-state.json).
Original source and all candidate data remain retained. Backup stays PAUSED;
ADR 0019 is preserved and inference work has not resumed. No reboot or push occurred.

The user authorized local implementation, bounded host administration, isolated
validation and commits using the retained [migration specification](task-specification.md).
The [TaskSpec](task-request.json) is an **unsubmitted draft**, because no Blaine
creation binding was available. These are deliverable/evidence records, not a
separate durable Task ledger.

## Earlier checkpoint and resumption

Commit `15c6551` stopped at missing noninteractive sudo. Its
[STOP summary](evidence/summary-before-resume.json) and `final-host.json` describe
that earlier checkpoint, not the accepted final state. The user then ran the
bounded root bootstrap and enabled linger. `root-bootstrap.json` records sanitized
source inventory/private materialization; `resumed-preflight.json` records verified
resumption, with working bounded sudo.

The initial storage attempt failed because SeaweedFS's wrapper tried chown/su-exec
under dropped capabilities. The corrected direct binary invocation preserved
upstream mini flags/FIPS behavior without extra capabilities or broader permissions.
Both attempts are retained. The full candidate subsequently passed against isolated
native PostgreSQL and Redis, ports and storage before the rootful project was stopped.

`offline-copy.json` proves unchanged source bytes/modes/relative links and matching
copied trees. Only destination ownership was mapped. `cutover-acceptance.json`,
`rootless-stack-restart.json` and `rootless-docker-restart.json` retain application
identity/health proof. `operator-without-docker-group.json` proves a fresh UID 1000
identity can operate the stack while the legacy socket denies access. Existing
login sessions may retain cached supplemental groups until a new session/reboot.

The pre-existing root:docker permission experiment is preserved as a patch and
superseded in desired state. Original reboot evidence in the adjacent
`d1-infrastructure-reboot` experiment proves **rootful foundation reboot PASS**,
not rootless boot or full D1.G. Original captures and that patch are byte-preserved
using per-file whitespace attributes. New command logs normalize trailing whitespace.
