# Multica carveout: standalone Codex probe

Research evidence, not an architectural decision. Recorded 2026-09-18
(America/Sao_Paulo). Scope: experience Multica's existing public abstraction
before considering extraction or a Blaine abstraction.

**Outcome: standalone execution and resume succeeded.** Two separate probe
processes used `server/pkg/agent` to launch the installed Codex CLI. The second
recovered the first conversation's marker under the same session ID. The
final narrow pass also exercised active cancellation, invalid resume, and child
process failure. It exposed gaps in the outcome/continuity contract while
confirming bounded cleanup in these cases. No extraction or architecture
changes follow from these findings.

## Source and environment

- Supplied source: `~/Downloads/multica-main.zip`; ZIP comment identifies commit
  `2df765a3c8f39789c9fb76316378bcffc20d22d9` in `multica-ai/multica`.
- The Go proxy resolved that hash to
  `github.com/multica-ai/multica/server v0.0.0-20260918100236-2df765a3c8f3`.
  `agent.go` and `codex.go` in the downloaded module compared byte-for-byte equal
  to the supplied source. No local `replace`, vendoring, or upstream edits.
- Linux amd64; upstream requires Go 1.26.6. Go 1.26.8 was downloaded from
  `go.dev`, SHA-256 checked, and unpacked under `/tmp`; no global Go installation.
- Existing executable: `/home/leofuso/.local/bin/codex`, `codex-cli 0.154.0`.
  Model: `gpt-6-astra`, matching the host's existing model setting.
- The public package was imported from the isolated
  [experiment module](../../experiments/multica-carveout/go.mod).
  [Probe and reproduction instructions](../../experiments/multica-carveout/README.md).

The source references below are pinned to this revision, not upstream `main`:

- [Public contracts and constructor (`agent.go`)][contracts]
- [Codex implementation (`codex.go`)][codex]
- [Codex contract/fixture tests (`codex_test.go`)][tests]
- [Process launch boundary (`launch.go`)][launch] and [Unix process ownership][process]
- [Codex environment preparation (`execenv/codex_home.go`)][home] and
  [sandbox policy (`execenv/codex_sandbox.go`)][sandbox]

