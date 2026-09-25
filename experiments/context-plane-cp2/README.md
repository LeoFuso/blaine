# CP.2 governed Memory qualification

**Current: CP.2 PARTIAL — implementation and deterministic tests complete; native
storage acceptance pending.** See [executable contract](../../docs/contracts/context-plane-cp2.md),
[milestone 056](../../docs/milestones/056-context-plane-cp2-storage-qualification.md) and
[durable current qualification](evidence/implementation/qualification.json).

`15a1df1` introduces governed WORKING observations and RETAINED declarations through
Blaine-owned contracts over MIRIX raw source/vector storage and a metadata-only registry
in the same database. `8d1c4f6` adds the bounded native acceptance harness and additive
HOST definition. Native run `run-613c0c65fb584188` was BLOCKED before steps by a driver-URL
probe defect; correction `e84e08d` requires separate trusted probe publication. No native
write/restart acceptance is claimed. The scheduler is healthy and idle.

Canonical HERMETIC qualification passes: 462 root tests (25 CP.2), 26 scheduler tests,
zero skips. The 61-test E1 subset also passed and overlaps root. Canonical results,
the actual HOST report and correction details are retained
under `evidence/implementation/`. No protected Memory content or credentials are retained.
The next action remains CP.2 native qualification through the published trusted suite;
no scheduler bypass, CP.3, push or production deployment.

The following sections preserve historical checkpoints and are superseded by the current
qualification record where they describe implementation/publication state.

# CP.2 storage qualification

**Current: CP.2 PARTIAL; reconciliation and published regression qualification PASS.**
[Reconciliation evidence](evidence/reconciliation/qualification.json) retains checkpoint
`0b2b46e`, normal merge `c5f3d97` of main `16f7e1a`, 26 scheduler tests and the actual
live canonical run `run-e524998cef0c437b`: 437 root tests PASS on a clean checkout.
The suite is independently trusted-published; no scheduler deployment or publication
was performed here. Native CP.2 persistence acceptance remains unimplemented/unproven;
this published suite is HERMETIC. Earlier publication holds below are historical for
these regressions, not current blockers. No CP.3 or push.


**CP.2 PARTIAL; implementation stopped pending trusted suite publication.**
The [publication boundary](evidence/resume/trusted-publication.json) records the user's
choice: a separate trusted infrastructure action publishes only the reviewed suite/harness.
No candidate-worktree Python is imported into the scheduler; no production implementation
is published or accepted by this action. The current local suite is HERMETIC, not yet a
HOST persistence harness. This session will not provision or redeploy the scheduler.
The scheduler-unavailable blocker is cleared: [resume health](evidence/resume/scheduler-health.json).
The live catalog does not discover this worktree's additive suites:
[discovery evidence](evidence/resume/suite-discovery.json). Trusted publication is required before implementation resumes; no scheduler redesign or bypass. No implementation
or new persistence acceptance was performed. The prior records below are historical.

**Previous checkpoint: CP.2 STOP at HOST prerequisite — 2026-09-24.** No CP.2 production writes accepted.
[Revision 2](evidence/storage-qualification-v2.json) supersedes the prior STOP criterion:
persistence is not retention, and embeddings are not inherently a blocker. Qualification
covers governed source plus useful derived processing, preserving Blaine-owned
WORKING/RETAINED, provenance and security semantics. No automatic retention or promotion.

The revised matrix covers all eight questions for raw+embedding, extraction ingestion,
and an internal existing-substrate adapter. Raw+embedding remains a viable candidate;
no production write path is accepted. [Processing observation](evidence/processing-observation.json)
found seven local embedding configurations. [Scheduler prerequisite](evidence/scheduler-prerequisite.json)
found the required services absent from the configured Restate registry: HOST BLOCKED,
ENVIRONMENT_FAILURE, no provisioning or scheduler bypass. No write/restart tests ran.

[Current refinement qualification](evidence/refinement/qualification.json): canonical
pre_handoff passed again, 463 unique tests, zero skips. JSON reports are extracted from
the retained canonical console with suite filenames, preserving their original run IDs.
No new runner or redundant acceptance claims. CP.2 persistence tests: zero.

The following records describe the **historical** checkpoint, not the revised decision.
Baseline: `origin/main 56f2e65cdf1bb470aa179168e3a628b29f422092`.
Branch: `feature/context-plane-cp2`, same worktree formerly used for CP.1.
CP.1 is merged and historical; CP.3 is not started.

- [Historical source-pinned storage qualification](evidence/storage-qualification.json): actual
  running MIRIX source/cleanliness, safe process observation, concrete source locations,
  positive substrate mechanisms, blocker and unproven guarantees.
- [Canonical qualification summary](evidence/qualification.json).
- [Canonical pre-handoff console](evidence/pre-handoff.txt).
- Promoted canonical reports: [Completion Contract](evidence/hermetic/run-1.json),
  [Context Plane/kernel](evidence/hermetic/run-2.json),
  [scheduler sample](evidence/hermetic/run-3.json).
- [Milestone, stop boundary and next session](../../docs/milestones/056-context-plane-cp2-storage-qualification.md).

The current public MIRIX raw route processes content through embeddings by default
before storage; the existing Blaine binding does not qualify that processing route.
Semantic ingestion performs model-driven extraction. Raw exact content/JSON metadata,
SQL commit/refresh and scoped search are real useful mechanisms, but do not establish
the complete scoped idempotency/metadata/retention contract. Internal-manager or direct
SQL access was considered and not silently adopted as a different integration seam.
This is not a claim that an approved adapter over the existing substrate is impossible.

Canonical HERMETIC results: **437 integrated tests + 26 scheduler tests PASS**,
zero skipped; the **61 E1.0 tests** also passed as their own suite and are included
in the 437. No CP.2 write acceptance tests exist yet. Existing CP.1 read/compiler,
E1.0 contract and E2.0 effect regressions remain green. A passing baseline does not
prove declaration/observation persistence.

Canonical command used the configured interpreter, with no dependency installation:

```sh
PYTHONDONTWRITEBYTECODE=1 /home/leofuso/workspace/blaine/.local/runtime-venv/bin/python -m nox --no-venv -s pre_handoff
```

The separate CLI invocations reused `run-1`, so the last local report overwrote the
others. The console retains every original report. To retain durable machine-readable
results through the repository's accepted API, the three discovered HERMETIC suites
were re-executed with one `verification.scheduler.Scheduler` instance and each actual
`RunRecord` was explicitly exported using `verification.report.promote`. Reports preserve
the tested base commit and dirty state. This evidence-recovery rerun is not a new runner
or a fix to the verification scheduler. No count is presented as unique twice.

**HOST: BLOCKED — MIRIX_STORAGE_BOUNDARY_NOT_QUALIFIED.** This prerequisite assessment
was made before any HOST submission; it is not a synthetic scheduler execution report.
No protected synthetic writes, native restart, resource-queue bypass, cloud call, secret
retrieval, service reconfiguration or infrastructure provisioning occurred.

The next increment is still CP.2: review and qualify the narrow existing-substrate
write adapter/server boundary, then implement and test the accepted write semantics.
No executable contract was frozen for an unqualified implementation. No alternative
Memory store, reflection, learning, promotion, declassification or semantic retrieval
was introduced.
