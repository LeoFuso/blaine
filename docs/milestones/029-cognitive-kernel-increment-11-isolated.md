# Increment 11 — isolated frontier authority proof

**Status:** PASSED (isolated only). STOP before real frontier inference.
**Date:** 2026-09-20.

## Hypothesis and implementation

Explicit Blaine-owned grants and durable budget state can enforce frontier
selection, egress and resource limits while the model/worker/provider remains
unable to authorize itself. See the [exact authority contract](../contracts/frontier-dispatch.md).

Added a small typed `runtime/kernel/frontier.py` boundary. The controlled synthetic
provider records immutable authorized requests and performs no network calls.
Existing `worker.run` and the trusted experimental checkpoint supply proof wiring;
no production kernel, Task contract, PolicyGate, verifier, lifecycle or
ExecutionEvent schema changed. No cloud provider adapter was enabled.

## Gate results

**96 focused tests pass** (87 baseline). Fourteen native Restate proof Tasks passed
independent artifact completion and offline journal/event verification:

- Authorized selection: one exact approved request reached the provider.
- Disabled cloud, wrong provider/model, wrong destination, exhausted budget,
  read/write escalation, missing approval, expired deadline and excessive runtime:
  rejected before provider execution.
- Second dispatch in one Task: first executed; second denied by exhausted allowance.
- Confirmed non-execution: no effect/token/cost charge, one invocation attempt.
- Process timeout: child process stopped; outcome unknown; reservation held; no retry.

Four synthetic provider invocations occurred: two executed results, one confirmed
non-execution and one timeout. Zero cloud/model inference calls. Synthetic results
are enforcement evidence only.

**Recovery:** SIGKILL after the authorized capability result was journaled, before
budget settlement. Replacement reconstructed the same accepted authority and held
reservation. The committed provider operation was not executed again; settlement
occurred once. Server journal SetState records independently establish budget and
authority persistence. This does not prove an uncommitted remote-response-loss window.

**Observability:** 247 valid ExecutionEvent v1 records. Exact policy artifacts
provide admitted/denied reason categories and authorized request identity. Provider
records match admitted requests. Existing completion verification remains independent.
The offline verifier was adjusted to decode Restate's observed void Run result
(`Success: []`) for audit-only callbacks; no acceptance criterion changed.

## Evidence

- [Summary](../../experiments/kernel-increment-11/evidence/summary.json)
- [Independent verification](../../experiments/kernel-increment-11/evidence/acceptance/verification.json)
- [Events](../../experiments/kernel-increment-11/evidence/acceptance/events.jsonl)
- [Provider requests](../../experiments/kernel-increment-11/evidence/acceptance/provider-calls.jsonl)
- [Authority integrity](../../experiments/kernel-increment-11/evidence/authority-integrity.json)
- [Tests](../../experiments/kernel-increment-11/evidence/focused-tests.txt)
- [Real-binding readiness](../../experiments/kernel-increment-11/evidence/readiness.json)

Reproduce with the existing runtime Python:
`experiments/kernel-increment-11/probe.py --output <fresh-dir> --restate-server <existing-binary>`;
then `experiments/kernel-increment-11/verify.py <fresh-dir>/evidence`.
All isolated probe processes were stopped. No installation, secret read, credential
mutation, serving change, real provider request or Increment 12 work occurred.

## Required stop and next human decision

Codex CLI 0.155.1 is installed; selected non-secret user configuration says
`model = "gpt-6-astra"`. Local CLI help supports per-run model/config overrides,
read-only sandbox and ephemeral operation. Authentication mode and actual provider
destination were not inspected or inferred from credentials. This is a candidate
harness, not a verified executable frontier adapter.

Official [configuration precedence](https://developers.openai.com/es-419/docs/config-file/config-basic)
supports invocation overrides; [provider configuration](https://developers.openai.com/es-419/docs/config-file/config-advanced)
separately exposes endpoint/retry controls. Those controls alone do not establish
one model request, total token/cost enforcement, all auxiliary destinations or safe
retry behavior for this installed harness. Live readiness remains UNVERIFIED.

Before one real call, the human must approve the exact Task, harness/provider/model,
actual destination, exact context artifact digest, read/write scope, invocation and
effect count, token/cost ceilings, deadline/runtime limit and scoped approval.
A narrowly bound adapter must demonstrate those limits; installing Codex or granting
permission does not supply enforcement. Do not assume the Codex CLI is a one-request
API transport.

Safest candidate first workload: a public synthetic text packet only, no repository
reads/writes or tools, one authorized attempt, no automatic retries, exact-response
verification. The actual destination and numeric ceilings remain explicit human
inputs. No draft here is an issued grant. **STOPPED; Increment 12 has not started.**
