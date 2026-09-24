# Track III.9 — Novelty and simplicity advisory

**2026-09-23 — PASS within the frozen synthetic proposal corpus.**
III.8 remains FAIL; III.8R remains its separately recorded PASS recovery.
**III.10 is not started. No hard gate or production integration was implemented.**

## Hypothesis and scope

Fresh, permitted workspace awareness should help a bounded model avoid duplicate
abstractions while retaining justified additions and material contract differences.
Broad retrieval alone cannot prove that a model will use evidence correctly.

Novelty asks whether an existing abstraction satisfies the current intended contract.
Simplicity asks whether another abstraction or wrapper is justified at all. The
[generic guidance](guidance.txt), adapted from the III.1 Ponytail findings, labels
these concerns separately and is **identical in both conditions**. The experimental
variable is the workspace packet, not a stronger instruction to avoid creating code.
This does not separately establish a causal benefit from the simplicity wording.

The model chooses REUSE_EXISTING or CREATE_NEW. Nothing blocks code creation or
confers authority on similarity, source-family normalization, embeddings or graphs.
Current Task evidence is primary; workspace indexes remain derived views of source.
Learned Memory is not a variable. Runtime lifecycle, PolicyGate, Completion Contracts,
promotion, verified-outcome admission and remote execution remain unchanged.
The [request](request.json) is unsubmitted: no suitable runtime binding was exposed,
and this experimental result is not an assertion about a running Restate Task.

## Recovery and integrity

The UI/process interruption occurred after fixture creation and two loopback inventory
GETs, before collection, formal registration or cognition. Inspection found no tracked
changes, no runner, an empty evidence directory and no partial inference result.
[recovery.json](evidence/recovery.json) pins every recovered file and records the first
incomplete steps. All JSON/Python parsed and both source manifests matched their files.
Those valid fixtures were preserved; fixture generation was not repeated.

[fixture-freeze.json](evidence/fixture-freeze.json) freezes the recovered corpus and
collector/data binding before collection. [preregistration.json](evidence/preregistration.json)
pins the runner, checker, original model adapter, original selector, prompts, budgets,
source files and actual advisory inputs before the first Qwen comparison.
**No fixture, prompt, ranking-policy or threshold tuning followed model outcomes.**

Per-call response journals in [calls](evidence/calls/) are written before a decision
is accepted. A pending request without a response stops rather than silently repeating
an uncertain call. Completed responses can be replayed locally for validation. No
completed generation call was repeated in recovery or evidence checks.

## Frozen corpus and authoritative oracles

[proposals.json](proposals.json) SHA-256:
`54c7e368549820df132102a3682342eed01e9d193d5fdac7e87888ae1297b2f5`.
Exactly 12 proposals: four DUPLICATE, four LEGITIMATE_ADDITION, four
NEAR_MATCH_MISMATCH. [oracles.json](oracles.json) independently specifies expected
choices/targets, required discovery candidates and material contract facts.
The model never receives group labels, oracle choices or a declaration that a
proposal is a duplicate.

The synthetic repository has 18 Python files per revision, including interfaces,
implementations, imports/calls, eight repetitive telemetry helpers, a neighboring
incomplete trim helper and an isolated protected source. Current cognition uses B.
A supplies stale-index controls; an old fold module/symbol is moved and renamed in B.
[revisions.json](revisions.json) pins every byte:

| Revision | Manifest identity |
| --- | --- |
| A | `sha256:11309396a9afe4cc361129aece403cc379ba61138432f3340196ecb7481e3ffd` |
| B | `sha256:0fa698619624e33725ad3227c615630374a51cc3848866a04587124626515771` |

| Group | Proposal contracts |
| --- | --- |
| Duplicate D1–D4 | Strip/casefold handles; admit capped 5xx retries; process-local digest/first-ack memo; synchronous atomic single-file overwrite. |
| Legitimate L1–L4 | Durable asynchronous transfer lifecycle; tenant quota accounting; immutable multi-file versions; locale-aware comparison without transforming labels. |
| Near-match N1–N4 | Preserve case while trimming; retry only 429 and reject 5xx; durable cross-process receipts; append-only history rather than overwrite. |

Topic queries are deliberately shared across duplicate, legitimate and near-match
proposals; current contract differences, not query-specific verdicts, govern choices.
Each condition receives the same current contract and local entry-module evidence.
The baseline has no broad-library packet and cannot invent unseen target IDs. This
is intentional bounded information availability, not a comparison against unrestricted
repository exploration. Decisions are proxies for duplication; no actual abstractions
are added to a production repository.

## Unchanged III.8R pipeline

[bind.py](bind.py) imports the actual original III.8 discovery and III.8R recovery
functions and changes only their experiment data-root bindings. The original files
and function bodies are unchanged; [policy.json](policy.json) is byte-identical to
III.8R's policy. The original Graphify normalization statements are reused unchanged.

