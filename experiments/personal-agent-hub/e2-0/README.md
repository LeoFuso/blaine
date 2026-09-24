# E2.0 — Provider-independent effect foundations

**Status: PASS (2026-09-24; operator decisions on the lifecycle invariant and Task
cancellation applied the same day).** Kernel semantics only, proven with a deterministic
fixture provider (`tests/effect_fixtures.py`, SQLite). No real file, IDE, MCP call,
terminal or run configuration was touched. **E2 is not PASS**: E2.A–E2.D (real
provider contract, conditional write adapter, bounded exec adapter, live recovery)
have not started. ADR 0027 remains Unvalidated.

Branch `impl/e2-effect-foundations`, based on `origin/main` `f0a3ca5` (E1.0).
Contract: [target effects](../../../docs/contracts/target-effects.md).

## What runs

- **Identity:** existing `operation_id` + `EffectRequest` digest; query-first,
  idempotent attempts recover receipts after a crash instead of re-executing.
- **Conditional writes:** whole-file UTF-8, expected SHA-256 / absent / admitted read
  receipt; atomic compare-and-swap receipts `applied` / `conflict`; readback digest.
- **Bounded execution:** reviewed profiles pinned into `EffectiveAuthority`; durable
  timer supervision, deadline stop, output as artifact references.
- **Cancellation:** before dispatch (proven no effect), confirmed stop (`started`
  stated), completed first, unconfirmed stop (uncertain).
- **Uncertainty:** `uncertain` → reconciliation `APPLIED` / `NOT_APPLIED` /
  `DIFFERENT_STATE` / `STILL_UNKNOWN`; only a receipt proves APPLIED; new target
  effects refused while unreconciled.
- **Journal:** `admitted`/`denied` → `dispatched` → `observed` → `reconciled`, refs only.
- **Verifiers:** `change_set@1`, `capability_result@1`, `effects_reconciled`.
- **Approval:** `ask_before` → deterministic HumanDecisionRequest through the
  existing boundary; the same operation dispatches on APPROVE.
- **Lifecycle invariant:** never COMPLETED while an admitted TARGET_EFFECT is
  unresolved, independent of the contract; reads and internal effects excluded.
- **Task cancellation:** closes never-dispatched effects, stops or recovers active
  ones (query first, one stop request), reconciles once, retains a final evaluation;
  CANCELLED results name every effect's actual outcome, including STILL_UNKNOWN.

## Required cases

| # | Case | Deterministic tests | Real Restate (`accept.py`) |
| --- | --- | --- | --- |
| 1 | Authorized effect admitted | `test_conditional_write_and_verified_tests_complete_the_task` | `change` |
| 2 | Unauthorized effect denied before dispatch | `test_unauthorized_effects_are_denied_before_dispatch`, `Authority.test_proposal_is_not_authority` | — |
| 3 | Write with matching precondition | `Lowering`, `Receipts` | all completed Tasks |
| 4 | Changed target → conflict, no overwrite | `test_changed_target_conflicts_without_overwrite_and_a_new_effect_retries` | — |
| 5 | Retry uses a new effect identity | same; `test_unreachable_provider_reconciles_not_applied…` | `outage` (write `/6` after `/3`) |
| 6 | Identical retry after response loss not duplicated | `test_crash_after_commit_recovers_the_receipt_without_a_second_write`, `test_dispatch_is_idempotent…` | `response-loss` (one provider write after SIGKILL) |
| 7 / 8 | capability_result PASS / FAIL | `Verifiers.test_capability_result`; `test_failing_tests_are_remediable…` | `change` |
| 9 / 10 | change_set expected PASS / unexpected FAIL | `Verifiers.test_change_set` | `change` |
| 11 | No unauthorized target effect | `test_admitted_unallowed_target_effect_is_a_terminal_invariant_violation`, `JournalLifecycle` | every Task (`no-unauthorized-effect`) |
| 12 / 13 | Verifier command success / failure remediable | `test_failing_tests_are_remediable_and_a_later_run_completes` | `change`, `process-control` |
| 14 | Timeout before completion | `test_timeout_stops_the_process_and_is_not_success` | `process-control/4` (runtime SIGKILL mid-supervision) |
| 15 | Cancellation before dispatch | `test_cancel_before_dispatch_proves_no_effect` | `cancel-before-dispatch` |
| 16 | Cancellation with confirmed stop | `test_cancel_running_process_with_confirmed_stop`, `Cancellation` | `process-control/5` |
| 17 | Cancellation with uncertain outcome | `test_cancel_with_unconfirmed_stop_is_uncertain_until_reconciled` | `process-control/6` |
| 18 | Crash after effect, before result admission | `test_crash_after_commit…` | `response-loss`, `change/dispatched/3` |
| 19 / 20 / 21 | Reconciliation APPLIED / NOT_APPLIED / UNKNOWN | `Reconciliation`; `test_lost_response…`, `test_unreachable_provider…`, `test_insufficient_evidence…` | `lost-reply`, `outage` |
| 22 | Human approval resumes the same Task and effect | `test_approval_waits_and_the_same_effect_continues` | `approval` (runtime + server SIGKILL while waiting) |
| 23 / 24 | Completion illegal while unresolved / legal once proven | `test_completion_is_illegal_until_effect_criteria_are_proven`, `test_insufficient_evidence…` | `outage` |
| 25 | Replay reproduces the same outcome | `test_crashes_and_replay_reproduce_the_same_outcome` | offline `verify()` for every Task |
| + | Invariant without an `effects_reconciled` criterion | `LifecycleInvariant`, `UnresolvedInvariantInput` (reads/internal excluded) | `task-cancel-unknown` final evaluation blocker |
| + | Task cancel before dispatch | `test_task_cancel_before_dispatch_closes_the_effect_as_never_dispatched` | `task-cancel-approval` |
| + | Task cancel of an active effect, confirmed stop | `test_task_cancel_stops_an_active_effect_with_confirmed_stop` | `task-cancel-active` |
| + | Effect completes before the Task cancel | `test_effect_completion_can_win_the_race_with_task_cancel` | `task-cancel-race` (no stop request) |
| + | Task cancel leaves STILL_UNKNOWN explicit | `test_task_cancel_keeps_a_still_unknown_effect_explicit` | `task-cancel-unknown` |
| + | Crash during Task cancellation, no duplicate stop/effect | `test_crash_during_task_cancellation_replays_without_duplicate_stop` | `task-cancel-active` (runtime SIGKILL mid-cancellation) |

