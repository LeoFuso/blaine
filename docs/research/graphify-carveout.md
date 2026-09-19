# Graphify carveout

Research evidence, not an architecture decision. Investigated 2026-09-19.

**Answer: Graphify can supply an independent, local structural extraction and
retrieval foundation without becoming Blaine's runtime or adopting its agent
workflow. This revision does not, by itself, satisfy the stronger requirement of
trustworthy, incrementally updated, provenance-aware Project Knowledge.**

The blockers are concrete: provenance categories conflate different derivation
methods, the canonical graph loses parallel relationships, partial updates can
miss newly resolvable calls, some document updates retain stale knowledge, and
textual query output omits information needed to assess provenance. These are
reasons to **ADAPT** before trusting the results, not reasons to combine Graphify
with MIRIX. Git and source files remain authoritative; the graph is derived data.

## Scope, pin and evidence

- **OBSERVED:** upstream repository: `https://github.com/Graphify-Labs/graphify`;
  exact commit **`b9cd9570728a5ff3485d2a1e36fe9a1272a368ae`**, package `graphifyy`
  0.9.64. Commit timestamp: `2026-09-18T22:16:16+01:00`.
- **OBSERVED:** unchanged sibling checkout at
  `/home/leofuso/workspace/graphify-upstream`; final `git status --porcelain` empty.
  Source links below are pinned to that commit, not a moving branch.
- **OBSERVED:** first corpus is a disposable clone of Blaine at
  `da6654e3a008b7e6be4f7ad54a5c4323bcb8f090`. This excludes later uncommitted edits,
  including the separate MIRIX report changes present when this work resumed.
- **OBSERVED:** CPython 3.12.14, isolated virtual environment and pinned
  dependencies. Graphify was imported from the sibling source, not installed
  globally or vendored. The environment includes SQL and MCP dependencies.
- **OBSERVED:** AGENTS.md, BLAINE.md, decisions 0001–0017, and the Multica/MIRIX
  carveouts supplied architectural context. No integration with those systems
  was performed. ADR [0014](../decisions/0014-project-knowledge-is-retrieval-first.md)
  is a proposed retrieval-first direction, not an implemented capability.

Here **OBSERVED** means inspected implementation or recorded empirical result;
the text distinguishes those two forms of evidence. **INFERRED** means a reasoned
consequence, not a demonstrated guarantee. **UNVERIFIED** means the experiment
does not establish the claim.

The [experiment README][probe] explains reproduction. Retained evidence is in
[primary results][results], [boundary results][boundary], [transport control][factory],
[freshness counterexamples][freshness] and [targeted upstream checks][checks].
Generated graphs and disposable repositories are ignored under the experiment's
`work/`; the initial artifact's digest was rechecked when finalizing this report.

The [TaskSpec][task] is **unsubmitted**: no authoritative Task creation binding was
available. No runtime Task identity or completion state is claimed. The
user-authorized workspace investigation produced the evidence described here.

No production source, upstream source or agent instructions were changed. No
hooks, assistant integration, credentials, model calls, database service, commit
or push were needed. The model transport probe uses a synthetic response and a
Python network guard. It is not a local-Qwen quality evaluation.

## Current implementation and reusable boundary

**OBSERVED — source:** there is a substantial importable Python implementation,
but no small, stable facade covering build/update/query. Updating and formatted
querying require internal functions or CLI orchestration.

