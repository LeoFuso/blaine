# PA-4 — Canonical conversation projection (desktop + ACP render one contract)

**Status: PASS (2026-09-25) for the bounded increment.** Contract:
[conversation projection](../../../docs/contracts/conversation-projection.md);
decision: [ADR 0028](../../../docs/decisions/0028-conversation-projection-is-the-presentation-contract.md).

## What changed

- `runtime/personal_projection.py` builds, from the encrypted Conversation store and the
  Task control surface only, the ordered entries clients render (messages, briefs, Tasks
  with phase/steps/criteria/delivery, human requests, results, follow-ups). Read-only,
  no model call; the store keeps digests + a monotonic cursor, no plaintext copy.
- `GET /conversation/<id>/projection?after=<cursor>` on the bridge; the services
  composition root (`runtime/personal_services.py`) is shared by the bridge and
  `personal_acp`.
- `personal_acp`: plain text = conversation turn; `/execute`, `/execute confirm|discard`,
  `/approve|/deny`, `/status`, `/wait`, `/conversation <id>`; Tasks rendered as ACP tool
  calls + plan, human requests as native `session/request_permission`, results as tool-call
  content, follow-ups as messages. D2 control syntax kept for diagnostics.
- Desktop (`blaine-ui`): one projection poll replaces the PA-3 watchers; the UI no longer
  derives Task lifecycle, human requests, progress or delivery from raw `inspect`/`events`.

## Live validation (ADR 0028 minimal validation)

One delegation, started from an ACP session (the real `~/.local/bin/blaine-agent`, driven by
[acp_probe.py](acp_probe.py)) attached to the desktop Conversation `6a0a06fe-…`, answered in
the desktop, followed to completion from ACP:

| Step | Evidence |
| --- | --- |
| ACP: conversation turn, `/execute`, `/execute confirm` | Task `task-44bf5b03…` created from brief in the desktop Conversation |
| ACP: `/wait` → `waiting_human` → native permission request | left pending by the probe (the human decides in the desktop) |
| Desktop: same Task card (`WAITING`, "Approval requested: write …") and approval card | operator pressed Approve; `submit_human_response` at 03:32:07Z |
| Task | write `/5` applied, `pa3-targeted-tests` exit 0, `pa3-completion-contract-suite` exit 0, verifier 5/5 ([inspect](evidence/acp-started-task.inspect.json)) |
| ACP `/wait` | same steps, `completed`, result + follow-up rendered from the same entries |
| Projection replay | [after=0](evidence/projection-after-0.json): 28 entries, cursor 73, the whole PA-3/PA-4 history (message text as digests only) |

Deliverable after the ACP-started Task: [file](evidence/deliverable-after-acp-task.py) (5 tests, pass).

## Findings fixed during the increment (live)

| Finding | Fix | Commit |
| --- | --- | --- |
| Every conversation turn in a Conversation with Tasks failed (HTTP 400): a second system message, rejected by the Qwen template | status merged into the single system message | `9ab38be` |
| A read of a 15 KiB source file overflowed the 16 KiB cognition packet and failed the Task | cognition gets a bounded excerpt; the whole file stays the admitted artifact | `6056b98` |
| Extending a delivered file was refused: readable paths excluded writable paths | readable = inspect + allowed paths | `c101541` |
| Result diff of an extended file claimed every line as added | diff against the admitted pre-write artifact (digest match) | `e02a7ea` |

## Verification

Targeted core suites (`test_personal_projection`, `test_personal_acp_projection`,
`test_personal_pa3`, `test_pa3_workflow`, `test_personal_agent`, `test_personal_http_*`,
`test_kernel_conversation`, workflow/effects/completion/context-plane suites) — OK.
Desktop: `blaine-projection` + transport + card Vitest specs, `tsc -b` — OK.

## Gaps (recorded)

- Transport is polling (desktop 2 s, ACP inside a turn); unsolicited ACP updates between
  turns are not sent. SSE/WebSocket later, same entries and cursor.
- ResultDelivery still runs only in the bridge process; with the bridge down, ACP renders
  but results are not delivered.
- Results delivered before `e02a7ea` keep their original (over-reported) diff; the
  Conversation is append-only.
- IntelliJ itself was not driven in this increment (human-attended track); the ACP adapter
  was exercised through the real `blaine-agent` over stdio.

## Checkpoint — frozen (2026-09-25)

- **PA-3: PASS — real coding delegation.** **PA-4: PASS — canonical conversation projection.**
  Both are historical POC results, frozen as recorded here and in
  [PA-3](../pa-3/README.md); their evidence is not to be rewritten.
- PA-4 proved an invariant that is retained: **product lifecycle projection must be
  backend-owned and shared by all surfaces.** Its specific implementation
  (`PersonalConversation`, `ConversationProjection`, the Personal Agent bridge and
  conversation store) may be superseded.
- Feature development on the Atomic Chat surface, the conversation service, the projection
  and the bridge is paused. The conversation/session/runtime implementation is under
  architectural review.
- The next investigation is Letta as a possible conversation/session substrate. No
  conclusion from that investigation has been adopted.
- Runtime at freeze: the POC-only debug desktop app and the manually started bridge were
  stopped; the canonical `blaine-runtime`/`blaine-restate` user services were left running
  with the code staged during PA-3/PA-4 (no unit or configuration change at freeze).
- Uncommitted by design: `tests/test_human_response_bounds.py` in the acceptance worktree
  `blaine-pa3-target` (branch `pa3/acceptance-target`) — the verified deliverable of Task
  `task-44bf5b03…` (sha256 `c889dc36981fdd5b2d7bbbd30391cab80772c39c2feb86bfd2a7355917bc941c`,
  2439 bytes, 5 tests). Left for the operator to decide.
- `pa-3/evidence/durability.log` is committed with `--force` at freeze (it was ignored by
  `*.log` although the PA-3 README cites it); content unchanged.