## Evidence

- [`evidence/summary.json`](evidence/summary.json) — PASS: 11 Tasks, 40 cognitive
  turns, 22 provider executions, no duplicates, at most one stop request per
  effect; 7 runtime and 2 server SIGKILLs;
  per-Task criteria, effect statuses and journal phases, each final evaluation
  recomputed offline.
- [`evidence/checks.json`](evidence/checks.json), [`journal-prefixes.json`](evidence/journal-prefixes.json),
  [`executions.json`](evidence/executions.json) (provider-side execution log).
- [`regression.json`](regression.json) — per-suite classification (below), results
  and intended canonical execution.

## Verification classification

| Suite | Class | Why | Intended execution |
| --- | --- | --- | --- |
| `python-unit` (351 tests) | HERMETIC | in-process; fixture provider in temp SQLite | canonical HERMETIC suite; local and CI-eligible |
| `e2-0-restate-acceptance`, `e1-0-restate-acceptance`, `increment-12-parallel` | HERMETIC | each starts and owns an isolated restate-server and runtime from checkout tooling on its own loopback ports and fresh data dir; no shared host state, secrets or network | canonical HERMETIC durability suite; CI-eligible with a temp `--evidence` |
| Increment 1/2/5 harnesses | HERMETIC deps, HISTORICAL non-gating | frozen milestone evidence | excluded from gating discovery |
| `verify-kernel-model/-memory/-worker/-youtrack` | HOST | local inference, MIRIX, Goose, YouTrack | local Restate verification scheduler |
| E1.A–E, E2.A–D, E0 workstation matrices | FLEET | real IntelliJ workstation / peers | operator-scheduled |
| client release | CI_ONLY | GitHub release infrastructure | unchanged |

No GitHub Actions change: no canonical named-suite mechanism exists on `main` and the
Local Verification Scheduler has not landed, so a workflow now would be a second
command list. The classification above is what that integration should attach.

## Limitations

- Fixture provider only; provider obligations (idempotent dispatch, atomic CAS,
  authoritative receipt store, confirmed kill) are assumptions E2.A must prove or
  STOP on.
- No dirty-buffer handling, access-time confinement, link races, environment or
  descendant control, or build-input hashing beyond the pinned profile.
- An effect left STILL_UNKNOWN by a CANCELLED or FAILED Task is reported, not
  revisited later by the kernel.
- Neither `cancel_effect` nor effect approvals are exposed by a Personal Agent/ACP binding.
