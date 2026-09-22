# E0.B — Tailscale prerequisite onboarding

**PARTIAL overall; PASS on the native Linux development platform.** E0.A remains
intact. E0 itself is not complete: E0.C–E0.F remain. macOS has design/build/fixture
proof only. Windows+WSL host reuse is **STOP pending a live verification spike**.

The [TaskSpec](request.json) is **unsubmitted**: no durable development Task binding
was exposed. The user explicitly authorized local implementation, safe live reads
and one local commit. No runtime Task identity, state or background execution is
claimed. No push or merge occurred.

## Development-host result

[Live evidence](live.json), recorded 2026-09-21 São Paulo time (2026-09-22 UTC):
Ubuntu 26.04.1 LTS, Linux `7.0.0-31-generic`, amd64, non-WSL.

```text
Tailscale: 1.102.4-t3caf7d9e7-g084ee3b64
Backend: Running
Native TUN: available
Authentication: authenticated
Device: online
Tailnet: visible
Assigned address count: 2
Health warning count: 0
```

Raw status JSON stayed in memory. No names, addresses, device IDs, peer maps,
keys, auth URLs or credential material were retained. Before/after comparisons
confirmed the same device and assigned addresses, and unchanged safe status.

`blaine connect` and `blaine connect --non-interactive` both exited **0**, printing:

```text
Checking workstation...
✓ Blaine client
✓ Platform detected
✓ Tailscale installed
✓ Tailscale authenticated
✓ Tailscale connected

Network prerequisite ready.
Blaine host connection will be configured in the next E0 stage.
```

A read-only `strace -f -e trace=execve` check asserted that each invocation launched
exactly one external command: `tailscale status --json`. The retained evidence is
that allowlisted command projection, not a raw trace. No install, up, logout,
service mutation or unnecessary authentication occurred. Fresh client config/state
locations remained absent. Existing tailnet connectivity was not disrupted.

Doctor human/JSON observations matched. Its Tailscale checks all passed:
installation present, owner `linux-system`, CLI available, daemon available,
authenticated, device online, tailnet visible, two addresses, zero health warnings,
WSL false. Overall remained **NOT_READY, exit 2**, because connection/remote host,
registration and IDE checks belong to later stages. No remote host was contacted.

The initial sandbox could see the binary/version but could not read the daemon
socket; the authorized read-only host run supplied actual live proof. That initial
unavailable observation was not counted as evidence of a broken host.

## Implemented behavior and limits

[Client guide](../../client/README.md) describes the shared state machine and exits.
[Mechanism decisions](mechanisms.md) record exact current vendor/platform choices.

- Inspect first; ready means no mutation or prompts. Missing installation offers
  supported action. Decline/failed install/native guidance returns nonzero.
- Signed APT assistance on allowlisted Debian/Ubuntu; preserve valid existing
  vendor repository configuration and stop on conflicting/partial metadata.
  Other distributions get official package guidance. No shell-pipe installer.
- Normal unprivileged `tailscale up --timeout=3m`, strict browser-URL presentation,
  bounded readiness polling and cancellation. Stopped state offers reconnection;
  no forced reauthentication, preference reset, operator grant or auth key.
  A daemon denying unprivileged onboarding requires administrator native login
  outside Blaine; client-driven elevation is limited to package/service setup.
- macOS native app and CLI are separate observations. Status uses documented
  child-only CLI mode; installation/login can open the official page/native app.
  OS installer/VPN/system-extension authorization stays visible and user-owned.
- WSL observes Windows status through available `tailscale.exe` interop, diagnoses
  unknown host availability and responding guest-daemon conflicts, but never
  mistakes Windows authentication for guest network readiness. No second daemon.
- Doctor is read-only and projects only safe scalar state/counts. No Blaine client
  configuration, login credential or duplicated Tailscale identity is persisted.

## Platform acceptance matrix

| Platform | Designed | Build-verified | Runtime-verified | Result |
| --- | --- | --- | --- | --- |
| Linux amd64, Ubuntu 26.04.1 | Yes | Yes, static ELF | Detection, real authenticated status, doctor parity, connect twice, no mutation | PASS for development-host E0.B criteria |
| Other allowlisted Debian/Ubuntu | Yes, APT fixtures | Linux amd64/arm64 | No install/login mutation proof | PARTIAL |
| Other Linux distributions | Vendor-guided assistance | Linux amd64/arm64 | No | PARTIAL; no automated installer claim |
| macOS amd64/arm64 | Native app/CLI/OS authorization | Both Mach-O targets | No | PARTIAL |
| Windows + WSL2 amd64/arm64 | Native Windows owner, bounded interop diagnostics | Linux artifacts only | No Windows/WSL workstation available | STOP for reuse readiness; fixtures are not runtime proof |

