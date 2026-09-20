# Increment 8: verifier-driven progression experiment

**EXPERIMENT PASS / STOP for architecture approval.** Production Increment 8 remains
FAILED / unpassed: no production migration or Increment 9 was performed.
Date: 2026-09-20.

The original clarification scenario completed with two real Qwen calls and two
capability effects. No cognition or rewrite occurred after completion became
independently provable. A separate incomplete-effect control correctly returned
to cognition. This supports verifier-driven completion for the existing bounded,
independently decidable CompletionContract; it is not a universal completion claim.

## Controlled change

Only the experiment dispatcher/probe changed. The previous hybrid files and every
`runtime/kernel/*.py` file remain byte-identical. The accepted TaskSpec, first two
complete model requests/messages, model parameters, human contracts, context
projection, action vocabulary, lowering, PolicyGate and verifier match the prior
hybrid arm exactly. **No prompt tuning or action masking adjustment.** COMPLETE
remained available in unchanged guidance to isolate progression order; Qwen did
not emit it. No production action was removed or migrated.

The experiment calls the existing `runtime.kernel.execution.evaluate` after
acceptance and persisted evidence/outcome transitions, before further cognition
or blocking suspension. It retains the CompletionEvaluation artifact and reference.
Only `satisfied` authorizes COMPLETED. `unsatisfied` and `unknown` do not. The effect's
success flag is never a substitute for verification. These are native Restate
journaled steps and Task state writes, not a second orchestration system.

## Observed combined progression

| Event | Independent evaluation / lifecycle | Qwen calls so far |
|---|---|---:|
| Task accepted, criteria missing | unsatisfied / RUNNING | 0 |
| Qwen proposes REQUEST_HUMAN; strict lowering and PolicyGate admit it | request effect persisted; unsatisfied | 1 |
| Scoped human request blocks work | WAITING on `input/1/retention` | 1 |
| Seven invalid/stale/malformed signals | HTTP 400; wait unchanged | 1 |
| Isolated application and Restate server SIGKILL/restart | same durable wait; no re-decision/effect | 1 |
| Valid response is scoped, verified and persisted | RUNNING; still unsatisfied without artifact | 1 |
| Reconstructed context supplies verified resolution; Qwen proposes artifact | exact artifact persisted; contract now independently satisfied | 2 |
| Application SIGKILL before progression verification; fresh process resumes | journal replays committed effect; existing verifier returns satisfied | 2 |
| Runtime stores verification and completes Task/TaskResult | COMPLETED, independently satisfied | 2 |

Zero model calls occurred while the request was pending. Zero model calls, cognitive
adapter invocations, or additional capability effects occurred after the first
persisted state that independently satisfies completion. The first provable state's
lifecycle was still RUNNING; recovery, rather than another model decision, performed
verification and completion. Its exact artifact and response references remain valid.
A duplicate response after consumption returned HTTP 409 and did not progress twice.

Every committed model decision, capability result, and progression evaluation was
compared offline with native Restate journal Run results and exact artifact bytes.
The completion reference is now actually committed and the attached TaskResult says
COMPLETED. This differs from the previous post-run-only verification of FAILED Tasks.

## Negative and semantic-choice controls

A separate durable Task, `incomplete-effect`, used an explicitly **scripted** provider
with the same experimental dispatcher, real artifact effects and original verifier:

`artifact.write(DRAFT)` → effect succeeds → exact digest verification unsatisfied
→ RUNNING with no dependency → second cognitive turn observes that successful
but insufficient effect → `artifact.write(VERIFIED_RESULT)` → verification satisfied
→ COMPLETED without a COMPLETE proposal.

Two scripted turns and two real capability effects; **zero LLM calls**. No synthetic
response is counted as Qwen evidence. This proves successful effects alone do not
terminate execution. Four offline controls also pass: exact artifact needs no
COMPLETE proposal; success without evidence does not complete; wrong artifact
continues; an early model COMPLETE cannot bypass verification. All 65 existing
focused tests pass. These tests use a fake context and are labeled separately from
native Restate evidence.

The previous genuine-choice experiment is retained by path and digest, without
re-running inference: both direct clarification and specialist HANDOFF were admitted
and Qwen chose clarification. The new initial verifier returns unsatisfied, and the
same hybrid choices reach cognition. No deterministic strategy selector was added.
The retained control proves legal alternatives and actual model selection, not the
quality or execution of the unselected strategy.

## Exact comparison

Effects below are capability invocations, excluding journal/artifact bookkeeping.
Repeated legal proposals count additional writes after the first correct artifact.

| Arm | Qwen calls | Invalid | Repeated legal writes | Input / output tokens | Inference request seconds | Effects | Task outcome |
|---|---:|---:|---:|---:|---:|---:|---|
| Prior current retry | 4 | 3 | 0 | 2,766 / 308 | 3.357144522 | 1 | FAILED |
| Prior suspension only | 6 | 0 | 4 | 4,168 / 172 | 2.034261177 | 6 | FAILED at experimental cap |
| Prior hybrid | 6 | 0 | 4 | 2,581 / 172 | 2.049474124 | 6 | FAILED at experimental cap |
| Verifier-driven hybrid | 2 | 0 | 0 | 961 / 96 | 1.074511617 | 2 | COMPLETED |

