# ADR 0012 — Blaine Core is protocol-neutral

**Status:** Accepted
**Validation:** Unvalidated

## Context

Blaine currently uses ACP as its first conversational integration because it
allows the Personal Agent to participate directly in clients such as IntelliJ.

Future consumers may need different interaction styles.

Examples include:

- a conversational IDE client;
- another agent invoking Blaine programmatically;
- command-line automation;
- scheduled jobs;
- future chat or messaging integrations;
- external tools querying or signalling Tasks.

ACP and MCP solve different interaction problems.

ACP is useful for exposing an agent conversationally.

MCP is useful for exposing tools and programmable capabilities to other agents.

Neither protocol should define Blaine's Task semantics or business behavior.

If Task creation, status, signalling, result retrieval, semantic triage, or
workflow behavior becomes embedded inside one protocol adapter, adding another
interface would require duplicating or reimplementing Blaine itself.

## Decision

Blaine's core semantics are protocol-neutral.

Protocols such as ACP, MCP, CLI, HTTP, or future integrations are adapters around
Blaine capabilities.

The initial conceptual boundary is:

Personal Agent
-> Blaine Core / Task operations
-> Durable Runtime

ACP is the first conversational adapter for the Personal Agent.

A future MCP adapter may expose programmable Blaine capabilities to other agents.

Neither protocol owns the underlying Task model.

## Blaine Core

Blaine Core represents protocol-independent operations and semantics.

Representative Task operations include:

- create;
- status;
- list;
- signal;
- result.

These operations describe Blaine capabilities rather than ACP commands, MCP
tools, CLI syntax, or HTTP endpoints.

Their semantic contracts should remain stable enough that different adapters can
invoke the same behavior.

The exact code boundary may remain lightweight initially.

This ADR does not require introducing speculative interface hierarchies before a
second adapter exists.

## Personal Agent

The Personal Agent is a semantic module, not ACP itself.

Its responsibilities include:

- interpreting natural-language intent;
- deciding whether direct interaction is sufficient;
- performing semantic triage;
- forming or steering Tasks;
- presenting Task state and results;
- requesting genuine user decisions or approvals.

ACP transports conversation between a compatible client and the Personal Agent.

The Personal Agent should remain reusable from another conversational transport
without rewriting its semantic behavior.

## ACP

ACP answers the question:

> How does a user or compatible client converse with Blaine's Personal Agent?

It is currently the first northbound conversational protocol.

ACP-specific concerns belong in the ACP adapter, including:

- protocol messages;
- session mechanics;
- transport;
- client-specific integration behavior.

ACP session state is not durable Task state.

Closing an ACP session must not destroy durable work.

## MCP

A future MCP adapter may answer a different question:

> How can another agent or compatible client invoke Blaine capabilities as
> programmable tools?

Representative MCP-exposed operations could eventually include:

- create Task;
- inspect Task;
- list Tasks;
- signal Task;
- retrieve result.

MCP is not required for the current architecture milestone.

Blaine should avoid design choices that make future MCP exposure unnecessarily
difficult, but must not build the MCP adapter before there is a concrete use case.

## Direction of interaction

A useful architectural view is:

User/client
-> conversational adapter
-> Personal Agent
-> Blaine Core
-> Durable Runtime

and, for future programmable consumers:

External agent/client
-> programmable adapter
-> Blaine Core
-> Durable Runtime

This northbound/southbound language is a Blaine architectural convenience rather
than a claim about the protocols themselves.

## Adapter responsibility

Adapters translate protocol-specific inputs into Blaine semantics and translate
Blaine outputs back into protocol-specific responses.

Adapters should not independently implement:

- Task lifecycle;
- retry behavior;
- durable waits;
- completion rules;
- cloud authorization;
- worker-selection policy;
- workflow semantics.

Those responsibilities belong to their respective Blaine layers.

## No premature abstraction

Protocol neutrality is an architectural boundary, not a requirement to build a
large generic framework.

While ACP is the only implemented conversational protocol, direct use of
concrete code is acceptable where it does not embed Blaine semantics into the
transport.

Interfaces should be extracted when they clarify an actual boundary or support a
second implementation.

Do not introduce factories, provider hierarchies, or generic transport
abstractions solely to satisfy this ADR.

## Relationship to the Durable Runtime

The Durable Runtime is also an implementation boundary.

Restate is the current Durable Runtime implementation.

ACP, MCP, and other client protocols should not need to know whether durable
execution is implemented by Restate, Temporal, or another suitable runtime.

Protocol adapters interact with Blaine semantics, not runtime-specific workflow
APIs unless confined to an internal binding layer.

## Boundaries

Protocol neutrality does not mean:

- all protocols must expose identical UX;
- every Blaine capability must be exposed through every adapter;
- MCP must be implemented now;
- ACP must be replaced;
- Blaine must define a new network protocol;
- every adapter needs a formal shared interface immediately;
- protocol-specific capabilities are forbidden.

An adapter may provide protocol-specific features as long as core Task and
workflow semantics remain outside the adapter.

## Consequences

The Personal Agent can evolve independently from IntelliJ or ACP.

Future agents may invoke Blaine programmatically without turning the Personal
Agent into a fake tool API.

Task semantics remain consistent across interfaces.

A future CLI or integration can reuse the same core operations.

The architecture gains explicit adapter boundaries while avoiding premature
transport abstraction.

Some duplication in thin adapters may be acceptable if extracting a generic
framework would cost more than it saves.

## Validation

### Hypothesis

The same Blaine Task semantics can be invoked through multiple interaction
adapters without duplicating lifecycle or workflow behavior inside those
adapters.

The Personal Agent can remain independent from ACP-specific session and transport
mechanics.

### Validation level

Integration.

### Minimal validation

Construct two thin adapters against the same minimal Blaine Core operations.

One adapter should represent conversational interaction similar to ACP.

The second may be a simple fake programmable adapter rather than a real MCP
server.

Both adapters should be able to exercise a representative subset of:

- create;
- status;
- signal;
- result.

The core or runtime fixture should own all Task state.

Terminate and recreate the conversational adapter during the experiment.

No durable state should be lost.

### Evidence

PASS requires demonstrating that:

- both adapters invoke the same underlying Task semantics;
- Task lifecycle logic is not duplicated in either adapter;
- ACP-style session loss does not affect Task identity or state;
- protocol-specific input/output translation remains in the adapter;
- the Personal Agent does not require ACP protocol objects to make semantic
  decisions;
- replacing the adapter does not require changing TaskSpec or workflow
  semantics;
- the Durable Runtime implementation is not exposed as part of the public
  adapter contract;
- a second adapter can be added without creating a second source of Task truth.

### Not required for validation

- a production MCP server;
- a new CLI;
- HTTP APIs;
- replacing the existing ACP implementation;
- Codex;
- paid cloud inference;
- SpecKit execution;
- GPU scheduling;
- Cloud Context Packets;
- a generic protocol framework;
- a second Durable Runtime implementation.

### Reconsider when

Reconsider this decision if:

- different protocols require fundamentally incompatible Task semantics;
- keeping protocol concerns outside core behavior creates more complexity than it
  removes;
- the Personal Agent proves inseparable from a specific conversational protocol;
- future integrations consistently require protocol-specific lifecycle behavior.

Such evidence should first challenge the adapter boundary rather than duplicating
Blaine's core semantics per protocol.
