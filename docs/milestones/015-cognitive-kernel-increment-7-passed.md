# Increment 7 — bounded Goose worker PASS

The authorized auxiliary diagnostic completed one tiny run. No supported per-run
title-disable setting was established from CLI help and targeted installed
metadata. Streaming capture identified two requests: main worker and background
title. Both used `http://127.0.0.1:8000/v1/chat/completions`, requested and returned
`Qwen/Qwen3.5-9B`. The main stream completed; the title client disconnected before
completion. The user's explicit option B permits progression with this known
observability limitation. Auxiliary request counts are separate; missing token
usage is UNKNOWN, never zero. No further auxiliary diagnostic was run.

## Executable boundary

`worker.run` accepts an admitted exact WorkerInput artifact reference and output
artifact name. The versioned bounded packet selects objective/context for a Task;
it does not forward cognitive history. An injected worker callable executes it.
`GooseWorker` is one replaceable adapter: local OpenAI-compatible provider/model,
fresh temporary root/session, no extensions/tools, no global configuration or
credentials. Output is text only. Terminal whitespace is removed explicitly;
the raw public stdout and normalization rule are retained in worker evidence.
No private reasoning is retained.

Policy admits the capability and packet reference. The dispatcher retains exact
worker receipt/output artifacts. Worker exit success is not Task success: only
the existing completion verifier accepts the exact Task evidence. The loop,
workflow, TaskResult and completion rules are unchanged. This demonstrates a
text-only external worker, not unrestricted filesystem or shell work.

## Live acceptance

- One durable Task, six scripted cognitive turns, two real Goose processes.
- Each worker receives the same 332-byte selected packet. Deliberately excluded
  Task sentinel is absent from every captured main and auxiliary request. No
  model tools are exposed; temporary cwd/config excludes repository/history.
- First worker is SIGKILLed after sending its main request to an experiment-only
  barrier, before that main request is forwarded to inference. Its interruption
  becomes an observation; premature COMPLETE remains unsatisfied.
- Runtime and Restate server are each SIGKILLed while the Task waits for a fresh
  worker. Same Task/state/packet refs recover; journal prefixes match exactly.
- Replacement Goose process uses a new attempt ID and isolated root, receives
  the retained packet and produces `ALPHA|BETA|UNKNOWN`. Exact artifact verifier
  establishes Task completion. No session/history recovery is required.
- Two outbound main requests (one intentionally not forwarded), two auxiliary
  title requests; response-model evidence confirms the authorized local model.
  The capture proxy rejects other destinations, models and tool-bearing requests.
- 36 focused tests pass, including prior contracts and a control where worker
  success returns wrong bytes and completion remains unsatisfied.

[Acceptance summary](../../experiments/kernel-increment-7/evidence/acceptance/summary.json),
[worker packets/results](../../experiments/kernel-increment-7/evidence/acceptance/workers.jsonl),
[outbound accounting](../../experiments/kernel-increment-7/evidence/acceptance/network.jsonl),
[binding diagnostic](../../experiments/kernel-increment-7/evidence/auxiliary-diagnostic/binding.json),
[replay verification](../../experiments/kernel-increment-7/evidence/acceptance/replay-verification.json).

Changed: new worker adapter/packet validation; capability admission/dispatch and
schema guidance; focused tests, live probe and capture helper. No global Goose,
Ollama, shared model serving or secret configuration changed. No cloud inference.
Architecture deviations: none. Auxiliary accounting limitation explicitly accepted
by the user; this is not a complete token-cost measurement.

Gate passed. Exact next increment: **8**, existing Spec Kit procedure guidance
as bounded cognitive context, with no runtime thought-phase state machine.