| Stage | Central source and callable | Actual responsibility |
|---|---|---|
| Detect | [detect.py][detect], `detect`, `detect_incremental`, `save_manifest` | Classify files, honor ignore/exclusion rules, record hashes and scan changes; optional document conversions have additional dependencies |
| Extract | [extract.py][extract], `extract`; `extractors/`; `symbol_resolution.py`; `resolver_registry.py` | Cached per-file parsing followed by cross-file symbol/import/call resolution; returns extraction dictionaries, failures and token counts |
| Build | [build.py][build], `build_from_json`, `build`, `build_merge` | Normalize and merge IDs, validate shape, resolve aliases, prune invalid endpoints, synthesize external import nodes, construct NetworkX graph |
| Cluster | [cluster.py][cluster], `cluster` | Community partitioning; Leiden when available, NetworkX Louvain fallback; deterministic labels can avoid model use |
| Analyze | [analyze.py][analyze] | Individual functions such as `god_nodes`, `surprising_connections`, `suggested_questions`, `graph_diff`, `find_import_cycles`; no required model service |
| Persist | [export.py][export], `to_json`; [paths.py][paths] | Node-link JSON, community attributes, reports/HTML and atomic file replacement |
| Update | [watch.py][watch], `_rebuild_code`; [cli.py][cli] update dispatch | Select changed/live sources, extract, reconcile old/new layers, rebuild analysis and outputs |
| Query | [serve.py][serve], `_load_graph`, `_query_graph_text`, `_shortest_path_text`; NetworkX | In-memory graph access, lexical seed selection and bounded neighborhood traversal |
| MCP | [serve.py][serve], `_build_server`, `_build_http_app`, `serve` | Tool/resource formatting, graph context cache, stdio or Streamable HTTP transport |
| Semantic inference | [llm.py][llm] | Provider selection, file/chunk prompts, response parsing, caching and partial-result handling |

**OBSERVED — exercised seam:** the smallest demonstrated code/docs build is
`detect(root)` → select paths with deterministic extractors →
`extract(paths, root=root, cache_root=isolated_root, parallel=False)` →
`build_from_json(raw, directed=True, root=root)` → optional `cluster` → `to_json`.
The probe explicitly supplies Markdown to the deterministic extractor. Loading
the JSON into NetworkX is sufficient for exact node and edge queries; Graphify's
private loader additionally supplies its serving conventions.

**OBSERVED:** `_rebuild_code(root, changed_paths=...)` is the existing narrow
incremental seam. It is private, writes several artifacts, uses process-wide
output configuration and returns a Boolean rather than a detailed reconciliation
result. `python -m graphify update ROOT` invokes the same machinery with a
blocking update lock and a full live-source selection. There is no separate
public `ProjectKnowledge`, `query.py` service or pure transactional update API.

**OBSERVED:** `graphify extract ROOT --code-only` worked independently, but skipped
all 51 detected document files. It therefore does **not** demonstrate the same
deterministic code-plus-Markdown corpus as the direct library probe. The update
path also has document handling of its own; these entry points are not equivalent.

**OBSERVED — source:** skill documents, `skills/<host>/references`, `install.py`
and always-on integrations own assistant instructions, host registration,
automatic context injection and optional semantic-agent orchestration. They are
not needed to call the extractor or query a saved graph. Likewise, `reflect.py`,
saved answers and learned graph overlays are optional product behaviors, not
necessary structural indexing. [CLI][cli], [installer][install], [reflection][reflect].

**OBSERVED — source:** the core is local but not free of global state. Output
paths depend on import-time `GRAPHIFY_OUT`; extraction uses module-level resolver
caches/registries; file-hash caching includes process state and an exit flush;
provider settings are read from environment/configuration. Extraction also
adjusts process settings such as recursion limits. The experiment sets output
configuration before importing Graphify. **INFERRED:** multiple independent
project operations in one shared Python process need explicit isolation and
concurrency review; arbitrary re-entrant safety is not established.

## Determinism, provenance and confidence

**OBSERVED — source and probe:** code parsing and the selected Markdown/manifest
parsers execute without LLM inference. The primary extraction returned zero input
and output tokens with network connections blocked. Deterministic execution does
not make every emitted relation a direct source fact. [Extraction][extract],
[Markdown resolution][markdown-resolution], [model processing][llm].

| Knowledge category | Example | Current representation | Reliable distinction? |
|---|---|---|---|
| Direct source observation | Function declaration, explicit import, Markdown heading | Usually `_origin: ast`, file/location; edges commonly `EXTRACTED` | Locations help verify the claim; the category alone is not a formal proof |
| Deterministic derived relationship | Resolving an imported name to another file's symbol | Also `_origin: ast`, frequently `EXTRACTED` | No universal field separates parsing from resolver-derived facts |
| Deterministic heuristic | Bare Markdown code span matched to a unique symbol; callback argument treated as indirect call | `_origin: ast`, often `INFERRED`, numeric score and context | Partially visible, but not a consistent four-way provenance taxonomy |
| LLM-produced relationship or concept | Semantic interpretation of prose/config | Prompt confidence labels; `_origin: semantic` supported but not guaranteed on direct model output | Cannot safely infer model origin from confidence or location alone |

