# ADR 0010 — Worker selection is capability and quality driven

**Status:** Accepted
**Validation:** Unvalidated

## Context

Blaine may execute work using several kinds of capabilities:

- deterministic tools;
- local models;
- local agent workers;
- paid cloud agents;
- future specialized workers.

These capabilities differ in quality, cost, latency, context capacity,
availability, tool access, mutation ability, and operational constraints.

Work strategies such as investigation or spec-driven development describe how
work should be structured. They should not permanently determine which concrete
worker or model performs that work.

Hardcoding mappings such as:

- investigation -> local model A;
- specification -> cloud model B;
- implementation -> coding agent C;

would couple workflow semantics to today's model landscape.

It would also prevent Blaine from taking advantage of a currently available or
already-resident worker that is sufficient for the required outcome.

## Decision

Worker selection happens after the work strategy and phase requirements are
understood.

Blaine selects workers based on the capabilities and quality required for the
specific operation.

The selection process should answer:

1. What capabilities does this operation require?
2. What quality threshold is required?
3. Which eligible worker can satisfy those requirements?
4. Among sufficient workers, which option best fits current policy and resource
   constraints?

A work strategy does not name a concrete worker.

A workflow phase describes its required outcome and capabilities.

Worker selection resolves those requirements to an available implementation.

## Capability requirements

Representative capability requirements may include:

- semantic classification;
- technical reasoning;
- repository search;
- repository understanding;
- code mutation;
- test execution;
- shell or tool execution;
- large-context synthesis;
- architectural planning;
- independent critique;
- structured output;
- access to a particular local or connected source.

This list is illustrative rather than a fixed schema.

Capabilities should describe what the work requires rather than which product is
expected to perform it.

## Quality requirements

Capability alone is insufficient.

Two workers may technically support the same operation while producing materially
different outcome quality.

Selection may therefore consider requirements such as:

- expected reasoning quality;
- reliability;
- verification difficulty;
- cost of being wrong;
- blast radius;
- architectural novelty;
- required independence from the worker that produced an earlier result.

Quality requirements should remain proportional to the work.

A low-risk classification does not need the strongest available model merely
because that model is accessible.

A consequential architectural review may justify escalation even when a weaker
worker could technically produce an answer.

## Selection order

ADR 0007 establishes the default precedence:

1. deterministic or authoritative tool;
2. local inference;
3. paid cloud inference.

Within that precedence, worker selection asks whether the currently available
option satisfies the required capability and quality.

Conceptually:

available authoritative tool sufficient?
-> use tool

otherwise:

eligible local worker sufficient?
-> use local worker

otherwise:

paid cloud materially justified and authorized?
-> request cloud dispatch

otherwise:

-> remain local with explicit limitations, choose another strategy, or surface a
   blocked/decision state as appropriate

The exact scoring or ranking algorithm is intentionally unspecified.

## Local worker selection

Local inference is financially abundant for Blaine, but local workers still
consume finite machine resources.

Selection should prefer a suitable local worker when it can satisfy the required
quality.

It should not switch models solely because another local model has a theoretical
advantage for a task category.

For example, if the currently resident model is sufficient for a classification
operation, Blaine should normally use it rather than force an unnecessary model
swap.

GPU residency, contention, switching cost, priority, and queuing are separate
runtime/resource concerns addressed by a later decision.

Worker Selection determines eligible candidates that satisfy semantic capability
and quality requirements. Under the scheduler proposal in ADR 0011, the Local
Inference Scheduler allocates/schedules only among these selector-approved
candidates. Residency, queue latency, and switching cost may influence which
eligible candidate runs; the scheduler MUST NOT relax capability or quality
requirements. If none can currently execute, scheduling may wait or request
reselection according to policy.

These resource concerns do not become workflow semantics.

## Cloud worker selection

A paid cloud worker is selected only when its capability or expected quality
materially justifies escalation.

Cloud selection remains subject to:

- ADR 0008's Cloud Dispatch Boundary;
- cloud authorization;
- provider/worker allowlists;
- budget policy;
- ADR 0009's Cloud Context Packet requirement;
- context-egress policy.

The worker selector cannot authorize cloud by itself.

Selecting a cloud worker means:

> This worker appears suitable if dispatch is permitted.

It does not mean:

> Dispatch is authorized.

## Worker identity

Concrete workers and models are implementations, not architectural task types.

Names such as Qwen, Nemotron, Codex, Astra, or future alternatives may appear in
runtime configuration, capability registries, adapters, evaluations, or policy.

