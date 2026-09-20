# Increment 8 — adopted verifier-driven progression

**PASSED.** The approved architecture is implemented in the existing production
Restate workflow. No alternate experimental dispatcher remains executable.

## Adopted invariant

Cognition proposes semantic work. Runtime determines whether cognition is needed.
After authoritative evidence changes, the unchanged CompletionVerifier runs first:
satisfied → COMPLETED; otherwise an explicit blocking dependency → durable wait;
otherwise derive hard-admissible alternatives → cognition → strict validation →
lowering → PolicyGate → effect/persistence → progression again.

Admissibility determines legality, never strategy. Accepted policy can exclude a
capability; a pending/resolved scoped question excludes a duplicate request. A legal
artifact rewrite is not masked as a quality heuristic. Known HumanDecision waits
are runtime-owned. The same input-wait helper handles automatic blocking and legacy
explicit waits; it uses native Restate promises and the existing response verifier.

COMPLETE and WAIT remain representable for compatibility. COMPLETE cannot authorize
completion and is no longer required to reach it. Known human blocking never invokes
cognition to obtain WAIT. General vocabulary removal and voluntary deferral remain
follow-up architectural debt, not changes made here.

## Implementation and scope

- `runtime/kernel/workflow.py`: verifier-first progression after accepted state and
  effects/outcomes; durable blocking after an admitted scoped human request; one
  shared input wait/resume path; verification precedes the next cognitive turn.
- `runtime/kernel/semantic_provider.py`: provider-neutral
  `decide(context, admissible_actions)`; only current action schemas/descriptions
  are emitted. No constrained decoding, repair, coercion, or fallback.
- `runtime/kernel/semantic_bridge.py`: hard policy/request-state projection and
  strict proposal admission; protocol-owned identity stays in deterministic lowering.
- The selected clarification excerpt is action-neutral: vocabulary is generated
  from the current action contract rather than repeated as static procedure prose.
- Production gate: `scripts/verify-kernel-procedure.py`, backed by instrumentation
  in `experiments/kernel-increment-8/acceptance*.py`. Probe instrumentation is not
  an alternate lifecycle implementation.

Completion criteria/verifier, PolicyGate, strict runtime contracts, HumanDecision
verification, artifact authority, context-resolution semantics, Increment 3 adapter,
MIRIX and worker adapters are unchanged. Source hashes and pre-change snapshots
are retained. Existing experimental workflow sources were archived as non-executable
text and their launchers explicitly retired. Historical evidence remains intact.

Deploy this changed durable code as a new Restate deployment. Do not replay older
in-flight deployment histories against the changed journal sequence. This session
ran new isolated probe Tasks, not a migration of live existing invocations.

## Live acceptance

Existing shared local vLLM, requested/returned `Qwen/Qwen3.5-9B`,
`http://127.0.0.1:8000/v1/chat/completions`; Restate 1.7.9 / SDK 1.0.5.
Original objective, accepted human request and completion criteria retained.
The complete first-two model requests match the earlier hybrid experiment exactly.

Observed: REQUEST_HUMAN → admitted/executed once → persisted WAITING → seven invalid
responses rejected without state change → application and Restate SIGKILL/restart
preserve the pending wait → matching verified response → fresh reconstructed
resolution → PRODUCE_ARTIFACT → exact effect persisted → application SIGKILL before
verification → recovery verifies → COMPLETED with committed CompletionEvaluation
and bounded TaskResult.

- 2 real Qwen calls; 961 input / 96 output tokens; 1.090314936 seconds total provider
  request duration (single-run observation, not a benchmark).
- 2 capability effects; 0 invalid semantic proposals; 0 extra rewrites.
- 0 cognition during pending input and 0 cognition/effects after evidence first
  satisfies completion, including across restart.
- Wrong-task, wrong-request, stale revision/digest, invalid answer, unsupported
  version and malformed responses rejected. Duplicate response rejected after
  consumption. Concurrent competing responses are not claimed as newly tested.
- All committed decisions, capability results and verifier evaluations match native
  journal results; exact artifact digests and attached TaskResult checked offline.

Separate native Restate negative Task: a **scripted** provider writes DRAFT; the effect
succeeds but verification fails; unblocked cognition continues and writes the correct
artifact; verification then completes it. Two scripted turns, two effects, no LLM
calls. Synthetic decisions are not counted as real inference.

## Regressions rerun

72 focused tests passed, including the 65 pre-migration tests with the approved
semantic-provider ABI/wait expectations updated, four production progression tests
and three action-projection controls. Existing human negative controls remain intact.

| Earlier boundary | Rerun coverage | Live external rerun |
|---|---|---|
| Increment 3 cognition | Strict JSON/envelope parsing, raw INVOKE preservation, malformed/unknown/stale/tool-call rejection, local endpoint/bounds, action vocabulary | New Qwen clarification gate; original runtime-command adapter unchanged, its six-case live probe not repeated |
| Increment 4 MIRIX/context | Bounded/provenanced recall, empty recall, retrieval errors, forbidden authority/cloud, resolution projection | MIRIX/BGE not called; deterministic coverage and unchanged provider sufficient for this dispatcher change |
| Increment 5 HumanDecision | YES/NO and general allowed sets, all scope/version/staleness checks, forged artifact rejection | New scoped clarification, invalid signals, durable wait/restart, duplicate rejection |
| Increment 6 YouTrack | Fake-transport scoped read, denial before transport, no Card authority | No credential/connector work or live YouTrack calls |
| Increment 7 worker | Bounded worker packet, admission, worker-success ≠ completion | No Goose rerun; unchanged worker/harness covered deterministically |

The genuine-choice snapshot from the prior experiment is retained by digest. It
admitted direct clarification and specialist handoff, and Qwen selected clarification.
No extra choice inference or new worker claim was made.

## Evidence and next gate

- [Summary](../../experiments/kernel-increment-8/evidence/production/summary.json)
- [Transition evidence](../../experiments/kernel-increment-8/evidence/production/acceptance/transition-evidence.json)
- [Per-turn wire/semantic/lowering/policy/effects](../../experiments/kernel-increment-8/evidence/production/acceptance/turn-evidence.json)
- [Offline journal/recovery assertions](../../experiments/kernel-increment-8/evidence/production/checks.json)
- [Focused tests](../../experiments/kernel-increment-8/evidence/production/focused-tests.txt)
- [Source integrity](../../experiments/kernel-increment-8/evidence/production/source-integrity.json)
- [Retired dispatcher sources](../../experiments/kernel-increment-8/evidence/production/retired-experimental-sources/manifest.json)

No unrelated installation, serving, secrets or host changes. No unresolved deviation
from the authorized Increment 8 progression model. Conditional progression now permits
Increment 9 only: bounded optional derived Project Knowledge with source authority,
provenance/freshness and one stale-knowledge counterexample. Existing Graphify
conclusions are inputs; no new upstream audit or SCIP integration is warranted.
