# ADR 0028 — Cognition selects hard-admissible actions the runtime can construct

**Status:** Accepted (2026-09-24, operator direction) — architectural principle only; implementation deferred
**Validation:** Deferred — unvalidated for the deployed Cognitive Loop; awaits real E3 / Daily Driver Tasks
**Date:** 2026-09-24

## Context

Increment 8 settled who owns progression in the Cognitive Loop: cognition proposes
semantic work, and the runtime decides whether cognition is needed at all. After
authoritative evidence changes, the Completion Contract is evaluated first; a
satisfied contract completes, a known blocking dependency suspends, and only
otherwise does the runtime derive hard-admissible actions and invoke cognition,
whose proposal is strictly validated, deterministically lowered and admitted by
PolicyGate ([milestone 024](../milestones/024-cognitive-kernel-increment-8-passed.md)).
That boundary is recorded in a milestone, in the roadmap's
[stable boundaries](../roadmap/001-blaine-development-roadmap.md) "Cognition" row and
in an amendment to the [Cognitive Loop checkpoint](../research/cognitive-loop-checkpoint.md),
whose §10 proposed an ADR for the Task-scoped Cognitive Loop. No ADR records it.

The code already contains the seam and a proven instance of the pattern:

- [`workflow.py`](../../runtime/kernel/workflow.py) invokes a deployment-injected
  `CognitiveAdapter` inside a journaled step. It returns a `CognitiveDecision`
  bound to `task_revision` and `turn_id`, which PolicyGate (`policy_gate` in
  [`execution.py`](../../runtime/kernel/execution.py)) admits or denies.
- [`semantic_provider.py`](../../runtime/kernel/semantic_provider.py) and
  [`semantic_bridge.py`](../../runtime/kernel/semantic_bridge.py) implement the
  bounded form. `current_actions()` derives the hard-admissible actions from
  state and policy ("legality only"), `SemanticDecisionProvider.decide(context,
  admissible_actions)` is the provider-neutral selector interface,
  `validate_admissibility()` rejects a proposal without substituting another, and
  `SemanticDecisionBridge.lower()` builds the protocol command in code.

That bounded form is scoped to the Increment 8 fixture and is not the deployed
adapter. The deployed `LocalModelCognition` ([`model.py`](../../runtime/kernel/model.py))
generates a whole `CognitiveDecision`, including arguments the runtime already
knows. The clearest case is the contract-fixed `HumanDecisionRequest`: PolicyGate
requires it to equal the accepted request exactly, yet the model must reproduce it
byte for byte. Admitted packet references, reviewed exec profile identifiers and
handoff specialists are likewise finite sets the runtime can enumerate.
Regenerating them spends inference and adds a failure surface without adding
judgement.

A draft proposal, prompted by external systems that let a light model pick among
host-built candidates, suggested a general principle here. The
[architecture review](../../reviews/adr-bounded-decisions-architecture-review.md)
of that draft against `main` found that most of it is already true, that parts
conflict with existing boundaries (it handed retry, failure, escalation, waits,
completion and model choice to a selector), and that one principle is useful and
unrecorded. This ADR records that principle only.

## Decision

### Principle

**When Blaine's runtime can derive the complete set of hard-admissible actions for a
cognitive decision, cognition selects among those actions rather than regenerating
them.** A selection is a proposal. It grants no authority and establishes no
outcome.

In Blaine's terms the invariant is:

```text
runtime derives hard-admissible actions       trusted code; legality only
cognition selects or proposes                 CognitiveAdapter → CognitiveDecision
runtime validates and lowers                  strict validation; task_revision/turn_id binding;
                                              deterministic lowering of runtime-known arguments
PolicyGate admits or denies                   the only authority over execution
dispatcher executes; evidence is retained     capability journal, receipts, observations
Completion Contract decides the outcome       legality; a COMPLETE proposal is only a request
```

This formalizes and extends the Increment 8 boundary. It introduces no second
Cognitive Loop, decision framework, action vocabulary or model hierarchy.

### Place in the loop

Deterministic runtime and verifier logic runs first and can make cognition
unnecessary:

```text
evidence or input changes
  → evaluate the Completion Contract ─────────── legal → COMPLETED       (no cognition)
  → known blocking dependency? ───────────────── yes   → durable WAITING (no cognition)
  → deterministic next action (initial_action)? ─ yes   → PolicyGate     (no cognition)
  → derive hard-admissible actions
      → bounded semantic decision: select among them
        or generative cognition: propose what cannot be derived
      → validate → lower → PolicyGate → execute → retain evidence
  → back to the top
```

### Three cases

1. **The runtime can construct the whole action** (type, target and arguments).
   Cognition selects; the runtime lowers the selection deterministically.
   Examples: the contract-fixed `human.request`, `worker.run` over an admitted
   packet reference, `workspace.exec` by reviewed profile identifier, `HANDOFF` to
   an eligible specialist, a `COMPLETE` request.
2. **The runtime can enumerate the action but not all of its content.** The
   runtime fixes the admissible type and every derivable field; cognition selects
   the action and generates only the content that cannot be derived, such as
   `artifact.write` content. Not every `CognitiveDecision` reduces to an
   identifier.
