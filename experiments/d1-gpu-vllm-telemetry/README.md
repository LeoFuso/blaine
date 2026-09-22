# GPU + vLLM infrastructure acceptance

**PASS.** Worktree `blaine-gpu-vllm-telemetry`, branch `d1-gpu-vllm-telemetry`,
starting at `ab7e5a9` (`Close best-effort metrics transport and inventory observability coverage`).
Validation occurred on 2026-09-21 local / 2026-09-22 UTC.
No merge or push. All changed repository files are new, separately named
infrastructure/evidence files; no existing application or shared Alloy base file
was edited. No likely same-file conflict with the concurrent Task-level OTel
branch. Both slices may eventually meet in the **live** Alloy configuration:
the reconciler preserves all bytes outside its marked block, and the concurrent
owner must preserve this block when deploying its own configuration.

The [TaskSpec draft](task-request.json) was **not submitted**; the session has no
development-work execution binding. [Submission evidence](submission.json)
records this limitation. PASS here describes measured implementation acceptance,
not a claimed durable Task lifecycle transition.

## Results

| Check | Evidence / result |
|---|---|
| Generation endpoint | `http://127.0.0.1:8000/metrics`; live [before](evidence/generation-before.json), [after](evidence/generation-after.json) inventories |
| Embedding endpoint | `http://127.0.0.1:8001/metrics`; live [before](evidence/embedding-before.json), [after](evidence/embedding-after.json) inventories |
| GPU exporter | Official NVIDIA DCGM Exporter 4.8.4 + DCGM core 4.6.1; [pinned packages](evidence/package-selection.json), [service/version/restart evidence](evidence/restart.json) |
| GPU endpoint | `http://127.0.0.1:9400/metrics`; [16 actual hardware series](evidence/gpu-inventory.json) |
| Local scraping | All three sources in local Alloy metrics output and accepted remote-write WAL; [acceptance](evidence/acceptance.json) |
| Cloud | Three new and two existing targets `up=1`; fresh post-restart samples; [query proof](evidence/cloud-queries.json), [final acceptance](evidence/acceptance.json) |
| Query catalog | **39 nonempty finite validated queries**, including GPU, generation and embedding latency; [copy/paste PromQL](PROMQL.md) |
| Workload | One 256-input-token / 512-output-token generation, one 48-token embedding concurrently; HTTP 200 for both; [operational aggregates only](evidence/bounded-load.json) |
| Convergence | Scratch and live second applications both `changed=0`; [scratch](evidence/ansible-scratch-second.txt), [live](evidence/ansible-live-second.txt) |
| Tests | **41 passed**; [platform tests](evidence/platform-tests.txt); native Alloy config validation exit 0 in final acceptance |
| Restarts | New exporter started, then explicitly restarted once; Alloy restarted for activation and once for acceptance; both ready and Cloud delivery resumed |
| Preservation | Same boot ID and all five Blaine service PIDs/start times/restart counts; unchanged unowned Alloy bytes, backup state and remote-write count |

Useful metric names, deployment/recovery instructions, support rationale,
cardinality policy and dashboard contract are in the
[platform runbook](../../docs/platform-gpu-vllm-telemetry.md).

## Bounded idle / load observations

Both generation and embeddings remained resident throughout. This validates
telemetry availability during coexistence, not inference capacity or benchmarks.
DCGM samples every 5 s; comparison `nvidia-smi` samples approximately every second,
so peaks and timestamps need not be identical.

| Measurement | DCGM idle | DCGM generation load | `nvidia-smi` load |
|---|---:|---:|---:|
| GPU utilization | 0% | peak 99% | peak 99% |
| Used framebuffer | 29348–29350 MiB | 29348–29419 MiB | 29376–29420 MiB |
| GPU temperature | 46 °C | peak 57 °C | peak 58 °C |
| Power | 24.4–26.0 W | peak 384.2 W | peak 385.8 W |

Generation completed in 7.71 s, embeddings in 0.031 s. Local generation token
counter increased by exactly 512; request, E2E, TTFT and inter-token histograms
advanced. Embedding prompt, request and E2E counters advanced. Cloud readback
contains both idle 0% and load 99% GPU samples, and positive generation/embedding
counter increases. PromQL `increase()` extrapolates across scrape boundaries;
its fractional values are not the exact test request counts.

GPU field watches and the two PCIe throughput fields worked unprivileged during
the preliminary probes. The selected dedicated service repeats that behavior
with an empty capability bounding set. Vendor DCGM services remain disabled and
inactive. `DCGM_FI_DEV_XID_ERRORS` was not emitted; it is excluded rather than
reported as zero. No other GPU exporter existed before this slice.

The catalog validates syntax, label selection, finite observation values and
Cloud delivery. With no traffic in a later five-minute window, latency quantiles
can become NaN and the guarded prefix-cache ratio returns no series. This is
expected idle behavior, documented alongside the queries.

## Reproduction

From the repository root, after deployment:

```bash
# Read-only current snapshot (baseline before.json is the retained acceptance baseline).
sudo -n python3 experiments/d1-gpu-vllm-telemetry/observe.py after

# Sends only bounded synthetic token-ID inference input; does not retain content.
python3 experiments/d1-gpu-vllm-telemetry/load-check.py

# Allow at least one 15-second scrape plus the remote-write delivery delay.
# Run within five minutes of the bounded request for finite rate-based latencies.
sudo -n python3 experiments/d1-gpu-vllm-telemetry/cloud-check.py
sudo -n python3 experiments/d1-gpu-vllm-telemetry/acceptance.py

python3 -m unittest discover -s tests/platform -v
git diff --check
```

The retained before/after files are acceptance snapshots, not a task ledger.
Reproduction overwrites corresponding evidence; preserve the originals if needed.
Cloud reads use the existing protected materialized credential in memory with
redirects disabled. No secret/header/request content is written to evidence.
The first all-platform test attempt inside the sandbox could not start its
temporary PostgreSQL socket; the complete suite passed outside the sandbox.
The load harness initially rejected spaces in the GPU model label; parsing was
corrected before any inference request was sent. Final evidence uses that parser.

## Boundaries and limitations

- No reboot; D1.G remains pending. No inference, MIRIX, Restate or runtime restart.
- No inference architecture/launch/configuration change, CUDA build, or driver update.
- No rootful Docker dependency, duplicate exporter, or permanently running shell sampler.
- Fleet stayed inactive. Logs/traces paths were untouched. Application and
  Task/cognitive-loop instrumentation were untouched.
- Existing host/self local and Cloud metrics stayed healthy after both Alloy restarts.
  The already accepted restart-replay limitation remains; this does not certify
  lossless transport or reopen OBS-001.
- No polished dashboard was created. The runbook's dashboard contract is ready
  to combine later with the separate Task-level telemetry.
- No push or merge. This new runbook supersedes the GPU/vLLM coverage gaps in the
  earlier observability inventory without rewriting that historical evidence.
