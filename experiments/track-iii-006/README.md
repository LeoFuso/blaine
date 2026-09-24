# Track III.6 — Verified outcome admission and reflection semantics

**PASS — offline deterministic experiment, 2026-09-23.**

Hypothesis: a trusted outcome/evidence boundary can qualify hand-authored reflection
candidates without treating worker/model claims as completion evidence. Success,
failure and unfinished observations must retain different semantic statuses and stay
inside their current bounded context. Reflection admission is not promotion.

## Accepted foundations and implementation boundary

The [III.1 research](../../docs/research/track-iii/001-reference-systems.md) and
[III.2 tree](../track-iii-002/README.md), [III.3 continuous capability](../track-iii-003/README.md),
[III.4 security](../track-iii-004/README.md), [III.5 promotion](../track-iii-005/README.md)
remain accepted. Their increments were not rerun or rewritten. The imported
ContextTree, capability, SecurityMemory and PromotionGate source hashes match their
accepted versions. No production contracts or behavior changed.

[admission.py](admission.py) is a Python standard-library experiment, not a production
schema. The harness owns execution bindings, requirements, envelopes, evidence and
the explicit candidate-support catalog. Caller requests cannot populate these stores.
This assumes trusted issuance and confinement of the request surface; it is not a
sandbox against hostile Python code with access to internals.

No LLM, arbitrary-language entailment, production Completion Contract, Restate,
Cognitive Loop, MIRIX, database, embeddings, Graphify, Claude Context, remote worker,
consolidation, utility/decay, revocation or concurrency implementation is involved.

## Hierarchy and trusted outcome boundary

The fixture reuses III.5's generic topology and adds protected descendant/sibling
probes. Labels never select memory behavior:

```text
root [public]
├── personal
│   └── project-personal
│       └── parent-personal
│           ├── child-personal
│           │   └── attempt-personal
│           └── sibling-personal
└── employer-x
    └── project-x
        ├── task-x
        │   └── work-x
        └── task-x-sibling
```

Personal execution cases bind to child-personal; protected case X binds to task-x.
The only initial memory is explicitly public baseline knowledge. Observations,
declarations and learned candidates enter through separate trusted paths.

Three objects remain distinct:

| Object | Authority |
| --- | --- |
| Worker claim | Untrusted SUCCESS/FAILURE/UNKNOWN plus text. Never establishes outcome. |
| Outcome envelope and evidence | Trusted synthetic stores, resolved from the issued execution binding. |
| Reflection candidate | Proposed content and SUCCESS/FAILURE/OBSERVATION intent, subject to admission. |

Each trusted execution specification fixes context, domain, required evidence IDs,
evidence kinds, expected success values and the completion-contract reference. The
outcome envelope must match that specification exactly; it cannot silently remove
a required test. Each evidence row must match execution/context/domain/ID/kind and
has a result, verifier identity, synthetic support facts and private raw diagnostics.

An opaque token maps to one trusted ExecutionContext. The closed request is:

```json
{
  "op": "admitReflection",
  "request_id": "local-request-key",
  "worker_claim": {"status": "SUCCESS", "text": "Everything passed."},
  "candidate": {"content": "Strategy A succeeded for problem shape P.", "intent": "SUCCESS"}
}
```

Source execution, context and domain come from the binding, not this payload.
Additional outcome, evidence, scope, status, provenance, completion or evidence-complete
fields reject. Fabricated and foreign tokens reject. The status assigned to a new
record comes exclusively from trusted admission code.

## Deterministic qualification and candidate support

VERIFIED_SUCCESS requires a SUCCEEDED envelope and **every** fixed requirement:
contract PASS, required test/verifier PASS, artifact PRESENT, and any additional
mandatory platform verifier PASS. FAIL/ABSENT contradict a claimed successful
outcome; MISSING/UNKNOWN/NOT_RUN leave it incomplete. Unavailable evidence prevents
admission. Missing rows are not satisfied requirements.

VERIFIED_FAILURE requires a FAILED envelope, contract FAIL and at least one
non-contract failure (FAIL/ABSENT). A missing artifact does not erase an independently
verified failed test/verifier; it still cannot support success. A PASS contract with
a failed mandatory check, or a FAILED envelope with a PASS contract, is contradictory.
Malformed/foreign evidence and mismatched requirements also fail closed.