## Retained verification

| Evidence | Scope |
| --- | --- |
| [tests.txt](tests.txt) | 43 top-level Go tests, including 19 shared connect state-machine scenarios; no real host installation/login/service mutation. |
| [race.txt](race.txt), [static.txt](static.txt) | Race instrumentation and go vet passed. |
| [offline.json](offline.json) | E0.A ACP regression copied into this slice with only connect/doctor expectations updated: standalone execution outside checkout, empty PATH, fresh home, exact byte/hash equality, stderr isolation, streaming before EOF, malformed invocations, exit propagation, deadline, signal cleanup and no client state. |
| [build.txt](build.txt), [builds.json](builds.json) | Go 1.27.1, CGO disabled, four standalone targets, identical repeat builds, sizes/formats/SHA-256, exact client source hashes. Linux amd64 has no dynamic interpreter. |
| [live.json](live.json) | Actual read-only host state, human/JSON doctor parity, two connect runs, allowed child commands and before/after invariants. |
| [vendor-metadata.json](vendor-metadata.json) | HTTPS-read official Ubuntu resolute public key/source metadata hashes; generated APT source exactly matches vendor. This is not package installation or signature-validation runtime proof. |
| [docs.txt](docs.txt), [summary.json](summary.json) | Local documentation consistency and acceptance summary. |

State fixtures cover missing CLI/install, daemon unavailable, logged out,
authenticated, stopped, starting, expired device authentication, device approval,
offline state, absent addresses, userspace/no-TUN mode, health warnings, malformed
and unknown status. Flow cases include installation failure/decline, login success,
login failure/decline/cancellation/timeout, successful child exit without readiness,
non-interactive refusal and repeated ready invocations with zero mutations.

Platform fixtures include kernel/env WSL detection, Windows executable unavailable,
Windows process/service failure, connected host with guest reuse unverified,
topology conflict, macOS missing app, app without CLI, CLI-only ownership unknown,
native authorization failure, embedded CLI mode and native app login/recheck.
Secret sentinels in raw errors/status, auth URLs, keys, peer/user data and health
text never escape the status/diagnostic projection. Only the intended validated
login URL reaches interactive authentication output. HTTPS tests reject wrong
origin, redirects, oversized/invalid key bodies and failed downloads without
mutation; installation fixtures inspect signed-by paths, safe argv, sudo scope,
signature-enforcement flags, temporary cleanup and abort after each failed step.

An isolated PTY fixture proves foreground borrowing/restoration for a native
password-owning helper and cancellation; it invokes no sudo or credentials. ACP
continues to use the original direct stream primitive and no PTY allocation.
Package-manager effects remain OS-owned and cannot be rolled back by process
cancellation. Actual fresh installation/login was intentionally not attempted on
the connected development workstation.

## Reproduce

```bash
BLAINE_GO=/tmp/blaine-e0a-toolchain/go/bin/go \
GOCACHE=/tmp/blaine-go-cache GOPATH=/tmp/blaine-go-path \
experiments/e0b-tailscale-onboarding/verify.sh

# Separately, on an already authenticated native Linux host, read-only:
python3 experiments/e0b-tailscale-onboarding/accept_live.py \
  .local/e0b-artifacts/blaine-linux-amd64
```

The offline script does not read live Tailscale status. The live script requires
existing authentication and does not install/login/logout. Outputs are written
only under the experiment when explicitly redirected. Distributed binaries need
no Go runtime; artifacts stay in ignored `.local/e0b-artifacts/`.

Build metadata names base source commit `503d56231e55183a0707ecf0eece8c2cc2223f29-dirty`
because artifacts precede the coherent local commit. `builds.json` pins exact
client source bytes; the enclosing Git commit retains them. No reproducibility
claim depends on pretending a dirty snapshot was already committed.

## E0.C handoff and exclusions

E0.C must supply the configured Blaine host/profile and validate trusted transport
peer binding, bounded protocol handshake/compatibility and remote ACP framing.
Local network readiness is the continuation boundary, not permission to discover
or register a host. No MagicDNS Blaine hostname, SSH configuration, host discovery,
handshake, registration, IntelliJ configuration or remote PersonalACP launch was
implemented. E0.D registration, E0.E IDE ownership/configuration and E0.F full
connect/doctor acceptance remain open.

Before cross-platform release, run native macOS app/login/authorization acceptance
and the Windows+WSL2 ownership/version/guest route spike. The current JetBrains WSL
ACP limitation belongs to E0.E separately. Fresh Linux install/authentication and
additional distro mechanisms need isolated runtime verification. None of those
gaps is represented as development-host installation/login proof.