**OBSERVED:** all 930 initial persisted edges came through the deterministic tier;
922 were `EXTRACTED` and **8 were `INFERRED`**. Thus `INFERRED` does not mean
LLM-generated. Of 796 nodes, 748 had `_origin: ast`; 48 builder-generated external
import stubs had no origin. A later reconciliation backfilled these sourceless
stubs as `semantic` even though no model had run. [Primary results][results].

**OBSERVED — source and synthetic control:** `build._is_ast_tier` trusts an
explicit `_origin`, otherwise treats `source_location` starting with `L` and a
digit as AST-derived. The current `llm.extract_files_direct` output in the stubbed
test lacked `_origin`. Its synthetic model node with location `L1` was classified
as AST; changing the location to null classified it as semantic. This is a real
postprocessing observation using an artificial model response, not a claim about
what a particular model will output. [Build classifier][build-tier],
[boundary evidence][boundary].

**OBSERVED — source:** numeric confidence is a rule/prompt convention, not a
calibrated probability. Examples include `1.0` for direct calls, `.85` for a
callback relationship and `.95` for unique bare-name Markdown matches. Java
member inference also uses `.8`. Export defaults include `EXTRACTED: 1.0`,
`INFERRED: .55`, `AMBIGUOUS: .2` when scores are absent. Those values describe
different mechanisms; a high score does not establish semantic entailment.
[Java resolver][java-resolver], [export][export], [primary evidence][results].

**OBSERVED — source:** semantic evidence binding checks some code identifiers
against supplied text and may mark `verification: unverified`; it does not prove
edge meaning or all document claims. The persisted graph has no universal
per-claim source-content digest, extractor rule/version, model/prompt identity
and extraction revision. Some top-level extraction metadata does not become
per-edge provenance. MCP text commonly exposes source locations but omits
`_origin`, numeric confidence and verification fields. [LLM][llm], [MCP][serve].

**INFERRED:** callers cannot reliably recover the requested four categories from
arbitrary existing graph JSON. Trust must be attached to known extraction paths
and evidence, not retrospectively inferred from `EXTRACTED`/`INFERRED`. No such
Blaine wrapper or schema is designed in this experiment.

## Language and repository coverage

The following is **OBSERVED in source**; explicitly marked fixtures/tests add
empirical support. Absence of a relationship is not proof that source lacks it.

| Area | Current useful coverage | Material limitations for Blaine |
|---|---|---|
| Java | Tree-sitter declarations, classes/methods, imports, inheritance, references, calls; typed receiver/member resolution across files | No compiler-equivalent overload/type/dispatch analysis. Local/field receiver inference is heuristic; chained/ambiguous cases are limited. Fixture `run(int)` and `run(String)` collapsed to one method node. Java member/type tests passed |
| Go | Functions, types/interfaces, receiver methods, imports/aliases, package-qualified calls; `go.mod` helps local resolution | Not the Go compiler/type checker; runtime interface dispatch, build constraints and cgo are not established. Qualified-resolution tests passed |
| Python | Declarations, imports, calls, class/method relationships, some receiver/callback inference | Dynamic imports, monkey patching and runtime dispatch exceed static evidence. Actual Blaine imports/direct calls were independently checked with Python AST |
| Rust | Struct/enum/trait/impl/use topology, member/self calls and bounded generic-impl handling | No rustc analysis, macro expansion or complete trait/generic/cfg semantics. Self-member tests passed |
| SQL | Optional tree-sitter SQL grammar; tables/views and other schema objects, references and reads-from relationships | Object topology, not a complete column/constraint catalog or migration-applied database state. Dialect/error recovery is bounded. Table foreign-key and view fixtures passed; no database was queried |
| YAML/config | Recognized special formats such as `apm.yml`; Markdown frontmatter uses YAML parsing when available | Generic YAML and generic TOML fixtures had no deterministic extractor. Blaine's Restate TOML files were unclassified. Special filename support is not general config understanding |
| Markdown/docs | Pages, headings, frontmatter, explicit links and symbol mentions in code spans; deterministic doc/code linking | Does not understand arbitrary prose meaning. Bare-name matches can be semantically misleading; metadata cache counterexample below. Diagrams such as Blaine's `.puml` were unclassified |
| Maven | Deterministic `pom.xml` package/dependency declarations | Not effective-POM evaluation: parent/property/profile resolution and dependency scopes/management are not faithfully modeled. Raw XML dependency enumeration is not a resolved build graph |
| Gradle | Groovy/Kotlin language parsing available | No demonstrated Gradle dependency model. The Groovy dependencies fixture emitted only its file node, with no package dependencies |
| Other manifests | `pyproject.toml`, `Cargo.toml`, `go.mod`, `apm.yml/yaml` package ingestion | Partial declaration parsing, not resolver/lockfile truth. Blaine `requirements.txt` dependencies were absent. External dependencies can be discarded during graph build |
| Git | Commit stamp, change discovery, optional hooks and rebuilds | Not commit-history topology, rename lineage, or a branch/worktree snapshot database |

