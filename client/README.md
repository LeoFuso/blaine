# Blaine workstation client — E0.C direct transport candidate

Small standalone Go workstation client, separate from the durable Python runtime.
The operator selected embedded tsnet and a direct private application transport.
**E0.C is PARTIAL; full E0 is unaccepted.** The public `v0.1.0-alpha.1` remains the
previous SSH candidate; no replacement release has been published.

The [canonical Hub plan](../docs/personal-agent-hub.md),
[ADR 0022](../docs/decisions/0022-workstation-personal-agent-client.md),
[direct protocol contract](../docs/contracts/host-connection.md) and
[migration evidence](../experiments/personal-agent-hub/e0c-direct/README.md)
record the decision, exact boundaries and pending live gates. E0.A and E0.B evidence
keeps its accepted historical scope. Old SSH/native onboarding modules and tests
remain available for comparison; the normal product commands use the direct path.

## Commands

| Command | Candidate behavior |
| --- | --- |
| `blaine version [--json]` | Offline client/protocol/exact source commit/Go/platform metadata. |
| `blaine doctor [--json]` | Read-only local checks, no embedded network start or state writes. Cached identity is not fresh connection evidence. Full E0 remains NOT_READY. |
| `blaine connect` | Enroll/reuse this installation's tsnet node, discover the internal Hub candidate, validate network + Blaine identities/readiness, persist the verified profile. No host or Unix username input. CONNECTED does not mean E0 onboarding complete. |
| `blaine connect --non-interactive` | Use existing enrollment; fail AUTH_REQUIRED instead of opening a browser. |
| `blaine connect --verify-transport` | Additionally run bounded production-path binary, cancellation, deadline, reconnect and remote ACP session diagnostics; no Task/workspace effects. |
| `blaine acp` | Standard local ACP frontend/authentication, then remote PersonalACP; stdout is only JSON-RPC. No workstation capabilities granted. |
| `blaine disconnect --logout` | Explicit embedded-node logout; preserve identity/store for inspection. Does not affect system Tailscale or Tasks. |
| `blaine disconnect --logout --reset-identity` | Confirm logout, then explicitly discard this installation's identities; later re-enrollment needs renewed host authorization. |
| `blaine acp --fixture echo\|exit-23\|wait` | Accepted E0.A bounded direct-file-descriptor/process-group fixtures, unchanged. |

Normal shutdown preserves node and application keys. One concurrent process may
lease the installation; another returns INSTANCE_BUSY. No workstation broker,
self-updater, background daemon or native Windows client is introduced. Linux/WSL
state lives under `$XDG_STATE_HOME/blaine/direct-v1` (default `~/.local/state`);
macOS uses `~/Library/Application Support/Blaine/state/direct-v1`. Private seed and
node credentials require 0700 directories/0600 files, safe ownership and no links.
Never send that state in acceptance reports. Reboot, upgrade and revocation claims
must distinguish fixture/spike evidence from this candidate's live measurements.

Exit status: 0 for the requested successful connection/operation, 2 for local/auth
remediation, 3 for unavailable/denied remote identity/transport/readiness, 4 for
protocol incompatibility, 64 for usage, 130 for cancellation. The raw fixture keeps
its original exit/signal/deadline contract. Loss of an ACP session never cancels,
completes or restarts a durable Task, and no prompt is automatically replayed.

## Build and validation

Go is pinned in `.go-version` to **1.27.1**. Public modules are pinned in `go.mod`
and `go.sum` (tsnet 1.102.4, coder/websocket 1.8.15); compile requires no secret.
Fetch pinned modules once with `go -C client mod download`; `client/ci.sh` then
uses offline module resolution for formatting, tests, race, vet, host checks,
E0.A/B/C regressions and reproducible builds. Existing Actions workflows were
extended, not replaced; ordinary CI remains contents:read. No release was invoked.

Build matrix: linux/amd64, linux/arm64, darwin/amd64, darwin/arm64. WSL2 consumes
the Linux amd64 binary. Names remain `blaine-OS-ARCH`; one `checksums.txt` covers all
four. Generated executables are ignored. The embedded stack increases binary size
and dependency surface relative to the stdlib-only E0.A foundation.

[Release installation](INSTALL.md) still documents the published alpha. The
[local candidate batch](../experiments/personal-agent-hub/e0c-direct/OPERATOR.md)
uses verified artifacts without a workstation build or SCP. The target provisioning
UX is JetBrains launching `blaine acp`; current manual candidate setup is validation,
not the final installer. Real Blaine-specific IDE launch/auth evidence remains
required. Changelog tooling and provenance/signing hardening remain recorded
release follow-ups; no changie automation or new prerelease is added here.
