# ADR 0011 — Local inference is a scheduled shared resource

**Status:** Proposed
**Validation:** Unvalidated

## Context

Blaine treats local inference as financially abundant.

That does not mean local inference is an unconstrained resource.

Multiple durable Tasks may execute concurrently while sharing one physical GPU.

Local models may differ substantially in:

- VRAM footprint;
- load time;
- context residency;
- throughput;
- quality;
- supported capabilities.

Frequent model switching can evict an already-loaded model, reload another model,
increase latency, reduce throughput, and cause unrelated Tasks to interfere with
each other.

A worker-selection decision that ignores current machine state may therefore be
semantically valid but operationally poor.

For example, a classification operation may be satisfiable by several local
models. If one sufficient model is already resident, loading another model for a
small theoretical quality advantage may be wasteful.

Blaine needs explicit control over local inference contention and model residency.

## Decision

Local inference is treated as a scheduled shared resource.

Tasks and workers request local inference capability rather than assuming
immediate exclusive access to the GPU.

A Local Inference Scheduler is responsible for coordinating access to the
available inference resource.

The scheduler should prefer useful model residency and avoid unnecessary model
thrashing.

The initial system may conceptually treat the primary local inference GPU as a
resource with limited concurrent capacity.

The exact concurrency value is an implementation and measurement concern.

## Scheduling principles

The scheduler should consider:

- whether a suitable model is already resident;
- whether that resident model is among the selector-approved eligible candidates;
- current local inference work;
- interactive versus background priority;
- cost of switching models;
- expected duration of queued work;
- starvation and fairness;
- whether cloud escalation is independently justified.

The default policy should favor stability over gratuitous model switching.

If the currently resident model is sufficient, Blaine should normally use it.

A different local model may be selected when its capability or expected quality
materially justifies the switch.

## Model residency

Model identity and residency are runtime concerns.

Workflow definitions should not require a particular model merely because it is
currently loaded.

Likewise, worker selection should not ignore residency when multiple workers can
satisfy the same requirement.

Conceptually:

required capability
-> Worker Selection identifies sufficient eligible local workers
-> prefer a sufficient resident worker
-> otherwise schedule an appropriate switch or wait
-> execute when the resource becomes available

Residency influences execution policy.

It does not redefine semantic workflow requirements.

## Queueing

When local inference is busy, additional requests may wait.

Waiting for a local inference resource should be representable durably when the
request belongs to durable work.

A Task must not require a model process or conversational session to remain alive
while waiting for GPU access.

The Durable Runtime remains responsible for durable Task lifecycle.

The Local Inference Scheduler is responsible for resource availability and
allocation.

The exact mechanism may use leases, queues, signals, durable waits, or another
implementation.

This ADR does not mandate a specific Restate primitive.

## Switching models

A model switch is an operational action.

The scheduler may switch automatically when:

- no incompatible inference work is active;
- the requested model materially better satisfies the requirement;
- policy allows the switch.

The scheduler should normally queue work rather than repeatedly swapping models
for competing background Tasks.

Interactive work may receive higher priority than background work.

Preemption may be introduced if measurements show it is useful, but preemption
is not required for the initial implementation.

The user should not be asked to approve routine local model switches.

User interaction is appropriate only when a meaningful policy or resource
trade-off cannot be resolved automatically.

## Relationship to worker selection

ADR 0010 decides which workers are semantically suitable.

This ADR governs whether and when a suitable local worker can execute on the
shared machine.

Worker selection may consider scheduler information such as:

- current resident model;
- expected queue delay;
- switching cost;
- resource availability.

The scheduler allocates/schedules only among selector-approved eligible candidates
that satisfy semantic capability and quality requirements. Residency, queue
latency, and switching cost may influence which eligible candidate runs, but the
scheduler MUST NOT relax those requirements. If no eligible candidate can
currently execute, scheduling may wait or request reselection according to policy.
This defines the ownership boundary, not a scheduling algorithm.

The order is:

semantic requirement
-> eligible workers
-> resource-aware execution choice
-> scheduling/allocation
-> execution

## Relationship to cloud

Local contention does not automatically authorize paid cloud escalation.

A busy GPU and an insufficient local worker are different conditions.

Cloud execution remains subject to:

- capability and quality justification;
- cloud authorization;
- budget;
- Cloud Dispatch Boundary;
- Cloud Context Packet and egress policy.

