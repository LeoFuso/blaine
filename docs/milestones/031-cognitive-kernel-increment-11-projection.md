# Increment 11 — mandatory frontier context projection

**2026-09-20 — PASS, isolated proof. STOP before any live frontier call.**

Hypothesis: every frontier dispatch can require a Blaine-produced projection before
exact-context authorization, without changing lifecycle, policy authority, economic
routing, accounting or replay. This gate tests traversal/binding, not context quality.

## Implementation

[frontier_context.py](../../runtime/kernel/frontier_context.py) adds a small
`FrontierContextProjector.project(resolved)` protocol and a factory issuing frozen
`ProjectedContext` v1 values. The production identity implementation is explicit and
provides no sanitization. Projection strategy is selected by trusted Blaine code.

The pipeline is `resolved → project → SHA-256/projected artifact → grant → authorize
→ dispatch-time recheck → adapter`. The digest covers exact outbound UTF-8 content,
not raw input or its JSON envelope. Existing `FrontierAuthority` v2 is unchanged.
`AuthorizedFrontierRequest` advances to v3 to carry the typed context plus explicit
`context_digest`; old raw-request v2 cannot enter the adapter path. Scope, approval,
provider/model/destination and all existing grant semantics remain in force.

`authorize` accepts only a factory-produced projection matching the Task and granted
artifact. Plain strings/dicts cannot stand in for it. `invoke` compares the projection
and reference against the separately held accepted grant before entering the adapter.
Even replacing content, digest and reference together is rejected. Projection error
or malformed output stops admission without raw fallback, provider invocation or
completed-effect accounting. Error text does not carry raw input into telemetry.

The boundary is structural application enforcement, not protection against arbitrary
malicious Python or a malicious adapter. The sole current frontier provider-call site
is recorded in [dispatch inventory](../../experiments/kernel-increment-11/evidence/projection/dispatch-paths.json).
No installed harness or live frontier path was enabled.

## Acceptance and retained evidence

Baseline 98 focused tests passed. Revised suite: **103 passed**. Existing native
proof extended from 19 to **22 Tasks**; **434 ExecutionEvents** independently validated.
Four fixed local synthetic provider invocations, zero live inference/cloud calls.
All earlier A–J authority/routing/accounting checks passed alongside A–F below.

Fictional equivalents for this maintained description (not the archived bytes):

Synthetic input: `organization=ORCHID; marker=RAW_SECRET_7319`.
Synthetic output: `organization=FLOWER; marker=MASKED_7319`.
No real secret is present. Replacement logic exists only in test/probe fixtures.

Historical projected UTF-8 SHA-256 (for the unchanged archived artifact, not
the fictional equivalents above):
`c3131651074f4fc72d640b9ebd24d27336596449a4255c89571d1cf1435636d9`.

| Gate | Independently checked evidence |
|---|---|
| A mandatory component | All 23 dispatch proposals have projection outcome records before policy records; authorization requires typed projection |
| B adapter input | Every recorded provider request contains exactly the transformed fixture, never the raw values |
| C exact digest | Request context digest = SHA-256(projected bytes) = grant artifact digest; differs from raw digest |
| D substitution | Replacing projected content, digest and reference after admission returns `context_authorization_mismatch`; provider count zero |
| E projection failure | Failed projector produces generic failure; no admitted request, reservation or provider call; malformed output also rejected in unit control |
| F telemetry | No raw fixture value in any event or its referenced payload; projection metadata contains identity/digest/ref only |

Additional unit controls reject wrong-Task projection, raw/dict bypass, authority
bound to raw instead of projected bytes, altered digest, altered authority digest,
and invalid projection output. Identity projection is tested explicitly, including
non-ASCII exact UTF-8 bytes. Projection quality is not evaluated.

Native recovery killed runtime PID 300583 after a committed synthetic worker effect
and before settlement. Replacement PID 300680 reconstructed execution from the same
Task/grant/journal. The projection reference and committed capability result matched
before/after restart. The provider executed once; settlement/accounting occurred once.
Unknown timeout still holds its slot without retry. Substitution is a confirmed
non-execution: one attempted slot settles, zero completed provider effects.

All proof Tasks independently verified their expected report digests. A denial-test
Task completing does not mean denied frontier work executed. Synthetic model-call
usage counters are fixtures inherited from the prior proof, not live inference.

- [Machine-readable summary](../../experiments/kernel-increment-11/evidence/projection/summary.json)
- [Independent verification](../../experiments/kernel-increment-11/evidence/projection/acceptance/verification.json)
- [Projection outcomes](../../experiments/kernel-increment-11/evidence/projection/acceptance/projection.jsonl)
- [Provider requests](../../experiments/kernel-increment-11/evidence/projection/acceptance/provider-calls.jsonl)
- [ExecutionEvents](../../experiments/kernel-increment-11/evidence/projection/acceptance/events.jsonl)
- [Focused test results](../../experiments/kernel-increment-11/evidence/projection/focused-tests.txt)
- [Unchanged boundary hashes](../../experiments/kernel-increment-11/evidence/projection/integrity.json)

The raw fixture is retained only as explicit synthetic test setup in `fixtures.json`
and the summary; it is absent from telemetry and provider requests. These fixtures
must not be repurposed to capture real secrets. Exact projected artifacts use the
existing artifact store; no parallel knowledge store was introduced.

## Reproduction and unchanged architecture

Use the same three commands as milestone 030 with a fresh `/tmp` output directory.
Current `probe.py` includes the projection controls; `verify.py` checks both the new
projection gate and previous A–J evidence. Prior source snapshots and evidence are
retained without retroactive reinterpretation.

Changes are limited to new `frontier_context.py`, frontier admission/dispatch context
checks, frontier tests, probe/verifier, contract documentation and progress index.
Hash evidence confirms workflow, contracts, execution/PolicyGate/CompletionVerifier,
events, model adapter, human decisions, memory, worker and economic router unchanged.
No inference service, credentials, environment settings or infrastructure changed.
No context transformation algorithm, DLP or quality model was implemented.

## Smallest proposed live probe — NOT EXECUTED

After explicit authorization and binding-specific preflight, execute one read-only
worker dispatch with a tiny synthetic artifact: probe ID, ORCHID/7319, and the fixture
organization/marker. The deterministic fixture projector visibly changes ORCHID /
RAW_SECRET_7319 to FLOWER / MASKED_7319 before any grant is issued. Authorize
only that projected artifact/digest. The bounded result contract should require the
probe ID, word, number and projected organization/marker; an independent verifier
checks them. Capture the dispatched projection digest and usage where observable.

Retain exact approved binding/destination, scope, short enforced deadline, no worker
retry, current guardrails and replay/unknown-outcome handling. Multiple underlying
model calls remain possible within one worker dispatch. This proposal does not prove
live egress, context fidelity or provider-native enforcement and is not authorization
to execute. **STOP here; Increment 12 remains unstarted.**
