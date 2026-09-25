# CP.2 — Storage qualification

## Reconciled checkpoint: PARTIAL; published regression suite passes

Pending docs/evidence and the suite substitution fix were committed as `0b2b46e`.
Canonical main `16f7e1a` was merged normally into CP.2 as `c5f3d97`, without conflicts,
rebasing or production CP.2 changes. Scheduler composition is preserved; 26 scheduler
unit tests and local composition/substitution checks passed. Both diff checks passed.

The corrected `context-plane` suite is now independently published in the trusted app;
its bytes match this branch. Existing live scheduler identity
`VerificationScheduler_blaine/host` ran it against clean `c5f3d97`:
**run-e524998cef0c437b PASS, 437 root tests**. The scheduler returned idle with an empty
queue. [Canonical report and reconciliation evidence](../../experiments/context-plane-cp2/evidence/reconciliation/qualification.json).
This session did not publish, provision, redeploy or push anything.

The earlier publication/substitution blockers are cleared for this regression suite.
Its class remains HERMETIC. Running it through Restate does not make it a HOST persistence
proof. CP.2 remains PARTIAL: governed writes and native storage/readback/restart/compiled
context acceptance are not implemented or accepted. Next is the retained CP.2 storage
qualification/implementation plan and its dedicated native harness, published separately
through trusted verification infrastructure before HOST acceptance. No CP.3.

The following checkpoints preserve earlier observations; their publication hold is
superseded for the existing regression suite by this successful live run.


## Resume checkpoint: PARTIAL; implementation held for trusted suite publication

The prior scheduler-unavailable blocker is **CLEARED**. Both canonical services are
registered; shared status is idle (`active = null`, empty queue), and live acceptance
`run-1a6e284513a14870` reports PASS. See
[health observation](../../experiments/context-plane-cp2/evidence/resume/scheduler-health.json).
No provisioning, deployment or acceptance rerun was performed.

Git remains on `feature/context-plane-cp2` at checkpoint `3d7ef0b`. Current main is
`16f7e1a`: its sole additional change extracts `build_services()` while preserving
scheduler execution behavior. No merge/rebase or other-worktree change was made.
All ten MIRIX source hashes retained in revision 2 still match; the previous storage
review is reused, not reopened. [Source continuity](../../experiments/context-plane-cp2/evidence/resume/source-continuity.json).

**Qualification integration gap:** the live scheduler imports named suites from its
own deployed `verification/suites` directory. `worktree` sets execution cwd and Git
identity; it does not select the suite-definition directory. The deployed catalog has
`completion-contract`, `completion-contract-native`, `sample-hermetic`, and
`live-acceptance` (a bounded sleep). Even this branch's existing `context-plane` suite
is unknown there. [Read-only discovery evidence](../../experiments/context-plane-cp2/evidence/resume/suite-discovery.json).
The user has selected **trusted suite publication** as a separate verification
infrastructure action. CP.2 remains **PARTIAL**, with implementation explicitly stopped
until the `context-plane` qualification suite is published and visible to the live
scheduler. The current branch, prior evidence and checkpoint are preserved.

Only the reviewed suite definition / verification harness needed to qualify CP.2 may
be published through that infrastructure action. It must run its named probes/tests
against the submitted worktree, which is the subject of qualification, not a trusted
scheduler-code source. Do not dynamically import candidate-worktree Python into the
scheduler, add arbitrary-command suites, redesign discovery, or bypass arbitration.
Publication does not publish/merge CP.2 production implementation and does not imply
acceptance. PASS / FAIL / BLOCKED semantics remain unchanged.

Repository fact: the current `verification/suites/context_plane.py` is **HERMETIC**
and runs root regressions. It is not yet the CP.2 HOST persistence harness. Trusted
publication must supply the intended HOST qualification definition and prerequisites;
merely publishing or relabeling this hermetic suite cannot prove persistence. No suite
code was changed as part of this hold.

Next: the trusted infrastructure owner publishes the qualification suite separately.
This session must not provision or redeploy the scheduler itself. After publication,
verify live suite visibility and its trusted definition, then resume the retained CP.2
storage proofs and implementation. The WORKING/RETAINED, provenance and authority rules
below remain unchanged. CP.3 is not started. No new test result is claimed for this
instruction-only checkpoint. See [publication boundary](../../experiments/context-plane-cp2/evidence/resume/trusted-publication.json).

## Historical scheduler-unavailable checkpoint

**CP.2 STOP — required HOST scheduler unavailable (2026-09-24; now cleared).** The revised
storage review is PARTIAL, not an architectural rejection of MIRIX. No CP.2 governed
write implementation is accepted yet. [Revision 2](../../experiments/context-plane-cp2/evidence/storage-qualification-v2.json)
supersedes the prior STOP criterion: persistence is not retention and embedding
processing is not inherently disqualifying. The previous report remains historical.

## Revised storage findings

The pinned MIRIX raw route preserves exact text plus JSON metadata and stores optional
embeddings on the same source row. It remains a viable candidate. SQL raw search
filters organization, authorized scope and supplied metadata before pagination, which
can support trusted WORKING/RETAINED separation. All seven observed embedding routes
point to the existing local port 8001 service. This observation does not grant processing
permission for every SecurityContext or pin mutable configuration atomically.