The collector uses the existing BGE-M3 client and real Graphify checkout at
`b9cd9570728a5ff3485d2a1e36fe9a1272a368ae` (v0.9.64), with domain-separated extraction,
temporary caches and the existing offline socket guard. Five local embedding requests
produce 48 vectors. No Claude Context, new embedding model, database or persistent
service is introduced. The collection directory retains completed batch responses.

Pipeline: broad BM25/cosine/structural discovery → per-contribution source/revision
and security validation → canonical target deduplication → RRF k=60 → exact-symbol
priority → source-family diversity → whole-entry compact packet. Excerpts remain
80 characters. No query-specific weighting or oracle exception was added.

One scoped revision, path/symbol/line, discovery codes L/S/G, indexed relations and
all diagnostic/truncation metadata are counted in the same **2048-byte** packet.
Packets are supplied directly as derived observation records without extra advisory
fields. Generic instructions are common to both conditions, outside this variable
retrieval packet. The complete cognitive request remains separately bounded by the
existing adapter; the 2 KiB limit is not a claim about total model input size.

D1's RuneFold target is absent from lexical candidates but present in semantic
retrieval and the final packet. D2/Fence and D3/Ledger likewise have **S-only** selected
provenance. D4/SwapWriter has **LSG** provenance. Real structural relations participate,
but no structural-only behavioral ablation was run. **Structural incremental utility
remains UNPROVEN**; we do not credit its presence as causal improvement.

## Cognition and deterministic decision contract

The unchanged `runtime/kernel/model.py::LocalModelCognition` calls the accepted
loopback endpoint `http://127.0.0.1:8000/v1`, provider `local.vllm`, model
**nvidia/Qwen3.8-27B-NVFP4**, temperature **0**, thinking **disabled**, max_tokens **768**.
Inventory and exact requests/responses are retained. No cloud cognition was used.

Both conditions have at most **three actions**: repeat current facts through
artifact.read, commit a structured answer through artifact.write, or request COMPLETE.
The first answer is immutable; malformed outputs consume budget. There is no arbitrary
workspace exploration or hidden tool advantage. Correctness comes from the frozen
oracle, not model prose, COMPLETE, or a successful provider response.

Answer shapes are `{"decision":"CREATE_NEW"}` and
`{"decision":"REUSE_EXISTING","existing_target":"path::symbol"}`. Correct reuse
requires the expected existing target. Wrong/invalid reuse does not earn duplicate-
reduction credit: the protocol additionally requires at least two more correct reuse
choices, alongside at least two fewer duplicate CREATE_NEW choices per repetition.

Two complete paired repetitions reverse OFF/ON order. Predeclared gates require
at least two fewer duplicates each repetition, absolute 4/4 legitimate correctness,
absolute 4/4 near-match correctness, zero paired regressions, zero stale/forbidden
advisory references, bounded packets and an actual caught behavioral mutation.

## Results

Both repetitions produced the same committed decisions:

| Outcome | Advisory OFF | Advisory ON |
| --- | ---: | ---: |
| Duplicate introductions | 4/4 | 0/4 |
| Correct existing-target reuse for duplicates | 0/4 | 4/4 |
| Legitimate additions correctly allowed | 4/4 | 4/4 |
| Material near-match distinctions preserved | 4/4 | 4/4 |

**Duplicate reduction: four per repetition**, exceeding two. No legitimate-addition
or near-match regressions. Across repetitions there are eight fewer duplicate choices;
these remain four fixture types, not eight independent problem shapes.

**406 independent checks PASS.** Maximum primary advisory **2012 bytes**. Zero stale
and zero forbidden emitted references. Every required discovery candidate was included.
D1 correctly reuses RuneFold in both advisory-on cases despite its unknown exact name
and lack of a lexical hit. This is the motivating broad-awareness case.

**58 Qwen calls:** 56 primary, two mutation. Eight initial outputs used fenced JSON
and were rejected by the existing adapter: D1/ON, D4/ON, L1/ON and N1/OFF in each
repetition. Each recovered within two actions. These were format retries, not facts
rereads; [action-metrics.json](evidence/action-metrics.json) retains that cost.
No committed-decision or action-count variance appeared across repeats. This small
observation does not prove probabilistic model determinism or universal behavior.

## Security, freshness and false-equivalence control

Trusted personal-task lineage intersects the personal/public grant and policy;
employer-x is an unrelated protected branch. The protected VaultFold is the **top
semantic match** for D1 in an internal global control, yet no protected path, symbol,
source, graph relation or diagnostic reaches cognition. Relevance is not authority.

The stale ArchivedFold is semantic rank **5** when A-derived data is queried for B.
The stale-safe control excludes it before selection, preserves independently fresh
lexical contributions and emits only current lexical evidence. No stale identifier
appears in primary model input. Administrative synthetic evidence deliberately retains
private/stale candidates for audit; it is not a caller-visible packet.

