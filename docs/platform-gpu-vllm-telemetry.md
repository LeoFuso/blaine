# RTX 5090 + vLLM platform telemetry

Status: **PASS**, validated 2026-09-21 America/Sao_Paulo (2026-09-22 UTC).
This slice adds infrastructure metrics only. Task instrumentation is separately
owned. Grafana Cloud uses the accepted best-effort metrics transport; its known
restart-replay limitation remains unchanged. Fleet is DEFERRED / STOP, D1.G is
PENDING its separately authorized reboot, and backup remains PAUSED.

## Sources and ownership

| Source | Live endpoint | Owner | Cadence |
|---|---|---|---|
| Generation | `127.0.0.1:8000/metrics` | Existing user unit `blaine-generation` | Alloy 15 s |
| Embeddings | `127.0.0.1:8001/metrics` | Existing user unit `blaine-embedding` | Alloy 15 s |
| GPU | `127.0.0.1:9400/metrics` | System unit `blaine-gpu-exporter` | DCGM / Alloy 5 s |

Generation remains `nvidia/Qwen3.8-27B-NVFP4`, revision
`482ca0f3832238542f8f5295dde86b5f22711d80`, context 131072. Embeddings remain
`BAAI/bge-m3`, revision `5617a9f61b028005a4858fdac845db406aefb181`.
The accepted runtime is vLLM `0.29.1rc1.dev401+gc3b484463`, Torch
`2.13.0+cu132`, CUDA 13.2. Neither service was restarted or reconfigured.

Native Alloy scrapes feed the existing local metrics receiver and the existing
`prometheus.remote_write.grafana_metrics` receiver. No Prometheus server, second
collector, second transport, credential, or application instrumentation was added.
The existing root-only BWS-materialized metrics credential serves Cloud reads and
writes. The new files do not modify secret materialization or the remote-write WAL.

The [Alloy fragment](../infra/alloy/platform-telemetry.alloy) is appended inside
explicit ownership markers by [the reconciler](../infra/telemetry/reconcile-alloy.py).
Everything outside those markers is retained byte-for-byte, including the existing
host/self metrics and logs/traces configuration. The shared `config.alloy`,
`metrics.alloy.inactive`, and `grafana-cloud.py` repository files are untouched.

## GPU selection and support