Source anchors: [extractor dispatcher and Java configuration][extract],
[Go extractor][go], [Rust extractor][rust], [SQL extractor][sql],
[manifest ingestion][manifest], [Markdown extractor][markdown],
[Git hooks][hooks]. Fixtures and targeted checks: [boundary][boundary], [checks][checks].

**OBSERVED:** the four manifest fixtures emitted four `depends_on` edges in raw
extraction. All four disappeared in `build_from_json` because their external
package targets were absent. External-node synthesis covers import-family edges,
not arbitrary dependency edges. Raw extraction and persisted graph therefore
answer different dependency questions. Package IDs are based on package name;
**INFERRED:** ecosystem/name collisions deserve care in mixed repositories.
[Manifest source][manifest], [builder][build], [fixture evidence][boundary].

**OBSERVED — source:** cross-language support is selective. Build-time language
families suppress implausible call/import/reference matches across unrelated
languages; some shared-language families are allowed. Docs can link to code,
and manifests can relate packages. This is not evidence of complete Java→SQL,
Go→Rust, HTTP-client→service or deployment-config→runtime topology.
**UNVERIFIED:** those application-level relationships in real Blaine projects.
[Builder guards][build], [Markdown resolution][markdown-resolution].

## Incremental update and freshness

**OBSERVED — source:** the normal flow is scan/extract/build → persist graph and
manifest → detect changed/deleted/excluded sources → parse selected sources using
per-file caches → reconcile → cluster/analyze → replace artifacts. Manifest
tracking separates AST and semantic hashes. Parsing caches have their own content
hash rules and namespaces. These are multiple mechanisms, not one atomic index
transaction. [Detection][detect], [cache][cache], [reconciliation][watch].

**OBSERVED:** node IDs largely normalize relative path, enclosing scope and name;
line number is not the identity. Identical source layouts at another root kept
the same IDs in the relocation control. Renamed symbols and moved files received
new IDs; old source definitions were pruned. There is no demonstrated rename
lineage or Java signature identity. Explicit root selection matters.
[IDs][ids], [primary results][results], [freshness results][freshness].

**OBSERVED:** a changed caller resolved an unchanged callee using existing graph
context. Removing/renaming definitions and moving/deleting files removed their
old definitions in the disposable Blaine clone. A warm complete extraction
reused all per-file parse results while still performing graph-level work.

Three counterexamples limit the freshness claim:

1. **OBSERVED:** adding a new callee while leaving its caller unchanged, then
   updating only the callee, did **not** create the direct call edge. A subsequent
   full rebuild did. Narrow changed-file updates do not establish complete inverse
   dependency invalidation. [Freshness evidence][freshness].
2. **OBSERVED:** changing only Markdown frontmatter from `review_status: draft`
   to `accepted` returned cached `draft`; direct cold parsing returned `accepted`.
   Cache hashing strips Markdown frontmatter even though the extractor emits it.
   This result concerns metadata values, not the different raw/normalized node IDs
   in the control. [Cache][cache], [freshness evidence][freshness].
