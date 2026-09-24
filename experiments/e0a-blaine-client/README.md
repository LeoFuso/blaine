# E0.A — Portable Blaine Client Skeleton

**PASS — isolated E0.A foundation, Linux amd64 runtime.** Full E0 is not accepted.
macOS and WSL2 have no runtime acceptance. No networking/onboarding, workstation
registration, IntelliJ plugin/configuration or server/runtime change was made.
No push or merge is authorized or performed.

The [TaskSpec](request.json) is **unsubmitted**: no suitable durable development
Task creation binding was available. The user explicitly authorized this local
implementation. No Task ID, runtime state or background execution is claimed.

## Decision and boundaries

[Go decision and acquisition evidence](language.md) records the accepted rationale,
host availability check and verified official build-tool download. Implementation
is the independent [client module](../../client/README.md), with no external Go
dependencies or server changes. The five-command contract, doctor exits, config
locations, process assumptions and remaining gates are documented there.

Config paths exist as an abstraction; E0.A has no config consumer and persists
nothing. Config schema/persistence is deliberately left to the first real consumer
in later E0 slices, avoiding invented connection fields or a premature migration.
No secrets belong in that config. Platform fixtures cover Linux, macOS and WSL
markers, XDG overrides, spaces and invalid paths. Native Windows is rejected;
WSL markers never certify WSL2, native Windows ownership or IDE compatibility.

## Retained proof

| Evidence | What it proves |
| --- | --- |
| [tests.txt](tests.txt) | Offline Go tests: version, argument rejection, doctor state/exit priority and read-only behavior, platform paths, literal argv, stream bytes, normal/signal exit codes, cancellation with blocked streams and descendant cleanup. |
| [race.txt](race.txt), [static.txt](static.txt) | Race instrumentation and `go vet` passed. |
| [build.txt](build.txt), [builds.json](builds.json) | Four standalone artifacts, hashes/sizes/formats, exact client source hashes, toolchain and identical repeat-build results. Linux amd64 has no ELF dynamic interpreter. |
| [live.json](live.json) | Copied binary run outside checkout with fresh home and PATH containing no commands; version and doctor output; exact input/stdout byte counts and SHA-256; separated stderr; duplex streaming before EOF; malformed ACP stdout empty; exit 23; five-second deadline; SIGINT/SIGTERM direct-child reaping. |
| [docs.txt](docs.txt) | Changed documentation links/anchors/fences/JSON validated. `git diff --check` also passed. |

The accepted stdout proof includes NULs, every byte value, CRLF framing and a
payload larger than a pipe buffer. Matching byte counts and hashes prove no banner,
newline or encoding mutation; stderr contains both parent and helper diagnostics.
Go process tests additionally cover descendants on cancellation and normal leader
exit, plus cancellation when stdin or stdout blocks. Same-group live descendants
are killed; terminated orphan zombies are left to OS/init reaping. The built
binary's direct children were completely reaped. This is transport-resource cleanup,
not Task cancellation or hostile-process containment.

The first local test invocation ran from the repository root instead of the Go
module; it was corrected. The first helper test invocation needed the Go test
flag separator; it was corrected before acceptance. The live signal observer was
corrected to enumerate child lists across all Go runtime threads. No failed probe
was counted as acceptance; retained files are the final validated pass.

## Reproduce

From the repository root with Go 1.27.1 and standard Linux build tools:

```bash
BLAINE_GO=/tmp/blaine-e0a-toolchain/go/bin/go \
GOCACHE=/tmp/blaine-go-cache GOPATH=/tmp/blaine-go-path \
BLAINE_COMMIT=7286bfd21dfd128af28e0a3d6735d665a9850843-dirty \
experiments/e0a-blaine-client/verify.sh
```

The retained artifacts were built before the coherent commit, so embedded commit
metadata honestly names the base commit plus `-dirty`. `builds.json` also pins each
client source file; the enclosing Git commit retains those exact sources. To build
a new snapshot, set its commit metadata accordingly. The build script uses:

```text
CGO_ENABLED=0 GOTOOLCHAIN=local GOPROXY=off GOOS=<os> GOARCH=<arch>
go build -trimpath -buildvcs=false \
  -ldflags '-buildid= -s -w -X blaine.local/client/internal/buildinfo.Version=0.1.0-e0a -X blaine.local/client/internal/buildinfo.Commit=<commit>' \
  -o <artifact> ./cmd/blaine
```

Artifacts stay in ignored `.local/e0a-artifacts/`; none are committed. Each target
was built twice to different output directories with identical hashes. The Go
race build uses the host C compiler; distributed builds disable CGO. Tests and
acceptance require no internet, Tailscale, IntelliJ, models or live Blaine host.

## Remaining work / E0.B handoff

E0.B retains the accepted scope: native Tailscale discovery/status/login and
supported prerequisite assistance. Establish WSL2/native Windows interop from real
observations; environment/kernel hints alone cannot certify it. Check native macOS
app and CLI availability separately. Resolve actual executable locations via the
platform boundary; do not guess fixed mount paths or start a WSL Tailscale daemon.
No new design blocker was discovered. Missing host Go was resolved with a temporary
verified toolchain, without packaging infrastructure or system install.

Later slices still own transport/handshake/framing rejection (E0.C), registration
(E0.D), supported IDE execution/config ownership (E0.E), and complete doctor/connect
acceptance (E0.F). No Windows-to-WSL launch encoding or signal claim follows from
Linux argv fixtures or cross-compilation. macOS signing/installer and real machine
runtime acceptance remain future release gates.

Concurrent-work conflict candidates: `docs/personal-agent-hub.md`,
`docs/roadmap/001-blaine-development-roadmap.md`, `docs/README.md`, and any parallel
creation of `client/`. Runtime, contracts, infrastructure and ADR 0022 are unchanged.
