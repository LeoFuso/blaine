# PA-3 — Real coding delegation (Personal Agent → durable Task → coding Worker)

**Status: PASS — accepted by the operator on 2026-09-24 with the evidence below; acceptance
frozen.** Branch `poc/pa-3-real-coding-delegation` (core) with main merged in (`d639158`);
the desktop surface is `poc/pa-3-real-coding-delegation` in `blaine-ui`.

## Acceptance criterion

> A user can discuss a code change with Blaine, explicitly ask it to implement the agreed
> work, and later receive the tested result back in the same Conversation without
> manually copying a prompt into a coding agent or copying the worker report back.

Met in the live desktop run: conversation `6a0a06fe-…`, Task
`task-71deb9e958a7313354d5eb809e0839f785f4d0b392fd40d75e57321c71bc67e1`
([inspect](evidence/live-ui-completed.inspect.json),
[conversation metadata](evidence/live-ui.conversation.json)).

## End-to-end flow (as run)

```
Blaine Desktop (Atomic-derived UI)
  └─ converse turns ──────────────► PersonalConversation (local Qwen, no Task)
  └─ Execute… ────────────────────► BriefService.propose  (ExecutionBrief v1, validated)
  └─ Execution Brief card: Execute ► BriefService.confirm  (write-ahead link → Restate create)
                                        │  grant/profiles/contract from operator coding policy
                                        ▼
                         CognitiveTaskV1 (Restate) — durable Task
  initial action: publish confirmed WorkerInput (c1 pins its digest)
  cognition (local Qwen): workspace.read → worker.run (Goose, toolless, file proposal)
     → workspace.write (ask_before → human APPROVE through /respond) → LocalWorktreeProvider
     → workspace.exec pa3-targeted-tests → workspace.exec pa3-completion-contract-suite
  CompletionVerifier: legality() over change_set@1 + capability_result@1 + invariants
                                        ▼
  ResultDelivery (bridge process): result message (res-*) → local-model follow-up (fup-*)
     → same encrypted Conversation → projected into the desktop transcript
```

## Live UI acceptance (Task `71deb9e9…`)

| Fact | Evidence |
| --- | --- |
| Human discussed, then pressed Execute… and confirmed the Execution Brief card | delegation `dlg-e335db2f…`, brief `brf-40435c1a…` |
| Brief → canonical TaskRequest; grant from policy (`blaine-pa3-target`, 2 profiles, `ask_before: workspace.write`) | `accepted_spec`, `contract` in the inspect evidence |
| Real repository edit in the dedicated worktree `blaine-pa3-target` | write `/13` applied, after `sha256 52f4895b…`; file copied as [deliverable](evidence/deliverable-test_human_response_bounds.py) |
| Targeted tests | exec `/14` `pa3-targeted-tests` exit 0 (4 passed) |
| Existing canonical HERMETIC suite via `verification.cli` | exec `/15` `pa3-completion-contract-suite` exit 0 |
| CompletionVerifier | `satisfied`, legal; all 5 criteria satisfied |
| Human requests answered in the approval card | `submit_human_response` ×4 on the Task |
| Result returned automatically to the same Conversation | `res-576dc813…` + `fup-576dc813…` (link `surfaced`) |
| Conversation usable while running | human turns during the run; replies continued |
| Bridge restarted mid-run (durability) | [durability.log](evidence/durability.log): killed 17:53:52 while RUNNING, restarted 17:53:58; delivery later completed exactly once |

Worker/model: Goose 1.50.1 (`--max-turns 1`, no tools) and cognition, both on local
`nvidia/Qwen3.8-27B-NVFP4` via vLLM `127.0.0.1:8000`. No cloud call.

A headless run through the same bridge also completed:
[smoke-4](evidence/headless-smoke-4-completed.inspect.json) /
[conversation](evidence/headless-smoke-4.conversation.json).

## Workspace-contention evidence (for the future resource-arbitration contract)

