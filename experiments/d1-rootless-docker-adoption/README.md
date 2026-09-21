# D1 rootless Docker adoption checkpoint — 2026-09-21

**STOP at sudo authentication; no cutover.** Rootful Blaine remains healthy and
required. Rootless Docker, native-loopback networking and isolated storage
compatibility pass; full Langfuse candidate and migration acceptance remain open.

The user explicitly authorized local implementation, host inspection, isolated
validation and commits using the retained [migration specification](task-specification.md).
The [TaskSpec](task-request.json) is an **unsubmitted draft** because no Blaine
creation binding was available; these files are deliverable/evidence records,
not an alternate durable Task ledger.

Read [the current runbook and exact root actions](../../docs/platform-rootless-docker.md),
[ADR 0020](../../docs/decisions/0020-rootless-docker-operator-runtime.md),
[summary](evidence/summary.json), and [validation](evidence/validation.json).

The pre-existing root:docker experiment is preserved as a patch in evidence and
superseded in desired state. Original reboot evidence is retained in the adjacent
`d1-infrastructure-reboot` experiment and supports **rootful foundation reboot PASS**,
not rootless reboot recovery or full D1.G. ADR 0019 and its commit are preserved.

The first storage attempt failed because SeaweedFS's wrapper tried chown/su-exec
under dropped capabilities. The corrected direct binary invocation preserves
upstream mini flags/FIPS setting without widening permissions; the passing second
attempt retained S3 bytes and a ClickHouse row across Compose restart and automatic
rootless Docker restart recovery. Both state directories and private fixture
secrets remain outside Git; final candidate containers are stopped.

No live secret, source-state copy, native database change, source ownership change,
rootful service stop, linger change, group cleanup, reboot, push, backup resume or
inference work occurred. Source secret metadata beneath the protected ancestor
remains unavailable until the documented bounded root action is run.

Original reboot captures and the pre-existing patch are byte-preserved using the
repository's per-file whitespace attributes. New command logs normalize trailing
whitespace only; validation outcomes are unchanged.
