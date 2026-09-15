# ADR 0005 — Semantic triage selects the work strategy

**Status:** Accepted
**Validation:** Unvalidated

## Context

A user request does not imply a particular model, worker, or workflow.

Some requests are satisfied by conversation. Some are best answered through a
deterministic tool. Some require a small durable Task. Others justify
investigation, structured specification, multiple dependent phases, or explicit
human decisions.

Choosing a worker too early couples user intent to implementation details such as
the currently loaded local model or an available cloud agent. It also encourages
over-processing simple requests and under-structuring consequential work.

Blaine needs a semantic decision boundary before worker and model selection.

## Decision

The Personal Agent performs semantic triage before selecting workers, models, or
execution infrastructure.

It chooses the minimum work strategy that preserves the user's objective,
constraints, required quality, and verification needs.

Representative strategies include:

- `DIRECT` — the conversational response itself satisfies the request.
- `DIRECT_TOOL` — a deterministic or authoritative tool can produce the required
  fact or result without an independent durable lifecycle.
- `SIMPLE_TASK` — bounded durable work with an obvious outcome and limited
  execution structure.
- `INVESTIGATION` — evidence must be gathered, compared, or interpreted before a
  supported conclusion can be produced.
- `SPEC_DRIVEN` — ambiguity, blast radius, dependent deliverables, or
  architectural consequences justify explicit requirements and planning phases.
- `COMPOSED` — the objective is too broad for one workflow and should be
  decomposed into multiple independently manageable Tasks or workflows.

These names describe useful starting strategies, not a closed taxonomy and not
runtime lifecycle states.

The Personal Agent may choose a different or progressively stronger strategy as
new evidence changes the character of the work.

Worker/model selection happens only after the work strategy and required
capabilities are understood.

Therefore:

`SPEC_DRIVEN` does not imply a particular cloud model.

`INVESTIGATION` does not imply a particular local model.

`DIRECT_TOOL` does not imply model inference at all.

## Triage considerations

The Personal Agent should consider properties of the request rather than relying
on a single numeric complexity score.

Relevant signals include:

- whether a deterministic or authoritative tool can satisfy the request;
- whether work needs an independent lifecycle;
- ambiguity in requirements or desired outcome;
- blast radius and cost of being wrong;
- reversibility of proposed actions;
- number of dependent steps or deliverables;
- architectural novelty;
- required human decisions or approvals;
- context size and distribution across sources;
- verification difficulty;
- whether the work fits within one bounded worker execution.

These signals inform judgment; they are not a mandatory form the user must fill
out and are not required fields in TaskSpec.

## Boundaries

Semantic triage decides how much process the intent deserves.

It does not:

- own Task lifecycle;
- implement waits, retries, scheduling, or recovery;
- choose a concrete model before required capabilities are known;
- bypass user authorization or autonomy constraints;
- treat agent confidence as completion evidence;
- require every request to become a Task.

Restate remains authoritative for durable workflow state.

Concrete workflow families, including SpecKit-style structured development, are
separate decisions.

Tool-versus-inference precedence, worker selection, cloud dispatch, and resource
scheduling are also governed separately.

## Consequences

Simple interactions remain simple.

Durable work gains only the amount of workflow structure justified by the
request.

Worker and model choices can evolve independently from user-facing semantics.

The same Personal Agent can handle coding, research, investigation, monitoring,
and other work without forcing them into one workflow.

Triage is inherently semantic and therefore suitable for bounded model inference,
while lifecycle enforcement remains deterministic.

Misclassification remains possible. Strategies must therefore be observable and
revisable rather than hidden permanent decisions.

## Validation

### Hypothesis

A Personal Agent can reliably distinguish requests that need materially different
amounts of process without selecting a concrete worker/model or owning durable
lifecycle state.

### Validation level

Isolated.

### Minimal validation

Evaluate a local-model-backed triage function against a small set of
representative natural-language requests.

The validation should include at least:

1. a conversational question that should remain `DIRECT`;
2. a deterministic lookup that should become `DIRECT_TOOL`;
3. small bounded work that should become `SIMPLE_TASK`;
4. a read-only diagnostic request that should become `INVESTIGATION`;
5. a high-blast-radius architectural change that should become `SPEC_DRIVEN`;
6. an objective intentionally too broad for one workflow that should be
   recognized as requiring decomposition or `COMPOSED` work.

For each request, capture:

- selected strategy;
- short rationale based on observable triage signals;
- required capabilities at a semantic level;
- whether durable work is required;
- whether clarification or approval is required.

No real worker needs to execute the resulting work.

### Evidence

PASS requires that:

- obviously conversational requests are not turned into Tasks;
- deterministic lookups do not become model-heavy workflows;
- bounded execution is not escalated to structured specification without reason;
- read-only constraints survive triage;
- consequential or ambiguous architectural work receives stronger workflow
  structure;
- worker/model names are absent from the semantic decision unless explicitly
  supplied as a user constraint;
- the triage output contains no runtime lifecycle state;
- repeated evaluations are sufficiently stable to support routing decisions.

Individual strategy labels are less important than preserving the architectural
boundary and choosing proportionate process.

### Not required for validation

- Restate integration;
- real Task creation;
- SpecKit execution;
- Codex or another paid cloud worker;
- GPU scheduling;
- MCP;
- context reduction;
- protected-context transformation.

### Reconsider when

Reconsider this decision if representative workloads show that:

- work strategy cannot be chosen meaningfully before worker selection;
- semantic triage routinely adds more process than it saves;
- strategy boundaries are too unstable to drive useful behavior;
- a simpler deterministic routing policy performs equally well on real workloads.
