# CP.1 — Local governed context projection and one delta

**PASS — 2026-09-24.** Latest completed Context Plane increment: **CP.1**.
Branch `feature/context-plane-cp1`, worktree `/home/leofuso/workspace/blaine-cp1`,
original baseline `b1b3073`. Implementation and acceptance are local; not deployed by default.
No push, merge into main or CP.2 work. Track III research and its historical outcomes are unchanged.

The [roadmap](../roadmap/002-context-plane-implementation.md) owns sequencing;
the [executable subset](../contracts/context-plane-cp1.md) owns concrete CP.1 shapes;
[retained acceptance](../../experiments/context-plane-cp1/evidence/acceptance.json) owns
measurements, source/evidence hashes and qualification gaps.

## E1.0 reconciliation and final qualification

**READY_FOR_PIPELINE — 2026-09-24.** Normal merge `e9e9196` integrates
`origin/main` at `f0a3ca5` without rewriting CP.1 commit `b0f782a`.
The only textual conflict was `runtime/kernel/workflow.py`; the resolution retains
E1.0 intake/settlement/journals and CP.1 route, compilation and delivery guards.

The Compiler now projects the runtime's current Completion Contract reference,
revision and exact criteria. Private worker admissions pin that revision; stale
delivery refuses. E1.0's existing amendment handler and journaled `promise().peek()`
remain authoritative. The deterministic integration test proves revision 0 initial
context, an authorized amendment, stale-packet refusal, revision 1 delta and replay.
An amendment also invalidates context prepared by a preceding handoff. This fixes
the observed stale cognitive packet without introducing another contract owner.
`context.request` is a TARGET_READ (`context.read`) in the existing classification
table; permission, class-forgery and scope denials remain enforced.

[Durable qualification](../../experiments/context-plane-cp1/evidence/reconciliation/qualification.json)
records exact commands, failures/resolutions, source hashes and per-file test counts:
**333 root tests**, including **22 CP.1** and **61 E1.0 contract/workflow/coverage**
tests, all passed. The exact CI host/readiness command passed its six tests (already
included in the root count). Native CP.1 passed 15 checks with two local Goose
dispatches, one delta and CompletionEvaluation v2 legality. Packets measured
**2,428 → 2,411 bytes**, delta **2,577**. The accepted E1.0 and parallel-child native
suites also passed: **9 + 12 Tasks**, **11 runtime + 5 server SIGKILLs** combined,
no duplicate effects. Expected negative fixture outcomes remain failures, not success.

The [reinspected CI matrix](../../experiments/context-plane-cp1/evidence/reconciliation/ci-matrix.json)
shows **no automatic GitHub job matching this branch/PR diff**. Client build/release
workflows are unchanged. Full client builds were not run for this unrelated diff;
GitHub artifact upload and tag-release publication require GitHub identity when
invoked and are not pending required checks for CP.1. No workflow was weakened.
Historical evidence below remains unchanged. No blocker remains; push/PR and merge
into main still require human authorization. CP.2 is next and **NOT STARTED**.

## Production result

Selected the existing hosted `create_workflow → owned Cognitive Loop → worker.run →
GooseWorker` seam because it already supplies bounded WorkerInput artifacts, PolicyGate,
independent completion and journaled operations. Goose stays one-shot/tool-free. An
explicit `Capabilities(context_plane=...)` deployment option enables this path; defaults,
D2/remote intake and legacy providers keep their behavior.

`LocalContextAuthority` binds existing Task/spec/operation identity to a configured local
principal, route, validated complete tree, independent security/policy visibility and exact
resource grants. Current application state wins over all serialized references. Private
snapshot/admission data stays in the existing artifact/journal boundary. The public
TaskState still uses `context_ref` for CognitiveTurn; workers cannot mint compiler admission.

The read-only Blaine Memory facade admits only explicitly owned/qualified corpus records,
filters before provider processing and validates returned IDs/content against trusted
origin/status/digests. Legacy MIRIX remains disabled on this route. ContextResolver routes
explicit needs to confined lexical/exact files, exact admitted evidence or governed Memory.
ContextCompiler independently validates and packs exact requirements/source/provenance
before optional context, preserving the existing WorkerInput schema and limits.

Initial compilation journals independently held admission. Physical worker delivery checks
the exact input digest, current binding and current source bytes. One later admitted need
re-resolves current state and produces a bounded ContextDelta plus replacement active input.
No old worker results/transcript are accumulated. New cognition and worker calls recheck
authority inside physical journal steps; historical replay causes no new inference/effects.
A new admitted resolution can narrow current policy; pending stale delivery is refused.

## Original CP.1 acceptance (before E1.0)

