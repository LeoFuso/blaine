# ADR 0019 — Local inference serving baseline

**Status:** Accepted
**Validation:** Unvalidated
**Date:** 2026-09-21

## Context

Blaine has already proven local model-driven cognition using terminal-owned
vLLM processes:

- `Qwen/Qwen3.5-9B` for generation;
- `BAAI/bge-m3` for embeddings.

D1 requires those processes to become stable long-lived platform services.

The workstation has one NVIDIA RTX 5090 with 32 GiB VRAM. Local inference is
also used outside the Cognitive Loop, including interactive Goose workloads.

The resident setup should therefore make good use of the available hardware
without making Blaine depend on complicated CPU offload, SSD streaming,
frequent model swapping, or heterogeneous inference tiers.

Larger-model approaches were considered, including:

- retaining Qwen3.5-9B;
- Qwen3.8-27B;
- larger MoE models;
- Colibrì;
- CPU/RAM/NVMe expert streaming;
- separate deep-local inference tiers.

Those remain valid future experiments, but D1 should first establish a simple,
inspectable and recoverable local inference baseline.

## Decision

### Generation

- runtime: vLLM;
- model family: Qwen3.8-27B;
- preferred deployment quantization: Blackwell-oriented 4-bit/NVFP4;
- initial checkpoint candidate: `nvidia/Qwen3.8-27B-NVFP4`;
- target maximum context: 131072 tokens;
- FP8 KV cache where supported and validated;
- primary consumers:
  - Blaine Worker Adapter;
  - Cognitive Loop;
  - Goose;
- no CPU weight offload;
- no NVMe inference tier;
- no swap-dependent inference.

The exact checkpoint revision and vLLM build are operational pins and MUST be
recorded from the accepted deployment.

### Embeddings

- model: `BAAI/bge-m3`;
- runtime: vLLM pooling/embedding service;
- maximum model length: 8192;
- GPU residency is preferred because embedding throughput and batching are
  useful to MIRIX and retrieval workloads.

Generation and embedding should coexist on the RTX 5090 if bounded acceptance
shows stable memory use.

## GPU policy

The generation model receives the majority of VRAM.

The embedding service should remain GPU-resident when practical.

Configuration must leave enough operating headroom to avoid routine OOM
behavior.

Do not optimize for maximum theoretical VRAM occupancy.

## Context fallback

128 KiB is the target, not an unconditional requirement.

If generation plus GPU-resident BGE-M3 cannot operate reliably at 131072
tokens:

1. verify actual vLLM memory accounting and quantization configuration;
2. reduce generation maximum context to 98304;
3. reduce generation maximum context to 65536;
4. benchmark BGE-M3 on CPU only if preserving larger generation context is
   materially more useful;
5. only then reconsider the generation checkpoint/model.

Do not silently introduce CPU weight offload, NVMe expert streaming, or swap
as a fix for VRAM pressure.

## Rollback

`Qwen/Qwen3.5-9B` remains the known-good generation rollback until the new
generation service passes D1.C acceptance.

The old model must not be deleted merely because the candidate starts.

## Deferred alternatives

Colibrì, larger MoE models, SSD-backed expert streaming, and a separate
deep-local tier are explicitly deferred experiments.

They may later become useful capabilities, but they are not dependencies of
Daily Driver v0 or D1.

## Validation

### Hypothesis

Qwen3.8-27B in a Blackwell-oriented quantization can provide a materially
stronger resident local model while preserving the simple vLLM operational
model and coexisting with BGE-M3 on the RTX 5090.

### Minimal validation

1. Pin exact model revisions and vLLM build.
2. Start Qwen3.8-27B manually outside systemd.
3. Verify health and `/v1/models`.
4. Verify normal generation.
5. Verify structured JSON.
6. Verify tool calling.
7. Verify a representative Goose interaction.
8. Verify a representative Blaine Worker Adapter interaction.
9. Run BGE-M3 concurrently and verify embeddings.
10. Demonstrate the selected context boundary.
11. Record VRAM use.
12. Confirm there is no CPU/NVMe weight offload or swap dependency.
13. Only after PASS, promote the exact commands into systemd-owned services.

## Reconsider when

Reconsider this decision if:

- quantization causes unacceptable behavioral regression;
- tool calling or structured output is unreliable;
- GPU-resident embeddings and useful context cannot coexist;
- interactive latency is unacceptable;
- vLLM support for the selected checkpoint is unstable;
- a later local model materially improves capability without adding operational
  complexity.

## Consequences

The intended D1 topology is:

    RTX 5090
    ├── Qwen3.8-27B — generation / Blaine / Goose
    └── BAAI/bge-m3 — embeddings / MIRIX

Future routing may choose different local or cloud workers by workload, but D1
does not need to solve that problem.
