# MIRIX carveout: independent memory service

Research evidence, not an architecture decision. Investigated 2026-09-19.

**Answer: MIRIX has a usable architectural seam for an external agent to submit
and retrieve memory without adopting its Chat Agent. This path is now validated
locally with native PostgreSQL 18 + pgvector, Redis, Qwen3.5-9B served by vLLM,
and BGE-M3 served by a second vLLM instance. Core, episodic, and semantic memory
writes survived process boundaries and were retrieved by a fresh client process.
MIRIX remains unsuitable as Blaine's credential store or durable execution
authority, and memory formation must be treated as fallible derived state rather
than authoritative truth.**

The obstacles are concrete: incomplete public configuration operations,
message conversion defects, inconsistent authorization/scope enforcement,
unencrypted Knowledge Vault values, and service-internal asynchronous work whose
acceptance is not evidence of completed memory writes. None requires making
MIRIX the owner of Blaine's identity or durable execution. They do prevent
calling the full intended deployment validated or production-ready.

## Evidence and scope

- **OBSERVED** means inspected source at the pinned revision or an explicitly
  identified probe result. The live-validation checkpoint distinguishes its
  integration observations from the initial source-only results.
- **INFERRED** means a conclusion drawn from those observations.
- **UNVERIFIED** means a behavior needing execution or evidence not obtained here.

Upstream: `https://github.com/Mirix-AI/MIRIX`, branch `main` at checkout.
**Exact SHA: `8cb06a62bbb7c478beb33dd4f2815696a72df482`**, commit dated 2026-08-20,
subject `Merge pull request #139 from Mirix-AI/feat/adaptive-session-tag-routing`.
The checkout is `../mirix-upstream` relative to the Blaine repository root,
outside Blaine and unmodified. Findings concern that SHA; upstream package metadata still says
`0.1.0`, so a release number such as “v0.1.6+” is not the evidence identifier.
All MIRIX source links below are commit-pinned; issue/PR status is dated separately.

Read first: `AGENTS.md`, `BLAINE.md`, ADRs 0001–0017 and decision conventions,
and [the Multica carveout](multica-carveout.md). The relevant constraints are
durable Task ownership, replaceable harnesses, explicit evidence, controlled
inference/egress, and no premature common interface. Restate remains the
intended durable runtime. Graphify remains a separate project/code knowledge
evaluation. MIRIX's own memory agents may be implementation details of its
memory capability; they gain no Blaine lifecycle authority.

Retained materials: [experiment and native prerequisites][experiment],
[source manifest][manifest], [isolated probe][probe], [probe results][results].
The [environment inspection][environment] records the missing native prerequisites.
The [TaskSpec request][task] is **unsubmitted**: no authoritative Task creation
binding was exposed. No runtime Task ID or runtime completion state is claimed.
The user-authorized investigation was performed in this workspace.

The initial source-review phase did not invoke MIRIX, PostgreSQL, Redis, or a
model. A subsequent local validation phase did. Native PostgreSQL 18.6 with
pgvector 0.8.6, Redis 8.10.2, MIRIX, Qwen3.5-9B via vLLM, and BGE-M3 via vLLM
were exercised together on the Blaine workstation. No Docker deployment,
Restate integration, Graphify integration, Goose integration, or cloud inference
was required for that validation.


## Live validation checkpoint — 2026-09-19

The source review was followed by a real local integration probe. Unless noted
otherwise, the observations in this section are empirical.

The files under `experiments/mirix-carveout/` retain the initial source-only
phase. This checkpoint records the subsequent run as a narrative; separate raw
request/response logs and a reproducible live-probe script are not included in
this repository update. Publishing this checkpoint did not rerun the services.

### Runtime used

- Ubuntu 26.04.1 LTS on the Blaine workstation.
- Native PostgreSQL 18.6 with pgvector 0.8.6.
- Redis 8.10.2 with Search/ReJSON support.
- MIRIX on `127.0.0.1:8531`.
- Qwen3.5-9B served by vLLM on `127.0.0.1:8000`.
- BGE-M3 served by a second vLLM process on `127.0.0.1:8001`.
- BGE-M3 returned 1024-dimensional embeddings through its
  OpenAI-compatible `/v1/embeddings` endpoint.

The Qwen server successfully handled ordinary chat, JSON-schema-constrained
output, tool calling, MIRIX Meta Agent routing, and child memory-agent tool
execution.

For the validated LLM path MIRIX uses:

```yaml
model: Qwen/Qwen3.5-9B
model_endpoint_type: openai
model_endpoint: http://127.0.0.1:8000/v1
api_key: EMPTY
context_window: 32768
```

No provider implementation change was required for this Qwen/vLLM path.

### Local embeddings

The working embedding configuration is:

```yaml
embedding_model: BAAI/bge-m3
embedding_endpoint_type: hugging-face
embedding_endpoint: http://127.0.0.1:8001/v1
embedding_dim: 1024
api_key: EMPTY
```

The `hugging-face` name is misleading in this revision. That branch constructs
MIRIX's generic `EmbeddingEndpoint`, which posts the configured model name to
`<base_url>/embeddings`. It therefore works with vLLM's OpenAI-compatible
embedding endpoint.

The `openai` embedding branch is materially different: it constructs
LlamaIndex `OpenAIEmbedding`. With the original code it selected
`text-embedding-ada-002`. A temporary experiment passing
`model=config.embedding_model` instead caused LlamaIndex to reject
`BAAI/bge-m3` because it is not a member of `OpenAIEmbeddingModelType`.

That temporary patch was reverted. The existing `hugging-face` /
`EmbeddingEndpoint` branch is the working generic OpenAI-compatible route for
this local BGE-M3 server.

A direct MIRIX adapter probe produced a 1024-dimensional embedding:

```text
MIRIX EmbeddingConfig
  -> EmbeddingEndpoint
  -> vLLM /v1/embeddings
  -> BGE-M3
  -> 1024-dimensional vector
```

### Persistent Meta Agent configuration

`MirixClient.initialize_meta_agent()` defaults to:

```python
update_agents=False
```

The server reuses the existing Meta Agent for the client.

Supplying new configuration while leaving `update_agents=False` did not update
the already-persisted child-agent embedding configuration. This was observed
when an episodic-memory write continued to use the old LlamaIndex/OpenAI path
and requested `text-embedding-ada-002`.

Reinitializing with:

```python
update_agents=True
```

updated the existing hierarchy rather than creating a new Meta Agent. The same
persistent Meta Agent identity was retained while the child agents began using
BGE-M3.

This gives the useful operational distinction:

```text
update_agents=False
  -> attach/create-if-absent behavior
  -> preserve persisted configuration

update_agents=True
  -> retain Meta Agent identity
  -> evolve persisted hierarchy configuration
```

### End-to-end persistent memory result