A complete outcome alone is insufficient to admit arbitrary prose. The trusted
fixture catalog lists exact candidate content/intent and required tagged support
facts for each execution. Candidate text must match its hand-authored pair, and
required facts must exist in resolved trusted evidence. Failure condition Q cannot
be admitted when its support fact is removed. An unrelated “Strategy Z always works
everywhere” candidate rejects even for a successful execution.

**This catalog is a synthetic entailment assumption**, not a natural-language reasoner.
VERIFIED_SUCCESS/FAILURE means the supplied candidate was qualified against its
explicit fixture pair and evidence snapshot. It does not establish that a strategy
caused success, always works, or generalizes beyond those conditions. Evidence remains
authoritative; memory remains a derived representation.

## Required outcomes and controls

| Case | Authoritative fixture | Success candidate | Other permitted result |
| --- | --- | --- | --- |
| A | Contract PASS, required test PASS, artifact PRESENT | ADMITTED_VERIFIED_SUCCESS | Worker claiming failure does not change the trusted result. |
| B | Contract FAIL, test FAIL; worker claims success | REJECTED_UNSUPPORTED | Supported condition-Q candidate becomes ADMITTED_VERIFIED_FAILURE. |
| C | Contract UNKNOWN, test/artifact MISSING | REJECTED_UNSUPPORTED | Explicit observation is RETAINED_UNVERIFIED. |
| D | Contract FAIL, deterministic verifier FAIL with condition Q | REJECTED_UNSUPPORTED | Approach-B/condition-Q candidate becomes ADMITTED_VERIFIED_FAILURE. |
| E | Contract PASS, mandatory test FAIL | REJECTED_CONTRADICTORY | No record is written. |
| F | Implementation PASS, required platform test NOT_RUN, contract UNKNOWN | REJECTED_UNSUPPORTED | Scoped attempted-work observation is RETAINED_UNVERIFIED. |
| G | SUCCEEDED envelope and PASS contract, but required test MISSING | REJECTED_UNSUPPORTED | Additional missing-as-pass mutation target. |
| X | Complete protected-domain success evidence | ADMITTED_VERIFIED_SUCCESS | Record stays task-x/employer-x-private. |
| Cancelled | CANCELLED envelope, unfinished checks | REJECTED_UNSUPPORTED | Explicit observation remains UNVERIFIED. |

Every required success component is independently changed to FAIL/ABSENT, MISSING,
UNKNOWN, UNAVAILABLE and NOT_RUN. None becomes verified success. Further cases cover
absent evidence rows/envelopes, removed requirements, foreign execution/domain,
malformed result, missing support facts, unsupported text and unavailable/malformed
security policy. Opposite worker claims cannot override either success or failure.

| Admission result | Meaning |
| --- | --- |
| ADMITTED_VERIFIED_SUCCESS | Exact candidate is supported by a complete trusted successful outcome. |
| ADMITTED_VERIFIED_FAILURE | Exact failure-qualified candidate is supported by trusted failure evidence. |
| RETAINED_UNVERIFIED | Explicit observation remains an AGENT_OBSERVATION, not verified knowledge. |
| REJECTED_UNSUPPORTED | Insufficient evidence, mismatched intent/content, invalid caller fields/binding, or conflicting request snapshot. |
| REJECTED_CONTRADICTORY | Inconsistent/malformed authoritative evidence or identity/requirement mismatch. |
| UNAVAILABLE | Admission/memory capability, security policy or required evidence is unavailable. |

Success-intent text is **not stored** when evidence is incomplete. A separate
observation candidate can retain useful uncertainty. Contradictory or unavailable
inputs cannot be bypassed by changing candidate intent. External failures contain
only status and a status-only diagnostic; no evidence IDs, logs or verifier detail.
When the security policy itself is unavailable, memory reads also return UNAVAILABLE,
not DENIED; this preserves the previously accepted result-state distinction.

## Provenance, security and continuous access

Verified records use the newly needed **experimental** provenance VERIFIED_OUTCOME
and separate VERIFIED_SUCCESS/VERIFIED_FAILURE status. Unfinished observations keep
AGENT_OBSERVATION/UNVERIFIED. All are marked REFLECTION_CANDIDATE; this does not
implement a lesson/procedure taxonomy or consolidation.

