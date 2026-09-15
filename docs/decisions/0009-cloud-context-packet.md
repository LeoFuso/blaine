# ADR 0009 — Cloud Context Packet is the mandatory cloud context contract

**Status:** Accepted
**Validation:** Unvalidated

## Context

Blaine may have substantially more context available locally than a cloud worker
needs to perform one bounded operation.

That context may include:

- repository files;
- previous decisions;
- Task artifacts;
- logs;
- tool results;
- conversation history;
- runtime state;
- connected sources;
- irrelevant neighboring information.

Forwarding all available context to a cloud worker by default is undesirable.

It increases paid token usage, makes relevant evidence harder to identify,
creates unnecessary data egress, and couples cloud execution to the caller's
current working context.

Naive summarization is also insufficient.

Some work requires exact code, logs, identifiers, constraints, or other evidence
whose precision would be damaged by lossy compression.

Blaine therefore needs an explicit context contract between local work and cloud
execution.

## Decision

As in ADR 0008, a **Cloud Worker** is an allow-listed externally hosted model or
agent outside the local trust boundary. A **Paid Cloud Worker** is a Cloud Worker
whose invocation incurs paid cloud usage.

Every Cloud Worker invocation must receive context through an explicit Cloud
Context Packet, whether or not it incurs paid usage.

A caller does not forward its complete working context directly to a Cloud Worker.

This applies whether the caller is:

- the Personal Agent;
- a durable Task;
- a SpecKit-style phase;
- a local worker;
- a future MCP client;
- a scheduled or background workflow.

Every Paid Cloud Worker invocation additionally crosses the Paid Cloud Dispatch
Boundary defined by ADR 0008.

The Cloud Context Packet is a first-class dispatch artifact.

It represents the context intentionally selected for one cloud invocation.

## Context preparation

The default preparation process is conceptually:

discover
-> rank
-> select
-> preserve exact evidence where required
-> compress or summarize where safe
-> construct Cloud Context Packet
-> dispatch

Compression is not synonymous with summarization.

The objective is:

> Send the smallest context that preserves the quality required for the work.

Some selected context may remain byte-for-byte or structurally exact.

Other context may be summarized, transformed, referenced, or omitted.

Irrelevant context should not be included merely because it is locally
available.

## Context Packet

The exact schema remains intentionally evolvable.

A useful packet may contain concepts such as:

- purpose;
- question or requested operation;
- relevant facts;
- constraints;
- selected context;
- exact evidence;
- known unknowns;
- requested output;
- provenance;
- context transformations that were applied.

For example, the packet should be capable of distinguishing:

- a summarized architectural description;
- an exact source-code fragment;
- a test failure copied verbatim;
- a reference to the source from which a fact was derived.

The packet is not a replacement for the original sources of truth.

It is a bounded representation prepared for a particular cloud invocation.

## Provenance

Selected context should retain enough provenance to understand where important
claims or evidence came from.

Context reduction must not turn sourced evidence into unattributed model memory.

Where practical, the packet should allow an answer or resulting artifact to be
traced back to the local evidence used to produce it.

The final provenance representation is an implementation concern.

## Mandatory protocol, proportional work

Every Cloud Worker invocation requires a Cloud Context Packet.

That does not mean every invocation requires an expensive preparation workflow.

A trivial request may produce a trivial packet directly.

For example, a user asking a Cloud Worker to critique one explicitly provided
paragraph may require little more than:

- the purpose;
- the paragraph;
- relevant constraints;
- requested output.

More complex requests may require repository discovery, tool execution, ranking,
comparison, and synthesis before a useful packet can be produced.

The protocol is mandatory.

The amount of preparation is proportional to the request.

## Context preparation as durable work

Preparing cloud context may itself require meaningful independent work.

Examples include:

- exploring several repository modules;
- locating relevant contracts and implementations;
- gathering runtime evidence;
- comparing previous architectural decisions;
- identifying which sources are authoritative;
- reducing a large evidence set into a bounded technical brief.

When context preparation requires its own independent lifecycle, verification,
waits, or substantial execution, it should become a durable Task rather than
remaining hidden inside one Personal Agent turn.

The resulting Cloud Context Packet can then be consumed by the original Task or
interaction.

This follows the existing Task-over-session boundary.

It does not introduce a second orchestrator for the Personal Agent.

## Broad-context override

Normal cloud dispatch uses context reduction.

There are cases where the Personal Agent or workflow may determine that broader
context would materially improve outcome quality.

Blaine may then request explicit user authorization for a broad-context override,
for example:

- allow once;
- allow for this Task;
- deny.

A broad-context override relaxes normal reduction.

It does not bypass:

- Cloud Worker allowlists;
- cloud authorization;
- configured budget limits;
- source permissions;
- local-only restrictions;
- secret handling;
- protected-context egress rules.

The cloud invocation still receives a Cloud Context Packet.

