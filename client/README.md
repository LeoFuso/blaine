# Blaine workstation client — E0.A / E0.B / E0.C

A standalone client foundation, separate from the Python Personal Agent under
`runtime/`. This implements **E0.A, E0.B and a PARTIAL E0.C candidate** from the
[Hub design](../docs/personal-agent-hub.md) and
[ADR 0022](../docs/decisions/0022-workstation-personal-agent-client.md).
Tailscale detection, installation assistance and native login are implemented.
E0.C adds explicit MagicDNS profile resolution, strict SSH transport, handshake
validation and guarded ACP framing. Production peer binding and remote launch are
still unavailable; no second workstation was designated. See the
[E0.C contract](../docs/contracts/host-connection.md) and
[evidence](../experiments/personal-agent-hub/e0c/README.md). Registration and IntelliJ
configuration remain later slices. Full E0 is not accepted.

## Commands and exits

| Invocation | Current behavior |
| --- | --- |
| `blaine version` | One line: `blaine VERSION protocol=1 commit=COMMIT go=GO_VERSION platform=OS/ARCH`; exit 0. Offline, no config access. |
| `blaine version --json` | One JSON object with `schema_version: 1`, `client_version`, `protocol_version`, `build_commit`, `go_version`, `os`, `arch`; exit 0. |
| `blaine doctor [--json]` | Read-only foundation plus real Tailscale installation, owner, CLI/daemon, authentication and device/network observations. Full onboarding stays NOT_READY; ordinarily exit 2. |
| `blaine connect [--non-interactive] [--host NAME]` | E0.B network preparation, then explicit/cached host handshake. First use qualifies a short name using native MagicDNS metadata and defaults SSH user to the local account. Failed handshake preserves configuration. Even a fixture-valid host stays NOT_READY (exit 2), awaiting E0.D/E. |
| `blaine disconnect` | JSON `{ "schema_version": 1, "command": "…", "status": "NOT_IMPLEMENTED", "milestone": "E0.A" }`; exit 2, no effects. |
| `blaine acp` | Requires a verified profile and fresh host handshake, then guarded remote framing. Missing profile returns NOT_CONFIGURED with empty stdout. Production host peer binding remains gated, so no working remote-agent claim. |
| `blaine acp --fixture echo` | Bounded subprocess byte roundtrip, operational diagnostics on stderr. No ACP handshake/parser or networking. |
| `blaine acp --fixture exit-23` | Same process relay, child exit 23 propagated. |
| `blaine acp --fixture wait` | Wait until cancellation or the fixed five-second deadline; exits 130 or 124. |

Unknown commands, extra positional arguments and unsupported flags return 64 with
usage on stderr. No arbitrary executable/shell CLI option exists. ACP stdout is
empty on usage/configuration failures. Exit 1 means an internal/start/I/O failure. Connect returns 2 for declined actions,
failed prerequisites or manual remediation, 124 for timeouts and 130 for cancellation.
`connect --non-interactive` never installs, logs in or prompts. E0.C may persist the
first profile only after verified host identity and readiness. Host/control failure
returns 3; incompatible protocol/features returns 4; local/trust/config action returns 2.
Normal child exits pass through; child signal exits use 128 + signal number.
The raw byte fixture retains its accepted cancellation exits. The new framed
bridge reports a lost/invalid connection nonzero after cleanup; it never replays a
prompt or changes a Task lifecycle.

`version` metadata defaults to `0.1.0-dev`, commit `unknown` in an unparameterized
`go build`. Protocol 1 is the Blaine handshake version, independent of ACP negotiation.
The E0.C verification build embeds `0.1.0-e0c` and an explicit source commit.
JSON schema 1 is the output envelope.

Doctor retains the versioned schema 1 report (`timestamp`, `overall`, `checks`).
Both renderers use identical observations and remediation. Overall remains
`NOT_READY` because required host/registration/IDE gates remain open, even when
`tailscale` is PASS. Doctor never initiates login, browser launch, package install,
service start or client-state writes. Directory checks still do not certify future
write permissions. Doctor reads an existing profile and attempts its bounded
handshake; it never creates a profile or modifies SSH known-host trust.