The eight-question matrix in revision 2 distinguishes source observations from unproven
adapter/runtime guarantees for raw+embedding, extraction ingestion and an internal
adapter over the same approved substrate. It does not require MIRIX to be a dumb store.
Raw retention-aware cleanup, scoped idempotency, trusted metadata, committed facade
readback and restart isolation still need qualification. No fixed TTL follows from the
names WORKING or RETAINED, and no actual cleanup/data loss was measured.

Full extraction ingestion is not admitted yet: session source persistence failures
can be caught while extraction continues; semantic update deletes old IDs and applies
current tags to replacements without a Blaine source-retention intersection; task
sessions can trigger procedural auto-dream. Useful extraction/consolidation is allowed
conceptually, but enabling this pipeline unchanged would not prove CP.2 semantics.
A narrow internal adapter is also within authorized CP.2 design scope; no extra
permission is inferred merely because it uses the existing approved storage differently.

## Current acceptance boundary

- AGENT_OBSERVATION / UNVERIFIED defaults to WORKING in current bound C.
- Explicitly authorized USER_DECLARATION intended to be remembered defaults to RETAINED.
- Retention is orthogonal to context/security and epistemic status. Caller metadata
  cannot choose or upgrade it; persistence/indexing cannot automatically retain it.
- Qualify exact source and metadata preservation, derived processing and scope,
  retention ownership, governed retrieval separation, no upward flow and provider egress.
- Prove both states across committed readback/reconstruction/isolation and fresh compiled
  context. Worker consumes compilation, not backend rows. E1/E2 remain authoritative.
- No automatic retention scoring, reflection, learning, promotion, abstraction,
  declassification, CP.3, new semantic workspace retrieval or second Memory system.

## Revised qualification validation

Canonical `pre_handoff` was rerun after the refinement: **437 root tests + 26 scheduler
tests passed, zero skips**. The 61-test Completion Contract suite also passed separately
and overlaps the root suite. CP.1's 22 tests remain covered; CP.2 write tests remain zero.
[Retained current qualification](../../experiments/context-plane-cp2/evidence/refinement/qualification.json)
contains canonical reports and exact console output. This validates unchanged runtime
regressions, not the proposed retention/write semantics. `git diff --check` passed.

## Current blocker and next session

Read-only observation of the configured Restate admin registry at loopback port 49070
found neither `VerificationScheduler_blaine` nor `VerificationRun` registered.
[Retained prerequisite result](../../experiments/context-plane-cp2/evidence/scheduler-prerequisite.json).
Classification: **ENVIRONMENT_FAILURE**; HOST qualification **BLOCKED**. No HOST run was
submitted and no resource queue bypassed. The user's “verify, don't provision” boundary
prevents deploying a scheduler to repair this prerequisite. This is separate from the
remaining storage design/proof work; it is not evidence that MIRIX is unsuitable.

Next increment remains **CP.2**, beginning with the configured canonical HOST scheduler
being made available by its owner. Then qualify the candidate's retention lifecycle and
trusted processing route; implement trusted declaration/observation with scoped replay,
facade readback and restart/compiled-delta acceptance. Keep this CP.2 branch/worktree;
fetch main for seam changes. There is no CP.2 implementation to merge yet. Once CP.2
passes, merge it before CP.3. Model recommendation remains GPT-6 Astra, high reasoning.

Continuation:

> Resume only CP.2 in feature/context-plane-cp2, /home/leofuso/workspace/blaine-cp1.
> Read roadmap 002, milestone 056 and storage-qualification-v2.json. Preserve independent
> WORKING/RETAINED semantics and useful scoped MIRIX processing. Verify that the canonical
> HOST scheduler is now available; do not provision or bypass it. Qualify retention,
> source/derived security and scoped idempotency over existing approved storage before
> accepting writes. Prove facade readback, restart isolation and CP.1 compiled context.
> Preserve E1/E2 authority. No automatic retention, reflection, promotion, declassification,
> CP.3, push or PR.

## Historical checkpoint (superseded decision criterion)


**STOP — 2026-09-24.** CP.2 is authorized but no governed write implementation is
accepted. CP.1 is complete and merged; its evidence remains historical and unchanged.

Worktree `/home/leofuso/workspace/blaine-cp1` was clean on `feature/context-plane-cp1`.
After fetch, a new `feature/context-plane-cp2` was created exactly at
`origin/main 56f2e65cdf1bb470aa179168e3a628b29f422092`; HEAD matched main and the
worktree was clean before CP.2 work. No CP.1 commits were manually carried forward.
Intervening integrations were CP.1 (`cca909a`), E2.0 effects/cancellation (`f84cfe9`,
`a4f6b86`) and Local Verification Scheduler v0 (`976ea52`, `16344d0`, `56f2e65`).
E1.0 completion authority and E2.0 effect semantics remain unchanged.

## Exact stop seam

