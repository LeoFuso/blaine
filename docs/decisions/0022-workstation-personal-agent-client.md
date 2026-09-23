# ADR 0022 — Workstation Connection and Personal Agent Client Architecture

**Status:** Accepted

**Validation:** E0.C primary transport accepted; full E0–E3 validation remains open.

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

**Selected correction, 2026-09-23:** embed stable tsnet in the Go workstation
client and connect to a private Blaine application endpoint. Use interactive
Tailscale browser enrollment, without a separately installed workstation CLI or
daemon. One installation persists one stable, revocable node identity and its
separate Blaine application key across process/reboot/upgrade. Store credentials
privately; ordinary disconnect does not erase them. Tailscale network identity,
Blaine application registration and ACP/provider authentication remain distinct.
The handshake verifies both the expected Hub node and signed Blaine server identity.

**E0.D admission clarification, 2026-09-23:** Tailscale is the workstation
admission authority in the current personal deployment. After a policy-authorized
tsnet peer passes the existing Blaine handshake, register its proven installation
automatically and idempotently. Registration owns durable identity/inventory,
reconnect/presence and future capability association, not a second authentication
system or manual operator approval. The temporary E0.C exact-node allowlist must
not turn into a second enrollment queue. Preserve application identity/key proof,
protocol validation and independent Task/workspace/PolicyGate authority.

Strong device revocation remains at the Tailscale boundary. Blaine may retain
retired/revoked product state and invalidate session routes, but cannot claim that
a registry flag protects a Hub against an identity with administrative SSH access
to that host. Additional Blaine approval requires a demonstrated threat and a
separate decision. This clarifies the planned E0.D contract; registration remains
unimplemented and the accepted E0.C deployment/evidence is unchanged.

This replaces SSH for product transport, removing remote Unix accounts, remote
shell/dispatcher framing and duplicated SSH trust plumbing from client onboarding.
Tailscale SSH remains for administration/diagnostics. The previous adapter is kept
until the new path passes acceptance. The decision follows measured Mac and WSL
spike connectivity/identity reuse and aims to remove workstation prerequisites,
align installation identity with future registration, and fit JetBrains provisioning.
The [E0.C closure](../../experiments/personal-agent-hub/e0c-direct/closure.json)
now records primary Mac live IDE acceptance, narrow effective network authorization
and canonical persistent Hub deployment. It does not claim full E0 acceptance.

Target Linux, native macOS and Linux inside Windows WSL2. Embedded userspace
connectivity needs no nested WSL daemon or TUN/root setup. The Windows IDE opening
a WSL project must launch the Linux client through an explicitly verified boundary;
project location alone does not establish agent execution location. No native
Windows client, custom plugin or topology substitution is introduced. Separate
designed, build-verified and runtime-verified platform claims. Connection grants
no filesystem or execution authority; E1/E2 retain local and PolicyGate enforcement.
ACP `authenticate` may own the normal browser enrollment UX; it does not register
or authorize a workstation by itself.

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

Full E0–E3 validation remains open. The [transport spike](../../experiments/personal-agent-hub/transport-architecture-spike/README.md)
and [E0.C migration](../../experiments/personal-agent-hub/e0c-direct/README.md) distinguish
Mac/WSL spike proof, local candidate/runtime proof and accepted primary Mac E0.C
live gates, including persistent service and effective tailnet policy. E0.D registration
is next and unblocked; full second Windows/WSL IDE acceptance remains E0.F.
Real Blaine-specific JetBrains provisioning/auth validation is required before E0
completion. E0.D registration has not been pulled forward.

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