The new negative Task is separate: 0 Qwen calls, 2 scripted turns, 2 effects.
The previously captured one-call choice control adds no new inference. These are
single runs; request timings include HTTP/provider overhead and are not a benchmark.
Correctness, byte-identical first-two requests and journal results support the finding.

Inference provenance: requested **and returned** `Qwen/Qwen3.5-9B`, existing local
vLLM at `http://127.0.0.1:8000/v1/chat/completions`, JSON-only output, unchanged strict
application validation. Qwen chooses semantic intent. Blaine constructs protocol
identity, validates, authorizes, executes, persists and verifies. No embedding,
MIRIX, cloud, alternative model, worker or infrastructure configuration participates.

## COMPLETE, WAIT and provider neutrality

For this independently decidable contract, model-facing COMPLETE is unnecessary:
all required evidence exists after admitted effects and the verifier can decide
without another model call. The unchanged vocabulary still included COMPLETE; this
experiment proves independence from its **emission**, not reliability of a newly
reduced vocabulary. Whether to remove that presentation is an architecture decision.

Some Tasks need a candidate before verification is possible: a proposed patch,
selected result artifact, or proof certificate may need to be explicitly submitted.
That is semantic work producing a candidate/result, not permission to set COMPLETED.
Verification still decides. For subjective, incomplete, externally changing or
ongoing objectives, a snapshot of available evidence may not establish all obligations.
The accepted contract must express required approval, closure or temporal conditions;
otherwise completion remains unknown. No verifier, contract or action for these
broader cases was invented here.

Model-facing WAIT is likewise unnecessary for this known blocking human dependency.
Its event identity and wake-up validation belong to the runtime. Timer/worker/other
external waits were not newly exercised; voluntary deferral remains a distinct,
untested semantic intent requiring a real condition rather than a generic WAIT.

The provider remains `decide(context, admissible_actions) -> SemanticDecision`.
A future Jev-like provider could supply intent without implementing wait/completion
mechanics or RuntimeCommand envelopes. It was not integrated or evaluated. The
current unchanged prompt's COMPLETE description is not a required provider operation
in the successful trace.

## Restate and smallest proposed production change

Pinned server 1.7.9 / Python SDK 1.0.5 execute the ordering directly:

`persist exact evidence/state → durable verifier step → complete, or existing
blocking promise, or next bounded cognitive step`.

Single-Task state ownership, durable run results and existing promise resolution
suffice. Restart after sufficient evidence and before verification required no new
scheduler, model session, retry protocol or source of authority.

If explicitly adopted, the smallest production change is a dispatcher progression
check using the existing verifier and completion-reference storage after authoritative
outcomes and before cognition, alongside the already-tested blocking-human suspension.
Both remain experiment-only. Keep model result proposals distinct from lifecycle
completion; do not silently migrate the entire action vocabulary.

No changes are required for this case to TaskSpec/TaskState/TaskResult or human-response
schemas, accepted CompletionContract criteria, PolicyGate, strict RuntimeCommand
validation, artifact authority, resolution projection, MIRIX, workers or inference
serving. Production adoption would amend **when** the unchanged verifier controls the
lifecycle; it requires human architectural approval rather than being treated as a
routine prompt fix.

## Evidence and next decision

- [Experiment summary](../../experiments/kernel-increment-8/evidence/progression/summary.json)
- [Exact comparison](../../experiments/kernel-increment-8/evidence/progression/comparison.json)
- [Per-turn wire/semantic/policy/effect evidence](../../experiments/kernel-increment-8/evidence/progression/acceptance/turn-evidence.json)
- [Every retained transition and independent evaluation](../../experiments/kernel-increment-8/evidence/progression/acceptance/transition-evidence.json)
- [Journal assertions and first provable states](../../experiments/kernel-increment-8/evidence/progression/checks.json)
- [Incomplete-effect control](../../experiments/kernel-increment-8/evidence/progression/acceptance/negative-control.json)
- [Retained real-choice evidence references](../../experiments/kernel-increment-8/evidence/progression/retained-choice-control.json)
- [Unchanged production and previous experiment](../../experiments/kernel-increment-8/evidence/progression/source-integrity.json)
- [Isolated dispatcher diff](../../experiments/kernel-increment-8/progression/workflow.diff)

Live command: existing runtime-venv Python runs `progression/run.py --mode hybrid
--output /tmp/blaine-verifier-progression-20260920 --restate-server
/home/leofuso/workspace/blaine/.local/bin/restate-server`. Logs, requests, responses,
journals and exact artifacts are retained in `evidence/progression/acceptance/`.
`progression/analyze.py` rechecks retained evidence without inference.

**STOP.** Human decision: whether to adopt verifier-first completion and explicit
blocking suspension as Cognitive Kernel lifecycle rules, with a separately approved
production implementation. No production migration or further increment follows
this experimental PASS automatically.