Use official NVIDIA **DCGM Exporter 4.8.4**, Debian package `4.8.4.3955-1`, paired
with **DCGM core 4.6.1**, Debian package `1:4.6.1-1`. This is the tested pairing
published in the [NVIDIA release](https://github.com/NVIDIA/dcgm-exporter/releases/tag/4.8.4).
Packages come from NVIDIA's Ubuntu 26.04 x86_64 CUDA repository over HTTPS, with
SHA-256 values pinned in Ansible and [package evidence](../experiments/d1-gpu-vllm-telemetry/evidence/package-selection.json).
No repository or driver pinning was changed, and no CUDA toolkit, driver, proprietary
diagnostics, or recommended package was installed. Apt simulation and actual install
selected just two new packages and upgraded none.

NVIDIA documents Maxwell-and-newer GeForce support and Ubuntu 26.04 in its
[platform matrix](https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/getting-started.html),
and supports GPU field watches on GeForce in its
[feature matrix](https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/feature-overview.html).
This is limited GeForce functionality, not a claim of datacenter diagnostics or
all fields on every driver. Actual telemetry and restart checks passed on the
Blackwell RTX 5090 with installed NVIDIA driver `595.91.07`.
NVIDIA supports [native package/systemd deployment](https://docs.nvidia.com/datacenter/dcgm/latest/installation/install-dcgm-exporter.html).

The [Blaine-owned unit](../infra/systemd/blaine-gpu-exporter.service) runs the
official binary with embedded DCGM as the package-created `nvidia-dcgm` account.
It has no Linux capabilities, `NoNewPrivileges`, a protected filesystem, a private
temporary directory, and only a loopback HTTP listener. Installation uses root;
the running exporter does not. Vendor `nvidia-dcgm` and `nvidia-dcgm-exporter`
services remain disabled/inactive; no separate host engine, rootful Docker,
container runtime socket, Kubernetes, or workload mapping is involved.
Systemd owns restart/enablement. DCGM field retention is one minute.

The bounded [counter file](../infra/telemetry/gpu-counters.csv) exports 16 actual
series: `DCGM_FI_DEV_GPU_UTIL`, `MEM_COPY_UTIL`, `FB_USED`, `FB_FREE`, `FB_RESERVED`,
`GPU_TEMP`, `POWER_USAGE`, `POWER_MGMT_LIMIT`, `SM_CLOCK`, `MEM_CLOCK`,
`CLOCK_THROTTLE_REASONS`, `PCIE_REPLAY_COUNTER`, `POWER_VIOLATION`,
`THERMAL_VIOLATION` (all with the `DCGM_FI_DEV_` prefix), plus
`DCGM_FI_PROF_PCIE_TX_BYTES` and `DCGM_FI_PROF_PCIE_RX_BYTES`.
PCIe throughput worked without elevated capabilities on this host.
XID errors were requested in the probe but not emitted, so they are omitted from
the production set; absence is not evidence of zero errors. ECC, NVLink,
datacenter diagnostic, and arbitrary profiling metrics are outside this slice.
Throttling reasons are a bitmask; cumulative power/thermal violation times use ns.

## Useful vLLM metrics

The live inventories, not generic version assumptions, determine the allowlist:

- `vllm:num_requests_running`, `vllm:num_requests_waiting`,
  `vllm:num_requests_waiting_by_reason`, `vllm:kv_cache_usage_perc` (fraction).
- `vllm:prefix_cache_queries_total`, `vllm:prefix_cache_hits_total`,
  `vllm:prompt_tokens_total`, `vllm:generation_tokens_total`,
  `vllm:request_success_total`, `vllm:num_preemptions_total`.
- Histograms `vllm:request_prompt_tokens`, `vllm:request_generation_tokens`,
  `vllm:time_to_first_token_seconds`, `vllm:inter_token_latency_seconds`,
  `vllm:request_time_per_output_token_seconds`, `vllm:e2e_request_latency_seconds`,
  `vllm:request_queue_time_seconds`, `vllm:request_inference_time_seconds`,
  `vllm:request_prefill_time_seconds`, `vllm:request_decode_time_seconds`.

Both servers expose the same core families. Embedding requests advance prompt,
success, and E2E observations. Autoregressive decode, inter-token latency, KV cache,
and prefix-cache panels are meaningful for generation, not the pooling model.
Do not treat generic embedding zero-valued generation families as useful work.

Target labels are stable `host`, `service`, `role`, `model`, `job`, and endpoint
`instance`. Allowed metric dimensions are `engine`, histogram `le`, bounded
`reason` / `finished_reason`, and GPU index `gpu`. Drop duplicate model names,
GPU UUID/PCI identity, configuration-info labels, process/Python metrics, created
gauges, and unrelated vLLM families before forwarding to either sink. No Task,
request, prompt, user, or artifact identifiers are emitted by this configuration.
Scrapes have sample/body/target limits. Acceptance observed **507 total Cloud
series** across the three targets, including scrape diagnostics. Grafana already
enriches `up` with `asserts_env="blaine-dev"`; this low-cardinality Cloud label is
also present on the unchanged host/self targets, and is absent from the local WAL.

## Deploy and converge

The playbook defaults to staging only. Run as root for the real host:

```bash
sudo -n /home/leofuso/.local/share/blaine/runtime/ops/bin/ansible-playbook \
  -i infra/ansible/inventory.ini infra/ansible/platform-telemetry.yml \
  -e blaine_activate=true
```

It checks the accepted GPU/driver/OS, refuses another active DCGM owner or an
unexpected installed version, downloads checksum-pinned packages, suppresses
package service autostart, installs the unit/counters, verifies the GPU endpoint,
and validates/reconciles Alloy. Only a changed exporter definition restarts that
service; only a changed Alloy block restarts Alloy. Reapplying produced `changed=0`.
Revalidate support deliberately after changing the GPU, driver, or package pair.

For isolated staging use `-e blaine_prefix=/tmp/blaine-telemetry-scratch` without
activation. Syntax and convergence evidence are retained. Rootless-host's existing
guard continues to protect the active Cloud configuration. The legacy
`activate-metrics` command will reject this extended active composition; use this
playbook for this slice instead of overwriting the active file with an old base.

Activation stores `/etc/alloy/blaine-before-platform.alloy`, validates the candidate,
checks for intervening configuration edits, and restores the previous config if
restart/readiness fails while the configuration is still owned. For deliberate
rollback, first compare the backup with the current unowned base; if they differ,
preserve the newer independent edits and remove only this block. Validate the
result, restart Alloy, then disable/stop `blaine-gpu-exporter`. Package removal is
optional. No rollback requires restarting inference or rebooting.

## Acceptance and dashboard contract

[Full evidence and reproduction](../experiments/d1-gpu-vllm-telemetry/README.md)
includes local inventories, service/boot preservation, bounded concurrent requests,
Cloud results, restarts, and tests. All **39 copy/paste PromQL expressions** are in
the [validated catalog](../experiments/d1-gpu-vllm-telemetry/PROMQL.md), also available
as [machine-readable queries](../infra/telemetry/promql.json).

| Dashboard group | Future panels | Units / semantics |
|---|---|---|
| GPU | utilization, VRAM used/free, temperature, power | %, GiB, °C, W; physical device, not per-model attribution |
| Generation | running/waiting, KV cache, tokens/s | requests, % of vLLM KV allocation, tokens/s |
| Generation latency | TTFT, inter-token and request TPOT, E2E | p50/p95 seconds; token-weighted ITL differs from request-average TPOT |
| Generation details | queue/prefill/decode, prefix-cache hit ratio | p50/p95 seconds; token-weighted cache hit % only with queries |
| Embeddings | successful request rate, E2E p50/p95, input tokens/s | requests/s, seconds, tokens/s |
| Health | metrics `up`, freshness | generation/embedding/GPU endpoints; API readiness separately proven |

Use `host`/`service`/`role`/`model` filters with fixed, low-cardinality choices.
Keep no-data visible for idle latency/cache panels. Do not interpolate missing
hardware metrics into fabricated zeros. Infrastructure metrics can later share a
dashboard with Task-level metrics through stable service/host selectors, without
Task IDs or request IDs in these series. No dashboard, recording rule, alert,
logs/traces pipeline, or Task-level code was added here.
