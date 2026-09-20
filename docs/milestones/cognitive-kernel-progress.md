# Cognitive Kernel progressive program

**Current: Increment 11 PASS / CLOSED after the second explicitly authorized live probe.**

`frontier-live-binding-002`, dispatch `dispatch:frontier-live-binding-002/2`,
completed through the corrected Codex 0.155.1 binding. One non-fatal diagnostic was
retained, followed by explicit terminal success; exact projected output was admitted,
independently verified, and Task state reached COMPLETED. One dispatch, one successful
settlement, no pending reservation for this Task; no Blaine retry/fallback/escalation.
See [live PASS milestone](036-cognitive-kernel-increment-11-live-pass.md) and
[machine-readable evidence](../../experiments/kernel-increment-11/evidence/live-authorized-002/summary.json).
The historical `001` FAILED Task and pending UNKNOWN reservation remain unchanged.
Increment 12 has not started. Stop; separate continuation is required.

The entries below preserve previous checkpoints and their then-current next decisions.

**Current: Increment 11 Codex 0.155.1 offline correction PASSED; no new live dispatch.**

Version-specific exec semantics supplied from `rust-v0.155.1` resolve milestone
034's protocol uncertainty. The corrected binding requires terminal success, rejects
fatal/failed/missing/conflicting outcomes, and preserves non-fatal item errors as
ordered structure-only diagnostics. Kernel and settlement semantics are unchanged.
Historical milestones 033/034 and the original FAILED Task/pending UNKNOWN reservation
remain exact. See [correction milestone](035-cognitive-kernel-increment-11-codex-protocol-correction.md)
and [offline evidence](../../experiments/kernel-increment-11/evidence/codex-01551-correction/summary.json).
Next: explicit authorization for one fresh synthetic live probe with a new Task and
dispatch identity. Do not reuse the old receipt. Increment 11 remains open;
Increment 12 remains unstarted.


**Current: Increment 11 offline event diagnostic STOP; no additional live dispatch.**

The adapter rejected the original completed `error` item before result normalization.
Its body and ordering were discarded. Local CLI/package vocabulary does not establish
version-matched exec terminality semantics, so the adapter's acceptance rule remains
unchanged pending that evidence. Synthetic characterization also exposes acceptance
of failure-shaped top-level events and missing terminal events; it is not a new PASS
for the live binding. Historical milestone 033, FAILED Task and pending UNKNOWN
reservation remain unchanged. See [offline diagnostic](034-cognitive-kernel-increment-11-offline-event-stop.md)
and [machine-readable cases](../../experiments/kernel-increment-11/evidence/offline-event-diagnostic/diagnosis.json).
Next: approved local version-matched exec protocol definitions, or authorization for
a narrow official source lookup, before an adapter correction. No new cloud call;
Increment 12 remains unstarted.


**Current: Increment 11 live attempt STOP; exactly one worker dispatch, Task FAILED.**

The approved retry-domain and worker-bound-context clarification resolved the earlier
preflight restriction. A sterile Codex 0.155.1 / gpt-6-astra-intent dispatch returned
correct projected values but also an unexpected CLI error item; the adapter rejected
the result. Its error body was not retained, leaving the cause unresolved. Existing
CompletionVerifier found no admitted result artifact; no runtime completion was
claimed. One dispatch remains pending/unknown, with no retry, fallback or escalation.
See [live STOP milestone](033-cognitive-kernel-increment-11-live-stop.md) and
[machine-readable evidence](../../experiments/kernel-increment-11/evidence/live-authorized/summary.json).
Next: explicit approval for a narrow offline event-handling/capture diagnostic.
Do not rerun the live probe or clear its spent receipt. Any second live dispatch
requires new explicit authorization. Increment 11 is not ready to close; Increment
12 remains unstarted. The previous isolated PASS records remain intact.

**Current: Increment 11 live preflight STOP; zero live dispatches. Isolated gates remain PASSED.**

The user authorized the first synthetic live probe, subject to preflight. Installed
Codex 0.155.1 reports OpenAI/ChatGPT routing and model intent gpt-6-astra, but rejects
the attempted built-in-provider retry overrides. Zero automatic retry and exact
model-visible input remain unverified; no Task, grant, reservation or cloud call was
started. See [STOP milestone](032-cognitive-kernel-increment-11-live-preflight-stop.md)
and [machine-readable preflight](../../experiments/kernel-increment-11/evidence/live/preflight.json).
Next decision: a narrow offline binding diagnostic or explicit clarification of
native transport retry allowance. No production semantics changed. Increment 12
remains unstarted. Earlier PASS records below are isolated evidence only.

**Current: Increment 11 context-projection gate PASSED; STOP before live frontier work.**