3. **OBSERVED:** after inserting an explicitly synthetic semantic node associated
   with `docs/architecture.md`, editing that document and doing a code update kept
   the old semantic claim and omitted the new heading. The updater deliberately
   preserves semantic-backed documents instead of replacing them with AST-only
   output. A successful code update is not semantic freshness evidence.
   [Updater][watch], [mixed-layer evidence][results].

**OBSERVED — source:** full CLI update selects the live deterministic source set
and benefits from parse caching; hook/watch paths can supply narrower changed
paths. Thus the first counterexample should not be generalized to every CLI
update, while cache staleness remains relevant beyond narrow updates.

**OBSERVED:** checking out Blaine's existing parent commit in the disposable clone
and rebuilding changed `built_at_commit` to
`82bb32f1dcf4c2ca7d794c3cc92bd20c51a67ac6` and produced 760 nodes. No hooks were
required. **UNVERIFIED:** simultaneous independent worktrees and branch switching
during extraction. A top-level HEAD stamp does not encode uncommitted contents,
prove every semantic claim is current, or provide per-claim revision history.
An explicit `GRAPHIFY_OUT` can isolate outputs, but branch/worktree identity is
not an enforced storage key. [Results][results], [paths][paths], [hooks][hooks].

**OBSERVED — source:** update has an advisory `flock` on platforms providing
`fcntl`; library extraction/build and all output producers do not universally
share this lock. JSON publication uses temporary-file replacement; reports,
manifests, labels and snapshots are separate writes, without a common transaction.
There is no demonstrated crash-durable database transaction or cross-platform
multi-writer guarantee. Hooks are optional convenience; watcher dependencies are
also optional. [Watch/lock][watch], [atomic replacement][paths].

**OBSERVED:** during one actual CLI update, concurrent readers observed 573 old
and 30 new graph snapshots with no JSON parse errors. The graph context cache
reloaded and found the added sentinel while the old loaded object remained an
old snapshot. **INFERRED:** immutable reader snapshots plus atomic graph
replacement are useful for concurrent queries. **UNVERIFIED:** multiple writers,
power loss, Windows semantics, sidecar consistency and a repository modified
while being scanned. The single-writer Linux result is not a broader guarantee.

## Persistence, query and MCP boundary

**OBSERVED — source:** NetworkX plus node-link JSON is the operational graph
representation. The normal builder creates a simple `Graph` by default or
`DiGraph` with `directed=True`, not a multigraph. The serving loader can use a
directed object while retaining the original logical-directedness flag; inspecting
its Python class alone is insufficient to infer graph semantics. [Build][build],
[export][export], [loader][serve].

**OBSERVED:** a control containing `a→b calls`, `a→b references`, `b→a calls`
retained one edge in the default undirected graph and two in the directed graph.
The second relationship on the same ordered pair was still lost. Generic
relationships are deprioritized when collapsing pairs. **INFERRED:** canonical
JSON is a useful query projection but cannot be assumed to preserve every
extracted fact or its separate evidence. [Builder control][results].

**OBSERVED:** `graph.json` alone was enough to load and query the structural graph.
Observed auxiliary outputs included `manifest.json`, `.graphify_root`, label
files/signatures, reports, HTML, caches and dated snapshots. Efficient incremental
processing uses more than the graph alone; some MCP resources depend on reports
or sidecars. SQLite is not required by this core path; Neo4j/FalkorDB are optional
export destinations, not mandatory storage/query services.
[Artifacts][results], [database exporters][graphdb].

**OBSERVED — source:** built-in question retrieval uses lexical scoring, IDF and
trigram matching to choose seeds, followed by BFS/DFS neighborhood traversal.
It is not an LLM answering engine or an embedding database. Depth limits and
approximate character-based token budgeting produce compact context with
truncation notices. Queries need independent interpretation against source.
Clustering and degree rankings organize topology; they do not establish that a
high-degree concept is architecturally authoritative. [Query/formatting][serve],
[analysis][analyze].

**OBSERVED:** direct NetworkX shortest path from `runtime_app_run` to
`runtime_task_validate_request` was the expected single call edge. Graphify's
textual shortest-path function selected `request()` as the target even when
given those exact IDs, then reported no directed path. Endpoint search remains
heuristic in that function. This is a query-selection defect, not a missing
graph edge. [Boundary evidence][boundary].

