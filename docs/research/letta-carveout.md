# Letta carveout: conversation substrate for the Personal Agent

Research evidence, not an architecture decision. Investigated 2026-09-25.
No Blaine code, ADR, roadmap or milestone is changed by this document, and no
spike was run. It is meant to be compared with the independent
durable-human-continuity proposals before any decision.

## Evidence labels and baselines

- **OBSERVED**: source inspected at the pinned SHA below.
- **DOC**: current Letta documentation. `docs.letta.com` is blocked by this
  environment's egress policy, so DOC statements come from search-engine extracts
  of those pages and from upstream READMEs. Re-read the pages before a decision.
- **INFERRED**: an architectural conclusion drawn from observations.
- **UNVERIFIED**: needs execution, which this investigation did not do.

| Repository | SHA | Date | Version |
| --- | --- | --- | --- |
| Blaine `origin/main` | `16f7e1a170ca0b0a4bb7f773dbb6922405e24287` | 2026-09-24 | — |
| [letta-ai/letta-code](https://github.com/letta-ai/letta-code) | `52ca1a635b9b98668ad9becc2470f30b907af8d0` | 2026-09-24 | 0.33.1 |
| [letta-ai/letta-agent-sdk](https://github.com/letta-ai/letta-agent-sdk) | `18283a40085ce40cf886fb3fd5c8c21ee081294c` | 2026-09-24 | 0.8.17 |
| [letta-ai/letta-acp](https://github.com/letta-ai/letta-acp) | `51974915c7084af4edaed08eee6ecb565b66a8ad` | 2026-08-20 | 0.1.11 |
| [letta-ai/letta-oss-ui](https://github.com/letta-ai/letta-oss-ui) (also `letta-cowork`) | `d145c2b06e71d1a0a1784667eb6f1eac6329f872` | 2026-07-24 | 0.1.0 |
| [letta-ai/letta-agent-sdk-react-chat](https://github.com/letta-ai/letta-agent-sdk-react-chat) | `ee47d2034eb667ad2eecb1cb9b292030764f01e7` | 2026-08-11 | — |
| [letta-ai/letta-code-server-deployment](https://github.com/letta-ai/letta-code-server-deployment) | `dfd7d8023ad928e8df9838f16b60a6d04bfee953` | 2026-09-24 | — |
| [letta-ai/letta](https://github.com/letta-ai/letta) (retired V1 server) | `5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a` | — | — |

Short links below use `LC/` for `letta-code/blob/52ca1a6…/`, `SDK/`,
`ACP/` and `UI/` similarly.

**Blaine components that could not be inspected.** `PersonalConversation`,
`BriefService`, `ResultDelivery`, the Atomic bridge/backend and the Atomic fork do
not exist on any branch of `LeoFuso/blaine`, and no other repository in the
account contains them. They appear to be local, unpushed work. Everything this
report says about them is classified from the responsibilities described in the
request, not from their code. The code-deletion analysis marks this explicitly.

---

## 1. Executive conclusion

The hypothesis holds for the **conversation substrate** and fails for the **UI,
multi-device and execution** parts.

- **Holds (OBSERVED).** Current Letta Code gives exactly the hierarchy Blaine has
  been trying to invent: a persistent **Agent** (identity + memory) owning many
  concurrent **Conversations** (message threads with retained history, compaction,
  fork, archive, summary, tags). Clients attach through a self-hostable **App
  Server** (`letta server --backend local --listen`). Several connections may
  subscribe to the same conversation, and a `sync` command replays state on
  reconnect. Telegram/Slack/Discord/Signal/WhatsApp **channels** route a chat to
  a specific agent+conversation and run in the self-hosted server. An **ACP
  adapter** maps an ACP session id directly to a conversation id and replays
  history on `session/load`. The code is Apache-2.0, and local mode runs with no
  Letta account on an OpenAI-compatible local model (our vLLM/Qwen).
- **Fails (OBSERVED/DOC).**
  - The public UI (`letta-oss-ui`) is a stale 2.8 kLOC demo. The real desktop and
    web apps are not public source.
  - Web/mobile access and "computers" require Letta Cloud.
  - Letta's tool model is weaker than Blaine's. The default permission mode is
    `unrestricted`, built-in tools execute on the App Server host, "mods" let the
    agent rewrite harness code, and after a restart unknown tool outcomes become
    "stale denials" rather than being reconciled.
  - Local persistence is JSONL files with a non-atomic rewrite path and in-memory
    queues and de-duplication.
  - The protocol is an "alpha hard-cut contract" and ships near-daily pre-1.0
    releases.

**Recommendation: a bounded L3.** Letta's App Server, in local mode on the Hub
host, owns Agent, Conversation, message history, compaction, channel routing and
the Personal Agent's own conversational memory. Blaine owns everything
governed. The two meet at one Blaine-owned controller that exposes Blaine
operations as Letta *external tools* and projects Task progress back into the
conversation through an idempotent outbox. Letta's own execution surface is
disabled: built-in tools, mods, cloud features, telemetry and MCP pass-through.

The request's `ActivityTrack` is not needed now. A Letta Conversation, wrapped by
a thin Blaine reference record, is the durable human-continuity aggregate:
`Project → Conversation → Tasks`.

**Pause further Atomic UI investment** until the spike in §19 has run. Its problems
(frontend reconstruction of lifecycle, polling several surfaces) come from the
missing conversation substrate, and any outcome of the spike rewrites that layer.

---

## 2. Current Letta architecture relevant to Blaine

### 2.1 What "Letta" is today

- The Python Letta server is **end-of-life**. The `letta-ai/letta` README points
  to `letta-code` as "the agent harness, interactive terminal UI, App Server,
  channels, and the runtime used by the desktop and web apps". The `letta-code`
  Docker entrypoint refuses legacy server settings with "The retired Python Letta
  server is end-of-life and this image now contains Letta Code"
  (`LC/docker/entrypoint.sh`). OBSERVED.
- `letta-code` is one TypeScript/Bun package of about 533 kLOC, including tests.
  It contains the TUI, the harness (agent loop), the App Server, channels, memory
  (MemFS), cron, subagents, mods and two backends. OBSERVED.

### 2.2 Backends: where state lives

`LC/src/backend/backend-mode.ts` defines two modes, `api` and `local`. OBSERVED.

| Mode | State | Notes |
| --- | --- | --- |
| `api` ("cloud") | A Letta API server via `@letta-ai/letta-client`. The URL defaults to Letta Cloud; `LETTA_BASE_URL` overrides it (`LC/src/backend/api/server-url.ts`). | With the V1 server retired, "self-hosted API server" no longer means a separate Letta server process. Cloud-only features key off the Cloud hostname (`isCloudServerUrl`). |
| `local` | Files under the local backend directory: per agent `agent.json`; per conversation `conversation.json` + `messages.jsonl` (`LC/src/backend/local/local-store.ts`). Memory under `memfs/<agent>/memory` as a git repository. | Selected with `letta backend local` or `--backend local`. The internal env name is still `LETTA_LOCAL_BACKEND_EXPERIMENTAL`. DOC calls it the self-hosting mode: "agent state … stays on-device, and no Letta account is required." |

### 2.3 Agent, Conversation, runtime, session

- **Agent**: persistent identity, system prompt, model defaults and memory. Memory
  is shared across all of the agent's conversations. OBSERVED (UI README "Key
  concepts"; SDK README).
- **Conversation**: `{id, agent_id, archived, archived_at, created_at,
  updated_at, last_message_at, summary, in_context_message_ids, model,
  model_settings, context_window_limit, hidden, tags}` in local mode
  (`createLocalConversationRecord`). Also supported: `fork`, `compact`,
  `recompile`, list/retrieve/update. There is no arbitrary metadata field beyond
  `tags` and `summary`. OBSERVED.
- **Runtime scope**: every v2 frame carries `{agent_id, conversation_id,
  acting_user_id?}` (`LC/src/types/runtime-scope.ts`). One connection may
  subscribe to several runtimes. Several connections may subscribe to the same
  runtime, and runtime events go to every subscriber. DOC (App Server integration
  patterns).
- **Session**: the client-side object (`client.resumeSession(agentId |
  conversationId)`) bound to one runtime. It is independently owned and closed
  (SDK README). An ACP session id *is* a conversation id (ACP README). OBSERVED.
- **Turn discipline**: "each {agent_id, conversation_id} should still have at most
  one active turn from your controller at a time". Additional inputs queue and are
  acknowledged with `disposition: "started" | "queued"`
  (`InputAcceptedResponseMessage`). DOC + OBSERVED.

### 2.4 App Server and protocol v2

- `letta server --listen [ws://host:port]` runs "the local App Server using native
  v2 WebSocket frames". It defaults to a loopback port. Non-loopback listeners are
  expected to use `--ws-auth capability-token` or `signed-bearer-token`
  (`LC/src/cli/subcommands/app-server.ts`, `LC/src/websocket/app-server-auth.ts`).
  It pings clients every 30 s and reaps them after 90 s of silence. OBSERVED.
- The header of `LC/src/types/protocol_v2.ts` reads: "Protocol V2 (alpha
  hard-cut contract)". OBSERVED.
- The single socket carries far more than chat. Frame families include:
  - conversation and agent CRUD;
  - `input` (create_message / approval_response);
  - `sync`;
  - stream deltas, `turn_finished`, `control_request`/`can_use_tool` approvals;
  - `update_queue`;
  - **filesystem** (`read_file`, `write_file`, `edit_file`, `get_tree`,
    `grep_in_files`);
  - **terminals** (`terminal_spawn`, `terminal_input`);
  - **memory writes**;
  - **channel account/route configuration**, **cron**, **secrets**, provider
    connection and model switching.

  OBSERVED. **INFERRED consequence:** an App Server socket is a shell-capable
  control plane for its host. Anything that can reach it with valid auth can
  operate the host.
- **Reconnect**: `sync` replays state and, optionally, recovers stale approvals
  (`SyncCommand`). OBSERVED.
- **Restart behavior**: after a process restart, pending approvals are rebuilt from
  the backend. Interactive tools (e.g. AskUserQuestion) are re-presented.
  Replay-unsafe tools ("Bash, MessageChannel, …") "may already have run before the
  process restarted, so they are never re-run or re-asked; they become stale
  denials" (`LC/src/websocket/listener/recovery-sync.ts`). OBSERVED.
- **Input de-duplication** by `client_message_id` is an in-process map
  (`runtime.acceptedInputDispositions`, `LC/src/websocket/listener/inbound-dispatch.ts`).
  The local store does persist the id as the message `otid`
  (`local-store.ts:1739`). OBSERVED.
  **INFERRED:** transport-level dedupe does not survive a restart; `otid` can
  support dedupe by lookup.

### 2.5 External tools: the delegation seam

- A connection can publish tools for specific runtimes
  (`runtime_external_tools_update`). The agent calls them, the App Server sends
  `external_tool_call_request` to **the registering connection**, and that
  connection replies with `external_tool_call_response`. OBSERVED
  (`LC/src/types/external-tool-protocol.ts`,
  `LC/src/websocket/listener/external-tools.ts`).
- Registrations are owned by the sending connection. Calls time out after
  **5 minutes**, and pending calls are rejected when that connection disconnects.
  OBSERVED.
- The Agent SDK exposes this as `AnyAgentTool { name, parameters, execute() }`.
  `execute` runs in the SDK process (`SDK/examples/custom-tools/main.ts`).
  OBSERVED.
- Per-turn `client_tool_allowlist` (an empty array means no built-in client
  tools) and `exclude_interactive_tools` exist on `input` (`InputCreateMessagePayload`)
  and are routed by the listener (`message-router.ts:559`). OBSERVED. That this
  fully suppresses every built-in tool is UNVERIFIED.

### 2.6 Conversation history, compaction, memory

This section covers the four layers the request asked to keep apart. All
OBSERVED in local mode.

1. **Canonical history**: `messages.jsonl` in "pi-session-entry-jsonl" format.
   New messages are appended (`appendConversationSessionMessageEntry`).
2. **Active LLM context**: `conversation.in_context_message_ids`. Compaction
   narrows it; it does not delete history.
3. **Compacted context**: compaction ("all" or "sliding_window", default
   `sliding_window` at 30 %) generates a model-written summary message. It is
   stored with `transcript: "append-compaction"`, so the pre-compaction messages
   stay in the transcript. The summary prompt asks for "Lookup hints" so the agent
   can later search history (`LC/src/backend/local/compaction.ts`).
4. **Learned long-term memory**: MemFS, per-agent Markdown files in a git
   repository, projected into the system prompt as core memory with configurable
   size limits (`LC/src/agent/memory-filesystem.ts`, `memory-constraints.ts`). The
   agent edits it with file tools. Background "reflection"/"dreaming" subagents
   rewrite it (README; `ReflectionSettingsSnapshot`). Provenance is git history,
   not source or evidence authority.

Caveats (OBSERVED):

- A `rewrite` transcript path exists (repair, migration and some loads) and uses a
  plain `writeFileSync` of the whole file, with no temp-and-rename and no fsync.
  Agent and conversation JSON records are written the same way.
- Local **search** is lexical: conversation search matches terms against
  summaries; message search scans transcripts. Vector/hybrid search exists only
  against an API server (`LC/src/backend/conversation-search.ts`,
  `message-search.ts`, `local/transcript-search.ts`).

### 2.7 Channels

- Bundled first-party channels: Telegram, Slack, Discord, Signal and WhatsApp.
  User plugins live in `~/.letta/channels/<id>/` (`LC/src/channels/README.md`).
  OBSERVED. DOC: "Channels (beta)"; "These CLI channels support the local backend
  only."
- A route maps `(channel, account, chat, thread)` to `(agentId, conversationId)`
  and is persisted to `routing.json` by write-then-replace
  (`LC/src/channels/routing.ts`). DM policy is `pairing | allowlist | open`;
  Telegram, Discord, WhatsApp and Signal default to pairing. OBSERVED/DOC.
- Channels run inside a `letta server` process
  (`letta server --backend local --channels telegram`). Telegram uses outbound
  long-polling, so no inbound port is needed. DOC. Whether one process can combine
  `--listen` (App Server) with `--channels` is UNVERIFIED. If not, channels and the
  App Server must share the same local state directory.
- Credentials are stored in the OS keyring or a file
  (`LETTA_CHANNEL_CREDENTIALS_STORE`, `LC/src/channels/credential-store.ts`).
  OBSERVED.

### 2.8 Computers and remote access

- **Computers**: `letta server` without `--listen` "Register[s] letta-code as a
  listener to receive messages from Letta Cloud" (`LC/src/cli/commands/listen.ts`).
  `letta-code-server-deployment` runs "an always-on computer for agents hosted in
  Letta Cloud. The container connects outward to Letta Cloud". The list API is
  `/v1/environments` on the Letta API. OBSERVED.
- DOC: "App Server … does not appear in the computer picker." "Remote access
  requires signing in with Letta and is not available for agents stored only on a
  local backend." The README marks remote computers and secrets "(requires signing
  in with Letta)".
- **INFERRED:** "Computer" is a Letta Cloud routing construct for tool execution,
  not a device-trust model.

### 2.9 Governance defaults

All OBSERVED.

- `DEFAULT_PERMISSION_MODE = "unrestricted"` (`LC/src/permissions/mode.ts`). The
  modes are `standard`, `acceptEdits`, `unrestricted` and `strict`.
- **Mods** are "trusted local code that the agent can inspect, edit, reload, and
  repair" (`LC/src/mods/README.md`). They can be disabled with `LETTA_DISABLE_MODS=1`.
- **Telemetry** is "Enabled by default unless explicitly disabled". It POSTs to
  `/v1/metadata/telemetry` on the configured server URL, which defaults to Letta
  Cloud even in local mode. Opt out with `LETTA_CODE_TELEM=0` or `DO_NOT_TRACK=1`
  (`LC/src/telemetry/index.ts`, `backend/api/metadata.ts`).
- The model provider can be any OpenAI-compatible endpoint with a custom base URL
  (`LC/src/providers/byok-providers.ts`), including our vLLM/Qwen.

### 2.10 Churn

About 15 commits a day on `letta-code` `main` over the last two weeks.
Versions went from 0.32.12 to 0.33.1 between 2026-09-16 and 2026-09-24. The SDK
pins an exact `@letta-ai/letta-code` version (`0.33.1`). OBSERVED.

---

## 3. License, self-host and local-runtime facts

| Component | Repository | License (verified) | Reuse form | Network/service dependency | Local/self-host | Cloud requirement | Upgrade coupling | Major risks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Letta Code (harness, App Server, channels, local backend) | letta-ai/letta-code | Apache-2.0 (`LICENSE`, `package.json`) | Runtime dependency (npm `@letta-ai/letta-code` or `ghcr.io/letta-ai/letta-code`); fork possible but large | Model provider; telemetry to Letta API unless disabled; channel platforms | Yes: `letta server --backend local --listen` | None for local mode. Computers, secrets, web/mobile and Cloud search require Letta Cloud. | Very high: alpha v2 protocol, near-daily releases, pre-1.0 | Execution surface on host; unrestricted default; mods; telemetry default; JSONL durability; protocol churn |
| Letta Agent SDK | letta-ai/letta-agent-sdk | Apache-2.0 | Runtime dependency (Node, or `/client` for browser/React Native) | App Server (spawned locally or remote) | Yes: `local` and `remote` backends | `query()` and `cloud` backend need Cloud; the rest does not | Pins exact letta-code; 0.x | Assumes Letta owns agent/conversation state |
| Letta ACP adapter | letta-ai/letta-acp | Apache-2.0 | Fork/reference; not unchanged (§13) | App Server via SDK | Yes: `local` and `remote` backends | `cloud`/`cloud-oauth` only if chosen | Tracks SDK | Hands IDE MCP servers to the agent; built-in tools run where the harness runs |
| Letta OSS UI (`letta-cowork`) | letta-ai/letta-oss-ui | **No LICENSE file.** Derived from DevAgentForge/Claude-Cowork, whose README says MIT. The npm package is `private: true`. | Reference only until the license is clarified | App Server via SDK `^0.2.7` | Yes: `LETTA_BACKEND=local|remote` | No | Stale: SDK 0.2.7 vs current 0.8.17; last commit 2026-07-24 | Demo quality; license ambiguity |
| React chat template | letta-ai/letta-agent-sdk-react-chat | Apache-2.0 | Fork/reference (Next.js, ~1.7 kLOC) | App Server via SDK 0.7.0 | README targets a cloud API key; server-side SDK could point at `remote` (UNVERIFIED) | Default setup uses Cloud | Moderate | Template, not a product UI |
| Letta desktop app and chat.letta.com | not public (`letta-ai/letta-desktop` not readable) | Unknown | None (binary use only) | Letta Cloud for web/mobile | Desktop app with local agents: UNVERIFIED | Web/mobile: yes | N/A | Closed; cannot be forked |
| Server deployment template | letta-ai/letta-code-server-deployment | No LICENSE file | Reference | **Connects outward to Letta Cloud** | No (it is a Cloud computer) | Yes | Hourly image-pin updates | Not applicable to Blaine |
| Retired V1 server | letta-ai/letta | Apache-2.0 | None | — | End-of-life | — | — | Do not build on it |

---

## 4. Component-by-component reuse matrix

| Letta component | Candidate Blaine role | Disposition | Why |
| --- | --- | --- | --- |
| Agent (identity + MemFS) | Personal Agent conversational identity | **Integrate** | Real persistent identity with memory shared across conversations. Scope and provenance limits in §12. |
| Conversation + transcript + compaction | Durable human-continuity aggregate | **Integrate** (wrap by reference) | This is the missing substrate. Full history is retained and compaction is non-destructive on the normal path. |
| App Server runtime (turn queue, multi-subscriber, sync) | Multi-client attachment | **Integrate** behind a Blaine gateway | Solves attachment and reconnect. It is also a host control plane (§17). |
| External tools | Delegation seam into Blaine | **Integrate** | Blaine operations become agent tools executed by a Blaine controller. |
| Built-in client tools (Read, Edit, Bash, …) | Workspace effects | **Remove / disable** | They bypass PolicyGate, the capability journal, target-effect identity and workstation providers. |
| Permission/approval UI (`can_use_tool`) | Human approval of Blaine tool calls | **Reuse** | Gives a human-action gate on `respond`/`approve` tools (§9). |
| Channels (Telegram, Slack, …) | Messaging interfaces | **Integrate later** | Route to the same conversation; beta; third-party egress. |
| Agent SDK | Blaine controller + clients | **Reuse** | Stable high-level client over an alpha protocol. |
| ACP adapter | IntelliJ attachment | **Fork/reference** | Needs Blaine-specific restrictions (§13). |
| OSS UI | Desktop UI | **Reference only** | Demo; stale; license unclear (§14). |
| Computers | Multi-device execution | **Reject** | Cloud-only; conflicts with the workstation model (§15). |
| Mods, cron, secrets, self-configuration skills | — | **Disable** | Self-modification and parallel scheduling or secret paths. |
| Letta memory search / recall subagents | Cross-conversation recall | **Wrap** via Context Plane | Useful signal; no authority or provenance (§11). |

---

## 5. Carveout alternatives

Five alternatives, ordered by how much Letta owns. L1 and L2 are folded into
Alternative A because inspection shows they are the same trade-off in practice.

### Alternative A: L0/L1, Blaine-native conversation, Letta as reference (plus UI code at most)

```text
Atomic UI / OSS-UI fork ──► Blaine PersonalConversation service ──► Blaine Tasks (Restate)
                                    (Blaine-owned messages, sessions,
                                     compaction, channels, ACP)
```

| Owner | Owns |
| --- | --- |
| Blaine | Everything: conversation, history, compaction, sessions, channels, ACP, UI backend, Tasks |
| Letta | Nothing at runtime; patterns only |

- **Advantages**: no upstream coupling, no new host process, one data model, full
  control of privacy and durability.
- **Disadvantages**: Blaine must build the whole substrate Letta already has:
  multi-subscriber streaming, turn queueing, reconnect sync, compaction,
  conversation fork/archive, channel adapters with pairing and routing, and ACP
  session/load replay. That is the path that produced the Atomic problems.
- **L1 specifically (reuse only `letta-oss-ui`)**: the UI is written against the
  SDK's session and stream model (`useIPC`, `runner.ts`). Pointing it at a
  Blaine-native backend means emulating Letta's protocol or rewriting its data
  layer, which reproduces the Atomic impedance problem with a smaller codebase.
- **Migration effort**: high (months of product plumbing). Operational complexity
  is low. Security implications are the smallest. Impact on existing code:
  additive. Code likely deleted: none. Upstream coupling: none.
- **Failure mode**: the substrate stays half-built, and every client reconstructs
  semantics again.

### Alternative B: L2, Letta SDK + UI over a Blaine-owned conversation

```text
OSS UI ─► Letta Agent SDK ─► (Blaine server speaking Letta protocol v2) ─► Blaine conversation + Tasks
```

- **Technically incoherent** (OBSERVED). The SDK is a client of an App Server it
  spawns or connects to. Its local and remote backends assume the App Server owns
  agent, conversation, turn queue and tool execution (SDK README table). To keep
  Blaine authoritative, Blaine would have to implement the alpha protocol server
  side (`protocol_v2.ts`, about 2.6 kLOC of types alone) and chase near-daily
  changes.
- **Advantages**: reuse of UI and SDK code.
- **Disadvantages**: maximal coupling for minimal ownership gain.
- **Verdict**: reject.

### Alternative C: bounded L3, Letta conversation substrate with Blaine governed back-end (recommended)

```text
 Desktop UI (web/Electron, SDK /client)     IntelliJ                 Telegram (later)
            │                                  │  blaine Go client        │ outbound poll
            │ private network                  │  (tsnet relay, E0)       │
            ▼                                  ▼                          │
   ┌────────────────────────── Blaine Hub host ──────────────────────────┼──────────┐
   │  Blaine gateway (frame allowlist, auth)   Blaine ACP bridge          │          │
   │            │                              (forked letta-acp)         │          │
   │            └──────────────┬───────────────────────┘                  │          │
   │                           ▼                                          │          │
   │        Letta App Server  (local mode, loopback, strict, no mods,     ◄──────────┘ │
   │        no telemetry, built-in tools off)                                          │
   │        owns: Agent, Conversation, transcript, compaction, turn queue,            │
   │              channel routes, conversational MemFS                                 │
   │                           │ external tools / input frames                         │
   │                           ▼                                                       │
   │        Blaine controller (SDK or v2 client): blaine_* tools + Task projector      │
   │                           │                                                       │
   │                           ▼                                                       │
   │        Blaine Personal Agent controls ─► Restate CognitiveTaskV1                  │
   │        PolicyGate · Completion Contract · effects journal · Context Plane         │
   │        workstation registry/providers · artifacts/evidence                        │
   └───────────────────────────────────────────────────────────────────────────────────┘
```

Ownership in §7.

- **Advantages**:
  - Adopts the exact Agent/Conversation/Session hierarchy and multi-client model
    that Blaine lacks.
  - The UI renders one conversation stream; Task state arrives as projected
    messages, not frontend reconstruction.
  - Channels and ACP session continuity come nearly for free.
  - Blaine's kernel is untouched.
  - Deletes bespoke conversation code (§18).
- **Disadvantages**:
  - A second stateful service on the host, TypeScript/Bun, with high churn.
  - Letta's execution surface must be actively neutralized and kept neutralized
    across upgrades.
  - The Blaine gateway and ACP bridge are new Blaine code.
  - Local-mode durability is file-based.
- **Migration effort**: medium. Spike ~1 week (§19), then a controller, projector,
  gateway and ACP bridge.
- **Operational complexity**: +1 service, +1 file-based state directory to back
  up, version pinning.
- **Security**: the App Server must never be directly reachable (§17).
- **Impact on existing Blaine code**: additive in the kernel. `personal_acp.py` is
  replaced. PersonalConversation, ResultDelivery and the Atomic bridge shrink or go.
- **Upstream coupling**: letta-code version pin plus protocol v2 surface used by
  the controller, gateway and bridge.
- **Failure modes**: an upgrade silently re-enables tools or changes frames
  (mitigate with pinning and gateway tests); transcript corruption on crash
  (mitigate with backups; Tasks unaffected); controller disconnected (external
  tools fail fast, projector retries).

### Alternative D: full L4, Letta is the Personal Agent runtime with its own tools; Blaine is only for "governed" Tasks

```text
IntelliJ / UI / channels ─► Letta agent (Read/Edit/Bash enabled, computers, MCP)
                                   └─ sometimes ─► Blaine Task
```

- **Advantages**: maximum immediate capability. Letta's coding harness works out
  of the box.
- **Disadvantages**:
  - Two execution paths. Every non-delegated edit or shell command bypasses
    PolicyGate, the capability journal, E2.0 target-effect identity,
    reconciliation and IDE-delegated workspace authority (ADR 0027).
  - Unknown tool outcomes become stale denials instead of being reconciled.
  - The model decides which path governs a given effect.
- **Security**: breaks Blaine's single-enforcer invariant.
- **Verdict**: reject. This is the case the request warned about: adoption would
  weaken Task properties.

### Alternative E: L5, Letta replaces substantial Blaine agent infrastructure

| Blaine component | Replace? | Reason |
| --- | --- | --- |
| MIRIX | Undecided (§12) | Overlaps Letta MemFS for conversational memory; not for governed knowledge. |
| Context Plane | **No** | Letta has no governed-source, provenance, trust or promotion model. Letta search is lexical locally. |
| PersonalConversation / BriefService / ResultDelivery | Largely yes (§18) | Conversation substrate and delivery sink. |
| ACP adapter | Host side yes (fork); transport no | tsnet relay and workstation identity remain. |
| Channel/session plumbing | Yes | Letta channels and runtime subscriptions. |

- **Verdict**: reject as a package. Its safe subset is Alternative C.

---

## 6. Recommended carveout

**Alternative C (bounded L3).** It is the only option that:

1. obtains durable multi-interface conversation without building it;
2. keeps every Blaine execution invariant intact, because Letta executes nothing
   except Blaine tools; and
3. deletes bespoke code rather than adding Letta beside it.

It is not maximal reuse: Letta's execution, computers, cloud features and UI are
excluded. It is not minimal reuse either: it adopts Letta's central abstraction
rather than copying patterns.

Conditions that must hold (tested by the spike):

- Built-in tools can be kept off for every turn.
- Mods, telemetry and cloud features can be disabled.
- A Blaine gateway can restrict the socket to a frame allowlist.
- Conversation continuity survives App Server restarts.
- Task results can be projected exactly once.

---

## 7. Recommended ownership boundaries

| Concern | Owner | Notes |
| --- | --- | --- |
| Project semantics, Cards | Blaine | Letta has no Project; Blaine binds conversations to Projects. |
| Personal Agent identity (conversational) | Letta Agent | One agent per Project or one personal agent: open question (§20). |
| Conversation, messages, compaction, conversational state | Letta | Canonical transcript on the Hub host; Blaine never copies it. |
| Conversation ↔ Project/Task references, delivery ledger | Blaine (`ConversationBinding` record) | A thin reference record, not a second conversation. |
| Session/connection attachment, reconnect sync | Letta App Server | Behind the Blaine gateway / ACP bridge. |
| Channel routing and pairing | Letta | Blaine sharing policy decides which conversations may be routed to third parties. |
| Task lifecycle, retries, waits | Restate (Blaine) | Unchanged. |
| Authority, approvals of effects | PolicyGate + HumanDecision (Blaine) | Letta approvals only gate *calls into* Blaine. |
| Completion | Completion Contract (Blaine) | Unchanged. |
| Effects, reconciliation, evidence, artifacts | Blaine | Letta built-in tools disabled. |
| Workspace/provider safety, workstation identity | Blaine | Letta computers not used. |
| Governed context, provenance | Context Plane (Blaine) | Letta conversations become one governed source. |
| Conversational memory (persona, preferences, working notes) | Letta MemFS | Advisory; never a source of Task authority or evidence. |
| Model serving | Blaine local vLLM | Letta connects as an OpenAI-compatible provider. |

---

## 8. Conversation / ActivityTrack conclusion

**What a Letta Conversation actually is** (OBSERVED, §2.3, §2.6): a durable thread
under one persistent agent. It has its own full transcript, active-context window,
non-destructive compaction, summary, tags, archive/hidden state, per-conversation
model override and fork. It shares the agent's memory with sibling conversations.
Any number of clients and channel routes may attach concurrently, and it is
addressable by id from every interface (UI, ACP `session/load`, channel route).

That is exactly the "long-running line of human work" the request describes: days
of messages, discussion without Tasks, delegation, results, pauses and resumption
from another client.

It does **not** natively own Task references, decisions, artifacts or cross-track
relationships.

**Comparison**

| Model | Assessment |
| --- | --- |
| `Project → ActivityTrack → Conversation → Tasks` | Adds an entity whose only extra content (Task refs, decisions, links) fits in a reference record. It creates two continuity objects that must be kept in sync. Not justified by current evidence. |
| `Project → Conversation → Tasks` | **Recommended.** Several simultaneous work lines in one Project are several conversations. Task references, human-interaction references and delivery ledger live in a Blaine `ConversationBinding` keyed by `(agent_id, conversation_id)`. Messages stay in Letta. |
| `Project → ActivityTrack` with conversation/timeline as a projection | Makes Blaine own the continuity aggregate and treat Letta as a renderer. That is Alternative A/B and inherits their costs. |

**Letta's hierarchy already provides what Blaine was inventing.** Agent is the
persistent identity plus memory. Conversation is the continuity aggregate. Session
is the connection. Channel route is the interface binding.

**Wrap by reference, do not reuse bare.** Blaine needs a domain reference that
carries Project, Task links and delivery state and keeps the conversation
authority-free. Do not wrap by copying: a Blaine object that mirrors messages would
recreate a second conversation store.

**When to reconsider an ActivityTrack.**

- One line of work routinely spans several conversations (forks, per-channel
  threads, an IntelliJ thread plus a desktop thread on the same subject) and users
  need them treated as one.
- Blaine needs lifecycle states on a work line (paused, blocked, done) that do not
  belong to a conversation.

Neither is demonstrated yet. Both can be added later as a grouping over
`ConversationBinding` without migrating messages.

---

## 9. Task integration model

```text
Letta conversation turn
   │ agent calls external tool blaine_task_create(spec…)     (tool_call_id T)
   ▼
Blaine controller ──► PersonalAgent.create(request_id = H(conversation_id, T))
   │                     (existing idempotent create: task_identity(request_id))
   │  returns receipt {task_id, submission}   ◄── within the 5-minute tool timeout
   ▼
ConversationBinding += task_id           (Blaine-owned, e.g. PostgreSQL like E0.D)
   ...
Task runs independently in Restate (unchanged)
   │  ExecutionEvents / inspect: progress, HumanDecisionRequest, terminal result
   ▼
Blaine conversation projector (one serialized outbox per conversation)
   │  input create_message, client_message_id = H(task_id, event_ref)
   │  before sending: look up otid in recent history; record delivery in ledger
   ▼
Letta conversation shows "Task X: waiting for your decision / completed"
```

| Question | Answer |
| --- | --- |
| Who owns the correlation id? | Blaine. `request_id` is derived from `(conversation_id, tool_call_id)`, so a retried or recovered tool call maps to the same Task (the existing `task_identity`). |
| How are Task references stored? | In `ConversationBinding`, not in Letta. Optionally mirrored as a Letta conversation `tag` for display only. |
| How do results appear? | As projected messages built from Blaine's authoritative result and evidence refs, never from the agent's paraphrase. The agent may discuss them afterwards. |
| How do human approvals route back? | The agent calls `blaine_task_respond(task_id, request_id, value)` or `blaine_effect_approve(…)`. These tools are configured **ask-always**, so the human's click on Letta's `can_use_tool` card, in the UI, IDE or channel, is the human action. Blaine then validates the typed response (allowed set, revision, digest) exactly as today. A model-originated call without that approval is rejected by configuration. **Residual risk**: the approval card shows the model's transcription of the value; it must display the exact request and value. |
| No UI connected? | The projector still appends to the conversation; the transcript persists. If a channel route exists, the agent's reply can go out through MessageChannel. The Task waits durably in Restate regardless. |
| Conversation resumed elsewhere? | Same `conversation_id` from any client. `sync`/`session/load` replays the projected messages. |
| Duplicate result delivery? | Deterministic `client_message_id`, persisted as `otid`, is checked before sending, plus a Blaine delivery ledger updated in a journaled step. Letta's own dedupe is in-memory and is not relied on. |
| Several Tasks concurrently? | Many `task_id`s per binding. The projector serializes inputs per conversation. Letta queues inputs behind the active turn (`disposition: queued`). |
| Workspace concurrency? | Remains Blaine's (future resource arbiter, E2 routing). The conversation may display claims; it never grants or holds them. |

**Invariant**: the conversation is never authoritative for Task lifecycle. It
contains projections and references. Status questions go to Blaine, via the
`blaine_task_status` tool, not to the transcript.

---

## 10. Restate interaction

**Option 1: Letta owns conversation durability; Restate owns finite Task
execution.** Recommended.

**Option 2: Restate owns a Conversation actor; Letta supplies UI, client and
memory.** Rejected. Letta's App Server already owns turn queueing, stream state,
approvals and the transcript, and its clients (SDK, ACP, channels) talk to it
directly. A Restate conversation actor would either shadow that state (two owners)
or require removing Letta's runtime, which is Alternative A/B.

A better refinement of Option 1: use Restate only for the **projector**, as a
Virtual Object keyed by conversation. It serializes deliveries per conversation and
journals the send, so delivery survives Blaine restarts. It owns no conversation
state beyond the delivery ledger.

| Concern | Behavior under the recommendation |
| --- | --- |
| Crash recovery | App Server crash: the transcript is on disk. Interrupted Letta turns recover per §2.4; a pending `blaine_*` call is re-issued and Blaine's create is idempotent. Blaine crash: Restate recovers Tasks and the projector as today. |
| Message delivery | Projector VO step → `input` frame. The otid lookup and ledger give at-most-once visible delivery; retries are safe. |
| Concurrent sessions | Letta: multi-subscriber per runtime; one active turn per conversation. Blaine: none needed. |
| Long-running conversations | Letta compaction plus the retained transcript. Blaine is unaffected. |
| Idempotency | Blaine request ids for Task creation; deterministic client message ids for projections. |
| Task result into conversation | Projector only. The agent never "reports" results from memory. |
| Client disconnect/reconnect | Letta `sync` replay. Blaine is unaffected. |
| Replay | Restate replays Tasks. Letta has no journal replay; its unknown tool outcomes become stale denials, which is harmless when its only tools are Blaine calls whose effects are idempotent on Blaine's side. |
| Cross-device | Any client that can reach the gateway or bridge. |

No lifecycle has two owners: Letta owns conversational turns, Restate owns Tasks,
and the projector's ledger is the only bridge state.

---

## 11. Context Plane interaction

**Letta should be a lower-level conversation provider beneath the Context Plane,
and the owner of conversational context compilation for the Personal Agent's own
turns only.**

- Letta compiles its own chat context: system prompt, core memory, in-context
  messages and compaction. Blaine should not try to own that.
- The Context Plane keeps ownership of context for **Tasks and workers**
  (initial packet, deltas, provenance, security context, promotion).
- The Context Plane gains a new governed **conversation source**: Letta
  conversations addressed by `(agent_id, conversation_id, message_id)` with
  timestamps. Its provenance is "human/agent conversation", never evidence of
  execution.
- Letta memory is **not** a Context Plane authority source (§12).

**Scenario: "Does this conflict with what we decided in the verification track?"**

| Step | Letta gives | Blaine must add |
| --- | --- | --- |
| Identify the other work line | Conversation list/search. Local search is lexical over summaries; Cloud has vector. Conversations carry summaries and tags. | Project-scoped `ConversationBinding` lookup; explicit links; authorization (only conversations of this Project/user). |
| Retrieve bounded state/history | Messages list with cursors; message search (lexical locally); recall/history-analyzer subagents | A Context Plane resolver request `blaine_context_resolve(question)` that retrieves bounded excerpts with message-id provenance. |
| Include artifacts and Task outcomes | Nothing (Letta does not know Blaine Tasks) | Context Plane joins `ConversationBinding` Task refs to authoritative results and evidence. |
| Preserve provenance | Message ids and timestamps exist | Packet items labelled with source and authority; the conversation is never task truth. |
| Reason over it | The Letta agent turn | — |

Conclusion: Letta supplies the storage and addressing primitives. The
"which other track, bounded, with Task outcomes and provenance" logic remains
Blaine work. It is a natural CP phase (a new source type), not a new Context Plane.

---

## 12. Memory / MIRIX recommendation

| Dimension | Letta MemFS | MIRIX (as integrated today) | Blaine Context Plane (accepted design) |
| --- | --- | --- | --- |
| Purpose | Agent's own core memory, in its prompt | Semantic memory service, retrieval | Governed knowledge for Task/worker context |
| Scope | Per agent (plus shared memory repos) | Client/user id; scope enforcement found inconsistent (MIRIX carveout) | Project/Task/security context, lineage |
| Mutation | Agent self-edits; background reflection rewrites | Service-internal async formation | Explicit promotion/declassification |
| Provenance | Git history | Tags; weak | Source/evidence authority |
| Blaine integration | None yet | Bounded loopback read-only provider; **live MIRIX disabled on the CP.1 path** | CP.1 PASS; CP.2 not started |
| Operational cost | Files + git, inside the App Server | PostgreSQL + pgvector + Redis + two vLLM models + MIRIX service | Part of Blaine |

Options:

1. **Keep MIRIX** alongside Letta. This produces two systems forming personal
   memory from the same conversations. Reject unless MIRIX serves a job Letta
   cannot.
2. **Replace MIRIX with Letta memory.** This works for conversational memory
   (preferences, persona, working notes). It fails for governed knowledge, because
   MemFS has no trust/provenance model and must not feed worker packets.
3. **Hybrid with explicit responsibilities.** Recommended, with MIRIX frozen:
   - Letta MemFS is the Personal Agent's conversational memory only. It is
     advisory and never read by the Context Plane as authority or evidence.
   - The Context Plane's governed Memory (CP.2+) is the only knowledge that
     reaches Task and worker packets, formed by explicit promotion from verified
     work.
   - MIRIX: freeze further integration. Re-decide after CP.2 qualification whether
     it is the storage backend for Context Plane Memory. Otherwise retire it.

   This is not two memory systems doing one job. MemFS answers "what does my
   assistant know about me and this conversation". Context Plane Memory answers
   "what verified knowledge may this worker rely on, with what provenance". They
   are fed differently and consumed by different readers. The rule that makes this
   hold: **nothing flows from MemFS into Task context without Context Plane
   promotion.**

Letta's self-editing and reflection are a governance concern. They are acceptable
for conversational memory only, and only because that memory carries no authority.

---

## 13. ACP / IntelliJ recommendation

**letta-acp facts** (OBSERVED, ACP README and `src/`):

- ACP v1 over stdio.
- `session/new` creates a conversation on one agent; `session/load` resumes a
  conversation id and replays up to 200 messages.
- `session/list` uses an adapter-side registry of `cwd`s.
- Modes: standard, acceptEdits, unrestricted, enforced in the adapter.
- Permissions are forwarded as `session/request_permission`.
- Editor fs is delegated only through two external tools (`read_editor_buffer`,
  `write_via_editor`). **Built-in Read/Edit/Bash "always execute Letta-side"**:
  with a `remote` backend they execute on the App Server host.
- IDE-supplied MCP servers from `session/new` are wired into the agent as SDK
  external tools.
- Terminal delegation is not implemented.
- The README lists JetBrains as a target client; live JetBrains compatibility is
  UNVERIFIED here.
- Credentials: an API key or OAuth via keychain (cloud), a capability token
  (remote), or none (local).

**Blaine facts** (OBSERVED):

- IntelliJ launches the `blaine` Go client (stdio ACP), which relays over embedded
  tsnet to the Hub edge, which runs the host ACP adapter (`personal_acp.py`).
- Workstation identity is Tailscale node + Blaine registration (E0.D).
- E0.C strips client capabilities and denies non-empty MCP forwarding.
- ADR 0027: the IDE's delegated MCP surface is workspace authority, and PolicyGate
  alone enforces it.
- Today's host adapter is a command grammar with no conversation.

**Comparison**

| Shape | Verdict |
| --- | --- |
| IntelliJ → letta-acp (unchanged) → Letta conversation, Blaine only via delegated Tasks | Reject. It bypasses the tsnet/workstation trust boundary unless run locally. IDE MCP tools go to the Letta agent, so mutating IntelliJ tools run under Letta permissions, not PolicyGate (violates ADR 0027). Built-in tools touch the Hub filesystem. |
| IntelliJ → Blaine Go client (tsnet) → **Blaine ACP bridge (forked from letta-acp)** → Letta conversation + Blaine tools | **Recommended.** Keep the transport, identity and relay. On the host, replace `personal_acp.py` with a bridge derived from letta-acp that maps ACP session ↔ Letta conversation (reusing its history replay, permission forwarding, streaming translation and `session/list`). It disables built-in tools and MCP pass-through into Letta. It routes IDE workspace capabilities to Blaine's E1 capability path (PolicyGate), never to the Letta agent. |

Reuse level: **fork selectively.** It is about 2.8 kLOC, Apache-2.0, and the
protocol-mapping code is the valuable part. Credentials: the bridge holds the App
Server capability token on the host. No token reaches the workstation. Tool
execution: only Blaine tools, executed in Blaine.

---

## 14. UI recommendation: Letta OSS UI vs Atomic

| Criterion | Continue Atomic fork | Fork/adapt `letta-oss-ui` | Use Letta UI unchanged on a Letta-backed agent |
| --- | --- | --- | --- |
| Code availability/quality | Not inspectable in this investigation (local work) | Electron + React, ~2.8 kLOC, "Demo open-source UI", SDK `^0.2.7` (current 0.8.17), last commit 2026-07-24 | The polished desktop/web apps are not public source; chat.letta.com needs Cloud |
| License | Upstream Atomic license not re-verified here | No LICENSE file; derived from MIT Claude-Cowork | Unknown/proprietary |
| Conversation model | Reconstructs lifecycle from several Blaine surfaces | Native Agent/Conversation/Session | Native |
| Streaming, tools, approvals | Custom polling | SDK stream; `DecisionPanel` for approvals | Full |
| Artifacts/diffs, memory UI, multi-conversation navigation | Unknown | Minimal: sidebar sessions; no memory UI | Full (Letta app) |
| Task visualization | Custom, drifting from ACP | None; would come from projected messages | None |
| Portability | Web? | Electron (macOS/Linux) | Desktop apps |
| Maintenance/upstream | Fork divergence | Stale upstream; effectively owned by Blaine after fork | Vendor-controlled |

**Conclusion.** Neither UI codebase is a production starting point. The decisive
change is the backend contract, not the UI.

Once Task state is *projected into the conversation stream*, any client that
renders a Letta conversation (messages, tool calls, approvals) shows Blaine work
correctly without knowing Blaine's APIs. That removes the root cause of the Atomic
problems. The frontend reconstruction and multiple polling paths exist because the
UI had to assemble conversation semantics from Task surfaces.

For the spike, use `letta-oss-ui` or the Apache-2.0 React chat template pointed at
the App Server as a **throwaway** client. Decide the long-term UI afterwards. It is
most likely a small Blaine-owned client on the Agent SDK `/client` entry, borrowing
from the React template (clear license).

---

## 15. Channels and multi-device recommendation

| Capability | Status | Category |
| --- | --- | --- |
| Telegram, Slack, Discord, Signal, WhatsApp | Bundled in letta-code; "beta"; local backend only | Available today, self-host compatible, Apache-2.0 code |
| Custom channels | Plugin directory contract | Available; example-grade |
| Same conversation across desktop, IntelliJ, Telegram | Route `(channel, chat[, thread]) → (agent, conversation)`; ACP `session/load` by conversation id; runtime multi-subscribe | Available in local mode through Blaine's gateway and bridge |
| Browser/mobile (chat.letta.com) | Requires Letta sign-in; not for local-only agents | **Cloud-only** |
| Desktop app | Binary; source not public | Unverified with local-only agents; not reusable code |
| Computers (multi-device tool execution) | Outbound connection to Letta Cloud | **Cloud-only; reject** |

**Multi-device.** Keep Blaine's workstation model: tsnet/Tailscale admission,
E0.D identity and presence, and IDE-delegated providers under PolicyGate. Letta's
"computer" overlaps in name only. It routes a Cloud agent's tool execution to a
machine; it does not model device trust, workstation identity or workspace
authority. Adopting it would move device routing into Letta Cloud and execution
outside PolicyGate. **No part of Blaine's workstation model is replaced.**

**Channels** are the cheapest high-value win after the spike. Enable one channel
(Telegram) with pairing, only for conversations whose Project sharing policy
permits third-party egress. Delivering conversation text to Telegram is egress of
Blaine content to a third party. Credentials follow ADR 0023 (materialized locally
as `0600`), not ad-hoc keyring storage.

---

## 16. Deployment topology

### Topology A: Letta App Server as a separate local service on the Hub host (recommended)

- **Processes**:
  - `letta server --backend local --listen ws://127.0.0.1:<port>` under user
    systemd, alongside the existing Blaine services;
  - Blaine controller + projector;
  - Blaine gateway;
  - Blaine ACP bridge.
- **State**: Letta local directory (transcripts, agent/conversation JSON, MemFS
  git, channel config) on the Hub host; Blaine state unchanged; ConversationBinding
  in PostgreSQL (like E0.D).
- **Network**: App Server on loopback only. Clients reach the Blaine gateway (web
  UI) or bridge (ACP) over the tailnet. Channels poll outbound. The model endpoint
  is local vLLM. Telemetry is disabled and `letta.com` blocked at egress.
- **Credentials**: an App Server capability token held by the gateway, bridge and
  controller (ADR 0023 delivery); channel tokens the same way; no Letta account.
- **Backups**: add the Letta directory (files + git) to D1 backup coverage.
- **Failures**:
  - App Server down: conversations unavailable; Tasks continue; the projector
    buffers.
  - Blaine down: conversation works; `blaine_*` tools fail fast.
- **Upgrades**: pin the letta-code version. Upgrade only after gateway frame tests
  and the spike's regression checks pass.

### Topology B: Agent SDK embedded in the Blaine Personal Agent (SDK spawns the App Server as a subprocess)

- Same components, with the App Server as a child of the Blaine controller process.
- Fewer services. But multi-client attachment then depends on the controller's
  lifetime, and the App Server still exists (the SDK "starts App Server
  automatically as a subprocess").
- No real simplification. Use only for the spike.

### Topology C: App Server reachable over the private network, clients connect directly

- Clients (desktop UI on another machine) connect to the App Server over the
  tailnet with `--ws-auth capability-token`.
- **Reject as specified**: the socket carries file, terminal, memory, channel,
  secret and cron frames (§2.4). Any client with the token could operate the Hub
  host.
- Acceptable only through the Blaine gateway (frame allowlist), which makes it
  Topology A.

No public internet exposure is needed in any topology.

---

## 17. Security and trust-boundary implications

1. **App Server = host control plane.** Never expose it beyond loopback. Remote
   clients go through a Blaine gateway that allowlists frames (conversation
   CRUD/list, `input`, `sync`, approval responses, stream events) and drops file,
   terminal, memory-write, channel-config, secret, cron, provider and model-switch
   frames. Whether the App Server can disable those handlers itself is UNVERIFIED.
2. **Execution surface off**: `client_tool_allowlist` limited to Blaine tools on
   every turn (enforced by the gateway and controller); permission mode `strict`
   (the default is `unrestricted`); `LETTA_DISABLE_MODS=1`; no MCP pass-through.
   Treat any Letta upgrade that adds a new built-in path as a regression.
3. **Privacy**: `LETTA_CODE_TELEM=0` and `DO_NOT_TRACK=1`, plus an egress deny for
   Letta hosts. The default telemetry target is Letta Cloud even in local mode.
4. **Human authority**: only approval-gated `blaine_*` calls may carry human
   decisions (§9). A Letta approval attests "the human allowed this call", so the
   card must show the exact request/value. Blaine's typed validation remains the
   authority check.
5. **Workstation trust** is unchanged. Tailscale/tsnet admission and E0.D
   identity; Letta computers are not used.
6. **Model self-modification**: mods disabled; MemFS/reflection allowed only for
   authority-free conversational memory.
7. **Third-party egress** via channels is gated by Project sharing policy.

If items 1 or 2 cannot be enforced, the adoption hypothesis fails (§20).

---

## 18. Migration and deletion analysis (recommended carveout)

| Component | Classification | Reason |
| --- | --- | --- |
| PersonalConversation *(not inspectable)* | **REPLACE WITH LETTA** | Letta Conversation is the substrate. What remains is a thin `ConversationBinding` (Project, Task refs, delivery ledger). |
| BriefService *(not inspectable)* | **REFACTOR / UNDECIDED** | If a brief is "summarize my work lines", it becomes an agent turn over Blaine tools (`blaine_task_status`, `blaine_context_resolve`) in a conversation. Keep only if it produces governed, evidence-backed reports. |
| ResultDelivery *(not inspectable)* | **REFACTOR** into the conversation projector | Delivery stays a Blaine responsibility; the sink becomes the Letta conversation; duplicate protection moves to the projector ledger. |
| Atomic bridge/backend *(not inspectable)* | **DELETE** (if the spike passes) | Its role was reconstructing product semantics from backend surfaces. |
| Atomic fork *(not inspectable)* | **DELETE / FREEZE** | Superseded by any Letta-conversation client. Keep until a replacement client exists. |
| ACP adapter (`runtime/personal_acp.py`, `runtime/acp_agent.py`) | **REPLACE** with Blaine ACP bridge forked from letta-acp | The command grammar goes. Workspace-read fulfilment moves to the E1 capability path. |
| Go client, tsnet relay, handshake (`client/`) | **RETAIN** | Security and identity boundary. |
| Workstation registry/presence (E0.D) | **RETAIN** | No Letta equivalent without Cloud. |
| Personal Agent controls (`runtime/personal_agent.py`) | **RETAIN / WRAP** | Becomes the controller's backend for `blaine_*` tools. |
| MIRIX integration (`runtime/kernel/memory.py`) | **UNDECIDED** (freeze) | Re-decide after CP.2 (§12). |
| Context Plane | **RETAIN** (+ conversation source) | Not replaceable by Letta. |
| Task kernel, PolicyGate, Completion Contract, effects, evidence, Restate | **RETAIN** | Untouched. |

Net effect: the bespoke product plumbing (conversation store, delivery,
session/channel handling, UI backend reconstruction, command-grammar ACP) shrinks
to four small Blaine components: controller, projector, gateway and ACP bridge.
**New** Blaine code: those four plus `ConversationBinding`. Whether this is a net
reduction depends on the size of the unpushed PersonalConversation/Atomic code,
which could not be measured.

---

## 19. Minimal reversible spike

**Question to answer**: can Letta local mode be the durable conversation for
Blaine, with Blaine Tasks delegated from and projected back into it, across two
interfaces, with Letta's execution surface off, and without changing the Blaine
kernel?

**Upstream components (pinned)**

- `@letta-ai/letta-code` **0.33.1**
- `@letta-ai/letta-agent-sdk` **0.8.17**
- `letta-acp` at `5197491` (used unchanged in the spike, local only)
- `letta-oss-ui` at `d145c2b` **or** the React template at `ee47d20`, as a
  throwaway client

**Topology** (Hub host only; separate state directory via the local backend
directory env; separate port)

```text
throwaway UI ──┐
               ├─► letta server --backend local --listen ws://127.0.0.1:<spike-port>
IntelliJ via   │     (LETTA_CODE_TELEM=0, DO_NOT_TRACK=1, LETTA_DISABLE_MODS=1,
Blaine Go ─────┘      model = local vLLM via OpenAI-compatible provider)
client + tsnet               │ external tools
(host side runs              ▼
 letta-acp remote)   spike controller (Node, Agent SDK): blaine_task_create /
                     blaine_task_status / blaine_task_respond ──► existing Personal Agent
                     controls ──► Restate CognitiveTaskV1 (unchanged)
                     spike projector: poll inspect → input create_message with
                     client_message_id = H(task_id, state)
```

**Temporary seam**

- An experiment-only host ACP launch that runs `letta-acp --backend remote`
  instead of `personal_acp.py`, reached through the existing relay. E0.C already
  strips MCP and client fs capabilities.
- Use the existing D2 Task shapes (`summarize`, `decision`) so the kernel is
  unchanged.

**Success criteria**

1. Create conversation C in the UI. Chat without a Task. Ask for a `decision`
   Task. The agent calls `blaine_task_create`; exactly one Task exists in Restate.
2. Close the UI. The HumanDecisionRequest is projected into C exactly once.
3. Open IntelliJ and `session/load` C through the tsnet relay. History, including
   the projection, is replayed.
4. Answer in IntelliJ. The `blaine_task_respond` call requires human approval; the
   Task completes by its unchanged verifier.
5. The result is projected exactly once, even after killing the projector and
   restarting the App Server between completion and delivery.
6. Reopen the UI: the conversation continues from where IntelliJ left off.
7. **Zero** Letta built-in tool executions (transcript audit). **Zero** egress to
   Letta hosts (egress log). No Letta account.
8. Blaine `runtime/kernel/**` diff is empty.

**STOP criteria** (any one falsifies adoption as recommended)

- Built-in tools, mods or telemetry cannot be reliably disabled for every turn,
  including channel- and cron-originated turns.
- Local mode requires a Letta account or Cloud call for any criterion.
- The projection cannot be made exactly-once, or it triggers unbounded agent
  turns (projection → reply → projection loops).
- History is lost or corrupted by an App Server kill during a turn.
- IntelliJ `session/load` through the relay cannot resume C.
- A human response can reach Blaine without a human approval step.
- Any criterion requires a change to Task, PolicyGate or Completion Contract
  semantics.

**Must not be built**: production UI, Project model, ActivityTrack,
ConversationBinding schema beyond an in-memory map, Blaine gateway (verify
feasibility only), channels (Telegram is an optional stretch after 1–8 pass), MIRIX
or Context Plane changes, E1/E2 workspace effects through Letta.

**Cleanup/reversibility**

- Everything lives under `experiments/letta-conversation-spike/`.
- Separate Letta state directory and port; removing the directory and stopping the
  process restores the host.
- No change to deployed services, `infra/services/runtime.json` or systemd units.
- The ACP launch swap is experiment-only.

**Estimated footprint**: about 4–6 new files (controller ~200–300 LOC TS,
projector ~150 LOC, launch script, README, evidence JSON). Zero Blaine runtime
files changed.

**Decision it enables**: if 1–8 pass, stop Atomic, proceed to Alternative C design
(an ADR, ConversationBinding, gateway, ACP bridge). If a STOP triggers, fall back to
Alternative A with Letta as reference, and resume UI work with the protocol lessons
learned.

---

## 20. STOP criteria for adoption (beyond the spike)

- A Letta upgrade removes or renames the external-tool, allowlist or `sync`
  mechanisms that Alternative C depends on, with no migration path.
- Upstream makes local mode Cloud-dependent or drops it.
- Local transcript durability proves inadequate (corruption under crash) and cannot
  be mitigated by backups and pinned versions.
- Protecting the Hub requires a gateway so large that it re-implements most of the
  App Server protocol.
- The upstream license changes for letta-code or the SDK.

---

## 21. Unresolved questions

1. **Agent cardinality**: one Letta agent per Blaine Project (memory isolation, no
   cross-project bleed) or one personal agent with Project-tagged conversations
   (single identity, shared memory)? Letta shared-memory repos might support "one
   persona, per-Project agents". Not evaluated.
2. Can the App Server itself disable file/terminal/memory/channel frame handlers,
   or must the Blaine gateway filter them? Not verified.
3. Can a projection be appended **without** starting an agent turn (a notification
   rather than a user message)? `task_notification` exists as an internal queue
   source; its external availability is not verified.
4. Does the agent's memory editing require built-in file tools that the allowlist
   would disable? If so, conversational memory needs a narrowly allowed memory-only
   toolset.
5. Local-mode transcript crash semantics: the `rewrite` path frequency and exact
   triggers were not measured.
6. JetBrains ACP compatibility of letta-acp specifically (`session/load`, modes,
   permissions) is not live-verified.
7. Letta desktop app licensing and whether it can attach to a self-hosted App
   Server over a gateway: not verifiable here.
8. Size of the unpushed PersonalConversation/BriefService/ResultDelivery/Atomic
   code, needed for the net-deletion claim.
9. `docs.letta.com` content was only read through search extracts. Re-read the
   self-hosting, App Server integration-patterns, channels and external-tools pages
   before any decision.

---

## 22. Explicit answers and the Atomic recommendation

| # | Question | Answer |
| --- | --- | --- |
| 1 | Fully local/self-hosted for our subset? | **Yes for the conversation subset** (agents, conversations, history, compaction, App Server, channels, ACP, SDK) in local mode with a local model and no account. **No** for web/mobile access and computers (Cloud-only). |
| 2 | Which components are open source and reusable? | letta-code, letta-agent-sdk, letta-acp and the React template: Apache-2.0. letta-oss-ui has no license file (MIT-derived). Desktop and web apps are not public. |
| 3 | Is the OSS UI materially better than Atomic? | Better aligned (native conversation model), but not better as code: stale demo. The real gain comes from the backend contract, not the UI. |
| 4 | Can Letta Conversation replace ActivityTrack? | **Yes, for now**: `Project → Conversation → Tasks` with a Blaine reference record. Reconsider only on demonstrated multi-conversation work lines. |
| 5 | Reuse directly or wrap? | Wrap **by reference** (ConversationBinding), never by copying messages. |
| 6 | Can multiple interfaces attach/resume the same state cleanly? | Yes: multi-subscriber runtimes, `sync`, and conversation id as ACP session id and channel route target. OBSERVED/DOC; the spike verifies it. |
| 7 | Can IntelliJ/ACP join the same continuity? | Yes, through a Blaine ACP bridge forked from letta-acp over the existing tsnet relay. Not with letta-acp unchanged. |
| 8 | Can Telegram join without another conversation model? | Yes: channel routes point at the same `(agent, conversation)`. Beta; egress policy applies. |
| 9 | Does compaction/history satisfy long-lived needs? | Mostly. Full transcript retained; compaction summaries are additive. Durability caveats (non-atomic rewrite, no fsync) mean backups are required, and Task truth stays in Blaine. |
| 10 | Is Letta memory good enough to reconsider MIRIX? | For conversational memory, yes. For governed knowledge, no. Freeze MIRIX; re-decide after CP.2. |
| 11 | Does Letta's Computer overlap dangerously with workstation identity? | It would if adopted: Cloud-routed execution outside PolicyGate. Do not adopt it; no overlap then remains. |
| 12 | Can Letta and Restate coexist with crisp lifecycle ownership? | Yes: Letta owns conversational turns, Restate owns Tasks, and a projector Virtual Object owns only the delivery ledger. |
| 13 | Which Blaine code becomes unnecessary? | PersonalConversation (mostly), Atomic bridge and fork, the command-grammar ACP adapter, delivery plumbing. Kernel, PolicyGate, Contract, effects, Context Plane, transport and workstation code stay (§18). |
| 14 | Smallest falsifying experiment? | §19: one conversation, one delegated decision Task, projection exactly once, resume from IntelliJ through the relay, execution surface off, no Cloud. |
| 15 | Would Letta materially accelerate a coherent end-to-end Personal Agent? | **Likely yes** for conversation continuity, multi-interface attachment and channels (weeks rather than months), **if** the spike shows the execution surface can be kept off. It does not accelerate E1–E3 governed workspace work, which stays Blaine's. |

**Should Blaine pause further Atomic UI investment pending the spike? Yes.**

- Limit Atomic to fixes needed for current use.
- The spike is small (§19) and decides between two futures:
  - in one, the Atomic backend-reconstruction layer is deleted;
  - in the other (fallback to Alternative A), it must still be redesigned around a
    single conversation stream.
- Either way, further investment in the current Atomic integration shape would be
  discarded.