A conversation stating that Leonardo configured BGE-M3 as Blaine's local
embedding model and that the model produces 1024-dimensional embeddings was
processed by the local Qwen-backed Meta Agent.

MIRIX persisted both episodic and semantic memory.

A later Python process created a fresh `MirixClient`, reattached to the
persistent Meta Agent, and retrieved:

```text
episodic.total_count = 1
semantic.total_count = 1
```

The episodic entry retained the configuration event and date. The semantic
entry retained the BGE-M3 model and 1024-dimensional embedding fact.

The selected path is therefore validated:

```text
conversation
  -> local Qwen3.5-9B / vLLM
  -> MIRIX Meta Agent
  -> memory child agents
  -> local BGE-M3 / vLLM
  -> PostgreSQL / pgvector persistence
  -> original client process exits
  -> fresh MirixClient
  -> persisted memory retrieval
```

Core memory persistence was independently validated across a fresh client
process as well.

The episodic result appeared under `recent`, while `relevant` was empty for the
specific retrieval request. This validates durable episodic storage/retrieval,
but does not by itself prove successful episodic vector-relevance ranking for
that query.

### Memory-quality and completion findings

The live run exposed several concerns relevant to Blaine.

1. The Meta Agent routed ordinary BGE-M3 configuration information to Knowledge
   Vault. A vault entry therefore existed for information that was not a
   credential or secret. Memory-type routing is an LLM judgment, not an
   authorization or sensitivity boundary.

2. A semantic-memory attempt generated plausible explanatory detail that was
   not supplied by the user. Derived memory therefore needs provenance and an
   explicit distinction between observed fact and inference/speculation.

3. Child memory operations can fail and later agent steps can still call
   `finish_memory_update` and finish with `function_failed=False`. Agent-level
   completion is not evidence that every requested durable memory write
   succeeded.

4. Knowledge Vault remains rejected as Blaine's credential store. The observed
   non-secret classification into Knowledge Vault strengthens the case for
   keeping credentials outside this boundary.

5. Redis emitted a Search warning involving `filter_tags_session_id`. It did
   not block the validated persistence path, but the index/schema mismatch
   remains an investigation item before relying on that filter.

### Local resource observation

With both local model servers active, measured GPU use was:

```text
RTX 5090 total             32607 MiB
total observed use         27833 MiB

Qwen vLLM EngineCore       24516 MiB
BGE-M3 vLLM EngineCore      2574 MiB
desktop / other              ~530 MiB
```

System memory remained comfortable:

```text
visible RAM                 59 GiB
used                        14 GiB
available                   44 GiB
swap used                    0 GiB
Redis                       ~124 MiB
```

The current Qwen server uses `--gpu-memory-utilization 0.80`. Reducing that
toward `0.70` is a later tuning experiment for additional workstation
headroom, not a requirement for the validated correctness result.

Qwen should be treated as a shared local inference service. MIRIX and Goose
should consume the same Qwen endpoint rather than loading independent copies
of the model.


## Current architecture and external-agent boundary

**OBSERVED.** The active REST path is:

```text
External consumer (Blaine, a harness, or ordinary HTTP client)
  POST /agents/meta/initialize
    AgentManager.create_meta_agent
      persisted meta_memory_agent parent + selected child agent states
  POST /memory/add_sync  OR  /memory/add -> internal queue worker
    AsyncServer.send_messages -> load_agent -> MetaMemoryAgent.step
      Agent._get_ai_reply -> configured LLM -> trigger_memory_update tool
        selected child Agent.step -> configured LLM -> memory tools
          deterministic service managers -> SQLAlchemy -> PostgreSQL

  GET /memory/search -> managers -> FTS/string/vector queries
  POST /memory/retrieve/conversation -> topic extraction -> memory queries
```

The relevant constructor is [AgentManager.create_meta_agent][construction]
called by [the initialization route][initialize], and the actual loaded class
is `MetaMemoryAgent`, a thin subclass of `Agent`. The separately retained
[`agent/meta_agent.py` wrapper][meta-wrapper] is not the constructor used by
that REST route. This distinction avoids deriving conclusions from a legacy
wrapper's comments or defaults.

**Chat Agent:** the default `CreateMetaAgent.agents` list contains memory,
reflexion, and background agents, but no `chat_agent`. The parent is explicitly
created with `AgentType.meta_memory_agent`; `/memory/add*` targets that parent.
`AsyncServer.load_agent` dispatches it to `MetaMemoryAgent`. Chat remains an
optional recognized agent type, with prompts and a generic message endpoint;
it is not required by this memory-service path. Source: [schema][agent-schema],
[construction][construction], [server loader][loader], [ingestion][ingestion].

**INFERRED.** Goose or any other external consumer can use this HTTP surface
while retaining its own conversation and identity. MIRIX still requires its
own internal client, user, agent-state, prompt, tool, and message records.
Those are memory-service state, not a requirement to move Blaine's conversation
or Task lifecycle into MIRIX. Core `human`/`persona` blocks are optional memory
content/templates; their existence does not make them Blaine's authoritative
persona. No Goose execution was performed.

The current Python `MirixClient` is an **async HTTP client**; its relevant
methods must be awaited even though some examples retain synchronous-looking
calls. Direct HTTP avoids importing an agent harness. [Client source][client]

### Which components infer, and when

“Memory Manager” can mean an LLM-backed agent or its deterministic persistence
service. These are different layers.

| Component | OBSERVED inference path and activation |
|---|---|
| Meta Memory Agent | Inherits `Agent`; topic extraction and the completion/tool loop use its `llm_config`. Dispatch decisions are LLM-produced tool calls. |
| Core Memory Agent | Inherits `Agent`; infers block edits. `BlockManager` applies database changes. |
| Episodic Memory Agent | Inherits `Agent`; infers event records/edits. Its manager persists and searches them, generating embeddings when enabled. |
| Semantic Memory Agent | Same common LLM loop; manager persists facts and optional embeddings. |
| Resource Memory Agent | Same common LLM loop; manager persists resource content and summary embeddings. |
| Knowledge Vault Agent | Same common LLM loop; emits plaintext structured values to memory tools. The manager embeds captions and persists entries. |
| Procedural Memory Agent | Inherits `Agent`, but normal automatic meta dispatch now removes `procedural`. Session distillation first calls an LLM for a JSON array of experiences; the curator then invokes the procedural agent's tool loop to evolve skills. |
| Reflexion / Background agents | Thin `Agent` subclasses with their own persisted configuration. They can infer when invoked, but normal `trigger_memory_update` does not dispatch either. Their registration alone is not evidence of a running background scheduler. |
| Auto-Dream | Generic modes run an `AutoDreamAgent` through the common LLM loop. `procedural` instead runs session distillation and procedural evolution. `dry_run` takes a count/report path without LLM execution or memory mutation in the inspected branches. |
| Summarization / retrieval | Context summarization copies the current agent's LLM configuration. REST conversational retrieval uses the client's first returned agent configuration, or an explicitly requested native Ollama topic extractor with fallback. |

