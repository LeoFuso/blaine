# Architecture Decision Records

This directory records architectural decisions for Blaine.

ADRs capture decisions that materially constrain the architecture, including:

- the problem and context;
- the decision;
- alternatives considered;
- consequences and trade-offs;
- current status.

Use sequential filenames, for example:

- 0001-task-is-the-unit-of-work.md
- 0002-intellij-acp-as-first-client.md
- 0003-evaluate-restate-as-durable-runtime.md

Possible statuses:

- Proposed
- Accepted
- Superseded
- Rejected

Do not create ADRs for routine implementation choices.

## Decision and validation status

An ADR records a decision. It does not prove that the decision works.

Keep these two dimensions separate:

### Decision status

- `Proposed` — under consideration.
- `Accepted` — current architectural direction.
- `Superseded` — replaced by a later decision.

### Validation status

- `Unvalidated` — accepted or proposed, but not yet exercised against its hypothesis.
- `Partially Validated` — meaningful evidence exists, but an important claim remains untested.
- `Validated` — the stated hypothesis has passed the evidence defined by the ADR.
- `Deferred` — validation intentionally waits for a real workload or prerequisite.

An `Accepted` ADR may still be `Unvalidated`.

## Validation convention

Every ADR should explain how its architectural claim can be challenged.

Prefer the smallest experiment that isolates the decision:

1. `Isolated` — fixtures, stubs, or deterministic components are sufficient.
2. `Integration` — two or more real Blaine components must interact.
3. `End-to-end` — the real client/runtime/worker path is required.
4. `Deferred` — validating now would require speculative work or an absent workload.

Validation sections describe **evidence**, not implementation plans.

A good validation section contains:

- **Hypothesis** — what must be true.
- **Validation level** — the minimum useful scope.
- **Minimal validation** — the smallest meaningful experiment.
- **Evidence** — observable PASS conditions.
- **Not required for validation** — explicit scope that should not be built just to run the experiment.
- **Reconsider when** — evidence that should cause the decision to be revisited.

Successful agent exit, a `DONE` message, or successful code generation is not
architectural evidence by itself.

The purpose of this convention is to make ADRs safe to delegate: an agent may
implement the smallest validation without also inventing the success criteria or
expanding into unrelated future work.

See [template.md](template.md) for the standard shape.


## Local platform constraint

[ADR 0018 — Blaine Local Platform, Durability and Observability Architecture](0018-local-platform-durability-and-observability.md) preserves the supplied proposed decision. It is an explicit architectural constraint for Cognitive Kernel Increment 10 and subsequent work. Its target platform is not claimed implemented or validated by recording the ADR.

## Decision index

Current sequencing lives in the [development roadmap](../roadmap/001-blaine-development-roadmap.md);
measured results live in the [milestone index](../milestones/README.md). Read each
ADR’s own status before treating it as an accepted constraint.

- [ADR 0001 — Task Is the Unit of Work](0001-task-is-the-unit-of-work.md)
- [ADR 0002 — IntelliJ ACP as the First Interactive Client](0002-intellij-acp-as-first-client.md)
- [ADR 0003 — Evaluate Restate as the Durable Runtime](0003-evaluate-restate-as-durable-runtime.md)
- [ADR 0004 — Personal Agent as Conversational Control Plane](0004-personal-agent-control-plane.md)
- [ADR 0005 — Semantic triage selects the work strategy](0005-semantic-triage-selects-work-strategy.md)
- [ADR 0006 — SpecKit is an optional structured-work strategy](0006-speckit-as-structured-work-strategy.md)
- [ADR 0007 — Deterministic tools precede model inference](0007-tools-before-model-inference.md)
- [ADR 0008 — Paid cloud access crosses a single dispatch boundary](0008-paid-cloud-crosses-single-dispatch-boundary.md)
- [ADR 0009 — Cloud Context Packet is the mandatory cloud context contract](0009-cloud-context-packet.md)
- [ADR 0010 — Worker selection is capability and quality driven](0010-worker-selection-is-capability-and-quality-driven.md)
- [ADR 0011 — Local inference is a scheduled shared resource](0011-local-inference-is-a-scheduled-shared-resource.md)
- [ADR 0012 — Blaine Core is protocol-neutral](0012-blaine-core-is-protocol-neutral.md)
- [ADR 0013 — Protected context is transformed locally before egress](0013-protected-context-transformations.md)
- [ADR 0014 — Project knowledge is retrieval-first, training-last](0014-project-knowledge-is-retrieval-first.md)
- [ADR 0015 — Durable Task execution and verification](0015-durable-task-execution-and-verification.md)
- [ADR 0016 — Agent harnesses are replaceable execution capabilities](0016-agent-harnesses-are-replaceable-execution-capabilities.md)
- [ADR 0017 — Human–Agent Work Coordination Plane](0017-human-agent-work-coordination-plane.md)
- [ADR 0018 — Blaine Local Platform, Durability and Observability Architecture](0018-local-platform-durability-and-observability.md)
- [ADR 0019 — Local inference serving baseline](0019-local-inference-serving-baseline.md)