Policy may eventually allow cloud escalation because local queue latency exceeds
a meaningful threshold, but such behavior must be explicit.

A queue must not silently become a paid cloud call.

## Task state

Resource waiting is real execution state, but this ADR does not require a new
public Task lifecycle state such as `WAITING_FOR_RESOURCE`.

The initial implementation may represent resource waits internally through the
Durable Runtime.

A public lifecycle state should be introduced only if it improves observability
or user interaction.

Avoid expanding Task state taxonomy prematurely.

## Multi-GPU and future resources

The initial motivating environment contains one primary GPU.

The abstraction should not assume that Blaine will always have exactly one GPU.

The same scheduling concept may later support:

- multiple GPUs;
- CPU inference;
- specialized accelerators;
- remote local-network inference workers;
- memory-constrained tools;
- other scarce execution resources.

This ADR does not require implementing a generic resource scheduler today.

Local inference is the first concrete resource that justifies the concept.

## Boundaries

The Local Inference Scheduler does not:

- perform semantic triage;
- define workflow strategy;
- decide whether a worker is capable enough;
- authorize paid cloud use;
- own durable Task lifecycle;
- require multiple local models;
- require preemption;
- require a distributed queue;
- require a generic cluster scheduler;
- make local inference artificially token-constrained.

Local token volume remains comparatively cheap.

The constraint addressed here is physical resource contention and model
residency, not token accounting.

## Consequences

Multiple Tasks can coexist without independently fighting over the GPU.

A useful model can remain hot for repeated work.

Local inference latency becomes more predictable.

Worker selection can account for actual machine conditions without coupling
workflow semantics to model identity.

Durable Tasks may wait for local inference without keeping agent processes alive.

The system gains scheduling complexity.

That complexity should remain small and targeted to observed contention rather
than growing into a general-purpose compute scheduler.

## Validation

### Hypothesis

Blaine can coordinate concurrent local-inference requests so that sufficient
resident models are reused, unnecessary model switching is reduced, and durable
work can wait for GPU access without losing execution intent.

### Validation level

Isolated.

### Minimal validation

Build a simulated local-inference scheduler.

No real model loading is required.

Represent:

- one logical GPU resource;
- at least two local models;
- model residency;
- multiple concurrent requests;
- capability/quality sufficiency;
- interactive and background priorities;
- model-switch cost.

Exercise at least these scenarios:

1. two Tasks requesting the same resident model;
2. a request that can use the current resident model or another equivalent model;
3. a request requiring a different model while inference is active;
4. multiple background requests that would otherwise cause repeated model swaps;
5. an interactive request arriving while background work is queued;
6. a waiting durable Task whose requesting worker disappears and later resumes;
7. a request for which the resident model is operationally convenient but
   semantically insufficient.

### Evidence

PASS requires demonstrating that:

- a sufficient resident model is reused when appropriate;
- an equivalent non-resident model does not cause an unnecessary switch;
- incompatible concurrent work is queued rather than causing uncontrolled model
  thrashing;
- repeated background requests do not produce pathological A/B/A/B model
  switching;
- interactive priority can affect queue ordering without destroying background
  work;
- durable waiting does not require the original worker process to remain alive;
- residency never causes a semantically insufficient worker to be accepted;
- local contention does not automatically trigger paid cloud dispatch;
- scheduling decisions are observable enough to explain why work ran, waited, or
  caused a model switch.

Useful metrics for the simulation may include:

- number of model switches;
- accumulated simulated switch cost;
- queue delay;
- completed requests;
- starvation;
- resident-model reuse rate.

Exact target thresholds should be established from measurements rather than
invented in this ADR.

### Not required for validation

- loading Qwen or Nemotron;
- real GPU memory allocation;
- Ollama integration;
- Restate integration;
- Codex or other cloud workers;
- paid tokens;
- preemption;
- multiple physical GPUs;
- distributed scheduling;
- a generic resource-management framework;
- new public Task lifecycle states.

### Reconsider when

Reconsider this decision if:

- real local inference supports concurrent heterogeneous models with negligible
  switching cost;
- GPU contention is not meaningful under representative Blaine workloads;
- the inference backend provides sufficient resource scheduling natively;
- scheduler complexity exceeds the operational benefit;
- a simpler single-model policy satisfies nearly all workloads.

Such evidence may simplify or replace the scheduler without changing the broader
principle that scarce execution resources should not be managed implicitly by
individual agents.
