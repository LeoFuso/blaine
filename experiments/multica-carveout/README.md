# Multica Codex probe

Disposable research experiment, not a production Blaine integration. It imports
Multica's public `server/pkg/agent` directly; no upstream source is copied here.

Upstream: `multica-ai/multica`, commit
`2df765a3c8f39789c9fb76316378bcffc20d22d9`, identified from the supplied
`multica-main.zip` and confirmed by the Go module proxy. The exact module pin is
`github.com/multica-ai/multica/server v0.0.0-20260918100236-2df765a3c8f3`.
Go 1.26.6 or newer is required by upstream.

Observed result (2026-09-18): built with Go 1.26.8 and executed against Codex
0.154.0. Fresh execution returned `PROBE_OK`; a separate invocation resumed the
same ID and recovered `CARVEOUT-7c91`. Both returned `completed`, token usage,
and confirmed process cleanup. A final narrow pass also observed active
cancellation, invalid-resume fallback, and forced child termination; see the
[research findings](../../docs/research/multica-carveout.md#final-live-execution-semantics-pass)
and [retained native observations](evidence/execution-semantics.json).

## Run

Prerequisites: an installed/authenticated Codex CLI, existing `auth.json` in
`$CODEX_HOME` or `~/.codex`, and network access for Go modules and Codex inference.
The probe uses the existing account's quota. It does not log in, install Codex,
or modify global Codex credentials/configuration.

```sh
cd experiments/multica-carveout
go build -o /tmp/blaine-codex-probe ./cmd/codex-probe
/tmp/blaine-codex-probe -model gpt-6-astra
```

`-codex /path/to/codex` overrides executable discovery. `-model` is optional;
without it, Codex chooses its default from the isolated configuration, not the
user's global config. The example model was configured on the tested host.

Stdout contains JSON lines: `setup`, `message`, and `result`. Stderr contains
Multica lifecycle logs. The final record retains the native `agent.Result`
fields: status, output, session ID, token usage, duration, error, and both resume
rejection flags. A missing usage map does not mean zero usage.

The first default prompt asks Codex to remember a marker and return `PROBE_OK`.
Copy `setup.state_dir` and `result.SessionID` into a second invocation:

```sh
/tmp/blaine-codex-probe -model gpt-6-astra \
  -state-dir /tmp/blaine-codex-probe-REPLACE \
  -resume RETURNED_SESSION_ID
```

The second default prompt asks for the marker without repeating it. Successful
continuity requires the same session ID **and** the remembered marker
`CARVEOUT-7c91`. Multica can fall back to a fresh thread after a resume error;
the probe prints the native result but exits unsuccessfully on an ID mismatch.
It does not add a fresh-session retry of its own.

Use `-timeout 30s` to bound execution; Ctrl-C/SIGTERM cancels the context through
Multica. Process cleanup can extend beyond the execution deadline. `-prompt`
allows another harmless text-only prompt. Do not run concurrent invocations in
one state directory.

## Isolation and retained state

Each fresh invocation creates a private temporary root with `work/` and
`codex-home/`. Codex receives a read-only sandbox, approval policy `never`,
disabled web search and selected tool/connector features, no inherited global
MCP configuration, and instructions to use no tools. The backend itself
auto-approves protocol approval requests: this probe is not an authorization
boundary for arbitrary workloads.

The existing `auth.json` is copied to the private home at mode 0600, never
symlinked, and removed when the invocation returns normally or handles a
signal. A hard kill can leave that private copy behind. Session files and the
private configuration are retained for the second invocation; removing the
printed temporary root discards the experiment and its resume state. Keep
private state out of the repository. There is no new Blaine task ledger.

Findings and measured limitations: [research note](../../docs/research/multica-carveout.md).
