# Track III.5 — Promotion and declassification admission gate

**PASS — offline deterministic experiment, 2026-09-23.**

Hypothesis: explicit admission can create an ancestor-owned representation while
preserving source identity, security and epistemic status. Cross-domain admission
must additionally require trusted, candidate-specific declassification approval and
all required deterministic checks. Generation and admission are separate concerns.

## Foundations and experiment boundary

The accepted [III.1 research](../../docs/research/track-iii/001-reference-systems.md)
and [III.2](../track-iii-002/README.md), [III.3](../track-iii-003/README.md),
[III.4](../track-iii-004/README.md) evidence remain historical foundations. Their
experiments were not rerun. The III.5 adapter imports III.4's SecurityMemory, which
imports the earlier binding/tree implementation. All three source hashes match their
accepted versions. No prior implementation or production contract changed.

[gate.py](gate.py) is a Python standard-library executable specification. Trusted
fixture construction, token issuance, approvals, source labeling and audit access
are outside the caller surface. It is not production authentication, authorization,
DLP, a hostile-code sandbox, a durable transaction or distributed enforcement.
No LLM, real scanner service, network, database, MIRIX, embedding, Graphify, reflection,
Completion Contract, Restate or production worker/runtime integration is involved.

## Topology and promotion semantics

[fixtures.json](fixtures.json) contains this generic tree, independent context-domain
assignments, source entries, authority bindings, routes and all candidates:

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
        └── task-x