3. **The solution space cannot reasonably be enumerated.** Normal generative
   cognition proposes, as today: a child TaskSpec, a `context.request` question,
   a new approach after verifier rejection. This ADR is not an argument to
   eliminate generative cognition.

### Outside semantic selection

These decisions stay where they are. No selector owns them:

| Decision | Owner |
|---|---|
| Technical retry | Runtime / Restate retry policy |
| Terminal failure | Runtime (turn limit, invariant failure, terminal errors) |
| WAIT on a known dependency | Runtime (durable suspension) |
| Completion legality | Completion Contract and its verifiers ([ADR 0026](0026-completion-contract-is-a-durable-task-primitive.md)) |
| Model-binding escalation | Policy C conditions and trusted admission ([ADR 0024](0024-local-first-execution-with-bounded-escalation.md)) |
| Provider, model and worker binding | Trusted deployment and worker-selection policy ([ADR 0010](0010-worker-selection-is-capability-and-quality-driven.md), [ADR 0024](0024-local-first-execution-with-bounded-escalation.md)) |
| Effect approval, contract amendment and waiver | Human governance (below) |

A model may propose `COMPLETE`; only the Completion Contract decides whether the
Task completes.

### Constructing hard-admissible actions

- Construction is **legality only, never strategy**. It excludes what policy,
  authority or Task state makes inadmissible and nothing else. A heuristic that
  pre-selects the "likely" action is a routing or progression policy and needs
  its own evidence; it is not candidate construction.
- Construction is trusted runtime logic and must be tested like PolicyGate. A
  selector cannot choose a correct action the runtime failed to expose.
- Actions carry stable named identifiers and are bound to the `task_revision` and
  `turn_id` they were derived from. A stale or misaddressed decision fails closed,
  as it does today; external-world staleness remains the job of conditional
  effects and reconciliation.

### Abstention

A bounded semantic decision may abstain. Abstention is a cognitive outcome, not an
authority: within the same turn and the same binding it may hand the decision to
generative cognition. It never rebinds the model (that remains Policy C), never
grants, completes or fails a Task by itself. Confidence scores are never
authority.

### Human governance

Human authority is a separate governed channel, not the last rung of a cognition
ladder. It covers `ask_before` approval of a concrete effect, Completion Contract
amendment and waiver, responses to contract-fixed human requests, and
`semantic_review` escalation to a human where a contract configures it. A selector
never acquires human authority. At most it proposes a contract-fixed
`human.request`, which PolicyGate checks against the contract.

### Provenance and authority

Selector output is model-derived. Under [ADR 0026](0026-completion-contract-is-a-durable-task-primitive.md)
it can create at most ADVISORY criteria and cannot amend or waive the contract.
Under [ADR 0024](0024-local-first-execution-with-bounded-escalation.md) it cannot
widen a grant or obtain a binding. Nothing in this ADR weakens PolicyGate, grants,
the Completion Contract or provenance rules.

### Remote selectors

A selector outside the local trust boundary is remote cognition. It is a Cloud
Worker under [ADR 0008](0008-paid-cloud-crosses-single-dispatch-boundary.md) and
[ADR 0009](0009-cloud-context-packet.md) and is subject to sharing and egress
policy for every decision packet it receives. It is not presumed cheaper or
preferable to local generative cognition; local-first
([ADR 0007](0007-tools-before-model-inference.md), ADR 0024) still applies, and
unobservable cost stays UNKNOWN.

### Evidence and replay

Bounded-decision evidence extends existing records rather than adding a store.
Today each turn retains its `CognitiveTurn` packet (`context_ref`) and
`CognitiveDecision` (`decision_ref`) as content-addressed artifacts, referenced by
the `cognition.decided` and `policy.evaluated` ExecutionEvents
([contract](../contracts/execution-event.md)), and each Task retains its
RoutingRecord. When bounded decisions are implemented, the derived admissible
actions and any selection or abstention are retained alongside those records, so a
historical decision can be replayed offline against another selector without
repeating its effect. No new cost field is mandated where accounting is UNKNOWN.

Improvement is replay- and evidence-driven. Selector or construction changes are
promoted through reviewed, version-controlled changes, never by online
self-modification. Models remain replaceable components behind `CognitiveAdapter`
and `SemanticDecisionProvider`.

### Terminology

Use **bounded semantic decision**, **semantic selection**, **hard-admissible
actions**, **selector** and **generative cognition**. Do not use "routing",
"escalation" or "classifier" for this concept; each already has a specific
meaning in Blaine (binding and worker selection, Policy C rebinding,
`WorkloadClassifier`). "System-1/System-2" and provider vocabulary are not Blaine
terms.

## Implementation timing

The principle is adopted now. Implementing it is **not** authorized by this ADR.
It adds no selector, changes no deployed adapter, adds no `NextAction` variant or
store, and selects or integrates no model or provider.

