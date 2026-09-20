# Increment 11 — first live frontier probe preflight STOP

**2026-09-20 — STOP before the live worker. Isolated Increment 11 remains PASSED.**

The user authorized one projected-context synthetic cloud execution, conditioned on
preflight, no automatic retry/escalation, strict scope and independent completion.
This record does not revoke that intent or claim a provider execution occurred.

## Expected / observed

Expected: installed Codex, intended model `gpt-6-astra`, projected synthetic values
only, one worker dispatch, no automatic retry/escalation, existing grant/reservation
path, runtime deadline, verified result and Task COMPLETED.

Observed: local CLI is 0.155.1. Its redacted doctor report, run with networking
disabled, identifies `openai` / OpenAI, stored ChatGPT authentication, Responses,
and inference origin `https://chatgpt.com` (WebSocket origin `wss://chatgpt.com`).
The diagnostic redacts the path after `/backend-api/`; exact path, account identity
and server-resolved model remain UNKNOWN. No credential values were inspected.
The initial root configuration had no explicit provider/base-endpoint override.

A temporary invocation-only configuration attempted to disable shell/unified exec,
web search, personal context and provider retries, in a filesystem without the
repository, global skills or personal MCP configuration. Existing auth was mounted
read-only for the CLI; the agent did not open or print it. No persisted/global
configuration changed. Bubblewrap disabled all network access for these diagnostics.

The installed CLI rejected:

```text
model_providers contains reserved built-in provider IDs: `openai`.
Built-in providers cannot be overridden.
```

Thus the proposed zero-retry settings for the built-in binding were not applied,
and exact model-visible prompt rendering did not finish. This is evidence of an
unsupported preflight configuration, not evidence of a model failure or an observed
live retry. We did not replace the provider with a custom one to bypass the error.
The earlier offline `--strict-config` rejection for `debug` was corrected locally;
the provider override rejection is the remaining blocker.

The [official configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference)
documents provider-specific request/stream retry controls. That alone does not
establish an effective zero-retry setting for this installed built-in binding.
Effective retry behavior therefore remains UNVERIFIED. One worker dispatch remains
distinct from its internal model requests; this STOP follows the current explicit
no-automatic-retry condition, not the superseded universal token/cost ceiling.

## Result and authority

- Intended Task: `frontier-live-binding-001`; **NOT_SUBMITTED**, no runtime ID.
- Raw intended synthetic values: ORCHID / 7319.
- Projected intended values: FLOWER / MASKED_01; only these were supplied to the
  offline prompt-debug command. No live artifact/grant/digest was issued.
- Live worker dispatches and model inference calls: **0**.
- Reservation, settlement, worker session, provider result: **none**.
- CompletionVerifier: **NOT_RUN**; no COMPLETED/FAILED runtime state fabricated.
- Tokens, cost and hidden provider internals: **UNKNOWN / not observed**.
- ExecutionEvents: none; Task dispatch never started. Preflight evidence is separate
  from runtime events and is not manufactured as a Task history.
- No retry, fallback, escalation, second live call or Increment 12 occurred.

No production source, contracts, policy, projection, accounting or lifecycle was
changed. [Integrity evidence](../../experiments/kernel-increment-11/evidence/live/integrity.json)
compares current source with the accepted projection proof. Previous isolated
103-test / 22-case evidence remains valid for that scope; it is not live evidence.

## Evidence and exact next decision

- [Preflight report](../../experiments/kernel-increment-11/evidence/live/preflight.json)
- [Selected redacted doctor metadata](../../experiments/kernel-increment-11/evidence/live/doctor-safe.json)
- [Rejected invocation-only configuration](../../experiments/kernel-increment-11/evidence/live/offline-config.toml)
- [Offline command and isolation](../../experiments/kernel-increment-11/evidence/live/offline-command.json)

Architecture impact: **None**. The current binding precondition is unverified.

Smallest next decision: authorize a narrow offline investigation of a supported
zero-retry Codex binding, or explicitly clarify whether bounded native transport
retries within a single worker dispatch are acceptable. Do not silently reinterpret
the one-shot rule. Safest option: keep the live dispatch blocked, establish the
supported binding, then render its exact synthetic-only input offline before any
provider invocation. No new cloud permission is inferred from this STOP report.
