# TaskSpec v1

A TaskSpec describes the intent and constraints of durable work.

It is not runtime state and not an execution plan.
The Personal Agent forms it from natural conversation; the user should not need
to fill out a workflow form.

Runtime code validates and persists the accepted specification, assigns identity,
and owns lifecycle state.

No session ID, retry counters, worker process details, runtime status, or workflow
steps belong here.

## Structure

Only `objective` and `completion` are required.

Other fields are included only when they materially change how the Task should be
executed. Bindings/runtime may normalize omitted fields to conservative defaults.

| Field | Shape and meaning |
|-------|-------------------|
| `objective` | **Required.** Nonempty string describing the desired outcome and scope, not a transcript. |
| `mode` | Optional `interactive` or `background`. Omitted means `interactive`. Neither ties execution to a chat/session. |
| `context` | Optional list of `{need, source?, freshness?, sharing?}`. `need` describes information required by the Task. `source` is an addressable reference, not prompt content or credentials. `freshness` describes a version/as-of requirement. `sharing` is `local-only` or `cloud-allowed`; unknown sharing is treated as local-only. |
| `capabilities` | Optional list of scoped capabilities the work requires, such as `read repository`, `edit task workspace`, `network`, or `read public web`. Requirements do not grant access or choose a worker/vendor. |
| `autonomy` | Optional object with `allowed`, `ask_before`, and `forbidden` string lists. It records user-granted scope and constraints. Omission never expands authorization. |
| `cloud` | Optional `{policy, max_usd?}`. Policy is `forbid`, `ask`, or `allow-within-budget`. Omitted means `ask`. |
| `completion` | **Required.** Nonempty list of `{criterion, evidence}`: an observable acceptance condition and how it will be checked or evidenced. The runtime's durable, amendable form is the [Completion Contract](completion-contract.md) (v1 designed, not implemented); this list lowers into its revision 0. |
| `schedule` | Optional. Either `at` for one-shot scheduled work, or `every` with `starts_at` for recurring work. Recurring work must have `ends_at` or another bounded stop condition expressed in completion. |

## Cloud authorization

Cloud budget and cloud authorization are distinct.

- `forbid`: paid cloud inference is not allowed.
- `ask`: paid cloud inference requires explicit user approval before dispatch.
- `allow-within-budget`: paid cloud inference is pre-authorized up to `max_usd`.

`max_usd` is required and positive for `allow-within-budget`.

A budget ceiling never grants authorization by itself. If `max_usd` is present
under `ask`, it remains only a ceiling after explicit approval.

Cloud ceilings apply across all paid attempts for the Task and must be enforced by
code. Unknown pricing or an unenforceable ceiling cannot authorize a paid dispatch.

## Context and scheduling

Resolve context just in time.

Freshness and sharing restrictions also apply to context derived from the original
source. Clarify before submission when a missing source determines the target,
authorization, or intended outcome.

Scheduling requires explicit dates and offsets. Resolve ambiguous user time zones
before submitting scheduled work.

Schedule describes when work should run; completion describes when the requested
outcome has been demonstrated.

See [examples](task-examples.md) for representative TaskSpecs.

Use [local/cloud policy](../policies/local-first-and-context.md) for context packet
and cloud decisions, and
[lifecycle policy](../policies/task-completion-and-lifecycle.md) for completion
and safety semantics.
