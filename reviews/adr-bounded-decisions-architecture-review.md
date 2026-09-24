# Architecture Review: ADR "Prefer Bounded Decisions Before Generative Cognition"

**Reviewer:** Claude Code
**Review Date:** 2026-09-24
**Repository:** blaine
**Branch:** main
**Commit:** 56f2e65cdf1bb470aa179168e3a628b29f422092 (Merge chore/local-verification-scheduler-v0: Local Verification Scheduler v0)
**Scope:** Read-only architectural assessment of a *Proposed* ADR against current `main`. No implementation, ADR file or roadmap change is made or implied by this review.

---

## 1. Executive conclusion

```text
Assessed origin/main:    56f2e65cdf1bb470aa179168e3a628b29f422092 (unchanged through the review)
ADR recommendation:      ADOPT_WITH_REVISIONS
Implementation timing:   AFTER_<E3 real-Task Cognitive Loop evidence, then the hard-admissible
                         action projection extended to the deployed cognition adapter>
Biggest confirming finding: Increment 8 already adopted "runtime derives hard-admissible actions →
                         cognition → strict validation → deterministic lowering → PolicyGate", with a
                         provider-neutral selector interface decide(context, admissible_actions).
Biggest contradiction:   The ADR hands retry, fail, escalate, wait, complete and worker/model choice
                         to a selector. Blaine deliberately made those deterministic or trusted.
Biggest architectural risk: A second decision/candidate/"routing" framework beside CognitiveDecision,
                         PolicyGate and Policy C, bringing in Jev's vendor term "System-1" and a
                         remote provider on every turn.
```

Most of the principle is already true on main. The one new idea worth keeping: where the runtime can fully construct an action, the model should select it rather than regenerate it. The ADR's experiment and model roster are premature.

## 2. Current architecture: the real loop on main

```text
TaskRequest envelope (TaskSpec + grant + contract + optional initial_action)
   │  personal_agent.py / ACP binding
   ▼
ACCEPT                       workflow.run  (Restate workflow "CognitiveTaskV1")
  effective caps = spec ∩ grant             routing.effective_capabilities
  pinned authority, profiles, ask_before    journal.compile_authority
  Completion Contract rev 0                 completion.accept_contract
   ▼
settle('accepted')  ── deterministic legality ─► may be COMPLETED with zero cognition
   ▼
for iteration in 1..16 (MAX_TURNS):
  admit_amendments      (human-only, compare-and-set by revision)       workflow + completion
  reconcile_effects     (uncertain target effects)                      effects
  escalation_condition → admit_escalation   (deterministic + trusted)   routing  [Policy C]
  reconstruct CognitiveTurn packet (retained artifact)                  context.reconstruct
  DECISION = initial_action (iteration 1, deterministic)
           | cognitive adapter in journaled step "cognitive/{i}"       model.LocalModelCognition (Qwen)
             (or escalation_cognitive if admitted)
  policy_gate(decision, state, spec, grant, contract, authority)        execution.policy_gate
     deny  → PolicyDecision observation → next turn
     allow → INVOKE_CAPABILITY: journal "admitted" → [lower → ask_before approval → dispatch
                                  → receipt/poll/cancel → reconcile]  or Capabilities.execute
             HANDOFF | SPAWN_TASK (child workflows, ALL_TERMINAL) | WAIT | COMPLETE (= settle request)
  observation retained; revision += 1
  settle('outcome') ── COMPLETED iff completion.legality() is legal
  admitted human.request → automatic WAITING on a one-shot promise (no model WAIT)
end: turn limit → FAILED; TerminalError → FAILED/CANCELLED + close_effects
     TaskResult + RoutingRecord retained; ExecutionEvents emitted (forensic, non-authoritative)
```

Mapped onto the ADR's stages:

