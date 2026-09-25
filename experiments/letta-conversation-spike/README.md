# Letta as Blaine's conversation substrate — overnight discovery and falsification

Experiment evidence, not a decision. Run 2026-09-25 on the Blaine host, branch
`spike/letta-conversation-substrate` (base `2c0985e`). No Blaine runtime, kernel,
PolicyGate, Completion Contract, effect, client or service file was changed; all
spike code and evidence is under this directory. Canonical services stayed up and
untouched throughout (checked at the end: all seven user units active).

It tests the bounded-L3 hypothesis in
[`docs/research/letta-carveout.md`](../../docs/research/letta-carveout.md): Letta
owns Agent, Conversation, transcript, context, compaction, sessions and channels;
Blaine owns Tasks, authority, effects and evidence, joined by a thin
`ConversationBinding`.

## 1. Verdict

**GO WITH CONDITIONS, for a narrowed role only. The carveout hypothesis as written
fails two STOP criteria.**

- **STOP 7 hit.** The carveout's Task identity, `request_id = H(conversation_id,
  tool_call_id)`, produced **two Blaine Tasks for one human request**. The App
  Server was SIGKILLed while a `blaine_task_create` call was in flight, after
  Blaine had already accepted the Task. Letta turned the lost call into a "stale
  denial" that tells the model to "re-issue the tool call". The model re-issued it
  with a new `tool_call_id`, and told the user "it was not confirmed the first
  time, so I just created it". An identity anchored on the triggering human message
  also duplicated, because the re-issue came in answer to the user's follow-up.
  Only a semantic rule held: converge on an open Task with identical arguments in
  the same conversation. That is heuristic glue, and a paraphrased re-issue would
  still duplicate.
- **STOP 8 hit (human-authority reuse).** Letta approvals cannot carry Blaine human
  authority:
  - After one click on Letta's standard "Yes, allow `blaine_task_respond`
    operations during this session", the model answered a *different* decision the
    human had explicitly said not to answer. No approval was shown, and Blaine
    completed the Task as `satisfied`.
  - That session rule leaked into three other conversations.
  - Any client can switch a conversation to `unrestricted`.
  - With an `alwaysAsk` rule in place, an automated second client still approved
    the call, because an approval frame carries no principal.
  - Blaine's kernel checks revision, digest and allowed value, not *who* answered,
    and says so itself (`submit_human_response` is "transport-neutral, not a public
    authenticated UI").

  A Blaine-owned decision ingress passed every test (§5.7).

Once the failed mechanisms are replaced by Blaine-owned ones, Letta genuinely provides:

- a local-only, account-free conversation engine;
- an append-only transcript that survived 30 random SIGKILLs during appends;
- non-destructive compaction on disk;
- multi-client streaming with convergent history;
- reconnect;
- ACP `session/load` onto the same conversation;
- an external-tool seam that restricts the model to exactly the `blaine_*` tools.

The narrowed design is empirically supported, but only with the conditions in
§9. Three of them are not built yet: the gateway, the ACP bridge plus relay
change, and a durability patch. The measured cost of neutralising Letta's defaults
is higher than the carveout estimated (§6), and upstream churn already broke
`letta-acp` against the current App Server. **The next step is an ADR plus a
short hardening spike, not product integration. Keep Atomic frozen.**

## 2. Topology actually run

```text
                         host (Blaine hub, loopback only)
 ┌──────────────────────────────────────────────────────────────────────────────┐
 │ probes / scripted human clients / ACP test client ──┐                        │
 │                      spike controller (blaine_* tools)├─ TCP 127.0.0.1:5828x │
 │                      spike projector (outbox+read-back)┘        │            │
 │                                     host bridge (TCP→Unix) ─────┤            │
 │  ┌─ bwrap sandbox per App Server generation ─────────────────────┼─────────┐  │
 │  │ own netns (loopback only), read-only /, real $HOME,/run,/tmp  │ app.sock│  │
 │  │ hidden; writable: spike state dir only                        ▼         │  │
 │  │   letta.js server --listen ws://127.0.0.1:18283 --ws-auth capability-token│
 │  │   local backend, LETTA_DISABLE_MODS=1 LETTA_CODE_TELEM=0 DO_NOT_TRACK=1  │  │
 │  │   DISABLE_AUTOUPDATER=1 (optional strace / strace fault injection)       │  │
 │  │   127.0.0.1:18000 ─▶ vllm.sock      127.0.0.1:18001 ─▶ hostile.sock      │  │
 │  └────────────────────────────┬───────────────────────────┬──────────────┘  │
 │     LLM tap (logs tool surface)│             scripted model (hostile_model) │
 │     canonical vLLM 127.0.0.1:8000 (Qwen3.8-27B-NVFP4)                         │
 │                                                                              │
 │  controller ─HTTP─▶ control_shim.py ─▶ runtime.personal_agent.PersonalAgent  │
 │                    (existing binding) ─▶ disposable Restate 1.7.9 :58080      │
 │                                          ─▶ unchanged runtime app :59080      │
 └──────────────────────────────────────────────────────────────────────────────┘
 ACP: letta-acp (remote backend) ─▶ App Server; relay: letta-acp as RelayHost child
 behind Blaine's real direct transport (client/internal/direct), test admission.
