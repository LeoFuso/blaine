# Increment 11 — second authorized live frontier probe

**2026-09-20 — PASS / CLOSED. Increment 12 has not started.**

Exactly one new Blaine-authorized worker dispatch completed through the existing
projection, authority, reservation, Codex binding, artifact admission and independent
CompletionVerifier paths. This is a synthetic binding proof, not model-quality or
production-workload evidence. No further cloud execution is authorized by this report.

## Preflight and authority

Task `frontier-live-binding-002`; worker dispatch
`dispatch:frontier-live-binding-002/2`. The fresh output directory, authority,
Task-scoped artifact references, reservation and exclusive fsynced receipt are
independent of the historical `001` execution. Approval reference:
`human-authorized-frontier-live-binding-002`.

The installed executable reports Codex CLI 0.155.1; binary/config hashes match the
accepted preflight. Configured intent is `gpt-6-astra`, built-in OpenAI provider with
existing ChatGPT authentication, service trust boundary `https://chatgpt.com`.
No credential value was inspected. Effective served account/model, precise internal
endpoint and final provider prompt remain UNKNOWN; the binding/config evidence does
not establish those hidden identities.

A network-disabled preflight checked the same isolated mount layout and empty
`/probe`. The live worker had no repository checkout, private documents, personal
instructions/skills or unrelated Task context. Its sandbox is read-only, tools are
not requested, and existing task-specific instructions prohibit exploration and
follow-up work. Only existing CLI authentication is mounted for authentication,
never included in Task context. No global configuration was changed.

Hard authority admits only the pinned binding, projected-context read scope, empty
write scope, one worker dispatch and a 60,000 ms runtime bound. Existing cancellation,
kill switch, process-group termination, Restate reservation and exclusive receipt
remain active. Blaine performed no retry, fallback, replacement or escalation.
Internal provider retries/model-loop calls remain UNKNOWN and are not worker dispatches.

## Exact context boundary

Raw synthetic controller input: `{"marker":"7319","organization":"ORCHID"}`.
Projector `synthetic-live-v1`, projection version 1, produces these exact UTF-8
bytes, without a trailing newline:

```json
{"marker":"MASKED_01","organization":"FLOWER"}
```

Projected context SHA-256:
`e4dfa3217256de41f4b4036aa046161b727f3db8b6efbfbde5da09ea4f17f183`.
Authority digest:
`3a3d5538d4843efccf7a489f409134cc1be82ad23c2382536bd05b358cf5e22c`.

The verifier checked the exact worker stdin against AuthorizedFrontierRequest's
projected content, digest and Task-scoped context reference, then checked the
request's authority digest against the actual grant. Raw values occur only in the
trusted synthetic fixture, not worker stdin or ExecutionEvent payloads. No assertion
is made about Codex's unobservable final internal provider prompt.

## Observed worker stream and result

| Sequence | Upstream event | Binding classification |
|---|---|---|
| 1 | `thread.started` | Session identity |
| 2 | `item.completed`, `error`, `item_0` | Non-terminal diagnostic |
| 3 | `turn.started` | Progress |
| 4 | `item.completed`, `agent_message`, `item_1` | Result content |
| 5 | `turn.completed` | Explicit terminal success |

Session: `01a0bfba-f2f9-7ec1-9d45-6ea9c0c39ca4`. Observation v2 uses the unchanged
`codex-exec/rust-v0.155.1` semantics. There was no terminal failure, contradictory
state, unsupported event or rejection. The diagnostic records ordering, item
identity, non-terminal classification and message presence/214 UTF-8 bytes. Arbitrary
message text is intentionally omitted under the existing structure-only policy;
its human-readable root cause remains UNKNOWN. It was not interpreted as authority.

Normalized output equals the projected JSON above. The existing capability admitted
`artifact://frontier-live-binding-002/sha256:e4dfa3217256de41f4b4036aa046161b727f3db8b6efbfbde5da09ea4f17f183`.
The unchanged CompletionVerifier independently verified its exact digest: SATISFIED.
Task lifecycle is COMPLETED at iteration 2. The existing successful dispatch settlement
ran once: dispatches 1, completed effects 1, settled 1, pending 0; accounting has one
entry. Successful worker settlement did not substitute for completion verification.

Observed CLI usage: 5,112 input tokens, 23 output tokens, 0 cached input tokens;
worker duration 4,702 ms. These are observed accounting, not enforced token ceilings.
Model-call count, internal retry count, monetary cost, served model/account and final
provider prompt remain UNKNOWN. One Blaine dispatch is not claimed to be one model call.

## Evidence and validation

[Evidence directory](../../experiments/kernel-increment-11/evidence/live-authorized-002/):
`preflight.json`, `summary.json`, immutable `acceptance/` records including exact
stdin, grant/request, receipt, worker observation/result, native Restate journal,
Task state/result, artifacts, independent verification and 18 valid ExecutionEvents.
Events plus referenced evidence and the correlated worker observation reconstruct
projection, admission, reservation, effect, artifact, verification and settlement.
No raw provider stream/free-text stderr is retained. Temporary service data/logs
remain outside Git; the exported journal/artifacts are the reproducible evidence.

Offline checks: 114 kernel tests, including 27 frontier tests; 12 standalone Codex
characterization tests. Independent verifiers: Increment 10 PASS (28 events), frontier
projection PASS (434 events), historical live 001 STOP/FAILED (74 events), live 002
PASS/COMPLETED (18 events). `git diff --check` passes. All prior Increment 11 evidence,
kernel source and the corrected binding match pre-probe hashes; milestones 033–035
remain byte-identical. No destructive live replay was attempted. Existing isolated
replay controls, native journal and one-shot receipt were retained.

Only the probe CLI was parameterized with an explicit Task identity propagated to
its server process and a Task-specific approval reference. No Codex normalization,
Task lifecycle, PolicyGate, CompletionContract/Verifier, projection, authorization,
reservation, routing or retry semantics changed.

The historical `frontier-live-binding-001` remains FAILED with its pending UNKNOWN
reservation. This new PASS neither repairs nor retroactively completes it.

**Increment 11 is CLOSED.** Stop here. Increment 12 requires a separate continuation;
no parallel Task work or further live dispatch was performed.