The live run started **three Tasks for the same file in the same worktree** within three
minutes (repeated Execute): `71deb9e9…` (COMPLETED), `3e713e8d…` (FAILED,
[inspect](evidence/live-ui-contention-failed.inspect.json)) and `b2a75cb0…` (CANCELLED
by the lead, [inspect](evidence/live-ui-contention-cancelled.inspect.json)). Observed:

- CAS writes kept every change honest: competing writes returned `conflict` receipts
  (`/7`, `/11` on the winner; `/4`, `/8`, `/13` on the loser) — no lost update, no
  overwrite of a verified file.
- The user experience was a "loop": every retried write raised a new approval request,
  from three different Tasks.
- A Task whose tests passed on another Task's file could still not complete
  (`change-made` needs its *own* applied write) — verifiers stayed correct.

Bounded response (not a lease): `BriefService.confirm` refuses a second Task on a coding
workspace whose delegated Task is not terminal; the desktop locks Execute while a Task runs.
Generic `workspace:<id>` claims remain FUTURE (see `docs/verification.md`).

## Findings fixed during the milestone

| Finding (live) | Fix | Commit |
| --- | --- | --- |
| Exec supervisor shadowed by the target repo's own `runtime` package → every run `canceled` | supervise from the provider's code root | `15664e5` |
| Exec observation said `success` for a failing run; exit code invisible to cognition | observation carries exit code/result/output artifact; non-zero ⇒ `failure` | `b3840ae` |
| Failing test output unreachable by the worker | latest profile output admitted as `output-<profile>` | `d1673b7` |
| One invalid cognition turn failed the Task (identical retries) | one bounded corrective re-prompt | `2e4a311` |
| Remediation step (read own evidence) denied | `artifact.read` granted | `0d5932b` |
| Goose text renderer truncated the proposed file | file mode reads Goose's JSON transcript | `180add3` |
| Rewrites used `absent` on an existing file; re-ran unchanged tests | target guidance: remediation path, conflict ⇒ read + receipt | `d22751f`, `180add3` |
| Personal Agent claimed a delegation that never happened; could not see Task state | delegations/results as `[System fact]`; per-turn read-only Task status | `d22751f` |
| Personal Agent drafted code for manual copy | prompt routes work through Execute | `d07f299` |
| Concurrent Tasks on one workspace | single-writer guard in `BriefService.confirm` | `1c4b7ef` |
| Bridge had no CORS; accepted non-JSON POSTs | origin-restricted CORS, JSON-only POSTs | `4428e46` |

## Verification

- Targeted core suites (runtime env, `PYTHONPATH=tests python -m unittest …`): kernel
  worker/context-plane/model/effects/completion/human/conversation, personal agent/http,
  `test_target_local`, `test_personal_pa3`, `test_pa3_workflow` (end-to-end workflow with
  the real provider and real processes), `test_personal_http_transport` — all OK.
- Canonical: `verification.cli run completion-contract --worktree .` → PASS on the core
  worktree; the same suite ran live inside the Task (`/15`).
- Deployment: staged through `infra/ansible/services.yml` (stage mode), `systemctl --user
  restart blaine-runtime`; bridge run from `~/.local/share/blaine/runtime/app`.

## Boundaries confirmed

Restate owns Task lifecycle; the CompletionVerifier alone completed the Task; PolicyGate and
envelope grants from the operator policy authorized every effect; the Personal Agent
compiled, confirmed-on-request, observed and interpreted but never executed; a
conversation turn never mutated a running Task; Atomic's agent loop, model picker and
`:1337` were never on the path; Memory/Track III, MIRIX and CP.2 were not touched.

## Known gaps (recorded, not blockers)

- The live Restate deployment kept its 2026-09-20 registration: main's `amend_contract` /
  `cancel_effect` handlers are not routable live (no force-registration over two suspended
  legacy invocations).
- HOST-bound qualification through the Restate Verification Scheduler is not integrated.
- The bridge has no systemd unit; it was started from the staged app.
- The desktop derives lifecycle, pending human requests and delivery state from raw
  inspect/events APIs; `personal_acp` does not use the PA-3 services at all. → next
  increment: a canonical backend conversation projection.
