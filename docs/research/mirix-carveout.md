# MIRIX carveout: independent memory service

Research evidence, not an architecture decision. Investigated 2026-09-19.

**Answer: MIRIX has a usable architectural seam for an external agent to submit
and retrieve memory without adopting its Chat Agent. Native PostgreSQL 18 is
likely compatible. Local Qwen inference is LIKELY COMPATIBLE through the
existing OpenAI client, subject to a real tool-calling and embedding probe.
This revision is not ready to trust as Blaine's sensitive memory boundary.**

The obstacles are concrete: incomplete public configuration operations,
message conversion defects, inconsistent authorization/scope enforcement,
unencrypted Knowledge Vault values, and service-internal asynchronous work whose
acceptance is not evidence of completed memory writes. None requires making
MIRIX the owner of Blaine's identity or durable execution. They do prevent
calling the full intended deployment validated or production-ready.

## Evidence and scope

- **OBSERVED** means inspected source at the pinned revision or an explicitly
  identified deterministic probe result. Source observations are not live
  integration results.
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

No MIRIX server, PostgreSQL, Redis, model, or cloud inference was invoked. No
system packages were installed, Docker used, upstream source changed, production
code modified, or Restate/Graphify/Goose integration attempted.

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
| `openai`, `azure_openai`, `anthropic`, `google_ai` | Factory branches import existing concrete clients. These are the four implemented modern completion-client paths. Their live provider behavior was not tested. |
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

### Local Qwen: LIKELY COMPATIBLE

**OBSERVED:** the unchanged `_prepare_client_kwargs` accepted a synthetic key
and preserved `http://127.0.0.1:8000/v1` exactly in the isolated probe. There is
no OpenAI-host allowlist or Qwen-model-name rejection in that path. An explicit
dummy key avoids falling through to database/global OpenAI credentials when
calling a local server. This is constructor-argument evidence, not a request
sent to a model. [OpenAI client][openai-client], [results][results]

**INFERRED:** a text-capable Qwen model behind a sufficiently compatible Chat
Completions server can service the Meta and memory-agent calls without a new
provider implementation. Use `model_endpoint_type: openai`, the actual served
model ID, an explicit local `/v1` endpoint, explicit synthetic key, and a
realistic context window. Do not select the `ollama`/`vllm` enum merely because
that software hosts the model.

Compatibility requires more than accepting a messages array:

- **Tools:** MIRIX normally sends `tool_choice="required"`; it sometimes forces
  a named function. A handle containing `vllm` changes the normal choice to
  `auto`, but named forcing can still occur. It expects structured
  `tool_calls`, JSON arguments, tool-call IDs, and tool-result messages, and
  may consume several calls per reply.
- **Schemas:** the OpenAI client attempts to convert every tool to
  `strict: true`, `additionalProperties: false`, all fields required, including
  nested schemas. Unsupported conversion can warn and retain the original
  schema. The small `STRUCTURED_OUTPUT_MODELS` allowlist influences initial
  tool rules; it does not prevent the client from sending strict tools for
  Qwen. This path does not require a separate `response_format=json_schema`.
- **Request/response details:** `max_completion_tokens`, temperature, system
  messages, and an empty `user` field are sent; completion choices/finish reasons,
  usage and tool-call structure must match MIRIX's response expectations.
  Token counting falls back to OpenAI-style tokenizers for unknown models;
  Qwen context-budget accuracy remains unverified.
- **Non-tool calls:** topic extraction forces a function; summarization expects
  prose; the session distiller asks for and parses a JSON array from ordinary
  completion content. Reliable tool use alone does not establish distillation
  quality.
- **Multimodal inputs:** the client can construct image URL/base64 messages and
  resolve stored file references. Text-only Qwen cannot satisfy image/audio
  workloads simply because its server is OpenAI-compatible. No multimodal
  equivalence is claimed.

Evidence: [OpenAI request builder][openai-client], [schema conversion][strict],
[tool rules][tool-rules], [agent loop][agent-loop], [distiller][distiller].

Serving-engine evidence is supporting context, not a live MIRIX result:

