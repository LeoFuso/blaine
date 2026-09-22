# Blaine workstation client — E0.A

A standalone client foundation, separate from the Python Personal Agent under
`runtime/`. This implements **E0.A only** from the
[Hub design](../docs/personal-agent-hub.md) and
[ADR 0022](../docs/decisions/0022-workstation-personal-agent-client.md).
Networking, onboarding, registration, IntelliJ configuration and real remote ACP
are unavailable. No plugin or daemon is installed. Full E0 is not accepted.

## Commands and exits

| Invocation | Current behavior |
| --- | --- |
| `blaine version` | One line: `blaine VERSION protocol=1 commit=COMMIT go=GO_VERSION platform=OS/ARCH`; exit 0. Offline, no config access. |
| `blaine version --json` | One JSON object with `schema_version: 1`, `client_version`, `protocol_version`, `build_commit`, `go_version`, `os`, `arch`; exit 0. |
| `blaine doctor [--json]` | Read-only local build, platform, config/state-directory shape and executable resolution checks. Future checks are UNKNOWN/NOT_IMPLEMENTED. Always NOT_READY in E0.A; ordinarily exit 2. |
| `blaine connect` / `blaine disconnect` | JSON `{ "schema_version": 1, "command": "…", "status": "NOT_IMPLEMENTED", "milestone": "E0.A" }`; exit 2, no effects. |
| `blaine acp` | Empty stdout, NOT_CONFIGURED diagnostic on stderr, exit 2. Safe to launch, but not yet a working ACP agent. |
| `blaine acp --fixture echo` | Bounded subprocess byte roundtrip, operational diagnostics on stderr. No ACP handshake/parser or networking. |
| `blaine acp --fixture exit-23` | Same process relay, child exit 23 propagated. |
| `blaine acp --fixture wait` | Wait until cancellation or the fixed five-second deadline; exits 130 or 124. |

Unknown commands, extra positional arguments and unsupported flags return 64 with
usage on stderr. No arbitrary executable/shell CLI option exists. ACP stdout is
empty on usage/configuration failures. Exit 1 means an internal/start/I/O failure.
Normal child exits pass through; child signal exits use 128 + signal number.
SIGINT and SIGTERM cancellation of the launcher both return 130 after cleanup.

`version` metadata defaults to `0.1.0-dev`, commit `unknown` in an unparameterized
`go build`. Protocol 1 is the **reserved Blaine handshake version**, not a claim
that handshake or ACP version negotiation exists. The release build embeds
`0.1.0-e0a` and an explicit source commit. JSON schema 1 is the output envelope.

Doctor uses the accepted statuses PASS, FAIL, UNKNOWN, NOT_APPLICABLE and the
versioned timestamp/overall/checks envelope in the Hub design. No external commands
are currently required or invoked. It validates absolute user/XDG paths, directory
components and executable resolution without making directories, probing writes,
reading config contents, dumping environment variables or logging private paths.
Absent directories pass the *location* check; this does not certify permissions
for future writes or a configured connection. Symlink/non-directory/inaccessible
components fail visibly. It checks no service or credential store.

Future stable IDs are `connection`, `tailscale`, `remote_blaine`, `restate`, `mirix`,
`qwen`, `intellij_acp`; each is UNKNOWN/NOT_IMPLEMENTED today. Replace placeholders
with observed checks in their owning slices. WSL detection adds UNKNOWN/
WSL_UNVERIFIED until a later native interop probe establishes WSL2. Exit priority
is 1 internal, 4 incompatible, 2 local remediation/unimplemented, 3 remote/unknown
required readiness, then 0 only if all required checks pass. E0.A cannot emit READY.

## Platform and config boundary

`internal/platform` owns detection, paths and executable discovery in one file.
Linux kernel markers and WSL environment hints select the WSL adapter; they do
not certify WSL version or interop. Native Windows is unsupported. WSL uses the
Linux artifact and selected distro's home, never a guessed Windows profile.