**OBSERVED — source:** MCP exposes ten tools: `query_graph`, `get_node`,
`get_neighbors`, `get_community`, `god_nodes`, `graph_stats`, `shortest_path`,
`list_prs`, `get_pr_impact`, `triage_prs`. Resources cover reports, statistics,
hubs, surprising connections, audit and suggested questions. The PR tools add
GitHub/`gh` dependencies and product workflow; they were not invoked.
`project_path` selects server-readable graph locations, not a tenancy boundary.
Some caught failures are formatted as text, so callers must not treat transport
success alone as successful knowledge retrieval. [MCP implementation][serve].

**OBSERVED — source:** launch stdio with `python -m graphify.serve GRAPH_JSON`
or the `graphify-mcp` entry point. HTTP uses a Streamable HTTP `/mcp` endpoint,
defaults to loopback port 8080 and supports optional API-key authentication.
Stateful sessions and stateless operation are distinct modes. Serving adds
in-memory graph/index caches and, for HTTP, transport sessions; it does not own
Blaine task execution. Optional learned/reflection overlays can affect loaded
context, so it is not universally a stateless view of only one JSON file.
[Server][serve], [reflection][reflect].

**OBSERVED:** with the locked MCP 2.2.0 environment, stdio initialization timed
out both through the normal launcher and through a diagnostic factory+SDK
launcher without Graphify's stdin filter. The cause is **UNVERIFIED**; this does
not isolate a Graphify defect from SDK/environment behavior. The actual HTTP
ASGI app, exercised in process without a listener, returned HTTP 200 and valid
JSON-RPC results for initialize, tool listing and `get_node`. This establishes
the tool-handler/HTTP app path, not production HTTP deployment, authentication
or stateful sessions. [Transport control][factory].

| Consumption option | Assessment | Trade-off |
|---|---|---|
| A. Library | **OBSERVED:** works for deterministic build, persisted graph access and direct queries | Best access to raw attributes/exact IDs; application must control globals, persistence and internal update/query APIs |
| B. Local MCP | **OBSERVED:** HTTP app handlers work; **UNVERIFIED:** usable stdio in this environment | Convenient bounded textual context; loses provenance detail, inherits fuzzy matching and adds process/session management |
| C. Either | **INFERRED:** both are architecturally separable from Graphify's assistant workflow | Library is the stronger demonstrated seam; MCP adoption needs compatibility and evidence-format validation |

**OBSERVED:** the initial small-corpus pipeline processed 79 files in about
0.313 seconds, producing 796 nodes, 930 edges, 53 communities and 660,802 bytes
of JSON. Warm extraction alone took about 0.100 seconds, with no parser calls.
Those timings cover different scopes and are not a speedup benchmark.
**INFERRED:** medium/large repositories incur full JSON deserialization, Python
object overhead, index construction and graph-wide resolution/clustering costs;
the server retains whole graph contexts (bounded LRU plus pinned default).
**UNVERIFIED:** medium/large memory, latency and incremental throughput. No larger
benchmark was added after the evidence answered the carveout question.

## LLM dependence and local-Qwen feasibility

**OBSERVED — source:** `llm.extract_files_direct` and `extract_corpus_parallel`
own direct model inference for semantic document/config/media extraction and
deeper relationships. Optional semantic deduplication/community labeling can add
model work. Structural Markdown extraction itself is deterministic; semantic
interpretation of its prose is a separate operation. Skill-driven extraction
can use a host assistant instead of the standalone provider path. None is
required for the demonstrated code updates. [Model implementation][llm],
[CLI][cli], [build][build].

**OBSERVED — source and stub:** the Ollama backend uses an OpenAI-compatible
Chat Completions client, normally `http://localhost:11434/v1`, with configurable
model and a `qwen2.5-coder:7b` default. `OPENAI_BASE_URL`/model settings and custom
providers support other compatible servers. The transport control selected an
explicit synthetic Qwen model name and observed the expected client/request
shape, including Ollama context-window/keep-alive options. It made no network
request. Actual model output quality, memory requirements and throughput remain
**UNVERIFIED**. [Provider/transport code][llm], [stub result][boundary].