The [qualification record](../../experiments/context-plane-cp2/evidence/storage-qualification.json)
pins the clean, running MIRIX checkout to
`8cb06a62bbb7c478beb33dd4f2815696a72df482` and records source hashes/line locations.
The existing service was observed active, using that checkout; its process environment
has no `BUILD_EMBEDDINGS_FOR_MEMORY` override, whose source default is true.
No memory content, credentials or complete process environment was exposed.

- Blaine's existing `MirixContext` is optional semantic retrieval, not a governed
  persistence adapter. CP.1 intentionally rejects it as an unqualified provider.
- MIRIX `/memory/add` and `/memory/add_sync` perform extraction. Queue acceptance or
  extraction success does not prove an exact declaration/observation was committed.
- The raw API is a closer seam: exact `context`, JSON `filter_tags`, optional ID,
  PostgreSQL commit/refresh and scoped search exist. These positive mechanisms were
  inspected rather than dismissed based on earlier semantic-adapter findings.
- However, public `create_raw_memory` selects an agent and supplies its state to
  `RawMemoryManager.create_raw_memory`; with the current default, submitted content
  reaches embedding processing before storage. The request has no per-write opt-out.
  CP.1's trusted binding grants no such processing route. Compiler filtering later
  cannot repair this boundary.
- Optional global row IDs and tags are not a scoped idempotency/conflict/readback
  protocol or immutable Blaine registry. A scoped adapter may be possible, but its
  transaction, response-loss and isolation guarantees have not been established.
- Raw by-ID cache reads check scope/user but do not explicitly compare organization;
  search and SQL fallback have different checks. No cross-tenant exploit is claimed.
- Raw storage advertises a 14-day TTL; the cleanup selection lacks a Blaine retention
  partition. No cleanup was executed, and this review does not establish whether a
  nightly job is installed or its synthetic actor succeeds. Retention is unqualified,
  not a measured data-loss claim.

Internal manager calls can disable embeddings/cache. Adopting those calls or direct
SQL would introduce a different integration boundary and still require review of
metadata atomicity, all-method isolation and retention. No such substitution, new
Memory store, upstream checkout edit or host reconfiguration was made. This STOP is
about the current unqualified boundary, not an assertion that PostgreSQL or MIRIX
could never support the contract.

## Acceptance and verification

Neither `memory.declare` nor `memory.recordObservation` was implemented. Trusted human
origin, UNVERIFIED agent origin, write isolation, scoped idempotency, committed facade
readback, response-loss retry, restart reconstruction and new-write-to-compiled-delta
composition are **NOT PROVEN**. No executable CP.2 contract is frozen prematurely.

Canonical `nox --no-venv -s pre_handoff` ran using the existing runtime environment.
An additive `verification/suites/context_plane.py` registers the integrated root tests;
it explicitly does not claim storage qualification. The existing Completion Contract
and scheduler checks also passed. See [retained evidence](../../experiments/context-plane-cp2/README.md).

The CLI reused `run-1` across separate hermetic processes, overwriting the local report.
The full canonical console output was retained; hermetic suites were then re-executed
through one canonical `Scheduler` instance and explicitly retained with
`verification.report.promote`. This uses the existing executor and suite discovery,
not a parallel runner. The scheduler/report collision was recorded, not repaired here.

HOST persistence qualification is **BLOCKED: MIRIX_STORAGE_BOUNDARY_NOT_QUALIFIED**.
No HOST run was submitted, no resource queue was bypassed, and no native write/restart
was attempted. These are prerequisite review results, not a fabricated scheduler run.
No production code changed; passing CP.1/E1/E2 regressions do not establish CP.2 PASS.

## Next session

Resume **CP.2 storage qualification**, not CP.3. The next review must select and qualify
a narrow adapter/server route over the existing approved substrate that prevents
ungranted processing, pins Blaine metadata/retention semantics, and provides scoped
atomic identity/digest behavior. Do not silently use another Memory database. Any
upstream change, service reconfiguration or other-worktree work needs explicit scope.

Keep `feature/context-plane-cp2` in this worktree and inspect its retained STOP changes
before editing; fetch main and check for further seam changes. There is no accepted
CP.2 implementation to merge. Once CP.2 passes, merge it before CP.3. Retain the previous
handoff's model recommendation: GPT-6 Astra, high reasoning, for the authority/storage seam.

Ready-to-paste continuation:

> Resume only CP.2 from feature/context-plane-cp2 in /home/leofuso/workspace/blaine-cp1.
> Inspect current Git state and origin/main, roadmap 002, milestone 056 and the retained
> storage qualification STOP. CP.1 is merged. Resolve the MIRIX exact-write processing,
> scoped metadata/idempotency and retention boundary before implementing writes; do not
> substitute another Memory product or modify another worktree/host configuration
> without authorization. Preserve E1.0/E2.0 authority and CP.1 compiler admissions.
> Use canonical additive verification and the Restate host scheduler; verify, do not
> provision. Prove facade readback, response-loss/restart isolation and fresh compiled
> context before PASS. No CP.3, learning, promotion, declassification, semantic retrieval,
> Graphify, push or PR.