| Stage | Blaine equivalent | Owner |
|---|---|---|
| Task | TaskRequest envelope → TaskState | Restate workflow `run` (single writer) |
| "Deterministic rules" | `settle()`/legality first, known waits, deterministic `initial_action`, Policy C conditions | `workflow.py`, `completion.py`, `routing.py` |
| Cognition / decision | `CognitiveAdapter(packet) -> CognitiveDecision` | Deployment-injected adapter (Qwen) |
| Authority | `policy_gate` + pinned authority + `admit_exec` + ask_before human approval | `execution.py`, `effects.py`, human |
| Execution | `Capabilities.execute` / target effects | `execution.py`, `effects.py` |
| Evidence | capability journal, receipts, observations, content-addressed artifacts | `journal.py`, `ArtifactStore` |
| Verification | `evaluate_contract` + `legality` (deterministic; `semantic_review` bounded) | `completion.py`, `review.py` |
| Task transition | only `settle()` sets COMPLETED; runtime sets FAILED/CANCELLED | `workflow.py` |

Two facts matter for this ADR:

- **The verifier runs before cognition.** Cognition is invoked only when evidence is insufficient and nothing is known to block.
- **The deployed runtime uses Qwen for full decisions.** `personal_runtime.py` wires either `no_unnecessary_cognition` (raises) or `LocalModelCognition` (`nvidia/Qwen3.8-27B-NVFP4` per `infra/services/runtime.json`). Qwen emits a whole `CognitiveDecision`, arguments included. The bounded `SemanticDecisionBridge` is wired only in the Increment 8 acceptance app.

## 3. Decision inventory

