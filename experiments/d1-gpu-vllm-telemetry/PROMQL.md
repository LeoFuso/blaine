# Validated GPU + vLLM PromQL

All 39 expressions below returned nonempty finite results against Grafana Cloud
after the bounded load test. Exact query responses and timestamps are retained in
[evidence/cloud-queries.json](evidence/cloud-queries.json). The machine-readable
source is [promql.json](../../infra/telemetry/promql.json).

Use the existing Grafana Cloud Prometheus data source. All selectors fix the host
and environment. Results retain service/role/model identity. `up` proves the
metrics endpoint is scrapable; it does not by itself prove inference readiness.
The validation also checked `/health` and successful inference responses.

Latency quantiles are bucket estimates over the last five minutes, in seconds.
They return NaN when there are no observations in the window; token/request rates
return zero when idle. Keep NaN/no-data visible rather than inventing zero latency.
Inter-token latency is token-weighted; request TPOT is a separate distribution of
per-request averages. Embedding latency uses E2E, not decode/TTFT/TPOT.

VRAM used percent divides by used + free + reserved physical framebuffer memory.
Reserved memory is excluded from the used numerator. Memory activity percent
measures memory-engine activity, not allocated VRAM. MiB / 1024 gives GiB.
Prefix-cache hit percentage is token-weighted, generation only, and returns no
series when no prefix-cache queries occur. No epsilon or fake idle hit ratio.

## gpu utilization percent

```promql
DCGM_FI_DEV_GPU_UTIL{host="blaine",environment="blaine-dev",job="blaine/gpu"}
```

## gpu vram used percent

```promql
100 * DCGM_FI_DEV_FB_USED{host="blaine",environment="blaine-dev",job="blaine/gpu"} / (DCGM_FI_DEV_FB_USED{host="blaine",environment="blaine-dev",job="blaine/gpu"} + DCGM_FI_DEV_FB_FREE{host="blaine",environment="blaine-dev",job="blaine/gpu"} + DCGM_FI_DEV_FB_RESERVED{host="blaine",environment="blaine-dev",job="blaine/gpu"})
```

## gpu vram used gib

```promql
DCGM_FI_DEV_FB_USED{host="blaine",environment="blaine-dev",job="blaine/gpu"} / 1024
```

## gpu vram free gib

```promql
DCGM_FI_DEV_FB_FREE{host="blaine",environment="blaine-dev",job="blaine/gpu"} / 1024
```

## gpu temperature c

```promql
DCGM_FI_DEV_GPU_TEMP{host="blaine",environment="blaine-dev",job="blaine/gpu"}
```

## gpu power w

```promql
DCGM_FI_DEV_POWER_USAGE{host="blaine",environment="blaine-dev",job="blaine/gpu"}
```

## gpu power limit w

```promql
DCGM_FI_DEV_POWER_MGMT_LIMIT{host="blaine",environment="blaine-dev",job="blaine/gpu"}
```

## gpu memory activity percent

```promql
DCGM_FI_DEV_MEM_COPY_UTIL{host="blaine",environment="blaine-dev",job="blaine/gpu"}
```

## gpu sm clock mhz

```promql
DCGM_FI_DEV_SM_CLOCK{host="blaine",environment="blaine-dev",job="blaine/gpu"}
```

## gpu memory clock mhz

```promql
DCGM_FI_DEV_MEM_CLOCK{host="blaine",environment="blaine-dev",job="blaine/gpu"}
```

## gpu throttle reason bitmask

```promql
DCGM_FI_DEV_CLOCK_THROTTLE_REASONS{host="blaine",environment="blaine-dev",job="blaine/gpu"}
```

## gpu pcie tx bytes per second

```promql
DCGM_FI_PROF_PCIE_TX_BYTES{host="blaine",environment="blaine-dev",job="blaine/gpu"}
```

## gpu pcie rx bytes per second

```promql
DCGM_FI_PROF_PCIE_RX_BYTES{host="blaine",environment="blaine-dev",job="blaine/gpu"}
```

## gpu thermal throttled seconds per second

```promql
rate(DCGM_FI_DEV_THERMAL_VIOLATION{host="blaine",environment="blaine-dev",job="blaine/gpu"}[5m]) / 1e9
```

