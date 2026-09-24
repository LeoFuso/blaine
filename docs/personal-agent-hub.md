# Personal Agent Hub — E0 through E3

**Design checkpoint: 2026-09-21. Status: architecture and implementation handoff;
E0.A foundation and E0.B network prerequisite implemented; E0.C and E0.D PASS; full E0–E3 remain unaccepted.**

The [E0.A client guide](../client/README.md) and
[isolated evidence](../experiments/e0a-blaine-client/README.md) record the five-command
skeleton, Go selection, platform paths and byte/process proof. Linux amd64 runtime
passed. [E0.B evidence](../experiments/e0b-tailscale-onboarding/README.md) adds native
Linux Tailscale detection, doctor and idempotent network readiness PASS. Linux
install/login mutations are fixture-tested; macOS is design/build/fixture-only,
and WSL host reuse is STOP pending a live spike.
[E0.C evidence](../experiments/personal-agent-hub/e0c/README.md) records profile,
strict transport/handshake and framing fixtures plus local host observations.
Second-workstation peer binding, production host dispatch/deployment and remote
ACP acceptance remained pending at that checkpoint; MIRIX readiness was UNKNOWN.
E0.D–F were untouched at that historical checkpoint. The migration and E0.D
evidence below records the subsequent dependency, registration and lifecycle proof. [Supporting client delivery](../experiments/personal-agent-hub/e0c/delivery.md)
now provides proven Actions Artifacts and the public `v0.1.0-alpha.1` prerelease;
it does not close those live gates. Command contracts
below describe the complete target, beyond these slices.

**Selected E0.C transport correction (2026-09-23):** embedded tsnet plus a direct
private Blaine protocol replaces SSH as the product path. The operator selected
this after the [Mac/WSL spike](../experiments/personal-agent-hub/transport-architecture-spike/README.md).
The [implementation evidence](../experiments/personal-agent-hub/e0c-direct/README.md)
records local tests, live Mac/WSL transport, real Mac IDE read-only exchange,
effective narrow tailnet policy and canonical persistent Hub deployment. E0.C is
PASS; [E0.D identity/inventory/presence](../experiments/personal-agent-hub/e0d/README.md)
also passed: primary Mac registration/reconnect, edge restart, alpha.4 upgrade and
distinct designated WSL registration. E0.E is next and not started. Full second-peer IDE
acceptance belongs to E0.F. The
[direct contract](contracts/host-connection.md) supersedes prior E0.C SSH/bootstrap
and external-workstation-Tailscale mechanics below. Historical E0.A/B evidence
keeps its original scope. Tailscale SSH remains for administration, not product
transport. The operator authorized `v0.1.0-alpha.2` publication to support real IDE
acceptance: [delivery status](../experiments/personal-agent-hub/e0c-direct/alpha2-delivery.json).
The current [alpha.4 delivery](../experiments/personal-agent-hub/e0d/alpha4-delivery.json)
provides the protocol-2 client. Development bootstrap is a shell-only release
installer delegating JetBrains JSON registration to the Go client; it is not ACP Registry publication.

**E1 design revision (2026-09-23, design only):** the operator selected IDE
delegation as workspace authority. Connecting Blaine to IntelliJ with **Pass
IntelliJ MCP server** enabled delegates the IntelliJ-exposed project surface; the
IntelliJ MCP server is the E1 provider; PolicyGate is the single enforcer and the
workstation client is a protocol/capability bridge. E1 is also the first consumer
of [Completion Contract v1](contracts/completion-contract.md). See
[ADR 0027](decisions/0027-ide-delegation-is-workspace-authority.md) and the
[E1 workspace contract](contracts/workspace-capability.md), which supersede this
document's earlier local-consent, local-guard and ACP-client-read statements for
E1 onward. Revised passages below are marked. Nothing is implemented.

Blaine is the persistent Personal Agent. A workstation is a registered execution
surface, and IntelliJ/ACP is its first interactive surface. The next product
increment makes that relationship usable without requiring the human to operate
network topology, remote paths, runtime ports, or Task protocol details.

This document owns the E0–E3 product architecture, command contracts, acceptance
and implementation decomposition. [ADR 0022](decisions/0022-workstation-personal-agent-client.md)
records the accepted architectural boundary. The [roadmap](roadmap/001-blaine-development-roadmap.md)
owns sequencing; [D2](daily-driver-d2.md) owns its existing implementation claims.
Recommendations below are implementation defaults subject to their stated gates.
This design changes no runtime, workstation, transport, or infrastructure.

Existing normative boundaries remain in [TaskSpec](contracts/task-spec.md),
[Task operations](contracts/task-operations.md), [frontier dispatch](contracts/frontier-dispatch.md),
[ExecutionEvent](contracts/execution-event.md) and the
[lifecycle/evidence policy](policies/task-completion-and-lifecycle.md). This document
specifies the Hub additions and links to those contracts rather than redefining
Task schemas, policy, cloud authority or completion ownership. The
[documentation map](README.md) identifies current authority versus historical proof.

The development [TaskSpec draft](personal-agent-hub-request.json) is **unsubmitted**:
no development Task-creation binding was available in this session. Local design
work was explicitly authorized; no runtime Task ID or execution state is claimed.

