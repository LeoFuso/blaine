# MIRIX carveout evidence

The [research report](../../docs/research/mirix-carveout.md) answers the memory
boundary, provider/Qwen, native PostgreSQL 18, and Knowledge Vault questions.
This directory contains research artifacts only. No service integration exists.

These artifacts cover the initial source-only phase. The report's
[live-validation checkpoint](../../docs/research/mirix-carveout.md#live-validation-checkpoint--2026-09-19)
records a subsequent local service/model run. The environment inspection and
prerequisite status below are historical; this directory does not contain raw
logs or a reproducible script for that later run.

## Source and reproducibility

- Upstream: `https://github.com/Mirix-AI/MIRIX`
- Branch at checkout: `main`
- Exact SHA: `8cb06a62bbb7c478beb33dd4f2815696a72df482`
- Checkout: `../mirix-upstream` relative to the Blaine repository root
- Observation date: 2026-09-19
- [Machine-readable source identity](source.json)
- [Central source-file hashes](source-files.sha256)
- [Environment inspection](environment.json)

The checkout was cloned as a sibling, inspected without changes, and is not
vendored. For a new checkout, clone upstream into a sibling workspace and check
out the exact SHA above; do not assume a later `main` reproduces these findings.

The [TaskSpec request](task-request.json) is an **unsubmitted draft**. No durable
Task binding was available; no Task ID or authoritative runtime state is implied
by these files.

## What actually ran

Read-only source searches, Git identity/status checks, native prerequisite
inspection, and the dependency-free [source probe](source_probe.py). Reproduce:

```sh
python3 experiments/mirix-carveout/source_probe.py ../mirix-upstream
```

Run this command from the Blaine repository root, or supply another checkout
path. Without an argument, the probe locates `mirix-upstream` beside Blaine.

The probe asserts the SHA, parses selected upstream files with Python's AST,
and executes narrow unchanged source fragments in isolated bindings. It does
not import the MIRIX package. Only annotation/decorator scaffolding is removed
when loading a function; inspected operation bodies are not rewritten. The
legacy fallback check binds its signature without executing its body.

It established:

- An explicit synthetic key and arbitrary local OpenAI `base_url` survive
  client-argument preparation.
- The identity resolver accepts caller-provided client/org IDs without an API
  key, while missing both identity methods gives 401.
- Both add handlers share preprocessing: role/string passes; the documented
  role/list-of-text-dictionaries shape raises `TypeError`.
- Conversational retrieval's guard and default topic conversion disagree on
  those input shapes.
- The modern factory includes an OpenRouter import whose module is absent.
- The agent's legacy fallback passes `user_id`, which the target function does
  not accept.
- SDK `add` has no `session_tag` parameter.

[Retained output](source-probe-results.json) records the assertions' observations.
This is source-fragment evidence, **not** an HTTP, provider, database, security
penetration, or end-to-end memory test. No real credentials were supplied.

## Native prerequisites for the proposed live portion

**Observed stop:** no `psql`, `postgres`, `pg_config`, `pg_isready`, or
`redis-server` on PATH; no standard PostgreSQL installation directories or
installed PostgreSQL/pgvector dpkg packages. This host has Python 3.14.4 and
Ubuntu 26.04.1. No database or model service was started. Nothing below was
installed or executed.

For a future disposable native probe, provide:

1. **Native PostgreSQL 18 server and client**, an initialized reachable cluster,
   a disposable database, and a role allowed to create its schema. The database
   role/credentials and database lifecycle belong to the operator; the probe
   must not reuse production data.
2. **Native pgvector built for PostgreSQL 18**, with `CREATE EXTENSION vector`
   completed in that database **before** MIRIX creates tables. MIRIX declares
   `vector(4096)` even when embedding generation is disabled. Upstream pgvector
   documents a native `postgresql-18-pgvector` package; use a maintained build,
   not MIRIX's old container example. Record `SELECT version()` and extension
   versions for the actual probe.
3. To reproduce the full upstream bootstrap, also make `uuid-ossp` and `pg_trgm`
   available and enable them. They are in upstream `init.sql`; no inspected
   active memory query demonstrated a hard dependency on their functions.
4. **An isolated Python environment with the pinned upstream server's Python
   dependencies.** Python 3.11 is the version in upstream's current backend
   build and is a conservative starting point. The declared project range is
   `>=3.10,<4.0`; this does not validate the dependency set on host Python 3.14.
   Core packages include SQLAlchemy, asyncpg, pgvector, FastAPI/Uvicorn,
   Pydantic, provider SDKs and embedding libraries. Use the full pinned upstream
   dependency declaration and retain the resolved versions. No dependency
   installation was attempted here. Keep installation/build/runtime writes
   outside the read-only upstream checkout.
5. **Pinned local Qwen serving endpoint** with working Chat Completions tool
   calls, plus a local embedding endpoint for the vector phase. Record model
   ID/weights, serving-engine version, parser/template, dimensions and context
   limits. A chat model is not automatically an embedding model.

Read-only native checks once these prerequisites exist:

```sql
SELECT version();
SHOW server_version_num;
SELECT name, default_version, installed_version
FROM pg_available_extensions
WHERE name IN ('vector', 'uuid-ossp', 'pg_trgm');
SELECT extname, extversion FROM pg_extension;
```

Configure `MIRIX_PG_URI` explicitly to that disposable native database (or all
five `MIRIX_PG_HOST`, `MIRIX_PG_PORT`, `MIRIX_PG_USER`, `MIRIX_PG_PASSWORD`,
`MIRIX_PG_DB` values); never rely on the default property to select PostgreSQL.
Supply credentials through local environment/configuration, not this artifact.

The intended small text probe uses native Uvicorn serving
`mirix.server.rest_api:app` on loopback, with `MIRIX_DIR` and image/log paths
pointing to disposable experiment data, `MIRIX_REDIS_ENABLED=false`,
`MIRIX_LANGFUSE_ENABLED=false`, and no configured telemetry export or cloud
provider credentials. Initial extraction sets `BUILD_EMBEDDINGS_FOR_MEMORY=false`
and explicitly chooses `search_method=bm25`. Redis/Kafka are not prerequisites
for the sync memory path. A later vector phase enables a known local embedding
model and repeats the round trip.

On startup, REST lifespan runs SQLAlchemy `create_all`, followed by a
missing-column check. It does **not** provision PostgreSQL, the database, the
role, or extensions. For an existing schema, inspect and apply only appropriate
upstream manual migrations; concurrent-index phase-2 files cannot run inside a
transaction. Do not use the legacy `mirix/server/startup.sh` Docker/Alembic path.

The concrete probe sequence and acceptance evidence are in the report. Live
work remains **not run**, pending native prerequisites and the separate decision
to conduct that experiment. No Blaine runtime, provider, secret store, or
generic Memory interface is implemented here.