Implementation waits for real E3 / Daily Driver Cognitive Loop Tasks. Only when
they show a concrete need does the next step follow: extending the hard-admissible
action projection and deterministic lowering (today `current_actions()` and
`SemanticDecisionBridge.lower()`) to the deployed cognition adapter, with the
derived actions retained per turn.

Comparing selectors becomes meaningful only after that: with a stable projection
on the deployed loop, retained decision evidence and a corpus of real Tasks. Any
comparison belongs to the existing roadmap Cycle C evidence process (C3/C5) under
its gates, not to a new track. Specific models or providers are candidates for
that process, not part of this decision.

## Alternatives considered

- **Leave the boundary in milestones and the roadmap only.** Rejected: it
  constrains E3 cognition design and the checkpoint already called for an ADR.
- **Adopt the draft as written.** Rejected: it placed retry, failure, escalation,
  known waits, completion and model choice under a selector, contradicting Policy
  C, verifier-first progression and ADR 0026; it named a model roster and an
  experiment; and it introduced a parallel "cognitive routing" vocabulary.
- **Treat every decision as a candidate identifier.** Rejected: many decisions
  need generated content that the runtime cannot derive.
- **Implement a general selector now.** Rejected: no real-Task evidence exists, and
  the roadmap directs kernel changes to answer concrete Daily Driver evidence.

## Relationship to existing decisions

- [ADR 0007](0007-tools-before-model-inference.md): extended. After deterministic
  mechanisms, prefer selecting a runtime-constructed action before generating one.
- [ADR 0015](0015-durable-task-execution-and-verification.md): complemented;
  semantic proposal stays separate from enforced execution.
- [ADR 0024](0024-local-first-execution-with-bounded-escalation.md): unchanged.
  Binding escalation remains deterministic and trusted.
- [ADR 0026](0026-completion-contract-is-a-durable-task-primitive.md): unchanged.
  The contract alone decides completion; model provenance stays advisory.
- [ADR 0008](0008-paid-cloud-crosses-single-dispatch-boundary.md) and
  [ADR 0009](0009-cloud-context-packet.md): apply to any remote selector.
- [ADR 0010](0010-worker-selection-is-capability-and-quality-driven.md): unchanged.

No accepted ADR is superseded.

## Consequences

Cognition design for E3 and later has a named rule: where the runtime can build
the action, prefer selection and deterministic lowering over regeneration. That
should shrink prompts and remove a class of rejected proposals, such as
imperfectly reproduced human requests, without touching authority or completion.

The runtime takes on more trusted work: deriving admissible actions, lowering
selections and retaining their evidence. Poor construction can hide the right
action, so construction needs tests of its own. The distinction between a fully
constructible action and one that still needs generated content must be kept
explicit rather than forced into identifiers.

Deferred: a general selector, abstention handling in the deployed adapter,
retention of admissible actions per turn, and any selector comparison.

## Validation

### Hypothesis

When the runtime can fully derive the hard-admissible actions for a decision,
semantic selection reduces unnecessary generative cognition without weakening
progress, authority or verification semantics.

### Validation level

`Deferred` for the deployed Cognitive Loop. Validating now would require
speculative work on an absent workload. When unlocked, `Integration` on retained
real Tasks, then `End-to-end` within Daily Driver use.

### Existing supporting evidence

Increment 8 established the semantic decision and projection boundary:
hard action projection worked as an interface constraint in a live experiment
([milestone 022](../milestones/022-cognitive-kernel-increment-8-hybrid-experiment.md)),
verifier-first progression was adopted in production
([milestone 024](../milestones/024-cognitive-kernel-increment-8-passed.md)), and
[`test_kernel_semantic_provider.py`](../../tests/test_kernel_semantic_provider.py)
shows a replacement provider needs only semantic context, projection filters by
policy without selecting strategy, and PolicyGate stays authoritative. That
evidence covers one fixture; it does not validate this ADR for the deployed loop.
Milestone 022 also showed the harder problem is choosing among legal actions
(a correct artifact was rewritten instead of finishing), which selection alone does
not solve.

### Minimal validation

On retained real E3 / Daily Driver Tasks, identify turns whose decisions were fully
constructible (case 1). Replay their retained packets through the extended
projection and a selector, without repeating effects, and compare with the
decisions actually taken and with downstream Task outcomes.

### Evidence

PASS requires that, on those turns:

- every selected action is admitted by the unchanged PolicyGate, and no decision
  outside the derived set is produced;
- no Task completes, fails, waits or rebinds because of a selection or an
  abstention;
- downstream outcomes (completion, verifier rejections, turns) are no worse than
  with generative cognition;
- generative calls or rejected proposals fall measurably on those turns;
- the derived actions and each selection or abstention are retained with the
  existing decision records.

### Not required for validation

A general selector framework, a new store, a new `NextAction` variant, a new
track or milestone, a remote provider, or a comparison between specific models.

## Reconsider when

Real Tasks show that useful action spaces cannot be projected without embedding
strategy in trusted runtime code; bounded selection measurably degrades downstream
Task outcomes; almost no real decisions fall into the fully constructible case, so
the principle adds no value; or the Cognitive Loop's ownership boundaries
(verifier-first progression, PolicyGate, Policy C) change.
