# Increment 7 — local worker binding BLOCKED

Historical authorization blocker resolved by the user's per-run binding approval.
The subsequent [binding probe](014-cognitive-kernel-increment-7-binding-stop.md)
proved the main local inference route but stopped on incomplete auxiliary capture.

Increments 5 and 6 passed their gates. The next bounded hypothesis is that a fresh
replaceable worker can receive selected context, emit exact artifacts, survive
interruption through durable Task state, and leave completion to the verifier.

## STOP REPORT

- **Expected:** use an already-working local harness with the existing permitted
  Qwen service, without new installation, global configuration or cloud inference.
- **Observed:** Goose 1.50.1 is installed, but its persisted provider is `ollama`,
  `OLLAMA_HOST=localhost`, model `qwen3.6:35b-a3b`. It is not the validated shared
  `Qwen/Qwen3.5-9B` vLLM binding. Codex is installed but selects `gpt-6-astra` and
  has no configured local model provider. CLI availability does not establish a
  working permitted inference binding. No harness execution was attempted.
- **Architecture impact:** none. No worker adapter, kernel, contracts, serving
  configuration or secrets were changed for this increment.
- **Attempted:** read existing harness research, executable availability, Goose
  version/help and only non-secret provider-selection fields from existing configs.
  Goose help emitted a sandbox logging-directory warning; no escalation or host
  changes were made to resolve it. No inference, installation or model startup.
- **Unresolved question:** which permitted local worker binding should execute?
- **Exact human decision required:** authorize a narrowly isolated, per-run Goose
  OpenAI-compatible binding to the existing shared Qwen endpoint, or supply an
  already-working permitted local harness binding. Do not change global defaults.
- **Safest next option:** validate that binding alone, then resume Increment 7's
  bounded packet, excluded sentinel, exact artifacts, interruption/replacement
  and independent completion probes. Do not use the configured alternative model
  or cloud provider just to satisfy the gate.

This follows the explicit mandatory STOP for materially different serving
assumptions. It is not evidence that Goose is incapable of using vLLM. That would
require a separately authorized bounded binding test, not a model-quality audit.

[Machine-readable evidence](../../experiments/kernel-increment-7/evidence/summary.json).
Next increment remains **7**. Increments 8–12 were not started.