| Roadmap boundary | Retained proof |
| --- | --- |
| Trusted ExecutionContext binding; no caller scopes | Closed v1 reference/request and trusted snapshot resolver; principal/Task/spec/route mismatch, malformed hidden topology and forged fields reject. |
| Lineage ∩ security ∩ policy | Exact current/ancestor sets; no siblings, descendants, unrelated or foreign-domain reads; public ancestor requires explicit security and policy inclusion. |
| Approved governed sources only | Exact path grants, symlink/traversal rejection, independently admitted Task evidence, read-only qualified corpus. No raw MIRIX fallback. |
| Bounded faithful initial packet | Exact intent, criteria, constraints, source bytes/digest and qualified Memory; 2,167 bytes in live smoke. |
| Compiler provenance and delivery | Forged packet/receipt fails; policy admission/artifact membership alone insufficient. Old source, packet digest and binding mismatch refuse dispatch. |
| One fresh delta | After source changes DRAFT→GOOD, owned cognition requests current source; delta 2,316 bytes; active packet 2,150 bytes. Second delta/duplicate successful packet dispatch deny. |
| Current authority and uncertainty | Direct and runtime delta tests narrow policy; old Memory disappears. Optional unavailability is explicit; missing mandatory evidence/budget fails; EMPTY differs from DENIED/UNAVAILABLE. |
| Whole-envelope budgets | Worker 4,096; delta 4,096; capability result 4,096; CognitiveTurn 16,384. UTF-8 and over-budget exact criteria controls pass without trimming. |
| Real existing runtime/worker path | Native Restate 1.7.9 / SDK 1.0.5, Goose 1.50.1, local nvidia/Qwen3.8-27B-NVFP4; two dispatches, one delta; exact final artifact verified. |
| Completion and replay | Wrong worker output leaves Task incomplete. Recorded-step replay causes no duplicate calls; partial replay cannot grant revoked reads/delivery. Native recovery races are not claimed. |
| Negative/mutation controls | Forbidden literals/IDs absent from caller outputs and ordinary logs. Deliberately unsafe caller-scope and artifact-membership controls cause actual caught leaks. Fresh source survives stale Memory. |
| Existing behavior/no phase creep | 217 relevant tests pass, including 21 CP.1 tests and kernel lifecycle, children, human resolution, PolicyGate, artifact integrity, frontier exact-byte authority, D2/ACP/remote read. No semantic search, Graphify or writes. |

The [native summary](../../experiments/context-plane-cp1/evidence/live/summary.json)
retains adapter/model versions and input sizes. Recorded coordinator decisions are not
claimed as live cognition. This is a bounded integration PASS, not general retrieval
quality, semantic entailment, DLP, authentication or production concurrency validation.

## Surprises, blockers and limits

- No architecture contradiction was found. The later E1.0 completion seam changes
  are reconciled and qualified above.
- MIRIX's existing client header/filter tags and row provenance are insufficient for
  governed processing. It remains **NOT QUALIFIED** here; that optional adapter gap does
  not invalidate the roadmap's permitted source-only/read-only-corpus CP.1 acceptance.
- Per-field WorkerInput limits can reject exact material well below 4,096 total bytes.
  Whole-file lexical/exact reads intentionally report insufficiency rather than silently
  cut conditions. Larger excerpts/range support require separately reviewed semantics.
- Snapshots are deployment-owned and immutable within an operation. Detected stale
  authority refuses delivery; automatic rebind/resume and concurrent revocation need CP.8.
- Local sandbox IPC restrictions required running the bounded fixture suites with local
  IPC permission. No host service reconfiguration was needed.
- No implementation Task was submitted because its creation binding was unavailable;
  the [draft](../../experiments/context-plane-cp1/task-request.json) records authorization.

No blocking condition remains for this bounded CP.1 implementation. Enabling a hosted
deployment still requires explicit review of the retained evidence. Do not confuse local
implementation acceptance with deployment approval.

## Next session

Exact next increment: **CP.2 — Governed declared/observed writes**, only after explicit
authorization. First qualify the existing MIRIX substrate and decide Blaine-owned entry
metadata in existing approved storage; no new memory product/ledger. Acceptance requires
trusted human declaration vs UNVERIFIED current-context agent observation, all-method
scope isolation, committed readback, scoped idempotency, response-loss/restart evidence
and provenance-preserving schema migration. A queued write is not committed evidence.

Review and merge CP.1 into main first. After that merge, create a fresh
`feature/context-plane-cp2` branch/worktree from the accepted base, e.g.
`/home/leofuso/workspace/blaine-cp2`; preserve this worktree and retained evidence.
If CP.1 review is still pending, remain on this branch for CP.1 fixes only.

Recommended model: **GPT-6 Astra, high reasoning** for authority/storage integration;
this is a task-specific recommendation, not a measured model comparison. Official
[reasoning guidance](https://developers.openai.com/api/docs/guides/reasoning) supports
using higher reasoning effort for complex multi-step work.

Ready-to-paste continuation:

> Start only CP.2 — Governed declared/observed writes from the reviewed, merged CP.1 base.
> Read docs/context-plane.md, docs/contracts/context-plane.md, ADR 0025,
> docs/roadmap/002-context-plane-implementation.md, docs/contracts/context-plane-cp1.md
> and docs/milestones/055-context-plane-cp1.md, including retained CP.1 evidence.
> Use a fresh feature/context-plane-cp2 worktree. Qualify existing MIRIX processing scope
> and Blaine-owned metadata in approved storage before writes; stop on missing trusted
> issuer/scope or incompatible storage semantics. Implement only CP.2's declared/observed
> writes and acceptance, preserving compiler admissions, current authority and independent
> completion. No learning/reflection, semantic retrieval, Graphify, promotion,
> declassification or remote propagation. Retain deterministic and bounded integration
> evidence, update the roadmap/handoff, commit locally; do not push or merge.