The internal provenance map links each admitted entry to its execution, exact
outcome envelope, fixed requirements, evidence rows/verifier results, explicit
candidate support and snapshot digest. The source stores remain unchanged. Ordinary
memory retrieval exposes only scoped candidate content, creator, origin/status and
a fixed admission marker/version. It does not include raw logs, evidence IDs, private
verifier names, envelope IDs, support facts or snapshot hashes. The entry ID is the
key for the internal audit mapping; no general evidence retrieval API is exposed.

For every scenario, direct reads at all 12 contexts prove the exact boundary:

- child-personal candidates are readable only there and at attempt-personal;
- task-x candidates are readable only there and at work-x;
- parents, projects, domain ancestors, root, siblings and unrelated domains cannot
  read a newly admitted child record.

A later worker uses the **same issued execution binding** to read the new record
through Memory. No prior prompt/result blob is handed off. Knowing an evidence ID
cannot retrieve its raw record through Memory, even from the source context.

Verified status does not grant public/declassified/generalized visibility. Literal
scans cover complete serialized retrieval/diagnostic exports. Private evidence
canaries must be absent even from permitted learned-memory retrieval; protected
memory identifiers/domain metadata must be absent from foreign/public outputs.
Privileged experiment reports intentionally also contain raw synthetic evidence and
mutant admissions; those are not caller-visible telemetry.

A trusted human still declares directly into its authorized project context with
USER_DECLARATION provenance, without producing a reflection audit or work-evidence
provenance. Human teaching does not enter verified-work admission.

## Reflection is not promotion; replay is not authority

Local IDs use `<bound-context>::reflection-N`. Allocation and the reused visibility
revision are scoped to permitted knowledge, never global activity. Each scenario
asserts zero public revision change after private local admission. No ancestor record
is created and ordinary writes cannot forge verification metadata.

III.5's PromotionGate remains a separate operation. Its frozen experimental schema
recognizes only the older observation/declaration status classes and **rejects the
new VERIFIED_OUTCOME class**. An explicit call demonstrates fail-closed rejection
with no write effects. This is an honest prototype compatibility boundary, not an
architectural contradiction or an automatic upgrade/downgrade. Supporting verified
candidate promotion later requires an explicit versioned extension that preserves
origin/status and all prior gates; no such extension is implemented in III.6.

Replay identity is execution plus local request key. All current evidence/policy and
candidate support are reevaluated before consulting a private snapshot fingerprint.
Identical immutable evidence returns the same result/record without duplicate effects.
Changing a required test to MISSING rejects; changing it to FAIL against a PASS
contract rejects as contradictory. Restoring valid evidence under a new envelope ID
still cannot silently reuse the old request key. A fresh request against that valid
new snapshot can admit a new, separately evidenced record.

Old records remain historical admissions for their captured evidence snapshots.
They are not proof of the Task's present state. This increment intentionally does
not revoke, delete or rewrite a prior memory after evidence changes.

## Results, mutation evidence and reproduction

**1122/1122 checks PASS; 958 independent evidence checks PASS.** There are 54 retained
admission scenarios plus separate declaration, replay, promotion and evidence-ID
probes. **708 retrieval exports scanned; zero leaks.** Gate receipts and inherited
memory responses remain bounded; per-scenario receipt limits are checked at 2 KiB.

Two isolated runner-only controls execute the same oracles:

| Mutation | Observed defect |
| --- | --- |
| Worker success claim replaces authoritative classification | **141 failed checks, exit 1**. Case B actually stores VERIFIED_SUCCESS despite FAIL contract/test evidence. |
| MISSING/UNKNOWN/NOT_RUN evidence is treated as required success | **55 failed checks, exit 1**. Case G actually stores VERIFIED_SUCCESS with a missing required test. |

These are actual unsafe admissions, not test crashes. The independent checker
inspects the mutated stored record and underlying FAIL/MISSING evidence. Security
isolation alone cannot detect false success; outcome assertions are separately
necessary. Neither mutation is active in admission.py. Correct execution after both
controls is identical. Two fresh hash-seeded processes reproduce retained primary
JSON artifacts byte for byte. Hashes are reproducibility evidence, not signatures.