Tailscale checks are `tailscale`, `tailscale_installation`, `tailscale_owner`,
`tailscale_cli`, `tailscale_daemon`, `tailscale_auth`, `tailscale_device`,
`wsl_environment`, plus `wsl_host_reuse`/`wsl_version` on WSL. Device reporting is
limited to online state, tailnet visibility, assigned-address count, health-warning
count and validated version metadata. No peer/user/tailnet names, actual addresses,
health text, login URLs or keys appear in doctor. Future check IDs remain
`connection`, `remote_blaine`, `restate`, `mirix`, `qwen`, `intellij_acp`.

Exit priority remains 1 internal, 4 incompatible, 2 local remediation/unimplemented,
3 remote/unknown required readiness, then 0 only if every required check passes.
Only connect's **network prerequisite** may be ready in this slice.

## E0.B connection flow and installation trust

Connect inspects first and returns immediately when already ready. Otherwise it
offers an available installation action, re-inspects, then offers native login or
reconnection. Every action is followed by observation; a successful child exit is
not readiness evidence. Readiness requires Running, native TUN available, online
self device, visible tailnet, assigned Tailscale addresses and no health warnings.
This is local prerequisite proof; it does not certify a route to any Blaine host.
Stopped devices can be reconnected without forcing reauthentication or resetting
preferences. Device approval, offline state, health warnings, unknown/malformed
status and unreachable service produce remediation and a nonzero exit.

All command arguments are structured. Status probes take at most eight seconds;
installation five minutes; authentication three minutes, including one-second
readiness polling. Ctrl+C cancels the owned child; it never logs out or rolls back
Tailscale identity. Partial package setup may remain after failure/cancellation and
is reported for administrator repair. No automatic retries, sudoers changes,
operator grants, tailnet policy changes or auth-key creation occur.

| Platform | Implemented assistance | Current limits |
| --- | --- | --- |
| Linux | Resolve `tailscale` through PATH; `status --json` checks the daemon. On allowlisted Debian/Ubuntu, offer official APT repository/package installation using scoped sudo. Invoke unprivileged `tailscale up --timeout=3m` for native browser login/reconnect. | Hosts denying unprivileged Tailscale operations require administrator native onboarding (`sudo tailscale up`), outside Blaine. Blaine does not elevate login or persist operator privilege. Other distributions receive vendor package guidance. |
| macOS | Prefer `/Applications/Tailscale.app`; inspect its embedded CLI using child-only `TAILSCALE_BE_CLI=1`, otherwise resolve PATH CLI. Distinguish app absent, app present without CLI, CLI-only ownership unknown, native authorization unavailable, login required and connected. Open official download page or native app after confirmation; poll native login completion. | Signed Standalone installer, VPN/system-extension and browser dialogs remain user/OS actions. No Homebrew daemon or unsupported headless setup. App outside `/Applications` requires ownership review. Runtime unverified. |
| Windows + WSL | WSL markers select Windows ownership. Resolve `tailscale.exe` through inherited PATH and query bounded JSON status. A responding Linux CLI/daemon alongside it yields topology conflict. Give Windows-native install/login guidance. | Missing executable cannot distinguish host absence from disabled interop or PATH differences. No guessed `/mnt/c` path. Windows status never proves WSL2 version or guest reachability: reuse remains UNKNOWN, connect cannot succeed on WSL pending live verification. No nested daemon, network repair or Windows mutation. |