**INFERRED:** local Qwen through Ollama, or a Qwen deployment implementing the
required OpenAI-compatible calls, is feasible without architectural changes.
Select the backend explicitly: automatic provider selection can prefer available
hosted credentials. This experiment did not configure or consume credentials.
Endpoint compatibility and useful semantic graph quality still require separate
evidence; no such additional research is authorized by this report.

**OBSERVED — source:** normal code updates do not need expensive inference.
Semantic/deep passes can select a different backend/model and file set; deeper
passes use different extraction prompts/cache treatment. Caches do not establish
complete per-claim model lineage, and changing model alone is not a guarantee
that all semantic results are recomputed. **INFERRED:** selective stronger-model
passes are possible, but their freshness/cost must be explicit rather than
implied by a successful code update. [LLM][llm], [cache][cache], [update][watch].

## Empirical questions and limits

| Question/control | Recorded answer | Evidence classification |
|---|---|---|
| Does `runtime/app.py` import/call `validate_request`? | Import at L10 and call at L19 matched independently parsed Python AST and graph edges | **OBSERVED**, source fact and resolved edge |
| Does `run` directly call `summarize_objective`? | Source passes it as a callback at L26; graph says `indirect_call`, `INFERRED`, .85 | **OBSERVED**, illustrates a deterministic heuristic |
| Can docs point to runtime symbols? | Bare `cancel` in task-operation docs linked to `BlaineAgent.cancel`, `INFERRED`, .95 | **OBSERVED**, name match only; the actual method explicitly distinguishes ACP-turn cancellation from durable-task cancellation |
| Where do architecture concepts appear? | Lexical queries returned relevant ADR/heading/source references; broad questions also reached the prior MIRIX report | **OBSERVED**, useful navigation, not semantic truth or system integration |
| Does the graph contain Blaine's declared Python dependency inventory? | No nodes from `runtime/requirements.txt` for its three declared dependencies | **OBSERVED**, coverage gap |
| Can the artifact survive reload and update? | Roundtrip, changed caller, rename/move/delete pruning, commit stamp and cache reload succeeded | **OBSERVED**, bounded scenarios |
| Are all incremental/freshness cases correct? | No: unchanged caller/new callee, frontmatter-only edit and mixed semantic/doc update counterexamples | **OBSERVED**, failures retained |
| Is querying lossless and exact? | No: parallel relationships collapse; textual shortest-path endpoint differs from exact NetworkX ID lookup | **OBSERVED**, distinct build/query limitations |
| Can MCP expose the graph independently? | HTTP ASGI initialize/list/get-node succeeded; stdio initialization timed out | **OBSERVED**; root cause/deployment readiness **UNVERIFIED** |
| Is local Qwen verified? | Only backend/request construction and synthetic-response postprocessing were exercised | **UNVERIFIED** for actual inference |

The existing targeted upstream run passed **94 tests in 0.94s**, covering Java
member/type resolution, Go qualified resolution, Rust self-member calls,
manifest ingestion, Markdown code spans and the inferred-confidence rubric.
This supports those selected cases, not completeness or provenance safety.
Finalization validated existing evidence rather than rerunning or broadening
the investigation. [Checks][checks], [probe code][probe].

## Fit with Blaine