They should not be required in generic workflow definitions.

A workflow should survive replacement of one worker implementation by another
that satisfies the same required capabilities and quality.

## Independent workers

Some phases may intentionally require a worker distinct from the one that
produced an earlier result.

Examples include:

- independent review;
- adversarial critique;
- verification of a proposed plan;
- comparison of competing solutions.

Independence is therefore itself a possible selection constraint.

It should be requested because the workflow needs independent judgment, not
because Blaine mechanically uses multiple agents for every task.

## Dynamic selection

Worker selection may change between workflow phases.

For example:

SPECIFY
-> local worker

PLAN
-> higher-capability cloud worker

IMPLEMENT
-> coding worker

VERIFY
-> deterministic tests plus independent reviewer

The workflow remains the same even if the concrete workers change.

Selection may also be reconsidered after failure or evidence that the current
worker is insufficient.

Such reconsideration must not allow silent bypass of authorization, budget, or
egress policy.

## Boundaries

Worker selection does not:

- perform semantic triage;
- define the work strategy;
- own Task lifecycle;
- authorize paid cloud usage;
- prepare unrestricted cloud context;
- manage durable GPU queues;
- treat the strongest model as the default;
- require one model per task type;
- guarantee completion merely because a capable worker was selected.

The Durable Runtime remains authoritative for execution lifecycle.

Verification remains authoritative for whether required outcomes were achieved.

## Consequences

Workflow semantics become independent from today's model landscape.

Blaine can replace workers without redefining Task or SpecKit-style workflow
semantics.

Local inference can be preferred when sufficient without making local execution
an absolute rule.

Cloud escalation becomes a quality/capability decision constrained by explicit
authorization and egress boundaries.

Worker specialization remains possible without becoming hardcoded architecture.

Selection introduces the need for capability metadata, worker evaluations, and
policy-driven comparison.

These can evolve progressively rather than requiring a complete scheduler or
scoring system in v0.

## Validation

### Hypothesis

Blaine can select suitable workers from semantic capability and quality
requirements without encoding task-type-to-model mappings.

The same workflow definition should remain valid when concrete workers are
replaced by other workers with equivalent capabilities.

### Validation level

Isolated.

### Minimal validation

Create a fake worker registry containing several workers with intentionally
different properties.

For example:

- deterministic repository search;
- a low-cost local semantic worker;
- a stronger local semantic worker;
- a paid cloud coding/reasoning worker;
- a worker without mutation capability.

Represent properties such as:

- supported capabilities;
- approximate quality tier;
- local versus paid;
- tool access;
- mutation ability;
- availability;
- optional independence constraints.

Evaluate several phase requirements against the registry.

Include at least:

1. a deterministic operation resolved to a tool;
2. a semantic classification satisfied by an available local worker;
3. a task where a stronger worker is unnecessary;
4. an operation whose quality requirement exceeds available local capability;
5. a mutation phase that rejects a read-only worker;
6. an independent-review phase that cannot reuse the producing worker;
7. a cloud-suitable result whose dispatch is still denied by cloud policy;
8. replacement of one worker with an equivalent implementation without changing
   the workflow request.

No real model execution is required.

### Evidence

PASS requires demonstrating that:

- workflow requests contain capability/quality requirements rather than concrete
  model names;
- deterministic tools win when they directly satisfy the operation;
- a sufficient local worker is preferred over unnecessary cloud escalation;
- the strongest available worker is not selected automatically;
- workers missing required capabilities are rejected;
- an independent-review constraint is enforceable;
- selecting a paid worker does not bypass cloud authorization;
- swapping equivalent workers does not require changing workflow semantics;
- selection output clearly distinguishes suitability from authorization;
- no Task lifecycle state is owned by the selector.

### Not required for validation

- real Qwen or Nemotron execution;
- Codex or Astra;
- paid tokens;
- Restate integration;
- SpecKit execution;
- IntelliJ;
- MCP;
- Cloud Context Packet implementation;
- GPU scheduling;
- production-quality worker scoring;
- benchmarking every available model.

### Reconsider when

Reconsider this decision if:

- representative work requires task-type-specific worker semantics that cannot be
  expressed through capabilities;
- capability metadata becomes more complex than explicit worker selection;
- quality requirements cannot be evaluated well enough to influence routing;
- dynamic worker replacement causes unacceptable behavioral instability;
- operational constraints dominate semantic capability so strongly that a
  different selection model is required.

Such evidence may change the selection mechanism without coupling workflow
semantics directly to concrete model identities.
