# ADR 0008 — Paid cloud access crosses a single dispatch boundary

**Status:** Accepted
**Validation:** Unvalidated

## Context

Blaine treats paid cloud inference as a scarce resource.

Cloud workers may provide materially better capability for difficult reasoning,
large technical changes, repository analysis, planning, implementation, or
independent review.

However, allowing Personal Agents, workflows, skills, or workers to invoke paid
cloud providers directly would distribute responsibility for:

- authorization;
- spend limits;
- provider allowlists;
- context preparation;
- data egress;
- telemetry;
- escalation policy.

That would make cloud usage difficult to reason about, audit, constrain, and
optimize.

It would also allow a semantic decision such as "this is difficult" to become an
uncontrolled implementation action such as sending the current conversation or
repository context directly to a paid model.

Blaine therefore needs one mandatory boundary for paid cloud dispatch.

## Decision

All paid cloud-agent and paid cloud-model access must cross a single conceptual
Cloud Dispatch Boundary.

No component receives unrestricted direct access to a paid cloud worker.

This includes:

- the Personal Agent;
- durable workflows;
- SpecKit-style phases;
- local workers;
- future MCP clients;
- future scheduled or background jobs.

A component requests cloud capability through the boundary.

It does not bypass the boundary by invoking a provider directly.

The boundary is architectural. It does not require a separate network service or
process in the initial implementation.

## Responsibilities

Before paid cloud dispatch, the boundary must be capable of enforcing:

- cloud authorization;
- Task-level cloud policy;
- provider/worker allowlists;
- configured spend or usage limits;
- context-egress requirements;
- required context preparation;
- telemetry for the dispatch.

A successful dispatch should be attributable to at least:

- the originating Task or interaction;
- the purpose of the cloud call;
- the requested capability or quality requirement;
- the selected cloud worker when known;
- the context packet or context preparation result used;
- the applicable authorization;
- observable usage/cost data when available;
- the resulting worker outcome.

The exact telemetry schema is an implementation concern and may evolve.

## Cloud authorization

Cloud authorization and cloud budget are separate concepts.

Blaine currently recognizes the semantic policies:

- `forbid` — paid cloud use is not allowed;
- `ask` — explicit user authorization is required before dispatch;
- `allow-within-budget` — paid cloud use is pre-authorized within an enforceable
  configured ceiling.

A budget does not grant authorization by itself.

A user may explicitly authorize broader or more expensive cloud use for a
particular Task, but that authorization must still cross this boundary.

## Context egress

Paid cloud dispatch does not receive the caller's complete working context by
default.

Before dispatch, cloud context must pass through the context-preparation and
egress process defined separately.

The next architectural decision defines the Cloud Context Packet and the default
context-reduction path.

Future protected-context policies may require local redaction,
pseudonymization, exclusion, or other transformations before egress.

Those transformations are separate from cloud authorization.

Authorization to use cloud does not imply authorization to send every available
piece of context.

## Relationship to semantic triage

ADR 0005 selects how much workflow an intent deserves.

ADR 0007 prefers deterministic tools and then local inference before paid cloud
inference.

Only after those decisions may a workflow determine that paid cloud capability
is justified.

The request then crosses the Cloud Dispatch Boundary.

The boundary does not decide whether a user request should become a Task and
does not own semantic triage.

## Relationship to worker selection

The boundary does not define a permanent mapping from work type to concrete
model.

For example:

- `SPEC_DRIVEN` does not mean a specific cloud model;
- `INVESTIGATION` does not imply cloud use;
- requesting high-quality reasoning does not itself authorize paid dispatch.

Capability, quality, availability, residency, and cost may influence worker
selection.

Concrete worker-selection policy is a separate architectural decision.

The Cloud Dispatch Boundary enforces whether the resulting paid dispatch is
permitted.

## Personal Agent behavior

The Personal Agent may determine that answering a request well requires paid
cloud capability.

