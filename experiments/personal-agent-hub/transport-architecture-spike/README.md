# ACP provisioning/authentication and private transport architecture spike

**REVIEW READY — PARTIAL live evidence; STOP for operator architecture decision.**
Research date: 2026-09-23. E0.C remains PARTIAL; its SSH-adapter implementation
work is paused at the operator's request. No new client release, public registry
submission, production adapter change, E0.D registration or E1/E2 capability was
implemented. ADR 0022 and the canonical roadmap remain authoritative.

[request.json](request.json) is an **unsubmitted** TaskSpec: no development Task
creation binding was available. No runtime Task state is inferred from this file.
The unaccepted `--ssh-user` source/documentation edits were removed; the committed
SSH implementation and accepted E0.A/B evidence are preserved.

The operator prefers a client without a separately installed workstation
Tailscale CLI/daemon if live evidence supports it. A stable, independently
revocable node per Blaine installation is a potential benefit, not a defect.
Costs to measure are credential protection, authorization, simultaneous IDE
processes, upgrades, revocation and stale-installation cleanup.

The operator requested consolidation instead of further incremental artifact
downloads. This report closes the decision-support pass with explicit unmeasured
properties. No additional workstation command is required to choose a direction.
Revision 4 is prepared and locally tested but is **not** claimed live-tested.
See [the consolidated follow-up acceptance plan](acceptance-plan.md) for one
coordinated batch after the architecture decision, not more one-off downloads.

## Evidence boundaries

| Experiment | Current evidence | Unresolved |
| --- | --- | --- |
| A: IDE provisioning | Official JetBrains installation/update contract; four-target binary entry validated against pinned registry schema; alpha-version and binary-preview rejection reproduced in [registry-validation.json](registry-validation.json). | Actual JetBrains download/cache/launch of this private fixture has not run. Ordinary custom `acp.json` names an already installed command; it does not prove IDE provisioning. No documented private-registry override was established. |
| B: ACP auth | Local Go fixture and race test: auth-required, browser callback with state validation, successful response/session, marker reuse across agent restarts, logout and timeout. | Real IDE button/browser/display behavior, installed plugin version, and reauthentication UI. Mock marker authenticates nobody; no OAuth token/provider exists. |
| C: macOS tsnet | arm64 private stream PASS reported; host corroborated stable node. Complete diagnostic reports verify reuse across binary revisions and clean close. Same-process Hub visibility arrived around 3 seconds after Running in some runs. With the system GUI quit and a live listener, three post-observation name/IP TCP comparisons verified the Hub successfully. See [macos-live-evidence.md](macos-live-evidence.md). darwin/amd64 remains build-only. | Bounded readiness behavior without a fixed diagnostic delay, original stream JSON, browser-flow details, reboot, published-client upgrade, revocation and complete absence of residual system components. |
| D: WSL2 tsnet | ST00251 Ubuntu WSL2 ran linux/amd64: first browser enrollment, three name/IP TCP plus Hub identity successes, same node ID and clean close; one delayed Hub appearance at about 2 seconds. Diagnostic baseline flag defect is documented in [wsl-live-evidence.md](wsl-live-evidence.md). No Linux daemon/CLI or Windows CLI data path. linux/arm64 build-only. | Live binary stream, corrected baseline reporting, reboot/upgrade/revocation, on-device state protection and precise Windows background-service independence. Browser opening uses Windows interop separately. |
| E: stream primitive | Real loopback HTTP/WebSocket fixture: server-initiated binary message, 1 MiB byte-equal roundtrip, read deadline, explicit cancellation, server-observed disconnect, subsequent fresh connection; race test PASS. First Mac private cross-machine run reported PASS and host traffic corroborated. | Full Mac report capture, WSL repetition, slow-reader backpressure/load limits and production identity enforcement. |

A sandboxed test first failed because loopback sockets were denied. It passed
when rerun with permission for local sockets. This is an execution-environment
restriction, not a transport failure. No tailnet node is enrolled by unit tests.

## 1. JetBrains provisioning and distribution

