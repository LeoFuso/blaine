# Track III.7 — Learned memory utility PASS

Checkpoint: 2026-09-23. **PASS within the fixed synthetic local-model workload.**

Hypothesis: verified, scoped historical knowledge improves later bounded work
without reducing completion on irrelevant or near-match Tasks. The
[experiment](../../experiments/track-iii-007/README.md) specifies the predeclared
workload, composition, model configuration, limits and exact reproduction boundary.

## Behavioral evidence

The protocol was frozen before model calls: 12 Tasks, two paired repetitions,
three-action maximum, 2 KiB retrieval, matching delta at least +2 per repetition,
and zero paired irrelevant/trap regressions. No fixture/prompt tuning followed
model outcomes. Both repetitions returned:

| Group | No memory | Memory | Difference |
| --- | ---: | ---: | ---: |
| MATCHING | 0/4 | 4/4 | +4 |
| IRRELEVANT | 4/4 | 4/4 | 0 |
| NEAR_MATCH_TRAP | 4/4 | 4/4 | 0 |

The actual accepted local deployment, **nvidia/Qwen3.8-27B-NVFP4**, was confirmed at
`http://127.0.0.1:8000/v1` and invoked through the unchanged LocalModelCognition
adapter. Temperature 0, max_tokens 768, thinking disabled; no cloud inference or
model/service/routing changes. **78 model invocations**: 72 paired, six mutated.
Fake cognition was not used to claim utility.

A deterministic verifier, not model claims, checks the first committed numeric
answer. Two actions remain available alongside commit: read facts and request
completion. All actions, including invalid responses, consume the same budget.
The first write is immutable; wrong commitments cannot be repaired with more tries.

No completion or parsed-decision variance appeared between repetitions. Memory
reduced matching calls but increased irrelevant/trap overhead. Irrelevant-2 emitted
fenced JSON once in each memory repetition; the existing adapter rejected it and
recovery stayed within budget. Three trap Tasks used an extra read. These costs
remain visible despite zero completion regressions.

## Composition and negative controls

**268 composition checks; 842 independent evidence checks PASS.**

- Actual III.6 outcome admission creates private learned candidates from trusted
  synthetic contract/test/artifact evidence. Explicit promotion creates new ancestor
  representations. Later siblings cannot read source entries directly.
- An isolated gate-v2 schema extension admits VERIFIED_OUTCOME paired with
  VERIFIED_SUCCESS or VERIFIED_FAILURE; the exact source patch also updates version
  labels and changes no other gate logic. UNVERIFIED stays unverified. Source
  provenance/status remain immutable. This is experimental compatibility, not a
  production API decision or a rewrite of III.5/III.6 history.
- The inherited failure is presented as VERIFIED_FAILURE, not recommended guidance.
  The isolated rendering mutation falsifies both status and reinforcing text. Real
  Qwen then commits **87 instead of 13** for trap-1 in both repeats. The independent
  unchanged verifier records two regressions and **exits 1**. Correct composition
  afterward is identical; no unsafe rendering is active by default.
- All later Tasks inherit only permitted promoted records. Semantically matching
  employer-x knowledge remains hidden. Cross-boundary raw content rejects, approved
  safe content admits, scanner unknown/unavailable fails closed and replay rechecks
  current scanners. Human declarations retain their separate trusted path.
- Maximum response **1761/2048 bytes**, no truncation. One packet contains three
  records with different applicability. Literal scans of retrievals, prompts and
  model responses find no private source evidence or protected-domain content.

Evidence: [protocol](../../experiments/track-iii-007/protocol.json),
[preregistration](../../experiments/track-iii-007/evidence/preregistration.json),
[composition](../../experiments/track-iii-007/evidence/composition.json),
[compatibility patch](../../experiments/track-iii-007/evidence/compatibility.patch),
[raw paired decisions](../../experiments/track-iii-007/evidence/behavior.json),
[mutation](../../experiments/track-iii-007/evidence/mutation-control.json),
[summary](../../experiments/track-iii-007/evidence/summary.json),
[independent verification](../../experiments/track-iii-007/evidence/verification.json).

## Decision and limits

**The full conceptual ContextNode + Memory + SecurityContext + PromotionGate +
VerifiedOutcomeAdmission + downstream retrieval composition survives**, with the
explicit experimental promotion schema extension. Verification determines whether
an experience may teach; reflection determines what it might teach. This experiment
uses hand-authored candidates and tests later use, not automatic reflection.

The matching Tasks deliberately omit deployment-specific formulas from their
current inputs. The result demonstrates a model using historical information
through governed retrieval. It does not establish arbitrary semantic entailment,
causal discovery, universal engineering improvement, optimal retrieval/consolidation
or production readiness. Two repetitions do not quantify stochastic variance.

III.1–III.6 sources/history and all production runtime contracts remain unchanged.
No LLM reflection, consolidation, automatic promotion, persistence, embedding/index,
MIRIX, Graphify, Claude Context, Restate or remote-execution integration was added.
The [TaskSpec](../../experiments/track-iii-007/request.json) is unsubmitted; this is
experiment acceptance, not a runtime Task completion state.

Unresolved: generated reflection quality, stale/conflicting memories, larger/noisier
retrieval sets, causal support, generalization to other models/workloads, model-format
overhead, production schema evolution and secure provider observability.
No human architectural decision is required to close III.7.

Next: [exact III.8 proposal](../../experiments/track-iii-007/README.md#exact-proposed-iii8-experiment--not-started):
12 pinned workspace queries across lexical, semantic and structural needs; compare
lexical-only discovery with combined discovery, two repository revisions, 2 KiB
packets, source-hash freshness and forbidden-domain controls. Require at least two
additional non-lexical oracle hits, no exact-query losses and no stale/forbidden
references, with a caught mutation. **III.8 has not started and requires explicit
authorization.**