```

All non-root contexts are private to personal or employer-x. Node kind is `generic`;
no behavior depends on project/task/attempt terminology. Permitted reads still
intersect structural lineage, domain visibility and policy. Ordinary writes stay
in the bound context, never at a parent or arbitrary destination.

The accepted research requires **one parent edge per promotion**. The two fixture
routes are child-personal → parent-personal and employer-x → root. The latter source
already exists at employer-x as trusted initial fixture data; the experiment does
not silently jump from task-x to root. Siblings, descendants, self, unrelated nodes,
missing destinations, skipped ancestors and an unapproved immediate-parent route
are rejected. Broader promotion would require separate future admissions at each
edge; chained promotion execution is not implemented here.

Three operations remain distinct:

| Operation | Authority and effect |
| --- | --- |
| Ordinary observation write | Existing worker binding; writes only current context, private and unverified. Extra target/public/verified/declassified fields deny. |
| Human declaration | Existing trusted human token; one fixture-authorized project/parent target, USER_DECLARATION provenance. No promotion audit or source transfer. |
| Promotion | Separate trusted promotion binding, explicit request, route and admission gate. Creates a new destination representation; leaves the original unchanged. |

There are AGENT, HUMAN and SYSTEM_PROMOTION_SERVICE fixture roles. Only the service
role is issued promotion authority. Agent authorship and human identity alone grant
none. A fabricated/foreign token or caller-supplied role cannot become that service.
No generalized human authorization policy is implemented.

## Request, authority and admission

The closed experimental request shape is:

```json
{
  "op": "requestPromotion",
  "request_id": "source-local-request-key",
  "source_id": "protected-source",
  "destination": "root",
  "candidate": {"content": "Hand-authored generalized candidate."}
}
```

The caller may propose source/destination/content; these are proposals, not grants.
The issued binding determines source context, security domain, principal and role.
Source must exist, be readable, and belong to the bound current context. Destination
must be its immediate parent and an explicitly permitted route. Unknown/invisible
source IDs receive the same generic policy rejection for a scoped service; authority
rejection happens before source lookup for an unauthorized caller.

Payload additions such as promotion authority, caller role, declassification status,
provenance, scanner/policy result, public flag and destination override are rejected.
Candidate fields that claim VERIFIED_OUTCOME are rejected. Malformed/unavailable
promotion or security policy cannot fall back to ancestry alone.

Cross-domain promotion also needs a trusted approval for the exact **source digest,
source ID, destination and candidate digest**, under the fixed gate/policy versions.
Missing or uncertain approval and source changes reject admission. Approvals live
outside the request payload. The fixture deliberately includes approvals for unsafe
candidates too, so scanners are tested independently of approval presence; this does
not assert those candidates were semantically safe or properly reviewed in reality.

A clean scan is necessary but insufficient. The experiment makes no automated
judgment that a sentence is a valid abstraction. Its positive candidates and approval
records are hand-authored. A model could later propose a candidate but cannot grant
promotion authority or determine security admission.

## Same-domain and cross-domain outcomes

Same-domain policy explicitly permits UNVERIFIED observations and DECLARED human
sources to be broadened **without upgrading those statuses**. Both positive fixtures
are admitted. A secret-pattern check is mandatory even within the same domain;
a synthetic token candidate is rejected. No verified outcome, lesson or procedure
is created.

At the boundary, a raw protected copy and each unsafe category are rejected. A safe
hand-authored Strategy candidate is admitted only with approval and all clean checks:

> When runtime behavior varies substantially behind a stable contract, separating
> behavior via Strategy can reduce conditional branching; first search for an
> existing canonical abstraction.

A human-origin safe candidate can also pass the same boundary gate, but raw protected
USER_DECLARATION content cannot. Human origin never automatically declassifies data.

The new record preserves the source's provenance class and epistemic status and
marks itself `PROMOTED_REPRESENTATION`, created by `promotion-gate`. Thus a retained
USER_DECLARATION origin means **derived from a human declaration**, not that the
human directly authored the transformed candidate. Full original creator/source
information remains auditable privately. Neither admission nor origin establishes
truth or Task completion.

## Deterministic scanners and failures

Nine synthetic scanners inspect candidate content:

| Check | Bounded mechanism |
| --- | --- |
| Secret/token | A regex for synthetic `SYNTH_TOKEN_…` fixtures; no real credentials. |
| Organization/domain | Manifest identifier match. |
| Project/repository | Manifest identifier match. |
| Hostname/internal URL | Manifest literal match. |
| Ticket | Manifest literal match. |
| Class/package/source | Manifest literal match. |
| Database/table | Manifest literal match. |
| Exact protected literal | Explicit protected-marker match. |
| Source fragments | Any eight contiguous normalized source tokens also occurring in the candidate; punctuation/case differences are ignored. |

Each unsafe category's own scanner is independently checked to return a match.
These are finite corpus checks, not complete DLP, secret scrubbing, semantic
abstraction, a useful recall/precision benchmark or real near-duplicate detection.
Scanners reject; they do not rewrite, redact or sanitize content.

For every required cross-boundary scanner, test six synthetic failure modes:
unavailable, crash, malformed output, unknown, timeout and cannot evaluate. **All 54
combinations fail closed** with no destination write. Timeouts are deterministic
exceptions, not real timers. Scanner exceptions become private failure records;
exception details never enter destination output. Only an exact clean result with
matching scanner/version and no matches can pass.

| Result | Meaning |
| --- | --- |
| ADMITTED | All requirements pass; new representation or identical successful replay. |
| REJECTED_POLICY | Invalid shape/source/route/status/policy or conflicting replay key. |
| REJECTED_AUTHORITY | Binding/role lacks promotion authority. |
| REJECTED_SECURITY | Missing declassification approval or detected protected candidate. |
| REJECTED_SCANNER | Required scanner cannot provide a valid clean/match evaluation. |
| UNAVAILABLE | Required policy, capability or scanner is unavailable. |

External rejection envelopes contain only status, null receipt and a status-only
diagnostic. Detailed scanner names, matches, source data and approvals are confined
to the private audit. Gate response byte bounds are checked against 2 KiB; memory
reads continue using III.3's inherited bounded envelope.

## Source, destination and metadata boundaries

Each scenario retains source snapshots and direct source-read responses before and
after admission. Source content, context, domain, classification, creator, provenance
and status remain identical. Destination gets a different record ID; the source is
not moved, rewritten, made public or removed. A later worker using the same source
execution binding can retrieve the admitted ancestor representation through the
continuous Memory capability.

Private audit records contain the source snapshot, source/candidate digests, caller,
scanner outcomes, approval and gate decision. They are harness-only protected
administrative evidence, not a public query API. A successful destination receipt
contains only admitted ID, origin class, epistemic status and fixed gate/policy
versions. Destination records contain generalized content and safe admission
metadata; no private source ID, path, creator, digest, match or request key is copied.
Rejected private attempts emit no destination event.

The entire serialized destination export includes records, metadata/provenance,
receipts, memory diagnostics and visible revision. The literal oracle scans that
whole projection, with independent verification. Full research reports intentionally
also contain protected synthetic inputs, audit and mutant leaks; those reports are
not the destination-visible projection and are not production-safe telemetry.

Admission IDs are freshly allocated under the destination namespace, for example
`root::admission-1`. Source IDs and caller request keys do not determine them. The
trusted loader reserves `::` for contextual runtime writes, so private callers cannot
occupy a different context's admission namespace. Tests compare hidden versus absent
source lookup/promotion probes and ordinary local-key collisions against a hidden
foreign record. Existing III.4 namespacing prevents cross-domain collision disclosure.

No global counter is introduced. The reused III.4 visible revision counts only
permitted post-setup records. A paired fixture adds a hidden private entry whose ID
matches the promotion request key, a private same-domain promotion and a rejected
cross-domain attempt. Public state stays at revision zero until a public admission;
the resulting public record/receipt/revision is identical to the quiet fixture.
Only the legitimately admitted public result changes public-visible state.

## Replay and negative control

Replay identity is scoped to source context, trusted principal and local request key.
The request/source/policy fingerprint stays private. **Every attempt rechecks authority,
policy, source, approval and required scanners before replay lookup.** An identical
successful request returns the same receipt without another record or revision change.
Changing candidate content under the same key rejects. An identical rejected request
stays rejected without destination effects. A later scanner failure rejects even if
the same request was previously admitted; the earlier valid record is not revoked.
Retention/revocation and production idempotency are out of scope.

The isolated runner-only `FailOpenControl` changes UNKNOWN/UNAVAILABLE scanner
outcomes to admissible. The same oracle suite fails with **42 failures and exit 1**.
Two unsafe token candidates are actually admitted to public root, and the independent
literal oracle detects **two leaking destination exports**. Other failures prove
missing scanners cannot be bypassed for safe text or positive replay either.

The unsafe subclass is never installed in gate.py. Correct execution afterward is
identical. Source/fixture hashes and two fresh hash-seeded runs establish reproducible
finite evidence, not authenticated audit signatures or a universal secrecy proof.

## Evidence and reproduction

**560/560 checks PASS; 512 independent evidence checks PASS.**
All **114 complete destination-visible exports** pass the protected-literal scan.
The evidence includes exact expectations, actual records, audits, all fault outcomes
and the separate destination export/scan. No runtime Task was submitted: the
[TaskSpec draft](request.json) is retained, with no claimed Task ID or lifecycle state.

Python 3.10+, standard library only:

```bash
python3 experiments/track-iii-005/probe.py --output /tmp/blaine-iii5-reproduction
python3 experiments/track-iii-005/verify.py /tmp/blaine-iii5-reproduction
```

Individual fail-open control, intentionally exit 1:

```bash
python3 experiments/track-iii-005/probe.py --variant fail-open --output /tmp/blaine-iii5-mutant
```

| Artifact | Evidence |
| --- | --- |
| [fixtures.json](fixtures.json) | Tree/security/policy, authority bindings, sources, candidates, approvals, scanner and leakage manifests. |
| [results.json](evidence/results.json) | Expected/actual checks; source snapshots/visibility; private audit, admitted records, replay and identifier probes. |
| [destination-exports.json](evidence/destination-exports.json), [leakage.json](evidence/leakage.json) | Complete public/destination projections and literal findings. |
| [fail-open.json](evidence/fail-open.json) | Unchanged-oracle control and actual unsafe admissions/leaks. |
| [restored.json](evidence/restored.json), [summary.json](evidence/summary.json) | Correct restoration, control exit, counts, source hashes and stop boundary. |
| [verification.json](evidence/verification.json), [reproducibility.json](evidence/reproducibility.json) | Independent assertions and fresh-process byte comparisons. |
| [documentation-checks.json](evidence/documentation-checks.json) | Links, JSON, imports, whitespace and changed-file boundary. |

## Architecture implications and limitations

**ContextNode + continuous Memory + SecurityContext + PromotionGate survives without
changing the accepted conceptual model.** Promotion is an explicit capability with
more authority than an ordinary observation write. A new destination record provides
controlled upward movement; source permissions continue unchanged. Metadata remains
subject to content's security boundary. No production architecture was modified.

Useful findings: replay must revalidate rather than return a remembered admission
before security checks; source origin and verification status must survive a change
in visibility; a public audit receipt must be a deliberate projection, not the raw
internal record. Same-domain admission of an unverified hypothesis is an explicit
fixture policy, not verified learning or a recommendation to promote all observations.

Remaining questions include who can approve declassification, how approval binds to
production policy/source revisions, semantic abstraction correctness and scanner
coverage, multi-source provenance, chained promotion, cross-domain audit access,
atomic/durable idempotency, concurrency, retention and revocation. Trusted labeling,
source completeness and approvals are assumptions here; malicious trusted code or
an incorrectly approved meaning is outside the deterministic proof. No real DLP or
production security claim follows. No human architectural conflict requires a decision
to close this increment.

## Exact proposed III.6 experiment — not started

Hypothesis: only an authoritative verified-outcome envelope may admit success-oriented
reflection candidates; failed/unverified work cannot acquire successful/verified
status through memory or worker claims.

1. Use offline **synthetic verifier/outcome envelopes**, with success, failure,
   unverified, cancelled and partial cases. Keep observations and declarations in
   their existing provenance classes. Do not integrate production Completion Contracts.
2. Supply hand-authored scoped reflection candidates and explicit outcome/evidence
   references. Test that only a matching trusted successful envelope can admit a
   success-labeled candidate; failure experiences may remain explicitly failures.
3. Reject missing/mismatched evidence, forged verifier/source fields, contradictory
   outcomes and unavailable verification. Preserve context/domain boundaries and
   source observations; reflection is not proof of causal strategy effectiveness.
4. Keep local candidate admission separate from the III.5 promotion gate. Any proposed
   broader visibility must independently pass promotion/declassification requirements.
5. Run a mutation that trusts worker success or candidate-provided VERIFIED status;
   it must cause a wrongly admitted success candidate and fail unchanged oracles.
6. Retain literal outcomes, evidence envelopes, state/provenance snapshots, rejection
   receipts and mutation/restoration evidence. No LLM-generated reflection, durable
   integration, lesson utility measurement or new production dependency is implied.

**III.6 has not started and requires explicit authorization.**
