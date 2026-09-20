# Frontier dispatch — projected context, authority, suitability and accounting

This includes the human-authorized Increment 11 routing/accounting correction and
its subsequent structural outbound-context projection gate.
[ADR 0008](../decisions/0008-paid-cloud-crosses-single-dispatch-boundary.md),
[ADR 0009](../decisions/0009-cloud-context-packet.md),
[ADR 0010](../decisions/0010-worker-selection-is-capability-and-quality-driven.md)
and [ADR 0018](../decisions/0018-local-platform-durability-and-observability.md)
remain constraints. No live frontier capability is enabled by this proof.

## Three independent decisions

| Concern | Owner | Representation |
|---|---|---|
| Hard authority | Trusted Blaine code, existing PolicyGate, enforcing adapter | `FrontierAuthority` v2, `GlobalGuardrails`, `AuthorizedFrontierRequest` v3 |
| Economic suitability | Replaceable workload classifier and deterministic router | `Workload`, `Assessment`, selected binding recommendation |
| Observed usage | Blaine records adapter observations, with unknown values preserved | Separate dispatch-keyed accounting records, exact artifacts and ExecutionEvents |

`worker_dispatch != model_inference`. One worker execution can contain many model
calls. Task, worker-dispatch, worker-session and model-call identities remain
separate. A recommended worker is not authorized by its recommendation.

## Mandatory outbound projection

```text
authoritative/resolved context
→ Blaine-configured FrontierContextProjector
→ immutable ProjectedContext v1
→ exact UTF-8 content digest / artifact
→ FrontierAuthority v2 and authorization
→ AuthorizedFrontierRequest v3
→ dispatch-time comparison with the accepted grant
→ provider adapter
```

[frontier_context.py](../../runtime/kernel/frontier_context.py) defines the small
provider-neutral hook. `project_context()` invokes the explicitly supplied trusted
projector and is the only supported constructor of `ProjectedContext`. The initial
`IdentityProjector` performs no transformation; it is not a filter or security/quality
claim. Projection selection is Blaine-owned configuration, never model input.

The frozen output contains version, Task identity, projector identity, projected
content and its SHA-256 digest. The digest covers **exact projected content encoded
as UTF-8**, not the raw source, projection envelope or a reserialized provider
request. The existing artifact store holds those bytes; the grant's `context_ref`
identifies them. Authority v2 still means the same exact Task/context/scope grant.
Request v3 explicitly carries the typed projection and `context_digest`; historical
request v2/raw context is not accepted at this execution entry point.

`authorize()` rejects plain strings, JSON dictionaries, wrong-Task projections and
projected bytes inconsistent with the grant. `invoke()` requires the separately held
accepted Blaine grant and rechecks its digest, Task, context reference and projected
bytes immediately before its sole provider-call site. Changing both projected
content and its claimed digest/reference cannot change the accepted grant. The
provider receives the projection, without the raw source or the grant handle.

Projection exceptions or invalid outputs raise a safe `ProjectionError`; callers
must stop admission. There is no raw-context fallback. The probe records a generic
failure category without exception text or raw input. Projection receipts in events
contain only projector identity, outcome, digest and artifact reference, with no raw
payload. Future projections may transform content, but no DLP, semantic filtering,
condensation, pseudonymization or context-fidelity behavior is implemented here.

The projector is deterministic. A fresh process can reproduce the same projection
against the persisted grant; a changed output fails the exact-byte check. Native
Restate still journals effects and owns replay. Python types and frozen values
establish the application integration boundary, not a sandbox against malicious
trusted Python code or a dishonest adapter.

## Hard authority

[frontier.py](../../runtime/kernel/frontier.py) defines frozen typed data. Trusted
application code supplies grants; the probe journals the accepted grant in Restate.
There is no model-facing grant/update endpoint. v1 grants are rejected rather than
silently reinterpreted with relaxed guarantees. Historical v1 evidence and source
snapshots remain under the Increment 11 evidence directory.

| Grant field | Meaning |
|---|---|
| `version=2`, `task_id` | One Task's explicit authority |
| `bindings` | Bounded approved bindings: ID, worker family, provider, model, exact destination, locality, capability/quality metadata, optional native controls |
| `frontier_permitted` | Independent Task permission, regardless of suitability |
| `approval_required`, `approval_ref` | Scoped approval established by trusted issuer |
| `context_ref` | Approved Task-owned projected artifact; digest checked against exact outbound bytes |
| `read_scope`, `write_scope` | Bounded literal resource sets; narrowing only |
| `max_dispatches` | Actual worker-attempt slots, not underlying HTTP/model-call limit |
| `deadline_unix`, `max_runtime_ms` | Hard validity/runtime bounds enforced by the binding |
| `required_native_limits` | Optional binding guarantees explicitly required by this Task |

`GlobalGuardrails` represents frontier enable/kill switch and an external account
ceiling status: `not_configured`, `available`, `exhausted`, or `unknown`. Exhausted
or unknown configured status denies frontier use; not-configured does not claim a
ceiling exists. There is no billing API integration. These inputs are trusted
fixtures in the proof; future provider/account monitoring supplies them, not the
worker. The kill switch is checked at admission and immediately before invocation.
This is not yet an out-of-band cancellation service for an already-running worker.

`FrontierProposal` v2 is closed JSON: Task, binding/provider/model/destination,
context reference, narrowed scopes, runtime, optional `usage_hints`. It cannot
contain grant state, approval or dispatch identity. Hints never alter authority.
Selection, context, scopes, approval, deadline, slots and any requested native
controls must pass before the existing Task PolicyGate admits `worker.run`.

