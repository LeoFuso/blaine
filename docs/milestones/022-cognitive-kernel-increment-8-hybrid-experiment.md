# Increment 8: runtime suspension and admissible-action experiment

Status: **EXPERIMENT COMPLETE / STOP; Increment 8 remains unpassed.**
Date: 2026-09-20. No final architecture adoption, prompt tuning iteration, or Increment 9.

The blocking-wait hypothesis passed. Hard action projection worked as an interface
constraint. The stronger hypothesis that these changes suffice for completion did
**not** pass: Qwen repeatedly chose a legal artifact rewrite after evidence was ready.

## Bounded design and ownership

Same accepted retention TaskSpec, human-response scope, exact artifact criterion,
model and serving parameters across three isolated Restate deployments. Each arm
had a maximum of six actual inference calls; no retries with adjusted prompts.
A reproduced all four requests from the previous captured failure byte-for-byte.

- A: existing broad semantic vocabulary and reject/retry behavior.
- S: same model messages/provider, plus automatic runtime suspension after the
  admitted blocking human-request effect. Isolates suspension from vocabulary.
- H: S plus hard action projection. Only currently legal action definitions are
  shown. The old procedure paragraph containing the entire action vocabulary is
  omitted; its semantic clarification instructions remain. JSON-only generation
  and the existing strict parser/semantic/runtime validators remain in use.
- Choice control: one additional live Qwen inference on a retained, authoritative
  initial-state snapshot. Direct clarification and same-Task specialist handoff
  are both admitted. This is snapshot replay, **not** a newly running Task.

All live inference: `Qwen/Qwen3.5-9B`, existing local vLLM at
`http://127.0.0.1:8000/v1/chat/completions`. Requested and returned model match in
all 17 captured calls. No embeddings, MIRIX, cloud, or second model participated.
Validation, action eligibility, lowering, effect admission, response verification,
state persistence and completion verification were deterministic application code.

The experiment explicitly treats this scoped human interaction as **blocking**.
It does not infer that every pending request blocks unrelated legal work.
No model-generated WAIT is inserted or substituted. The experimental dispatcher
uses the admitted request identity to persist the existing WAITING state and await
its native Restate promise. The valid response restores RUNNING and the existing
verified-resolution projection feeds later cognition.

## Results

| Arm | Qwen calls | Rejected proposals | Prompt / output tokens | Inference seconds | Wall seconds | Final Task |
|---|---:|---:|---:|---:|---:|---|
| A: current retry | 4 | 3 | 2,766 / 308 | 3.357 | 5.406 | FAILED, duplicate pending requests |
| S: suspension only | 6 | 0 | 4,168 / 172 | 2.034 | 6.215 | FAILED at experimental call cap |
| H: hybrid | 6 | 0 | 2,581 / 172 | 2.049 | 5.936 | FAILED at experimental call cap |

S/H each emitted `REQUEST_HUMAN`, then five `PRODUCE_ARTIFACT` decisions. No
COMPLETE was emitted. Completion evidence was ready, but this is **not Task
completion**: `completion_ref` stayed null. The separate post-run deterministic
verifier says satisfied; it did not transition the Task. Do not interpret the
summary's `completion` field (post-run evaluation) as a committed runtime result.

Each S/H arm invoked human.request once and artifact.write five times with distinct
committed decision/operation IDs. The four additional writes are fresh legal model
choices, not replay duplicates. Exact content-addressed storage retained the same
artifact reference. No duplicate human-request effect occurred in any arm.

The original pending-state retries consumed three calls, 2,073 prompt tokens,
231 output tokens and 2.511 seconds of inference. S/H consumed **zero** inference
in that interval. This is a bounded local saving, not an end-to-end performance win.
S/H wall measurements include invalid-signal checks, a one-second idle observation,
and controlled restarts. Wall minus measured controller pauses was respectively
4.659/4.455 seconds (A: 5.406); startup/replay/cache effects and single samples make
this unsuitable as a latency benchmark. H reduced prompt tokens versus S by 1,587,
but both failed to request completion. Choice control: 619/77 tokens, 0.885 seconds.