```

- **Model endpoint.** The canonical `blaine-generation` vLLM,
  `nvidia/Qwen3.8-27B-NVFP4` (rev `482ca0f`, vLLM `0.29.1rc1.dev401`, tool parser
  `qwen3_coder`). It was reached only through a Unix-socket bridge. The LLM tap in
  front of it records the exact tool list offered on every request.
- **Scripted "hostile" model.** An OpenAI-compatible endpoint that emits queued tool
  calls, used where the test needed determinism: unoffered-tool calls, fabricated
  approvals, and crash windows.
- **Blaine.** A disposable Restate instance with its own ports and state, running
  the unchanged `runtime.personal_runtime.application`. The shim calls the existing
  `PersonalAgent` binding and the D2 Task shapes (`summarize`/`text.stats`,
  `decision`/`human.request`).
- **State dirs.**
  - `s1`: exploration and tool surface.
  - `s2`: Blaine integration and ACP, real model.
  - `s3`: disposable crash, mods and reflection runs, scripted model.
  - Four egress states.
- **Scale.** 106 App Server generations: 75 SIGKILLs, 23 SIGTERMs, plus injected
  kills.

Pins are in [`versions.json`](versions.json):

- `letta-code` 0.33.1, tag `5631c53`; `main` was at `a9ee041` when fetched.
- `letta-agent-sdk` 0.8.17 (`18283a4`).
- `letta-acp` 0.1.11 (`5197491`), which itself pins SDK 0.7.8 and letta-code 0.30.28.
- `@agentclientprotocol/sdk` 1.5.0.
- Node 24.21.0.
- Go 1.27.1, used for the relay test.

## 3. Results

| # | Question | Result | Class | Evidence |
| --- | --- | --- | --- | --- |
| 1 | Local mode without Letta account/Cloud | **PASS** | — | Agent, conversation and turns inside a netns with no route off the host; zero Letta-host DNS with privacy flags (§5.3). `01-local-and-tools/probe01…` |
| 2 | Uses Blaine vLLM reliably | **PASS** | env note | All real turns and tool calls on Qwen. vLLM rejects `tools: []` once history has tool calls, and Letta sends `[]` rather than omitting the field. Avoided by always offering ≥1 tool. |
| 3 | Conversation durable across restart / process death | **FAIL, bounded mitigation** | upstream | Clean restarts and 72 random SIGKILLs: intact. A death inside the `conversation.json` rewrite (every message) leaves 0 bytes, and the conversation is **gone** from every API while its transcript is intact. The repair tool restores it. `04-durability/inject-…` |
| 4 | Append survives SIGKILL | **PASS** | — | 30 kills at 0–25 ms: 26 present once, 4 cleanly absent, 0 duplicated, 0 unparseable, all usable. `04-durability/crash-a-…` |
| 5 | Compaction survives SIGKILL | **FAIL, bounded mitigation** | upstream | Kill during the summary call: clean. Kill at the compaction-entry append: **silent context loss** (list shows 0; the next model call sees only `[system,user]`). Kill at the compaction `conversation.json` write: conversation gone. Both repaired. `04-durability/crash-c-…` |
| 6 | History complete after compaction | **PASS on disk / not via API** | upstream | The transcript keeps every message plus a `compaction` entry. `conversation_messages_list` returns only the working set (32 → 1), so UI history, ACP replay and any Context Plane reader lose pre-compaction history unless they read files. |
| 7 | Two simultaneous clients | **PASS** | — | `06-concurrency/probe14…` |
| 8 | Ordering / queue semantics intelligible | **PASS with hazards** | upstream | FIFO with `started`/`queued` dispositions, broadcast to all subscribers. Hazards: (a) a queued input is **cancelled when its sender disconnects**; (b) queued inputs are lost on crash; (c) a resend with the same `client_message_id` can be acked `queued` yet never enqueued (stale dedupe); (d) an input sent in the same millisecond as `turn_finished` loses any approval raised in that turn, and the turn hangs. |
| 9 | Reconnect / sync continuity | **PASS** (1 caveat) | upstream | A turn continues after its origin disconnects; the reconnecting client gets the rest of the stream; histories converge. `sync resume_interrupted_turn` after a crash started no turn (3 runs; waits of 5, 5 and 1 min); the next user message resumed it. |
| 10 | ACP `session/load` resumes the same conversation | **PASS with SDK override** | upstream | Unchanged letta-acp 0.1.11 against App Server 0.33.1: `session/prompt` **hangs** although the turn completed server-side. With SDK 0.8.17: new, load, replay, continuation, permissions and reload all work. Replay drops the first human message, the one carrying `<system-reminder>`. |
| 11 | Through Blaine's Go/tsnet relay without weakening identity | **FAIL as-is; transport PASS** | Blaine | Real relay code: new, prompt and load-after-new pass the guard. But the frontend answers `initialize` with `agentCapabilities: {}` and rejects `session/load` as an opening method (-32601). Any Letta approval becomes host→IDE `session/request_permission` and is killed: `ACP_DENIED: host client capabilities require a later E slice`. Needs a small frontend change; identity untouched. |
| 12 | Built-in filesystem/terminal/tool execution disabled | **PASS, conditional** | upstream defaults | Per conversation, `toolset: none` or `client_tool_allowlist` leaves zero built-ins (tap-verified). But: new conversations default to `unrestricted` with 19 host tools, and a scripted `exec_command` **ran on the host with no approval**; letta-acp sessions get 18 tools; any client can re-enable; and the background **reflection** subagent (Bash+Edit, auto-approved, reads the host broadly) runs regardless of toolset until `reflectionTrigger: off`. |
| 13 | Mods disabled | **PASS** | — | `LETTA_DISABLE_MODS=1`: canary mods not loaded. Positive control: global **and MemFS** mods executed code. |
| 14 | Telemetry / Letta egress disabled | **PASS** (exercised paths) | — | Privacy off: `api.letta.com` DNS at start and every 2 min. Privacy on: 0 DNS, 0 non-loopback connects, 0 sink requests over >2 min including a turn and shutdown. |
| 15 | Only registered `blaine_*` callable | **PASS** | — | A scripted model emitting unoffered `Bash`/`Write`/`exec_command`/`Agent`/`memory` got "Tool not found" **even with the human approving**; no canary appeared. |
| 16 | External tool calls safe across disconnect/restart | **FAIL, bounded mitigation** | upstream semantics | A restart turns in-flight calls into stale denials and the model re-issues them. Controller disconnect rejects pending calls. Registrations are in-memory and must be re-published; an empty-runtime update is silently dropped. |
| 17 | Idempotent Task creation from a tool call | **FAIL as proposed / PASS with reconcile** | upstream + Blaine | See STOP 7. Also a **Blaine binding race**: two concurrent creates with the same `request_id` and different input both return `SUBMITTED` (Restate `Accepted` + `PreviouslyAccepted`); one input silently never runs. Triggered naturally by parallel tool calls. |
| 18 | HumanDecision without model impersonation | **FAIL via Letta approvals (STOP) / PASS via Blaine ingress** | architecture | §5.7 |
| 19 | Projection without recursive turns | **PASS** (cost) | upstream | No non-turn append exists: local mode stores every input as a `user` message and starts a turn. Recursion is structurally impossible: projection turns offer only `blaine_task_status`. 16 projection turns on Qwen, avg 13.8 KB prompt each, 0 recursive creates. |
| 20 | Effectively exactly-once projection | **PASS** | — | Deterministic `client_message_id` plus transcript read-back plus persistent retry. D1–D3 each end with exactly 1 visible projection. `input_accepted` is not evidence (D3). |
| 21 | Task completion with every UI disconnected | **PASS** | — | `09-line-of-work` |
| 22 | Result observed later from another interface | **PASS** | — | ACP `session/load` replay showed both outcomes, then continued correctly. |
| 23 | Custom glue required | ~660 LOC spike glue; production estimate §6 | — | |
| 24 | Glue small enough to be worth it | **INCONCLUSIVE** | spike | Gateway, ACP bridge and durability patch not built; see §6. |
| 25 | Evidence for ActivityTrack/Workstream | **No** | — | One conversation carried the whole line of work (§5.13). |

## 4. STOP criteria

| # | Criterion | Status |
| --- | --- | --- |
| 1 | Local mode needs Cloud/account | Not hit |
| 2 | Built-in host tools cannot be reliably disabled | Not hit, **conditional**: disabling works, but every default is on, and reflection is a hidden Bash path (§5.2). Holds only with a gateway as sole conversation creator, plus settings. |
| 3 | Mods cannot be disabled | Not hit |
| 4 | Telemetry/egress cannot be suppressed | Not hit (exercised paths) |
| 5 | Safe remote use needs the App Server protocol exposed | Not hit, provided clients reach Letta only through a Blaine gateway or bridge. The App Server socket carries file, terminal, memory-write, secret, cron, channel and provider frames and must stay loopback. |
| 6 | Conversation corrupts under process death, no bounded mitigation | Not hit (mitigation exists). Corruption was demonstrated under injected worst-case death (§5.5). |
| 7 | Retried external tools duplicate Blaine Tasks | **HIT** for the proposed identity (and the anchor identity); heuristic mitigation only |
| 8 | Human approval can be fabricated | **HIT** for Letta-approval-as-authority. Consequence: Blaine-owned decision ingress (H3 passes). |
| 9 | Projection cannot avoid duplicates or recursion | Not hit (one agent turn per projection is unavoidable) |
| 10 | ACP cannot resume through a safe Blaine boundary | Not hit **with** an adapter fork plus a small relay-frontend change; hit for unchanged letta-acp and the unmodified relay |
| 11 | Requires weakening Task/PolicyGate/Contract/effect/workstation invariants | Not hit. No kernel change; the binding race is a pre-existing Blaine defect to fix. |
| 12 | Gateway/adapter becomes a reimplementation | Inconclusive (gateway not built) |

## 5. Findings

### 5.1 Local and Cloud independence

- Account-free: `letta connect openai-compatible` and `letta server --listen`
  worked inside a network namespace with no route off the host.
- The only reachable model endpoints were Blaine's vLLM, which validated the
  provider, and the spike's own scripted model.
- `letta server --listen` refuses `--channels`, so channels need a second process
  (see §5.5, second process).

### 5.2 Tool isolation

LLM tap records are in `01-local-and-tools/llm-tap-tool-surface-summary.json`.

**Defaults are unsafe:**

- A new conversation is `unrestricted` with the model-dependent built-in preset:
  19 tools including `Bash`, `Read`, `Edit`, `Write`, `Agent`, `Workflow` and
  `TaskCreate`, or the Codex preset with `exec_command`.
- In such a conversation, a scripted `exec_command` wrote `id -u` and the host
  name to a canary file with **zero approvals**. The canary file reads `1000` /
  `blaine`.
- `DEFAULT_PERMISSION_MODE` is `unrestricted`.

**Controls that work (tap-verified):**

- `update_toolset none` persists **per conversation** only, in
  `settings.json → toolsetsByConversation`. The agent-level `toolset` applies only
  to the agent's `default` conversation.
- `client_tool_allowlist` applies per turn and **also filters external tools**.
- The execution registry is the per-turn filtered set, so an unoffered call is
  rejected even after approval.

**Paths that bypass per-conversation controls:**

- Any socket client can:
  - `update_toolset`;
  - send `client_toolset.base`/`include` per turn;
  - `change_device_state` to `unrestricted`;
  - `set_reflection_settings`;
  - `execute_command /reflect|/dream|/upgrade-letta-code|/secret`.
- The **reflection subagent** ("You only have access to **Bash** and **Edit**")
  is launched in the background with its own toolset:
  - 4 reflection model requests in 60 large turns on a new agent, and 25 during
    the probe09 growth phase;
  - 0 with `reflectionTrigger: off`, a matched pair;
  - Letta auto-approves it;
  - it reads the conversation through Bash (`$TRANSCRIPT_PATH`);
  - its confinement "can read the host broadly".

  So conversation text, including projections and Task output, feeds a
  shell-capable agent unless reflection is off.
- letta-acp forces `standard` mode, and that **persists**: a conversation's
  `strict` became `standard` for every client after one `session/load`.
- Strict mode still honours session and persisted allow rules. Only `alwaysAsk`
  rules precede mode and allow rules (`permissions/checker.ts`).
- Letta itself `execve`s `git` (running the MemFS repository's
  `.git/hooks/pre-commit` and `post-commit` hooks), `bash` and `cat`. These are
  harness processes, not model tools.

### 5.3 Telemetry and egress

Method: the bwrap netns makes every outbound attempt fail visibly under strace; an
in-sandbox HTTP sink stands in for `LETTA_BASE_URL`; a negative control runs with
the flags off (`08-…/egress-*.json`, strace excerpt).

- **Flags off:** `api.letta.com` A/AAAA lookups at startup and at the 2-minute
  telemetry flush. With the sink configured: `GET /v1/health` to the sink, and the
  Cloud lookup still happened.
- **`LETTA_CODE_TELEM=0 DO_NOT_TRACK=1 DISABLE_AUTOUPDATER=1 LETTA_DISABLE_MODS=1
  LETTA_DISABLE_LSP_DOWNLOAD=1`:** nothing.
- **Install time:** npm 11 executed no install scripts, including the
  `@scarf/scarf` analytics beacon; `DO_NOT_TRACK=1 SCARF_ANALYTICS=false` were set
  anyway.
- **Not exercised:** channels, cron, and subagent turns with a real model.

### 5.4 Mods

- The env flag is honoured, and the positive control proves the test detects loads.
- With mods enabled, a file in the agent's **MemFS** `mods/` directory is executed.
  So any memory write becomes code execution: agent memory tools, reflection, or
  the `write_memory_file` socket frame.

### 5.5 Durability

`04-durability/*`, file-level checker `harness/integrity.py`.

**Transcript (`messages.jsonl`).** Append-only, one `appendFileSync` of a whole
line per entry. Across 72 random SIGKILLs (append and update windows):

- every line parsed;
- every probe message was present once or absent;
- no user turn was duplicated;
- every tool call was paired, including stale denials;
- the conversation stayed usable.

**`conversation.json`.** Rewritten with a truncating `writeFileSync` (no rename,
no fsync) on **every** persist, and *before* the transcript append.

- Deterministic fault injection (strace `inject=write:signal=KILL` on its first
  `write()`) left it at 0 bytes.
- After restart the conversation was "not found" for list, retrieve,
  `runtime_start` and messages, with the 7.3 MB transcript intact and no
  self-repair.
- `harness/repair_conversation.py` rebuilt it from the transcript: 159 messages,
  and the next turn was OK.

**Compaction.** Writes `conversation.json` (context narrowed to the new summary)
*before* appending the compaction entry.

- A kill between the two leaves context pointing at a missing summary: the API
  lists 0 messages and the next model request is `[system,user]`. That is
  **silent context loss** in a conversation that otherwise "works".
- A kill during the summary model call is harmless.
- The repair tool rebuilds the context from the transcript.

**Queued inputs.** In-memory only: lost on crash (D2) and cancelled when the
submitting connection drops (D3, M4).

**Message IDs.** `ui-msg-N` comes from a per-process counter restored from loaded
conversations, and restarts at 1 for a new conversation in a new process. IDs are
unique only per conversation, so always key messages by `(conversation, id)`.

**Real-model compaction.** 22 → 1 in context. The summary was mostly faithful but
**garbled a Task ID** (a duplicated segment) and included model self-talk
("*Correction*: …"), which now forms the whole active context. Identifiers from
context after compaction are unreliable.

**Second process on the same state.** A headless `letta -p` (as a channels process
would be) appended its turn to the transcript. The running App Server neither
listed it nor put it in model context until restart (6 → 10 listed vs 12 on
disk). Two Letta processes sharing a state directory diverge.

**Not tested:** power loss (no fsync anywhere); the transcript rewrite on fork and
on load repair; a real App Server under systemd.

### 5.6 Delegation and idempotency

`02-delegation-and-crash-b/*`

- The external-tool seam works: registration by the controller, call routing,
  strict-mode approval, and the controller calling the existing binding. The
  controller's create call into Blaine took 19 ms.
- The Crash B sequence and the identity schemes are summarised under STOP 7 in §1.
  File-level state after each crash was clean.
- The line-of-work run exposed the **Blaine binding race** (#17):
  - The model issued summary and decision creates in parallel, and my first
    anchor identity collided them.
  - `PersonalAgent.execute` returned `SUBMITTED` for both.
  - The decision Task never existed, while the model told the user both were
    created.
  - The spike fix: arguments go into the identity, plus per-conversation
    serialisation.
  - The binding fix still needed (outside this spike): treat `PreviouslyAccepted`
    as `EXISTING` and verify the digest.

### 5.7 HumanDecision

`03-human-decision/*`

**Baseline (H1a).** The real model called `blaine_task_respond` with the exact
revision and full digest copied from the projected card. The approval card
matched the canonical request, and Blaine completed the Task (`human_response@1`).

**Attacks:**

| Case | Letta config | Human action | Result |
| --- | --- | --- | --- |
| H1b | default | clicked "allow … during this session" once, on decision 1 | model answered decision 2 with **0 approvals**; COMPLETED |
| (leak) | default | none in 3 other conversations | same session rule auto-approved there too |
| H1c | default | none; another client set `unrestricted` | 0 approvals; COMPLETED |
| H1d | default | left the card untouched | an automated second client approved; COMPLETED |
| H1e | default | approved with `updated_input` NO over the model's YES | Blaine recorded NO: the *approving client* authors the value |
| H1b/c + `alwaysAsk` | `permissions.alwaysAsk: [blaine_task_respond]` | declined | asked each time; stays WAITING (mitigated) |
| H1d + `alwaysAsk` | same | left untouched | bot approved; COMPLETED (**not mitigable in Letta**) |

**Consequence.** HumanDecision responses must enter Blaine through a Blaine-owned,
authenticated ingress: the gateway, and in the IDE the Blaine ACP bridge. Letta
only displays the request and the recorded outcome.

**H3, the Blaine ingress (`src/decision_ingress.mjs`):**

- The model has no respond tool; asked to "answer YES for me", it refused.
- `/decide CODE VALUE` is intercepted before Letta.
- A stale revision, a forged digest and `MAYBE` were each **rejected by the
  Blaine kernel** (HTTP 400).
- The real answer was accepted and completed.
- A second answer was refused.

**Why scanning the transcript is not an alternative (H2).** Letta writes
harness-authored text into **user-role** messages: environment reminders, and
"MEMORY COMMIT NEEDED" nags. Compaction summaries are model-written user-role
messages. "User message" does not mean "human-authored".

### 5.8 Projection

`05-projection/*`

- **Protocol.** A deterministic `client_message_id` (`blaine-proj-…`); a durable
  attempt record; confirmation **only** by reading the transcript back; resend
  when the message is absent; persistent retry.
- **Projection turns** carry `client_tool_allowlist: ["blaine_task_status"]`.
  Creating a Task from a projection turn is impossible ("Tool not found"). The
  controller also refuses creates whose latest user message is a projection.
- **Crash cases:**
  - **D1:** the projector died after acceptance → confirmed by read-back, no resend.
  - **D2:** a queued projection was lost in an App Server SIGKILL → resent once.
  - **D3:** a queued projection was cancelled when the projector disconnected; an
    immediate resend was acked `queued` but swallowed; a later retry delivered it.
  - Every case ended with exactly 1 visible projection.
- **Cost.** Every projection is a full agent turn on the single-sequence vLLM.
- **Gap fixed during the run.** The terminal projection now includes the recorded
  decision value, read from the Task's `response` artifact.

### 5.9 Concurrency and reconnect

`06-concurrency/probe14-two-clients.json`

Sequence:

1. A's message started a turn.
2. B's message during it was `queued`.
3. A's socket was killed mid-turn, and the turn completed.
4. A reconnected, synced, and received the rest of the stream.
5. B saw both turns.
6. Identical ordered histories on both clients.

A third client's queued message was **cancelled** when it disconnected.

### 5.10 ACP and the relay

`07-acp-and-relay/*`

**Unchanged letta-acp 0.1.11** (SDK 0.7.8, letta-code 0.30.28) against App
Server 0.33.1: `session/new` works; `session/prompt` never returns although the
server finished the turn in about 2 s. This is protocol drift about five weeks
after the adapter's release.

**With npm overrides** (SDK 0.8.17, letta-code 0.33.1):

- `session/new` works.
- `session/load` of a Blaine conversation replays history, then continues; the
  model called `blaine_task_status`.
- A Task was created via ACP `session/request_permission` (options `allow_once`,
  **`allow_always`**, `reject_once`).
- A fresh adapter process reloads the session.

**Blaine-fork requirements:**

- `session/new` hardening (toolset none, no forced `standard` mode);
- replay of reminder-bearing messages;
- distinct rendering of projections;
- `/decide` interception;
- no Letta approvals.

**Relay.** `relay/letta_spike_test.go` runs letta-acp as the `RelayHost` child
behind Blaine's real handshake, session, guard and `relayClient`, with only
tsnet/WhoIs replaced by the package's test host.

- Passive `session/update` traffic, including load replay, passes.
- Host→IDE requests are denied by E0 policy, and the session dies.
- The real `ACP()` frontend advertises no `loadSession` and refuses `session/load`
  before `session/new`.

**Required change:** the Go frontend advertises `loadSession` and accepts
`session/load` as an opening method. The bridge never asks the IDE for approval.
This does not touch workstation identity or E0's capability policy.

### 5.11 Memory

`08-…/memory-scope.json`

- MemFS is a per-agent git repository, injected into the system prompt, shared by
  all of that agent's conversations, and isolated from other agents.
  - A socket client's `write_memory_file` fact appeared in two new conversations
    (system prompt +1 KB).
  - Another agent did not know it.
- With `toolset: none` the main agent cannot edit memory; memory editing depends
  on Bash/Edit (reflection) or file tools.
- In the hardened configuration Letta memory is **inert**. It is client-writable
  at system-prompt level, and it bleeds across Projects unless there is one agent
  per Project.
- It is advisory at best. Blaine's Context Plane stays the only governed memory,
  and nothing flows from MemFS into Tasks.

### 5.12 UI

The spike used protocol-level clients and the ACP test client. Neither public UI
was run:

- `letta-oss-ui`: no LICENSE, pinned to SDK `^0.2.7`.
- React chat template: SDK 0.7.0, API routes hardcoded to `backend: "cloud"` plus
  an API key.

Both need at least an SDK port, given that 0.7.8 already hangs against 0.33.1
(inferred, not run). Neither is worth keeping. After a gateway exists, a small
Blaine-owned client on the SDK `/client` entry remains the likely path.

### 5.13 Conversation vs ActivityTrack

`09-line-of-work/probe18-line-of-work.json`, real model. One conversation carried:

1. two discussion turns with no Task;
2. a mixed request that got an answer plus two Tasks;
3. a pause with **all clients disconnected**, during which the summary completed
   and the decision was answered at the Blaine ingress;
4. both outcomes projected with nobody attached;
5. a resume from a *different interface* (ACP `session/load`) with a correct recap;
6. the desktop client's return, onto a converged history.

Blaine metadata needed outside Letta was references only:

- project → (agent, conversation);
- Task ids;
- the request/identity ledger;
- the delivery ledger;
- decision cards, which are derivable.

That is a thin `ConversationBinding`. The only multi-conversation pressure found
is mechanical, not domain-driven:

- IDE chats call `session/new`, and the current relay cannot open with
  `session/load`;
- channels would be a separate process.

The binding, via the Blaine bridge choosing which conversation an IDE chat
attaches to, is the right fix. **No evidence for ActivityTrack.**

## 6. Glue required

The spike's integration code, excluding the harness and ~1.3 kLOC of probes:

| Component | LOC | Production form |
| --- | --- | --- |
| v2 protocol client | 134 | shared by controller, projector, gateway |
| controller (`blaine_*` tools, identity + reconcile, serialisation) | 181 | Blaine service, ConversationBinding in Postgres |
| projector (outbox, read-back, retry) | 120 | Restate Virtual Object per conversation |
| decision ingress | 36 | inside gateway and ACP bridge, bound to the authenticated principal |
| setup / hardening | 40 | in gateway at conversation creation |
| control shim | 86 | disappears (direct binding call) |
| repair tool | 63 | health checker + repair, or an upstream patch |

Required but **not built**:

- **Gateway.** The sole socket owner and conversation creator. It needs a frame
  allowlist over roughly 70–80 command types and field stripping (`client_toolset`,
  `mode`), plus hardening at creation.
- **ACP bridge.** A letta-acp fork; the upstream `src` is about 2.5 kLOC.
- **Go relay frontend change.**
- **Durability patch.** Atomic `conversation.json` and compaction ordering, in a
  pinned letta-code fork or upstream.
- **Upgrade regression suite.** Tap tool surface, egress, mods, reflection,
  approvals and crash windows; the probes here are the start.

Realistic Blaine-owned total: **~3–5 kLOC plus a maintained adapter fork plus a
small patched letta-code pin**. That is permanently coupled to an "alpha
hard-cut" protocol shipping near-daily releases.

## 7. Unresolved risks

- A paraphrased re-issue after a crash still duplicates a Task (heuristic
  convergence).
- The gateway's frame surface is large and changes with releases; a new frame or
  default could silently reopen a path, as reflection did against the carveout.
- Channels are untested, and imply a second process with divergent state.
- Real JetBrains/IntelliJ ACP behaviour is untested. Only SDK clients were used;
  IDE UI automation is BLOCKED here.
- There is no fsync anywhere in the local store; power-loss durability is unknown.
- Every projection costs a full-context turn on a single-sequence local model.
- Upstream acceptance of the durability and replay fixes is unknown.
- The unhardened default posture is host command execution. Any path that creates
  a conversation outside the gateway (channels, cron, a new client) re-exposes it.

## 8. What adoption would delete or replace in Blaine

| Component | Outcome |
| --- | --- |
| `runtime/personal_acp.py`, `runtime/acp_agent.py` (command grammar) | Replaced by the Blaine ACP bridge (letta-acp fork) |
| PersonalConversation / BriefService / ResultDelivery / Atomic bridge | Not in this repository; unverifiable. The substrate plus projector take their conversation and delivery roles. |
| `runtime/personal_agent.py` | **Retained**, and the `PreviouslyAccepted` race needs fixing |
| Go client, tsnet relay, workstation registry | **Retained**; frontend gains `loadSession` |
| Kernel, PolicyGate, Completion Contract, effects, evidence, Context Plane, Restate | **Retained, unchanged** |
| MIRIX | Unaffected. Letta memory is inert in the hardened configuration and is no replacement. |

## 9. Recommendation for the next architectural decision

Write an ADR for a **narrowed Letta conversation engine**, or decide to go
Blaine-native, after a 2–3 day **hardening spike** that builds and tests the
unbuilt conditions. The harness here already covers them.

1. **Authority.** Letta approvals never carry Blaine authority. Human decisions
   enter through the Blaine gateway or ACP bridge, bound to the authenticated
   principal. Letta auto-allows `blaine_*` tools, so it never raises
   IDE-incompatible approvals.
2. **Gateway.** It is the sole socket owner and the only conversation creator. It
   applies `toolset: none` and `strict` at creation, with allow rules only for
   `blaine_task_create`/`blaine_task_status` (so any other tool still asks), strips
   per-turn toolset and mode overrides, and blocks memory, reflection, command,
   terminal, file, provider, secret, cron and channel frames. The App Server stays
   loopback, sandboxed, with only vLLM reachable.
3. **Deployment flags and settings pinned.** `LETTA_DISABLE_MODS=1`,
   `LETTA_CODE_TELEM=0`, `DO_NOT_TRACK=1`, `DISABLE_AUTOUPDATER=1`,
   `reflectionTrigger: off`.
4. **Durability.** Atomic `conversation.json` and compaction-ordering patch, or a
   detect-and-repair supervisor plus backups.
5. **Task identity.** Arguments in the identity, convergence on open identical
   requests, per-conversation serialisation, and a fix to the binding race.
6. **Projector.** A Restate VO with read-back confirmation and persistent retry;
   projection turns offer only read tools.
7. **ACP.** A bridge fork, plus the relay-frontend `loadSession` change.
8. **Memory.** One Letta agent per Project; memory treated as inert and untrusted.
9. **Upgrades.** Pinned letta-code; any upgrade gated on this regression suite.
10. **Channels.** None until multi-process state divergence is solved.

If the hardening spike shows the gateway or bridge growing toward a protocol
reimplementation, STOP 12 applies and the fallback is a Blaine-native
conversation service, which would reuse this spike's projector, ingress and
identity lessons.

**Atomic: keep frozen.** Both futures consume one conversation stream plus a
Blaine-owned decision ingress. The current Atomic integration shape
(reconstructing lifecycle from several surfaces) would be discarded either way,
and no public Letta UI is usable as-is.

## 10. Reproducing

```bash
export SPIKE_SCRATCH=<scratch dir>   # upstream clones, npm envs, Letta and Restate state
# npm envs: package.json here pins letta-code 0.33.1 + SDK 0.8.17 (node_modules is a symlink)
python3 harness/blaine_stack.py start $SPIKE_SCRATCH/blaine/b1           # Restate+runtime+shim
python3 harness/lettactl.py init $SPIKE_SCRATCH/state/s2 --host-port 58284
bash harness/letta_sandbox.sh $SPIKE_SCRATCH/state/s2 connect openai-compatible \
  --base-url http://127.0.0.1:18000/v1 --api-key none
python3 harness/lettactl.py start $SPIKE_SCRATCH/state/s2
node src/setup.mjs agent $SPIKE_SCRATCH/state/s2 58284 $SPIKE_SCRATCH/state/s2/work/agent.json
node src/controller.mjs --state … --port 58284 --bindings …/bindings.json --identity reconcile
node src/projector.mjs  --state … --port 58284 --bindings …/bindings.json
# then any probe: src/probe04…probe19 (usage in each file header)
harness/egress_run.sh on-default 58293 on no        # egress observation
SPIKE_STRACE=inject SPIKE_INJECT_PATH=<file> python3 harness/lettactl.py start <state>
harness/collect_evidence.sh                          # sanitized evidence/ (aborts on token leak)
```

Scripts are experiment-only and are not repository test suites (no nox or CI
wiring). They are classified HOST: they need the canonical vLLM service, bwrap,
and a Go toolchain for the relay test.

## 11. Files

- `harness/`: sandbox (`letta_sandbox.sh`, `sandbox_entry.sh`), `lettactl.py`,
  `uds_bridge.py`, `llm_tap.py`, `hostile_model.py`, `egress_*`, `integrity.py`,
  `repair_conversation.py`, `blaine_stack.py`, `spike_runtime.py`,
  `control_shim.py`, `proc.sh`, `collect_evidence.sh`.
- `src/`: `v2client.mjs`, `controller.mjs`, `projector.mjs`,
  `decision_ingress.mjs`, `setup.mjs`, `human.mjs`, `acp_client.mjs`, probes
  01–19, `frame.mjs`, `approve.mjs`.
- `relay/letta_spike_test.go`: copied into a scratch copy of
  `client/internal/direct` to run; not part of the client module.
- `evidence/`: 59 sanitized files. Scratch paths are shown as `$SCRATCH`; the
  collector aborts if a capability token appears.
- `versions.json`, `package.json`.
