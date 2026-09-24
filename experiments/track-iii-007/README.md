# Track III.7 — Learned memory utility

**2026-09-23 — PASS within the fixed local-model synthetic workload.**
The measured status is in [summary.json](evidence/summary.json) and independently checked in
[verification.json](evidence/verification.json).

## Hypothesis and scope

Permitted, verified, relevant historical knowledge can improve later bounded work
without reducing completion on irrelevant or near-match Tasks. Fake cognition cannot
answer whether a model actually uses, ignores or overgeneralizes such knowledge.
III.7 therefore uses the real existing local Qwen deployment and adapter. It does
not generate reflections or consolidate lessons with a model.

This is a deliberately small **synthetic information-ablation experiment**. Matching
Tasks need deployment-specific numeric transformations absent from the Task input.
Those rules are available only through historical memory. The baseline has an
explicit identity fallback, not another source of the missing deployment rule.
That fallback is a decision policy under missing knowledge, not a guarantee of
satisfying the hidden deployment verifier. This design favors informational benefit
on matching cases and limits how far the result can be generalized.
A utility result here demonstrates use of that information through the composed
capability path; it does not establish causal discovery or broad engineering transfer.

The user's III.7 assignment refines the historical III.6 proposal: use real local
cognition, explicitly adapt the promotion schema, and route knowledge through a
common ancestor rather than avoid promotion. III.1–III.6 evidence remains historical
and unchanged. No prior increment is rerun or rewritten.

## Predeclared protocol

[protocol.json](protocol.json), [fixtures.json](fixtures.json) and
[preregistration.json](evidence/preregistration.json) fix the Tasks, model settings,
thresholds, instructions and implementation hashes **before any behavioral model
invocation**. There was no prompt pilot or post-outcome fixture tuning.

- Twelve Tasks: four MATCHING, four IRRELEVANT, four NEAR_MATCH_TRAP.
- Two paired repetitions. First repetition runs no-memory before memory for each
  Task; the second reverses condition order. Mutation runs follow both repetitions.
- At most three model-selected actions per Task. Available action shapes are
  artifact.read(ref=facts), artifact.write(name=answer, content=integer), and COMPLETE.
- The first write commits an immutable answer. A deterministic exact-answer verifier
  evaluates it. Further writes are denied; COMPLETE cannot turn a wrong answer into
  success. Reads return the already available current facts. The bound is a maximum,
  not a requirement to consume all three actions; verified completion stops a run.
- Both conditions use identical Task facts, instructions, affordances, budget,
  verifier and model. Initial packets differ only by the memory context. Later
  observations can differ because the model took different actions.
- Required in **each** repetition: matching completion delta at least +2, zero paired
  losses on irrelevant Tasks, zero paired losses on near-match Tasks. Aggregate
  gains cannot hide an individual regression. Structural/security checks must pass.
- Mandatory failure-as-success control: at least one previously passing Task must
  fail the unchanged verifier under the mutated rendering. Maximum 150 model calls
  across primary and mutation runs. No cloud calls or benchmark expansion.

## Local cognition and execution boundary

Repository evidence supersedes the older Qwen3.5-9B direction: accepted
[D1.C](../../docs/milestones/038-d1-local-inference.md) serves
**nvidia/Qwen3.8-27B-NVFP4**. The live loopback model inventory confirmed that model.
No service, model routing or rollback configuration was changed.

The unchanged [LocalModelCognition](../../runtime/kernel/model.py) uses
`http://127.0.0.1:8000/v1`, provider `local.vllm`, temperature 0, max_tokens 768,
and `chat_template_kwargs.enable_thinking=false`. It validates CognitiveDecision
responses, enforces loopback/no redirects and bounds responses. The experiment
wraps its existing request method only to retain exact request/response evidence;
it does not implement another inference transport or alter its system prompt.

The experiment harness executes only the three synthetic actions. It neither
submits production Tasks nor integrates Restate/Completion Contracts. The retained
[TaskSpec](request.json) is unsubmitted; no runtime Task identity/state is claimed.

