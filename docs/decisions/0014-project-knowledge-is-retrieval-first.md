# ADR 0014 — Project knowledge is retrieval-first, training-last

**Status:** Proposed
**Validation:** Deferred

## Context

Blaine may operate across several projects with distinct:

- codebases;
- terminology;
- architecture;
- conventions;
- historical decisions;
- operational knowledge;
- privacy requirements;
- rates of change.

A future optimization may appear attractive:

> Train or specialize a model for each project.

That approach can embed useful domain knowledge into model behavior, but it also
creates difficult questions around:

- what data entered training;
- whether restricted information was included;
- whether model weights can memorize sensitive material;
- how stale knowledge is updated;
- how project versions are represented;
- how data is removed;
- whether one project's model may be reused elsewhere;
- how model artifacts themselves must be protected and governed.

Much of the apparent need for project-specific training may instead be a context
retrieval problem.

Blaine should therefore establish a default progression for introducing
project-specific knowledge.

## Decision

Project-specific knowledge is retrieval-first and training-last.

Blaine should first represent project knowledge as explicit, addressable context
that can be discovered, ranked, selected, and supplied when needed.

The preferred progression is:

1. project instructions and harness;
2. addressable project context;
3. context catalog and metadata;
4. retrieval, ranking, and selection;
5. local synthesis using retrieved context;
6. evaluated model adaptation only when justified;
7. fine-tuning or project-specialized models only after evidence shows that
   retrieval-based approaches are insufficient.

A project-specific model is not the default mechanism for teaching Blaine about
a project.

## Project instructions

Stable behavioral expectations should first live in explicit project
instructions.

Examples include:

- coding conventions;
- architectural boundaries;
- repository usage rules;
- testing expectations;
- definitions of done;
- preferred workflows;
- local terminology.

Instructions are visible, reviewable, versionable, and easy to change.

They should not be hidden inside model weights when a normal document or
configuration is sufficient.

## Addressable project context

Project knowledge that changes over time should remain addressable.

Examples include:

- source files;
- ADRs;
- specifications;
- documentation;
- issue history;
- generated artifacts;
- runtime evidence;
- architecture diagrams;
- selected conversations or decisions;
- connected project systems.

Blaine should prefer references to authoritative sources over copying their
knowledge permanently into model behavior.

This allows project knowledge to evolve without retraining a model.

## Context Catalog

A future Context Catalog may index and describe available project knowledge.

The catalog may eventually capture metadata such as:

- source;
- project;
- scope;
- freshness;
- sensitivity;
- authority;
- semantic topics;
- provenance;
- sharing policy.

The exact catalog implementation is not defined by this ADR.

Its purpose is to make context discoverable and selectively retrievable rather
than implicitly embedded in one large prompt or one model.

## Retrieval and synthesis

When a Task requires project knowledge, Blaine should retrieve only the context
needed for the objective.

The normal flow is conceptually:

Task or interaction
-> determine context need
-> discover candidate project context
-> rank and select relevant sources
-> preserve authoritative evidence
-> synthesize where useful
-> perform the work

This applies to both local and cloud workers.

For cloud workers, selected project context remains subject to the Cloud Context
Packet and egress policies.

## Freshness

Project knowledge changes.

Retrieval has an important advantage over model specialization: Blaine can
prefer current authoritative sources at execution time.

A model trained on an older project snapshot may confidently return stale
knowledge.

Project-specific facts that are expected to change should therefore remain in
retrievable sources of truth whenever practical.

Model weights should not become the authoritative project database.

## Model adaptation

Model adaptation is not forbidden.

Possible future techniques may include:

- fine-tuning;
- adapters;
- LoRA-style specialization;
- preference tuning;
- domain-specific embeddings;
- project-specific local models.

Such approaches should be introduced only for a demonstrated repeated need.

Before project-specific model adaptation is accepted, Blaine should have
evidence that:

- the target capability is repeatedly useful;
- suitable project context is already available;
- retrieval and harness improvements have been evaluated;
- the adaptation materially improves measured outcome quality, cost, or latency;
- the adapted model's data provenance is known;
- its allowed usage scope is explicit.

## Model artifacts as sensitive assets

A model trained or adapted using private project data may itself become a
sensitive project artifact.

Its weights or adapters may encode information derived from protected sources.

Therefore a future specialized model may require controls around:

- storage;
- distribution;
- backup;
- sharing;
- retention;
- deletion;
- project scope;
- allowed inference environments.