Frontier authorization now requires a Blaine-produced immutable projection and binds
its exact outbound bytes. Dispatch rechecks the accepted grant before the adapter;
raw bypass, projection failure and later context substitution are rejected. The
identity production hook makes no sanitization/quality claim. 103 focused tests,
22 native Restate cases and 434 independently validated events passed; previous
A–J authority/routing/accounting guarantees remain intact. No cloud/model calls.
See [projection milestone](031-cognitive-kernel-increment-11-projection.md),
[current frontier contract](../contracts/frontier-dispatch.md), and
[summary](../../experiments/kernel-increment-11/evidence/projection/summary.json).
Next: human review/authorization of the proposed one-worker synthetic live probe,
including binding-specific preflight. Increment 12 remains unstarted.

**Current: Increment 11 revised isolated boundary PASSED; STOP before live frontier work.**

The authorized correction separates hard authority, economic suitability and observed
usage. Frontier v2 retains exact Task/context/scope/binding authorization, real worker
slots and replay protection; underlying model-call/token/cost caps are optional
binding controls rather than universal worker requirements. 98 focused tests and 19
native Restate cases passed; 356 ExecutionEvents independently verified. No cloud
calls or credentials were used. See [current milestone](030-cognitive-kernel-increment-11-revised.md),
[current contract](../contracts/frontier-dispatch.md), and
[machine-readable evidence](../../experiments/kernel-increment-11/evidence/revised/summary.json).
Next: human-authorized real-binding preflight/one bounded worker dispatch under the
revised model. Increment 12 is unstarted. Historical v1 results below remain valid
for their isolated scope; their universal per-Task token/dollar assumptions are
superseded by this authorized correction.

**Increments 8–10 PASSED. Increment 11 isolated boundary PASSED; STOP before live dispatch.**

The human-authorized isolated proof passed 96 focused tests and 14 native Restate
cases, including committed-effect restart, denial without provider execution,
durable budget ownership, timeout reservation and ExecutionEvent evidence.
No cloud inference, credential inspection or production kernel migration occurred.
See [Increment 11 milestone](029-cognitive-kernel-increment-11-isolated.md),
[summary](../../experiments/kernel-increment-11/evidence/summary.json), and
[real-binding readiness](../../experiments/kernel-increment-11/evidence/readiness.json).
The earlier [prerequisite STOP](028-cognitive-kernel-increment-11-stop.md) is resolved
for the isolated proof only. Exact next human decision: approve a concrete real
provider binding and Task-scoped authority inputs after its enforcement constraints
are established. Increment 12 remains unstarted.

The previously missing workload has been supplied. Increment 10 must conform to
[ADR 0018](../decisions/0018-local-platform-durability-and-observability.md), recorded
from the supplied architecture on 2026-09-20. The repository ADR is the architectural
source of truth for Increment 10 and future work; it is a constraint, not optional
background. Its proposed status is preserved; recording it does not validate or
implement its infrastructure.

The bounded workload is the backend-independent ExecutionEvent v1 foundation,
minimal runtime emission, a local JSONL acceptance/forensic sink, and independent
reconstruction of a real durable Task. No observability platform is authorized.
Increment 10 passed: 87 focused tests, 28 independently verified events, native
recovery without duplicate worker effect, and completion during telemetry outage.
See [Increment 10 worklog](027-cognitive-kernel-increment-10.md) and
[evidence](../../experiments/kernel-increment-10/evidence/summary.json). The earlier
[workload STOP](026-cognitive-kernel-increment-10-workload-stop.md) is historical
and resolved by the supplied objective and acceptance criteria.

**Increment 8 PASSED: approved verifier-driven progression adopted.**

The production live gate completed with two Qwen calls, durable human suspension,
verified resolution after restart, and no cognition/effects after sufficient evidence.
The incomplete-effect control and 72 focused regressions passed. Experimental
dispatchers are archived, leaving one production workflow. See [milestone](024-cognitive-kernel-increment-8-passed.md)
and [evidence](../../experiments/kernel-increment-8/evidence/production/summary.json).
Increment 9 subsequently passed; its record appears above.

Historical STOP records (subsequently resolved by explicit authorization):

**STOPPED after the Increment 8 verifier-progression experiment: experimental PASS; production Increment 8 remains FAILED / unpassed.**

Latest bounded experiment completed the original scenario with two real local Qwen
calls (REQUEST_HUMAN, PRODUCE_ARTIFACT), unchanged prompts/contracts/verification,
and no model calls after sufficient evidence. Native Restate recovery completed
from persisted evidence without another decision. A separate scripted negative Task
proved that a successful but incorrect artifact returns to cognition. No production
files or previous experiments changed. See [report](023-cognitive-kernel-increment-8-verifier-progression-experiment.md)
and [machine-readable summary](../../experiments/kernel-increment-8/evidence/progression/summary.json).
Exact next step: human architectural approval or rejection of verifier-first
completion and blocking suspension; no production migration or Increment 9 is authorized.