The provider receives an immutable authorized request with the authority digest,
`worker_dispatch_id`, selected binding, exact context bytes/ref, narrowed scopes,
deadline/runtime, optional native requirements and clearly soft usage hints. It
receives no approval control or budget handle. A direct raw proposal is rejected.
An observed binding mismatch becomes an unknown outcome, not an authorized result.

Approval references here are synthetic trusted fixtures. A real grant issuer must
verify human approval; a nonempty model-supplied string cannot issue authority.

## Routing suitability

[worker_routing.py](../../runtime/kernel/worker_routing.py) implements a bounded,
provider-neutral `WorkloadClassifier.assess(workload, binding)` seam. The current
scripted classifier compares required capabilities and a quality threshold:

- UNDERPOWERED: required capability/quality is missing.
- JUST_RIGHT: capabilities suffice and quality meets the threshold.
- OVERKILL: capabilities suffice and quality exceeds the threshold.

These are recommendations, not security categories. The router considers adequate,
authorized candidates, prefers a sufficient local binding per ADR 0010, then uses
an explicit ordinal **expected cost-to-success** rank. Ranks are scripted fixture
inputs, not prices, measured reliability or adaptive learning. The rank can favor a
stronger model when its expected total cost-to-success is better. No adequate
authorized candidate returns `STOP_OR_ESCALATE`, with no unauthorized fallback.
The selected binding still requires dispatch authorization against current state.

An OVERKILL worker remains legally admissible when explicitly selected and
otherwise authorized. A future Jev-like classifier could replace the recommendation
without owning grants or changing kernel semantics. Fixture bindings demonstrate
Goose/local Qwen, Codex/economical or strong, and Junie/Claude representations;
none of those workers/models is invoked by this proof.

## Budget and usage semantics

Blaine owns dispatch slots in Restate `frontier-budget`, separately from the
`frontier-accounting` observations. Neither is an observability-derived authority.

- Denied proposal: no provider invocation and no slot/effect mutation.
- Admitted attempt: reserve one worker slot under stable dispatch identity.
- Known executed outcome: settle once, count one completed effect.
- Confirmed non-execution: settle with zero completed effects; retain attempted slot.
- Unknown/timeout: retain pending slot, unknown usage stays unknown, no automatic retry.
- Repeated reservation, settlement or identical accounting identity is idempotent;
  conflicting accounting under the same identity is rejected.

Token/model-call/cost fields survive as optional required provider-native controls,
optional soft hints, and observed usage. They are **not universal per-Task hard
ceilings**. A Task that explicitly requires a native guarantee is denied if its
binding does not support it. Native support is a trusted adapter attestation, not
proof obtained by merely passing a number. An observed violation remains unknown
and cannot become verified success. No pricing is invented.

Accounting records worker/provider/model binding, observed producer/session, usage,
runtime and outcome; final completion/verification joins through Task/dispatch/event
references. Model-call IDs are recorded when available. Missing metrics are `null`,
not zero. Fixture counters and costs are labeled synthetic, never live inference.
Repeated attempts/escalations can be correlated without building a learning system.

## Retry domains and worker-bound context (approved live clarification)

Blaine distinguishes Task/runtime retry, worker-dispatch retry/replacement,
worker-internal model-loop calls, and provider/client transport retries. For the
first live probe, exactly one Blaine-authorized worker dispatch is permitted. Blaine
must not automatically repeat that frontier effect, replace the worker, change
provider/model or escalate. Provider-internal transport retries within that execution
are permitted; unobservable counts are UNKNOWN, never inferred zero. A future Task
may require a stronger binding guarantee, but it is not a universal requirement.

The hard context guarantee ends at the worker-binding boundary: the exact approved
ProjectedContext bytes are delivered there, with no raw-context side channel.
A heterogeneous worker may add system instructions/protocol metadata. Its final
provider/model prompt is UNKNOWN unless actually exposed. A sterile workspace and
restricted context are therefore required for the first live probe. This does not
relax the projection, digest, scope or authority checks.

## Enforcement and recovery limits

This boundary is not a firewall or a sandbox for hostile Python code. A real adapter
must enforce provider/destination binding, filesystem/tool scope, deadline/process
termination and any specifically required native controls. Merely selecting an
installed harness cannot prove those properties. The proof uses a fixed local
synthetic subprocess with a minimal environment, process timeout and no networking
code. All authority denial cases are checked before that process is started.

Native Restate replay after a committed capability result does not execute the
provider again or settle twice. This does not prove exactly-once remote execution
if a process dies before its response is journaled. Live integration still requires
binding-specific idempotency or an explicit unknown-outcome/no-retry strategy for
that window. A failed/denied operation is never counted as a completed effect.

## Observability and independent completion

Existing ExecutionEvent v1 records reference exact artifacts for classification,
candidates, selected recommendation, proposal, authority decision, authorized
request, observed usage and result. These are diagnostic records, not authority.
No event schema change, unrestricted payload dump or credential access is needed.

The isolated proof uses existing `worker.run` and the trusted probe checkpoint.
Production workflow, Task/NextAction contracts, PolicyGate, completion criteria,
verifier, MIRIX, workers and event schema are unchanged. Each proof Task independently
verifies its expected dispatch-report digest. Completing a denial/timeout **test
Task** does not mean frontier work succeeded. JSONL remains an acceptance sink.

The next live proof should authorize **one worker dispatch**, not one model HTTP
request: a visibly transformed synthetic projection/result, approved binding/destination, read-only
scope, short enforced deadline, no automatic worker retry, current guardrails and
observed usage where available. Exact token/dollar controls are required only if
explicitly demanded by that Task. Exact destination, scope enforcement and unknown
outcome handling still need binding-specific preflight. No live call is authorized
by this document, and Increment 12 remains unstarted.