Evidence: [agent subclasses][agent-types], [common completion loop][agent-loop],
[memory dispatch][dispatch], [memory tools][memory-tools],
[session distiller][distiller], [curator][curator], [Auto-Dream][dream],
[summarizer][summarizer], [retrieval][retrieval].

**OBSERVED current-main change:** ingestion stamps `session_tag` as
`conversation` by default (overridable by `MIRIX_DEFAULT_SESSION_TAG`).
`conversation` sessions permit ordinary extraction and do not automatically
trigger skill distillation. `task` sessions suppress all ordinary inline
memory extraction and participate in the every-N-session procedural trigger
(default threshold 5). A batch `session_id` causes real user/assistant/tool
turns to be written to the Conversation Message Store. Procedural learning
depends on that store and sealed sessions; it is not just a sixth parallel
memory extractor. The current SDK `add` method does **not** expose `session_tag`;
the REST request does. [Constants][constants], [ingestion][ingestion],
[dispatch][dispatch], [client][client], [probe results][results]

## Internal provider and configuration path

**OBSERVED construction-to-call trace:**

1. `MirixClient.initialize_meta_agent` reads YAML or accepts a config dictionary,
   then posts it to `/agents/meta/initialize`.
2. REST constructs `LLMConfig` and `EmbeddingConfig`, and flattens
   `meta_agent_config.agents/system_prompts` into `CreateMetaAgent`.
3. `AgentManager.create_meta_agent` uses that **same top-level configuration**
   for the parent and every child `CreateAgent`. Per-child dictionaries handle
   block seeds; they do not select a child's model/provider.
4. Agent state stores LLM/embedding configuration in JSON columns. The server
   loads the appropriate subclass with that state; dispatch passes the stored
   child state, not a separate hard-coded cloud model.
5. `Agent._get_ai_reply` calls `LLMClient.create(agent_state.llm_config)`.
   Non-streaming supported clients build requests and execute them through
   `LLMClientBase.send_llm_request`.
6. OpenAI's implementation passes `model_endpoint` as SDK `base_url`, builds a
   Chat Completions request, calls `AsyncOpenAI.chat.completions.create`, then
   validates/normalizes the result as `ChatCompletionResponse`.
7. `Agent` parses returned tool arguments, validates them, invokes the linked
   memory function, persists messages/results, and continues/stops its loop.

Evidence: [client][client], [initialization][initialize],
[construction][construction], [config schema][llm-config], [loader][loader],
[factory][factory], [OpenAI client][openai-client], [agent loop][agent-loop].

### Shared versus distinct models

**OBSERVED:** each agent record has its own `llm_config`; internal
`AgentManager.update_llm_config/update_agent` can change one record and invalidate
parent caches. Thus heterogeneous providers are representable and the execution
path consumes the individual configurations. However:

- Standard hierarchy creation and `update_agents=true` propagate the top-level
  LLM configuration to every child.
- Public `PATCH /agents/{agent_id}` unconditionally returns **501**, despite
  accepting an LLM config in its request schema and having an SDK method.
- The separate `MetaAgent` wrapper also propagates its common configuration.
- Auto-Dream's procedural distiller derives configuration from the meta agent;
  evolution uses the procedural child. Generic dream creation inherits the
  meta configuration. A request-level `model` override is only a model name,
  not a provider configuration. In the generic path it changes a local state
  copy and then reloads the agent by ID, so it is not reliable evidence that
  the override reaches execution.

**Conclusion:** one configured LLM across the normal public memory hierarchy;
distinct models/providers are supported by the internal state/service design,
but **not a working documented per-child initialization/update capability at
this public seam**. Do not present heterogeneous public configuration as
validated. [Internal updates][agent-updates], [public 501][update-route],
[construction][construction], [dream][dream]

### Actual provider coverage

| Endpoint type | OBSERVED status in this revision |
|---|---|
| `openai`, `azure_openai`, `anthropic`, `google_ai` | Factory branches import existing concrete clients. These are the four implemented modern completion-client paths. The `openai` path was exercised against local Qwen/vLLM; hosted provider behavior was not tested. |
| `openrouter` | Factory branch exists, but `mirix/llm_api/openrouter_client.py` does not. Selecting this branch cannot instantiate the named client. An OpenRouter-compatible URL can instead be configured as `openai`; that is a different path. |
| `groq`, `bedrock` | Legacy `llm_api_tools.create` contains completion branches. However the current agent's fallback passes `user_id`, absent from that function's signature. The retained probe confirms argument binding raises `TypeError`. These are not established working end-to-end memory-service providers. Summarization/distillation also rely on the modern factory. |
| `azure` | Legacy fallback spelling; the LLM schema accepts `azure_openai`, not `azure`. Modern Azure uses the concrete client above. Embeddings separately use `azure`. |
| Other accepted LLM tags | `cohere`, `google_vertex`, `ollama`, `webui`, `webui-legacy`, `lmstudio`, `lmstudio-legacy`, `lmstudio-chatcompletions`, `llamacpp`, `koboldcpp`, `vllm`, `hugging-face`, `mistral`, `together`, `deepseek`, `xai`: accepted by `LLMConfig`, but no modern factory branch and no corresponding fallback completion branch. A schema enum or discovery class is not working execution support. |

Source: [schema][llm-config], [factory][factory], [legacy API][legacy-api],
[fallback call][agent-loop], [isolated signature result][results].
**It is not restricted to OpenAI, Anthropic, and Google AI:** Azure OpenAI is
also implemented, and OpenAI's endpoint is configurable. Conversely, the large
provider enum greatly overstates the current working dispatch surface.

Retained local support is mixed. `OllamaProvider` can discover models but emits
the unsupported `ollama` completion tag. `VLLMCompletionsProvider` emits the
unsupported `vllm` tag; **`VLLMChatCompletionsProvider` emits `openai` and is
registered by the server**, so that route is still wired. Old model-wrapper
fields/configurations and provider helper files remain; `cohere.py` imports a
missing `mirix.local_llm.utils`. Do not restore or select legacy local paths
based only on their names. [Discovery][providers], [server registration][registration]

### Local Qwen: VALIDATED WITH vLLM

The local Qwen path has now been exercised end-to-end rather than only inspected
statically.

The validated serving configuration is Qwen3.5-9B behind vLLM's
OpenAI-compatible Chat Completions API:

```yaml
model: Qwen/Qwen3.5-9B
model_endpoint_type: openai
model_endpoint: http://127.0.0.1:8000/v1
api_key: EMPTY
context_window: 32768
```

