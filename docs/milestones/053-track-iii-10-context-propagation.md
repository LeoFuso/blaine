# Track III.10 — Context propagation across durable boundaries PASS

Checkpoint: 2026-09-23. **PASS within the deterministic offline fixture.**
III.8 remains FAIL and III.8R its separately recorded PASS. No production integration
or subsequent Track III increment was started.

## Hypothesis and trusted boundary

A durable Task must outlive sessions, workers and processes. Context semantics should
survive serialized handoff and checkpoint/resume when receivers reconstruct access
from trusted current state. A serialized scope, provenance label, prior receipt or
policy snapshot is not authority. The III.9 UI interruption is motivation only; the
[III.10 experiment](../../experiments/track-iii-010/README.md) supplies independent proof.

Exactly **12 primary cases** were frozen before execution: four local handoffs, four
checkpoint/resumes and four second-process transfers. Corpus SHA-256:
`147f4dc5a520d18e1bb111e97704d841748f5d0ee12296172b2fd93a43c21239`.
[Protocol](../../experiments/track-iii-010/PROTOCOL.md),
[freeze](../../experiments/track-iii-010/evidence/fixture-freeze.json) and
[source pins](../../experiments/track-iii-010/evidence/preregistration.json) distinguish
predeclared oracles from observed results. The retained TaskSpec is unsubmitted.

The harness separately owns the receiving execution route, participant role, topology,
domain/policy, provenance and current binding evidence. The caller supplies only the
transfer envelope. The receiver reloads current trusted state per operation, validates
the whole structure with unchanged III.2 ContextTree, then intersects lineage, domain
visibility and current policy. This assumes trusted fixture-file/route issuance; it
is not production authentication or a process sandbox.

Local boundaries round-trip JSON and reconstruct objects. Checkpoint writers run in
separate processes, persist material, then exit before independently loaded resume.
Second-process receivers use actual subprocess/exec, with parent-observed PID and
child PID/PPID attestations. No network, database, inference, embeddings or production
Restate/MIRIX integration is involved.

## Results

| Group | Expected and actual outcomes |
| --- | --- |
| Local handoff, 4/4 | Valid cognition→worker→verifier preserves five entries; forged scope/domain/authority does not expand access; forged provenance cannot upgrade; foreign context DENIED. |
| Checkpoint/resume, 4/4 | Valid resume preserves five; P2 removes old-rule despite cached historical packet; T2 reparenting replaces old-rule with new-rule; missing context INVALID_CONTEXT. |
| Second process, 4/4 | Valid and forged-scope transfers preserve five; trusted P2 overrides stale P1; prior success followed by missing current evidence returns UNAVAILABLE. |

The baseline visible IDs are failure, observation, old-rule, public-rule and success.
Narrowed P2 has four, excluding old-rule. T2 instead includes new-rule and excludes
old-rule. A domain-private record at shared root remains invisible; ancestry alone
is insufficient. All data is synthetic. SAME-state replay matches exactly, including
current denials; changed state is re-evaluated rather than trusted through old receipts.

**1,460 independent checks PASS**, covering 12 primary cases and 29 supplemental probes.
**60 complete exports scanned; zero forbidden content and zero forbidden metadata.**
The primary run uses 26 real subprocess operations, all exiting 0 with empty stderr.
Maximum full response is **1696 bytes**, including provenance, receipt, diagnostics,
partial flag and stdout newline, below 2048. Primary-case maximum is 1051 bytes.
Saturation and an exact JSON-marker boundary exercise actual whole-entry truncation.

USER_DECLARATION/DECLARED, AGENT_OBSERVATION/UNVERIFIED, VERIFIED_SUCCESS and
VERIFIED_FAILURE preserve their trusted origin/status across valid transfers. A worker
writes only into task-main; a subsequent process verifier queries and sees that new
observation. The parent cannot read it, while a separately trusted descendant can.
Reflection and promotion are not invoked or conflated. Human provenance remains scoped.

Correlations survive without granting authority; a forged trace leaves visibility
unchanged. There is no exposed global activity/revision counter. Direct foreign IDs
and missing IDs return identical denials. Malformed topology behind the forbidden
branch, malformed JSON/references and unavailable/invalid current policy fail closed.
Normal retrieval never exports raw audit logs or binding-evidence identifiers.

## Mutation controls and integrity

| Mutation | Actual observed defect | Independent result |
| --- | --- | --- |
| Trust serialized scopes | Protected root/foreign/sibling/descendant records returned | Exit 1; 6 failed checks; 16 content / 24 metadata hits across replays |
| Trust stale P1 snapshot | old-rule reappears under current restrictive P2 | Exit 1; 8 failed checks; 4 content / 4 metadata hits |
| Trust serialized provenance | Failure becomes success; observation becomes human declaration | Exit 1; 4 failed checks |

Default behavior is restored. Two fresh runs with hash seeds 7/83 reproduce primary
results and exports byte-for-byte. Real PID/PPID evidence varies and is checked
separately. Initial evidence retains a scanner false positive for the permitted word
`observation`; its scope calculation was corrected. Review also fixed complete JSON
marker accounting and explicit subprocess participant dispatch. Corrections are
recorded with source hashes; **frozen primary expectations and thresholds did not change**.

Evidence: [summary](../../experiments/track-iii-010/evidence/summary.json),
[primary results](../../experiments/track-iii-010/evidence/primary/results.json),
[exports](../../experiments/track-iii-010/evidence/primary/exports.json),
[verification](../../experiments/track-iii-010/evidence/verification.json),
[mutations](../../experiments/track-iii-010/evidence/mutation-controls.json),
[reproduction](../../experiments/track-iii-010/evidence/reproducibility.json).

## Architecture implications and stopping point

Context semantics survive these bounded boundaries without weakening the accepted
hierarchy, security or provenance model. Serialize references and historical facts;
re-resolve authority and re-query Memory against trusted current state. Old receipts
remain evidence of past decisions. The minimal experimental adapter is not a production
contract and does not change PolicyGate, Completion Contracts, Restate, Cognitive Loop,
remote execution or the historical experiments. III.8's FAIL is unchanged.

The experiment assumes an atomic trusted snapshot per operation. Production issuer
identity, concurrent policy/topology changes, action-time enforcement, crash consistency,
revocation latency, cross-host authentication, transport, durable storage and distributed
idempotency remain unresolved. Hashes/PID observations are experimental integrity checks,
not security attestation. No remote-machine or production durability claim follows.

Recommend a **separately authorized architecture consolidation and contract gap review**
next: define reference issuance/resolution, snapshot freshness/atomicity, scoped evidence/
diagnostics and per-operation enforcement ownership across existing runtime boundaries;
then propose one minimal integration slice and its acceptance evidence for human review.
No new increment or implementation is started here. No human decision is needed to
close III.10; production contract and integration-priority choices need future approval.
