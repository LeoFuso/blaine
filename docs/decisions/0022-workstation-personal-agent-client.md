# ADR 0022 — Workstation Connection and Personal Agent Client Architecture

**Status:** Accepted

**Validation:** Unvalidated

**Date:** 2026-09-21

## Context

Blaine has durable Task, policy, human-response and evidence boundaries. D2 exposes
bounded controls through ACP; historical IntelliJ acceptance proves session
independence. The next product need is a workstation that can connect and provide
local capabilities without making users configure networking and remote scripts.

IntelliJ is the first surface, not the Personal Agent. A Task may use workstation
files/tools, semantic memory, replaceable workers and external applications.
Worker selection and effect location must remain independent. Historical evidence
does not prove onboarding, live IDE filesystem access or safe writes/execution.

## Decision

Adopt a small reusable local Blaine client with `connect`, `doctor`, `acp`,
`disconnect`, and `version`. `connect` owns idempotent workstation onboarding and
safe IntelliJ configuration. `doctor` is read-only. IntelliJ launches a stable
local `blaine acp`; private transport implementation and host installation paths
remain behind that launcher. ACP stdout contains protocol messages only.

Use interactive Tailscale authentication for human workstations without requiring
a long-lived tailnet administrative credential. Tailscale is an external
prerequisite, not a Blaine networking/authentication subsystem. Assist installation
through supported vendor/platform mechanisms with visible actions and explicit
OS/admin approval, then validate. Never persist raw login credentials.

Target Linux, native macOS and Windows development environments using WSL2 through
one small platform abstraction. Prefer native macOS Tailscale and native Windows
Tailscale for WSL2; do not install a second WSL daemon by default. Keep config/path/
subprocess handling portable and Blaine unprivileged. Native system/browser prompts
are expected. Initial implementation may validate fewer platforms, but architecture
and reporting must preserve all three targets. Separate network authentication,
Blaine registration, and Task/workspace authorization. Connection never grants
ambient filesystem or shell access. Require local scope enforcement in addition
to host PolicyGate decisions before forwarding workspace effects.

Keep workspaces and tool execution on their workstation, with scoped read/write/
exec capabilities and admitted evidence. Do not require a host checkout, custom
filesystem daemon or workspace synchronization. Task lifecycle remains owned by
Restate, independently of ACP sessions and device availability. Reconnect never
implicitly completes, cancels, approves or restarts a Task; human waits need an
explicit matching response. Completion remains contract/verifier-driven.

IntelliJ/ACP is the first surface; no Blaine plugin is required for E0–E3. Any later
plugin is a thin UX over the same reusable client. External application resources
remain separately authorized capabilities in the same Task model.

The [canonical Hub design](../personal-agent-hub.md) defines E0 connection, E1 live
read, E2 bounded effects and E3 verified coding with genuine human response. These
product milestones consume D-series capabilities without renaming their history.

Language, package formats, registry schema, pairing mechanics, operation-envelope
encoding and safe provider choices remain recommendations/open gates in that
design. This ADR does not certify unproven ACP semantics or select arbitrary shell
as a fallback when a client capability is absent.

## Alternatives considered

- Keep direct IDE → SSH → worktree-script configuration: retains the historical
  proof, but couples every surface to host topology and onboarding mechanics.
- Put connection/authentication in a JetBrains plugin: ties reusable client logic
  to one IDE and adds a product prerequisite without demonstrated need.
- Mirror/export the workspace to Blaine: duplicates ownership and introduces
  synchronization/security problems before proving existing capability hooks.
- Identify the Personal Agent or Task with a worker/ACP session: conflicts with
  accepted durable lifecycle and replaceable-worker boundaries.

## Consequences

The workstation becomes a first-class capability surface while core ownership
stays unchanged. Onboarding can hide transport details, preserve other agents and
expose actionable diagnostics. Explicit registration/workspace identity permits
later multiple devices without path ambiguity.

The client must enforce local scope and correlate capabilities to authorized
operations. Standard ACP alone does not establish race-safe confinement,
conditional writes or durable effect idempotency. E1/E2 must prove these properties
or stop for a bounded provider decision. Disconnect can leave uncertain process
outcomes; truthful reconciliation is required instead of blind replay.

## Validation

### Hypothesis

A small local client can make a workstation usable through IntelliJ while keeping
Task identity, policy and evidence authoritative in Blaine, without ambient local
authority or a second project checkout on the host.

### Validation level

End-to-end, preceded by isolated configuration/protocol checks and integration
checks for registration and operation admission.

### Minimal validation

Run E0 per supported platform (Linux, macOS, Windows+WSL2), reporting untested
platforms explicitly; first E1–E3 may use a second native Linux workstation with
a real supported IntelliJ
instance and a synthetic Java 25 Gradle project. Record versions and capability
advertisements. Include connect twice, safe ACP config merge, actual confined read,
conditional write, bounded build/test, transport loss and a genuine typed human
question/response that resumes the same Task.

### Evidence

The canonical design's positive/negative gates pass with authoritative Task
snapshots, client operation receipts, immutable file/command/test evidence and
CompletionEvaluation. Demonstrate wrong-workspace/policy rejection, preserved
human WAITING, no host checkout, no ACP stdout contamination and no blind replay
of uncertain effects. Worker output or a successful exit alone is insufficient.

This ADR is unvalidated: prior Milestone 002 and D2 remain evidence only for their
recorded scopes. This design slice does not run new live acceptance.

### Not required for validation

Blaine plugin, custom GUI, public API, filesystem daemon, arbitrary shell, universal
capability catalog, new cloud plane, Fleet/Cloud telemetry completion, backup
continuation or all of D7. Existing service health is required where exercised.

## Reconsider when

The installed IDE cannot safely provide required capabilities; transport cannot
bind authenticated workstation identity; a local guard cannot enforce scopes; or
actual onboarding requires more complexity than the reusable client can justify.
Record the failed gate and review the smallest boundary change. Do not silently
weaken authorization, conflate session and Task, or introduce a host checkout.