| Class | Concept/behavior | Finding and boundary |
|---|---|---|
| HARVEST | Local parser/resolver pipeline | **OBSERVED:** useful structural extraction independent of assistant workflow or runtime services |
| HARVEST | Source-addressable nodes and graph neighborhoods | **OBSERVED:** practical navigation and compact context seeds; consistent with retrieval-first project knowledge |
| HARVEST | Per-file parse reuse, reconciliation and atomic graph publication | **OBSERVED:** useful mechanisms with the documented invalidation/concurrency limits |
| HARVEST | Graph analytics and communities | **OBSERVED:** local topology tools; **INFERRED:** useful context organization rather than authority ranking |
| ADAPT | Provenance and confidence | **OBSERVED:** origin/category gaps; **INFERRED:** evidence must retain derivation method and source version before trustworthy use |
| ADAPT | Canonical storage fidelity | **OBSERVED:** simple graphs discard parallel relationships and some external dependencies; preserving raw evidence matters |
| ADAPT | Freshness and worktree identity | **OBSERVED:** HEAD stamp and narrow reconciliation are insufficient; **INFERRED:** claim freshness must be assessed against the selected source snapshot |
| ADAPT | Query result semantics | **OBSERVED:** fuzzy endpoint selection and omitted provenance; exact identity and evidence-bearing output need deliberate handling |
| ADAPT | Global configuration and lifecycle | **OBSERVED:** mutable/import-time process state; **INFERRED:** isolate indexing/serving operations before sharing them among tasks |
| REJECT | Agent install/always-on workflow, automatic instruction edits and hooks | Product responsibility outside this carveout; unnecessary for Project Knowledge |
| REJECT | Saved-answer/learned memory as Blaine personal/task memory | Would cross the intended MIRIX/Graphify responsibility boundary; do not import it as memory authority |
| REJECT | GitHub PR triage and graph-guided agent work management as runtime | Blaine's durable Task/runtime boundary remains independent |
| REJECT | Graph as authoritative source or proof of execution | Source/Git and runtime evidence own those claims; a derived graph cannot establish them |
| INVESTIGATE | Java semantic precision, application cross-language topology, large-repo costs | **UNVERIFIED** beyond the bounded source/tests/fixtures |
| INVESTIGATE | Multi-writer/worktree isolation, crash consistency, stdio interoperability | **UNVERIFIED**; single-writer Linux and in-process HTTP evidence do not settle them |
| INVESTIGATE | Actual Qwen semantic extraction and selective stronger-model quality | **UNVERIFIED**; compatible transport is not useful-knowledge evidence |

MIRIX remains the separate candidate for personal/episodic/semantic/procedural
memory. Graphify's relevant responsibility is derived project/code structure,
relationships and retrievable evidence. No data was merged between them, and no
context resolver or ProjectKnowledge interface is proposed here.

## Remaining questions and stop decision

The remaining uncertainties are bounded: an enforceable provenance taxonomy;
preservation of multiple facts per entity pair; complete dependency invalidation
and document freshness; explicit dirty-tree/worktree identity; multi-writer and
crash behavior; stdio compatibility; real-language precision at project scale;
and semantic quality/cost with actual local Qwen. They are future adoption
questions, not missing work in this carveout.

**INFERRED — decision supported by the evidence:** retain Graphify as an **ADAPT
candidate**, with the deterministic library seam as the strongest demonstrated
starting point. The answer to independence is yes. The answer to trustworthy,
incrementally current, provenance-aware Project Knowledge **as shipped at this
SHA** is no. That answers the experiment's stop condition. No integration follows.

[probe]: ../../experiments/graphify-carveout/README.md
[results]: ../../experiments/graphify-carveout/results.json
[boundary]: ../../experiments/graphify-carveout/boundary-results.json
[factory]: ../../experiments/graphify-carveout/factory-results.json
[freshness]: ../../experiments/graphify-carveout/freshness-results.json
[checks]: ../../experiments/graphify-carveout/upstream-checks.txt
[task]: ../../experiments/graphify-carveout/task-request.json
[detect]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/detect.py
[extract]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/extract.py
[build]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/build.py
[build-tier]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/build.py#L45
[cluster]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/cluster.py
[analyze]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/analyze.py
[export]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/export.py
[paths]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/paths.py
[watch]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/watch.py
[cache]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/cache.py
[ids]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/ids.py
[cli]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/cli.py
[serve]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/serve.py
[llm]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/llm.py
[install]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/install.py
[reflect]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/reflect.py
[java-resolver]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/extract.py#L4251
[go]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/extractors/go.py
[rust]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/extractors/rust.py
[sql]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/extractors/sql.py
[manifest]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/manifest_ingest.py
[markdown]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/extractors/markdown.py
[markdown-resolution]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/markdown_resolution.py
[hooks]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/hooks.py
[graphdb]: https://github.com/Graphify-Labs/graphify/blob/b9cd9570728a5ff3485d2a1e36fe9a1272a368ae/graphify/exporters/graphdb.py