| Decision | Current owner | Current mechanism | Proposed category | Why | Repository evidence |
|---|---|---|---|---|---|
| Is cognition needed now? (complete / wait / think) | workflow `settle`, `await_input` | Verifier-first legality; automatic WAITING after an admitted human request | DETERMINISTIC | Already runtime-owned by design (Increment 8) | `workflow.py:307-358, 829-833`; `tests/test_kernel_progression.py` |
| First action of intake Tasks | Personal Agent intake + `initial_action` | Fixed action, no model | DETERMINISTIC | D2 runs whole Tasks with zero model calls | `workflow.py:671-676`; `personal_agent.py:small_request`; `personal_runtime.py:no_unnecessary_cognition` |
| Next action *type* and capability *name* | Qwen `LocalModelCognition` | Generated JSON; static schema is "guidance only"; validators decide | BOUNDED_SEMANTIC_CANDIDATE | The legal set is computable from state (allowed caps, `SPECIALISTS`, child budget, contract human bindings) | `model.py:18-48`; `contracts.py:12-17, 351-383`; `context.py:131` |
| Human request payload | Completion Contract (fixed); Qwen must reproduce it byte-exactly | `policy_gate` exact equality | DETERMINISTIC payload; *whether to ask now* is BOUNDED | The model regenerates what the runtime already has — the ADR's anti-pattern, present today | `execution.py:60-65`; `semantic_bridge.py:77-100` |
| Enumerable arguments (`artifact.read` ref, `worker.run` packet_ref, `workspace.exec` profile/args, HANDOFF target) | Qwen generates; gate checks membership | Membership checks against state/authority | BOUNDED_SEMANTIC_CANDIDATE | Domain is a finite admitted set | `execution.py:56-59, 69-75, 96-112, 127-128`; `effects.py:172-179` |
| Generative arguments (`artifact.write` content, child TaskSpec, `context.request` question, `workspace.write` path, `youtrack` issue id) | Qwen | Generated, then shape/limit validation | GENERATIVE | Not enumerable by the runtime | `execution.py:50-55, 76-83`; `contracts.py:247-255` |
| Semantic next step among legal actions (rewrite vs. finish, which capability) | Qwen | Generative choice | BOUNDED_SEMANTIC_CANDIDATE | Increment 8 showed this is the hard "legal-action progress/termination selection" problem | `docs/milestones/022-…hybrid-experiment.md` ("Results", "Action projection") |
| WAIT on known dependency | Runtime | Automatic durable suspension; model WAIT kept for compatibility | DETERMINISTIC | Roadmap "Waiting" boundary | roadmap `001…:58`; `workflow.py:205-255` |
| Completion | `completion.legality` | Single deterministic function; COMPLETE is only a request | DETERMINISTIC | ADR 0026 | `completion.py:511-570`; `test_model_complete_still_cannot_bypass_verifier` |
| Semantic criterion satisfied? | `semantic_review` reviewer | Verdict enum + high/low confidence; low → `unknown`/`request_human`; cannot override deterministic verdicts | BOUNDED_SEMANTIC (already adopted) | An existing precedent for bounded decisions with abstention | `review.py:20-37, 93-120`; `completion.py:136, 247-253` |
| Admissibility | `policy_gate` | Code | DETERMINISTIC | — | `execution.py:16-148` |
| Effect approval | Human (`ask_before`) | HumanDecisionRequest on the concrete effect | HUMAN_GOVERNED | — | `workflow.py:485-509`; `effects.py:443` |
| Contract amendment / waiver | Human via `amend_contract` | Compare-and-set, actor from the binding | HUMAN_GOVERNED | Cognition cannot weaken REQUIRED criteria | `workflow.py:1034-1103`; `completion.py:709-840` |
| Escalation to a stronger model | `escalation_condition` + `admit_escalation` | Turn budget / repeated verifier rejection; grant ∩ deployment | DETERMINISTIC (by explicit design) | "No model is asked whether it feels stuck" | `routing.py:8-11, 117-142`; `workflow.py:601-617` |
| Model/binding selection | Deployment config | Static; `REBIND_MODEL` UNSUPPORTED | DETERMINISTIC (trusted config) | ADR 0024: a model may never choose a provider | `adapter_profiles.py:37-38`; ADR 0024 "Escalation is a recommendation" |
| Worker suitability | `worker_routing.select` (library; **not in the Task path**) | Scripted classifier + deterministic min + hard gate; Jev in shadow | BOUNDED_SEMANTIC_CANDIDATE (C3) | The only seam where Jev already plugs in | `worker_routing.py:1-5, 56-80`; `tests/test_jev_provider.py:186-204` |
| Frontier dispatch authorization | `frontier.authorize` | Code | DETERMINISTIC | — | `frontier.py:199` |
| Technical retry | Restate | `run_typed(max_attempts=3)` | DETERMINISTIC | Checkpoint: retry is a runtime policy, not a model action | `workflow.py:79-80`; checkpoint §2 |
| Semantic retry after a failed effect or verifier | Qwen next turn | Observation fed back | GENERATIVE / MIXED | — | `context.py:73-74, 130` |
| Terminal failure | Runtime | Turn limit, irrecoverable invariants, TerminalError; **no FAIL action exists** | DETERMINISTIC | — | `workflow.py:353-357, 936-948`; `contracts.py:80` |
| Invalid / stale decision | Adapter + gate | Strict parse; `task_revision`/`turn_id` binding; exception → step retries → FAILED | DETERMINISTIC | — | `model.py:150-171`; `execution.py:38-43`; `test_kernel.py:51` |
| Uncertain effect | `reconcile_effects`; gate blocks new effects | Code | DETERMINISTIC | — | `workflow.py:554-578`; `execution.py:100-103` |
| Continuation supervision | `BoundaryObserver` | PROCEED/ABSTAIN, no intervention admitted | BOUNDED (observation-only) | — | `instrument.py:355-378`; `worker-execution-boundary.md` "Control path" |
| Personal Agent triage (direct vs. Task, strategy) | Personal Agent (prose procedure) | Not implemented in code; ADR 0005 Unvalidated | MIXED_OR_UNCLEAR | Strategy labels look enumerable, but no code seam exists | ADR 0005; no triage code under `runtime/` |
| Verification suite / exec command choice | Scheduler / reviewed profiles | Caller names a known ID; the host resolves the commands | DETERMINISTIC resolution of a BOUNDED choice | This is already the "candidate_id" pattern | `verification/scheduler.py` docstring; `effects.py:70-71, 214-218` |

## 4. ADR fit matrix