## Suspension, wake-up and recovery evidence

Both S and H passed:

1. Request effect and committed decision → persisted WAITING with
   `input/1/retention`, accepted request artifact and scoped human-response type.
2. Seven invalid signals (wrong Task, wrong request, stale revision/digest,
   disallowed answer, unsupported version, malformed payload) returned HTTP 400.
   Task state stayed identical and the call count stayed one.
3. SIGKILL of **both** isolated Restate server and application while pending;
   restart from the same isolated Restate data restored the same wait/decision.
   No call or effect was repeated. The shared inference server was untouched.
4. A valid controlled response resolved the promise once; existing deterministic
   verification retained its artifact and one RUNNING transition followed.
5. After the first artifact, a second application SIGKILL/replacement preserved
   the verified answer and exact artifact in freshly reconstructed cognition.
   A duplicate response outside the consumed wait returned HTTP 409.
6. Offline checks compare all committed model decisions and capability results
   with native journal Run completions, verify all artifact digests, and confirm
   a single GetPromise command. Request-effect-to-verified-resume call count is zero.

The duplicate control is sequential; concurrent competing valid responses were
not tested. No claims about untested transport authentication or general races.
The response alone fails the unchanged completion verifier when the answer artifact
is removed. Original objective/spec artifacts remain identical; no chat history.

## Action projection and retained cognition

After resolution, the **entire sent messages**, including procedure text and JSON
shapes, contain neither REQUEST_HUMAN nor WAIT. PRODUCE_ARTIFACT and COMPLETE remain.
This passed in all five post-response H calls, with zero malformed, inadmissible or
hybrid outputs. No invalid-action retries were needed in S/H. Rejection remains a
necessary safety boundary; a single bounded run does not justify deleting it or
claiming general model reliability.

Crucially, a matching artifact does not make rewriting illegal. Nor is an early
completion request forbidden: the verifier remains authoritative. Suppressing the
rewrite merely to force COMPLETE would select a strategy heuristically, contrary
to this experiment. The evidence exposes a remaining **legal-action progress /
termination selection problem**, not an admissibility failure.

The separate real-choice control offered direct REQUEST_HUMAN and HANDOFF to an
eligible specialist, alongside other legal actions. Both genuine strategies lower
to commands independently admitted by existing PolicyGate. Qwen chose direct
clarification; code did not choose the strategy. The unselected handoff was not
executed, and this does not claim specialist quality or end-to-end handoff success.

## WAIT and native Restate mapping

| Known blocking dependency | Proposed runtime operation | Evidence in this spike |
|---|---|---|
| Human response | Existing WAITING + scoped durable promise + validating shared handler | Live, including server/application restart |
| Timer | Native durable `ctx.sleep`, resume at accepted deadline | Mapping only; not executed |
| Worker result | Await durable service/workflow call, or scoped external completion promise | Mapping only; not executed |
| External event | Scoped durable promise/awakeable, validating resolver | Human event is one instance; no general adapter tested |

WAIT is unnecessary in cognition for the tested blocking human dependency. The
other mechanically known waits also have native runtime primitives; no new
scheduler is suggested. Voluntary deferral despite other legal actions could be a
semantic choice (for example, deliberately waiting for a named publication until a
bounded deadline), but no such contract/capability exists in this fixture and none
was invented. A generic reason-only WAIT has no demonstrated need. This experiment
does not remove WAIT from the existing internal NextAction contract.

