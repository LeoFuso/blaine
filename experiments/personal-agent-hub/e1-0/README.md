# E1.0 — Completion Contract kernel

**Status: PASS (2026-09-24; operator clarifications applied and re-accepted the same day).** Kernel only: no workstation, IDE, MCP, provider,
model or network path. ADR 0026 moves to Accepted / Partially Validated (Integration
PASS; end-to-end inside E1 acceptance pending). ADR 0027 is untouched and remains
Unvalidated. E1 as a whole is **not** PASS; E1.A–E have not started.

Branch `impl/e1-completion-contract`, based on `b1b3073` (ADRs 0026/0027 accepted).
Contract: [Completion Contract v1](../../../docs/contracts/completion-contract.md),
including its [implementation status](../../../docs/contracts/completion-contract.md#implementation-status-e10)
and [E1.0 clarifications](../../../docs/contracts/completion-contract.md#e10-implementation-clarifications).

## What runs

- **Storage:** contract revisions, amendments, amendment requests (the retained human
  action), `CompletionEvaluation` v2, capability journal entries, `EffectiveAuthority`,
  read receipts and semantic review packets/results are immutable content-addressed
  artifacts. `TaskState` gains only `contract_ref`, `contract_revision`,
  `authority_ref`, `journal_head`, `journal_length` and `semantic_reviews` (refs).
- **Revision 0** is retained before any effect: the lowered `TaskSpec.completion`
  (`c1..cN`, REQUIRED, `user` or `parent_task`) or a trusted envelope contract that
  carries those lowered criteria unchanged.
- **Provenance:** only `task_type`, `operator_rule`, `project_policy`, `user`,
  `parent_task` can create REQUIRED criteria; `repository`, `memory`, `model` are
  ADVISORY. `project_policy` needs a designation ref and pinned source digest.
- **Journal:** `denied`/`admitted`/`observed` entries appended by the workflow on the
  single dispatch path, admission before dispatch, hash-chained by `previous_ref`.
- **No mutation** = no unauthorized TARGET_EFFECT (`no_target_effect`). The Task's
  INTERNAL_EFFECTs (state, journal, artifacts/evidence, human requests, evaluations,
  local computation, semantic-review packets) and TARGET_READs never violate it.
- **Terminal vs remediable:** only a gating, unwaivable (`task_type` invariant),
  monotonic (`capability_journal`) failure ends the Task FAILED at once; any other
  failed REQUIRED criterion blocks COMPLETED while the Task keeps working.
- **Verifiers:** `artifact_digest`, `human_response` (optional `accept`),
  `capability_journal`, `evidence_citation` (`InvestigationFindings@1`, exact quoted
  spans in admitted receipts), `semantic_review` (interface and deterministic
  admission; stub reviewers only), `unbound`.
- **Legality:** `settle()` is the only path to COMPLETED; `completion.legality` checks
  the current revision, fresh evidence/journal, REQUIRED statuses, unbound criteria,
  outstanding human waits, journal integrity/authority and waiver authority.
- **Amendments:** `amend_contract` takes a binding envelope — the actor established
  by the authenticated binding around content with no authority field (the Personal
  Agent's `amend` always establishes the user) — with the authority matrix, compare-and-set on
  revision-named one-shot promises (`peek` verified on SDK 1.0.5/server 1.7.9),
  idempotent retries, application at iteration boundaries and during human waits.
- **Human boundary:** the existing `human.request` capability, HumanDecision contracts
  and `submit_human_response`; no new queue. The same Task resumes.

## Required cases

| # | Case | Deterministic tests (`tests/`) | Real Restate (`accept.py`) |
| --- | --- | --- | --- |
| 1 | Revision-0 compatibility, verbatim intake | `test_completion_contract` Intake, RevisionZero, V0Parity; all 249 pre-existing tests | `human-resume` (v0 TaskSpec); child lowered with `parent_task` provenance |
| 2 | REQUIRED blocks until satisfied | Legality; workflow `test_model_complete_is_neither_necessary_nor_sufficient` | `investigation` |
| 3 | ADVISORY does not block | Legality `…advisory_does_not`; `test_cited_findings_complete…` | `irrecoverable` concerns |
| 4 | Deterministic PASS | `test_cited_findings_complete_and_result_explains_why` | `investigation`, `denial` |
| 5 | Deterministic FAIL | Citation, Journal; `test_fabricated_quote_fails…` | `investigation` (fabricated first) |
| 6 | Unresolved / UNKNOWN | `test_corruption_is_unknown_not_pass`, unreadable journal, low-confidence semantic | — |
| 7 | Human verifier → WAITING → same Task | `test_v0_human_criterion_waits…`, `test_required_semantic_escalates_to_human…` | `human-resume` (runtime + server SIGKILL while waiting) |
| 8 | Explicit amendment | Amendments; `test_user_waiver_during_human_wait…`; add/bind in Revisions | `human-waiver`, `policy-exception` |
| 9 | Unauthorized amendment rejected | `test_authority_matrix`, `test_payload_cannot_claim_or_upgrade_the_actor`, `test_cognition_cannot_change_the_contract`, Personal Agent `test_amendment_actor_is_established_by_the_binding_not_the_request` | invariant waiver via the Personal Agent 403; forged operator actor through the binding 400; bare content 400; model actor 400 |
| 10 | Non-waivable invariant | authority matrix, supersession; `TerminalOrRemediable`; `test_admitted_mutation_fails_the_invariant_irrecoverably` | `irrecoverable`, invariant waiver 403 |
| 11 | Project policy / exception, pinned | `test_project_policy_requires…`, `test_policy_requirements_stay_pinned_to_their_source_digest` | `policy-exception` (user 403, user naming the rule 400, edited-policy digest 403, pinned exception applied) |
| 12 | Concurrent amendment conflict | `test_amendments_are_authorized_compare_and_set_and_idempotent` | two concurrent HTTP amendments: one 200, one 409 |
| 13 | Duplicate evaluation/result idempotent | `test_duplicate_results_are_admitted_once`, reproducible evaluation refs | duplicate workspace result/human response 409; `ALREADY_SUBMITTED` |
| 14 | Crash/replay preserves state | `test_crash_and_replay_reproduce_identical_durable_state` (journaled replay stand-in) | 5 runtime + 2 server SIGKILLs; journal prefixes byte-identical |
| 15 | Evidence citation success | Citation; `test_cited_findings…` | `investigation` |
| 16 | Invalid citation fails | Citation (quote, lines, path, unadmitted receipt, schema) | `investigation` |
| 17 | Journal no-effect verification | Journal, NoMutation (internal effects and reads pass; target effect fails); `test_policy_denial_is_journaled_and_reported` | `denial` (denied, no dispatch), `irrecoverable` |
| 18 | Semantic cannot override deterministic failure | SemanticStatus; `test_semantic_review_cannot_override…` | stub reviewer in `investigation` |
| 19 | Legality uses the current revision | stale-revision blockers; `test_legality_uses_the_current_revision` | `human-waiver`, `policy-exception` (revision 1) |
| 20 | TaskResult links to durable evidence | chain walk and offline recomputation | offline `verify()` for every Task |
| + | Remediable failed criterion does not fail the Task | `Remediable.test_a_failed_test_criterion_is_remediable`, `…_waivable_journal_criterion_failure_is_not_terminal` | `investigation` (fabricated quote, then completes) |
| + | Frozen-harness classification hides no regression | `test_regression_coverage` (every frozen property resolves to a live test or acceptance check) | `denial/outcome/4` (HANDOFF recovery), `policy-exception/stale-input`, `response-loss`, `child-parent` + child human wait |

## Evidence

- [`evidence/summary.json`](evidence/summary.json) — PASS; 9 Tasks (including a joined
  child waiting on a human); per-Task criteria statuses, journal phases, concerns,
  revisions; 18 cognitive turns and 17 capability executions without duplicates
  (the one deliberate response-loss retry reused its committed effect), 3 semantic
  reviews; 8 runtime and 2 server SIGKILLs.
- [`evidence/checks.json`](evidence/checks.json) — handler responses for every
  negative and idempotency case; [`journal-prefixes.json`](evidence/journal-prefixes.json)
  — Restate `sys_journal` rows before each kill and after recovery.
- `evidence/*-final.json`, `*-result.json`, `artifacts/` — authoritative Task state,
  TaskResults and every referenced artifact; `verify()` recomputes each final
  evaluation from these alone.
- [`regression.json`](regression.json) — **gating:** unit suite 249 → 311 OK, this
  acceptance, and the Increment 12 Restate harness (PASS on branch and baseline).
  **Historical, non-gating:** the Increment 1, 2 and 5 harnesses. They are frozen
  milestone evidence whose fixtures predate verifier-first progression (milestone
  024) and fail identically on unchanged `HEAD`; each property they covered is mapped
  to a current gating test or acceptance check, and `tests/test_regression_coverage.py`
  fails if any mapping stops resolving. HANDOFF recovery, stale-input rejection,
  effect response-loss and child human waits were re-homed into this acceptance
  rather than editing the old scripts.

All fixtures are synthetic (`tests/completion_fixtures.py`, neutral names, no
credentials or live data). The semantic reviewer is a deterministic stub; its
verdicts are not model evidence.

## Reproduce

```sh
PY=/home/leofuso/workspace/blaine/.local/runtime-venv/bin/python   # restate-sdk 1.0.5
PYTHONDONTWRITEBYTECODE=1 $PY -m unittest discover -s tests -p 'test_*.py'
PYTHONDONTWRITEBYTECODE=1 $PY experiments/personal-agent-hub/e1-0/accept.py \
  --restate-server /home/leofuso/workspace/blaine/.local/bin/restate-server \
  --output "$(mktemp -d)/e10"     # loopback ports 38280/39270/39280/35322
```

`accept.py` refuses to start if its ports are taken, owns only the processes it
starts, and rewrites `evidence/`.

## Limitations (E1.0)

- Receipts come from the existing D2 exact-path read (`acp-client`/`read_file`,
  whole-file range); IntelliJ MCP receipts, `intellij-mcp@1` classification,
  `DelegationSnapshot` and the full `EffectiveAuthority` are E1.C.
- Only `InvestigationFindings@1`; explanation/location schemas and task-type
  templates are E1.D. `capability_result` (E2) and `change_set` (reserved) are rejected.
- No real semantic reviewer is deployed; E1.D may add a local one.
- Amendments are applied immediately during human waits, but during workspace, text
  and child waits only when the wait resumes.
- Cognition cannot add ADVISORY `model` criteria or raise a typed waive/amend/fail
  request for an impossible criterion; both are deferred until a consumer exists.
- The actor is established by the calling binding, like `submit_human_response`. The
  Personal Agent binding (user only) has `amend`, but the ACP grammar does not expose
  it; no operator or policy-synchronisation binding exists, so the acceptance acts
  as a labelled operator fixture binding (`e10-operator-fixture`).
- Project-policy designations and operator rules are validated for shape and pinned
  digest only; their store and verification belong to contract synthesis (E2/E3).
- The deterministic replay stand-in in `tests/completion_harness.py` is not
  durability evidence; `accept.py` on the real server is.