| ADR assertion | Classification | Evidence |
|---|---|---|
| Deterministic logic before model invocation | **ALREADY_TRUE** | Verifier-first `settle`; `initial_action`; `no_unnecessary_cognition`; ADR 0007; roadmap "Cognition" row (`001…:57`) |
| Bounded selection before generative cognition | **PARTIALLY_TRUE** | Exists in `semantic_review`, exec profiles, suitability vocabulary and the non-deployed semantic bridge. The deployed Qwen adapter generates whole decisions, and nothing tries bounded selection first. |
| Runtime-owned candidate set | **PARTIALLY_TRUE** | `semantic_provider.current_actions` (fixture-scoped). The deployed `decision_schema` is static and even omits the `workspace.*` and `text.stats` capabilities (`model.py:21`). |
| Models do not own authority | **ALREADY_TRUE** | `model.py:1` docstring; ADR 0024; `accept_task_request` keeps the grant out of the TaskSpec |
| Host revalidation | **ALREADY_TRUE** | `validate_decision` runs in both the adapter and the gate; revision/turn binding; `validate_admissibility`: "Reject a proposal; never replace it" |
| PolicyGate remains authoritative | **ALREADY_TRUE** | `workflow.py:686`; semantic bridge test `test_lowering_preserves_semantics_and_existing_policy_remains_authoritative` |
| Cognition separated from execution | **ALREADY_TRUE** | `workflow.py:1`: "Cognition returns data; only this dispatcher acts." |
| Execution result represented as evidence | **ALREADY_TRUE** | Capability journal and receipts (ADR 0026, E2.0) |
| Completion independently verified | **ALREADY_TRUE** | `completion.legality`; `test_model_complete_still_cannot_bypass_verifier` |
| Selector abstention | **PARTIALLY_TRUE** | Present in `semantic_review`, `BoundaryObserver` ABSTAIN and `select()` `STOP_OR_ESCALATE`. **Missing from the CognitiveAdapter contract**: an invalid or undecided output raises, is retried, then fails the Task. |
| Escalation from bounded to generative | **MISSING** within a turn; **CONFLICTS** if abstention can move the binding | Blaine "escalation" means Policy C binding rebind through trusted admission only |
| Model interchangeability | **ALREADY_TRUE** at the interfaces | `CognitiveAdapter`; `test_replacement_provider_needs_only_semantic_context`; `WorkloadClassifier` |
| Replayable decision records | **PARTIALLY_TRUE** | Per-turn packet and decision are retained (`workflow.py:640, 679`) and referenced by `cognition.decided` events. The admissible set lives only in a non-durable audit callback; `RoutingRecord.usage` is always `None`. |
| Offline comparison of selectors | **PARTIALLY_TRUE / PREMATURE** | Jev `carveout.py` rows plus `ShadowClassifier` for suitability only; Increment 8 snapshot replay; C5 "begin offline". No corpus of real Cognitive Loop Tasks exists. |
| Context claim: Qwen emits retry / fail / escalate / continue | **CONFLICTS** | NextAction is exactly INVOKE/HANDOFF/SPAWN/WAIT/COMPLETE (`test_schema_keeps_five_actions`). Retry and failure are runtime policies (checkpoint §2). |
| "Should execution retry, escalate, wait, fail, or continue?" is a selection | **CONFLICTS** | Each of those is deterministic or trusted today (Policy C, verifier-first, known waits) |
| Worker / model-class selection as bounded selection | **SUPERSEDED_BY_EXISTING_DESIGN** | ADR 0010 + `worker_routing` + ADR 0024 + roadmap C3 already govern this, gated on evidence |
| Candidate versioning / stale-state detection | **SUPERSEDED_BY_EXISTING_DESIGN** | Single-writer workflow, `task_revision`/`turn_id` binding, E2.0 conditional writes, uncertain-effect blocking |
| Opaque `candidate_id = 17` | **CONFLICTS** (style) | Blaine uses stable named IDs: profile IDs, suite IDs, specialists, `allowed_responses` |
| Candidate generator is part of trusted architecture and must be tested | **ALREADY_TRUE** in spirit | `current_actions`: "Legality only. Never mask a valid rewrite"; `test_legal_rewrite_not_masked_by_quality_preference` |
| Laya / Jev / Qwen experiment | **PREMATURE** | Laya and Keel appear nowhere in the repo. Jev is an unadopted remote candidate (C3). |
| Replay over online self-modification; promotion by explicit change | **ALREADY_TRUE** | Roadmap C5; ADR 0024 "history, measurement, proposal, evaluation, then human promotion" |
| Steady-state distribution (mostly bounded) | **PREMATURE** (the ADR already disclaims it) | No real-Task Cognitive Loop data |