## Topology and verified-memory origin

```text
root [public]
├── personal
│   └── project
│       ├── prior
│       ├── match-1 … match-4
│       ├── irrelevant-1 … irrelevant-4
│       └── trap-1 … trap-4
└── employer-x
    └── protected-prior
```

All ContextNodes are generic. Personal and employer-x are separate trusted domains.
Each prior synthetic execution has concrete attempted/expected results, trusted
contract/test/artifact evidence, a fixed outcome envelope and an exact hand-authored
candidate-support pair. The prior verifier compares the attempted result with the
fixture expectation; a worker claim of success is present even for failed work.

The actual composition is:

```text
trusted synthetic outcome/evidence
 → unchanged III.6 OutcomeAdmission
 → private current-context reflection candidate
 → explicit authorized III.7 PromotionGate v2
 → new representation at the immediate parent
 → governed Memory retrieval by later sibling Tasks
```

Four successful numeric experiences, one verified failed attempt, one successful
logging experience, one protected-domain success and one unverified observation
exercise admission and promotion. The relevant formulas contain no later fixture
identifiers or literal answers; prior values differ from later inputs. This uses
explicit fixture support, not arbitrary natural-language entailment.

[composition.json](evidence/composition.json) retains trusted envelopes/evidence
links, admission/promotion receipts, source/destination records, exact visibility
checks and private audits. All later Tasks are denied direct access to prior private
source entries. They inherit only the explicitly promoted project representations.
Protected source and promoted employer knowledge remain inaccessible even though
its topic matches a later personal Task. Human declaration is checked separately
and does not enter the behavioral memory variable.

## Experimental III.5/III.6 compatibility extension

[promotion_v2.py](promotion_v2.py) is an isolated copy with an intentionally tiny
[source patch](evidence/compatibility.patch). It adds VERIFIED_OUTCOME paired only
with VERIFIED_SUCCESS or VERIFIED_FAILURE, and changes the gate version to gate-v2.
The fixture policy explicitly allows these statuses. Existing USER_DECLARATION/
DECLARED and AGENT_OBSERVATION/UNVERIFIED pairs remain unchanged.

An exact-source check proves that no other gate code changed. Authority, permitted
immediate-parent routes, source immutability, separate destination IDs/receipts,
private audit, required scanners and replay-before-receipt revalidation remain the
III.5 implementation. Promotion preserves provenance/status verbatim; it does not
verify an observation or transform failure into success. Invalid candidate metadata
still rejects. The cross-domain controls use new verified provenance to test raw
rejection, approved safe admission, unknown/unavailable scanners and unauthorized
callers. A successful receipt still fails replay after a scanner becomes unavailable.

This resolves the finite prototype compatibility limit explicitly. It is not a
production API decision, and historical III.5/III.6 results are not retroactively
changed.

## Task families, retrieval and semantic qualification

Matching Tasks use folded version-2 inputs for four synthetic protocol families.
Prior verified experiences provide reusable linear transforms. Irrelevant Tasks
require explicit current arithmetic sums; numeric-protocol and logging memories
must be ignored. Traps use version 1, outside the version-2 successful experience.
An identity fallback applies when no applicable successful override is known.

The amber version-1 failure records a tested multiply-by-seven/subtract-four
transformation. Its VERIFIED_FAILURE status means it does not establish a successful
rule. A correct model should retain the fallback. The failure's tested transform is
neither omitted from memory nor rendered as a recommendation in correct packets.

At each decision, the harness queries the existing continuous Memory capability
using the same trusted ExecutionContext. Deterministic topic matching narrows the
already authorized lineage; it cannot select a domain or arbitrary scope. Memory
condition supplies that actual retrieval response as derived, fallible knowledge.
No-memory condition withholds it. Full visible IDs, included entries, exact packets
and model requests are retained. No hidden answer string is manually appended.