| Purpose | Linux / WSL distro | macOS |
| --- | --- | --- |
| Non-secret user configuration | `$XDG_CONFIG_HOME/blaine/config.json`, default `~/.config/blaine/config.json` | `~/Library/Application Support/Blaine/config.json` |
| Durable local client state/receipts | `$XDG_STATE_HOME/blaine/`, default `~/.local/state/blaine/` | `~/Library/Application Support/Blaine/state/` |
| Transient process state | Optional `$XDG_RUNTIME_DIR/blaine/`; otherwise memory | Memory; future temporary files must use a private OS temporary directory |
| Secrets | Native Tailscale/SSH stores; any justified future pairing secret uses an OS credential store | Same; native OS credential store for a justified future secret |

**E0.A persists nothing.** No config file, client identity, registration, secret,
log or local database is created. Config contents and their versioned schema will
be introduced with the first real consumer; E0.A establishes locations only.
Relative XDG overrides fail validation. Future writes must use restrictive
permissions, atomic replacement and concurrency checks per the existing design.
Do not put secrets in normal config/state. Optional macOS file logs would belong
under `~/Library/Logs/Blaine/`, but no file logger exists now.

Prerequisite installation/status/authentication and IDE ownership discovery will
extend this boundary when they have real consumers. No speculative installer
interface, Windows-to-WSL launcher shim or plugin framework is implemented. WSL2
continues to use native Windows Tailscale by design; E0.A runs no Tailscale command
and installs no second daemon.

## ACP and process contract

`internal/process.Run` accepts an absolute executable, an argument vector and
three `*os.File` streams. It uses `os/exec`, never `sh -c`, a PTY, encoding
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
validation**. No remote stdout is admitted in E0.A. E0.C must implement the accepted
remote framing/banner rejection and handshake gates before enabling real ACP.

## Build and validation

Use Go 1.27.1 for the recorded reproducible build (module language floor 1.23).
Only the standard library is used. The compiler is a developer dependency; users
need only the produced binary. From the repository root:

```bash
BLAINE_COMMIT="$(git rev-parse HEAD)" client/build.sh
.local/e0a-artifacts/blaine-linux-amd64 version
.local/e0a-artifacts/blaine-linux-amd64 doctor  # expected exit 2 in E0.A
```

Append `-dirty` to the commit when building modified sources. `BLAINE_GO` may name
an absolute Go executable. `BLAINE_VERSION` defaults to `0.1.0-e0a`. The build is
`CGO_ENABLED=0`, `GOTOOLCHAIN=local`, `GOPROXY=off`, `-trimpath`, `-buildvcs=false`,
with a cleared build ID and explicit version/commit linker values. There is no
build timestamp. Pin source bytes, metadata and Go version to reproduce hashes.
The script builds linux/amd64, darwin/amd64, darwin/arm64 and linux/arm64 into the
ignored `.local/e0a-artifacts/` directory; binaries are not committed.

```bash
cd client
go test ./...
go test -race ./...  # requires a host C compiler for Go's race instrumentation
go vet ./...
```

[Offline acceptance script](../experiments/e0a-blaine-client/accept.py) copies the
binary to a temporary directory outside the checkout and runs it with an empty
command PATH and fresh home. It asserts byte/hash equality, stderr separation,
streaming before EOF, errors, exit propagation, deadlines and signal cleanup.
The [verification script](../experiments/e0a-blaine-client/verify.sh) reproduces the
bounded build/test/evidence pass without internet or live services.

**Runtime evidence: Linux amd64 only.** macOS amd64/arm64 and Linux arm64 have build
proof only. Linux amd64/arm64 are the intended WSL2 binaries; no WSL runtime,
Windows interop, macOS runtime, IDE launch, package signing or installer acceptance
is claimed. Cross-build support is not runtime support. See the
[evidence report](../experiments/e0a-blaine-client/README.md) and
[current roadmap](../docs/roadmap/001-blaine-development-roadmap.md#current-next).