## 5. The bounded-decision seam that already exists

**The smallest seam** is `CognitiveAdapter = Callable[[dict], dict]` (`workflow.py:28`). It is invoked inside the journaled step `cognitive/{iteration}` (`workflow.py:647-677`), takes a `CognitiveTurn` packet, and returns a `CognitiveDecision` that `policy_gate` then judges. Increment 8 already built the bounded pattern behind that seam:

- `SemanticDecisionProvider.decide(context, admissible_actions)` (`semantic_provider.py:108-109`) is the selector interface, and it is provider-neutral.
- `current_actions()` (`semantic_provider.py:43-56`) constructs the admissible set from runtime state and policy, for legality only.
- `validate_admissibility()` rejects without substituting another action. `SemanticDecisionBridge.lower()` deterministically builds the protocol command.

The ADR's pipeline (state → legal candidates → selector → revalidate → PolicyGate → execute) fits this seam with **no workflow, lifecycle, PolicyGate or verifier change**. A parallel framework is not needed.

Answers to the seam questions:

- **Explicit action vocabulary?** Yes. The five `NextAction` variants, plus four semantic actions in the bridge.
- **Enumerable from state?** The action type, capability name, handoff target, human request, packet ref and exec profile are. Content, child specs and paths are not.
- **Does the model invent or select?** It selects a type and capability from a closed set, which is enforced (unknown types are rejected; capabilities outside the admissible set are denied), and it generates the arguments. Safety is already contained, so the ADR's benefit here is efficiency and reliability, not safety.
- **Authoritative version?** Yes. `task_revision` and `turn_id` are checked in the adapter and again in the gate.
- **Can state go stale between cognition and execution?** Not inside the loop: the main handler is the single writer, and amendments apply only at iteration boundaries. External-world staleness is handled by E2.0 conditional writes and reconciliation. Stale-selection rejection therefore already belongs in `policy_gate` and effect lowering, and it is already there.
- **PolicyGate downstream, Completion Contracts untouched?** Yes, by construction.

**What is missing for this seam to carry a real selector:**

1. **A general projection.** The bridge is fixture-scoped: its constructor takes a single `purpose`, `request_id` and `artifact` (`semantic_bridge.py`). The deployed adapter's schema is not derived from state.
2. **Separating which action from its arguments.** When the runtime already knows the arguments (for example the contract-fixed human request), lowering should fill them in. Today even the bridge makes the model re-emit the question and choices.
3. **An abstain / unresolved outcome** that does not turn into exception → retries → FAILED. For example, a composite adapter that falls back to generative cognition within the same journaled step.
4. **A durable per-turn record** of the admissible set and the selector's trace. Today this exists only as an audit callback.

## 6. Jev / Laya / Qwen implications

**Candidates today, with no change to lifecycle, authority, capabilities, execution or verification:**

- `WorkloadClassifier.assess`: clean; Jev is already plugged in, in shadow mode. It is not a Qwen decision and not in the Task path.
- `BoundaryObserver.inspect`: clean; observation only.
- `SemanticDecisionProvider.decide`: clean at the interface (`test_replacement_provider_needs_only_semantic_context`). But it is not deployed. Only `COMPLETE` is a pure selection there; REQUEST_HUMAN and PRODUCE_ARTIFACT require generated content.
- The `semantic_review` reviewer: nearly clean. Jev's choice + confidence fits the verdict and confidence fields, but a nonblank rationale and packet-cited evidence refs are required, and no deployment injects a reviewer today.

**Not candidates, under any framing:**