| Local server | INFERRED fit and remaining test |
|---|---|
| vLLM | Strong candidate: official documentation describes required and named tool calls, strict-schema handling, and model-specific parsers/templates. Pin an engine/model/parser version and exercise MIRIX's exact payload. [vLLM tool calling](https://docs.vllm.ai/en/latest/features/tool_calling/) |
| Ollama | Its OpenAI-compatible `/v1` endpoint is a candidate; compatibility covers only a subset of OpenAI behavior. Test required/named choices, strict schemas, token-limit fields, and tool replay against the chosen version. The native `ollama` MIRIX LLM tag is not the route. [Ollama compatibility](https://docs.ollama.com/api/openai-compatibility) |
| llama.cpp | Function calling and Qwen-related chat templates exist; server/template/schema behavior must satisfy the same contract. No equivalent behavior was measured. [llama.cpp function calling](https://github.com/ggml-org/llama.cpp/blob/master/docs/function-calling.md) |
| Other compatible server | Apply the same payload-level criteria; a successful plain-text completion is insufficient. |

**Embeddings are a separate local dependency.** They default to enabled.
`embedding_model` supports an actual native Ollama embedding implementation and
configurable endpoints for other branches. The ordinary OpenAI/LlamaIndex branch
passes the endpoint/key but **omits `config.embedding_model`** when constructing
`OpenAIEmbedding`; arbitrary embedding-model selection cannot be assumed to work
there. Its custom-auth branch uses the configured model. Native Ollama embeddings
are a plausible configuration-only alternative. Model dimensions are padded to
4096, and vectors from different models are not interchangeable. Text-only
`bm25`/string probes can set `BUILD_EMBEDDINGS_FOR_MEMORY=false`, but the default
search path still requests embeddings unless explicitly changed. [Embeddings][embeddings],
[constants][constants], [search][search]

Native Ollama topic extraction is **currently wired** by
`local_model_for_retrieval` and `MIRIX_OLLAMA_BASE_URL`; it is not general internal
LLM configuration, does not extract temporal expressions, and on failure falls
back to the configured main LLM. To make eventual inference local-only, all
completion/embedding configurations and fallbacks must be local, and tracing
must also be considered. [Retrieval implementation][retrieval]

**UNVERIFIED:** Qwen memory quality, schema/tool reliability, effective context
limits, multimodal handling, and an entirely local end-to-end run. No evidence
currently establishes a mandatory provider-code rewrite for the `openai` route;
an incompatible chosen server could require a small payload adaptation or a
different serving configuration. The current application defects below are
independent of Qwen.

## Native PostgreSQL 18

**Conclusion — INFERRED: likely compatible without MIRIX source changes for a
fresh native database. UNVERIFIED in a live database.**

**OBSERVED environment:** Python 3.14.4 on Ubuntu 26.04.1. `psql`, `postgres`,
`pg_config`, `pg_isready`, and `redis-server` are absent from PATH; standard
PostgreSQL installation directories are absent. Matching dpkg database entries
were `un` (not installed); no installed PostgreSQL/pgvector package was found.
No live database portion was attempted. Exact prerequisites are retained in the
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

**UNVERIFIED:** dependency resolution on this host, schema creation, exact query
execution, migration upgrades, query plans/performance, crash recovery, and
driver compatibility with the eventual installed PG18/pgvector build.

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

The research judgments remain unchanged: MIRIX is **architecturally viable as
an independent memory service**; native PostgreSQL 18 and local Qwen through
an OpenAI-compatible endpoint are **likely compatible**. Live database/model
proof remains **UNVERIFIED**. Knowledge Vault as a credential store and MIRIX
as Blaine's root secret store remain **REJECT**. Blaine's intended security
direction is external secret storage (Bitwarden or equivalent), with no
integration or secret-store design undertaken here. Upstream fix coverage,
merge timing, and empirical compatibility remain **UNVERIFIED**.

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
| Qwen tool/schema behavior and memory quality | INVESTIGATE | Configurable transport observed; no local model run. |
| PG18 migration/query/performance behavior | INVESTIGATE | Static compatibility evidence only; native prerequisites absent. |
| Complete isolation, retention/deletion and recovery guarantees | INVESTIGATE | Specific defects found; no live adversarial/recovery test. |

## Unanswered questions and next empirical probe

**UNVERIFIED questions that remain:**

1. Which pinned Qwen model/server/parser combination reliably handles the exact
   strict schemas, required/named tools, JSON distillation and context limits?
2. Does a fresh native PG18/maintained pgvector database create all models and
   execute every selected memory search without driver/type/query failures?
3. Which message/config/auth defects will upstream fix, and which would require
   a narrowly scoped future adaptation before trusted use?
4. Do memory isolation, deletion and read scopes hold across cache on/off,
   direct/retrieval/tool/dream paths and users? Source evidence already shows
   they cannot be assumed; live tests should measure the precise exposure.
5. What survives process death after queue acceptance, session recording,
   partial child writes, or a claimed consolidation window? What duplicate
   effects arise when the caller retries?
6. What quality/provenance/retention policy is appropriate for remembered facts
   and learned skills? This experiment does not decide Blaine's final interface
   or production architecture.

**Proposed next probe, not executed:** after the user supplies/authorizes native
prerequisites, use a disposable native PG18 database with pgvector, a pinned
local Qwen Chat Completions server, synthetic content, and a tiny ordinary HTTP
client. Keep the MIRIX checkout read-only and runtime data outside it.

First verify the exact MIRIX completion payload against the local server:
required tool call, forced `update_topic_and_time`, nested vault schema with a
synthetic value, tool-result continuation, and JSON-array distillation. Record
raw requests/responses and confirm no cloud fallback. This separates protocol
failure from memory-service behavior.

Then create a fresh schema and a minimal meta hierarchy without Chat Agent,
reflexion or background agents. Disable tracing/caches; start with embedding
generation disabled and explicit `bm25` search to isolate ingestion/storage.
Submit role-plus-string synthetic conversation content using `/memory/add_sync`
and `session_tag=conversation`; verify the database row and a separate API
read, then repeat with a configured local embedding model and vector search.
Record the known nested-block/conversational-retrieval failures rather than
silently patching upstream. Test rejected identity headers and scope/user
separation using synthetic tenants before trusting any sensitive data.

Only after that narrow round-trip passes would session-based procedural
distillation and one explicit dry-run/real Auto-Dream comparison add useful
evidence. Pin every dependency and serving model used. No Restate, Goose,
Graphify, provider implementation, credential-store implementation, or common
Blaine interface is needed for this probe.

The present stop condition is met at source-evidence level: **independent memory
service is architecturally possible; native PG18 and local Qwen are plausible;
the immediate blockers to trusted adoption are implementation/security defects
and missing empirical validation, not a requirement to adopt MIRIX's Chat Agent
or runtime.**

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