APT assistance allowlists Ubuntu jammy/noble/questing/resolute and Debian
bullseye/bookworm/trixie. It reuses an exact official `signed-by` source/key when
present; otherwise downloads only the official public signing key from
`https://pkgs.tailscale.com/stable/<distro>/<release>.noarmor.gpg` with verified
HTTPS, no redirects and a 64 KiB limit. It generates the vendor's scoped source
list and uses `sudo -k --` only for installing public repository metadata, APT
update/install and (when detected) `systemctl start tailscaled`. APT signature
checks are explicitly enforced. Existing differing/partial repository metadata
requires review and is never overwritten. OS repository/package changes persist;
Blaine's temporary public bootstrap files are removed. Nothing runs `curl | sh`.

Sudo owns its password dialog directly on the controlling terminal. Its timestamp
cache is neither reused nor updated by these commands; Blaine stays non-root.
Installation commands borrow and restore foreground terminal ownership. No admin
password passes through Blaine's reader or diagnostic sink.

Linux login emits only strict `https://login.tailscale.com/a/<alphanumeric>` URLs
to the interactive terminal, including when vendor output arrives in chunks.
Other command output is withheld; login URLs are never written to disk or doctor.
Opening a Linux browser is optional: the user opens the displayed URL. Custom
control-server URLs require native Tailscale login outside Blaine. Normal Tailscale
credentials remain exclusively in Tailscale-owned storage.

The [installation decisions and primary sources](../experiments/e0b-tailscale-onboarding/mechanisms.md)
record current Linux package choices, native macOS distributions, Homebrew
cask/formula distinctions and WSL interop limits.

## Platform and config boundary

`internal/platform` owns detection, paths, executable discovery and Tailscale adapters.
Linux kernel markers and WSL environment hints select the WSL adapter; they do
not certify WSL version or interop. Native Windows is unsupported. WSL uses the
Linux artifact and selected distro's home, never a guessed Windows profile.

| Purpose | Linux / WSL distro | macOS |
| --- | --- | --- |
| Non-secret user configuration | `$XDG_CONFIG_HOME/blaine/config.json`, default `~/.config/blaine/config.json` | `~/Library/Application Support/Blaine/config.json` |
| Durable local client state/receipts | `$XDG_STATE_HOME/blaine/`, default `~/.local/state/blaine/` | `~/Library/Application Support/Blaine/state/` |
| Transient process state | Optional `$XDG_RUNTIME_DIR/blaine/`; otherwise memory | Memory; future temporary files must use a private OS temporary directory |
| Secrets | Native Tailscale/SSH stores; any justified future pairing secret uses an OS credential store | Same; native OS credential store for a justified future secret |

**E0.A/B introduced no persisted state.** E0.C adds schema-1 host/client/server
metadata after successful verification, private permissions, atomic first publish
and rejection of existing/concurrently created destinations. It does not implement
re-pairing, registration, logs or a database. No live profile was persisted because
the production identity gate is unresolved.
Relative XDG overrides fail validation. Future writes must use restrictive
permissions, atomic replacement and concurrency checks per the existing design.
Do not put secrets in normal config/state. Optional macOS file logs would belong
under `~/Library/Logs/Blaine/`, but no file logger exists now.

The Tailscale adapter exposes inspection, installation planning/execution and
native authentication to the small shared connect state machine. IDE ownership
discovery and a Windows-to-WSL launcher remain later work; no plugin framework
or second WSL daemon is introduced.

## ACP and process contract

`internal/process.Run` accepts an absolute executable, an argument vector and
three `*os.File` streams. It uses `os/exec`, never `sh -c`, an allocated PTY, encoding
conversion, line scanning or a protocol buffer. Stdio descriptors are inherited
directly, preserving bytes, duplex streaming and OS backpressure; there are no
stdin-copy goroutines to hang after early child exit. All CLI operational output
in the ACP branch goes through its stderr diagnostic function. Future logging
can replace that sink without gaining access to protocol stdout.

Linux/macOS/WSL use a dedicated POSIX process group. Cancellation immediately
SIGKILLs the group and waits/reaps the direct child; normal leader exit also kills
remaining group members. Immediate termination is intentional for disposable
transport resources, not workspace execution or durable Task cancellation.
Helpers must remain in the owned group: daemonizing/`setsid` helpers are outside
this primitive's contract. Orphan descendant zombies are reaped by the OS/init;
tests distinguish terminated zombies from live processes. No promise is made
about cleanup after SIGKILL of the launcher itself or a host crash.