It must not call that capability directly.

It instead requests a cloud dispatch through the same boundary used by durable
Tasks.

If producing the required cloud context involves substantial independent work,
the Personal Agent may create a durable Task for that preparation rather than
performing the work entirely inside the conversational turn.

This does not create a second Personal Agent orchestrator.

It applies the existing rule that meaningful independent work belongs in a Task.

## Failure and denial

A cloud dispatch request may result in outcomes such as:

- permitted;
- approval required;
- denied by policy;
- denied by budget;
- worker/capability unavailable;
- context not eligible for egress;
- context preparation incomplete.

These outcomes must remain distinguishable.

A denied or unavailable cloud request must not silently degrade into an
unauthorized provider call.

The caller may choose another valid strategy, remain local, ask the user, or mark
the Task blocked as appropriate.

## Boundaries

The Cloud Dispatch Boundary does not:

- own Task lifecycle;
- replace the Durable Runtime;
- perform semantic triage;
- require every difficult Task to use cloud;
- define the final worker-selection algorithm;
- define the final Cloud Context Packet schema;
- make protected data cloud-eligible;
- treat payment or budget as authorization;
- require a standalone gateway service in v0.

The Durable Runtime remains authoritative for durable execution state.

## Consequences

Paid cloud usage becomes observable and enforceable at one architectural
boundary.

The Personal Agent and workflows can request higher capability without gaining
unrestricted provider access.

Cloud cost optimization can evolve independently from workflow semantics.

Provider/model changes do not require every caller to understand provider
details.

Context-egress policy gains one mandatory enforcement point.

The boundary introduces indirection into cloud calls, but that indirection is
intentional because paid cloud usage has cost, privacy, and control implications.

## Validation

### Hypothesis

Blaine can prevent direct paid-cloud execution while allowing callers to request
cloud capability through one enforceable boundary.

The boundary can distinguish authorization, denial, and approval-required
outcomes without requiring a real cloud provider.

### Validation level

Isolated.

### Minimal validation

Implement a fake paid-cloud adapter and a minimal dispatch boundary.

Exercise requests from representative callers such as:

- a Personal Agent request;
- a durable Task phase;
- a workflow that is forbidden from cloud use;
- a workflow requiring explicit approval;
- a workflow pre-authorized within a budget.

The fake cloud adapter should record every invocation.

The validation must also include at least one attempted bypass path.

No real paid cloud call is required.

### Evidence

PASS requires demonstrating that:

- allowed paid-cloud invocations reach the fake adapter only through the dispatch
  boundary;
- a `forbid` policy prevents dispatch;
- an `ask` policy returns an approval-required outcome before dispatch;
- approved requests may subsequently dispatch;
- `allow-within-budget` requires an enforceable configured ceiling;
- budget alone does not grant authorization under `ask`;
- a disallowed worker/provider is rejected;
- each accepted dispatch records its purpose and originating work identity;
- context preparation is represented as a prerequisite rather than silently
  forwarding all caller context;
- an attempted direct/bypass invocation is detectable or structurally
  unavailable in the validation harness;
- no real cloud credentials or paid usage are required.

### Not required for validation

- Codex;
- Astra or another real paid model;
- Restate integration;
- IntelliJ;
- SpecKit execution;
- final worker-selection policy;
- GPU scheduling;
- final Cloud Context Packet schema;
- protected-context pseudonymization;
- real billing integration.

### Reconsider when

Reconsider this decision if:

- a single boundary becomes a material bottleneck without providing meaningful
  control;
- provider-native security or accounting mechanisms make part of the boundary
  redundant;
- representative workloads require direct provider access that cannot be
  expressed safely through the boundary;
- the abstraction starts owning workflow semantics or lifecycle rather than
  enforcing cloud dispatch policy.

Such evidence should lead to changing the boundary, not silently introducing
direct paid-cloud calls.