Quick navigation: [decisions](#decision-log), [identity/storage](#connection-identity-and-storage),
[platforms and WSL2](#platform-boundary-and-prerequisite-installation),
[commands](#command-contracts), [capabilities](#capability-and-workspace-contracts),
[milestones](#milestone-acceptance), [open questions](#open-questions),
[security](#security-boundaries), [implementation slices](#implementation-decomposition).

## Product and ownership

The target experience is:

```text
install Blaine client
blaine connect
complete interactive authentication if needed
blaine doctor
READY
open IntelliJ → open AI Chat → select Blaine → express intent
```

Example requests are “Investigate this bug and report the likely root cause,”
“Implement this requirement in the active workspace,” and “Review my assigned
work items and identify anything blocked.” The human selects outcomes and answers
meaningful questions. Blaine handles Task creation, memory, routing and policy.
Direct questions still need no Task; independent work does.

```text
Human → IntelliJ / CLI / future UI
                      |
              Blaine Personal Agent
                      |
        durable Tasks (Restate) + semantic memory (MIRIX)
                      |
             policy / routing / evidence / completion
                      |
        +-------------+------------------+
        |             |                  |
  workstations    external apps       workers/models
  files / IDE     issue trackers      Qwen / Jev
  terminal        source control      Codex / Claude
  build tools     communication       other adapters
```

Workers and workstations are orthogonal. Worker selection identifies who performs
bounded reasoning/work, not where filesystem or process effects execute. A Task
may combine memory, an issue-tracker read, workstation reads, a selected worker,
workstation edits/tests, verification and an authorized issue-tracker update.
Each external application retains ownership of its resources and separate grants.
These are synthetic future examples, not new integrations required by E0–E3.

| Owner | Responsibility and limit |
| --- | --- |
| Personal Agent | Interpret intent, select work strategy, route workers, explain decisions and evidence; never infer lifecycle from conversation. |
| Restate/runtime | Durable Task identity, lifecycle, waits, retries, response admission and recovery. |
| PolicyGate / CompletionVerifier | Authorize each concrete effect; evaluate accepted completion criteria from admitted evidence. |
| MIRIX | Semantic memory with provenance; never authoritative Task state or authorization. |
| Local Blaine client | Onboarding, connection profile, stable ACP launcher, workstation identity and local enforcement adapter; no Task scheduler or shadow Task ledger. |
| IntelliJ | Conversation, active project/editor context, advertised ACP capabilities and IDE permission UI. |
| Workstation | Local files, toolchain, processes and locally enforced workspace grants. No host checkout required. |
| Worker | Produce bounded proposals/results under Task grants; cannot grant itself capabilities or mark work complete. |

## Decision log

### Accepted

These decisions come from the agreed product direction and are safe to implement
within the milestone gates. Acceptance of a design is not live validation.

| ID | Decision |
| --- | --- |
| A1 | Ship a small local `blaine` client with only `connect`, `doctor`, `acp`, `disconnect`, `version` initially. No general CLI framework. |
| A2 | `connect` owns onboarding and IntelliJ configuration. Human workstations use interactive Tailscale login when needed; no long-lived tailnet administrative credential. |
| A3 | IntelliJ launches a stable local `blaine acp`. Transport and remote entrypoint details live behind the client connection profile. |
| A4 | No IntelliJ plugin is required for E0–E3. A later plugin may be a thin UI over the same client. |
| A5 | ACP session is not Task identity. Disconnect/restart never implicitly completes, cancels, approves or restarts a Task. Human WAITING requires an explicit matching response. |
| A6 | Workspace effects execute on the workstation. No NFS, mirroring, synchronization daemon, or second checkout on Blaine. |
| A7 | Connection grants no filesystem/shell authority. `workspace.read`, `workspace.write`, `workspace.exec` require Task, workspace, scope, PolicyGate and evidence checks. |
| A8 | IntelliJ/ACP is the first surface. Personal Agent identity and Task controls remain independent of it. |
| A9 | Worker and execution surface are separate concepts; Codex is not synonymous with workspace execution. |
| A10 | External applications compose with workstation capabilities through the same durable Task model and separate resource authority. |
| A11 | E0 closes without project mutation; E1 is read-only; E2 adds bounded effects; E3 proves natural-language coding with genuine human input and verified completion. |
| A12 | Existing D-series history remains intact. New platform/observability work is outside the E0–E3 critical path unless an observed blocker requires a bounded fix. |
| A13 | Selected correction: the workstation embeds tsnet with one private, stable, revocable node store per installation; no separate workstation CLI/daemon is required. Tailscale remains vendor private-network infrastructure, distinct from Blaine application identity and registration. |
| A14 | E0 architecture targets Linux, native macOS and Windows development environments using WSL2. One platform boundary owns OS differences; implementation evidence may initially cover fewer platforms. |
| A15 | Native macOS and Linux/WSL clients use userspace tsnet. No nested WSL daemon, TUN/root prerequisite or dependency on Windows Tailscale. Native browser approval remains explicit. Windows IDE → wsl.exe → Linux ACP stdio must be verified live. |
| A16 | (2026-09-23) IDE delegation is workspace authority: Blaine connected with `use_idea_mcp` enabled delegates the IntelliJ-exposed project surface. No second Blaine workspace approval. Delegated scope, Task relevance, user constraints (ACP `configOptions` as input channel) and effective authority stay separate; PolicyGate alone enforces. [ADR 0027](decisions/0027-ide-delegation-is-workspace-authority.md). |
| A17 | (2026-09-23) Completion is governed by a durable, revisioned Completion Contract with provenance, REQUIRED/ADVISORY levels, a closed verifier taxonomy and a capability journal. [ADR 0026](decisions/0026-completion-contract-is-a-durable-task-primitive.md). |

### Recommended

Defaults to use when beginning a slice, with reconsideration criteria in
[Open Questions](#open-questions): portable Go client; user-scoped binary/package;
embedded single-Hub deployment profile and direct private transport;
PostgreSQL workstation registry in E0.D; platform-native non-secret
local state;
explicit protocol compatibility; native Linux as the first live proof, with macOS
and WSL2 equally represented in the design and separately gated for release;
conditional
whole-file text writes; structured bounded build commands; conservative handling
of uncertain effects. These are not claims that packaging or live capabilities
have passed.

### Open

The gating unknowns are authenticated peer binding at the host launcher, supported
IntelliJ/AI Assistant versions, effective ACP filesystem/terminal behavior,
local race-safe enforcement and conditional writes, process lifetime after
transport loss, and the exact versioned extension/receipt contract. Resolve them
in the named slices; never turn an unverified assumption into a capability grant.
All questions, including those with straightforward defaults, are explicit below.

## Evidence baseline and D-series relationship

| Evidence | Established | Not established |
| --- | --- | --- |
| [Milestone 002](milestones/002-intellij-acp-durable-task.md), [ADR 0002](decisions/0002-intellij-acp-as-first-client.md) | Live IntelliJ → WSL `/usr/bin/ssh` → Tailscale SSH → ACP → Restate, same Task across sessions on 2026-09-14. | Current IDE compatibility, workstation onboarding or file/terminal effects. |
| [D2 acceptance](../experiments/daily-driver-d2/evidence/summary.json), [PersonalACP](../runtime/personal_acp.py), [workspace validation](../runtime/kernel/workspace.py) | Native Task controls, typed human response, exact-artifact verification, scoped POSIX read through official ACP test client. | Real IntelliJ filesystem read; canonical/symlink enforcement beyond the client; workstation identity; writes/exec; general natural-language coding. |
| [Platform services](platform-services.md), [rootless operations](platform-rootless-docker.md) | Recorded long-lived service, memory/inference, restart and infrastructure evidence in their stated scopes. | Fresh host readiness, full D1.G reboot acceptance or completed backup. |
| [Current JetBrains ACP help](https://www.jetbrains.com/help/ai-assistant/acp.html) (checked 2026-09-21) | Custom local agent configuration is documented. | Installed-version feature parity. Current help lists WSL as unsupported; the historical WSL PASS remains valid for its recorded run. |

| Product milestone | Existing workstream relationship |
| --- | --- |
| E0 — Connect a Workstation | New product entry point consuming D1 service availability and D2 controls. |
| E1 — Remote Workspace Read | Product acceptance of D3.A, strengthened with registered workstation/workspace identity. |
| E2 — Remote Workspace Effects | Bounded effects needed for D3.B; adds safe write/exec and remote evidence. |
| E3 — First Personal Agent Coding E2E | Synthetic product loop spanning D3.B and a precursor to D3.C. Does not by itself close D3.C useful real-work acceptance or all of D7. |

D1.G, D1.F backup continuation, D4's universal capability registry, D5 Telegram,
perfect Task-level OTel, Cloud logs/traces, Fleet, telemetry restart durability,
and new cloud control planes are not E0–E3 prerequisites. Existing services must
actually be available for the relevant acceptance; a demonstrated blocker may
pull forward the smallest responsible repair. Do not relabel incomplete platform
work as completed to justify product progress. Post-v0 “Cycle E” remains advanced
multi-worker work and is unrelated to the E0–E3 product numbering.

## Connection, identity and storage

```text
IntelliJ → local blaine acp → private authenticated transport
                          → host connection boundary → PersonalACP
                          → PersonalAgent → existing Restate binding

Task-authorized capability → PersonalACP → same connection/session
                          → local guard → IntelliJ ACP capability → workspace
                          ← bounded result/receipt ← admitted Task evidence
```

**Revised 2026-09-23 ([ADR 0027](decisions/0027-ide-delegation-is-workspace-authority.md)).**
The launcher/adapter is a protocol/capability bridge, not a filesystem daemon,
replacement ACP protocol or second policy engine. For E1 it relays the IntelliJ
MCP server the IDE delegates in `session/new` over a negotiated capability channel
of the direct transport, keeps IDE tokens local, and correlates each call to a
Blaine operation ID; it never alters standard ACP meaning or leaks onto
IntelliJ's stream. PolicyGate on the Hub is the single enforcement authority. The
earlier requirement that "local user-approved scope must independently bound
forwarded effects" is withdrawn: the operator's IDE delegation is the scope, and
the residual risk under a compromised host is recorded in
[security boundaries](#security-boundaries). Wire details:
[E1 workspace contract](contracts/workspace-capability.md#direct-protocol-extension).

### Distinct identities

| Identity | Recommended representation and source |
| --- | --- |
| Personal Agent / host | Stable server ID returned over verified transport, pinned to the configured host profile. DNS alone is not identity. |
| Network principal | Embedded Tailscale stable node and user/tag principal derived from the actual socket. Never accept a claimed peer ID from request JSON. |
| Client installation | Persistent Blaine Ed25519 key and derived installation ID, proven in the handshake. This is distinct from the server-assigned workstation ID; a different transport node cannot inherit an existing workstation through a copied key. |
| Workstation registration | Durable server-assigned inventory ID bound uniquely to the authenticated tailnet/stable node; created automatically on first accepted connection. The proven installation key is recorded, not used to nominate the registry ID. Display name and client UUID cannot authenticate or select another record. |
| Workspace | Registration ID + opaque workspace ID + locally canonical absolute root and path-platform tag. Two machines with `/home/user/project` are distinct. |
| Surface/session | Ephemeral ACP session/connection ID and generation bound to registration/workspace. Recreated on reconnect. |
| Task / operation | Existing durable Task ID and stable capability operation ID; neither derived from ACP session ID. |

Tailscale is the workstation admission authority for the current personal
deployment: the peer must be authenticated and authorized by the effective policy
for the private Hub service. Tailnet membership alone is not service authorization.
Blaine's existing handshake preserves server identity, installation-key proof and
protocol validation. Registration records that accepted installation; it does not
introduce another manual approval or authentication system. Task/workspace effects
still require separate authority, PolicyGate enforcement and local consent.

The E0.D implementation uses the existing PostgreSQL instance, an isolated
`blaine` logical database and `blaine_workstations` schema. Unique
`(tailnet, transport_node_id)` selects the durable record; changing installation
key or descriptive metadata on that same admitted node does not create a new
workstation. First/last seen are observations. Presence derives from expiring
connection leases, never a manually assigned product status. No Task ledger or
capability grants are stored here. See the [workstation contract](contracts/workstation-identity.md)
for fields, protocol compatibility, storage access and operator commands.
This follows [ADR 0018 storage ownership](decisions/0018-local-platform-durability-and-observability.md).
MIRIX, Redis, tsnet state, telemetry and IDE config are not registry authorities.

### E0.D registration: identity, inventory and presence

**Selected boundary:** automatically and idempotently register an authenticated,
policy-authorized tsnet peer after the existing Blaine handshake succeeds. Both
`connect` and an IDE-launched `acp` use this path; no separate enrollment command,
operator approval queue or per-device Blaine allowlist is the target UX. The E0.C
exact-node allowlist is a temporary acceptance/deployment control, not a second
admission authority to carry into E0.D. Its replacement must preserve trusted
socket-derived peer identity and effective narrow Tailscale service authorization.
E0.D replaces that temporary host allowlist with validated socket identity from Tailscale after network policy admits the connection. Deployment/live status is recorded in the [E0.D evidence](../experiments/personal-agent-hub/e0d/README.md).

E0.D must prove:

- First accepted connection creates one durable record and returns its receipt;
  concurrent attempts, response loss and retries return the same registration.
  Unauthenticated, policy-denied or invalid-handshake attempts create no record.
- Reconnect, process restart and binary upgrade preserve the same registration
  for the same authenticated tailnet/stable node binding, independently of ACP session or installation metadata. A supplied UUID, display
  name or copied receipt cannot claim another binding. Changed identities cannot
  silently inherit a previous installation's workspace or Task authority.
- Durable inventory survives connection loss. Current route/session generation
  is ephemeral; last-seen and connected/disconnected/unknown presence are server
  observations, not authentication or proof that a workstation is still available.
  An old session closing must not invalidate a newer accepted route. `doctor`
  remains read-only and does not register or refresh presence.
- Future capability associations have an identity to refer to, but registration
  and capability advertisements grant no workspace read/write/terminal authority.
  Workstation disconnect changes availability, never durable Task lifecycle.

Strong device revocation belongs to Tailscale for this deployment. Blaine may
record retired/revoked product state, preserve inventory history and invalidate
its own session routes; these are not independent device-security guarantees.
A retired installation can return through an explicit connect and the same
current Tailscale admission/handshake checks, without a second manual approval.
Network revocation and later re-admission remain Tailscale decisions; do not
silently transfer an old binding or its grants to a new node. Installation key replacement on the same authenticated node does not itself replace the workstation.

In particular, an application registry flag cannot protect the Hub against an
identity that retains administrative SSH authority over that host. Removing that
authority requires action at the Tailscale/host administration boundary. Session
teardown and policy-propagation latency must be measured, not described as instant
revocation. A new Blaine approval boundary requires a demonstrated threat and a
separate decision; it is not part of E0.D by default.

Recommended Linux and WSL-distribution paths: `$XDG_CONFIG_HOME/blaine/config.json` (default
`~/.config/blaine/config.json`) for schema version, connection profile, host/server
identity, client/registration IDs and transport selection;
`$XDG_STATE_HOME/blaine/` (default `~/.local/state/blaine/`) for owned-config receipts,
backups and redacted diagnostics. Persist permissions restrictively; atomically
replace owned files and detect concurrent changes. Store no private keys, login
URLs, tokens, raw conversations or workspace contents in connection config.
The selected E0.C path stores its application seed and embedded tsnet credentials
separately in private `state/direct-v1/` (0700 directories, 0600 files), never in
non-secret configuration or reports. Normal close/upgrade preserves them. On macOS use
`~/Library/Application Support/Blaine/config.json` and a
separate `state/` beneath that application directory; bounded logs may use
`~/Library/Logs/Blaine/`. On WSL keep the client config/state in the selected distro,
not a guessed Windows home. Detect Windows user/profile and IDE config ownership
separately through supported interop. Persist the selected distro/IDE execution
location so another default distro cannot redirect launches. No repository path is required on the workstation.

### Handshake and compatibility

Use a bounded application handshake on the private WebSocket connection before
ACP data. The embedded Hub public key/server ID and Tailscale stable Hub node are
independent pins. The host derives caller identity from the accepted socket,
requires proof of the installation's application key and binds that observation to
a fresh session. This is not registration or a workspace grant. See the
[direct transport contract](contracts/host-connection.md) for exact fields, limits,
fail-closed readiness, framing and replay/reflection rejection. Registration and
operation admission remain later slices; Task lifetime remains server-owned.

## Platform boundary and prerequisite installation

The native installer/status details in this section preserve the accepted E0.B
history. For the selected E0.C product path they are superseded by embedded
userspace tsnet: no separate workstation Tailscale CLI/daemon and no nested WSL
daemon. Platform paths, unprivileged operation and measured IDE execution
location remain requirements. Do not run the historical installer as E0.C repair.

E0 design supports **Linux, macOS and Windows+WSL2** through the same
`blaine connect` journey. An initial implementation may prove a subset, but reports
must name tested platforms and must not imply untested platform readiness. The
architecture gate is satisfied only when all three have defined installation,
authentication, config, process and diagnostics behavior. Cross-platform product
acceptance requires the respective live results; OS authorization prompts are
normal onboarding, not a UX failure.

Use a small internal `WorkstationPlatform` interface with `detect()`,
`install_prerequisites()`, `tailscale_status()`, `authenticate()`,
`configure_intellij()` and `diagnostics()`. `LinuxPlatform`, `MacOSPlatform` and
`WslPlatform` return typed observations and remediation plans to the shared connect
state machine. This is an internal adapter boundary, not a plugin framework.
Config-location discovery, executable resolution, structured subprocess arguments,
stdio/signal forwarding, process cleanup and path canonicalization belong behind
that boundary. Shared logic must not assume systemd, `/usr/bin/ssh`, POSIX signals,
case-sensitive paths or that the IDE and client share a home directory/OS.

Tailscale remains independently installed/operated vendor software. Blaine does
not embed its daemon, modify its networking/authentication model or implement a
VPN/overlay. Native status/login calls are orchestration of an external prerequisite,
not a Blaine network subsystem. Installation is a visible optional step within
connect: identify the supported vendor/package-manager method, explain the change,
obtain OS/admin authorization if needed, launch it, then re-detect and validate.
Declining or failing installation yields `PREREQUISITE_REQUIRED`, preserving the
flow for the next connect. Never persist raw login credentials or collect admin
passwords. Do not make `curl | sh` the only installation route; unsupported systems
receive exact vendor guidance within onboarding rather than an unexplained exit.
Doctor only detects and explains; it never installs or authenticates.

| Platform | External prerequisite and onboarding | Config/process boundary and live gate |
| --- | --- | --- |
| Linux | Detect distro/package manager and existing Tailscale CLI/service. Use a supported vendor repository/package or official installation path. Make package/daemon privilege escalation explicit, then use native interactive login. | Blaine runs as the user, never requires permanent root. Discover SSH and init system rather than require systemd. XDG client state; detect IDE execution home. Validate distribution/architecture and clean stdio. |
| macOS | Prefer the native Standalone Tailscale app. Detect app and usable CLI separately; guide/open the supported installer and native app/system settings when absent or unapproved. Invoke/direct native browser login and validate afterward. | App present does not imply CLI integration or VPN/system-extension approval. Respect native UI/admin approval; do not install a Blaine daemon or replace an existing Tailscale variant silently. Native Application Support state; discover CLI/app paths. |
| Windows + WSL2 | Native Windows Tailscale owns connectivity. The WSL Blaine binary detects and queries the Windows installation through supported interop, and reuses the resulting network path. | Client config/tooling stay in the selected distro. IDE may run on Windows or another supported location; discover it explicitly. Verify actual WSL2-to-host connectivity, path mapping and launch framing. Never install a second WSL daemon as an automatic repair. |

Vendor documentation provides Linux package choices and native Windows/macOS
installers. The macOS Standalone client can require extension/VPN authorization;
CLI integration is a separate installation detail. Use the installed variant's
supported mechanism and recheck instead of assuming a shell alias is available
to an IDE process. [Linux installation](https://tailscale.com/docs/install/linux),
[macOS installation](https://tailscale.com/docs/install/mac),
[Windows installation](https://tailscale.com/docs/install/windows),
[macOS extension approval](https://tailscale.com/docs/concepts/macos-sysext).

### WSL2 investigation and acceptance boundary

Official Tailscale guidance warns against simultaneous Windows and WSL2 Tailscale
because nested networking can cause MTU/packet-size problems. The accepted default
is Windows Tailscale plus a Linux-side Blaine client. An alternative with Tailscale
inside WSL requires an explicit deployment decision and separate proof.
[Tailscale WSL2 guidance](https://tailscale.com/docs/install/windows/wsl2).

Microsoft documents Windows executable interop, distribution version inspection,
and NAT/mirrored WSL networking. These are building blocks, not proof that the
selected tailnet route works. [Windows executable interop](https://learn.microsoft.com/en-us/windows/wsl/filesystems),
[WSL version commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands),
[WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking).

The following is a **proposed detection/probe sequence**, to be verified on a real
WSL2 workstation in E0.B/C/F. No WSL/Windows live investigation occurred in the design or E0.B implementation.
E0.B implements only bounded PATH-based host CLI observation and diagnostics; it
explicitly withholds guest-network readiness until this spike can run.

1. Detect a WSL environment from kernel/runtime markers and distro metadata;
   verify WSL2 and the exact selected distribution via trusted `wsl.exe` interop
   and version/list output. Parse Windows encoding and localized output carefully;
   an environment variable alone is not conclusive. If interop is disabled or
   version cannot be confirmed, report UNKNOWN and a precise remediation.
2. Locate the native Windows Tailscale executable using supported Windows install
   metadata/path discovery, not a fixed `/mnt/c` path. Query machine-readable
   native status (for example `tailscale.exe status --json`) with structured args
   and bounded timeout. Separate absent executable, stopped/unreachable service,
   login required and authenticated. A read-only Windows service query may explain
   a failed CLI; exact command/permissions are a live spike outcome.
3. Detect a second active WSL Tailscale daemon and report `TOPOLOGY_CONFLICT`;
   do not uninstall/kill it or silently choose an identity. The human must select
   a deployment mode. Query the host installation even when no Linux `tailscale`
   executable exists. Registration binds the Windows network device plus the
   particular WSL client installation/distro, not an invented Linux tailnet node.
4. From the WSL process, test DNS resolution, TCP reachability and verified SSH/
   Blaine handshake to the configured host. Compare with a native Windows probe
   only to isolate failure. Host authentication success is not proof of guest
   reachability. Record available NAT/mirrored/DNS/firewall observations and actual
   source identity seen by Blaine; do not infer them from `.wslconfig` alone.
5. Use a bounded stdio payload probe as well as a short handshake to detect a
   path that connects but stalls on realistic traffic. Record whether direct WSL
   SSH works or a host-native SSH process invoked via interop is necessary. The
   latter is a candidate transport mode, never a silent identity-changing fallback.
6. Start with **no added forwarding or config changes**: this is an outbound
   stdio connection, not a workstation listener. If direct use fails, retain DNS,
   route and transport evidence; recommend the smallest supported adjustment for
   review. Do not automatically add port proxies, broad firewall exceptions,
   subnet routing, a second daemon, or rewrite WSL networking/MTU. Whether any
   adjustment is necessary remains open until live measurement.

The JetBrains WSL support limitation is a separate IDE gate from Windows-host
Tailscale connectivity. WSL2 remains a first-class E0 target. E0.E must identify a
working supported IDE/process arrangement or report that platform's IDE integration
as blocked, even if network onboarding is healthy. Candidate Windows IntelliJ
launching a thin local adapter into a pinned WSL distribution must be tested; the
historical WSL experiment does not certify today's arrangement.

For Windows IntelliJ, the ACP config belongs to the detected Windows user's
`.jetbrains/acp.json`, not automatically WSL `~/.jetbrains/acp.json`. A proposed
stable local launcher shim may invoke the selected distro's absolute `blaine acp`
through `wsl.exe --distribution ... --exec ...`, with structured arguments and no
shell interpolation. It contains no SSH/host/remote-script configuration. Determine
whether the supported arrangement instead uses an IDE running in Linux before
writing anything. Never update both configs speculatively. Preserve cwd/path
namespace and signal/EOF semantics across interop; unsupported Windows/UNC workspace
paths fail visibly until a path adapter is proven. The shim format/location and
JetBrains version pair are open E0.E decisions, not implemented commands.

## Command contracts

Command behavior in this section describes the complete E0 target. The
[implemented command subset](../client/README.md#commands-and-exits) includes
network prerequisites and a gated E0.C host candidate; production host onboarding
remains unavailable and no full E0 claim follows.
Optional flags remain small: `connect --host NAME` for
first-use override and `doctor --json` for automation; normal operation needs
neither a host argument nor raw transport knowledge. Use a release/operator
connection profile containing the stable host name when available. If no profile
or persisted host exists, ask once for a host name and retain it after validation;
do not scan the tailnet. A ready host profile is an operator prerequisite, not
network configuration the workstation user must assemble.

### `blaine connect`

An idempotent flow based on observed state, not a persistent onboarding workflow:

| Stage | Observation/action | Branch and recovery |
| --- | --- | --- |
| 1. Inspect | Validate platform, executable, private installation state and IDE execution location. | Unsafe state or unsupported platform: STOP without overwriting. No system Tailscale prerequisite. |
| 2. Authenticate | Reuse this installation’s embedded tsnet identity; ACP authentication or connect opens normal interactive login when necessary. | Browser flow; no long-lived admin/auth key. Protect persistent node credentials and never change system Tailscale preferences. |
| 3. Resolve | Load persisted host, otherwise provisioned profile/explicit host. Resolve and test the selected host. | Offline/DNS/access failure: `REMOTE_UNAVAILABLE`, preserve previous configuration. No host guessing/fallback to public routes. |
| 4. Secure transport | Verify the expected Tailscale Hub node and signed Blaine server identity on the direct private endpoint. | Identity changes fail closed. No Unix account, SSH key/known_hosts input or shell framing. |
| 5. Handshake | Check server identity, protocol compatibility and runtime readiness. | `INCOMPATIBLE` or `REMOTE_UNAVAILABLE`; registration is not proof of runtime readiness. No service restart or deployment mutation. |
| 6. Register | Automatically upsert durable inventory/presence for the policy-authorized network peer and proven installation key after handshake. Persist receipt after authoritative success. | Lost response: retry the same binding, return the same registration. No second manual approval. Tailscale controls revocation/re-admission; a changed binding cannot inherit an old identity or grants. |
| 7. Configure IDE | Merge owned Blaine agent entry with stable absolute local launcher. | Absent IntelliJ: retain connection, report `IDE_MISSING`, not full READY. Running IntelliJ: merge safely, report reload/restart action only if needed. Name conflict or malformed config: STOP with a reviewable proposed change. |
| 8. Diagnose | Perform the read-only doctor checks. | All required E0 checks pass: `READY`. Exact existing connection/config: `ALREADY_CONNECTED`, then current diagnostics. Repairable owned drift: repair only that entry and verify again. |

Second invocation must preserve registration ID, other agents, tailnet settings
and Task state. Never treat an old READY stamp as current health. If interrupted,
reconstruct onboarding progress from observations and durable registration/config
receipts; repeat only idempotent operations. Connection setup does not resume
human WAITING Tasks. No prompts for safely inferable paths or redundant consent;
ask only for prerequisite installation/OS authorization, login, untrusted identity
change or conflicting user-owned config.

Recommended connect exits: `0` READY/already connected and healthy; `2` local or
human action required (prerequisite/OS approval, auth, IDE, conflict);
`3` remote unavailable; `4`
incompatible; `1` unexpected internal failure; `64` invalid usage. Report the
specific named state as well as the exit code.

### IntelliJ configuration contract

Current JetBrains help specifies `~/.jetbrains/acp.json`, `agent_servers`, absolute
local executable paths and `args`; it describes immediate discovery with an IDE
restart as troubleshooting. Managed installations can restrict custom agents.
This establishes a configuration mechanism, not verified capability behavior.
[JetBrains ACP documentation](https://www.jetbrains.com/help/ai-assistant/acp.html).

Illustrative **entry fragment**, not a replacement for the complete file:

```json
{
  "Blaine": {
    "command": "/home/example/.local/bin/blaine",
    "args": ["acp"]
  }
}
```

Implementation must parse the existing file, reject duplicate keys or unexpected
structure, preserve unknown keys, environment fields, defaults and every other
agent. Keep a permissions-preserving backup and original content digest; update
only the owned entry, using a same-directory temporary file and atomic replacement
with a concurrent-edit check. Identical config requires no rewrite. Do not follow
an unexpected config symlink or change file ownership silently. An existing
unowned `Blaine` entry is a conflict requiring explicit adoption, even if it is a
historical SSH entry. Rollback restores only the owned change when its receipt
still matches; never restore a stale whole-file backup over later edits.

Record IDE/AI Assistant versions, installation path and OS/process location.
Resolve ACP config in the IDE user home through the platform adapter. A running IDE is not a
reason to terminate it; first test discovery/reload, then request restart if needed.
Config validation includes parse/schema, executable existence, correct args,
clean stdio probe and live agent selection. Doctor can report disk configuration
valid while marking IDE reload/launch unverified. A one-time live IntelliJ smoke
is required for E0 acceptance, not every invocation of doctor.

Do not enable MCP forwarding as an onboarding side effect. Preserve global
settings for other agents. Use a documented per-agent disable option if supported
by the installed version; otherwise the Blaine adapter must reject/ignore incoming
MCP server descriptors and expose no MCP-derived capabilities. That rejection
needs a negative test; changing global defaults is not the fallback.

### `blaine doctor`

Read-only and bounded: inspect config/process availability; perform reachability,
identity/handshake and non-mutating readiness reads. No login, registration,
last-seen update, config repair, Task creation/resume, model generation, embedding
request, memory mutation or service restart. The host needs a read-only diagnostics
operation whose inspection does not refresh the registration lease. Network audit
logs may naturally record access; no application mutation is requested.

| Check | Required observation |
| --- | --- |
| Client | Version, OS/architecture/platform adapter and protocol; config schema; WSL distro/version and IDE process location where relevant. |
| Tailscale | Native owner installed/running/authenticated; macOS app/CLI/OS approval separately; WSL Windows host status and duplicate-daemon detection. Redact personal identifiers in export. |
| Host / transport | Actual client-process DNS/reachability and verified handshake, selected mode; on WSL distinguish Windows host readiness from guest route and report UNKNOWN forwarding needs until measured. |
| Blaine | Compatible handshake, active registration, correct remote runtime/deployment readiness. |
| Restate | Reachable and intended workflow deployment ready, not merely listening. |
| MIRIX | Read-only readiness and dependency status. |
| Generation / embeddings | Configured endpoints/models present and ready, sampled timestamp; no inference benchmark or hidden generation. |
| IntelliJ ACP | Installation/version compatibility, config parse/owned entry/launcher; report disk validity separately from live IDE selection evidence. |

Human output is concise and actionable; JSON output is versioned with timestamp,
`overall`, and `checks[]` containing `id`, `status`, `code`, `summary`,
`remediation`, `observed_at`. Statuses: `PASS`, `FAIL`, `UNKNOWN`, `NOT_APPLICABLE`.
Unavailable downstream checks are UNKNOWN with the blocking dependency, never
PASS. Initially bound each probe to 5 seconds and the run to 30 seconds; adjust
from live evidence. Do not expose credentials, environment dumps or raw service
responses. Local output may show necessary paths; exported diagnostics redact
private paths/identity by default.

Illustrative healthy output:

```text
client                 PASS  0.x / Blaine protocol 1
network / transport    PASS  authenticated, verified private host
Blaine / Restate        PASS  compatible, registered, deployment ready
MIRIX                  PASS  ready
generation / embeddings PASS ready
IntelliJ ACP            PASS  configuration valid
READY — select Blaine in IntelliJ AI Chat
```

READY means the required E0 checks passed at observation time. It does not assert
workspace grants, E1–E3 capability support or future availability. Missing IDE or
unknown required readiness produces NOT_READY; scoped diagnostic successes remain
visible. JSON stdout is exactly one JSON document; explanatory diagnostics go to
stderr. Exit `0` only if required checks pass; `2` local/auth/IDE remediation;
`3` remote failure or unknown required readiness; `4` incompatibility; `1` internal
error; `64` usage. When multiple conditions occur choose `1`, then `4`, `2`, `3`;
the JSON preserves all conditions. Inspection must never open a browser or modify SSH known-host trust.

### `blaine acp`

This is the stable launcher and transport adapter. Standard ACP initialization
exposes the agent-owned authentication method; an explicit ACP `authenticate`
request may open the browser to enroll the embedded node. This replaces the former
CLI-only login restriction. Authentication and connection diagnostics never appear
as unframed stdout. E0.D adds automatic durable registration after the accepted
handshake; it does not require a separate manual pairing step before IDE use.

No PTY. Keep stdin/stdout exclusively ACP JSON-RPC with correct framing,
backpressure, request correlation and bidirectional client capability calls.
Do not send banners, readiness JSON, shell output, debug prints or worker output
into the protocol. Operational diagnostics go to stderr and optional bounded,
redacted local logs. Transport diagnostics stay on stderr; command output becomes typed
capability evidence, never unframed stdout. An invalid/non-ACP remote stdout line
fails the connection visibly; do not silently filter arbitrary banners and risk
misinterpreting a stream. Unknown ACP extensions must not acquire authority.

On EOF/signal/transport loss, release owned transport resources and invalidate
session routing. Do not issue Task cancel, response or create operations. Do not
silently reconnect mid-request and replay a prompt. The IDE may launch a fresh
session; the user surface then queries authoritative Task state. ACP turn cancel
stops that interaction; explicit Task cancellation remains a distinct semantic
operation. Later E2 process cleanup is an execution-resource action with its own
receipt and must not be presented as Task cancellation.

### `blaine disconnect` and `blaine version`

`disconnect` disables local launches and active owned connections, removes only
an unchanged client-owned ACP entry, and reports disconnected/retired product state
when the Hub acknowledges it. If unreachable, report local disconnect and unknown
remote presence; do not claim device revocation. Ordinary disconnect preserves
installation identity for reconnect. Strong network revocation is a separate
Tailscale operation, not a registry flag. Preserve Task IDs/results and workspace
files; never cancel Tasks, log out system Tailscale, delete credentials or affect
other agents implicitly. Product retirement and local cleanup are idempotent.
`version` is an offline read of
client/build/protocol versions with no network or filesystem mutation.

## Capability and workspace contracts

### Future session controls in the IDE

ACP `configOptions` is the intended future UI surface for Blaine session controls:
available Hub models, read-only mode, approval mode and bounded execution. Blaine
will supply enforceable choices; the IDE presents supported controls and sends
selections through `session/set_config_option`. Boolean controls require the
corresponding advertised client support; actual target IDE behavior must be verified.
[ACP session configuration](https://agentclientprotocol.com/protocol/v1/session-config-options).
This is a documented direction, not an E0 implementation or acceptance gate.
Do not advertise a mode, model choice or capability before Blaine can enforce it.

A selection requests session policy; it does not confer authority. Effective
capability remains bounded by implementation, live negotiation, local Workspace
scope, Task authority and PolicyGate. A session change must not silently broaden
existing durable Task grants. Restate retains Task lifecycle independently of the
selector or IDE session. E1/E2 own workspace read/write/execution enforcement.

**E1 (revised):** selections are operator constraints delivered by the IDE and
compiled by Blaine into the Task's effective authority; the option layer is an
input channel, not a policy engine. E1 advertises only `access = read_only`.
See [effective authority](contracts/workspace-capability.md#effective-authority).

Prompt `resource_link` data is independent of these selectors and capability
advertisements. E0 accepts links as inert references with an explicit unused-context
notice. Receiving a URI or context from the IDE does not authorize resolving,
reading or executing it. From E1 a link is a relevance hint inside the delegated
scope; reading its target is an ordinary admitted `workspace.read` operation.

### Negotiation matrix

Protocol support, IDE support and Blaine support are separate evidence columns.
Current upstream documentation was checked on 2026-09-21.

| Capability | ACP protocol | JetBrains evidence | Current Blaine | Gate |
| --- | --- | --- | --- | --- |
| Read | `fs.readTextFile` advertises `fs/read_text_file`. | Target IntelliJ must advertise and successfully execute it. | D2 checks advertisement and reads through the official SDK fixture. | E1 live read, identity and confinement. |
| Write | `fs.writeTextFile` advertises `fs/write_text_file`, supplying path/content. | Installed behavior and editor/disk consistency unverified. | No D2 write adapter. | E2 conditional write and negative tests. |
| Exec | `terminal` advertises create/output/wait/kill/release methods. | No target live proof; do not infer from the IDE having a Terminal tool window. | No D2 terminal adapter. | E2 capability and lifecycle probe before execution. |
| Other | ACP supports session/control/UI mechanisms; not a universal file listing, diff, stat or CAS API. | Verify each needed method/extension explicitly. | D2 supplies bounded controls, not generic IDE navigation. | Add only a demonstrated need. |
| IntelliJ MCP (E1 provider, revised) | ACP `session/new` `mcpServers` carries MCP servers the IDE passes. | Per-agent "Pass IntelliJ MCP server" (`use_idea_mcp`, default off); read/search/list tools respect project/library/SDK roots; mutating/exec tools share the server. Upstream source checked 2026-09-23; installed payload unobserved. | E0.C strips client capabilities and denies non-empty MCP forwarding. | E1.A records the real delegated surface; E1.B bridges it. |

ACP filesystem reads can reflect unsaved editor content; a hash of that content
is not necessarily a disk hash. The base write request has no expected-content
hash or atomic compare-and-swap field. [ACP filesystem specification](https://agentclientprotocol.com/protocol/v1/file-system).
Terminal results provide output, truncation and exit status, with lifecycle
methods for kill and release; separate stdout/stderr is not guaranteed by that
result shape. [ACP terminals specification](https://agentclientprotocol.com/protocol/v1/terminals).
Capabilities and ACP version are negotiated at initialization.
[ACP initialization](https://agentclientprotocol.com/protocol/v1/initialization).

A public JetBrains issue includes a Rider 2025.3.3 handshake with file capabilities
true and terminal false. It is a historical report, not proof of current IntelliJ
behavior or the issue's resolution. It strengthens the requirement to record the
actual handshake. [JetBrains issue LLM-25770](https://youtrack.jetbrains.com/projects/LLM/issues/LLM-25770/Incorrect-implementation-of-ACP-fs-writetextfile).

Effective capability = installed implementation ∩ live negotiation ∩ local scope
∩ Task grant ∩ PolicyGate decision. Persist the observed advertisement for diagnosis;
never use yesterday's advertisement as current permission. Missing/false capability
fails explicitly; no host filesystem fallback, hidden MCP forwarding or arbitrary
shell workaround. **Revised for E1:** "local scope" in this formula is the IDE
delegation, and the IntelliJ MCP server delegated by the operator is the E1
provider, which supplies project search without a Blaine search service. MCP use
is explicit, delegated and journaled — not the hidden forwarding forbidden here.

### Workspace identity and path confinement

**Revised for E1 (2026-09-23).** A Workspace is an IDE project delegated from one
registered workstation; its identity is derived from registration, path platform
and canonical project root, with no Blaine consent step. For the read-only IntelliJ
MCP provider the IDE project model is the confinement boundary; PolicyGate rejects
absolute, parent-traversal and URL arguments and pins the target project. The
"local user selected / local consent" and "actual filesystem provider must enforce
access-time confinement" requirements below remain the design input for **E2
writes**, where the provider question is still open (Q11). E1 authority:
[workspace contract](contracts/workspace-capability.md#workspace),
[confinement](contracts/workspace-capability.md#confinement).

Treat ACP `cwd` as a proposed workspace root, not authorization. On the workstation,
canonicalize it, verify the local user selected that project and bind the canonical
root to a workspace ID under the authenticated registration. Tasks refer to that
identity and a bounded grant, not merely a path string. The first E1 provider proof may use native Linux POSIX paths;
record path semantics explicitly behind the portable platform boundary. macOS
case/Unicode behavior and WSL/Windows path namespaces need their own validation;
never emulate them with ad hoc string replacements. Moving the project, changing the canonical root
or replacing the device requires explicit rebinding. Do not resolve remote paths
on Blaine or assume a same-named host path is equivalent.

Use workspace-relative paths in Task requests; reject absolute paths, parent
traversal, NUL, unsupported encodings/separators and paths outside the grant. Convert
to the ACP absolute path only at the local boundary. Resolve symlinks locally and
verify the final target stays under the authorized root. New-file writes validate
the existing parent. For E1/E2 start with regular text files and deny symlink paths,
special files, links to external targets and unapproved metadata/secret paths.
Writes also reject hard-linked targets or require safe replacement semantics.

Lexical prefix checks and preflight `realpath` are insufficient against concurrent
rename/symlink changes. The actual filesystem provider must enforce confinement
at access time (descriptor-relative/no-follow access or an equivalently proven
client implementation). An interposing launcher check cannot prove what IntelliJ
later opens. E1 STOPs on a failing containment probe; do not silently certify an
unsafe client. A bounded local provider/extension may be proposed if needed, but
replacing the required E1 ACP client read needs an explicit design revision.

### Task operation and evidence envelope

Before an effect, the runtime records Task ID, operation ID, grant/revision,
registration/workspace identity, operation kind, exact request digest and limits
— from E1 as an `admitted` entry in the Task's capability journal
([Completion Contract](contracts/completion-contract.md#capability-journal)).
**Revised:** the bridge correlates this operation to the relayed call; it does not
re-authorize it. Session generation prevents stale routing. Evidence
admission checks the same identities, expected pending operation, revocation and
payload bounds; random client JSON or a worker artifact path cannot satisfy it.

Retain immutable evidence references/digests in the existing artifact boundary,
with execution location, relevant client/provider/tool versions and timestamps.
Restate owns operation progression; any local crash receipt stores only effect
outcome/deduplication information and is not a Task ledger. Exact wire schema and
extension names must be frozen with fixtures before E1 effects are admitted.
Retain runtime read/status evidence separately from diagnostic logs.

### E2 write semantics

Recommended minimal contract: bounded UTF-8 whole-file creation/replacement of
explicitly allowed regular files; include expected previous SHA-256 or an explicit
`absent` precondition, new content hash, size cap, operation ID and workspace grant.
No delete, rename, chmod, arbitrary binary write or patch engine initially. A
worker may propose a diff; deterministic code lowers it into this contract.

The provider must atomically check the precondition and commit the replacement
relative to concurrent editor/filesystem edits, or offer an equally strong
serialized guarded operation. Preserve allowed file mode, reject unsafe links,
and reread committed content for evidence. Read-then-unconditional-ACP-write is
not compare-and-swap; a post-write read cannot repair a lost update. Base ACP
alone does not establish this contract. E2.A must prove an installed provider
extension or identify the smallest additional local mechanism. If unavailable,
STOP write enablement and record a scoped design decision; do not quietly weaken
to best-effort overwrites or add a filesystem daemon.

Dirty editor buffers require explicit reconciliation before disk-based edits or
build verification. Record whether read bytes came from editor state or disk.
If that distinction cannot be established, require a saved/clean fixture for the
initial proof and do not claim broader safe dirty-buffer support. Evidence records
before/after hashes, file identity/path, diff, provider receipt and disk readback.
On reply loss, reuse the operation ID and query the effect receipt; a matching
current hash alone does not prove who performed the write. Uncertain outcomes
remain pending reconciliation without a blind overwrite/retry.

### E2 exec semantics

Recommended first command is a reviewed fixture build/test profile resolving to
an exact executable plus structured args, for example the authorized project's
Gradle wrapper with `--no-daemon test`. This permits a reviewed script as an
executable, not arbitrary shell text. No `sh -c`, pipelines, command substitution,
arbitrary executable paths, user-provided init scripts or unrestricted flags.
Validate executable identity and wrapper/build configuration before dispatch.

Bind command profile, exact args, canonical cwd, relevant source/build hashes,
timeout, output cap and explicit environment policy to the operation/grant.
Start with a 120-second deadline and 1 MiB output cap for the tiny fixture; exceeding
a limit is a recorded non-success, not permission to lift it automatically.
Use a minimal deterministic environment including approved JDK/JAVA_HOME and
controlled PATH; omit credentials, SSH agent sockets and unsafe inherited
`JAVA_TOOL_OPTIONS`/Gradle injection variables. Standard ACP env fields do not
prove inheritance can be removed: the provider must demonstrate this property.

Allowlisting `gradlew` is not a sandbox: build scripts/plugins/tests execute code.
For E2/E3 use a reviewed synthetic project, pinned wrapper/toolchain/dependencies,
bounded local consent to that build, and no ambient secrets. Changes to build
logic invalidate the command approval. Actual containment of malicious project
code requires an established OS isolation mechanism or later design; do not claim
cwd confines a process or arbitrary projects are safe. A script-hash allowlist
alone also does not cover transitive build inputs.

Use ACP terminal create → bounded output/wait → exit evidence → release, with
kill on deadline/cancel and confirmed cleanup. Retain command/args, cwd identity,
tool versions, start/end, exit code or signal, output/digest, truncation and test
report references. If output is merged, label it merged; never manufacture separate
streams. Deterministic verification checks report freshness and completeness.
Timeout, missing exit, truncation that loses required evidence or unknown process
state cannot count as success. Kill/release must cover descendant build processes;
probe the installed client, including IDE termination. If unavailable, disable exec
and STOP E2; a session-owned local process provider is a separate recommended
fallback decision, not an automatic change of provider or new daemon.

An ACP terminal ID is transient, not a durable operation key. Do not replay exec
on reconnect. Runtime interruption/cancellation and native process termination
are distinct; pending kill on an unreachable workstation is reported as unknown,
not completed. Confirm cleanup or reconcile the outcome before another dispatch.

### Evidence and completion

For E1, admit the bounded bytes, source-kind, file/workspace/registration identity,
content hash and matched operation receipt to the same Task. For E2/E3, add exact
change set/diff, before/after disk hashes, execution profile and source revision,
command output/exit, structured test report and any required artifact hashes.
Store private file evidence within the authorized artifact/context boundary;
logs and metrics carry references, not raw source or secrets.

Completion Contracts declare criteria before execution
([Completion Contract v1](contracts/completion-contract.md)). E1 uses
`capability_journal` and `evidence_citation` criteria instead of a known fixture
digest; see the [E1 contract examples](contracts/workspace-capability.md#completion-contract-examples). E2 adds deterministic contract predicates for the exact allowed
change set, command identity, terminal outcome and admitted test report. E3 adds
observable CLI behavior, required human decision evidence and no unrelated writes.
These are bounded extensions to the existing verifier, not worker-written claims
or a second completion engine. A successful worker exit, a write acknowledgement,
a process exit of zero, or an old test report alone cannot complete the Task.
Recompute hashes/admit tool receipts, check source/result correlation and run
positive and negative verification. A compromised workstation can fabricate its
own observations; E0–E3 do not provide hardware attestation or independent rebuild
proof. Evidence trust is explicit about this execution boundary.

## Reconnect and multiple surfaces

| Event | Required behavior |
| --- | --- |
| Network loss / laptop sleep | Invalidate live route; preserve durable pending operation/Task. Suspend on a typed unavailable-surface dependency when progress requires it. Runtime owns waits/retries, not client polling. |
| IntelliJ closes / ACP crashes | Drop session routing; Task is unchanged. E2 reconciles process/write outcomes before any new effects. |
| Fresh ACP session | Authenticate/re-negotiate; bind only the same registration/workspace with fresh session generation. Query Task by durable identity. Never create a replacement Task automatically. |
| Task already WAITING for human | Display the pending question; connection/heartbeat/registration never resolves it. Only a matching explicit response resumes the same Task. |
| Pending read | Re-read only the still-authorized pending operation; duplicates may occur but accepted evidence is one-shot and cannot be replaced. Source changes are visible to the verifier. |
| Pending write/exec | Inspect durable operation and available receipt; unknown outcome blocks redispatch. No promise of exactly-once remote execution from ACP alone. |
| Workstation unavailable | Non-workspace Task steps may progress if independently authorized. Workspace-dependent work waits; no host checkout or alternate workstation substitution. |
| Retired, network-revoked or unavailable workstation | Invalidate the affected route; preserve inventory and Task state. Reconnect revalidates Tailscale admission, installation binding and session generation. Last-seen age or a product flag is not strong device revocation; future effects still require current grants. |
| Multiple surfaces/devices | Task identity is global within the existing single-user namespace. Surface grants remain per registration/workspace. A status query elsewhere does not retarget effects. |

Recommend one active effect route per Task/workspace with runtime-admitted route
generation fencing. Two IDE windows can inspect a Task, but cannot race to execute
the same pending effect. Changing workstation/workspace is an explicit scoped
retargeting decision, outside initial E0 acceptance. No Task-listing subsystem is
required: retain the Task ID/result link in the surface and query runtime state.
The existing D2 completed-workflow retention limit still applies; this design does
not promise perpetual queryability or migrate old journals.

## Milestone acceptance

Every milestone retains client/IDE/AI Assistant/Tailscale/transport/server versions,
fixture identity, authoritative Task snapshots where relevant, redacted protocol
transcript and evidence digests. A synthetic ACP client can prove contracts but
cannot replace required live IntelliJ acceptance on a second workstation. Capture
absence of the project on the Blaine host and positive evidence that the operation
occurred on the registered workstation. No live tests were run by this design slice.

### E0 — Connect a Workstation

**Goal:** a new Linux, macOS or Windows+WSL2 workstation can use the same
`blaine connect` flow with platform-specific prerequisite assistance and native
login/authorization. The design covers all three; initial live implementation
acceptance may be platform-scoped and must say so.

**Positive acceptance per implemented platform:** install the distributed client
on a workstation separate
from Blaine; detect prerequisites; complete native browser login if necessary;
resolve the provisioned host; verify transport/handshake; register once; safely
merge IntelliJ config; doctor reports READY; open an actual supported IntelliJ
instance and select Blaine. A simple direct exchange proves clean ACP launch.
Repeat connect with the IDE closed and running: same registration, no duplicate
agent, no changed unrelated config. Repair owned launcher drift. No project writes
or shell commands are necessary. A development install alone cannot close that platform's E0 acceptance.

Retain this platform matrix even when the first implementation is Linux-only:

| Target | Required E0 path and platform-specific evidence |
| --- | --- |
| Linux | `blaine connect`: absent prerequisite → visible supported package install/admin prompt → native login → verified connection/IDE → READY; user-level Blaine afterward. |
| macOS | `blaine connect`: native app/CLI detection or guided install → required system-extension/VPN/native UI approval → browser login → verified connection/IDE → READY. Declined approval stays actionable, never false READY. |
| Windows+WSL2 | `blaine connect` in selected distro: confirmed WSL2 → native Windows Tailscale install/status/login → verified route from WSL → supported IDE/launcher mapping → READY. Prove no second daemon and record whether any network adjustment was actually necessary. |

Live proof on fewer platforms is a scoped implementation checkpoint, not an
exclusion from E0 architecture or a claim that all targets passed. Unsupported
current IDE behavior may block full WSL2 product acceptance independently of
successful host networking; retain that blocker until verified resolution.

**Negative acceptance:** missing Tailscale, unauthenticated/expired login, wrong
host/host key, removed device, revoked registration, remote service down, failed
Restate/MIRIX/model readiness, incompatible protocol, absent/managed-restricted IDE,
missing macOS CLI/extension authorization, disabled WSL interop, WSL1, duplicate
Tailscale daemons, Windows-connected/WSL-unreachable, incorrect distro/home mapping,
malformed ACP config, conflicting Blaine entry, concurrent config edit and remote
stdout banner must fail with the documented state and remediation. Preserve all
unrelated state. Verify doctor is read-only and disconnect neither cancels Tasks
nor logs out the tailnet. Test missing feature/unknown readiness is not READY.

**STOP:** unverifiable host/peer identity, dependency failures hidden as healthy,
config damage, false READY, ACP corruption, or a demand for broad admin credentials.

### E1 — Remote Workspace Read

**Goal:** prove an actual connected IntelliJ workstation as a read capability
provider, without mutation or a project checkout on Blaine.

**Revised acceptance (2026-09-23) — authoritative:** the
[E1 acceptance matrix](contracts/workspace-capability.md#e1-acceptance) replaces
the text below for provider, authority and completion. Its core additions: the
operator's `use_idea_mcp` delegation is the only workspace approval; a READ_ONLY
Task runs an investigation through the delegated IntelliJ MCP surface, completes
by its Completion Contract, and the capability journal shows zero mutating
admissions although mutating tools were delegated; scripted mutating proposals
produce journaled denials and zero IDE calls. The prior text is retained for its
still-valid identity, reconnect, human-WAITING and no-host-checkout requirements;
"read a known fixture through IntelliJ's ACP filesystem method" and "register …
under local consent" are superseded.

**Positive acceptance (prior text):** create a disposable project only on a second workstation;
open it in IntelliJ and record `cwd`/capability advertisement; register its canonical
workspace under local consent; submit a read-only Personal Agent request; record
the durable Task and pending authorized operation. Read a known fixture through
IntelliJ's ACP filesystem method, return bytes/receipt to that **same Task**, and
verify content hash and execution identity. Disconnect while the operation waits;
reconnect in the same workspace, inspect and explicitly continue the pending read.
Also preserve a human WAITING Task across the disconnect without auto-response.
Record root identity and actual client call, not only the returned content.

**Negative acceptance:** mismatched device with identical path, wrong project,
absolute/parent traversal, external symlink, symlink-swap race, absent read
capability, oversized response, stale/replayed operation, wrong Task result and
unexpected digest. Each rejects without escaping scope or accepting completion.
Host-side sentinel paths must never be read. No project writes/exec grants exist.

**STOP:** lack of live IntelliJ capability, failure to bind workspace identity,
insufficient client confinement, result accepted into a different Task, or any
host checkout required. D2 fixture PASS alone does not close E1.

### E2 — Remote Workspace Effects

**Goal:** add the smallest safe workstation write and execution contracts.

**Positive acceptance:** after E1, use a reviewed disposable workspace on the second
workstation; authorize an exact file set and build profile; make one conditional
write, record the actual diff/hashes, execute the permitted test/build locally,
retain exit/output/report evidence and evaluate completion deterministically.
Prove stale file rejection and confirmed process deadline cleanup. Complete one
positive verifier case and reject a deliberately failing test/incorrect artifact.

**Negative acceptance:** unauthorized path/write, stale expected hash, dirty buffer
conflict, symlink/hard-link escape, race during commit, unapproved executable/args,
shell metacharacter attempt, outside cwd, inherited secret/injection environment,
changed build script, absent terminal support, timeout, lost write/exec response,
stale test report, and duplicate/replayed operation. No blind effect replay after
IDE/network interruption. Verify unrelated files remain unchanged and unsupported
capability never falls back to host execution.

**STOP:** base ACP cannot safely satisfy write preconditions, local process/env
control is insufficient, outcome is unknown, provider hides failures, or completion
can be accepted from worker text. Do not replace a STOP with unrestricted shell.

### E3 — First Personal Agent Coding E2E

**Goal:** natural-language intent produces a verified change and a useful result
through the same persistent Personal Agent and Task.

Use a small Java 25 Gradle project existing only on another workstation. Pin a
Gradle wrapper version verified to support running/building with Java 25 when the
fixture is implemented; select exact dependencies then, not from an assumed host
JDK. An example request is: “Add a CLI that totals integer arguments. Ask me how
invalid inputs should be handled, then implement the selected behavior and test
it.” Use deterministic inputs/outputs and a genuine unresolved behavior choice,
not a ritual approval after the answer has already been selected.

**Required flow:** IntelliJ request → semantic normalization → durable Task →
scoped workspace context → bounded MIRIX retrieval with provenance → documented
worker routing → REQUEST_HUMAN → durable WAITING → actual user response → resume
**same Task** → authorized writes/exec → tests/build/evidence → CompletionVerifier
→ runtime terminal completion → useful result/diff/test summary in IntelliJ.
`REQUEST_HUMAN` denotes the existing typed human capability/decision contract;
`COMPLETE` denotes verified terminal completion using the runtime's actual state
label, not a new lifecycle enum. Local Qwen/existing worker is the default when
adequate. A paid worker needs existing dispatch authorization and budget; E3 does
not require a particular model/vendor or a new worker framework.

**Positive acceptance:** record Task identity before wait, after reconnect if used,
after typed response admission and at completion. Record MIRIX retrieval and
selected worker rationale, exact human request/response revision/digest, source
changes, command/location/toolchain, fresh tests, contract and verifier result.
The final surface explains the selected behavior, changes and verified result
without requiring runtime mechanics. No host checkout and no unrelated edits.

**Negative acceptance:** no auto-answer/default while waiting; stale, duplicate or
wrong-Task human reply cannot authorize work; rejected human choice causes no
unauthorized effect; model claiming success with broken tests remains incomplete;
client disconnect does not create another Task; external memory/text cannot widen
a grant; worker change cannot move effects to the host. Show that failing tests or
missing required evidence prevents completion, then retain the successful case.

**STOP:** only command-shaped D2 intake works, no genuine human cycle, memory/worker
path is bypassed without disclosure, identity changes, or completion lacks admitted
verification evidence. E3 is a synthetic E2E acceptance, not blanket readiness for
arbitrary company repositories or full D7 acceptance.

## Open Questions

Every item has a default and a decision gate. “Recommended” permits the next agent
to begin a bounded implementation; “Open” identifies a claim that still requires
a spike, live observation or scoped product decision. No further product approval
is implied for routine defaults already authorized by an implementation request.

| ID / question | Why it matters / current evidence | Recommended default | Reconsider when / decision gate |
| --- | --- | --- | --- |
| Q1 Client language / packaging — Recommended | Existing Blaine/ACP runtime is Python; shell launchers assume a repo and venv. Client needs JSON, subprocesses and clean stdio with few installation dependencies. | Go for the small local client; retain Python host runtime. Evaluate the comparison below during E0.A. | A packaged proof cannot deliver clean process control or protocol integration without excessive new code; decide E0.A before broader client work; preserve Linux/macOS/WSL2 boundaries. |
| Q2 Installation/distribution — Recommended | E0.C supporting delivery now proves Actions Artifacts and an alpha GitHub Release; native packaging/signing and full product acceptance remain open. | E0 design: Linux/WSL binaries or packages and native macOS binary/package; trusted release checksums, stable user-level launcher and rollback. Initial release may validate fewer targets; dev install for iteration. | Enterprise policy requires managed package/signing: add `.deb`; macOS managed packaging/Homebrew can follow initial standalone distribution, with OS trust/signing requirements validated for the selected artifact. Bootstrap convenience is optional, never `curl \| sh` as the core. E0.A then E0.F. |
| Q3 Host discovery — Recommended | Proven path uses an SSH alias. MagicDNS provides device names; no Blaine discovery API exists. | Provision stable MagicDNS FQDN in a connection profile, allow first `--host`, persist verified server identity. No tailnet enumeration/admin API. | Multiple hosts/failover becomes a real requirement or DNS unavailable; require explicit profile, not guessing. E0.C. |
| Q4 SSH mode — Recommended | Milestone 002 explicitly proved Tailscale SSH through `/usr/bin/ssh`; D2 says existing SSH authentication. Current installed transport has not been observed here. | Preserve Tailscale SSH first behind a narrow interface; record mode explicitly. Normal SSH over Tailscale may be a configured adapter, not an automatic fallback. | Live host uses ordinary sshd or managed policy disallows Tailscale SSH; separately verify user mapping, host-key trust, auth, reauth and cleanup. E0.C. Migration is not free. |
| Q5 Admission/registration — Selected | E0.C proves socket-derived tsnet identity and the Blaine handshake. Tailscale controls workstation admission; E0.D durable registry and primary live identity/presence acceptance passed. | Automatically register accepted peers for identity/inventory/presence. No second manual approval, IdP or SSH product transport. Preserve installation-key proof and Task/workspace authority boundaries. | A demonstrated threat not mitigated by Tailscale admission and the existing handshake warrants reviewing an additional boundary. Unverifiable peer identity remains STOP. E0.D. |
| Q6 Registration storage — Recommended | PostgreSQL owns structured durable brain data; Restate owns Task execution; D2 has no device registry. | Small PostgreSQL registry as specified above; no new service/database instance or MIRIX registry. | Existing adopted application already provides a suitable identity/config repository; preserve ownership and migration/uniqueness guarantees. E0.D. |
| Q7 Local config/secrets — Recommended | Host scripts use private local paths; no client config schema exists. | Versioned platform-native config/state (XDG Linux/WSL, Application Support macOS), restrictive permissions, native credential stores, no secrets in JSON. | A supported packaging mechanism changes location/credential needs. All platform paths defined in E0.A; live validation may be staged. |
| Q8 IntelliJ installation — Open | Current official docs specify `~/.jetbrains/acp.json`; old live WSL path conflicts with current support statement. | Platform-specific IDE discovery and owned-entry merge; preserve others, test running IDE and Windows-to-WSL launcher arrangement. Native Linux may be first live proof. | Actual installed versions/schema/reload or managed restrictions differ. E0.E/F must record a supported version pair. |
| Q9 Capability negotiation/provider — Open; **E1 provider selected** (IntelliJ MCP via IDE delegation, [ADR 0027](decisions/0027-ide-delegation-is-workspace-authority.md)); E2 write/terminal provider still open | ACP defines read/write/terminal; D2 implements only read fixture; JetBrains terminal support is unproven. | Negotiate every session and fail closed. Probe live read in E1, write/terminal in E2 before enabling. | Missing capability: choose a supported IDE version or separately review a small session-owned local provider; no silent MCP/host fallback. E1.A/B and E2.A. |
| Q10 Workspace identity/confinement — **E1: Recommended** (derived `workspace_id`; IDE project model is the read boundary; PolicyGate argument/project pinning — [contract](contracts/workspace-capability.md#confinement)); E2 write confinement still Open | D2 compares POSIX cwd and lexically validates paths; symlink protection is delegated to client. | Registration + workspace ID + canonical local root/platform, local grant, access-time containment; regular files with platform-aware paths. | IntelliJ provider cannot prove confinement or needs unsupported platform semantics. STOP E1; review local provider boundary. E1.A/B. |
| Q11 Write semantics — Open | ACP whole-file write has no base CAS parameter or atomicity guarantee. | Conditional whole-file UTF-8 replacement with expected hash/absent and atomic guarded commit; avoid a patch engine. | Installed provider cannot enforce concurrency/editor safety: E2.A must choose an extension or bounded provider and record it before E2.B. No best-effort downgrade. |
| Q12 Exec semantics — Open | ACP has terminal lifecycle; D2 has no exec, and env/descendant cleanup are unverified. | Exact reviewed profile + structured args/cwd, minimal env, deadline/output bounds, confirmed cleanup and receipt. | Terminal unavailable or insufficient control: decide whether a session-owned local provider is warranted; no daemon/arbitrary shell. E2.A/C. |
| Q13 Evidence/completion — Recommended; **specified** as [Completion Contract v1](contracts/completion-contract.md) | Existing verifier admits exact artifacts and typed human responses, not generic remote coding claims. | Extend existing contracts with matched remote receipts, change hashes, source-correlated build/test evidence and deterministic predicates. | Tool output lacks enough provenance or tests do not establish requested behavior. E1.C, E2.D, E3.A. |
| Q14 Reconnect/uncertain effects — Open | Same-Task waiting and read replay have D2 evidence; remote writes/exec do not. | Fresh routing, explicit human response, one-shot result admission; uncertain mutations require reconciliation, never blind replay. | Provider supports durable idempotency receipts or proven cancellation semantics. Freeze E1.A read behavior; E2.D mutation recovery. |
| Q15 Multiple workstations/surfaces — Recommended | Existing session cwd alone cannot distinguish identical paths on devices. | Stable registration/workspace IDs from E0; one active effect route per Task/workspace, no implicit migration. | Concurrent surface demand requires a richer routing policy. Identity required E0.D/E1.A; multi-device product UX deferred. |
| Q16 IntelliJ plugin — Accepted boundary; future UX open | Custom ACP agents need no Blaine plugin. | No plugin in E0–E3; possible later thin settings/connect UI calling the same client. | Measured user friction cannot be addressed by connect/config/diagnostics. No current milestone gate. |
| Q17 Version compatibility — Recommended | ACP negotiates its own version; no Blaine client handshake exists. | Client/server versions, explicit supported Blaine protocol range initially one value, feature flags, actionable incompatibility error. | Actual independently shipped releases need broader compatibility windows. Required E0.C; extend features explicitly in E1/E2. |
| Q18 Local authorization transport — **Revised**: capability-relay channel with operation correlation; no local authorization ([ADR 0027](decisions/0027-ide-delegation-is-workspace-authority.md)) | Standard ACP session/path calls lack Task ID/grant revision. Host-only policy is insufficient under host compromise. | Minimal private, versioned operation envelope bound to ACP call IDs, consumed by local guard and stripped before IDE; local scope is user-controlled. | SDK/transport cannot preserve correlation or local scope cannot be enforced; STOP E1.A, choose a documented compatible extension. No new public protocol replacement. |
| Q19 E3 normalization/fixture — Open | D2 currently accepts deterministic controls and narrow completion schemas; Java 25 workflow is not implemented. | Small deterministic CLI, local-first routing, genuine behavior question, existing human/runtime primitives, fresh build/test predicates. | Fixture cannot expose real human choice or installed Gradle/JDK combination is unsupported. E3.A before coding acceptance. |
| Q20 WSL2 network reuse — Open | Vendor warning excludes default nested daemons; host/guest routing is untested here. | Native Windows Tailscale; detect via Windows interop, probe actual WSL path; no forwarding changes initially. | Real WSL2 evidence shows DNS/routing/interop failure; record the smallest supported adjustment and explicit deployment mode. E0.B/C/F. |
| Q21 Cross-platform install/IDE launch — Open | macOS needs native approval; IDE and client may occupy different OS namespaces under WSL. | Three platform adapters, guided supported installs, explicit escalation, no permanent root; stable local launcher in the IDE namespace. | Supported installer/CLI discovery or JetBrains process arrangement differs on target machine. E0.A/B/E/F; no all-platform PASS without results. |

### Client language comparison

This is an engineering recommendation, not a language preference. The launcher is
primarily connection/config/process plumbing; it should not replicate Python's
Task runtime or require a full ACP agent implementation just to bridge stdio.

| Option | Fit and costs | Judgment |
| --- | --- | --- |
| Tiny Python application | Reuses team/runtime knowledge and official ACP SDK; JSON/subprocess tooling is available. Requires a supported interpreter and isolated installation, or a separately validated bundled runtime. [uv tool installation](https://docs.astral.sh/uv/guides/tools/) manages an isolated application environment but is another installed component. | Strong fallback if SDK reuse dominates. Do not require a checkout/venv operation from the end user. |
| Go | Standard JSON and process primitives; executable distribution avoids an end-user language environment. `os/exec` does not invoke a shell by default. [Go build](https://pkg.go.dev/cmd/go#hdr-Compile_packages_and_dependencies), [process API](https://pkg.go.dev/os/exec). Supports a native macOS executable and the Linux-side WSL binary with the same shared logic; adds a second implementation language and platform-specific process/installer release checks. | Recommended for a small dependency-light launcher; validate Linux artifact, signals, stdio and platform config/process roundtrip in E0.A. No automatic claim of static linking for every build. |
| Rust | Compiled executable with strong control over local enforcement; dependencies/build targets and development cost must be justified. `cargo install` builds/distributes through Cargo and is not an end-user standalone release by itself. [Cargo installation](https://doc.rust-lang.org/cargo/commands/cargo-install.html). | Viable if later enforcement demands or established maintainer experience justify it; no demonstrated E0 advantage over Go. |
| Existing shell / Java runtime | Shell is already used for host entrypoints but becomes difficult for safe structured config/state/error handling. A Java client would require a runtime/bundle before workstation onboarding; the E3 project's JDK is not an E0 prerequisite. | Keep shell as packaging glue, not core client. Do not choose Java solely because IntelliJ/E3 uses it. |

E0.A selected Go with a standalone build and stdio/process proof; see the
[language decision](../experiments/e0a-blaine-client/language.md). The remaining
platform runtime gates below still apply. The language gate calls for an executable
that can
roundtrip platform-native config and relay clean stdio/exit signals; explicitly
test macOS path discovery and Windows-to-WSL argument/encoding boundaries in
fixtures before claiming live support. It should not become a
multi-language benchmarking program or implement several competing clients.

## Security boundaries

These controls constrain implementation; they do not claim resistance to a fully
compromised trusted machine or provide a new enterprise security platform.

| Threat | Required control and residual boundary | Milestone |
| --- | --- | --- |
| Compromised workstation | Treat content/capability replies as untrusted inputs; validate schema, size and operation identity. Workstation cannot authorize host/global effects. Its own evidence can still be fabricated; no attestation claim. | E0 identity, E1 evidence, E2/E3 verification. |
| Compromised Blaine host | **Revised (ADR 0027):** no independent local policy. A compromised host can invoke any tool in the IDE-delegated surface, including mutating/executing ones, limited by IDE-side controls (exposed-tool settings; command confirmation unless brave mode) and by what the operator delegates. IDE tokens and workstation credentials never leave the workstation. Accepted residual of the delegated-authority model. | E0 no ambient grants; E1 delegation only via `use_idea_mcp`; E2 revisits for writes. |
| Device removed from tailnet | Tailscale owns strong network revocation; Blaine reflects observed state and invalidates affected routes. Measure propagation/session teardown; a registry flag cannot neutralize retained administrative SSH authority over the Hub. | E0.D state reflection; E0.F integrated negative probe; E1/E2 route invalidation. |
| Stale/retired inventory | Preserve durable identity/history; last-seen is informational. A fresh policy-authorized handshake can restore presence without manual Blaine approval. Reinstall or a changed binding cannot inherit old grants. | E0.D onward. |
| Path traversal / link races | E1 reads: IDE project model plus PolicyGate argument schema and project pinning; symlinked content the IDE treats as project content is an accepted residual. E2 writes: canonical workspace, operation-time containment, negative traversal/symlink/hard-link probes. | E1 reads, E2 writes. |
| Arbitrary command execution | Exact profile/args/env/cwd with reviewed build inputs, bounds and lifecycle; deny shell text. Trusted synthetic fixture initially; allowlist is not an OS sandbox. | E2/E3. |
| Client impersonation | Server derives authenticated principal/device; UUID/path/name cannot authenticate. Detect copied UUID on another device, mismatched server and stale route generation. | E0.C/D, E1. |
| ACP stdout injection/corruption | Separate diagnostics/control channel, no PTY/banners, strict framing/correlation, reject malformed traffic, serialize tool output as data. | E0.C/F; regress E1–E3. |
| Accidental capability widening | Effective authority = Task grant ∩ user constraints ∩ delegated scope ∩ Blaine operation classification (unknown ⇒ denied), enforced by PolicyGate and evidenced by the capability journal; session option changes never widen a running Task. | E0 no grants; E1–E3 per operation. |
| Malicious source/memory instructions | Repository/MIRIX text is context, never policy. Workers cannot rewrite grants or Completion Contracts to accept their own output. | E1 context; E3 cognition. |
| Configuration/supply-chain tampering | Trusted versioned distribution, verified digest provenance, restrictive local permissions, host verification, safe merge/rollback and no automatic arbitrary remote installer. | E0. |

Network trust depends on the selected transport. Tailscale SSH uses tailnet identity
and its SSH policy; normal SSH over Tailscale retains separate sshd/key policy.
Check-mode reauthentication is specific to Tailscale SSH. Validate the actual mode
before preserving or migrating it. [Tailscale SSH](https://tailscale.com/docs/features/tailscale-ssh).
The CLI provides machine-readable state and interactive login mechanisms; its
`tailscale ssh` helper validates host keys using Tailscale-distributed identity.
Using it in place of the recorded `/usr/bin/ssh` invocation still requires stdio
acceptance. [Tailscale CLI](https://tailscale.com/docs/reference/tailscale-cli).
MagicDNS supplies stable device names, not Blaine registration or authorization.
[MagicDNS](https://tailscale.com/docs/features/magicdns).

## Implementation decomposition

This is a delegation plan, not permission to execute it in this design slice.
Component paths below that do not yet exist are **proposed**, not links to delivered
code. Reuse `runtime/personal_acp.py`, `runtime/personal_agent.py`,
`runtime/personal_runtime.py`, `runtime/kernel/workspace.py` and the existing
PolicyGate/CompletionVerifier where appropriate. Keep future client code under
`client/`, compatibility/operation schemas under `docs/contracts/`, and bounded
acceptance artifacts under `experiments/personal-agent-hub/`. Each slice records
PASS/STOP with evidence and can commit independently; no slice claims a later live
gate merely because its mocks pass. No concurrent agent execution is required.

| Slice | Goal and likely components | Live acceptance / retained proof | STOP conditions | Dependencies |
| --- | --- | --- | --- | --- |
| E0.A Client skeleton/package — [foundation PASS](../experiments/e0a-blaine-client/README.md) | Settle Go recommendation; proposed `client/cmd/blaine`, `client/internal/platform` Linux/macOS/WSL adapters, versioned config model and portable artifact/install notes. Five-command surface with explicit unavailable stubs for later behavior. | Install executable in a clean Linux user environment; version works without repo/language runtime; config/path and stdio/signal fixtures cover all three platform boundaries; live portability explicitly scoped. | Packaging requires hidden runtime/repo, stdout corruption, unsafe config migration. | This design; no live host required. |
| E0.B Tailscale state/login | Proposed platform prerequisite adapters; supported install assistance, native status/login, macOS approvals, Windows host inspection from WSL. | On available targets, prove install/missing/expired/login states; macOS native approval and WSL2 host status/topology probes; no changed unrelated preferences. Record untested targets. | Needs admin token/permanent root, duplicate WSL daemon, wrong tailnet, unsupported install or cannot distinguish auth/host/guest reachability. | E0.A; authorized test workstation. |
| E0.C Host/transport/handshake — [PASS](../experiments/personal-agent-hub/e0c-direct/README.md) | Embedded tsnet, internal Hub profile, private application endpoint, signed handshake and bounded binary/ACP session. | Primary designated Mac: persistent peer identity across restart/reconnect, handshake, binary stream, cancellation/disconnect, narrow tailnet policy, persistent Hub service/readiness, Task independence and real Blaine IDE read-only round trip. Existing WSL transport evidence is additional; full second-workstation IDE acceptance belongs to E0.F. | Claimed peer identity, public endpoint, failed application pin/protocol accepted, unsafe state or hidden transport fallback. | E0.A; accepted E0.B history; authorized designated peers and private host deployment. E0.C and E0.D accepted; E0.E is next. |
| E0.D Workstation identity/inventory/presence — [PASS](../experiments/personal-agent-hub/e0d/README.md) | PostgreSQL registry, automatic registration after the accepted handshake, signed protocol-2 receipt, read-only host inventory CLI and expiring connection presence; primary Mac lifecycle, public alpha.4 upgrade and designated WSL distinct-identity acceptance passed. | First connection/concurrent retry/response loss produce one registration; restart/reconnect/upgrade reuse it; copied identifiers cannot take over another binding; presence and stale-session fencing preserve inventory and Tasks. Retirement/revocation records reflect product/network state; Tailscale owns strong admission/revocation. | Second manual Blaine approval without a demonstrated threat; new Task ledger; registration grants workspace scope; unknown outcome reported success; registry revocation claimed to resist host-admin authority. | E0.C; effective narrow Tailscale admission; existing PostgreSQL access scoped to registry. |
| E0.E IntelliJ config | Proposed client IDE config adapter and merge fixtures. | Actual IntelliJ with a second agent, closed/running merge/reload; correct OS user config and stable launcher; test supported Windows/WSL arrangement before that platform PASS. | Overwrites unrelated fields, managed installation blocks agents, version unsupported. | E0.A/C/D; supported IDE installation. |
| E0.F Doctor/connect acceptance | Integrate state flow, diagnostics, disconnect and release artifact; proposed E0 acceptance report. | New-workstation journey and E0 positive/negative matrix per implemented platform, twice-run connect, read-only doctor; full real IntelliJ acceptance on the designated second Windows/WSL workstation; mark other targets unverified. | False READY, any missing identity/config/stdio invariant; no live IntelliJ evidence. | E0.A–E; closes only explicitly validated platform scope of E0. |
| E1.0 Completion Contract kernel (no workstation) | [Completion Contract v1](contracts/completion-contract.md): contract artifact/revision in TaskState, v0 lowering, CompletionEvaluation v2, legality function, capability journal on the single dispatch path, `capability_journal`/`evidence_citation` verifiers, human-only amendment handler. | Kernel fixtures: v0 parity; cited-findings completion; fabricated quote fails; cognition cannot drop REQUIRED; human waiver visible; SIGKILL/replay stable refs; unadmitted journal entry fails. | Contract mutable by cognition; journal bypassable; evaluation not tied to revision/evidence. | None beyond current kernel; new Restate deployment. |
| E1.A Delegation observation | Allow `session/new` with the IntelliJ MCP entry in an observation mode; record redacted descriptor, `cwd`, IDE versions and `tools/list`; no tool calls. | Real IntelliJ with `use_idea_mcp` on: delegated surface recorded (including mutating tools); with it off: none. | IDE does not pass its MCP server to a custom ACP agent; no read/search tools in the surface. | E0.C client; E0.D registration ID preferred (installation ID allowed for this spike, labelled). |
| E1.B Capability relay | Direct-protocol `capability-relay/1` feature and frame kind 5; Go bridge to the observed MCP transport; Hub MCP client in `PersonalACP`; counting fake MCP server fixture. | Fixture: relayed `tools/list`/`tools/call` round trip with operation correlation; bridge never originates or filters calls; ACP stream unaffected. | Capability bytes on IntelliJ stdio; token leaves workstation; uncorrelated calls. | E1.A. |
| E1.C Read-only authority and dispatch | `workspace.read` provider form, `intellij-mcp@1` classification, argument schemas, `EffectiveAuthority`, `access` configOption, `DelegationSnapshot`, receipts, `continue` delivery. | Fixture: READ_ONLY Task with mutating tools delegated → denials journaled, zero fake-IDE mutating calls; wrong workspace/registration/generation rejected. | Local tool filtering substituted for PolicyGate; unclassified tool admitted. | E1.0, E1.B. |
| E1.D Investigation templates | `investigation@1`, `explanation@1`, `location@1` templates, findings schemas, bounded `investigate/explain/locate` intake; optional advisory `semantic_review` (local model). | Fixture Tasks for all three examples complete only with valid citations; unresolved conclusion completes honestly. | Completion from model sentiment; REQUIRED semantic without human path. | E1.C. |
| E1.E Live E1 acceptance | Run the [E1 acceptance matrix](contracts/workspace-capability.md#e1-acceptance) on a real second workstation. | Positive/negative matrix, disconnect/continue same Task, restart during pending op, human WAITING unaffected. | Any STOP in the matrix. | E1.A–D; E0 PASS for the platform used; closes E1. |
| E2.A Provider contract spike | Observe live write/terminal support; specify CAS/editor behavior, environment, timeout and descendant cleanup. Proposed contract and probe report first. | Demonstrate guarded conditional write and process controls on disposable fixture, or explicit STOP with smallest provider decision. | Base ACP cannot deliver required safety, proposed workaround is daemon/unrestricted shell or hidden provider switch. | E1 PASS; scoped temporary effect authorization; resolves Q11/Q12. |
| E2.B Conditional write adapter | Extend workspace/PolicyGate dispatch, local guard/provider and receipt store. | One bounded write with before/after/diff evidence; stale, dirty-buffer, link/race and response-loss controls. | Lost update, unauthorized mutation, blind replay or false atomicity claim. | E2.A proven write mechanism. |
| E2.C Bounded exec adapter | Add command profile/provider, terminal lifecycle and output/report normalization. | Allowed local build/test with actual exit/output, deadline and descendant cleanup; env/argument denial. | Unrestricted shell, inherited secrets, uncontrolled process, exec on host or missing evidence. | E2.A proven terminal mechanism; reviewed fixture. |
| E2.D Effects/verification/recovery | Extend existing completion predicates and remote operation reconciliation. | Successful edit/test verified; failing test/stale evidence denied; disconnect before/after effects causes no blind redispatch. | Worker text accepted as completion, uncertain effect hidden, incorrect replay or cancellation claim. | E2.B/C; closes E2. |
| E3.A Natural-language Task/fixture | Extend Personal Agent normalization and bounded completion templates; proposed Java 25 Gradle fixture and pinned toolchain notes. | Real IntelliJ request forms correct Task/grants/criteria; MIRIX retrieval and selected worker recorded; genuine choice becomes typed human request. | Only D2 command grammar works, unsupported JDK/Gradle, scope/cloud grants inferred from model output. | E2 PASS; available memory/local inference/worker. |
| E3.B Human response/resume | Bind existing HumanDecision to user surface with matching revision/digest and durable identity. | Real human answers actual unresolved choice; disconnect/new surface retrieves wait and resumes same Task; stale/wrong replies denied. | Auto-response, cosmetic decision, replacement Task or widened authorization. | E3.A. |
| E3.C Coding E2E/result | Run full fixture workflow through effects, deterministic verification and user result projection. | Java 25 build/tests, allowed diff, human evidence, fresh CompletionEvaluation and terminal Task/result; negative verifier case retained. | No workstation provenance, missing genuine human cycle/evidence, host checkout, unintended writes. | E3.B and E2 effects; closes E3, not D7. |

**Original first implementation request (now completed within E0.A scope):**
E0.A only. Create the small packaged
client skeleton, platform interface and config contract for Linux/macOS/WSL2;
prove initial native Linux installation/version and clean stdio behavior, exercise
the other platform boundaries in fixtures, and record the language decision and
unverified live platforms. Do not onboard
a real workstation, mutate host services or implement workspace effects in E0.A.
Subsequent host/workstation effects need their own scoped implementation request.

## Non-goals

No implementation in this slice. No IntelliJ plugin requirement, custom GUI,
public Blaine endpoint, custom remote filesystem daemon, workspace synchronization
system, NFS/rsync dependency, host project checkout, multi-user SaaS identity,
replacement for Tailscale or ACP, arbitrary remote shell by default, or new cloud
control plane. No general CLI framework, universal capability catalog, worker
framework rewrite, broad company-repository acceptance, infrastructure migration,
backup continuation, telemetry completion or paid-model benchmark program.

## Design-slice verification

Review this document and ADR as specifications, not deployment evidence. Validate
local Markdown links/anchors, the draft JSON and `git diff --check`; inspect the
diff for implementation changes. One coherent local commit is required, without
push or merge. Live IntelliJ/Tailscale/provider gates remain future implementation
acceptance. The absence of their live evidence does not prevent accepting this
documentation slice; it does prevent claiming E0–E3 product PASS.

Recorded local documentation checks (2026-09-21): `git diff --check` passed;
271 local Markdown links and 19 heading/explicit anchors in changed documents
resolved; the TaskSpec draft and four fenced JSON examples parsed; Hub table
column counts and code fences passed. Changed-file inspection found only README
and documentation changes. No repository Markdown/link checker was present, so
these checks used a temporary local Python validator, not new product/test code.
No client, ACP effect, workstation onboarding or coding workflow was implemented;
no live IntelliJ, Tailscale, platform or runtime acceptance was performed.