- Qwen's full `CognitiveDecision` (it generates payloads).
- Completion legality, PolicyGate, `escalation_condition` / `admit_escalation`, waits on known dependencies, effect reconciliation, `ask_before` approvals, contract amendments and waivers.
- Binding / model selection, which is trusted deployment configuration governed by C3.

**Missing prerequisites:**

1. Items 1–4 from §5.
2. **Egress.** Jev is remote (`DESTINATION = 'https://api.typesafe.ai'`, `jev_provider.py:33`), credential- and credit-metered, with cost UNKNOWN. Today it receives only declared routing metadata (`routing_state`, `jev_provider.py:182-187`). Cognitive Loop observations contain Task content, so each call becomes a Cloud Worker invocation under ADR 0008/0009 and sharing policy. This inverts the ADR's premise: in Blaine, local Qwen inference is the abundant resource, not the expensive one.
3. **Laya** does not exist in the repository.
4. **A real-Task corpus.** C3 requires roughly 20–30 real Tasks.

**The Laya vs. Jev vs. Qwen experiment:** do not run it soon. Blaine must first have a stable typed decision boundary on the deployed path, plus retained admissible sets, and real Tasks to replay.

There is also a caution from Increment 8. It found the hard problem was choosing among *legal* actions: Qwen rewrote a correct artifact five times instead of finishing. That was solved by moving the decision out of cognition (verifier-first progression), not by a better selector. A bounded selector faces exactly the same choice. Reframing the experiment as "which decision classes can be reduced" is right, but that question cannot be answered until the classes exist in retained records.

## 7. ADR edits

**KEEP**
- The core invariant (selector proposes; host validates; executor executes; verifier establishes the outcome).
- Candidates are constructed by the runtime; output never grants authority or becomes an executable primitive.
- A stale decision fails closed.
- Selection and verification are separate; "COMPLETE must not itself complete."
- Confidence is never authority; escalation policy is host-owned.
- Replay-based improvement, and promotion only by explicit version-controlled change.
- Candidate construction is trusted and tested.
- The "over-applying to generative problems" negative.
- The non-goals list.
- "Models are replaceable components inside a deterministic execution system."

**CHANGE**
- Context: replace "continue / retry / fail / escalate" with the actual five `NextAction` variants. State plainly that retry, failure, escalation, known waits and completion are already runtime-owned.
- Candidate example: drop `FAIL`. Replace `RUN_TESTS`/`INSPECT_DIFF`/`CONTINUE_IMPLEMENTATION` with real admissible actions, e.g. `workspace.exec` with a reviewed profile ID, `worker.run`, `human.request(<contract-fixed id>)`.
- Candidate identity: use stable named IDs bound to `task_revision`/`turn_id`, not ephemeral integers. Stale handling should cite the existing revision binding, not new "candidate versioning."
- Diagram: put verifier/legality at the top of the loop (verifier-first), not only after the capability. Keep PolicyGate downstream.
- "Cognitive Routing" → e.g. "bounded semantic decision within a cognitive turn". "Routing" already means binding/worker selection in Blaine.
- "Escalation to System-2" → "fallback to generative cognition". "Escalation" already means Policy C binding rebind.
- "Which worker / which model class" → defer to ADR 0010/0024 and C3. A selector may at most produce a suitability recommendation that the hard gate admits.
- Position the ADR as the extension of ADR 0007 and the formal record of Increment 8's cognition boundary. No ADR currently records that boundary: the checkpoint's proposed ADR (a) was never written (`cognitive-loop-checkpoint.md:345-347`). This is the ADR's strongest reason to exist.

**REMOVE**
- System-1 / System-2 as domain terms (see the terminology note below).
- Keel and `jev-ultrafast` as rationale. They are external and unevidenced in the repo; mention them at most as inspiration.
- The model roster (Laya/Jev/Qwen per layer) and the reframed experiment. They belong in a C3/C5 slice, not the ADR.
- "Hallucinated capabilities / invalid tool calls" as a positive consequence; that containment already exists.
- The illustrative distribution.
- The per-decision latency/cost fields as a mandate (cost is often UNKNOWN by rule).