Training locally does not automatically make the resulting model safe to share.

## Removal and correction

Explicit context can be updated or removed relatively directly.

Knowledge embedded in model weights is harder to inspect, correct, or delete.

For project facts that may need correction, revocation, or removal, explicit
retrieval remains preferable.

Blaine should not rely on retraining as its normal mechanism for updating
project knowledge.

## Relationship to context preparation

ADR 0009 defines Cloud Context Packets for cloud dispatch.

This ADR addresses the broader source of project knowledge before any particular
worker is chosen.

Conceptually:

project sources
-> Context Catalog / discovery
-> retrieval and ranking
-> selected working context
-> local worker

or:

project sources
-> Context Catalog / discovery
-> retrieval and ranking
-> cloud context preparation
-> Cloud Context Packet
-> cloud worker

Retrieval and cloud compression are related but distinct.

Retrieval answers:

> What project context is relevant?

Cloud context preparation additionally answers:

> What subset and representation should be allowed to leave the local trust
> boundary?

## Relationship to protected context

ADR 0013 governs protected-context transformation and egress.

Retrieval does not override project confidentiality.

A source may be highly relevant and still be `LOCAL_ONLY`.

Project-specific model training would also need to respect those source policies.

A future training pipeline must not assume that information allowed for local
retrieval is automatically allowed to enter model weights.

## Boundaries

This decision does not:

- forbid future fine-tuning;
- require a vector database;
- require embeddings for every source;
- define the final Context Catalog architecture;
- require all project knowledge to be indexed immediately;
- require cloud retrieval;
- make model weights a source of truth;
- require one context strategy for every project;
- justify training merely because local inference is inexpensive.

The smallest adequate mechanism should be preferred.

## Consequences

Project knowledge remains visible, inspectable, versionable, and easier to
correct.

Workers can receive fresh project context without retraining.

The same general-purpose model can work across multiple projects with different
retrieved context.

Protected-context and egress rules can operate on explicit sources rather than
hidden training data.

Blaine gains future work around context discovery, ranking, provenance, and
cataloging.

Specialized models may still become valuable, but only after real workloads
demonstrate that explicit context engineering is insufficient.

## Validation

### Hypothesis

For representative project-specific tasks, explicit project instructions plus
retrieval of relevant context can provide sufficient project knowledge without
embedding that knowledge into project-specific model weights.

The retrieval approach should also respond more naturally to project changes
than a static trained snapshot.

### Validation level

Deferred until representative project-context workloads exist, then isolated.

### Minimal validation

When suitable workloads exist, create a small benchmark of project-specific
questions or tasks whose answers depend on project knowledge.

Prepare at least two approaches:

1. a general local model using project instructions plus retrieved relevant
   context;
2. a baseline without targeted project retrieval.

Measure whether retrieval materially improves:

- factual correctness;
- adherence to project constraints;
- architecture awareness;
- use of current project state;
- provenance of important claims.

Where practical, change one piece of authoritative project information and repeat
the evaluation to confirm that retrieval reflects the new state without model
retraining.

Model fine-tuning is not required for this initial validation.

### Evidence

PASS requires demonstrating that:

- retrieved project context materially improves representative outcomes compared
  with the no-retrieval baseline;
- important claims can be traced to explicit sources;
- current project changes can be reflected by updating sources or indexes rather
  than model weights;
- different projects can use the same base model with different selected
  contexts;
- project-specific instructions remain explicit rather than hidden in model
  behavior;
- no project-specific training is required to satisfy the tested workload.

This ADR does not require retrieval to outperform a future fine-tuned model.

Training becomes worth evaluating only after retrieval-based approaches show a
repeatable deficiency worth solving.

### Not required for validation

- fine-tuning;
- LoRA or model adapters;
- training a project-specific model;
- a vector database;
- a production Context Catalog;
- cloud inference;
- paid tokens;
- protected project data;
- Restate integration;
- MCP;
- GPU scheduling.

### Reconsider when

Reconsider this decision if representative workloads show that:

- retrieval repeatedly fails to provide knowledge a specialized model can
  reliably learn;
- context size or retrieval latency becomes prohibitive;
- repeated stable domain behavior is significantly more efficient when adapted
  into model weights;
- evaluated specialization produces a material quality advantage that cannot be
  achieved through better retrieval, instructions, or context preparation.

Any move toward project-specific training should include explicit evaluation,
dataset provenance, sensitivity policy, model scope, retention, and deletion
considerations.
