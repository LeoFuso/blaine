# ADR 0027 — IDE delegation is workspace authority; PolicyGate is the single enforcer

**Status:** Proposed
**Validation:** Unvalidated
**Date:** 2026-09-23

## Context

The [Hub design](../personal-agent-hub.md) planned E1 reads through IntelliJ's ACP
`fs/read_text_file`, bound by a Blaine "local workspace consent" and a local guard
in the workstation client that would independently deny out-of-scope calls. That
plan has three problems exposed while designing E1:

- ACP filesystem methods offer no listing, stat or search, so investigation Tasks
  ("find where customer status is computed") would force the model to guess paths,
  contrary to [ADR 0007](0007-tools-before-model-inference.md).
- A local consent step duplicates a delegation the operator already made in the
  IDE, adding a second approval ceremony.
- A local guard that filters capabilities becomes a second PolicyGate, with its own
  policy that can drift from the Hub's.

IntelliJ exposes an MCP server to ACP agents when the operator enables
**Pass IntelliJ MCP server** (`use_idea_mcp`, default off) for that agent. Its
read/search tools respect the IDE project model; it also exposes mutating and
executing tools, and it is IDE-global across open projects (verified against
upstream source; see the [workspace contract](../contracts/workspace-capability.md#verified-intellij-mcp-semantics)).

## Decision

1. **Delegation is authority.** Installing Blaine as a JetBrains ACP agent with
   `use_idea_mcp` enabled is the operator's delegation of the IntelliJ-exposed
   project capability surface, including every project IntelliJ exposes. Blaine
   records it (`DelegationSnapshot`) and adds no second workspace approval, per
   project or otherwise. `blaine integration jetbrains install` (invoked by the
   installers) sets the per-agent `use_idea_mcp` for the Blaine entry, never the
   global default; `check`/`doctor` report it. `blaine connect` stays Hub
   connectivity only and does not touch JetBrains configuration.
2. **IntelliJ MCP is the E1 capability provider.** No Blaine-owned filesystem
   provider is built for E1. ACP `fs/*` remains a possible future provider.
3. **Four concepts stay separate:** delegated scope (what IntelliJ exposes), Task
   relevance (which project the Context Plane selects), user constraints (e.g. Read
   Only, delivered through ACP `configOptions` as an input channel), and effective
   authority (compiled by Blaine).
4. **PolicyGate is the single enforcement authority.** Effective authority is the
   Task grant ∩ user constraints ∩ delegated scope ∩ Blaine's reviewed operation
   classification (unknown operations are unclassified and always denied).
5. **The workstation client is a bridge.** It relays MCP between the Hub and the
   IDE's local endpoint, keeps IDE tokens local, enforces framing/correlation/limits,
   and never filters, rewrites or originates tool calls.
6. **The Hub is trusted.** For the current personal deployment the Blaine Hub is
   part of the trusted computing base. PolicyGate is the authoritative application
   policy boundary; the client does not independently re-evaluate Task authority.
   A compromised Hub is outside that protection. This residual is accepted.
7. **Read-only is authority, proven by the journal.** A READ_ONLY Task has no
   mutating operation class; the capability journal
   ([ADR 0026](0026-completion-contract-is-a-durable-task-primitive.md)) shows that
   no mutating operation was admitted or executed even though the delegated surface
   contains mutating tools.

Where [ADR 0022](0022-workstation-personal-agent-client.md), the Hub design and the
[Context Plane](0025-context-plane-and-compiled-agent-context.md) refer to Hub-owned
"workspace consent" for an IntelliJ-provided workspace, this delegation is that
consent. The Context Plane Resolver supplies Task relevance; IntelliJ MCP can serve
as the remote provider of its exact-read and lexical/symbol search semantics, with
receipts using its result states. Workspace identity uses the E0.D Hub-assigned
`workstation_id`; availability combines E0.D presence with a live delegation.

This supersedes, for E1 onward, the Hub design's "local workspace consent",
"independent local guard" and "E1 reads through the ACP client read" statements,
and narrows ADR 0022's "the client must enforce local scope" to protocol integrity,
and replaces the Hub rule "do not enable MCP forwarding as an onboarding side
effect" with the explicit per-agent delegation above. Connection still grants nothing
by itself: without the IDE delegation there is no workspace capability.

## Alternatives considered

- **ACP `fs/read_text_file` only (prior plan).** Single named-file reads, no search,
  confinement unverifiable by Blaine, and IDE advertisement never yet recorded.
- **Blaine-owned confined filesystem provider in the client.** Stronger theoretical
  sandboxing (descriptor-relative access), but it is a Blaine workspace provider
  the roadmap rejects, ignores editor state, and duplicates what the IDE delegates.
  Rejected; the IDE boundary plus PolicyGate covers the relevant risks.
- **Local MCP tool allowlist in the client.** Rejected: a second policy engine that
  merely reproduces PolicyGate; keeps policy in two places.

## Consequences

- E1 gains search, symbol lookup and directory listing through the IDE's index,
  with no Blaine filesystem code.
- **Accepted residual (current threat model):** a compromised Hub can invoke any
  delegated IDE tool, including write, terminal, run-configuration, debugger and
  database tools, limited only by IDE-side controls (exposed-tool settings;
  command confirmation unless "brave mode" is on). No local authorization engine
  is added against it. Revisit if the Hub leaves the TCB (see below).
- Onboarding needs one fewer step: installing the integration delegates. The
  per-agent key is undocumented and must be observed before it is frozen.
- E2 reuses the same provider; only effective authority changes.
- Evidence reflects the IDE's view (`ide_document` may contain unsaved edits); it is
  labelled, and E2 must address dirty-buffer reconciliation before disk-based checks.
- The direct protocol gains a negotiated capability channel; the client gains an
  MCP transport bridge.
- Behavior depends on JetBrains' delegation mechanics, which must be re-observed on
  IDE upgrades (classification is pinned by version).

## Validation

### Hypothesis

With IDE delegation as the only workspace approval and PolicyGate as the only
enforcer, a READ_ONLY investigation Task on a real second workstation obtains
useful cited evidence, invokes zero mutating operations despite their presence in
the delegated surface, and survives IDE disconnect in the same Task.

### Validation level

End-to-end, preceded by an integration fixture with a counting fake MCP server.

### Minimal validation

E1 acceptance in the [workspace contract](../contracts/workspace-capability.md#e1-acceptance):
record the real delegated surface; run the investigation example; replay scripted
mutating proposals and count zero IDE calls; disconnect and continue.

### Evidence

Redacted `session/new` MCP descriptor and tool list containing mutating tools;
journal with only `workspace.read` admissions plus recorded denials; verifier
evaluation confirming it; IDE-fixture call count; same Task ID across reconnect.

### Not required for validation

Blaine filesystem provider, local policy engine, ACP `fs/*` read, E0.D presence
routing, write/exec capabilities, IntelliJ plugin.

## Reconsider when

IntelliJ stops passing its MCP server to custom ACP agents, offers no per-agent
delegation, or changes project semantics; the Hub leaves the trusted computing base
(for example multi-user or shared hosting) or a demonstrated threat requires
workstation-side enforcement independent of the Hub; or E2 shows IDE tools cannot
provide safe conditional writes.