**ADD**
- Candidate construction is **legality only, never strategy**. A heuristic pre-selection is Policy B and must be derived from evidence.
- Deterministic **lowering**: the selected action's runtime-determined arguments are filled by code. Name the existing `SemanticDecisionProvider` / `SemanticDecisionBridge` as the seam.
- **Human governance is a separate authority channel**, not the tail of a cognition ladder: approvals, amendments/waivers, contract-fixed requests, and `semantic_review` escalation.
- **Provenance**: selector output is `model` provenance and can create at most ADVISORY criteria (ADR 0026).
- **Egress**: a remote selector is a Cloud Worker (ADR 0008/0009); local-first applies.
- **Resources**: selecting an action never acquires resources; the trusted arbiter owns claims (Verification Scheduler).
- Abstention must be representable **without** failing the Task and **without** touching binding escalation.
- Decision records **extend** retained `context_ref`/`decision_ref` and the ExecutionEvents; they are not a new store.
- A Validation section in the repo's ADR convention (hypothesis, level, evidence, not-required, reconsider-when).

**Terminology.** Jev's SDK method is literally `client.system_one(...)` (`jev_provider.py:136`), so "System-1" is a vendor term. Blaine has already rejected imported vocabulary on this principle: the worker boundary contract chose "ContinuationBoundary" because "step imports a foreign harness vocabulary" (`worker-execution-boundary.md:28-33`). Recommended terms:
- **bounded semantic decision** or **semantic selection** over **hard-admissible actions** (the existing term), with **selector** as the component role;
- **generative cognition** only as explanatory prose;
- avoid "classifier" (taken by `WorkloadClassifier`), "routing", and "escalation" for this concept.

## 8. Roadmap fit

- **The principle belongs now.** It formalizes an existing stable boundary (roadmap "Cognition" row, `001…:57`) and fills a missing ADR slot. Adopting it costs no delivery time.
- **Implementation belongs in no active track.**
  - The roadmap says Jev and learned routing are explicitly not v0 blockers (`:186`).
  - "Future kernel changes should answer concrete Daily Driver evidence" (`:100`).
  - C3 says "do not invent a use case" for Jev (`:640`); C5 says learning starts offline (`:644`).
  - The current critical path is E0.E → E1.A–E → E2.A and CP.2. None of it needs this work.
- **The prerequisite seam** is Increment 8's recorded follow-up debt (hard projection on the production adapter and scoped vocabulary cleanup, milestone 024 "Adopted invariant"). The first real evidence source is E3, which already requires REQUEST_HUMAN and typed human input. E3 is where a need would show up.
- **No new track.** When evidence arrives, this is a bounded Cycle C slice (C3/C5) plus the Increment 8 debt item.

Two small incidental drifts, noted and not acted on: the roadmap (`:1018`) still says the Local Verification Scheduler is "not yet on main" although this commit merged it; and `architecture.md:74-77` still calls the Context Plane NOT STARTED although CP.1 has passed.

## 9. Final recommendation

**ADOPT_WITH_REVISIONS.** Roughly two-thirds of the ADR's assertions are already true on main, and the rest duplicates existing mechanisms or conflicts with them. What remains is genuinely useful and currently has no ADR:
- where the runtime can fully construct an action, select it rather than regenerate it;
- abstention as a first-class outcome;
- retained admissible sets so decisions can be replayed.

Adopt it as a narrow principle ADR: an extension of ADR 0007 that records the Increment 8 cognition boundary, with the §7 revisions, marked Accepted / Unvalidated.

**IMPLEMENTATION_TIMING: AFTER_<E3 real-Task Cognitive Loop evidence, then the hard-admissible action projection extended to the deployed cognition adapter>.**
- The selector experiment (Laya/Jev/Qwen) has a further gate on top of that: C3/C5 (a real-Task corpus and beating Policy B/C).
- Laya must first exist in the repo.
- Any remote selector must pass ADR 0008/0009.

## 10. Evidence index

