# ADR 0007 — Deterministic tools precede model inference

**Status:** Accepted
**Validation:** Unvalidated

## Context

Language models are useful for semantic judgment, interpretation, synthesis,
planning, and decisions under ambiguity.

They are a poor substitute for authoritative or deterministic mechanisms that
can directly establish a fact or produce a result.

Examples include:

- searching files;
- matching text;
- parsing structured data;
- performing calculations;
- querying runtime state;
- inspecting Git state;
- checking network reachability;
- running tests;
- reading an authoritative API or database.

Using model inference where a direct tool is sufficient wastes compute, adds
latency, and replaces observable results with probabilistic guesses.

This applies to local inference as well as paid cloud inference.

Local inference may be abundant, but it is not more authoritative than a tool.

## Decision

Blaine prefers the cheapest reliable mechanism capable of satisfying the
required operation.

The default precedence is:

1. authoritative or deterministic tools;
2. local model inference;
3. paid cloud inference.

A model should orchestrate, select, parameterize, and interpret tools rather than
imitating work the tools can perform directly.

Escalation to model inference is justified when the work actually requires
semantic capability such as:

- interpretation;
- synthesis;
- ranking;
- classification;
- planning;
- ambiguity resolution;
- judgment across evidence.

When inference is required, local inference is preferred when it can satisfy the
required quality and capabilities.

Paid cloud inference is considered only after local capability is insufficient
or materially lower quality for the required outcome, and remains subject to
cloud authorization and egress policy.

## Relationship to semantic triage

ADR 0005 chooses the work strategy before worker/model selection.

A request classified as `DIRECT_TOOL` should normally terminate through a tool
result plus only the interpretation needed to present that result.

A durable Task may also contain tool-only phases.

Creating a Task does not imply that an LLM must execute every phase.

For example, a Task may use deterministic tools to gather evidence before any
model is asked to interpret it.

## Authority

Tool preference is about epistemic authority as well as cost.

When an authoritative source can answer a question, its result is evidence.

A model prediction about that same fact is not equivalent evidence.

Examples:

- runtime status comes from the runtime;
- test success comes from the test runner;
- file contents come from the filesystem or repository;
- network reachability comes from an actual probe;
- arithmetic comes from deterministic computation.

Models may explain these results, but should not replace them.

## Boundaries

This decision does not mean that:

- every semantic request must invoke a tool;
- tool output is automatically sufficient for the user's objective;
- local inference is discouraged;
- paid cloud inference is forbidden;
- tools may bypass Task autonomy, authorization, or safety constraints;
- a deterministic mechanism should be built when no suitable one already exists.

Do not create unnecessary tooling solely to avoid model inference.

The rule is to prefer an available reliable mechanism when it already answers
the question or performs the required operation.

## Consequences

Simple factual operations become cheaper, faster, and more verifiable.

Local models are reserved for work that benefits from model capabilities rather
than being used as expensive implementations of basic utilities.

Cloud escalation starts from grounded evidence instead of asking a paid model to
rediscover facts that the local environment can provide directly.

Task workflows may contain phases with no model invocation at all.

The Personal Agent and workers need access to capability metadata so they can
recognize when a suitable tool exists.

Tool selection itself may still require bounded semantic reasoning.

## Validation

### Hypothesis

A Personal Agent can reliably prefer available deterministic tools for requests
whose core operation is directly executable, while still invoking model
inference when semantic judgment is genuinely required.

### Validation level

Isolated.

### Minimal validation

Evaluate a local-model-backed decision function against paired requests covering
both deterministic operations and semantic reasoning.

Include cases such as:

- find references to a symbol -> repository/text search;
- calculate a value -> calculator/deterministic computation;
- determine whether a host responds -> network probe;
- report current Task state -> runtime query;
- determine whether tests pass -> test runner;
- explain why observed test failures share a cause -> model interpretation;
- compare architectural alternatives -> model reasoning;
- summarize evidence gathered by several tools -> model synthesis.

The validation may use stub tools that record which capability was selected.

No real cloud model is required.

### Evidence

PASS requires that:

- requests directly answerable by an available deterministic tool select that
  tool before model inference;
- the model does not fabricate the result of an unexecuted tool;
- authoritative results remain distinguishable from model interpretation;
- semantic requests still invoke inference when deterministic output alone is
  insufficient;
- tool output can become input to subsequent local inference;
- no paid cloud worker is required for the validation;
- selection remains proportionate rather than mechanically invoking every
  available tool.

### Not required for validation

- Restate integration;
- SpecKit;
- Codex or another paid cloud agent;
- GPU scheduling;
- MCP;
- Cloud Context Packets;
- protected-context transformation;
- implementation of new deterministic tools.

### Reconsider when

Reconsider this decision if:

- tool-selection overhead consistently exceeds its reliability or cost benefit;
- representative semantic workloads are degraded by excessive tool-first
  decomposition;
- a model-backed operation demonstrably provides stronger authority than the
  available deterministic mechanism for a particular domain.

Such exceptions should remain explicit rather than weakening the default rule.