The [JetBrains ACP guide](https://www.jetbrains.com/help/ai-assistant/acp.html)
states that the IDE downloads agent files, prepares required runtimes, launches
the executable, and offers updates under Settings → Tools → AI Assistant → Agents.
A compiled Go agent can use a binary distribution and needs no Node/Python wrapper.
A wrapper is needed only if the executable itself does not implement ACP.
Registry selection therefore can own installation UX with either transport option.
This benefit is not evidence in favor of SSH versus tsnet.

The [registry format](https://github.com/agentclientprotocol/registry/blob/6e560740b8dd4eae6ae420092e02d5dbd081ab10/FORMAT.md)
supports raw executables and zip/tar archives, explicit command/args/environment,
and optional SHA-256; Blaine should supply SHA-256. Metadata includes id, name,
version, description, distribution and license URL. Curated admission and auth
validation are required; a local/private fixture is not a public registry entry.

| Existing Go target | Registry target | Interpretation |
| --- | --- | --- |
| darwin/arm64 | darwin-aarch64 | Native binary supported by format; live IDE install pending |
| darwin/amd64 | darwin-x86_64 | Same |
| linux/amd64 | linux-x86_64 | Same |
| linux/arm64 | linux-aarch64 | Same |
| Native Windows | windows-x86_64 / windows-aarch64 | Format supports it; Blaine has no native Windows client in scope |
| Linux inside WSL | No WSL target | Linux artifact matches a Linux IDE backend. Generic help warns about WSL, while JetBrains support describes ACP running on Linux when the IDE backend runs in WSL via Remote Development. Windows-backend to Linux-agent launch is a separate unverified arrangement. |

Exact cache directory is IDE/version-specific and not promised by the guide;
record the installed executable path from the actual IDE experiment. Do not build
state location around an IDE cache or versioned binary path. Registry catalog
version updates and an IDE's installed-version update are separate operations.
The IDE exposes update/uninstall controls; continuous unattended update is not
assumed.

Do not turn the generic guide's WSL warning into an ACP protocol limitation.
[JetBrains support clarifies backend placement](https://youtrack.jetbrains.com/issue/LLM-28234/Claude-Code-ACP-in-AI-Assistant):
in its Claude Agent example, a Windows IDE opening a WSL project runs ACP on
Windows, while a Remote Development backend inside WSL runs ACP on Linux. This
is a documented topology distinction, not a measured Blaine/Codex launch on the
operator's installation. The [JetBrains ACP explanation](https://blog.jetbrains.com/idea/2026/08/how-to-use-ai-agents-in-intellij-idea-with-acp/)
explicitly lists Codex among the bundled ACP-compatible agents. Blaine targets
that same IDE-agent protocol boundary. A functioning Codex session with WSL files
does not by itself locate the agent process; equally, the guide's broad warning
does not establish that a Linux-backend ACP path is impossible. Record backend
OS and actual agent executable once in the consolidated IDE test, not a separate
transport investigation. No native Windows Blaine client or custom plugin is
introduced to resolve this question.

A concrete release constraint exists: the pinned registry schema requires root
`X.Y.Z`; it rejects `0.1.0-alpha.1`. Preview distributions only permit npm/PyPI,
not binary, and use the registry's preview-version convention. The existing alpha
release must not be relabeled stable to pass this check. Keep current GitHub
four-target binaries/checksums; future registry delivery needs a separately
reviewed channel/admission decision. Do not introduce a runtime wrapper just to
work around an alpha schema restriction. No release workflow was changed.

## 2. ACP authentication

[Released ACP schema v1.23.0](https://github.com/agentclientprotocol/agent-client-protocol/tree/schema-v1.23.0)
includes v1 auth methods, `authenticate`, auth-required errors and optional logout.
The [authentication contract](https://agentclientprotocol.com/protocol/v1/authentication)
permits an agent-owned browser flow. Initialization advertises `authMethods`;
`session/new` may return `-32000`; the IDE requests `authenticate` for an agent
method; successful completion returns `{}` and session creation can proceed.
This supports authentication after selection rather than mandatory CLI bootstrap.
It does not mean production Blaine is READY after network login alone.

Browser launching, callback server, OAuth state/PKCE if using OAuth, provider
exchange, credentials and refresh remain the agent/provider's responsibility.
ACP transports neither a universal token store nor automatic OAuth configuration.
The fixture opens only 127.0.0.1, requires an unpredictable state plus an explicit
POST, times out, and persists a private **MOCK ONLY** marker. It is deliberately
not an identity provider. No credentials or callback URLs enter evidence.

Terminal auth depends on a client capability and is a separate process. There
is a documentation discrepancy: registry AUTHENTICATION.md describes replacing
arguments/environment, while the released ACP contract describes appending args
and merging environment. The fixture uses agent auth, not that ambiguous route.
Logout is capability-gated; support in the installed IDE must be measured. Ending
application auth, logging out a tsnet node and administratively deleting a node
are distinct actions. None should cancel unrelated durable Tasks.

A Tailscale login URL is completed at Tailscale; the embedded backend observes
its state becoming Running. Blaine need not implement an OAuth callback server
for that particular flow. The mock callback demonstrates ACP/browser mechanics,
not the provider-specific Tailscale exchange.

## 3. Stable tsnet API and state

GitHub's stable release endpoint returned **v1.102.4**, released 2026-09-10, not a
prerelease. The [pinned module](https://github.com/tailscale/tailscale/blob/v1.102.4/tsnet/tsnet.go)
requires Go 1.26.6; this experiment uses the repository's Go 1.27.1. Dependencies
are isolated in `probe/go.mod` and `go.sum`; production `client/go.mod` is unchanged.

`tsnet.Server` embeds a userspace network stack. With the default nil `Tun`, this
path uses an in-process fake TUN/netstack, not `/dev/net/tun`; it does not install
a service or require a system tailscaled socket. `Start`, bounded `Up`, `Dial`,
`LocalClient`, `WhoIs` and `Close` provide the needed small API. The embedded
LocalClient addresses this instance, not the system daemon. See the
[overview](https://tailscale.com/docs/features/tsnet) and
[server API](https://tailscale.com/docs/reference/tsnet-server-api).

The fixture sets an explicit stable state directory outside any executable cache:

- macOS: `~/Library/Application Support/BlaineArchitectureSpike/tsnet`.
- Linux/WSL: `$XDG_CONFIG_HOME/BlaineArchitectureSpike/tsnet`, otherwise
  `~/.config/BlaineArchitectureSpike/tsnet`, on the distro filesystem.

The directory is 0700; upstream FileStore writes state with 0600. It contains
machine/node private keys, account/profile state and potentially other private
Tailscale state. Filesystem permissions are protection, not encryption at rest.
Never attach, commit, sync or clone this directory to another installation.
It is **not** the existing non-secret Blaine connection profile and must not be
silently folded into generic secret-delivery storage. Production adoption would
need an explicit credential-store/backup/uninstall policy.

The probe persists a unique node name and compares stable node ID on subsequent
runs, despite executable relocation. It closes the embedded instance on exit;
closing is not logout and does not delete its tailnet record. Credentials surviving
restart/upgrade are supported by API design. Separate-process reuse after binary
relocation is now operator-verified on the Mac and corroborated by the host's
stable peer ID. Diagnostic revision 2 also retained that identity across an actual
source/binary change; reboot and published-client upgrade remain live-gated.
Public node keys can rotate: correlate stable node ID, not a public-key string.

WSL also retained one stable ID across three processes, although the old
diagnostic boolean incorrectly conflated an absent measurement baseline with
non-reuse. Original reports and the correction are retained. Reboot persistence
is supported by the disk-state design, not measured on either workstation.

The upstream tsnet implementation uploads diagnostic logs to Tailscale by default;
silencing this fixture's console logger does not disable those uploads. Product
adoption needs an explicit logging/privacy policy alongside local credential
storage. This is distinct from sending application payloads or Blaine memory.

One node per installation must also work with multiple IDE windows. Sharing the
state file between independent embedded instances is not a proven coordination
mechanism. This fixture takes a file lock and permits only one instance at a time.
A production owner/multiplexing decision is required; spawning a new node per ACP
session would fail the product requirement. No persistent workstation daemon is
implemented by this spike.

System Tailscale and tsnet are separate nodes/identities and can coexist by design;
OS routing, firewalls, proxies and endpoint policy still require live checks.
Distinct persisted names prevent accidental name collisions; a hostname alone
never authorizes access. No new physical peer is selected: only the designated
Mac and WSL may enroll these experimental application nodes.

## 4. Identity, revocation and node lifecycle

A stable installation-owned identity permits independent revocation and narrow
network grants. Tailnet ACLs/grants can select an approved source node/address or
controlled tags and allow only the Hub service port. Hostname prefixes are not a
trustworthy enrollment classification. Existing broader allow rules must also be
considered: adding a narrow allow does not subtract broad access.

[Tags](https://tailscale.com/docs/features/tags) replace user ownership with tag
identity; they are not merely labels attached to the same user principal. Do not
silently tag a human-authenticated node and claim its user binding remains intact.
Possible policies are admin-managed source-node selectors preserving user identity,
or explicit app-node tags with a separate Blaine user binding. Neither policy has
been applied here. Positive Hub access and negative access to a forbidden port
must be measured after a reviewed policy; no broad ACL was added.

Conceptual future correlation: a Blaine installation/registration ID bound by the
host to transport-observed stable node ID plus validated owner/authentication and
application server identity. Caller-supplied node IDs are not evidence. Registration
status, workspace grants and revocation stay Blaine-owned; Tailscale is not the
sole application identity. This is decision analysis, not E0.D implementation.

The embedded LocalClient offers logout. Expiry/revocation must deny traffic and
require normal login/reapproval where appropriate. Removing a node through the
admin console/API, deleting local state, and revoking Blaine registration are
separate actions. Offline last-seen alone is insufficient reason to delete a
workstation: an infrequently used installation may still be legitimate.

Persistent nodes remain administratively visible after process exit/uninstall.
Keep an inventory mapping registration, stable node ID, creation/version and last
contact; define explicit retirement and retention. Reinstall with erased state
may enroll a new node and leave the old record. Automated cleanup requires scoped
administrative authority and is not implemented. Ephemeral nodes auto-clean but
conflict with the stable installation requirement; do not choose them by default.

Authentication options:

- **Interactive Tailscale login:** preferred spike; browser/provider flow enrolls
  the application node and may require device approval. SSO can reduce prompts;
  existing machine login is not an automatic credential for tsnet.
- **Auth keys:** concept only. A one-use/short-lived enrollment mechanism could
  enroll a node, but someone must securely issue it with appropriate policy.
  Never embed a reusable auth key or admin credential in the client. Revoking an
  enrollment key is not a substitute for removing already enrolled devices.
- **Future public OIDC gateway:** separate option, no deployment or IdP work here.

## 5. Direct stream and durable lifecycle

The minimal prototype uses mature `github.com/coder/websocket` **v1.8.15**, with
an explicit experimental subprotocol, bounded frames and per-operation contexts.
Its fixture service binds only loopback or the designated host's tailnet IP,
never wildcard/public interfaces, and expires after 20 minutes. No Hub runtime,
Restate, model, workspace or Task endpoint is invoked.

The experiment uses WebSocket over HTTP **inside WireGuard**, not public plaintext
transport. This proves a private primitive, not a production authentication design.
A production endpoint must bind actual socket peers using trusted Tailscale
observations (the private fixture exercises a bounded same-owner WhoIs check), apply application authorization and verify expected Hub server_id.
Headers or request JSON cannot supply the authoritative peer identity. An eventual
public gateway would additionally require TLS and independent application auth.

| Candidate | Fit and cost |
| --- | --- |
| WebSocket | Full-duplex binary frames, mature Go library, deadlines/close; simplest primitive for a bounded spike. Multiplexing channels, operation envelopes and replay rules remain application work. |
| HTTP/2 streaming | Multiplexed streams and flow control; server-originated operations need an established duplex request stream or another explicit channel, not assumed server push. |
| Connect/gRPC-style bidi | Typed schemas, stream cancellation and deadlines; adds schema/codegen/runtime commitments. Not needed to prove this primitive. |

A future envelope needs protocol version, request/operation ID, Task ID,
workstation/registration identity and route generation, message/channel type,
payload bounds, deadline and authorization. TCP/WebSocket flow control alone does
not bound every application queue; slow-reader tests and queue budgets remain.
Cancellation of an operation needs an explicit acknowledged protocol outcome;
closing a socket is not proof an effect never happened. Reconnect authenticates
again, invalidates stale routes and reconciles uncertain operations without blind
replay. stdout/stderr become logical channels, not terminal text conversion.

Restate remains authoritative for durable Tasks. Session disconnect affects only
operations requiring that workstation under their policy. The fixture demonstrates
server availability for another connection after disconnect; it does **not** prove
a live Restate Task continued. No Task lifecycle code was changed or invoked.

## 6. JetBrains tools and roadmap

[JetBrains' integration description](https://blog.jetbrains.com/idea/2026/08/how-to-use-ai-agents-in-intellij-idea-with-acp/)
distinguishes ACP interaction, optional MCP tools and agent-side tools. ACP can
negotiate file/terminal client capabilities and permission requests; actual support
must be read from initialization, not inferred from a Codex demonstration. A local
agent may also execute commands using its own tools without IDE terminal RPC.

`use_idea_mcp` and allowed-tool settings expose the integrated IDE server. This
can provide inspections and run configurations without a custom plugin. It does
not establish confinement, race-safe conditional writes or operation authority.
The auth fixture rejects MCP descriptors and exposes no local capability. E0 is
connection/onboarding; E1 proves confined reads; E2 proves conditional writes and
bounded execution; E3 proves the Java/Gradle workflow and genuine human interaction.

## 7. Comparison (design properties unless explicitly measured)

| Criterion | 1 — system Tailscale SSH | 2 — embedded tsnet + direct service |
| --- | --- | --- |
| End-user installation | Registry can install Blaine; system Tailscale remains prerequisite | Registry can install one binary containing tsnet; channel/admission and actual IDE-backend launch validation remain |
| First authentication | System enrollment plus SSH check when required | Agent-owned Tailscale enrollment/browser; device approval if configured |
| System Tailscale dependency | Yes | No CLI/daemon for data path; live Mac and WSL TCP/Hub checks under the operator's GUI-disconnected/quit setup; residual service/extension absence unmeasured |
| macOS | Existing live SSH wrapper byte/exit/channel evidence | arm64 private stream, identity reuse across binary revisions and three GUI-quit TCP/identity checks observed; delayed target visibility needs bounded readiness handling; reboot pending; amd64 build-only |
| Linux | Existing E0.A/B and transport fixtures | Go userspace architecture; native fixture tests and build |
| Windows + WSL2 | Windows ownership + guest route; helper/cleanup integration unresolved | ST00251 live enrollment and three name/IP TCP/Hub identity successes with same embedded node; no nested daemon; stream and exact service-state independence pending |
| Workstation identity | Existing machine node; installation remains distinct metadata/registration | Stable installation node is a useful binding input; separate Blaine registration still required |
| Server identity | Tailscale-distributed SSH host key plus Blaine server_id | Tailscale destination identity plus application server_id; production binding pending |
| Authorization | Network grants + SSH policy/Unix account + Blaine policy | Network grants + application authorization; no SSH account grants |
| Secrets | System Tailscale manages node state; Blaine profile non-secret | Blaine installation must protect private tsnet state; no hard-coded auth key |
| Encryption | WireGuard and SSH | WireGuard; TLS required for future public path |
| Framing | Existing NDJSON ACP relay/control handshake | Explicit application messages; WebSocket primitive passed locally and operator-reported on designated Mac; not production ACP |
| Binary safety | Mac fixed-byte probe passed | 1 MiB complete byte range passed locally and covered by Mac-reported fixture PASS; WSL stream unmeasured |
| Bidirectional streaming | SSH stdio supports both directions | Server-initiated binary and client roundtrip tested locally and covered by Mac fixture report; WSL primitive currently TCP-only |
| Cancellation | Local groups; remote sleep survived Ctrl+C, stdin-reading cat exited | Context deadline/cancel closes fixture stream; server observes disconnect; operation-effect cancellation remains application work |
| Reconnect | Reopen SSH and handshake; no automatic Task replay | Reopen stream and revalidate; operation reconciliation must be specified |
| Task/session independence | Preserved by server architecture, not provided by SSH | Same invariant; changing transport does not move Restate into client |
| Process tree | Blaine → helper/OpenSSH/proxy plus remote shell/dispatcher | Blaine with embedded stack → already-running private service |
| Unix account | Deployment-specific SSH account needed internally | No remote login account in application connection |
| Shell | Fixed remote command launch | No shell for network transport; browser launch remains OS integration |
| Tailnet policy | Existing SSH check/user rules plus network grants | Application-node classification and Hub-port grants; tags/user distinction requires decision |
| Node lifecycle | Reuses machine node | One persistent node per installation, independently revocable |
| Stale-node cleanup | Mostly existing machine administration | Installation retirement and node inventory required; restart must not create nodes |
| Observability | Native SSH/Tailscale diagnostics plus Blaine | Embedded networking diagnostics and app stream metrics owned by client/service |
| Debugging | Familiar SSH tools, but two process/platform boundaries | Single app entrypoint; must expose layered redacted diagnostics |
| Implementation complexity | Adapt helper, peer binding, deployment and cleanup; substantial pieces exist | New stream listener/protocol adapter, enrollment/state owner and policy; bounded primitive works |
| Custom code ownership | Transport orchestration + host dispatcher | Application adapter + state lifecycle; reuse mature Tailscale/WebSocket implementations |
| Maintenance | Track installed Tailscale/OpenSSH across platforms | Ship Tailscale/security updates with Blaine; larger dependency graph and binaries |
| Future public gateway | Replace SSH adapter while preserving higher-level contracts | Reuse application framing behind TLS/OIDC; network identity mapping still changes |

Option 3 is reference-only: an authenticated public TLS gateway could eliminate
Tailscale enrollment for workstations, but introduces exposed service operations,
OAuth/OIDC, abuse controls and application credential lifecycle. None is deployed.

## 8. Migration and decision gate

JetBrains provisioning and ACP agent auth can improve UX with either transport.
Embedded tsnet specifically targets the separately installed Tailscale dependency
and remote Unix/shell path. **Recommendation: choose option 2 for the next E0.C
design revision**, subject to explicit operator approval. Live evidence on both
designated platforms is sufficient to support that direction, not to certify
product readiness. Stable installation identity is a benefit consistent with the
later registration model; it does not replace application identity/authorization.

Adoption would amend A13/external prerequisite and non-secret client state rules,
the E0.B meaning, E0.C transport/peer contract and build/security dependencies.
Allowing browser authentication during `blaine acp` also requires an explicit
change to the current noninteractive ACP-launch rule, using protocol-negotiated
authentication rather than prompts or diagnostic output on ACP stdout.
Retain previous PASS evidence with its original scope. Keep the stable launcher,
server-owned Task lifecycle, platform distinction, PolicyGate and E0 sequencing.
The host would need an application listener and trusted socket-peer binding,
not a repackaged shell dispatcher. Existing framing/handshake invariants and
negative tests remain useful; provider-specific tests must be replaced explicitly.

The decision is not automatic and the spike does not accept E0.C. Before a
production claim, resolve one-state-owner behavior across multiple IDE processes,
credential lifecycle/revocation and narrowed node authorization, production Hub
listener/handshake/ACP checks, IDE delivery/auth UI and the actual Windows/WSL
IDE-backend launch arrangement. The alpha binary registry restriction and macOS notarization
experience remain delivery issues under either transport. Ordinary Linux/arm64
and macOS/amd64 are build-verified only; WSL execution is not a native Windows or
all-Linux runtime certification.

No production adapter or canonical decision was changed. E0.D remains blocked;
the next canonical implementation slice is still **E0.C**, after the transport
decision and any explicitly approved contract amendment. No new release, public
registry entry, native Windows client, plugin, gateway, workspace capability or
Task-lifecycle change was implemented. Generated artifacts remain ignored under
`.local/`; credentials and authentication URLs are absent from retained evidence.

**Decision requested:** Should E0.C remain on Tailscale SSH, or should the Blaine
workstation client move to embedded tsnet + a direct Blaine application transport?
