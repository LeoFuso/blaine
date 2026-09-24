# Balanced local inference

The 2026-09-21 operator correction prioritizes functional daily use and headroom
for Blaine services and the desktop. Saturation benchmarks are not acceptance requirements. Preserve the 128k target
with one generation at a time; reduce it only for observed coexistence problems. ADR 0019 retains its original history with an
explicit amendment.

The operator also explicitly deferred investigation of hybrid CPU/GPU model
execution until the remaining service-adoption work is complete. It is low
priority, not a fallback to investigate during this pass. CPU use for serving
or bounded kernel compilation does not imply CPU weight offload.

`candidate.json` pins the checkpoints, environment and proposed serving settings.
D1.C is accepted; see [evidence](../../experiments/d1-service-adoption/evidence/inference-summary.json). Full host reboot remains pending.

| Resource | Qwen generation | BGE-M3 embeddings |
|---|---|---|
| Context limit (input + output for generation) | 131072 (accepted) | 8192 |
| Maximum sequences per scheduler iteration | 1 | 4 |
| GPU memory budget, fraction of total VRAM | 0.80 | 0.08 |
| Host MemoryHigh / MemoryMax | 22 GiB / 28 GiB | 5 GiB / 6 GiB |
| Host swap allowance | 0 | 0 |
| CPU quota | 800% (8 logical CPUs) | 200% (2 logical CPUs) |
| CPU weight / nice | 50 / 5 | 50 / 5 |

GPU fractions are vLLM budgets, not hard GPU isolation or promised utilization.
Their sum leaves 12% (about 3.82 GiB on this GPU) outside the requested budgets.
The combined host RAM ceilings are 34 GiB on a roughly 59 GiB host; unused budget
is not preallocated. MemoryHigh induces reclaim/throttling; MemoryMax is the final
containment boundary. Other workloads still need their own sensible limits.
CPU quotas bound utilization, not latency, and do not reserve physical cores.

`serve.py` applies MAX_JOBS=1, NVCC_THREADS=1, FLASHINFER_NVCC_THREADS=1 and
TORCHINDUCTOR_COMPILE_THREADS=1 before importing vLLM. Cold compilation takes
longer, but must not fan out across the entire host again. OMP threads are four;
OpenBLAS threads are one. No CPU weight offload or swap-dependent inference.

The accepted user units are `blaine-generation.service` and `blaine-embedding.service`, both enabled. Temporary candidate units have been stopped. Run a small functional
acceptance with `python3 infra/inference/accept.py --output <evidence.json>`.
The separate `context-check.py` validates one configured-window request with output bounded to 128 tokens; it is not a saturation loop.
Record health, generation/JSON/tool correctness, simultaneous embeddings,
infrastructure health, actual memory and cgroup OOM counters. A short successful
check does not establish long-term stability or full-context capacity.

The previous 2026-09-21 16:24 host OOM killed Chrome and a CUDA `cicc` compiler;
it is not proof of GPU exhaustion or failure of a particular context length.
The known-good Qwen3.5-9B rollback checkpoint remains untouched.

Operator clarification: simultaneous generation plus embeddings is required, not
two Qwen generations. Multiple durable Tasks may share one serialized generation
engine. The briefly staged 32k/two-sequence candidate was an assistant choice,
not an accepted requirement; host compiler RAM OOM did not justify that reduction.

Provision the isolated environment with `bash infra/inference/install-env.sh`;
then use that environment's Python to run `prepare-models.py candidate.json`
from this directory. Serving runs offline and resolves only pinned revisions.
`prepare-cuda.py` adds only the local CUDA wheel linker aliases required by JIT.

Embedding startup precedes Qwen startup because vLLM profiles global VRAM. Both
services remain independently restartable; restarts and combined startup passed.
The cache contains reused PyTorch AOT/Inductor artifacts, FlashInfer CUDA libraries
and autotuning configurations; exact versions and compiled-library hashes are in
`runtime-versions.json`. Do not remove the cache as a routine restart operation.
