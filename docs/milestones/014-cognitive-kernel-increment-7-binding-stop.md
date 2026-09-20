# Increment 7 — main Goose binding proven; auxiliary capture BLOCKED

Historical stop resolved by the user-authorized narrow auxiliary diagnostic and
option B. See [Increment 7 PASS](015-cognitive-kernel-increment-7-passed.md).

The user authorized invocation-scoped Goose configuration for the shared local
Qwen service. No repository or Task changes were made during the binding probes;
both ran entirely under `/tmp`. This record/evidence was retained after stopping.

Local help established `--provider`, `--model`, `--no-profile`, `--no-session` and
`--max-turns`. Embedded installed-provider strings identified `OPENAI_HOST` and
`GOOSE_PATH_ROOT`. A non-inference `goose info` invocation confirmed that the root
override isolates config, sessions and logs. No global defaults were modified.

## Proven

Goose 1.50.1 ran with CLI provider `openai`, model `Qwen/Qwen3.5-9B`,
`OPENAI_HOST=http://127.0.0.1:8000`, `GOOSE_PATH_ROOT` under `/tmp`, disabled keyring
and telemetry, and a non-secret invocation-only `OPENAI_API_KEY=EMPTY` placeholder.
The default provider path generated `/v1/chat/completions`. A temporary capture
proxy forwarded only HTTP requests addressed to `127.0.0.1:8000`; it did not run
a model or change vLLM. Exact command/environment are in each binding artifact.

In both attempts, the main request reached that endpoint, requested and received
`Qwen/Qwen3.5-9B`, and returned `BINDING_OK` with HTTP 200. Goose exited zero.
The global Goose configuration hash was identical before and after each run;
the existing Ollama selection was untouched. No cloud or alternative harness ran.
Captured response data excludes reasoning fields and private chain-of-thought.

## STOP REPORT

- **Expected:** complete provider/model provenance for the minimal binding probe,
  then start worker acceptance without unexplained behavior.
- **Observed:** despite `--no-session`, Goose also sends a conversation-title
  generation request. Its URL and requested model match the authorized local
  binding, but its response was not captured before the recorder ended. The main
  call is verified; the auxiliary response/completion remains UNKNOWN.
- **Attempted:** one probe, then one local recorder correction to wait up to 20
  seconds for pending capture after Goose exits. The second capture still lacks
  an auxiliary response. No prompt/model tuning or serving changes were attempted.
- **Evidence limitation:** the capture proxy buffers a complete upstream response
  before retaining sanitized metadata. Missing capture completion alone does not
  establish whether this is upstream delay, stream/framing behavior or another
  recorder limitation. Do not label it a Qwen or Goose inference defect.
- **Architecture impact:** none. All runtime source hashes match Increment 6.
  Worker adapter, sentinel, artifacts, interruption/replacement and completion
  acceptance scenarios are NOT RUN.
- **Decision required:** authorize only a narrow auxiliary-request/stream-capture
  diagnostic, or establish a documented invocation-only title-disable option,
  before repeating binding capture. No global configuration changes are needed
  for the already-proven main inference route.
- **Safest next option:** isolate the capture/auxiliary-call question with the same
  tiny prompt and local endpoint; do not broaden into model quality investigation.

[Summary](../../experiments/kernel-increment-7/evidence/binding/summary.json),
[first capture](../../experiments/kernel-increment-7/evidence/binding/attempt-1/binding.json),
[bounded repeat](../../experiments/kernel-increment-7/evidence/binding/attempt-2/binding.json),
[unchanged runtime](../../experiments/kernel-increment-7/evidence/binding/unchanged-runtime.json).

This stops under the bounded-debugging and unexplained-behavior gates, not because
per-run provider overrides require persistent configuration changes. Next remains
Increment 7. No later increments started.
