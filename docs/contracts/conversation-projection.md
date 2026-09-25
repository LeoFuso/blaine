# Conversation Projection v1 — the product presentation contract

**Status: DESIGNED (PA-4, 2026-09-25).** Follows PA-3, whose live acceptance showed the
desktop deriving Task lifecycle, pending human requests, completion progress and delivery
state on its own from raw `inspect`/`events`, while `personal_acp` saw none of PA-3.

One backend projection per Conversation is the only thing a client renders. Atomic Chat is a
renderer of it; `personal_acp` maps the same projection into ACP. The raw Task APIs
(`/inspect`, `/task/<id>/events`, `/artifact`) remain for diagnostics and are **not** a
presentation contract.

The projection is **derived and read-only**. It owns no lifecycle, grants nothing, decides no
completion and never steers a Task. Restate, PolicyGate/grants and the CompletionVerifier stay
authoritative; the Personal Agent services stay the only writers of Conversation state.

## 1. Authoritative input sources

| Source | Owner | What the projection reads |
| --- | --- | --- |
| `conversation_messages` (encrypted) | `ConversationService` via `PersonalConversation`, `BriefService`, `ResultDelivery` | human/agent turns, `delegation`, `result` (`res-*`), follow-ups (`fup-*`) |
| `execution_briefs` (encrypted) | `BriefService` | proposed / confirmed / rejected briefs |
| `conversation_task_links` | `BriefService` (write-ahead), `ResultDelivery` (advance) | Task↔Conversation mapping and delivery state |
| Task control surface `inspect` | Restate `CognitiveTaskV1` | lifecycle, pending human decision, effect receipts, CompletionEvaluation |

Nothing else. In particular the retained event log is not needed for presentation, and no
model is ever called to build the projection.

## 2. State model

A projection is an ordered set of **entries**. Each entry has a stable `entry_id`, a `kind`,
a `seq` (see §3) and a kind-specific body. Entries are never deleted; an entry's body can
change (a Task progresses), and every change gives it a new `seq`.

| kind | entry_id | body |
| --- | --- | --- |
| `message` | message id | `role` (`human`/`agent`), `text`, `created_at` |
| `brief` | brief id | `status` (`proposed`/`confirmed`/`rejected`), `objective`, `deliverable`, `inspect`, `targeted_tests`, `constraints`, `requested`, `task_id?` |
| `task` | `task:<task_id>` | see below |
| `human_request` | `hr:<task_id>:<request_id>:<revision>` | `task_id`, `status` (`pending`/`resolved`/`closed`), `question`, `options` (allowed responses), `effect` (`{operation, target}` when it gates an effect) |
| `result` | result message id | `task_id`, `lifecycle`, `verifier`, `criteria` (`id`,`status`,`detail`), `changed_files`, `runs`, `diff`, `markdown` |
| `followup` | follow-up message id | `task_id`, `text`, `grounded` |

`task` body (closed vocabulary, facts only — never model reasoning):

```
task_id, brief_id, delegation_message_id, objective, deliverable,
phase:     submitting | running | waiting_human | completed | failed | cancelled | unavailable
lifecycle: the Restate lifecycle verbatim
steps:     ordered [{key, label, status: done|in_progress|waiting|failed, detail?}]
           from the brief admission, effect receipts (writes/runs, exit codes, conflicts)
           and the verifier; one step per effect operation
criteria:  {satisfied, total, items:[{id, status}]}   (CompletionEvaluation v2)
delivery:  pending | result_recorded | surfaced         (the link state)
revision:  Task state version (diagnostic)
```

`phase` is derived only as: link `submitting` → `submitting`; lifecycle `WAITING` with a pending
human decision → `waiting_human`; lifecycle `RUNNING`/`WAITING` → `running`; terminal
lifecycles map one-to-one; inspect unavailable → `unavailable` (the entry keeps its last
known facts and says so).

Every entry carries `order` = `[anchor, sub]`, its position key; clients that apply deltas
insert by it. Ordering: entries are listed in Conversation order — the `rowid` order of the message that
introduced them (a `task` entry sits at its `delegation` message; a `brief` entry at the last
message it was compiled from; a `human_request` directly after its `task`).

## 3. Cursor and idempotency

- The projection store keeps, per Conversation, one row per entry:
  `(conversation_id, entry_id, digest, seq)`, where `digest` is the SHA-256 of the entry's
  canonical body and `seq` comes from one store-wide monotonic counter.
