# Personal Agent Hub — E0 through E3

**Design checkpoint: 2026-09-21. Status: architecture and implementation handoff;
E0–E3 are planned, not implemented or accepted.**

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
| A13 | Tailscale is an external prerequisite. Blaine detects it, assists supported installation, invokes/guides native login and diagnoses connectivity; it does not wrap or replace its networking/authentication, persist login credentials or create an identity substitute. |
| A14 | E0 architecture targets Linux, native macOS and Windows development environments using WSL2. One platform boundary owns OS differences; implementation evidence may initially cover fewer platforms. |
| A15 | Prefer native macOS Tailscale and native Windows Tailscale for WSL2. No second WSL daemon by default; OS/admin/browser prompts are acceptable and explicit, while Blaine itself stays unprivileged. |

### Recommended

Defaults to use when beginning a slice, with reconsideration criteria in
[Open Questions](#open-questions): portable Go client; user-scoped binary/package;
stable MagicDNS host profile; retain the proven Tailscale SSH path behind a small
transport interface; PostgreSQL workstation registry; platform-native non-secret
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

The local guard is a proposed responsibility inside the launcher/adapter, not a
new filesystem daemon or replacement ACP protocol. E0 can bridge standard ACP;
E1 must add enough Task/workspace-bound validation to safely forward reads.
Standard ACP messages do not themselves carry Blaine Task authority. Before E1,
a minimal versioned private control message must bind an authorized operation to
the corresponding ACP request ID/session; it must not alter standard ACP meaning
or leak onto IntelliJ's stream. Exact encoding is an E1.A gate. Neither byte
forwarding nor a host-only PolicyGate protects a workstation from a compromised
host. Local user-approved scope must independently bound forwarded effects.

### Distinct identities

| Identity | Recommended representation and source |
| --- | --- |
| Personal Agent / host | Stable server ID returned over verified transport, pinned to the configured host profile. DNS alone is not identity. |
| Network principal | Tailscale device/user and SSH target user derived from trusted transport observations. Do not accept a claimed peer ID from request JSON. |
| Client installation | Locally generated random client UUID; descriptive, not a credential. Reinstall with lost identity creates a new registration unless explicitly repaired. |
| Workstation registration | Server-issued ID tied to authenticated peer/device, client UUID, owner and status. Display name is not a key. |
| Workspace | Registration ID + opaque workspace ID + locally canonical absolute root and path-platform tag. Two machines with `/home/user/project` are distinct. |
| Surface/session | Ephemeral ACP session/connection ID and generation bound to registration/workspace. Recreated on reconnect. |
| Task / operation | Existing durable Task ID and stable capability operation ID; neither derived from ACP session ID. |

Network login establishes tailnet membership/transport identity under tailnet and
SSH policies. Registration associates a particular installation with Blaine and
records compatibility/capabilities. Authorization is a separate Task-specific
policy decision intersected with local workspace consent. Registration is not
an OAuth provider, shared workstation secret, or blanket project grant.

Recommended host registry: a small Blaine-owned PostgreSQL table with registration
ID, client UUID, authenticated principal/device binding, display metadata,
first/last seen, status/revocation revision, client/protocol versions and last
observed capabilities. Uniqueness is scoped by owner and authenticated device plus
installation, so replayed registration returns the same row. Last seen is only an
observation, not a liveness promise. Active ACP routes are ephemeral; current
capabilities are negotiated on each connection. Restate stores the Task's selected
registration/workspace, grants, operation receipts and waits. PostgreSQL must not
become a second Task ledger. This follows [ADR 0018 storage ownership](decisions/0018-local-platform-durability-and-observability.md),
while preserving its documented implementation/validation status. MIRIX, Redis,
telemetry and the local config are not registry authorities.

Recommended Linux and WSL-distribution paths: `$XDG_CONFIG_HOME/blaine/config.json` (default
`~/.config/blaine/config.json`) for schema version, connection profile, host/server
identity, client/registration IDs and transport selection;
`$XDG_STATE_HOME/blaine/` (default `~/.local/state/blaine/`) for owned-config receipts,
backups and redacted diagnostics. Persist permissions restrictively; atomically
replace owned files and detect concurrent changes. Store no private keys, login
URLs, tokens, raw conversations or workspace contents in connection config.
Tailscale and SSH retain their native credential stores; a future pairing secret,
if proven necessary, uses an OS credential store. On macOS use
`~/Library/Application Support/Blaine/config.json` and a
separate `state/` beneath that application directory; bounded logs may use
`~/Library/Logs/Blaine/`. On WSL keep the client config/state in the selected distro,
not a guessed Windows home. Detect Windows user/profile and IDE config ownership
separately through supported interop. Persist the selected distro/IDE execution
location so another default distro cannot redirect launches. No repository path is required on the workstation.

### Handshake and compatibility

Use a separate bounded control invocation over the same authenticated transport
for handshake/readiness/registration; these are proposed operations, not existing
CLI commands. They must not prepend JSON to ACP stdio. Install one stable host
entrypoint rather than encode worktree script paths in the IDE. The current
`scripts/run-personal-agent.sh` is implementation evidence, not the future public
host installation path.

Handshake request: client version, supported Blaine protocol range (initially one
integer), expected server ID if paired, client UUID and optional registration ID.
Response: server ID/version, supported range, selected protocol, authenticated
peer binding, registration status, feature flags and bounded readiness results.
ACP version negotiation remains separate. Require a nonempty protocol intersection
and required feature flags; otherwise refuse launch with an actionable upgrade
message including installed and supported versions. Never downgrade security or
silently continue with incompatible semantics. Recheck registration/revocation
when launching and before admitting effects. Unknown peer binding fails closed.

The host boundary must establish source identity through a trusted transport
mechanism (for example the SSH source connection mapped by local Tailscale peer
lookup) and verify the intended SSH user. Whether the installed Tailscale SSH
launcher exposes sufficient trusted data is an E0.C live gate. A caller-supplied
environment variable alone is insufficient. Do not add a second identity system
or shared bearer credential to bypass a failed gate.

## Platform boundary and prerequisite installation

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
WSL2 workstation in E0.B/C/F. No WSL/Windows live investigation occurred here.

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

Command behavior in this section is proposed for implementation. No command is
claimed available today. Optional flags remain small: `connect --host NAME` for
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
| 1. Inspect | Select platform adapter; validate client/config, executable location, native Tailscale owner/CLI, SSH and IntelliJ presence. | Missing dependency: offer supported installation in the same flow with visible action/explicit OS privilege prompt, then re-detect; declined action remains resumable. Unsupported platform/config: STOP without overwriting. |
| 2. Authenticate | Read the platform-owned Tailscale state (Windows host for WSL2). Reuse authenticated identity; guide native interactive login only when required. | Browser/device flow; no raw credentials, admin API key or auth-key provisioning. User completes login, then client rereads state. Do not reset existing tailnet preferences. |
| 3. Resolve | Load persisted host, otherwise provisioned profile/explicit host. Resolve and test the selected host. | Offline/DNS/access failure: `REMOTE_UNAVAILABLE`, preserve previous configuration. No host guessing/fallback to public routes. |
| 4. Secure transport | Verify intended peer and SSH host identity, negotiate noninteractive stdio transport. | Host identity change: STOP for explicit trusted re-pairing; never disable host-key checks. Check-mode reauthentication is completed in the terminal/browser, never inside ACP stdout. |
| 5. Handshake | Check server identity, protocol compatibility and runtime readiness. | `INCOMPATIBLE` or `REMOTE_UNAVAILABLE`; registration is not proof of runtime readiness. No service restart or deployment mutation. |
| 6. Register | Idempotent registration bound to authenticated device/client UUID. Persist receipt after authoritative success. | Lost response: look up/retry same identity; no duplicate registration. Revoked identity requires explicit re-pairing, not automatic resurrection. |
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

This is the stable launcher and transport adapter. Read the persisted profile,
validate basic identity/registration/compatibility with bounded timeouts, then
establish remote PersonalACP stdio. No onboarding, interactive login, repair or
automatic update in this command. If action is needed, return a concise stderr
message directing the human to `connect`/`doctor` and exit nonzero.

No PTY. Keep stdin/stdout exclusively ACP JSON-RPC with correct framing,
backpressure, request correlation and bidirectional client capability calls.
Do not send banners, readiness JSON, shell output, debug prints or worker output
into the protocol. Operational diagnostics go to stderr and optional bounded,
redacted local logs. SSH diagnostics stay on stderr; command output becomes typed
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
an unchanged client-owned ACP entry, and marks/revokes this registration remotely
when reachable. If remote revocation cannot be confirmed, report local disconnect
and revocation pending; do not claim global revocation. Future connect must
reconcile explicitly. Preserve Task IDs/results and local workspace files; never
cancel Tasks, log out all of Tailscale, delete credentials or affect other agents.
Revocation and local blocking must be idempotent. `version` is an offline read of
client/build/protocol versions with no network or filesystem mutation.

## Capability and workspace contracts

### Negotiation matrix

Protocol support, IDE support and Blaine support are separate evidence columns.
Current upstream documentation was checked on 2026-09-21.

| Capability | ACP protocol | JetBrains evidence | Current Blaine | Gate |
| --- | --- | --- | --- | --- |
| Read | `fs.readTextFile` advertises `fs/read_text_file`. | Target IntelliJ must advertise and successfully execute it. | D2 checks advertisement and reads through the official SDK fixture. | E1 live read, identity and confinement. |
| Write | `fs.writeTextFile` advertises `fs/write_text_file`, supplying path/content. | Installed behavior and editor/disk consistency unverified. | No D2 write adapter. | E2 conditional write and negative tests. |
| Exec | `terminal` advertises create/output/wait/kill/release methods. | No target live proof; do not infer from the IDE having a Terminal tool window. | No D2 terminal adapter. | E2 capability and lifecycle probe before execution. |
| Other | ACP supports session/control/UI mechanisms; not a universal file listing, diff, stat or CAS API. | Verify each needed method/extension explicitly. | D2 supplies bounded controls, not generic IDE navigation. | Add only a demonstrated need. |

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
shell workaround. Initial E1 can use an explicitly selected file; do not require
a generic project search service to prove a read.

### Workspace identity and path confinement

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
registration/workspace identity, operation kind, exact request digest and limits.
The local guard matches this authorization to the ACP request/session and its
locally approved scope. Session generation prevents stale routing. Evidence
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

Completion Contracts declare criteria before execution. E1 may retain D2's known
fixture digest. E2 adds deterministic contract predicates for the exact allowed
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
| Revoked/stale registration | Deny new effects; invalidate route. Last-seen age alone does not authorize or revoke. Fresh authentication/registration check is required. |
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

**Positive acceptance:** create a disposable project only on a second workstation;
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
| Q2 Installation/distribution — Recommended | No workstation release pipeline or client exists. Repo launchers are development mechanisms. | E0 design: Linux/WSL binaries or packages and native macOS binary/package; trusted release checksums, stable user-level launcher and rollback. Initial release may validate fewer targets; dev install for iteration. | Enterprise policy requires managed package/signing: add `.deb`; macOS managed packaging/Homebrew can follow initial standalone distribution, with OS trust/signing requirements validated for the selected artifact. Bootstrap convenience is optional, never `curl \| sh` as the core. E0.A then E0.F. |
| Q3 Host discovery — Recommended | Proven path uses an SSH alias. MagicDNS provides device names; no Blaine discovery API exists. | Provision stable MagicDNS FQDN in a connection profile, allow first `--host`, persist verified server identity. No tailnet enumeration/admin API. | Multiple hosts/failover becomes a real requirement or DNS unavailable; require explicit profile, not guessing. E0.C. |
| Q4 SSH mode — Recommended | Milestone 002 explicitly proved Tailscale SSH through `/usr/bin/ssh`; D2 says existing SSH authentication. Current installed transport has not been observed here. | Preserve Tailscale SSH first behind a narrow interface; record mode explicitly. Normal SSH over Tailscale may be a configured adapter, not an automatic fallback. | Live host uses ordinary sshd or managed policy disallows Tailscale SSH; separately verify user mapping, host-key trust, auth, reauth and cleanup. E0.C. Migration is not free. |
| Q5 Authentication/pairing — Open | Tailnet membership and SSH access do not grant workspace authority; no workstation pairing implementation exists. | Bind registration to transport-derived peer/device plus intended user; client UUID is only metadata. Reuse Tailscale/SSH identity, no second IdP. | Installed host cannot derive trusted source identity: STOP and choose the smallest verifiable pairing mechanism. E0.C/D before READY. |
| Q6 Registration storage — Recommended | PostgreSQL owns structured durable brain data; Restate owns Task execution; D2 has no device registry. | Small PostgreSQL registry as specified above; no new service/database instance or MIRIX registry. | Existing adopted application already provides a suitable identity/config repository; preserve ownership and migration/uniqueness guarantees. E0.D. |
| Q7 Local config/secrets — Recommended | Host scripts use private local paths; no client config schema exists. | Versioned platform-native config/state (XDG Linux/WSL, Application Support macOS), restrictive permissions, native credential stores, no secrets in JSON. | A supported packaging mechanism changes location/credential needs. All platform paths defined in E0.A; live validation may be staged. |
| Q8 IntelliJ installation — Open | Current official docs specify `~/.jetbrains/acp.json`; old live WSL path conflicts with current support statement. | Platform-specific IDE discovery and owned-entry merge; preserve others, test running IDE and Windows-to-WSL launcher arrangement. Native Linux may be first live proof. | Actual installed versions/schema/reload or managed restrictions differ. E0.E/F must record a supported version pair. |
| Q9 Capability negotiation/provider — Open | ACP defines read/write/terminal; D2 implements only read fixture; JetBrains terminal support is unproven. | Negotiate every session and fail closed. Probe live read in E1, write/terminal in E2 before enabling. | Missing capability: choose a supported IDE version or separately review a small session-owned local provider; no silent MCP/host fallback. E1.A/B and E2.A. |
| Q10 Workspace identity/confinement — Open | D2 compares POSIX cwd and lexically validates paths; symlink protection is delegated to client. | Registration + workspace ID + canonical local root/platform, local grant, access-time containment; regular files with platform-aware paths. | IntelliJ provider cannot prove confinement or needs unsupported platform semantics. STOP E1; review local provider boundary. E1.A/B. |
| Q11 Write semantics — Open | ACP whole-file write has no base CAS parameter or atomicity guarantee. | Conditional whole-file UTF-8 replacement with expected hash/absent and atomic guarded commit; avoid a patch engine. | Installed provider cannot enforce concurrency/editor safety: E2.A must choose an extension or bounded provider and record it before E2.B. No best-effort downgrade. |
| Q12 Exec semantics — Open | ACP has terminal lifecycle; D2 has no exec, and env/descendant cleanup are unverified. | Exact reviewed profile + structured args/cwd, minimal env, deadline/output bounds, confirmed cleanup and receipt. | Terminal unavailable or insufficient control: decide whether a session-owned local provider is warranted; no daemon/arbitrary shell. E2.A/C. |
| Q13 Evidence/completion — Recommended | Existing verifier admits exact artifacts and typed human responses, not generic remote coding claims. | Extend existing contracts with matched remote receipts, change hashes, source-correlated build/test evidence and deterministic predicates. | Tool output lacks enough provenance or tests do not establish requested behavior. E1.C, E2.D, E3.A. |
| Q14 Reconnect/uncertain effects — Open | Same-Task waiting and read replay have D2 evidence; remote writes/exec do not. | Fresh routing, explicit human response, one-shot result admission; uncertain mutations require reconciliation, never blind replay. | Provider supports durable idempotency receipts or proven cancellation semantics. Freeze E1.A read behavior; E2.D mutation recovery. |
| Q15 Multiple workstations/surfaces — Recommended | Existing session cwd alone cannot distinguish identical paths on devices. | Stable registration/workspace IDs from E0; one active effect route per Task/workspace, no implicit migration. | Concurrent surface demand requires a richer routing policy. Identity required E0.D/E1.A; multi-device product UX deferred. |
| Q16 IntelliJ plugin — Accepted boundary; future UX open | Custom ACP agents need no Blaine plugin. | No plugin in E0–E3; possible later thin settings/connect UI calling the same client. | Measured user friction cannot be addressed by connect/config/diagnostics. No current milestone gate. |
| Q17 Version compatibility — Recommended | ACP negotiates its own version; no Blaine client handshake exists. | Client/server versions, explicit supported Blaine protocol range initially one value, feature flags, actionable incompatibility error. | Actual independently shipped releases need broader compatibility windows. Required E0.C; extend features explicitly in E1/E2. |
| Q18 Local authorization transport — Open | Standard ACP session/path calls lack Task ID/grant revision. Host-only policy is insufficient under host compromise. | Minimal private, versioned operation envelope bound to ACP call IDs, consumed by local guard and stripped before IDE; local scope is user-controlled. | SDK/transport cannot preserve correlation or local scope cannot be enforced; STOP E1.A, choose a documented compatible extension. No new public protocol replacement. |
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

E0.A should settle language by producing a small packaged executable that can
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
| Compromised Blaine host | Independent local workspace consent and guard; deny unsolicited/out-of-scope filesystem/exec calls even over authenticated transport. Never forward workstation credentials. A host can still misuse already granted scope; keep it narrow/revocable. | E0 no ambient grants; E1 guard; E2 effect enforcement. |
| Device removed from tailnet | New connections fail network policy; invalidate known revoked routes and check registration before effects. Existing session teardown/revocation latency must be measured, not assumed instantaneous. | E0 revocation probe; E1/E2 route invalidation. |
| Stale registration | Last-seen is informational; fresh authenticated binding and active status required. Revoke explicitly; no automatic resurrection or grant inheritance on reinstall. | E0.D onward. |
| Path traversal / link races | Canonical local workspace plus operation-time containment, narrow file set, negative traversal/symlink/hard-link probes; cwd string is not a sandbox. | E1 reads, E2 writes. |
| Arbitrary command execution | Exact profile/args/env/cwd with reviewed build inputs, bounds and lifecycle; deny shell text. Trusted synthetic fixture initially; allowlist is not an OS sandbox. | E2/E3. |
| Client impersonation | Server derives authenticated principal/device; UUID/path/name cannot authenticate. Detect copied UUID on another device, mismatched server and stale route generation. | E0.C/D, E1. |
| ACP stdout injection/corruption | Separate diagnostics/control channel, no PTY/banners, strict framing/correlation, reject malformed traffic, serialize tool output as data. | E0.C/F; regress E1–E3. |
| Accidental capability widening | Intersect negotiated support, local consent and Task/PolicyGate grants; absent capability denies; MCP forwarding cannot grant authority; workspace/worker change invalidates assumptions. | E0 no grants; E1–E3 per operation. |
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
| E0.A Client skeleton/package | Settle Go recommendation; proposed `client/cmd/blaine`, `client/internal/platform` Linux/macOS/WSL adapters, versioned config model and portable artifact/install notes. Five-command surface with explicit unavailable stubs for later behavior. | Install executable in a clean Linux user environment; version works without repo/language runtime; config/path and stdio/signal fixtures cover all three platform boundaries; live portability explicitly scoped. | Packaging requires hidden runtime/repo, stdout corruption, unsafe config migration. | This design; no live host required. |
| E0.B Tailscale state/login | Proposed platform prerequisite adapters; supported install assistance, native status/login, macOS approvals, Windows host inspection from WSL. | On available targets, prove install/missing/expired/login states; macOS native approval and WSL2 host status/topology probes; no changed unrelated preferences. Record untested targets. | Needs admin token/permanent root, duplicate WSL daemon, wrong tailnet, unsupported install or cannot distinguish auth/host/guest reachability. | E0.A; authorized test workstation. |
| E0.C Host/transport/handshake | Proposed transport adapter and installed host connection entrypoint; versioned handshake/readiness schema. | Verify actual SSH mode/host/peer identity and clean stdio; mismatch/offline/check-mode tests; measure WSL path and any real forwarding need separately. | Untrusted claimed device identity, public endpoint, incompatible protocol accepted, unsafe SSH fallback. | E0.A/B; host profile and bounded host-entrypoint deployment authorization. |
| E0.D Registration | Proposed PostgreSQL migration/repository and client registration receipt. | Register/replay after response loss and restart: one identity; copied UUID on another device denied; revoke/re-pair explicit. | New Task ledger, registration grants workspace scope, unknown outcome reported success. | E0.C; existing PostgreSQL access scoped to registry. |
| E0.E IntelliJ config | Proposed client IDE config adapter and merge fixtures. | Actual IntelliJ with a second agent, closed/running merge/reload; correct OS user config and stable launcher; test supported Windows/WSL arrangement before that platform PASS. | Overwrites unrelated fields, managed installation blocks agents, version unsupported. | E0.A/C/D; supported IDE installation. |
| E0.F Doctor/connect acceptance | Integrate state flow, diagnostics, disconnect and release artifact; proposed E0 acceptance report. | New-workstation journey and E0 positive/negative matrix per implemented platform, twice-run connect, read-only doctor; mark other targets unverified. | False READY, any missing identity/config/stdio invariant; no live IntelliJ evidence. | E0.A–E; closes only explicitly validated platform scope of E0. |
| E1.A Workspace/operation boundary | Extend workspace contracts, route binding and proposed local guard/private envelope. | Real IntelliJ initialization captures versions/cwd/support; bind canonical workspace and authorization to one read request; wrong-device/session denied. | Task authority cannot be matched locally, no live read capability, ambiguous workspace. | E0 PASS; Q9/Q10/Q18 decisions. |
| E1.B Live confined read | Extend PersonalACP read path and local provider checks without host filesystem access. | Actual second-workstation ACP read; traversal/link/race negatives; no host checkout/sentinel access. | Containment relies only on preflight lexical/realpath checks or local fallback replaces required IDE proof. | E1.A. |
| E1.C Same-Task evidence/reconnect | Extend read receipts/admission and acceptance fixtures. | Disconnect at pending read, rebind, return verified evidence to same Task; human WAITING unaffected; stale/wrong replies denied. | Session becomes Task identity, evidence substitution or implicit response/restart. | E1.B; closes E1. |
| E2.A Provider contract spike | Observe live write/terminal support; specify CAS/editor behavior, environment, timeout and descendant cleanup. Proposed contract and probe report first. | Demonstrate guarded conditional write and process controls on disposable fixture, or explicit STOP with smallest provider decision. | Base ACP cannot deliver required safety, proposed workaround is daemon/unrestricted shell or hidden provider switch. | E1 PASS; scoped temporary effect authorization; resolves Q11/Q12. |
| E2.B Conditional write adapter | Extend workspace/PolicyGate dispatch, local guard/provider and receipt store. | One bounded write with before/after/diff evidence; stale, dirty-buffer, link/race and response-loss controls. | Lost update, unauthorized mutation, blind replay or false atomicity claim. | E2.A proven write mechanism. |
| E2.C Bounded exec adapter | Add command profile/provider, terminal lifecycle and output/report normalization. | Allowed local build/test with actual exit/output, deadline and descendant cleanup; env/argument denial. | Unrestricted shell, inherited secrets, uncontrolled process, exec on host or missing evidence. | E2.A proven terminal mechanism; reviewed fixture. |
| E2.D Effects/verification/recovery | Extend existing completion predicates and remote operation reconciliation. | Successful edit/test verified; failing test/stale evidence denied; disconnect before/after effects causes no blind redispatch. | Worker text accepted as completion, uncertain effect hidden, incorrect replay or cancellation claim. | E2.B/C; closes E2. |
| E3.A Natural-language Task/fixture | Extend Personal Agent normalization and bounded completion templates; proposed Java 25 Gradle fixture and pinned toolchain notes. | Real IntelliJ request forms correct Task/grants/criteria; MIRIX retrieval and selected worker recorded; genuine choice becomes typed human request. | Only D2 command grammar works, unsupported JDK/Gradle, scope/cloud grants inferred from model output. | E2 PASS; available memory/local inference/worker. |
| E3.B Human response/resume | Bind existing HumanDecision to user surface with matching revision/digest and durable identity. | Real human answers actual unresolved choice; disconnect/new surface retrieves wait and resumes same Task; stale/wrong replies denied. | Auto-response, cosmetic decision, replacement Task or widened authorization. | E3.A. |
| E3.C Coding E2E/result | Run full fixture workflow through effects, deterministic verification and user result projection. | Java 25 build/tests, allowed diff, human evidence, fresh CompletionEvaluation and terminal Task/result; negative verifier case retained. | No workstation provenance, missing genuine human cycle/evidence, host checkout, unintended writes. | E3.B and E2 effects; closes E3, not D7. |

**Proposed first implementation request:** E0.A only. Create the small packaged
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