Previous experiment record:
**Prior hybrid experiment: suspension proven; full completion was unpassed.**

Latest authorized experiment (not adopted architecture): native blocking suspension
survived application/server restart with zero pending-interval model calls. Hard
vocabulary projection produced no invalid decisions. Both suspension-only and hybrid
arms nevertheless repeated legal artifact writes and hit their six-call caps without
COMPLETE. A separate one-call control preserved model choice between direct
clarification and eligible specialist handoff. All existing runtime files remain
unchanged. See [experiment report](022-cognitive-kernel-increment-8-hybrid-experiment.md)
and [machine-readable comparison](../../experiments/kernel-increment-8/evidence/hybrid/comparison.json).
Exact next step: human architecture decision on the proven blocking-wait boundary
and a separately bounded legal-action progress/termination question. No further
prompt tuning, automatic completion, adoption or Increment 9 is authorized.

Historical continuity below:
Increments 1–7 passed their recorded gates. The latest user-authorized Goose
auxiliary diagnostic established local request/model accounting; incomplete title
streams remain an explicitly accepted observability limitation. Increment 7 then
passed bounded-worker interruption/replacement and exact completion verification.

Increment 8 originally repeated WAIT after losing the generic clarification answer
from its bounded projection. The authorized diagnostic confirmed that gap and stale
objective wording. The subsequent approved correction reuses verified human-response
artifacts and projects a scoped current resolution without history or objective
mutation. All 44 focused tests pass (37 baseline plus seven projection controls).
Only context reconstruction changed in runtime; authority/lifecycle/contracts,
adapter and verifier remain unchanged.

The corrected live probe failed earlier: all 16 local Qwen decisions added an
invalid sibling `version` field to human.request input. Policy denied every request;
zero effects occurred and the Task FAILED. No answer was submitted, so live
resolution/restart/completion remain unverified. No Increment 9–12 work started.
The authorized output-shape diagnostic found the exact shape already explicit in
every sent schema, matching PolicyGate. The user's stop condition applies:
classification MODEL_ACTION_SERIALIZATION_BEHAVIOR. No guidance/runtime changes or
new inference followed. All 48 focused tests pass, including four new boundary
tests; 12 synthetic controls are retained separately from live evidence.
The subsequently authorized semantic/runtime separation carveout adds an opt-in,
strict JSON semantic human request and deterministic lowering to existing commands.
All 56 focused tests pass. One live attempt made four local Qwen calls: first an
inadmissible WAIT, then three attempts embedding semantic fields in the old runtime
human.request envelope. The adapter rejected that mixed representation. Task FAILED;
no live lowering/effect/response occurred. Existing runtime files and the accepted
projection remain unchanged; no migration or Increment 9 work began.
The authorized coherent-boundary revision then removed all runtime forms from the
model-facing context/vocabulary. All 65 focused tests pass. In one four-call live
run, Qwen emitted only valid semantic shapes; the first REQUEST_HUMAN was lowered,
policy-admitted and published once. With status pending and WAIT available, the
next turn repeated REQUEST_HUMAN on three existing attempts. New local admissibility
checks rejected duplicates without substitution or effects. Task FAILED; response,
live recovery and completion remain unverified. No Increment 9 work followed.
See [the previous STOP record](021-cognitive-kernel-increment-8-coherent-semantics-stop.md).
Resume requires a bounded action-selection/admissibility-feedback decision, not
weaker enforcement, automatic action substitution or broad migration.

Approved basis: [checkpoint](../research/cognitive-loop-checkpoint.md), Increment
1 clarifications, and the user's ordered progressive program. Do not restart
architecture research. Each increment is a hard gate: hypothesis → smallest
implementation → focused tests → required live probe → retained evidence and
milestone → explicit gate evaluation. The table records actual status, not plans
as accomplishments.