The amber packet includes a matching success record, a differently scoped failure
and an unrelated logging record. Other families include the successful family
record plus logging noise. Irrelevant Tasks receive amber memories. The bound is
**2048 compact UTF-8 bytes for the complete retrieval response**; no permitted record
is truncated in this corpus. Prompt envelopes are separately bounded by the adapter.

## Results

**268 composition checks and 842 independent evidence checks PASS.**

Both repetitions produced the same verified completion totals:

| Group (four Tasks per repetition) | No memory | Memory | Delta |
| --- | ---: | ---: | ---: |
| MATCHING | 0/4 | 4/4 | +4 |
| IRRELEVANT | 4/4 | 4/4 | 0 |
| NEAR_MATCH_TRAP | 4/4 | 4/4 | 0 |

There were zero paired irrelevant/trap regressions. The matching delta exceeds the
predeclared +2 threshold in each repetition (+8 pooled, without treating repetitions
as independent new Tasks). Correct failure-qualified memory preserves trap-1's
answer of 13. The mutation commits 87 in both repetitions; the independent mutation
oracle reports two failures and **exits 1**. Correct sources/composition are unchanged.

**78 real local model invocations**: 72 for primary pairs, six for the two mutated
runs. Primary calls were 40 without memory versus 32 with memory. The gain is not
free: matching calls fell from 24 to 8, but irrelevant calls rose from 8 to 10 and
trap calls from 8 to 14 across both repetitions. Three traps perform an extra read.
Irrelevant-2 initially emits fenced JSON in each memory repetition; the unchanged
adapter rejects it, consuming an action, then the model recovers within budget.
No parser repair or extra action allowance was introduced.

No completion or parsed-decision sequence variance was observed between the two
repetitions. That is a small observation, not proof of deterministic model behavior.
Reported usage totals were 188612 input tokens and 7412 output tokens, including
mutation runs. Exact per-call usage is retained; no cloud cost was incurred.

Maximum retrieval response: **1761/2048 bytes**, with no truncation. The independent
literal scan found no private evidence or protected-domain literals in any tested
retrieval, model request or response. Original Task-source records remain inaccessible
to later siblings; only promoted destination records are inherited. All lineage,
provenance, cross-domain scanner/replay and human-declaration checks pass.

The full ContextNode + continuous Memory + SecurityContext + PromotionGate +
VerifiedOutcomeAdmission + downstream retrieval composition survives this experiment
with the explicit experimental gate schema extension. Outcome verification, reflection
content, promotion permission and downstream usefulness remain separate decisions.
No human architectural decision is needed to close III.7.

## Negative control and evidence checking

The isolated FAILURE_AS_SUCCESS rendering changes only the returned copy of the
amber failure: it falsely assigns VERIFIED_SUCCESS and describes the recorded
transform as successful guidance. The source, admitted record and promoted record
remain VERIFIED_FAILURE. The mutation is not an alternate normal operation; both
the schema label and reinforcing text are corrupted, so its behavioral effect does
not identify which individual field mattered most.

The model executes trap-1 again under the same facts, budget, affordances and
verifier. [verify.py](verify.py) independently replays its first committed answer
and exits non-zero for the incorrect result. Correct composition is reconstructed
afterward and compared with its initial retained evidence. No unsafe mutation is
active by default, and no additional model rerun is used to tune a control.

The independent checker imports neither evaluator nor model code. It recomputes
answers and completion counts from raw model decisions, verifies actual response
JSON against retained decisions, compares paired inputs, inspects authoritative
provenance, checks source/private exclusion and scans prompts/retrieval/responses
for protected literals. It does not trust the evaluator's summary PASS label.

## Reproduction and artifacts

Offline evidence verification makes **no model calls**:

```bash
python3 experiments/track-iii-007/verify.py
python3 experiments/track-iii-007/verify.py --mutation-only  # expected exit 1
```

`run.py --execute` is the fixed live protocol. It refuses to overwrite retained
behavior.json. A fresh authorized reproduction needs a separate checkout/evidence
location and the same available local deployment; do not delete accepted evidence
or equate a new stochastic run with byte-level reproduction. All model prompts and
raw responses are retained; deterministic composition/checker reproducibility and
model variance are different claims.