The packet is simply permitted to contain a broader authorized context set.

There is no mode where arbitrary caller memory is silently forwarded directly to
the cloud worker.

## Separate gates

Cloud execution involves distinct decisions.

They must not collapse into one boolean such as `useCloud`.

Conceptually:

1. Quality/capability gate:
   Is cloud capability materially justified for the required outcome?

2. Authorization gate:
   Is this cloud invocation allowed and within the applicable policy/budget?

3. Context egress gate:
   What exact information is necessary and permitted to leave the local
   environment?

ADR 0008 primarily establishes the dispatch and authorization boundary.

This ADR establishes the context preparation and egress contract.

Worker capability and quality selection is addressed separately.

Future protected-context policy may further restrict or transform individual
context elements before they are eligible for a packet.

## Dynamic context access

A Cloud Worker must not escape the packet boundary by gaining unrestricted access
to local context after dispatch.

Future controlled retrieval mechanisms may allow a cloud worker to request
additional information.

Any additional context exposed through such a mechanism must pass through the
same context preparation and egress rules as the original packet.

Each cloud interaction remains bounded by explicit context policy.

## Boundaries

The Cloud Context Packet does not:

- own Task lifecycle;
- replace the Durable Runtime;
- decide whether cloud usage is authorized;
- choose the concrete cloud worker;
- require lossy summarization;
- require every source to be copied into the packet;
- make protected data eligible for cloud use;
- replace authoritative local sources;
- imply that context preparation must always become a Task;
- define the final protected-data transformation mechanism.

Protected-context redaction, pseudonymization, and local-only classification are
separate architectural decisions.

## Consequences

Cloud workers receive smaller and more relevant context by default.

Paid token usage can be reduced without assuming that all context is safely
summarizable.

Exact evidence can be preserved selectively.

Context selection becomes observable and testable rather than an implicit side
effect of the caller's conversation window.

The same cloud worker can be used from different workflows without receiving
their entire local state.

Context preparation can evolve independently from cloud providers.

Complex preparation can be delegated as durable work.

This introduces explicit context artifacts and preparation logic that would not
exist in a direct provider-call design.

That complexity is intentional because context quality, cost, and egress are
first-class concerns for Blaine.

## Validation

### Hypothesis

Blaine can reduce the context exposed to a cloud worker while preserving the
evidence required to perform a bounded task at the expected quality.

The same Cloud Context Packet contract can support both trivial synchronous
preparation and substantial preparation performed as independent work.

### Validation level

Isolated.

### Minimal validation

Create a fixture context corpus containing:

- directly relevant evidence;
- irrelevant neighboring material;
- information safe to summarize;
- exact evidence that must not be summarized;
- constraints;
- provenance metadata;
- at least one intentionally missing fact.

Define several bounded questions against that corpus.

Use local tools and, where semantic ranking or compression is required, local
inference to produce Cloud Context Packets.

Send the resulting packets to a fake Cloud Worker that records exactly what it
received.

Include at least:

1. a trivial request producing a small direct packet;
2. a larger context set requiring discovery and ranking;
3. a case requiring exact evidence preservation;
4. a case containing insufficient evidence, which must preserve a known unknown;
5. a context-preparation result represented as if it came from independent
   durable work;
6. a broad-context override case.

No real cloud provider is required.

### Evidence

PASS requires demonstrating that:

- every fake cloud invocation receives an explicit Cloud Context Packet;
- raw caller context is never implicitly forwarded;
- irrelevant fixture context is excluded under normal preparation;
- required exact evidence remains exact;
- safely compressible context may be reduced;
- provenance survives for selected important evidence;
- known missing information is represented rather than invented;
- packet size is measurably smaller than available source context for cases where
  reduction is expected;
- a packet prepared through an independent-work path is consumable exactly like
  one prepared synchronously;
- broad-context authorization still produces a packet and does not bypass other
  egress restrictions;
- the fake Cloud Worker cannot access unselected local fixture context.

Quality evaluation should focus on whether the packet retains the evidence needed
for the bounded question, not token reduction alone.

A smaller packet that materially damages the required outcome is a failure.

### Not required for validation

- Codex;
- Astra or another real Cloud Worker;
- paid tokens;
- Restate integration;
- IntelliJ;
- MCP;
- SpecKit execution;
- final worker-selection policy;
- GPU scheduling;
- protected-context pseudonymization;
- secret-management integration;
- a final production Context Packet schema.

### Reconsider when

Reconsider this decision if:

- representative cloud workloads consistently require nearly all locally
  available context;
- context preparation costs more than the cloud usage it saves without improving
  quality or control;
- reduction repeatedly removes evidence required for correct outcomes;
- cloud-provider-native context mechanisms can satisfy the same invariants
  without exposing unrestricted local context;
- treating the packet as an explicit artifact creates more coupling than
  observability or control.

Such evidence may change how packets are prepared, but should not silently
restore unrestricted cloud access.