Restate 1.7.9 / Python SDK 1.0.5 executed the experiment unchanged. The official
[Python workflow example](https://github.com/restatedev/examples/blob/main/python/basics/app/3_workflows.py)
uses the same durable promise and shared-handler resolution pattern. Native
journals and restarts, rather than analogy to another runtime, establish compatibility.

The versioned [MCP Tasks specification](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks#input-required-status)
models required input as task status; the current [draft Tasks extension](https://tasks.extensions.modelcontextprotocol.io/specification/draft/tasks)
retains that distinction with outstanding input requests/responses. Exact transport
bindings are version-dependent. [A2A's Task lifecycle](https://a2a-protocol.org/dev/topics/life-of-a-task/)
also separates input-required from working. These support a future adapter mapping
Blaine's wait and scoped input to protocol state; they do **not** prescribe our
zero-inference policy or replace Restate, PolicyGate or completion verification.
No protocol integration was attempted.

The experiment-only `SemanticDecisionProvider.decide(context, admissible_actions)`
is provider-neutral. A Jev-like provider could replace Qwen at that boundary while
preserving strict semantic validation and deterministic RuntimeCommand lowering.
No alternative provider's performance or capability has been measured.

## Smallest recommendation and code impact

Consider adopting automatic suspension for **explicitly blocking**, admitted human
requests, retaining typed scoped response verification and existing state/promise
storage. Consider hard action projection as a separate boundary improvement; it
does not by itself solve progress/termination. Neither is adopted by this spike.

If approved, the narrow production changes would be:

- Dispatcher in `runtime/kernel/workflow.py`: enter/resume the existing durable
  human wait after an admitted blocking request, sharing the existing wait logic.
- Semantic bridge/provider: accept a deterministic current action set and render
  only those action definitions; retain strict rejection after generation.
- Focused tests/evidence for blocking semantics, projection and replay.

No changes are needed to RuntimeCommand/TaskSpec/TaskResult schemas, PolicyGate,
HumanDecisionResponse contracts, CompletionContract/verifier, artifact storage,
MIRIX, the context-resolution authority model, workers, serving configuration or
the selected procedures' semantic intent. No scheduler, automatic action repair,
objective mutation, history store or universal action migration is proposed.

Before implementation, the human must decide whether to adopt only the proven
blocking-wait boundary and authorize a **separate bounded decision** on legal-action
progress/termination. Do not silently make COMPLETE automatic or artifact rewrites
illegal. No additional experiment is authorized by this report.

## Retained evidence and reproducibility

- [Comparison and measurements](../../experiments/kernel-increment-8/evidence/hybrid/comparison.json)
- [Offline journal/provenance assertions](../../experiments/kernel-increment-8/evidence/hybrid/checks.json)
- [Hybrid per-turn joined evidence](../../experiments/kernel-increment-8/evidence/hybrid/hybrid/turn-evidence.json)
- [Hybrid suspension interval](../../experiments/kernel-increment-8/evidence/hybrid/hybrid/suspension-interval.json)
- [Genuine alternatives and actual model choice](../../experiments/kernel-increment-8/evidence/hybrid/choice/input.json), [result](../../experiments/kernel-increment-8/evidence/hybrid/choice/result.json)
- [Source integrity](../../experiments/kernel-increment-8/evidence/hybrid/source-integrity.json): every existing runtime/kernel Python file unchanged.
- [Experiment-only workflow diff](../../experiments/kernel-increment-8/hybrid/workflow.diff),
  [harness](../../experiments/kernel-increment-8/hybrid/run.py), [projection](../../experiments/kernel-increment-8/hybrid/actions.py).

65 existing tests and seven isolated projection tests passed. Original validators'
negative controls are retained. Run files contain exact local invocation paths;
`hybrid/run.py --mode retry|suspend|hybrid --output <fresh-dir> --restate-server <pinned-binary>`
reproduces an arm using the existing shared Qwen endpoint. Model runs are not an
open-ended benchmark; rerunning them requires a new bounded authorization. The
analysis script can recheck retained evidence without new inference.

STOP: experiments are complete; full Increment 8 acceptance is still not achieved.