## vllm running requests

```promql
sum by (host,service,role,model) (vllm:num_requests_running{host="blaine",environment="blaine-dev",job="blaine/vllm"})
```

## vllm waiting requests

```promql
sum by (host,service,role,model) (vllm:num_requests_waiting{host="blaine",environment="blaine-dev",job="blaine/vllm"})
```

## generation kv cache percent

```promql
100 * max by (host,service,role,model) (vllm:kv_cache_usage_perc{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"})
```

## vllm prompt tokens per second

```promql
sum by (host,service,role,model) (rate(vllm:prompt_tokens_total{host="blaine",environment="blaine-dev",job="blaine/vllm"}[5m]))
```

## generation tokens per second

```promql
sum by (host,service,role,model) (rate(vllm:generation_tokens_total{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m]))
```

## generation prefix cache hit percent

```promql
100 * sum by (host,service,role,model) (rate(vllm:prefix_cache_hits_total{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])) / (sum by (host,service,role,model) (rate(vllm:prefix_cache_queries_total{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])) > 0)
```

## embedding requests per second

```promql
sum by (host,service,role,model) (rate(vllm:request_success_total{host="blaine",environment="blaine-dev",job="blaine/vllm",role="embedding",finished_reason="stop"}[5m]))
```

## telemetry scrape up

```promql
up{host="blaine",environment="blaine-dev",job=~"blaine/(vllm|gpu)"}
```

## host and alloy scrape up

```promql
up{host="blaine",environment="blaine-dev",job!~"blaine/(vllm|gpu)"}
```

## generation ttft p50 seconds

```promql
histogram_quantile(0.5, sum by (le,host,service,role,model) (rate(vllm:time_to_first_token_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation ttft p95 seconds

```promql
histogram_quantile(0.95, sum by (le,host,service,role,model) (rate(vllm:time_to_first_token_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation e2e p50 seconds

```promql
histogram_quantile(0.5, sum by (le,host,service,role,model) (rate(vllm:e2e_request_latency_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation e2e p95 seconds

```promql
histogram_quantile(0.95, sum by (le,host,service,role,model) (rate(vllm:e2e_request_latency_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation inter token p50 seconds

```promql
histogram_quantile(0.5, sum by (le,host,service,role,model) (rate(vllm:inter_token_latency_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation inter token p95 seconds

```promql
histogram_quantile(0.95, sum by (le,host,service,role,model) (rate(vllm:inter_token_latency_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation request tpot p50 seconds

```promql
histogram_quantile(0.5, sum by (le,host,service,role,model) (rate(vllm:request_time_per_output_token_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation request tpot p95 seconds

```promql
histogram_quantile(0.95, sum by (le,host,service,role,model) (rate(vllm:request_time_per_output_token_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation queue p50 seconds

```promql
histogram_quantile(0.5, sum by (le,host,service,role,model) (rate(vllm:request_queue_time_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation queue p95 seconds

```promql
histogram_quantile(0.95, sum by (le,host,service,role,model) (rate(vllm:request_queue_time_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation prefill p50 seconds

```promql
histogram_quantile(0.5, sum by (le,host,service,role,model) (rate(vllm:request_prefill_time_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation prefill p95 seconds

```promql
histogram_quantile(0.95, sum by (le,host,service,role,model) (rate(vllm:request_prefill_time_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation decode p50 seconds

```promql
histogram_quantile(0.5, sum by (le,host,service,role,model) (rate(vllm:request_decode_time_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## generation decode p95 seconds

```promql
histogram_quantile(0.95, sum by (le,host,service,role,model) (rate(vllm:request_decode_time_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="generation"}[5m])))
```

## embedding e2e p50 seconds

```promql
histogram_quantile(0.5, sum by (le,host,service,role,model) (rate(vllm:e2e_request_latency_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="embedding"}[5m])))
```

## embedding e2e p95 seconds

```promql
histogram_quantile(0.95, sum by (le,host,service,role,model) (rate(vllm:e2e_request_latency_seconds_bucket{host="blaine",environment="blaine-dev",job="blaine/vllm",role="embedding"}[5m])))
```