| Increment | Status | Evidence / record | Architecture deviations | Next required gate |
| --- | --- | --- | --- | --- |
| 1: kernel | PASS; reproduced | [baseline](../../experiments/kernel-program/baseline/summary.json), [milestone](003-cognitive-kernel-increment-1.md) | None | Passed into 2 |
| 2: joined sequential child | PASS | [evidence](../../experiments/kernel-increment-2/evidence/summary.json), [milestone](004-cognitive-kernel-increment-2.md) | None | 3: real local model |
| 3: real local model | PASS after authorized adapter-only correction | [evidence](../../experiments/kernel-increment-3/evidence/json-only-correction/summary.json), [milestone](007-cognitive-kernel-increment-3-passed.md) | None | STOP; do not start 4 without a new instruction |
| 4: MIRIX context | PASS | [evidence](../../experiments/kernel-increment-4/evidence/resumed/summary.json), [milestone](009-cognitive-kernel-increment-4-passed.md) | None | 5: scoped human decision child |
| 5: human decision | PASS | [evidence](../../experiments/kernel-increment-5/evidence/approved-extension/summary.json), [milestone](011-cognitive-kernel-increment-5-passed.md) | Explicitly approved additive scoped verifier; exact-digest behavior retained | 6: bounded YouTrack capability |
| 6: YouTrack | PASS; live read via controlled MCP bridge | [evidence](../../experiments/kernel-increment-6/evidence/summary.json), [milestone](012-cognitive-kernel-increment-6-passed.md) | None; production transport remains injected | 7: one existing external worker/harness |
| 7: worker/harness | PASS; auxiliary requests separately accounted | [evidence](../../experiments/kernel-increment-7/evidence/acceptance/summary.json), [milestone](015-cognitive-kernel-increment-7-passed.md) | None; user accepted title-stream accounting limitation | 8: Spec Kit as bounded procedure context |
| 8: Spec Kit procedure | PASSED | [production evidence](../../experiments/kernel-increment-8/evidence/production/summary.json), [milestone](024-cognitive-kernel-increment-8-passed.md) | Approved verifier-first progression and runtime blocking; strict authority/contracts preserved | Increment 9: bounded derived Project Knowledge |
| 9: Project Knowledge | PASSED | [evidence](../../experiments/kernel-increment-9/evidence/summary.json), [milestone](025-cognitive-kernel-increment-9-passed.md) | No loop/authority changes; derived navigation with exact source freshness checks | Increment 10: concrete medium-size objective and completion criteria |
| 10: context economy | BLOCKED before implementation: workload required | [STOP record](026-cognitive-kernel-increment-10-workload-stop.md), [preflight](../../experiments/kernel-increment-10/evidence/preflight.json) | None | Concrete real objective and independent completion criteria; then sequential proof |
| 11: cloud routing seam | NOT STARTED | — | — | Separate usefulness, authorization, egress, budget and provider; existing safe configuration only; unavailable live provider may be skipped with seam recorded |
| 12: parallel children | NOT STARTED | — | — | Only after prior stability; explicit independence, resource bounds, deterministic aggregation, failures/cancellation, isolated context and total budget |

## Continuation rules

One loop per Task. Runtime owns lifecycle/effects/enforcement; cognition chooses
semantics. INVOKE_CAPABILITY, same-Task HANDOFF and independent SPAWN_TASK remain
distinct. COMPLETE only requests verification. Minimum-sufficient packets and
bounded child results replace automatic history sharing. Keep Restate state,
exact artifacts, MIRIX semantic memory, authoritative source and derived Project
Knowledge separate. Parallelism is deferred to 12; no infrastructure migration.

Stop immediately on an invariant contradiction, non-local semantic change,
ambiguous authority/storage, unsafe effect, dependency installation, secret/host
change, broad unresolved product decision, earlier regression, speculative
abstraction or uncontrolled inherited context. Stop bounded debugging if direct
evidence cannot resolve it. Record EXPECTED / OBSERVED / IMPACT / SMALLEST NEXT
DECISION REQUIRED. Do not continue to later increments after a failed gate, except
the user's explicit live-integration exceptions at 6 and 11.

## Repository baseline and retained progress

Prior Increment 1 files were uncommitted/untracked, as left by the prior session.
Their recorded source digests matched before implementation. Baseline: 23 tests
passed once; all seven live probes reproduced. Increment 2: 27 tests, joined child
recovery and all seven earlier live regression probes passed. Exact evidence and
source digests are retained per increment. No commit or production deployment is
claimed. Artifact snapshots preserve each gate's evidence independently of later
source changes. On the resumed Increment 3 run, neither Increment 1 nor 2 was
repeated; unchanged kernel source digests were checked. Four new adapter tests
passed. Qwen was called for 32 bounded turns across two failed live attempts;
that initial acceptance attempt failed. Increment 3A then used four controlled
calls and five focused tests to isolate the constrained-path action failure and
JSON-only envelope omission. The subsequent authorized adapter-only correction
passed five focused tests and the unchanged six-case Increment 3 live probe.
Application validation, kernel and contracts remain unchanged. Work stopped there,
as explicitly requested; no later increment followed. No external capabilities have been connected
beyond local fixture capabilities and native joined Task calls. MIRIX/BGE-M3,
PostgreSQL, Redis, secrets and serving configurations were not modified.

Development request draft, **not submitted** through a Personal Agent binding:
implement only the ordered increments whose gates pass; retain independent tests,
evidence and these progress records; stop on the first blocker. Authority excludes
installation, secrets and host reconfiguration. This draft is not runtime state;
actual probe Tasks have their own Restate receipts and identities.
