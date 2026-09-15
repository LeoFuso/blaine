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