Python 3.10+, standard library only:

```bash
python3 experiments/track-iii-006/probe.py --output /tmp/blaine-iii6-reproduction
python3 experiments/track-iii-006/verify.py /tmp/blaine-iii6-reproduction
```

Standalone controls intentionally exit 1:

```bash
python3 experiments/track-iii-006/probe.py --variant worker-claim --output /tmp/blaine-iii6-worker-mutant
python3 experiments/track-iii-006/probe.py --variant missing-as-pass --output /tmp/blaine-iii6-missing-mutant
```

| Artifact | Retained evidence |
| --- | --- |
| [fixtures.json](fixtures.json) | Executions, requirements, trusted envelopes/evidence, worker claim, support pairs and literal expectations. |
| [results.json](evidence/results.json) | Expected/actual checks, source snapshots/digests, private provenance/audit, all-context reads and replay/promotion probes. |
| [retrieval-exports.json](evidence/retrieval-exports.json), [leakage.json](evidence/leakage.json) | Complete caller-visible projections and scan result. |
| [worker-claim.json](evidence/worker-claim.json), [missing-as-pass.json](evidence/missing-as-pass.json) | Unsafe controls, stored false-success records and original evidence. |
| [restored.json](evidence/restored.json), [summary.json](evidence/summary.json) | Correct restoration, subprocess exits, counts, hashes and stop boundary. |
| [verification.json](evidence/verification.json), [reproducibility.json](evidence/reproducibility.json) | Independent assertions and byte comparisons. |
| [documentation-checks.json](evidence/documentation-checks.json), [request.json](request.json) | Repository checks and unsubmitted TaskSpec; no runtime Task identity/state claimed. |

## Implications, limitations and unresolved questions

**The conceptual ContextNode + continuous Memory + SecurityContext + PromotionGate +
VerifiedOutcomeAdmission composition survives.** A new experimental verified-outcome
origin/status is necessary for this increment; the earlier prototypes are not silently
made wire-compatible with it. Verified outcome qualification, contextual visibility,
promotion authority and epistemic generalization remain independent decisions.

Useful findings: failure can be established despite an absent success artifact;
partial work cannot satisfy an all-required-success contract; a previously admitted
memory cannot substitute for current evidence; and exact support pairing is needed
even when an execution succeeded. None establishes arbitrary natural-language
entailment, causal effectiveness or transfer to future work.

Open questions: production authoritative envelope format/issuer, candidate support
validation, verifier trust and evidence completeness, promotion schema extension,
multi-source outcomes, contradictory evidence precedence, immutable evidence versions,
stale-memory presentation, concurrency/durable idempotency, retention and revocation.
These are future contracts/experiments. No human architectural conflict requires a
decision to close this bounded increment.

## Exact proposed III.7 experiment — not started

Hypothesis: correctly scoped success/failure-qualified hints can improve later bounded
work, while irrelevant or mismatched hints do not cause negative transfer.

1. Prepare **12 deterministic held-out task fixtures**: four matching learned conditions,
   four irrelevant conditions and four near-match traps. Pin expected artifact/test
   outcomes before comparing variants. Use hand-authored hints tied to admitted
   III.6-style success/failure records; do not generate/consolidate them with a model.
2. Run each task twice with the same fake worker, verifier and three-action budget:
   memory disabled versus bounded memory retrieval enabled (2 KiB). Place later work
   in permitted descendants of the knowledge context; do not bypass promotion to
   share across sibling/security boundaries.
3. Measure verified completion, failed/repeated approaches, actions and retrieved
   bytes. Require at least two additional verified completions overall, zero lost
   completions on irrelevant/near-match cases, correct provenance use and no scope
   leakage. Report each pair, including no-benefit and harmful results.
4. Add an isolated control that treats failure-qualified or mismatched knowledge as
   a successful procedure; a near-match verifier must expose the resulting regression.
5. Retain paired evidence, input/hint digests, explicit eligibility/routing rules and
   control failures. A PASS would show utility only for this finite synthetic corpus,
   not real model generalization or production effectiveness. No runtime adoption or
   automatic promotion is implied.

**III.7 has not started and requires explicit authorization.**
