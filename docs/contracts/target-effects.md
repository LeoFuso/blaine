# Target effects — provider-independent contract (E2.0)

**Status: IMPLEMENTED in the kernel (E2.0 PASS, 2026-09-24) with a deterministic
fixture provider only.** No real provider, IDE, filesystem target or process is
connected; the IntelliJ MCP mapping, dirty-buffer handling, confinement at access
time, environment control and descendant cleanup remain E2.A–E2.D gates. Evidence:
[`experiments/personal-agent-hub/e2-0`](../../experiments/personal-agent-hub/e2-0/README.md).

This contract turns the recommended semantics in the Hub design
([E2 write semantics](../personal-agent-hub.md#e2-write-semantics),
[E2 exec semantics](../personal-agent-hub.md#e2-exec-semantics),
[evidence and completion](../personal-agent-hub.md#evidence-and-completion), Q11/Q12/Q14)
into a kernel boundary that any provider must meet. It extends the
[Completion Contract](completion-contract.md) and the E1
[workspace capability](workspace-capability.md#extension-to-e2-and-e3); it adds no
second lifecycle, approval queue or policy engine.

## Principle

An effect is never "the model asked, the tool said success, so it is done":

```text
intent (cognition proposal)
  → authority admission (PolicyGate; journal: admitted | denied)
  → deterministic lowering (EffectRequest: identity, precondition, digests)
  → [approval, when the grant says ask_before]  (existing human boundary)
  → dispatch recorded (journal: dispatched)
  → provider attempt (journaled Restate step; query-first, idempotent)
  → receipt, or explicit uncertainty (journal: observed)
  → reconciliation of uncertainty (journal: reconciled)
  → verification (capability_journal, change_set, capability_result)
  → Completion Contract legality
```

## Kernel boundary

Semantic capabilities only. A provider adapter maps them onto concrete tools later.

| Capability | Operation | Class | Effect scope |
| --- | --- | --- | --- |
| `workspace.read` (form `file`) | `read_file` | `workspace.read` | TARGET_READ |
| `workspace.write` | `write_file` | `workspace.write` | TARGET_EFFECT |
| `workspace.exec` | `run_profile` | `workspace.exec` | TARGET_EFFECT |

The trusted grant (envelope data, never TaskSpec data) may name `workspaces`,
reviewed exec `profiles` (by id) and `ask_before` classes. At intake the selected
profile definitions are **pinned** into `EffectiveAuthority` (with their digests
in each request), so a later profile change cannot silently alter a running Task.
A grant naming an unreviewed profile is rejected at intake.

## Effect identity

One logical effect = the existing capability `operation_id` (`<task>/<iteration>`,
the decision identity) plus the `EffectRequest` digest. No new identifier system.

- A provider must treat `dispatch` as idempotent per `operation_id` and digest: a
  repeat returns the existing receipt and never re-executes; the same identity with
  a different request is rejected.
- The kernel's attempt step **queries first**: if the provider already holds a
  receipt for the operation (a crash after commit, before Restate journaled the
  step), it is recovered (`delivery: recovered`) instead of executing again.
- A retry after a conflict, NOT_APPLIED or failure is a **new** intentional effect:
  a new decision, a new `operation_id`, a new precondition.

## Conditional writes

`workspace.write {workspace_id, path, precondition, content_ref}`:

- whole-file UTF-8 create/replace of a confined workspace-relative path (no
  absolute, parent, URL, NUL or backslash paths); ≤ 64 KiB; no delete, rename,
  chmod, binary or patch engine;
- content comes from an admitted Task artifact (`content_ref`), so the exact bytes
  are evidence before the effect;
- `precondition` is exactly one of `{"absent": true}`, `{"sha256": …}` or
  `{"receipt": <admitted read receipt>}`. A receipt precondition lowers
  deterministically to that receipt's content digest, after checking it is a
  whole-file read of the same workspace and path admitted by this Task. File
  mtime is never a precondition.

The provider must check the precondition and commit atomically and re-read the
committed bytes. Receipt states: `applied` (before = precondition, after = content
digest, readback = after) or `conflict` (before ≠ precondition, nothing written).
A receipt that contradicts its request is not admitted; the effect is uncertain.
**A conflict is remediable**: the Task re-observes, re-plans and proposes a new write.

## Bounded execution

`workspace.exec {workspace_id, profile, args?}` runs a reviewed profile: exact
executable (no shell text), fixed args plus allowlisted extra args, deadline,
poll interval, output cap and `environment: minimal`. The request pins the profile
id and digest and the exact command.

Lifecycle: the provider returns `running`; the kernel supervises on Restate
durable timers, polling the receipt, until one of:

| Ending | Receipt state | Notes |
| --- | --- | --- |
| process ends | `completed` (exit code or signal, output ref and digest, truncation, structured `result`, cleanup) | exit code is data; `capability_result` judges it |
| deadline | `timed_out` (`started: true`, cleanup stated) | a recorded non-success, never permission to wait longer |
| requested stop | `canceled` (`started: true`, cleanup stated) | see cancellation |
| never started | `not_started` / `rejected` | provably no process |

Output is stored as an artifact; the journal and receipts carry references and
digests only. An exec is never replayed on reconnect.

## Cancellation

`cancel_effect {operation_id}` (a steering signal through the binding; one-shot
per operation). Its receipt means the request was recorded, not that anything
stopped.

| Situation | Result | Did the effect happen? |
| --- | --- | --- |
| canceled while awaiting approval, before dispatch | `not_dispatched`, no `dispatched` entry | **No** (proven) |
| provider confirms the stop | `canceled` (or `timed_out`) with `started`, `cleanup` | Possibly partly; never "did not happen" |
| provider completed first | its `completed` receipt wins | Yes |
| stop not confirmed / provider unreachable | `uncertain` | Unknown → reconcile |

## Uncertainty and reconciliation

`uncertain` is recorded whenever the kernel cannot know the outcome: the reply was
lost after dispatch, the provider was unreachable, its answer was invalid, or a
stop was not confirmed. Uncertain is neither success nor failure. It is reconciled
immediately and again at every iteration boundary, never by redispatch:

| State | Evidence required |
| --- | --- |
| `APPLIED` | the provider's receipt **for this operation** (terminal state) |
| `NOT_APPLIED` | the provider's authoritative statement that the operation never ran |
| `DIFFERENT_STATE` | the target matches neither the precondition nor the intended content |
| `STILL_UNKNOWN` | anything else — including a target that already equals the intended content (a matching hash does not prove who wrote it) or a process still running |

While any target effect is uncertain, **PolicyGate admits no new target effect**
for the Task. Reads, internal work and waits continue. `DIFFERENT_STATE` closes the
uncertainty for planning (re-observe), but the effect's own outcome stays unknown
for verification.

## Journal

For every target effect the capability journal reconstructs: `admitted` (or
`denied`), `dispatched` (request ref and digest, approval ref), `observed`
(`success` | `failure` | `uncertain` | `not_dispatched`, receipt ref), and
`reconciled` (state, evidence ref, receipt ref). Integrity is checked: no dispatch
without admission, no observation of a lifecycle effect without dispatch (except
`not_dispatched`), no reconciliation without uncertainty. The journal holds refs,
never content or output. It remains the authority for "no unauthorized target
effect" (`no_target_effect`) and adds `effects_reconciled`, which is `unknown` while
an effect is unreconciled.

## Verifiers

- **`change_set@1`** `{workspace_id, predicates}` — the net change of admitted
  writes in one workspace, from receipts: `changed {paths}`, `expected_content
  {path, sha256}`, `only_paths {allowed}` (exact paths or `dir/` prefixes),
  `evidence_complete` (before/after/readback and retained content). Git is not the
  definition; a diff may later be one more evidence source.
- **`capability_result@1`** `{operation_class, profile? | path? | operation?,
  predicates}` — the latest matching effect's structured receipt: `state`,
  `exit_code`, `result_field {field, equals}`, `resulting_digest`,
  `cleanup_confirmed`, `result_after_last_change` (no later possibly-applied write).
  Prose and model readings of output are never deterministic evidence; semantic
  judgement belongs to `semantic_review`.

Both are `pending` with no matching effect, `unknown` when the relevant effect is
uncertain, `failed` when a predicate is false (remediable), `satisfied` otherwise.

## Terminal versus remediable

| Situation | Treatment |
| --- | --- |
| write conflict | remediable — re-observe, new effect |
| failing tests / nonzero exit / timeout | remediable — `capability_result` failed; keep working |
| uncertain effect | neither pass nor fail — reconcile; new target effects refused meanwhile |
| a target effect the contract's invariant does not allow was admitted | terminal invariant violation — FAILED ([rule](completion-contract.md#terminal-versus-remediable)) |

## Approval

`ask_before: [workspace.write | workspace.exec]` in the grant compiles into
authority. An admitted effect of such a class publishes a deterministic
HumanDecisionRequest (`APPROVE`/`DENY`) naming the operation, target and request
digest, and waits through the existing `submit_human_response` boundary. The same
logical effect (same `operation_id`) dispatches on `APPROVE`; `DENY` or a
cancellation closes it `not_dispatched`.

## Not in E2.0

Real provider mapping (IntelliJ MCP `apply_patch`, terminal, run configurations),
dirty editor buffers, access-time confinement and link races, environment and
descendant-process control, profile/build-input hashing beyond the pinned profile
definition, Task-level cancellation of an in-flight effect, and a global legality
rule for unreconciled effects (contracts express it with `effects_reconciled`).