The selected vLLM configuration enables Qwen tool calling with the Qwen reasoning
and tool-call parsers. Live probes established ordinary chat, disabled-thinking
behavior, JSON-schema-constrained output, structured tool calls, MIRIX Meta
Agent routing, child memory-agent execution, and persistent Core, Episodic, and
Semantic memory formation.

MIRIX therefore does not need a new provider implementation for this selected
Qwen/vLLM path. Its existing `openai` completion endpoint type is sufficient
when pointed at vLLM's OpenAI-compatible `/v1` API.

This does not establish equivalent behavior for every model or serving engine
accepted by MIRIX's configuration schemas, multimodal workloads, native Ollama
paths, or every procedural/distillation prompt. Those are separate
compatibility questions and should be tested only when Blaine needs them.

Tool/schema compatibility remains part of the serving contract: MIRIX depends
on structured tool calls, JSON arguments, tool-call IDs, tool-result
continuation, and usable schema adherence. Plain text Chat Completions support
alone is insufficient.

Embeddings are a separate local service. BGE-M3 is served independently by
vLLM and accessed through MIRIX's generic `EmbeddingEndpoint` using the
currently misleading `embedding_endpoint_type: hugging-face` configuration
documented in the live-validation section above.

## Native PostgreSQL 18

**Conclusion — VALIDATED for the selected local path.** Native PostgreSQL
18.6 with pgvector 0.8.6 was used successfully by the running MIRIX service for
the memory operations exercised in this carveout. This is not exhaustive
validation of every migration, query, index, or recovery path.

**OBSERVED initial environment:** the first source-only inspection found no
PostgreSQL or Redis installation. The subsequent empirical phase installed and
used native PostgreSQL 18.6 with pgvector 0.8.6 and Redis 8.10.2. The initial
environment record remains retained as historical experiment evidence in the
[experiment README][experiment].

| Concern | OBSERVED implementation / consequence |
|---|---|
| Connection | `MIRIX_PG_URI` or complete `MIRIX_PG_*` settings select PostgreSQL; otherwise the runtime can fall back to SQLite. `server.py` converts `postgresql://`/`postgresql+pg8000://` to `postgresql+asyncpg://` and creates an async SQLAlchemy engine. Docker is not involved in this code path. |
| Required extension | `vector` is required because PostgreSQL ORM columns are declared `Vector(4096)` even if embedding generation is disabled. Install pgvector for PostgreSQL **18**, then enable it in the target database before table creation. |
| Bootstrap extras | `init.sql` also enables `uuid-ossp` and `pg_trgm`. No inspected active query requires their UUID/trigram functions; matching “fuzzy” behavior includes Python `rapidfuzz` and ordinary text predicates. These are shipped bootstrap extras, distinct from the hard vector-type requirement. |
| pgvector version | MIRIX does not pin a server-extension minimum/version check. Its Compose example uses old `ankane/pgvector:v0.5.1`; that image is not a native PG18 compatibility constraint. Use a maintained PG18-compatible native build; this experiment selects no system installation. |
| Vectors | Normal `vector(4096)` storage, zero-padding, cosine distance (`<=>` through SQLAlchemy), limits and distance thresholds. No HNSW/IVFFlat PostgreSQL index declaration found in the inspected ORM/migrations. Do not confuse 4096-dimensional storage with support for a 4096-dimensional ANN index. |
| Text search | `to_tsvector('english', ...)`, `to_tsquery`/`plainto_tsquery`, `@@`, weighted vectors and `ts_rank_cd`. “bm25” names a service method; PostgreSQL execution uses native ranking, not a required BM25 extension. Episodic memory declares GIN expression indexes. Not every dynamic search expression has a matching index. |
| Other SQL | JSON storage with JSONB casts, GIN tag indexes, B-tree/expression/partial indexes, JSON `->>` extraction, timestamps, foreign keys, `ON CONFLICT`, row locks, and advisory locks in procedural consolidation. No PostgreSQL-17-specific executable path or server-version check found. |
| Generated columns | No generated-column/`Computed` declaration found in current ORM or SQL migrations; FTS uses expressions. PostgreSQL 18's generated-column defaults therefore do not change this schema path. |
| Fresh schema | REST lifespan calls `ensure_tables_created`, which runs `Base.metadata.create_all`, then checks for missing columns. It does not install extensions or create the database/role. |
| Upgrades | Operator-run `scripts/migrate_*.sql`; startup detects missing columns and prints migration hints. `create_all` does not upgrade existing tables. Index/backfill/type drift is not fully covered by that missing-column check. Phase-2 scripts using `CREATE INDEX CONCURRENTLY` must run outside a transaction. |
| Legacy migration script | `server/startup.sh` still refers to Docker startup and `alembic upgrade head`; no corresponding Alembic configuration/revision tree was found. The inspected current entrypoint is Uvicorn and REST lifespan. Do not use that legacy script for the native experiment. |

Source: [settings][settings], [database setup][database], [extension bootstrap][init-sql],
[ORM vector definition][vault-orm], [episodic indexes][episodic-orm],
[search query builder][query-utils], [manual migrations][migrations],
[Auto-Dream locks][dream], [container example][compose], [legacy startup][startup].

