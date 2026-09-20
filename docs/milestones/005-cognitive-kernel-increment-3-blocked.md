# Increment 3 — Local model gate BLOCKED

**2026-09-19 · Stop report · No model adapter implemented**

Hypothesis: the already-running shared Qwen can receive the existing bounded
CognitiveTurn and emit structured CognitiveDecision without changing lifecycle,
dispatch, authority or completion. No second model instance, dependency install,
secret change or vLLM reconfiguration is permitted.

**EXPECTED:** the shared Qwen/vLLM endpoint documented in the
[MIRIX carveout](../research/mirix-carveout.md) is available at
`http://127.0.0.1:8000/v1`.

**OBSERVED:** a read-only `GET /v1/models`, bypassing proxies with a five-second
timeout and permitted local network access, failed immediately with
`Connection refused` / `ECONNREFUSED (111)`. This is an actual local connection
refusal, not a filesystem/network sandbox permission error. No model request was
sent. The cause of the service's absence has not been investigated or inferred.

**IMPACT:** real-model probes cannot run; this hard gate is BLOCKED. No adapter,
model tuning, service start, installation, host change or secret mutation was
attempted. Increments 4–12 remain NOT STARTED. This is an external availability
blocker, not a failure of the loop architecture.

**ARCHITECTURE IMPACT: None.** Increment 2 remains validated and executable with
scripted cognition, one independently durable joined child, bounded result,
policy enforcement and independent completion. Its 27 tests and the seven
Increment 1 live regression scenarios passed before this gate was opened.

**SMALLEST NEXT DECISION REQUIRED:** provide the correct already-running shared
Qwen endpoint, or restore the existing shared service through its existing
infrastructure workflow. Then authorize/resume Increment 3 from this checkpoint.
Do not install or start a second Qwen instance to bypass this gate.

Evidence:
[availability.json](../../experiments/kernel-increment-3/evidence/availability.json),
[summary.json](../../experiments/kernel-increment-3/evidence/summary.json).

## Resume contract

Read [progress](cognitive-kernel-progress.md) and the
[Increment 2 milestone](004-cognitive-kernel-increment-2.md); do not repeat the
architecture investigation. Recheck the supplied/shared endpoint first. If
available, use the same `CognitiveAdapter` and bounded input, prefer constrained
JSON, validate before effects, and keep tools/state mutation out of cognition.
Retain actual context sizes and model token usage where available.

The gate requires: model chooses at least two legitimate actions from evidence;
malformed/unknown output is rejected before effects; premature COMPLETE is
rejected; a forbidden model-requested effect is denied; scripted and real-model
adapters use the same loop unchanged. Retain focused tests and live machine-readable
evidence; check earlier regressions; document the gate before proceeding to MIRIX.
No inference infrastructure tuning is included.
