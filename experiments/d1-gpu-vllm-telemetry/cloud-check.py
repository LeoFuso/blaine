#!/usr/bin/env python3
"""Read existing Cloud metrics; retain sanitized query results, no credentials."""
from concurrent.futures import ThreadPoolExecutor
import json
import math
import time
from observe import ROOT, query, save

catalog = json.loads((ROOT / 'infra/telemetry/promql.json').read_text())


def check(item):
    name, expression = item
    result = query(expression)
    result['finite_values'] = all(math.isfinite(float(row['value'][1])) for row in result['result'])
    return name, result


with ThreadPoolExecutor(max_workers=4) as pool:
    results = dict(pool.map(check, catalog.items()))
extra = {
    'vllm_families': 'count by (__name__,service) ({host="blaine",environment="blaine-dev",job="blaine/vllm"})',
    'gpu_families': 'count by (__name__) ({host="blaine",environment="blaine-dev",job="blaine/gpu"})',
    'generation_increase': 'increase(vllm:generation_tokens_total{host="blaine",job="blaine/vllm",role="generation"}[5m])',
    'embedding_increase': 'increase(vllm:request_success_total{host="blaine",job="blaine/vllm",role="embedding",finished_reason="stop"}[5m])',
    'gpu_load_seen': 'max_over_time(DCGM_FI_DEV_GPU_UTIL{host="blaine",job="blaine/gpu"}[5m])',
    'gpu_idle_seen': 'min_over_time(DCGM_FI_DEV_GPU_UTIL{host="blaine",job="blaine/gpu"}[5m])',
    'freshness_seconds': 'time() - timestamp(up{host="blaine",job=~"blaine/(vllm|gpu)"})',
}
proof = {name: query(expression) for name, expression in extra.items()}
save('cloud-queries.json', {'observed_at': time.time(), 'catalog': results, 'proof': proof})
failed = [name for name, result in results.items() if not result['result'] or not result['finite_values']]
for name, result in results.items():
    print(name, 'series=' + str(len(result['result'])), 'finite=' + str(result['finite_values']))
assert not failed, 'Missing/nonfinite queries: ' + str(failed)
up = results['telemetry_scrape_up']['result']
assert len(up) == 3 and all(float(row['value'][1]) == 1 for row in up)
assert all(float(row['value'][1]) == 1 for row in results['host_and_alloy_scrape_up']['result'])
assert all(float(row['value'][1]) < 60 for row in proof['freshness_seconds']['result'])
assert any(float(row['value'][1]) > 0 for row in proof['generation_increase']['result'])
assert any(float(row['value'][1]) > 0 for row in proof['embedding_increase']['result'])
assert any(float(row['value'][1]) > 20 for row in proof['gpu_load_seen']['result'])
print('PASS: catalog, current scrapes, preserved host/self and bounded-load metrics read back from Cloud')