Supporting external evidence: pgvector's changelog added PostgreSQL 18 support
in 0.8.1 and records subsequent PG18 fixes; its current installation instructions
include native `postgresql-18-pgvector`. Its documented ANN limits distinguish
`vector` indexing from larger vector storage. PostgreSQL 18 retains native
GIN text-search support. [pgvector changelog](https://github.com/pgvector/pgvector/blob/master/CHANGELOG.md),
[pgvector native installation and limits](https://github.com/pgvector/pgvector),
[PostgreSQL 18 FTS indexes](https://www.postgresql.org/docs/18/textsearch-indexes.html)

**UNVERIFIED beyond the selected live path:** reproducibility from a fresh
dependency install, full schema/query coverage, migration upgrades, query
plans/performance, crash recovery, and compatibility with other PG18/pgvector
builds.

## Knowledge Vault security

**Conclusion — OBSERVED/INFERRED: plaintext sensitive memory, not a credential
store.** The names “vault,” “secret,” and “securely” in prompts do not correspond
to encryption or a dedicated secret authorization boundary.

### Complete value path

1. **Ingress:** `/memory/add*` receives conversation/event content. With a batch
   session ID, external turns are also persisted in the Conversation Message
   Store. The original sensitive content can therefore exist outside the vault.
2. **Inference:** the Meta Agent receives input; its knowledge child receives
   content selected for extraction. The Knowledge Vault Agent emits
   `knowledge_vault_insert`/`knowledge_vault_update` tool arguments containing
   `secret_value`. The secret has already entered internal LLM input/output.
3. **Application model:** `KnowledgeVaultItemBase.secret_value` is a required
   Python `str`, not a secret wrapper or encrypted representation. `sensitivity`
   is also a plain string, with descriptive examples rather than a constrained
   security policy.
4. **Persistence:** `insert_knowledge` passes the value into the Pydantic model;
   `create_item` uses `model_dump` and constructs the ORM object;
   `create_with_redis` adds/commits/refreshes it. ORM `secret_value` is a normal
   SQLAlchemy `String` column. **No encryption occurs on this path.**
5. **Caches/search:** optional caching serializes the full Pydantic entry to
   Redis JSON. PostgreSQL FTS can tokenize `secret_value`; string matching can
   read it; all matching records still contain the plaintext value.
6. **Retrieval/exposure:** direct search/components serialize `secret_value` into
   responses. `search_in_memory` returns it to the calling internal agent as a
   tool result. Auto-Dream serializes complete vault items except embedding
   vectors into its LLM payload.

Evidence: [ingestion][ingestion], [memory tools][memory-tools],
[application schema][vault-schema], [manager][vault-manager],
[ORM][vault-orm], [base persistence/cache][orm-base], [search tool][search-tool],
[REST search][search], [Auto-Dream serialization][dream].

### Encryption, representation, and exposure

**OBSERVED:** no application encryption algorithm/library, vault encryption-key
source, key persistence, or vault key rotation exists in this traced path.
There is also no `pgcrypto` bootstrap or column encryption transform. JWT
signing secrets, password hashes, and API-key hashes elsewhere in the system
are unrelated to encryption of `secret_value`. Disk encryption, TLS, database
hosting controls, and backup encryption are deployment properties not established
by this source review.

One transport detail is visible: the PostgreSQL URI adapter handles `sslmode`
values other than `disable` or `prefer` by creating an SSL context and then setting
`check_hostname=false` and `verify_mode=CERT_NONE`. Thus even supplying a
verification-oriented SSL mode does not establish certificate verification in
this implementation. Transport encryption would not encrypt the stored vault
column in any event. [Database connection setup][database]

| Surface | Can secret plaintext or derived information appear? |
|---|---|
| PostgreSQL columns | **Yes, directly:** `knowledge_vault.secret_value`. Input conversation/message/tool records can contain additional copies. |
| PostgreSQL FTS | **Query-time tokenization: yes.** The vault's native FTS builds `to_tsvector` over the value when that field/all fields are searched. **No persistent vault FTS index over `secret_value` is declared in the inspected schema.** GIN stores lexemes rather than a reversible copy of a full original string. Secret material copied into episodic summary/details could reach that component's FTS indexes; no automatic redaction prevents this. |
| pgvector / embedding provider | **Not directly from `secret_value` in vault insertion:** only `caption` is embedded, and secret-value embedding searches are explicitly rejected. **No confidentiality guarantee:** a secret in a caption, query, other extracted memory, or supplied embedding input can be encoded and sent to an embedding provider. Vectors are not encrypted secret storage. |
| Redis | **Yes:** full entry JSON includes the value. Its declared search index covers caption/scope/user/vector fields, not a secret-value text field; cache storage still holds the secret. |
| Logs/stdout | **Yes:** insert/update failure paths print the entire `item!r`, including `secret_value`, and traceback. Tool results can reach interface output; summary logging and SQL exception/echo logging add possible copies. No sensitivity-aware redaction is applied there. |
| Traces | **Yes when enabled/exported:** Langfuse records message contents, tool arguments and completion results. OpenTelemetry span attributes include serialized LLM inputs and outputs. Truncation limits are not redaction. |
| API responses | **Yes:** direct vault search and `/memory/components` include it. Conversational/topic retrieval normally returns vault IDs/captions only; that narrower response is not an authorization rule for other endpoints. |
| Internal LLMs/tools | **Yes:** incoming extraction, tool arguments, search tool results, and Auto-Dream payloads. High sensitivity is not a prohibition on these flows. |

Sources: [vault insertion/search][vault-manager], [vault indexes][vault-orm],
[episodic indexes][episodic-orm], [failure logging][memory-tools],
[LLM tracing][llm-base], [OTel attributes][agent-loop], [Redis index][redis],
[search tool][search-tool], [retrieval][retrieval], [dream][dream].

### What sensitivity and authorization really enforce

**Sensitivity — OBSERVED:** `low`/`medium`/`high` are metadata and prompt
conventions, with an optional query filter. `Agent.retrieve_relevant_memories`
filters ordinary agents to low/medium, while the vault/reflexion agents can see
all levels. That preliminary view contains IDs/captions. The general search
tool, public direct search, and Auto-Dream do not impose that exclusion. Redis
fast paths in `list_knowledge` do not pass the `sensitivity` filter. This is
neither a consistent authorization boundary nor protection against disclosure
to a provider. [Agent retrieval][agent-retrieval], [manager][vault-manager],
[schema][vault-schema], [search tool][search-tool]

**Authentication/access — OBSERVED controls and gaps:**

- API-key middleware hashes/looks up a key, checks active client state, and
  injects client/org headers; dashboard endpoints can also use JWTs. Agent
  records are filtered by organization and creating client. Normal ingestion
  requires a `write_scope` and stamps that scope on memory tags. Direct search
  passes the client's `read_scopes` to managers.
- **Identity headers are trusted without authenticating them.** If no API key
  is supplied, middleware leaves `X-Client-ID`/`X-Org-ID` untouched. The resolver
  accepts those values; search and the JWT-or-key helper also accept the client
  header path. The isolated resolver probe reproduced acceptance without a
  key. An external gateway that strips/authenticates those headers could change
  deployment exposure, but no such gateway was assumed or tested.
- The base ORM access predicate discards its `access` argument and generally
  enforces same-organization access, not distinct read/write/admin permission.
  Vault delete resolves the entry by organization and hard-deletes it; the
  inspected public route does not require a write scope or check the item's
  memory scope/user/sensitivity. A read-only scope must not be treated as a
  global prohibition on mutation.
- Scope enforcement differs by path. The vault branch of conversational/topic
  retrieval omits `filter_tags`, `read_scopes`, and `use_cache`; components,
  internal general search, and generic Auto-Dream have comparable omissions.
  `get_item_by_id` returns a cache hit by object ID without checking the supplied
  user's ownership; its database fallback uses an organization-level actor.
- The PostgreSQL vault FTS helper discards the already-scoped base query and
  builds raw SQL with `user_id` and supplied tag/scope filters, **without an
  explicit organization or `is_deleted` predicate**. The ordinary ORM branch
  has additional organization filtering. This is a source-visible inconsistency;
  a cross-tenant exploit was not attempted, and global user-ID/FK constraints
  affect exploitability.

Evidence: [header middleware/resolver][auth], [client keys][client-manager],
[ORM permissions][orm-access], [delete route][vault-delete],
[vault manager][vault-manager], [retrieval][retrieval], [Auto-Dream][dream].
These are specific implementation findings, not a complete penetration test.

### Audit and mutation history

**OBSERVED:** base rows have creation/update timestamps, creator/last-updater IDs
and a soft-delete flag; vault rows have one `last_modify` JSON object. The
Knowledge Vault update tool hard-deletes old IDs and inserts replacement items
through separate manager operations. It does not retain a vault version chain,
atomic supersession transaction, or immutable before/after record. Reads have
no mandatory append-only access event in the traced managers. Diagnostic logs,
agent messages and optional traces are neither a complete access ledger nor
safe credential audit storage. Procedural skill lineage elsewhere is not vault
audit history. [Base row metadata][row-metadata], [vault update tool][memory-tools],
[manager deletion][vault-manager]

**INFERRED recommendation:** treat Knowledge Vault only as sensitive memory
whose contents may be read by internal inference and ordinary service clients.
Do not store working credentials there or make MIRIX Blaine's root secret store.
Blaine's intended direction is external secret storage (Bitwarden or equivalent);
this experiment neither selects nor implements that integration. Even
sensitive-memory use needs an explicit trust boundary
and resolution of the observed access/egress defects.

## Smallest public memory seam

These are existing MIRIX operations, not a proposed Blaine Memory interface.

| Need | OBSERVED public surface and semantics |
|---|---|
| Initialize extraction | `POST /agents/meta/initialize`; client-owned hierarchy, top-level LLM/embedding configuration, selected children/block templates. Returns null for a client without a write scope. |
| Add conversation/event | `POST /memory/add_sync` waits for the current extraction call; `/memory/add` returns a queue receipt. Inputs include user, meta-agent ID, messages, session ID/tag, tags, `occurred_at`, cache and chaining options. SDK `add(async_add=False)` selects sync, but does not expose session tag. |
| Store raw event | `POST /memory/raw`, raw get/patch/delete/search routes. This is raw retention with its own manager, not proof of semantic extraction into the six components. |
| Direct search | `GET /memory/search`; memory type/field/query/method, tags, date range, limit, similarity threshold, optional core blocks. Explicit `bm25` or `string_match` avoids query embeddings. Default is embedding except procedural's configurable hybrid BM25/vector rank fusion. No conversational-agent reply required. |
| Conversational retrieval | `POST /memory/retrieve/conversation`; extracts topics/time, then returns structured memories. `GET /memory/retrieve/topic` accepts an already-known topic. Both are context retrieval, not a Chat Agent answering the user. Current conversion defects are below. |
| Scope/user/session | API key → client/application → organization; client write scope and read scopes; explicit end-user ID (otherwise a derived admin user); memory `filter_tags`, including session ID. A session is transcript provenance, not Blaine Task identity. Scope checks are inconsistent as described above. |
| Cross-user access | `GET /memory/search_all_users` intentionally searches the client's organization/scopes. This is a materially broader operation than per-user retrieval. |
| Inspect memory | `GET /memory/components` and `/memory/fields`; component responses can include secrets, and components are not a uniformly scope-enforced admin-only view. |
| Update/supersession | Public patches exist for episodic, semantic, resource and raw memory; procedural/vault have delete routes, but no equivalent public general patch in this REST file. LLM memory update tools perform delete/replace operations. There is no uniform immutable revision/supersedes contract across types. |
| Consolidation | `POST /memory/auto_dream`, optional user/meta-agent, mode, dry run, dates, model name and session count. `experience` combines episodic/semantic/vault. Generic modes currently fetch current memories (typically capped at 500), despite time-window parameters; reported counts are fetched totals, not verified merge/conflict counts. |

Sources: [REST ingestion][ingestion], [retrieval][retrieval], [search][search],
[REST raw/update routes][raw-api], [Auto-Dream route][dream-api],
[dream implementation][dream], [SDK][client].

### Defects and lifecycle limits that affect the seam

**OBSERVED by isolated source execution:**

- Both add handlers concatenate each list content element to a string. The
  documented `{"role":"user","content":[{"type":"text","text":"..."}]}`
  shape raises `TypeError`. Role-plus-string content and flat text blocks pass
  this preprocessing. Only the former also represents conversation roles for
  the session store. No server-level ingest success is claimed.
- Conversational retrieval's content guard recognizes the nested text-block
  shape, but the default topic extractor concatenates those dictionaries to
  strings and catches the resulting error, returning no topics. Role-plus-string
  content fails the guard and falls back to recent retrieval. An explicitly
  selected native Ollama topic extractor uses a different flattening function;
  direct topic search is also a separate path. A `success: true` retrieval
  response can therefore conceal absence of useful topic extraction.
- The generic agent-update route returns 501; the SDK exposes an unavailable
  operation. The modern OpenRouter import is missing; the legacy completion
  fallback has an incompatible `user_id` argument.

[Probe source and limits][probe], [retained results][results].

**OBSERVED from source:** the default queue is process-local memory; optional
Kafka is a separate mode. `/memory/add` returns `queued` with an agent ID/count,
not an independently queryable durable write result. The SDK transport retries
POST requests on several server/network failures without a visible ingestion
idempotency key in the payload. A lost response/retry therefore needs duplicate
handling; selected memory deduplication heuristics are not exactly-once delivery.
Child extraction errors may be returned as tool results; the sync route's
`processed` status is not independent evidence that every requested memory type
was persisted. Session-store ingestion errors are logged without aborting the
main add, so successful extraction can coexist with missing skill-learning input.
[Queue config][queue], [client retries][client], [ingestion][ingestion],
[child dispatch][dispatch]

Auto-triggered procedural dreams claim a persisted window and then use
`asyncio.create_task`. The implementation explicitly logs failed claimed windows
and suggests manual recovery. Database cursors/locks improve coordination but
do not turn that task into Restate-style durable execution. There is no basis
for equating MIRIX queue acceptance, an agent's successful turn, or an
Auto-Dream checkpoint with Blaine Task completion. [Trigger][dispatch],
[dream implementation][dream]

## Upstream status / risk register

**OBSERVED — checked 2026-09-19:** the investigation reviewed the currently
public open issues and related PRs. The items below were open at that check;
the PRs were not merged. Their status is a dated observation, separate from
the source findings at the pinned SHA.

| Upstream item | Relevance to this carveout |
|---|---|
| [Issue #113 — vLLM support](https://github.com/Mirix-AI/MIRIX/issues/113) | Directly relevant to local Qwen/vLLM usability: reports Qwen3 through vLLM, stale documentation, and no current-main example. It does not validate our proposed endpoint configuration. |
| [Issue #54 — Qwen](https://github.com/Mirix-AI/MIRIX/issues/54) | Related Qwen compatibility request; not proof of local inference support. |
| [Issue #98 — custom models](https://github.com/Mirix-AI/MIRIX/issues/98) | Related model-format/tool-calling incompatibilities for Qwen/Kimi/DeepSeek. It does not establish the exact causes found here. |
| [PR #125 — OpenRouter LLM and embedding support](https://github.com/Mirix-AI/MIRIX/pull/125) | Directly relevant to the incomplete provider path: adds the missing implementation and tool-schema adaptations. Open, not merged; its proposed behavior is not current-main support. |
| [Issue #116 — multimodal capability gaps](https://github.com/Mirix-AI/MIRIX/issues/116) | Directly relevant to the gap between advertised multimodal behavior and the implemented memory-service path. |
| [Issue #64 — embedding configuration](https://github.com/Mirix-AI/MIRIX/issues/64) | Related, but concerns fixed Google embeddings in the evaluation branch, not the omitted configured OpenAI embedding model found in current main. |
| [Issue #140 — How to report Security Issue?](https://github.com/Mirix-AI/MIRIX/issues/140) | Asks how to report a security issue, with no public description or comments at the check. It does not publicly track the concrete security findings in this report. |
| [PR #133 — LiteLLM support](https://github.com/Mirix-AI/MIRIX/pull/133) | Relevant proposed provider work, still open and not merged. No resulting current-main capability is established. |
| [PR #96 — Ollama support](https://github.com/Mirix-AI/MIRIX/pull/96) | Historically relevant, but targets the legacy desktop-agent path. It does not validate current-main Ollama support. |

**OBSERVED — no matching public open issue found** for these specific findings:

| Finding already evidenced in this report | Risk classification |
|---|---|
| Message-conversion `TypeError` / conversational-retrieval inconsistency | Implementation defect. |
| Public agent-configuration update returning HTTP 501 | Unimplemented public operation / configuration limitation. |
| Legacy provider fallback's incompatible `user_id` argument | Implementation defect. |
| SDK omission of `session_tag` | API/SDK capability mismatch. |
| Configured model omitted in the OpenAI embedding path | Implementation defect. |
| Authentication/scoping inconsistencies around header-supplied identifiers | Security enforcement defects. |
| Disabled TLS verification in the inspected database connection path | Security implementation defect. |
| Knowledge Vault plaintext persistence | Architectural/security capability limitation for credential storage. |
| Potential secret exposure through tools, prompts, logs and traces | Memory-service data-flow limitation; inadequate redaction/protection for secret storage. |
| Inadequate Knowledge Vault access audit history | Audit capability limitation for credential storage. |

This search result is **not evidence that maintainers are unaware** of these
findings. Private reports, other channels, and future changes are outside the
observed public record. Similar issues in older branches are not substitutes
for tracking the exact current-main defects.

**INFERRED:** #140 indicates uncertainty about the security-reporting path;
it does not identify a vulnerability or establish the project's internal
response process. The provider PRs offer relevant work to revisit, but do not
resolve this checkpoint's risks. A memory system's lack of credential-store
guarantees is an architectural limitation, distinct from broken configuration,
conversion, or access enforcement in its existing paths.

The research judgment is now stronger: MIRIX is **validated locally as an
independent memory service** for the selected Qwen/vLLM + BGE-M3/vLLM + native
PostgreSQL/pgvector + Redis path. This is not equivalent to production readiness
or exhaustive provider/database validation. Knowledge Vault as a credential
store and MIRIX as Blaine's root secret store remain **REJECT**. Blaine's
security direction remains external secret storage such as Bitwarden. Broader
isolation/security guarantees, recovery semantics, memory-quality policy, and
upstream fix coverage remain open investigation areas.

## HARVEST / ADAPT / REJECT / INVESTIGATE

Classifications are research judgments, not authorization to extract/integrate.

| Concept or responsibility | Class | Evidence and Blaine implication |
|---|---|---|
| External HTTP add/query/retrieve boundary | HARVEST | Current routes require internal memory agents, not an external Chat Agent. Reusable capability concept; implementation defects remain. |
| Six memory categories and structured records | HARVEST | Explicit models and managers; useful vocabulary without adopting a final interface now. |
| Caller-provided topic and deterministic FTS/string search | HARVEST | Existing direct retrieval/search paths can avoid topic-extraction inference. |
| Native SQLAlchemy/PostgreSQL/pgvector persistence | HARVEST | No Docker or PostgreSQL-17 runtime dependency observed. Live PG18 execution remains unverified. |
| Memory extraction and tool-based edits | ADAPT | LLM routing, tool schemas, error reporting, destructive replacement, and provenance need Blaine-owned expectations. |
| Client/user/scope/session identifiers | ADAPT | Useful dimensions, but authorization is inconsistent; session tags change extraction semantics and are not Task IDs. |
| Core persona/human blocks | ADAPT | May supply remembered context; must not define Blaine identity or override authoritative instructions. |
| `task` session procedural learning | ADAPT | Skill-only routing and sealed-session cadence need explicit consumer policy; SDK exposure is incomplete. |
| Public model configuration | ADAPT | Custom OpenAI URL is real; heterogeneous child config is internally representable but public update returns 501. |
| Queues, retries, receipts and consolidation triggers | ADAPT | Service-level mechanisms need explicit delivery/recovery semantics; no durable Task completion authority follows. |
| Knowledge Vault as sensitive memory | ADAPT | Plaintext, prompt/tool/trace exposure and access gaps must be addressed by the eventual trust boundary. |
| Knowledge Vault as credential store | REJECT | No encryption, sensitivity authorization, safe access audit or rotation boundary. |
| MIRIX as Blaine's root secret store | REJECT | Secret storage belongs outside this memory boundary (Bitwarden or equivalent); no integration is implemented here. |
| MIRIX Chat Agent as Blaine persona/runtime | REJECT | Not needed by memory path; identity, interaction and execution remain Blaine/harness responsibilities. |
| MIRIX as scheduler or durable Task owner | REJECT | Contradicts Blaine ownership; current queue/dream implementation does not supply those guarantees. |
| Memory-derived skills as authoritative policy/completion evidence | REJECT | Distillation produces fallible memories, not authorization or verified Task state. |
| Replacing Graphify/project knowledge with MIRIX | REJECT | Outside this memory experiment and the separately evaluated project-knowledge role. |
| Local Qwen/vLLM inference path | HARVEST | Chat, structured output, tool calls, Meta Agent routing, and memory-manager execution passed locally. Keep the serving layer replaceable. |
| Memory formation quality/provenance | INVESTIGATE | Routing and generated content remain fallible; observed Knowledge Vault misclassification and unsupported semantic elaboration require provenance/epistemic policy. |
| Native PostgreSQL 18 + pgvector persistence | HARVEST | Selected live Core/Episodic/Semantic write and fresh-process retrieval paths passed on PostgreSQL 18.6 + pgvector 0.8.6. Broader migrations/query plans/recovery remain unverified. |
| Complete isolation, retention/deletion and recovery guarantees | INVESTIGATE | Specific defects found; no live adversarial/recovery test. |

## Open questions and next steps

The original source-only stop condition has been exceeded. The selected local
Qwen/BGE-M3/PostgreSQL/Redis round trip passes, including persistent memory
retrieval from a fresh Python process.

Further work should be driven by concrete Blaine integration needs rather than
by attempting to exhaustively validate MIRIX.

Remaining questions with architectural value are:

1. **Memory provenance and epistemics.** Blaine needs to distinguish
   user-supplied facts, source-derived facts, model inference, and speculation.
   MIRIX memory formation cannot itself be treated as truth.

2. **Memory-type policy.** The live run showed ordinary configuration
   information being classified into Knowledge Vault. Blaine should control
   which memory categories are permitted. Knowledge Vault remains inappropriate
   for credentials and is a candidate for exclusion from normal Blaine memory
   formation.

3. **Completion evidence.** A child memory write may fail while the surrounding
   agent later finishes successfully. MIRIX agent completion must therefore not
   become Blaine Task completion evidence. Durable writes that matter to a
   Completion Contract need independent verification.

4. **Redis index/schema warning.** The observed `filter_tags_session_id` Search
   warning should be investigated before Blaine depends on that filtering
   behavior.

5. **Security and isolation.** The source-visible authentication, scope, TLS,
   plaintext Knowledge Vault, logging/tracing, and authorization concerns remain
   unresolved by the successful local functional probe.

6. **Recovery and idempotency.** Queue acceptance, caller retries, process
   death, and partial child writes need explicit semantics if MIRIX ingestion
   becomes part of a durable Blaine workflow.

7. **Operationalization.** PostgreSQL and Redis are already native services,
   while MIRIX and both vLLM servers are currently started manually. The next
   practical task is reproducible lifecycle and observability using OS process
   supervision plus thin repository scripts.

8. **Shared inference.** Goose should consume the existing Qwen vLLM endpoint
   rather than loading another Qwen instance. Once lifecycle automation exists,
   a concurrent Goose + MIRIX probe can establish the local VRAM and latency
   budget.

### Carveout classification after live validation

The useful seam is now strong enough to **HARVEST / ADAPT**, not to adopt MIRIX
as Blaine's architecture.

**HARVEST**

- independent HTTP memory-service boundary;
- persistent Core, Episodic, and Semantic memory;
- native PostgreSQL/pgvector persistence;
- local Qwen through OpenAI-compatible vLLM;
- local BGE-M3 through MIRIX's generic embedding endpoint;
- persistent Meta Agent reattachment across client processes.

**ADAPT**

- memory formation and routing;
- provenance and confidence semantics;
- configuration lifecycle;
- scope and isolation expectations;
- durable-write verification and recovery semantics.

**REJECT**

- MIRIX as Blaine's durable Task runtime;
- MIRIX Chat Agent as Blaine's persona;
- Knowledge Vault as credential storage;
- memory-derived content as authoritative policy or completion evidence.

The MIRIX carveout can stop here. The next work belongs in Blaine's local
runtime integration rather than additional MIRIX feature exploration.

[experiment]: ../../experiments/mirix-carveout/README.md
[manifest]: ../../experiments/mirix-carveout/source.json
[probe]: ../../experiments/mirix-carveout/source_probe.py
[results]: ../../experiments/mirix-carveout/source-probe-results.json
[task]: ../../experiments/mirix-carveout/task-request.json
[environment]: ../../experiments/mirix-carveout/environment.json

[construction]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/services/agent_manager.py#L175-L342
[initialize]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/rest_api.py#L2033-L2123
[meta-wrapper]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/agent/meta_agent.py#L156-L408
[agent-schema]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/schemas/agent.py#L252-L286
[loader]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/server.py#L682-L758
[ingestion]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/rest_api.py#L2125-L2616
[client]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/client/remote_client.py#L78-L1704
[agent-types]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/agent/__init__.py
[agent-loop]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/agent/agent.py#L620-L950
[dispatch]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/functions/function_sets/memory_tools.py#L1434-L2021
[memory-tools]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/functions/function_sets/memory_tools.py#L1282-L1432
[distiller]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/services/session_experience_distiller.py#L387-L498
[curator]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/services/skill_experience_curator.py#L131-L285
[dream]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/services/auto_dream_manager.py
[summarizer]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/memory.py#L61-L118
[retrieval]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/rest_api.py#L2641-L3137
[constants]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/constants.py#L263-L330
[llm-config]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/schemas/llm_config.py#L10-L127
[factory]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/llm_api/llm_client.py
[openai-client]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/llm_api/openai_client.py#L69-L328
[agent-updates]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/services/agent_manager.py#L737-L880
[update-route]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/rest_api.py#L874-L904
[legacy-api]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/llm_api/llm_api_tools.py#L117-L556
[providers]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/schemas/providers.py
[registration]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/server.py#L603-L665
[strict]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/llm_api/helpers.py#L1-L136
[tool-rules]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/services/helpers/agent_manager_helper.py#L245-L253
[embeddings]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/embeddings.py#L401-L572
[search]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/rest_api.py#L3194-L3837
[settings]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/settings.py#L124-L270
[database]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/server.py#L287-L512
[init-sql]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/init.sql
[vault-orm]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/orm/knowledge_vault.py
[episodic-orm]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/orm/episodic_memory.py#L88-L180
[query-utils]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/services/utils.py#L1-L101
[migrations]: https://github.com/Mirix-AI/MIRIX/tree/8cb06a62bbb7c478beb33dd4f2815696a72df482/scripts
[compose]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/docker-compose.yml#L20-L44
[startup]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/startup.sh
[vault-schema]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/schemas/knowledge_vault.py
[vault-manager]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/services/knowledge_vault_manager.py
[orm-base]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/orm/sqlalchemy_base.py#L631-L890
[search-tool]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/functions/function_sets/base.py#L83-L250
[llm-base]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/llm_api/llm_client_base.py#L90-L195
[redis]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/database/redis_client.py#L839-L885
[agent-retrieval]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/agent/agent.py#L1844-L1880
[auth]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/rest_api.py#L352-L417
[client-manager]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/services/client_manager.py#L80-L143
[orm-access]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/orm/sqlalchemy_base.py#L513-L566
[vault-delete]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/rest_api.py#L5887-L5911
[row-metadata]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/orm/base.py
[raw-api]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/rest_api.py#L4891-L5608
[dream-api]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/server/rest_api.py#L5708-L5793
[queue]: https://github.com/Mirix-AI/MIRIX/blob/8cb06a62bbb7c478beb33dd4f2815696a72df482/mirix/queue/config.py