- A read recomputes the current entries from the sources, and **in one short transaction**
  assigns a new `seq` to every entry whose digest changed (or is new). Unchanged entries keep
  their `seq`. No model call, no Restate write, no Conversation write happens inside it.
- `GET …/projection?after=<cursor>` returns the current body of every entry with
  `seq > cursor`, in Conversation order, plus `cursor` = the highest `seq` returned (or the
  request's cursor when nothing changed).
- Idempotent: the same source state never produces a new `seq`; two readers (the bridge and
  `personal_acp`) racing on the same change produce one bump (the transaction compares
  digests). Bodies are recomputed on read, so the table holds no content (no plaintext copy of
  encrypted history).
- A client applies entries by `entry_id` (replace), never by position.

## 4. Task-to-Conversation mapping

The only mapping is `conversation_task_links(conversation_id, task_id, message_id, brief_id,
state)`, written ahead of submission by `BriefService.confirm`. A Task appears in exactly the
Conversation that confirmed its brief. Other Tasks (ACP `summarize`/`decision`, probes) are
not projected into any Conversation.

## 5. Human requests

A pending `HumanDecisionRequest` of a linked Task becomes a `human_request` entry with the
Task's own `request_id`, `revision`, `question` and `allowed_responses`. When the Task no
longer waits on it, the entry becomes `resolved`; if the Task ended first, `closed`. Answers
go through the Personal Agent (`POST …/respond`), which builds the `HumanDecisionResponse`
envelope from the Task's *current* pending request; a stale `request_id` is refused. The
projection never answers anything.

## 6. Result delivery

Delivery stays with `ResultDelivery` (staged, idempotent, outside transactions around
inference). The projection shows it as: the `task` entry's `delivery` field, the `result`
entry (deterministic facts, `res-*`) and the `followup` entry (`fup-*`). A client never
builds, injects or marks a result.

## 7. Reconnect and replay

- `after=0` returns the full current projection (latest body of every entry) — the replay a
  reloaded window or a new ACP session starts from.
- A client that kept its cursor resumes with `after=<cursor>`; because `seq` only grows and
  every changed entry is re-emitted with its full body, no event can be missed and none needs
  to be replayed twice.
- Restarting the bridge or `personal_acp` loses nothing: the sources are durable, the digest
  table is durable, and bodies are recomputed.
- Transport v1 is polling (UI every ~2 s; ACP inside a turn). SSE/WebSocket may replace the
  poll later without changing entries or cursor semantics.

## 8. Desktop (Atomic Chat) mapping

| Entry | Rendering |
| --- | --- |
| `message` | the transcript's own turns (not re-rendered; ids match) |
| `brief` `proposed` | Execution Brief card (Execute / Discard) |
| `task` | delegation message + lifecycle card from `steps`/`criteria`/`phase` (no client derivation) |
| `human_request` `pending` | approval card (options from the entry) |
| `result`, `followup` | transcript messages (result Markdown + diff) |

"Execute" is disabled while any `task` entry is non-terminal or a `brief` is `proposed`.

## 9. ACP (IntelliJ) mapping

One ACP session is attached to one Conversation (`acp-<session>` by default; `/conversation
<id>` attaches an existing one, e.g. the desktop's). Each prompt turn first emits the entries
since the session's cursor, then handles the prompt, then emits again.

| Entry | ACP |
| --- | --- |
| `message` agent / `followup` | `agent_message_chunk` text |
| `brief` `proposed` | `agent_message_chunk` summary + "reply `/execute confirm`" |
| `task` | one `tool_call` per Task (`tool_call_id` = task id, status `pending`/`in_progress`/`completed`/`failed`) and an `plan` update from `steps` |
| `human_request` `pending` | `session/request_permission` on the Task's tool call, one option per allowed response (`allow_once` for APPROVE, `reject_once` for DENY); the selection is sent through the same `respond` path |
| `result` | `tool_call` update with the result Markdown as content |

Plain text prompts are conversation turns (`PersonalConversation`); `/execute` proposes a
brief, `/execute confirm` confirms the latest proposed brief, `/wait` follows the projection
inside the turn until the Task needs the user or ends (bounded). The existing D2 command
syntax (`summarize …`, `inspect …`, `task {…}`) remains for diagnostics.

## 10. Non-goals (v1)

No push transport, no multi-Conversation feed, no projection of non-delegated Tasks, no
client-side authority, no Memory writes, no change to Task, contract or verifier semantics.