| Path | Symbol / location | What it proves |
|---|---|---|
| `runtime/kernel/workflow.py` | `:1` docstring; `:647-693` `decide`, gate | Cognition returns data; only the dispatcher acts; PolicyGate sits downstream of every decision |
| `runtime/kernel/workflow.py` | `:307-358` `settle` | The only path to COMPLETED; verifier runs before cognition |
| `runtime/kernel/workflow.py` | `:601-617`; `runtime/kernel/routing.py:8-11, 117-142` | Escalation is deterministic and trusted; no model is asked if it is stuck |
| `runtime/kernel/workflow.py` | `:671-676`; `runtime/personal_runtime.py` `no_unnecessary_cognition` | Deterministic actions skip cognition entirely |
| `runtime/kernel/workflow.py` | `:829-833`, `:205-255` | Known human waits are runtime-owned |
| `runtime/kernel/workflow.py` | `:640, 679, 684-685, 965-979` | Packet and decision retained per turn; `RoutingRecord.usage=None` |
| `runtime/kernel/contracts.py` | `:12-17, 48-80, 351-383` | Closed action vocabulary; no RETRY/FAIL/ESCALATE actions |
| `runtime/kernel/execution.py` | `:38-43, 47-48, 60-65, 96-112` | Stale rejection; capability membership; exact human request; profile admission |
| `runtime/kernel/model.py` | `:18-48` (esp. `:21`), `:150-171` | Deployed schema is static "guidance"; Qwen generates full decisions; strict validation |
| `runtime/kernel/semantic_provider.py` | `:43-63, 93-109` | Runtime-derived admissible set; reject-don't-replace; provider-neutral selector interface |
| `runtime/kernel/semantic_bridge.py` | `:29-100` | Projection + deterministic lowering; single-fixture scope |
| `runtime/kernel/review.py` | `:20-37, 93-120` | An adopted bounded semantic judgement with confidence and abstention |
| `runtime/kernel/completion.py` | `:25, 511-570`; `:171` | Deterministic legality; model provenance limited to ADVISORY criteria |
| `runtime/kernel/worker_routing.py` | `:1-5, 56-80` | Suitability recommendation plus hard gate; not in the Task path |
| `runtime/kernel/instrument.py` | `:355-378` | PROCEED/ABSTAIN observers; no intervention |
| `runtime/kernel/effects.py` | `:70-71, 172-179, 214-218` | Named-candidate pattern already exists for execution (reviewed profiles) |
| `infra/services/runtime.json` | `cognition` | Deployed cognition is local Qwen |
| `experiments/jev-provider-carveout/jev_provider.py` | `:33, 136, 182-187` | Jev is remote; "system_one" is a vendor term; metadata-only today |
| `tests/test_kernel_progression.py` | `test_model_complete_still_cannot_bypass_verifier` | Model COMPLETE cannot complete a Task |
| `tests/test_kernel_semantic_provider.py` | `:136, 147, 157, 174` | Provider replaceability; legality-only projection; no provider call while pending |
| `tests/test_kernel.py` | `:51` | Stale and invalid decisions rejected |
| `tests/test_kernel_routing.py` | `:333` | Policy C path contains no classifier or Jev |
| `tests/test_jev_provider.py` | `:196, 396` | Jev disagreement is recorded, not applied; kernel has no Jev reference |
| `docs/milestones/024-…increment-8-passed.md` | "Adopted invariant" | The ADR's pipeline is already the adopted production invariant |
| `docs/milestones/022-…hybrid-experiment.md` | "Results", "Action projection" | The hard problem is legal-action progress selection, not admissibility |
| `docs/roadmap/001-…roadmap.md` | `:57-58, 100, 186, 640-644` | Stable cognition boundary; kernel changes need Daily Driver evidence; Jev not a v0 blocker; C3/C5 gates |
| `docs/research/cognitive-loop-checkpoint.md` | `:114-115, 345-347` | Retry/failure are runtime policies; the Cognitive Loop ADR was proposed but never written |
| `docs/contracts/worker-execution-boundary.md` | `:28-33` | Precedent for rejecting foreign vocabulary |
