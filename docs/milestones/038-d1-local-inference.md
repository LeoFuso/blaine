# D1.C — Accepted local inference services

2026-09-21: PASS for live adoption and controlled restarts. D1.G reboot remains
pending; this is not Daily Driver product acceptance.

Qwen `nvidia/Qwen3.8-27B-NVFP4` at revision
`482ca0f3832238542f8f5295dde86b5f22711d80` serves one generation at a time with
131072 total tokens. A real request consumed 130944 prompt tokens with a 128-token
output allowance and correctly retrieved three separated markers. BGE-M3 remains
on the same GPU at revision `5617a9f61b028005a4858fdac845db406aefb181`.

[All 21 checks and exact serving arguments](../../experiments/d1-service-adoption/evidence/inference-summary.json),
[runtime/CUDA versions and cached artifact hashes](../../experiments/d1-service-adoption/evidence/runtime-versions.json),
[context evidence](../../experiments/d1-service-adoption/evidence/context-131072.json),
[controlled restart evidence](../../experiments/d1-service-adoption/evidence/inference-restarts.json).

The normal Goose provider now uses the same local endpoint; its experimental
Ollama configuration remains intact and unloaded. Both Goose and the actual
Blaine GooseWorker adapter completed useful source/configuration interpretation.
JSON constraints, tool calls, embeddings and simultaneous operation passed.
Observed total GPU memory reached 29821 MiB of 32607 MiB.

The earlier host OOM involved parallel CUDA compilation and killed Chrome.
Compilation is now serialized and service RAM/swap/CPU limits are explicit.
Isolated CUDA wheel linker aliases enabled reuse of the existing runtime and
compiled FlashInfer/PyTorch artifacts. No system CUDA replacement or CPU offload.

Embedding readiness precedes generation startup because vLLM profiles global
VRAM. Independent restarts and combined startup passed. Neither runtime belongs
to a terminal. Both user services are enabled under the existing linger manager.
See [deployment material](../../infra/inference/README.md) and preserved
[ADR 0019](../decisions/0019-local-inference-serving-baseline.md).