The fixture self-execs the same installed binary with the internal
`acp --fixture-worker MODE` entrypoint. Both entrypoints are bounded to five seconds;
echo accepts at most 1 MiB (one extra byte is read/emitted to detect overflow, then
exit 1). `wait` exists only to exercise cancellation/deadlines. The fixture carries
arbitrary bytes, including invalid UTF-8, as a purity test; it is **not ACP protocol
validation**. The E0.C candidate adds a separate strict NDJSON frame relay with correlation,
size/pending-request bounds and banner rejection. It strips advertised client
capabilities and rejects MCP/host capability calls; no workspace authority exists.
Its real-pipe tests are fixtures, not remote Tailscale/ACP acceptance.

Non-protocol prerequisite commands use bounded in-memory capture around the same
process primitive. Raw status/authentication output is never persisted. Child-only
environment overrides support the documented macOS CLI mode without changing the
parent environment. Foreground terminal borrowing applies only to installation;
The E0.A raw fixture still inherits streams directly; the E0.C candidate validates
complete frames in bounded pipes before forwarding. Package managers and native
apps may launch OS-owned services outside the transport process-group contract;
cancellation never claims to roll back or stop those services.

## Build and validation

Use Go 1.27.1 for the recorded reproducible build (module language floor 1.23).
Only the standard library is used. The compiler is a developer dependency; users
need only the produced binary. From the repository root:

```bash
BLAINE_COMMIT="$(git rev-parse HEAD)" client/build.sh
.local/e0b-artifacts/blaine-linux-amd64 version
.local/e0b-artifacts/blaine-linux-amd64 doctor  # expected exit 2: full E0 is not ready
```

Append `-dirty` to the commit when building modified sources. `BLAINE_GO` may name
an absolute Go executable. `BLAINE_VERSION` defaults to `0.1.0-e0b`. The build is
`CGO_ENABLED=0`, `GOTOOLCHAIN=local`, `GOPROXY=off`, `-trimpath`, `-buildvcs=false`,
with a cleared build ID and explicit version/commit linker values. There is no
build timestamp. Pin source bytes, metadata and Go version to reproduce hashes.
The script builds linux/amd64, darwin/amd64, darwin/arm64 and linux/arm64 into the
ignored `.local/e0b-artifacts/` directory; binaries are not committed.

```bash
cd client
go test ./...
go test -race ./...  # requires a host C compiler for Go's race instrumentation
go vet ./...
```

[Offline acceptance script](../experiments/e0b-tailscale-onboarding/accept_offline.py) copies the
binary to a temporary directory outside the checkout and runs it with an empty
command PATH and fresh home. It asserts byte/hash equality, stderr separation,
streaming before EOF, errors, exit propagation, deadlines and signal cleanup.
The [verification script](../experiments/e0b-tailscale-onboarding/verify.sh) reproduces the
bounded build/test/evidence pass without internet or live services.

| Target | Designed | Build-verified | Runtime-verified |
| --- | --- | --- | --- |
| Native Linux amd64 | Yes | Yes | Ubuntu 26.04.1, existing Tailscale 1.102.4: detection/doctor/idempotence PASS. Install/login mutation is fixture-only. |
| Native Linux arm64 | Yes | Yes | No |
| Native macOS amd64/arm64 | Yes | Yes | No; app/CLI/native UI paths remain PARTIAL. |
| Windows + WSL2 amd64/arm64 | Windows-host ownership | Linux artifacts | No; host-network reuse STOP pending live spike. |

Build proof is not runtime support. [E0.B evidence](../experiments/e0b-tailscale-onboarding/README.md)
contains the live safe status projection, no-mutation command trace, deterministic
state machines, ACP regression, hashes and remaining E0.C–E0.F gates.