The fixed mutation changes only RuneFold's selected excerpt, falsely presenting it
as strip-only and case-preserving. It changes neither Task requirements nor source
files and issues no reuse command. N1 then incorrectly chooses REUSE_EXISTING in
**both repetitions**, whereas unmutated N1 chooses CREATE_NEW. The independent
checker applies the same contract oracle and **exits 1**, with two false-equivalence
failures. Final presentation can invalidate otherwise safe discovery; semantic
contract distinctions must survive rendering.

Default packets are unchanged afterward. Two offline hash-seeded runs reproduce the
selector and checker byte-for-byte using retained vectors and model responses, with
**zero additional model calls**. Mutant rendering is isolated and never the default.

## Evidence and reproduction

| Artifact | Scope |
| --- | --- |
| [recovery](evidence/recovery.json), [fixture freeze](evidence/fixture-freeze.json), [preregistration](evidence/preregistration.json) | Interruption assessment, preserved corpus and pre-comparison hashes. |
| [raw candidates](evidence/results.json), [advisory results](evidence/advisory-results.json) | Mechanism lists, validation/dedup/fusion, ranks, omissions and exact packets. |
| [behavior](evidence/behavior.json), [calls](evidence/calls/) | Every model input, raw response, adapter validation and committed choice. |
| [verification](evidence/verification.json), [summary](evidence/summary.json) | Independently recomputed oracle outcomes and frozen thresholds. |
| [mutation](evidence/mutation.json), [mutation control](evidence/mutation-control.json) | Actual incorrect reuse and nonzero oracle-check exit. |
| [safety controls](evidence/safety-controls.json), [reproduction](evidence/reproducibility.json), [documentation checks](evidence/documentation-checks.json) | Protected relevance, stale exclusion, deterministic retained-evidence integrity and repository checks. |

```bash
python3 experiments/track-iii-009/check.py --output /tmp/iii9-verification.json
# Expected exit 1, applying the same contract oracle to the mutation:
python3 experiments/track-iii-009/check.py --mutation-only --output /tmp/iii9-mutation-check.json
```

These commands perform no inference and do not rewrite retained evidence. Do not
rerun model execution to establish reproducibility; inspect the completed call
journals. The checker reconstructs source/AST facts and parses raw provider decisions,
checks exact prompts/decoding/budgets and calculates metrics independently of summary.
No primary N1–N6 failure classification applies because all gates passed. The isolated
mutation deliberately demonstrates representation corruption leading to false equivalence.

## Interpretation, limits and architecture implications

The advisory demonstrates behavioral value on this finite synthetic information-
availability comparison. It supports contract-aware advice, **not a hard gate**.
Current evidence, scoped source references and material differences remain essential.
The model never receives a verdict that a proposal is duplicate; it makes the choice.

The known corpus is small and Python-only, with unusually compact contracts and
repetitive distractors. Decisions are not actual implemented code or measured long-term
architectural entropy. Some source details are absent from 80-character snippets:
Ledger's exact hash algorithm is in its full implementation, beyond the displayed
contract. Correct target choice does not prove that cognition verified that detail.
Larger evidence demands may expose representation failures. Simplicity wording and
structural retrieval have no independent causal ablations here.

Operational costs are five embedding calls, four isolated Graphify extractions,
source validation/rank fusion, and extra context/model format recovery. No production
service was added. Open questions include richer contract extraction, uncertainty
handling, source revalidation at action time, representative repositories, incremental
freshness, snippet adequacy, prompt overhead and human review policy. Source-family
similarity must never become an equivalence verdict merely because this run passed.

## Exact proposed III.10 experiment — not started

Freeze 12 lineage-transfer cases: four local handoffs (worker, verifier, forged sibling
scope, forged caller/provenance); four durable checkpoint/resume cases (valid resume,
replay, changed denied policy, malformed topology behind a denied boundary); and four
remote-process cases (valid trusted handoff, altered domain, stale authority binding,
interrupted/replayed handoff with missing outcome evidence).

Use two isolated processes and explicit synthetic trusted binding/checkpoint fixtures;
no production Restate/remote integration or authentication system. Exercise current-
context writes and bounded reads before/after transitions. Independently compare
lineage/domain/policy/provenance and authoritative outcome expectations. Require all
12 expected outcomes, zero scope expansion or provenance upgrades, zero forbidden
content/metadata, 2 KiB responses and replay revalidation. A mutation trusting serialized
caller scope and a mutation reusing obsolete policy authority must cause caught leaks
or unauthorized effects. Retain checkpoint/handoff/evidence traces and independent
checks. Do not equate serialization with authority or old receipts with current grants.

No human architectural decision is required to close III.9. This proposal requires
explicit authorization. **III.10 has not started; no production hard gate is justified.**
