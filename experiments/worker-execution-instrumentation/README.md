# Worker execution instrumentation and continuation boundary

Live evidence for the [worker execution boundary contract](../../docs/contracts/worker-execution-boundary.md).
The machine-readable result is [evidence/evidence-summary.json](evidence/evidence-summary.json),
regenerated from the retained observations by [summarize.py](summarize.py).

**Zero paid cloud inference calls and zero frontier dispatch grants were consumed.**
Both probes drive real harnesses against the adopted loopback Qwen deployment, so
the Codex agent loop was exercised without a provider-account call.

## What was established

| Question | Answer | Evidence |
| --- | --- | --- |
| Can Blaine observe what model and tool activity occurred at each continuation boundary? | Yes, for the Blaine-owned durable loop and for the Codex app-server stream | both probes |
| Can Blaine synchronously inspect a boundary before the next model continuation? | Yes where it owns the loop; **no** for Codex, which never awaits the client there | kernel probe / Codex capability claim |
| Does a boundary decision survive process death without being recomputed? | Yes: after SIGKILL, zero historical boundaries were recomputed | `kernel-loop/recovery-summary.json` |
| Does telemetry reach a real Collector without the Task depending on it | Yes: 26 spans delivered by OTLP; an unroutable Collector adds no execution latency | `kernel-loop/otlp-delivered-spans.json` |
| Was a semantic supervisor required? | No. A deterministic observer proved the hook; no Jev call was made | `evidence-summary.json` |

## Blaine-owned durable loop

`probe_kernel.py` starts an isolated Restate server, the real `CognitiveTaskV1`
workflow, real local Qwen cognition, a deterministic synchronous boundary observer
and a real OTLP exporter aimed at the native Collector. It owns its own ports,
state directory and processes; the adopted long-lived services are untouched.

Three live Tasks ran:

- `boundary-live-001` — COMPLETED with both exact artifacts. SIGKILL landed after
  the second boundary admission was journaled. The replacement process consulted
  the observer **zero** additional times: `historical_boundaries_recomputed` is
  empty and only one process id ever appears in
  [recovery-observer-calls.jsonl](evidence/kernel-loop/recovery-observer-calls.jsonl).
  The journal contains `continuation/1` and `continuation/2`.
- `boundary-delivery-001` — COMPLETED with a clean shutdown flush. The exported
  spans show the causal order per continuation: `boundary_control` →
  `chat <model>` → `execute_tool artifact.write` → `blaine.verifier`, all carrying
  the same `blaine.task_id` and `blaine.run_id`, with real token usage
  (2238/131 and 2639/73) and `finish_reasons` of `stop`.
- `boundary-delivery-002` — **FAILED**, and retained deliberately. The local model
  returned non-JSON at the second continuation and the pre-existing validator
  rejected it three times, so the Task failed with a truthful concern. This is
  existing local-model behavior, not an instrumentation regression, and it shows
  retry visibility: three `model_invocation` spans share one continuation index.

Two findings are recorded because they are real, not because they are convenient:

- **Buffered telemetry is lost on SIGKILL.** The killed process's spans never
  reached the Collector, while its journaled ExecutionEvents and the Task outcome
  were unaffected. That is the intended asymmetry between the two paths.
- **A durable at-least-once retry duplicates a physical span.** Two
  `tool_execution` spans exist for the single `capability_call_id`
  `boundary-live-001/2`. The content-addressed artifact write is idempotent, the
  Task completed correctly, and the journaled ledger still records one logical
  `capability.finished` per call. Spans are attempts; events are observations.

## Codex app-server

`probe_codex.py` drives the installed Codex CLI 0.155.1 app-server over stdio and
feeds the recorded conversation through [codex_appserver.py](codex_appserver.py),
which maps the protocol onto continuation boundaries. Codex keeps its own thread
and turn lifecycle; nothing reconstructs its agent loop inside Blaine.

Protocol facts were taken from `codex app-server generate-json-schema` on the
installed binary and confirmed by live execution:

| Observation | Result |
| --- | --- |
| Boundary marker | `thread/tokenUsage/updated`, emitted exactly once per model invocation, carrying that invocation's own token breakdown in `tokenUsage.last` |
| Boundary counts | 3 boundaries / 3 model invocations / 2 tool calls in the multi-tool case; 2/2/1 in the steering case |
| Tool observation | `item/started` and `item/completed` with status, exit code and duration |
| Steering | `turn/steer` accepted in 0.4 ms while a tool was running, then consumed 0.4 ms **after** the next boundary marker, at boundary index 1 |
| Interruption | `turn/interrupt` ended the turn as `interrupted`; the in-flight tool item received **no** terminal event and is reported as `unterminated` |
| Synchronous callback | The approval `ServerRequest` genuinely blocks: a deliberate 3000 ms client delay held the turn with `activeFlags: ["waitingOnApproval"]`, and the turn still completed afterwards |
| Model / effort rebinding | `turn/start` only, so both are `agent_turn` granularity; no mid-turn rebinding exists |
| Synchronous continuation admission | **UNSUPPORTED.** The boundary marker is a notification; Codex does not wait for the client there. The only blocking callback is tool approval, which happens *before* a tool runs, not before the next model continuation |

Boundary, model-invocation and tool counts are observations of the recorded runs,
not invariants: a re-run of the multi-tool case produced 2 boundaries and 2 tool
calls because the model grouped both calls into fewer continuations. The invariant
is the one-to-one relationship between the boundary marker and a model invocation,
not any particular count.

The last row is the increment's negative result, and it is declared as an
`UNSUPPORTED` capability rather than emulated. A blocking tool-admission callback
is a useful control point, but it is not a continuation-boundary admission, and
the profile does not let calling code treat it as one.

## Reproduction

Both probes need the adopted loopback serving endpoint on `127.0.0.1:8000`.
The Codex probe additionally needs the installed CLI; the kernel probe needs the
`restate-server` binary and free ports 41070, 41080, 41090 and 41122.

```sh
python3 experiments/worker-execution-instrumentation/probe_codex.py --output /tmp/codex-boundary
python3 experiments/worker-execution-instrumentation/probe_kernel.py --output /tmp/kernel-boundary
python3 experiments/worker-execution-instrumentation/probe_kernel.py \
    --output /tmp/kernel-delivery --task boundary-delivery-003 --no-recovery
python3 experiments/worker-execution-instrumentation/summarize.py
```

Offline controls, which start no harness and perform no inference:

```sh
PYTHONPATH=.:tests python3 -m unittest discover -s tests
```

## Retained evidence

- [evidence-summary.json](evidence/evidence-summary.json) — machine-readable result
- [codex-app-server/](evidence/codex-app-server/) — normalized observations per case and the declared capability profile
- [kernel-loop/](evidence/kernel-loop/) — recovery, delivery and retry summaries, observer consultations, the journaled event ledger, model audit records and the spans the Collector actually received

Observations retain metadata, identities, digests, counters and statuses only.
No command text, model output, reasoning, prompt or environment value is kept, and
no secret is read or emitted. The Codex probe uses a private throwaway `CODEX_HOME`
so the user's own thread history is not modified.

## Boundary of this result

This is an instrumentation and capability-evidence increment. It does not adopt a
Codex worker binding, register a new deployment, change the adopted services,
implement a supervisor, or claim any roadmap workstream status. Capability claims
apply to the exact CLI version and protocol observed here and must be revalidated
on upgrade.