The `execenv` files were read only to understand configuration/auth/session
preparation; the probe does not import them. Official [Codex App Server
documentation](https://learn.chatgpt.com/docs/app-server) was consulted for the
stdio thread/turn protocol; the pinned implementation and observed CLI behavior
are the evidence for this experiment.

## What ran

Preparation succeeded: `go mod tidy`, `go build`, and `go mod verify` (`all
modules verified`). The executable was then invoked twice:

```sh
/tmp/blaine-multica.orf0qL/codex-probe -model gpt-6-astra
/tmp/blaine-multica.orf0qL/codex-probe -model gpt-6-astra \
  -state-dir /tmp/blaine-codex-probe-3885137611 \
  -resume 01a0b75c-cf41-7131-9c48-2232d8add219
```

Both prompts prohibited tools, commands, file access, browsing, and delegation.
The first asked Codex to remember `CARVEOUT-7c91` and answer `PROBE_OK`. The
second asked for the previous marker **without including it again**.

| Observation | Fresh invocation | Separate resume invocation |
|---|---|---|
| Exit code / native Result.Status | `0` / `completed` | `0` / `completed` |
| Result.Output | `PROBE_OK` | `CARVEOUT-7c91` |
| Result.SessionID | `01a0b75c-cf41-7131-9c48-2232d8add219` | Same ID |
| Result.Error | Empty | Empty |
| Result.DurationMs | 3487 | 2839 |
| InputTokens (uncached) | 9405 | 250 |
| OutputTokens | 7 | 11 |
| CacheReadTokens | 0 | 9216 |
| CacheWriteTokens | 0 | 0 |
| CostUSDTicks | 0 (not reported) | 0 (not reported) |
| ResumeRejected / ResumeRejectedTransient | `false` / `false` | `false` / `false` |
| Streamed messages | `status:running`, text `PRO`, text `BE_OK` | `status:running`, text `CAR`, text `VEOUT-7c91` |
| Codex child PID | 28527 | 29004 |
| Cleanup log | `reaped:true`, exit status 0 | `reaped:true`, exit status 0 |

The durations are the backend's execution measurements, not total command wall
time. Native usage belongs to the execution; the zero cost field is not evidence
of free inference. The successful check combines returned IDs, streamed/final
content, and protocol lifecycle logs, rather than trusting `completed` alone.

Selected lifecycle evidence:

```text
fresh:  initialize_response -> thread_start_response -> turn/start
        -> turn/completed (completed) -> cleanup (reaped:true)
resume: initialize_response -> thread_resume_response -> "codex thread resumed"
        -> turn/start -> turn/completed (completed) -> cleanup (reaped:true)
```

Each invocation received exactly one native `agent.Result`. Both children were
absent from the process table afterward. The temporary `work/` remained empty;
no tool events were observed. SHA-256 comparisons before and after both runs
confirmed the global `auth.json` and `config.toml` were unchanged. The private
auth copy had been removed.

Raw stdout and lifecycle logs are retained locally under
`/tmp/blaine-multica.orf0qL/{fresh,resume}.{jsonl,stderr.jsonl}`; the measured
observations above are retained here because temporary files can disappear.
The private resume store is `/tmp/blaine-codex-probe-3885137611`. It retains Codex
session files and a probe-only config, not global credentials.

## What Multica code was exercised

The probe calls `agent.New("codex", Config{...})`, followed by
`Backend.Execute(ctx, prompt, ExecOptions{...})`, drains `Session.Messages` and
`Session.Result`, and prints the unmodified result fields. It introduces no
generic Harness interface.

The observed call paths use `codexBackend.Execute` / `executeOnce`, argument
normalization and the shared launch boundary, stdio JSON-RPC initialization,
`startOrResumeThread`, `turn/start`, notification/message handling, final output
selection, usage collection, and process cleanup. The logs distinguish
`thread/start` from `thread/resume`, record different PIDs, and confirm each
process exited. `CODEX_HOME` was supplied, so `ensureCodexMcpConfig` inspected the
private config with a nil MCP configuration; no MCP server was materialized.

This is behavioral evidence, not instrumented branch coverage. In particular,
the probe did not distinguish notification-based usage collection from the
rollout-log fallback. The final pass below adds cancellation, invalid-resume,
and child-failure evidence. Watchdog expiry, provider auth/quota/network errors,
active tools, MCP servers, and skills remain **not live-tested**. Relevant
upstream tests were inspected, not executed.

## Dependencies actually required

`go list -deps` reported only these non-standard-library imports, besides the
probe itself:

```text
github.com/multica-ai/multica/server/pkg/agent
github.com/multica-ai/multica/server/pkg/redact
github.com/multica-ai/multica/server/pkg/taskfailure
golang.org/x/sys/unix
```

`go version -m` on the built executable confirmed just two dependency modules:
the pinned Multica server module and `golang.org/x/sys v0.48.0`. Their checksums
are retained in the experiment's `go.sum`. The module download contains the
server source and its much larger `go.mod`; importing `pkg/agent` does not
compile or start that application's server, database, queue, scheduler, or UI.
The package compiles its other provider backends too, which explains the
`pkg/taskfailure` import even though `codex.go` itself only imports `pkg/redact`
outside the standard library.

Runtime prerequisites were the existing Codex executable, existing file-based
authentication, provider network access, and private writable Codex session
storage. No Multica frontend/backend/database or Blaine runtime was started.

## Final live execution-semantics pass

Three additional executions used the **unchanged** probe binary, Go source,
pinned Multica package, CLI version, model, and private-home configuration.
There were no dependency changes. The full native Messages and Results,
injection records, and selected lifecycle logs are retained in
[execution-semantics.json](../../experiments/multica-carveout/evidence/execution-semantics.json).

A temporary Python driver launched the probe and drained stdout/stderr. For
cancellation and child failure it requested the integers 1 through 2000, one
per line, and injected the signal on the first `MessageText("1")`. It verified
the child's executable, parent PID, and process group, and pinned its PID with
a Linux pidfd. No completion had been observed before either injection.

- Cancellation: SIGINT to the **probe**, which cancels the Go context passed to
  Multica. The driver did not signal the Codex child in this case.
- Invalid resume: the existing probe's default resume prompt with
  `-resume 00000000-0000-4000-8000-000000000000` and the cancellation case's private
  state directory. This UUID had no rollout in that isolated store.
- Child failure: SIGKILL through the verified Codex child's pidfd. The probe's
  context remained active, allowing Multica to observe and report child failure.
  This tested signal termination, not a simulated executable or a normal
  application `exit(N)`.

Every call returned a Session without an immediate `Execute` error. Both
channels drained and closed, and each Session delivered exactly one Result.
There was one Codex launch per case and no additional process attempt. No case
emitted `MessageError` or a terminal `MessageStatus`; the only status message
was `running`. Terminal findings came through Result and the logger.

| Exposed observation | Active cancellation | Invalid resume / automatic fallback | Active child failure |
|---|---|---|---|
| Session messages, in order | `running`, text `"1"`, text `"\n"` | `running` with **new** ID, text `"UNKNOWN"` | `running`, text `"1"` |
| Native Result.Status | `aborted` | `completed` | `failed` |
| Native Result.Error | `execution cancelled` | Empty | `codex process exited; codex stderr: ...` (full text below) |
| Native Result.Output | Empty | `UNKNOWN` | Empty |
| Native Result.SessionID | `01a0b765-cdc0-7391-93a7-d95b7fca3ff0` | `01a0b766-11bf-7992-8e62-6739b9ec1363` | `01a0b766-5c0f-7e22-890f-a06e6c820092` |
| ResumeRejected / ResumeRejectedTransient | `false` / `false` | **`false` / `false` despite rejection** | `false` / `false` |
| Usage | `null` | Input 9424; output 5; cache read/write 0; cost ticks 0 | `null` |
| Result.DurationMs | 2644 | 3163 | 3592 |
| Codex child PID | 30160 | 30603 | 31058 |
| Codex terminal protocol event | `turn/completed`, status `interrupted` | `turn/completed`, status `completed` | None observed |
| Cleanup log exit_status / wait_error | `exit status 0` / `null` | `exit status 0` / `null` | `signal: killed` / `signal: killed` |
| Cleanup log reaped | `true` | `true` | `true` |
| Probe process exit code | `1` (non-completed Result) | `1` (**probe's own ID mismatch check**) | `1` (non-completed Result) |

The probe's process exit code is not a Multica Result field or Codex exit code.
In particular, Multica considered the fallback execution completed; the existing
probe rejected its changed ID after printing the unmodified native Result.

For cancellation, Multica sent `turn/interrupt` and logged successful
interruption in **14ms**, within its default 2s interrupt budget.
The observed partial transcript was `"1\n"`, yet Result.Output was empty and
Usage was null. Graceful interruption therefore did not guarantee a final
output snapshot or token accounting in this early-generation sample.

For invalid resume, the concrete provider rejection appeared in `Config.Logger`
as a warning, followed by `thread/start` and a successful turn:

```text
msg: codex thread/resume failed; falling back to thread/start
error: thread/resume: no rollout found for thread id 00000000-0000-4000-8000-000000000000 (code=-32600)
```

That error was absent from Session.Messages and Result.Error, and both resume
rejection flags were false. The caller-supplied continuity notice preceded the
fallback prompt; the resulting answer was `UNKNOWN`. The rejection and fallback
occurred within one `Execute` call and one app-server process.

For child failure, the exact native Result.Error was:

```text
codex process exited; codex stderr: WARNING: proceeding, even though we could not create PATH aliases: Refusing to create helper binaries under temporary dir "/tmp" (codex_home: AbsolutePathBuf("/tmp/blaine-codex-probe-545253644/codex-home"))
```

The causal event was the injected SIGKILL. The appended startup warning did not
cause the failure: initialization and text generation had already succeeded.
Result.Error did not identify signal 9; the cleanup logger's `exit_status` and
`wait_error` exposed `signal: killed`. Partial text remained in Messages while
Result.Output and Usage were empty/null. Multica did not restart the child.

After all three cases, the recorded Codex PIDs were absent, private auth copies
were removed, and both temporary `work/` directories remained empty. Checksums
confirmed global auth/config, probe source, and the imported Codex backend were
unchanged. Original logs and the one-shot driver remain locally under
`/tmp/blaine-multica-semantics.VnTwib/`; the retained JSON preserves the relevant
evidence independently of that temporary directory.

### Can the caller distinguish the outcomes?

| Outcome | What the caller can establish | Limit of the public contract |
|---|---|---|
| Successful continuation of the requested session | Compare the requested ID with Result.SessionID and require a completed turn. The primary pass additionally proved memory continuity; logs confirmed `thread/resume`. | `completed` alone says nothing about which session continued. `resume_matched` is a probe computation, not a Multica field. |
| Resume rejection | In the live invalid-ID case, the logger records the exact RPC refusal and reason. | Neither rejection flag, Result.Error, nor a Session error event reported this rejection. `ResumeRejected=false` cannot be read as proof of successful resume. |
| Automatic fallback to a fresh session | Retain the requested ID and compare it with the new `running`/Result ID; correlate the fallback warning. | No explicit fallback field or caller veto exists in this path. Detection does not prevent the fresh turn or its usage. |
| Cancellation | The caller knows it cancelled the context; this run returned `aborted` plus `execution cancelled`, corroborated by an interrupted turn in logs. | The status was not `cancelled`; `aborted` also covers other abort paths. Status alone is not an unambiguous cancellation-reason enum. |
| Execution failure | Child death returned `failed` and a process-exited error while the caller's context was active. | No structured child exit code/signal is in Result. The exact signal and reap confirmation were logger records; provider-specific failure causes remain untested. |

The caller can distinguish these measured cases by combining its own invocation
and cancellation inputs, native results, and lifecycle logs. **Session/Result
alone do not expose all the distinctions.** These are observations relevant to
a future Restate boundary, not a design for that boundary. A returned session ID
after interruption/failure is retained evidence, not proof that it can be resumed;
no further resume or retry tests were run.

## Coupling discovered

**No coupling prevented standalone use.** The public package built and worked
without `server/internal/daemon`, so no extraction boundary was needed to meet
this objective. Several policy assumptions remain relevant to a later review:

1. **Approval policy is embedded.** `handleServerRequest` auto-accepts command,
   patch, permission, and MCP elicitation requests. The public API offers no
   caller approval callback. The probe constrains Codex through its private
   read-only/never-approve configuration and a harmless prompt; it is not proof
   that the upstream backend preserves Blaine authorization for arbitrary Work.
2. **Resume is allowed to become fresh execution.**
   `startOrResumeThread` falls back to `thread/start` on non-transport errors or
   a missing ID. The eventual Result may be `completed` with a new ID and
   `ResumeRejected=false` (now observed live). `ResumeExpected` and
   `ResumeContinuityNotice` disclose lost context to the model but do not forbid
   fallback. The probe checks the
   returned ID; that detects a fallback after execution, not before it happens.
   `TestCodexStartOrResumeThreadFallsBackOnResumeError` documents this path.
3. **Some recovery is inside the backend.** `Execute` can make a second attempt
   after a proven-clean initialize timeout or model-catalog startup failure;
   the latter can discard a resume pointer. This is bounded process recovery,
   but a future runtime caller must understand the extra attempt and continuity
   implications. The probe adds no retries and puts one parent deadline around
   the whole call.
4. **Environment and session files matter.** A session ID alone is insufficient:
   the CLI needs accessible persisted Codex history. `Config.Env` overlays the
   inherited environment, not a full environment allowlist. Supplying a
   `CODEX_HOME` permits the backend to rewrite its MCP config. The daemon also
   symlinks shared authentication, copies config, arranges session stores and
   skills, and chooses sandbox policy. None of that preparation was required
   here: the probe uses a private auth copy and retains one isolated CLI home.
5. **Contract shape carries product history.** `Config` has task/daemon metadata;
   `ExecOptions` mixes portable and provider/product-specific fields. For Codex,
   `SystemPrompt` is deliberately not forwarded (Multica expects an on-disk
   `AGENTS.md`); `IdleWatchdogTimeout` belongs to the daemon. `Session` describes
   transcript consumption as optional, but the outer Codex wrapper forwards
   messages with blocking sends. A non-draining caller can fill the channel and
   stall it. The probe continuously drains both channels.
6. **Outcome and accounting are incomplete at interruption boundaries.** Both
   interrupted executions streamed text but returned empty output and null
   usage. Process exit details and the invalid-resume cause were exposed by the
   logger rather than structured Result fields. Native statuses also need the
   caller's context to distinguish cancellation from other aborts.

## Classification after the final pass

Classes express research judgments: HARVEST = likely reusable execution glue;
ADAPT = useful with coupling; REJECT = responsibility owned elsewhere;
INVESTIGATE = insufficient evidence. They do not authorize extraction. Result,
cancellation, and token accounting move from HARVEST to ADAPT because the live
interruption/fallback cases exposed contract gaps. Their execution mechanisms
remain useful harvesting candidates; this changes the assessment, not the code.

| Concept | Class | Evidence and implication |
|---|---|---|
| `Backend` / `New("codex", Config)` | HARVEST | Public factory and `Execute` worked independently in the primary pair and all three final cases. No daemon object required. [Contracts][contracts] |
| `Config` and provider registry | ADAPT | Executable/env/logger are useful; task/runtime/daemon metadata and one package containing every backend reflect Multica's host. [Contracts][contracts], [launch][launch] |
| `ExecOptions` | ADAPT | Cwd/model/resume worked; the deadline was configured but not triggered. Other fields are provider-specific, ignored by Codex, or consumed by the daemon. [Contracts][contracts], [Codex][codex] |
| `Session` / streaming | ADAPT | Streaming preserved partial text on cancellation/child death when Result.Output was empty. All three cases closed channels with one Result, without error/terminal-status messages. Blocking forwarding and nil optional callbacks remain contract caveats. [Contracts][contracts], [Codex][codex] |
| `Result` | ADAPT (was HARVEST) | Live cancellation used `aborted`; rejection/fallback returned `completed` with false rejection flags; child signal/reap details were logger-only. Empty output and null usage can coexist with streamed text. Useful execution findings, but not a complete typed outcome or Blaine Task completion contract. [Contracts][contracts] |
| Session IDs and persisted CLI history | ADAPT | Same ID and remembered content survived process replacement when reusing the isolated home. Multica's per-issue/chat session storage ownership is product-specific. [Codex][codex], [home][home] |
| Resume rejection / fallback | ADAPT | Invalid-ID rejection was observed live as RPC -32600 in logs, followed by a new ID and completed execution; both rejection flags stayed false. ID comparison establishes fallback, not its precise cause. Overflow/transient cases remain source-only. [Codex][codex], [tests][tests] |
| Process launch, ownership and cleanup | HARVEST | Normal, cancelled, and SIGKILL cases were reaped with no surviving observed child. Active child death returned one failed Result without restart. Tools/descendants and other platforms remain untested; exit/reap evidence is logger-only. [Launch][launch], [Unix helpers][process] |
| Cancellation | ADAPT (was HARVEST) | Active cancellation reached `turn/interrupt` and an interrupted completion in 14ms; child exit was 0, Result was `aborted` / `execution cancelled`. No final output/usage was returned in this sample. Cancellation cause needs caller context, not just status. [Codex][codex], [tests][tests] |
| Timeouts, watchdogs and local retry | ADAPT | Codex has handshake, first-progress, semantic-inactivity and interrupt budgets plus internal startup retry. Defaults are 30s initialize, 60s thread setup, 60s first progress, 10m inactivity, 2s interrupt. Keep process liveness distinct from durable scheduling/retry policy. Source-only failure-path evidence. [Codex][codex] |
| Token accounting | ADAPT (was HARVEST) | Successful/fallback turns returned model-keyed counts, but cancellation and child death returned null usage despite text generation. Normalization is useful; these observations do not support complete usage accounting across interruption. [Codex][codex], [tests][tests] |
| Provider-specific errors | ADAPT | The invalid-resume RPC cause survived only in logs. Child failure returned a generic error plus incidental startup stderr; exact signal was also logger-only. Other provider failure families and Multica's broader service taxonomy remain source evidence. [Codex][codex], [failure taxonomy][failures] |
| Codex app-server protocol | HARVEST | Initialize, thread start/resume, turn start/completion, normalized streaming, and active `turn/interrupt` worked against CLI 0.154.0. Resume policy/reporting still needs adaptation as assessed separately. [Codex][codex], [tests][tests] |
| MCP configuration | ADAPT | JSON-to-TOML materialization, secret-safe file permissions and managed configuration precedence are useful, but mutate an assumed private home and include Multica selectors. Only the nil-config inspection path ran. [Codex][codex], [tests][tests] |
| Environment/auth materialization | ADAPT | A caller-supplied private home sufficed. Daemon auth symlinks, session-store ownership and platform sandbox policy need separate consideration; do not import the whole preparation layer. [Home][home], [sandbox policy][sandbox] |
| Skills / runtime brief | INVESTIGATE | Codex relies on disk context instead of `SystemPrompt`; no skill was materialized or exercised. That is insufficient evidence to select a harvesting boundary. [Contracts][contracts], [home][home] |
| Multica UI, issue tracker, backend, task queue, scheduler, durable runtime | REJECT | Not required by the measured import/runtime path; outside the requested scope. Human coordination belongs to YouTrack; durable execution remains intended for Restate. |
| Upstream redistribution/harvesting terms | INVESTIGATE | The supplied LICENSE combines Apache-2.0 text with additional Part I conditions. Review those terms before any future extraction/distribution; this probe only imports the pinned dependency. [License][license] |

## Boundary of the result

This proves the public-package execution/resume path and records one live sample
each of active cancellation, invalid-ID fallback, and forced child termination
on one installed CLI/account/platform. It does not validate all cancellation
races, failed/slow interrupt handling, failure recovery, post-failure resume,
cross-machine resume, keyring-only authentication, MCP/skills, active tools,
watchdog expiry, long-running workloads, or Blaine lifecycle enforcement.
Upstream test names are source pointers, not claims of test execution here.

The final validation pass is complete. No further probe executions, extraction,
or refactoring were performed after these three cases.

Restate integration, ContextResolver, MIRIX, Graphify, a Blaine Harness contract,
source extraction and refactoring remain outside this experiment. The next
action is review of these findings by the user.

[contracts]: https://github.com/multica-ai/multica/blob/2df765a3c8f39789c9fb76316378bcffc20d22d9/server/pkg/agent/agent.go
[codex]: https://github.com/multica-ai/multica/blob/2df765a3c8f39789c9fb76316378bcffc20d22d9/server/pkg/agent/codex.go
[tests]: https://github.com/multica-ai/multica/blob/2df765a3c8f39789c9fb76316378bcffc20d22d9/server/pkg/agent/codex_test.go
[launch]: https://github.com/multica-ai/multica/blob/2df765a3c8f39789c9fb76316378bcffc20d22d9/server/pkg/agent/launch.go
[process]: https://github.com/multica-ai/multica/blob/2df765a3c8f39789c9fb76316378bcffc20d22d9/server/pkg/agent/proc_other.go
[home]: https://github.com/multica-ai/multica/blob/2df765a3c8f39789c9fb76316378bcffc20d22d9/server/internal/daemon/execenv/codex_home.go
[sandbox]: https://github.com/multica-ai/multica/blob/2df765a3c8f39789c9fb76316378bcffc20d22d9/server/internal/daemon/execenv/codex_sandbox.go
[failures]: https://github.com/multica-ai/multica/blob/2df765a3c8f39789c9fb76316378bcffc20d22d9/server/pkg/taskfailure/failure.go
[license]: https://github.com/multica-ai/multica/blob/2df765a3c8f39789c9fb76316378bcffc20d22d9/LICENSE