| Artifact | Purpose |
| --- | --- |
| [protocol.json](protocol.json), [fixtures.json](fixtures.json), [gate-fixture.json](gate-fixture.json) | Fixed workload, thresholds, prior outcomes, topology and authority policy. |
| [preregistration.json](evidence/preregistration.json), [model-availability.json](evidence/model-availability.json) | Pre-inference hashes/instructions and live served model identity. |
| [composition.json](evidence/composition.json), [compatibility.patch](evidence/compatibility.patch) | Admission/promotion/isolation checks and exact schema extension. |
| [behavior.json](evidence/behavior.json), [mutation.json](evidence/mutation.json) | Every paired/mutant input, retrieval, raw response, decision and verifier result. |
| [mutation-control.json](evidence/mutation-control.json), [restored.json](evidence/restored.json) | Non-zero control verification and restored correct composition. |
| [summary.json](evidence/summary.json), [verification.json](evidence/verification.json) | Measured outcomes and independently calculated totals, leakage, variance and thresholds. |
| [reproducibility.json](evidence/reproducibility.json), [documentation-checks.json](evidence/documentation-checks.json), [request.json](request.json) | Offline-only reproducibility, repository checks and unsubmitted TaskSpec. |

Privileged synthetic evidence includes private fixtures/audits by design. Ordinary
model packets receive only permitted destination representations, without raw
source evidence or internal provenance IDs. No real proprietary inputs or secrets
were used. Raw evidence hashes provide integrity comparisons, not signatures.

## Limitations and open questions

This finite corpus is intentionally small, with hand-authored paired support and
simple arithmetic; successful use of supplied rules is not discovery of those
rules, causal credit assignment or universal generalization. Irreversible first
writes make an incorrect action consequential within the fixture but do not model
a full coding lifecycle. Two repetitions identify obvious variance, not its rate
or statistical significance. Temperature zero is not a determinism guarantee.

Fixture topic routing is not semantic retrieval quality. No consolidation,
automatic reflection/promotion, utility/voting/decay, durable storage, revocation,
concurrency, authentication or distributed enforcement was added. No production
Cognitive Loop, model routing, Restate, remote execution or Completion Contract
changed; no database, MIRIX, vector store, Graphify or Claude Context was integrated.

Open questions include naturally generated candidate quality, causal/semantic
support, contradictory or stale lessons, retrieval noise at scale, promotion policy
for generalized content, selection overhead, other models/workloads and secure
provider observability. These remain experiments, not production adoption claims.

## Exact proposed III.8 experiment — not started

Hypothesis: adding structural and semantic workspace discovery to lexical discovery
improves broad awareness while keeping model-consumed evidence small and current.

1. Freeze a synthetic repository at two revisions, with known canonical abstractions,
   renamed/moved definitions and one forbidden security-domain subtree. Author 12
   query/oracle pairs before execution: four lexical names, four paraphrases, four
   structural relationships. Repository/git content remains authoritative.
2. Compare rg/native lexical discovery against lexical plus structural/semantic
   discovery through isolated adapters. Inspect existing validated Graphify/code-search
   or embedding paths before selecting a read-only experiment backend; report an
   unavailable required backend as BLOCKED rather than substitute a fake quality claim.
3. Resolve returned references against source hashes and construct at most 2 KiB
   evidence packets. Measure oracle hits, bytes consumed, latency and stale-reference
   rejection for both revisions. Enforce the same lineage/domain/policy boundary
   before discovery and rendering, including derived indexes and diagnostics.
4. Predeclare PASS: at least two extra correct hits among the eight non-lexical queries,
   no losses on exact-name queries, zero forbidden/stale references and every packet
   within budget. Include a stale-index or forbidden-scope mutation; the independent
   checker must reject it. Report overhead and no-benefit cases.
5. Retain fixtures, pins, query/results, source digests and independent checks. Do not
   adopt production dependencies or implement Novelty/Simplicity gates in this test.

**III.8 has not started and requires explicit authorization.**
