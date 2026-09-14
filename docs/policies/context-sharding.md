# Context Sharding & Artifact-Based Delegation Policy

When investigation or codebase analysis would materially pressure the coordinator's context window — beyond what conversation history can carry without degrading working fidelity — decompose the work into coherent research units and delegate those units to workers with fresh context windows.

This is **context sharding**: treating multiple worker context windows as external storage rather than expecting the coordinator to hold all raw evidence in its own working memory. Multiple workers may process substantially more aggregate context than fits in one coordinator window; this is intentional. Do not attempt to merge all raw worker context back into the coordinator.

## When to shard

Shard when:
- An investigation or analysis task would materially overflow the coordinator's working context if pursued as a single flow (deep dependency tracing across many files, cross-repository audit, broad architecture review, etc.).
- Decomposing along subsystem/component boundaries reduces wall-clock time without losing meaningful relationships between units.

Do **not** shard when:
- Tasks are small or tightly coupled; decomposition would increase coordination cost or lose important contextual relationships. See [triage-routing.md](triage-routing.md) for size thresholds.
- One agent can reason about the sub-units jointly — conceptual coherence trumps file count. If coupling or dependency structure is unclear, **require** a brief discovery/scout pass to map the dependency graph and use that evidence to choose parallel fan-out vs. sequential sharding before decomposing.

## Artifact conventions — what workers produce

Workers write structured artifacts to **persistent working storage** (project directories, task files) instead of returning long transcripts into the coordinator's context. These artifacts serve as **external working memory**, not authoritative ground truth. They must preserve enough structure to support later synthesis:

Artifact sections (**only relevant sections** — do not fabricate content for empty sections):

| Section | Purpose |
|---------|---------|
| Responsibility | What this component / module / service is for |
| Public API / inputs / outputs | Surface contract and data flow boundaries |
| Dependencies | External modules, libraries, services, infra it relies on |
| Execution flow | Entry points, hot paths, decision trees in critical paths |
| State mutations / side effects | What changes externally (DB writes, filesystem, network calls) |
| Errors / failure paths | Exception classes, retry logic, degradation modes |
| Transaction or consistency boundaries | ACID scopes, eventual-consistency zones, idempotency claims |
| Security assumptions | Threat model perimeters, trust boundaries, auth assumptions |
| Invariants | Properties that must always hold; assertions worth noting |
| Important calls into other components | Cross-cutting dependencies not captured above |
| Evidence / source references | File paths, line ranges, commit hashes, SQL queries — enough to retrieve the original |
| Uncertainties | Explicitly marked gaps, partial evidence, hypotheses pending verification |

### Evidence provenance

Every artifact section that cites observed facts must include path-to-original-evidence (file, line/function, commit, query) so the coordinator can retrieve the source again when needed. **Summaries are not ground truth.** Align with the canonical principle: **Observable evidence > worker claims.** Observable source state, Git state, tool results, and other authoritative evidence remain higher priority than compressed worker findings or agent claims.

When making a material implementation, correctness, security, or architectural conclusion that depends on compressed worker findings, re-check the relevant original evidence when reasonable — do not treat worker artifacts as final authority.

## Artifact lifecycle

1. **Workers write to durable paths.** Use files in the project tree (e.g., under `reviews/`, `reports/`, or a task-specific directory) so the coordinator can selectively retrieve them on demand.
2. **Workers must distinguish directly observed evidence from inference.** Each artifact section should be annotated clearly: `[OBSERVED]` for facts obtained via tool results or source inspection; `[INFERENCE]` for conclusions drawn by the worker that have not been directly verified.
3. **Coordinator synthesizes selectively.** Read only the artifacts and sections relevant to the current reasoning step — do not pre-load all worker output at once. Retrieve deeper evidence (original files, Git state) only when a synthesized conclusion warrants re-checking.
4. **Durable storage > conversation continuity.** Completion should leave durable state in artifacts/files/Git where useful rather than relying on a long-lived chat transcript to carry workflow state across sessions or compaction events.

## Worker → Coordinator handoff

After delegated research, a worker completion response must **not** include the worker's full artifact, raw source inspection, or investigation transcript copied back into the coordinator's context. A normal completion response should contain only:

- Artifact location (path to durable storage);
- Concise findings summary;
- Material uncertainties or blockers that require coordinator attention;
- Critical evidence requiring immediate coordinator review.

The coordinator retrieves worker artifacts selectively and on demand, rather than eagerly ingesting every artifact after workers finish. This preserves the rule that raw worker context must not be merged back into coordinator context, and that artifacts are external working memory — not authoritative ground truth.

## Coordinator synthesis rules

- Synthesize from compact artifacts and retrieve only what the current reasoning step demands. The coordinator's role is judgment — not re-holding all raw context that workers already compressed into evidence-backed summaries with references.
- When synthesizing a cross-cutting conclusion (e.g., architectural assessment, security audit summary), verify internal consistency across artifact boundaries before finalizing. If artifacts conflict on a point of substance, treat it as an uncertainty and seek resolution rather than silently picking one side.
- Before any action that depends on compressed findings — implementation decisions, correctness claims, security judgments — check the original evidence when reachable. This is not mandatory boilerplate for every synthesized finding; it is scoped to what matters: conclusions that would materially change if a worker's inference were wrong.

## Remote capability compatibility

This sharding model is compatible with remote capability providers (IntelliJ MCP, cloud IDEs, etc.): multiple workers may inspect the same remote source repository through their respective tools concurrently while all inference — decomposition decisions, artifact synthesis, verification judgments — remains local to the coordinator. Each worker's context window and its remote tool access remain independent; nothing requires the coordinator to merge raw outputs or share remote state with other workers.

Artifacts produced by workers using remote tooling should follow the same structure and provenance rules to remain interoperable with locally-produced artifacts.

## Cross-references

| Resource | Location |
|----------|---------|
| Triage size thresholds (small/medium/large) for shard decisions | [triage-routing.md](triage-routing.md) |
| Fan-out criteria, builder-critic, reader/writer isolation | [orchestration.md](orchestration.md) |
| Keep-vs-delegate criteria; provenance & secret exclusion | [local-first-and-context.md](local-first-and-context.md) |
| Completion states, verification-pass levels | [task-completion-and-lifecycle.md](task-completion-and-lifecycle.md) |
