#!/usr/bin/env python3
"""Bounded synthetic token-ID inputs. Retain only operational aggregates, never content."""
from concurrent.futures import ThreadPoolExecutor
import json
import subprocess
import time
from urllib.request import Request
from observe import HTTP, get, save, inventory


def metrics(port):
    return {line.rsplit(" ", 1)[0]: float(line.rsplit(" ", 1)[1]) for line in get(f'http://127.0.0.1:{port}/metrics').splitlines()
            if line.startswith(('vllm:', 'DCGM_')) and 'cache_config_info' not in line and '_bucket{' not in line and '_created{' not in line}


def sample():
    raw = subprocess.check_output(['nvidia-smi', '--query-gpu=utilization.gpu,memory.used,memory.free,temperature.gpu,power.draw', '--format=csv,noheader,nounits'], text=True)
    return {'time': time.time(), 'dcgm': metrics(9400),
            'nvidia_smi': dict(zip(['utilization_percent', 'used_mib', 'free_mib', 'temperature_c', 'power_w'], map(float, raw.strip().split(',')))),
            'generation_gauges': {k: v for k, v in metrics(8000).items() if any(x in k for x in ['num_requests_running', 'num_requests_waiting', 'kv_cache_usage_perc'])}}


def request(port, route, body):
    start = time.time()
    req = Request(f'http://127.0.0.1:{port}/v1/{route}', data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    with HTTP.open(req, timeout=60) as response:
        status, data = response.status, json.load(response)
    # No request body, completion, embedding vector, request ID or prompt retained.
    return {'http_status': status, 'elapsed_seconds': time.time() - start, 'usage': data.get('usage'),
            'embedding_count': len(data.get('data', [])) if route == 'embeddings' else None}


before = {role: metrics(port) for role, port in [('generation', 8000), ('embedding', 8001)]}
report = {'started': time.time(), 'input_kind': 'synthetic token IDs', 'max_output_tokens': 512, 'idle': [], 'load': []}
for _ in range(6):
    report['idle'].append(sample())
    time.sleep(1)
with ThreadPoolExecutor(max_workers=2) as pool:
    generation = pool.submit(request, 8000, 'completions', {'model': 'nvidia/Qwen3.8-27B-NVFP4', 'prompt': [42] * 256, 'max_tokens': 512, 'ignore_eos': True, 'temperature': 0})
    embedding = pool.submit(request, 8001, 'embeddings', {'model': 'BAAI/bge-m3', 'input': [42, 43, 44] * 16})
    for _ in range(60):
        report['load'].append(sample())
        if generation.done() and embedding.done():
            break
        time.sleep(1)
    report['generation_request'] = generation.result(timeout=5)
    report['embedding_request'] = embedding.result(timeout=5)
time.sleep(2)
after = {role: metrics(port) for role, port in [('generation', 8000), ('embedding', 8001)]}
report['deltas'] = {role: {key: value - before[role].get(key, 0) for key, value in values.items() if value != before[role].get(key, 0)} for role, values in after.items()}
report['ended'] = time.time()
save('bounded-load.json', report)
save('gpu-inventory.json', inventory(9400))
for role in ['generation', 'embedding']:
    assert any('vllm:request_success_total' in k and v >= 1 for k, v in report['deltas'][role].items())
    assert any('vllm:e2e_request_latency_seconds_count' in k and v >= 1 for k, v in report['deltas'][role].items())
assert any('vllm:generation_tokens_total' in k and v >= 512 for k, v in report['deltas']['generation'].items())
for phase in ['idle', 'load']:
    for row in report[phase]:
        gpu = {k.split('{')[0]: v for k, v in row['dcgm'].items()}
        assert abs(gpu['DCGM_FI_DEV_FB_USED'] - row['nvidia_smi']['used_mib']) < 256
        assert abs(gpu['DCGM_FI_DEV_GPU_TEMP'] - row['nvidia_smi']['temperature_c']) < 15
        assert 10 < gpu['DCGM_FI_DEV_POWER_USAGE'] < 650
idle_max = max(next(v for k, v in s['dcgm'].items() if k.startswith('DCGM_FI_DEV_GPU_UTIL{')) for s in report['idle'])
load_max = max(next(v for k, v in s['dcgm'].items() if k.startswith('DCGM_FI_DEV_GPU_UTIL{')) for s in report['load'])
assert load_max > idle_max + 20
print(json.dumps({'result': 'PASS', 'idle_gpu_max': idle_max, 'load_gpu_max': load_max,
                  'generation': report['generation_request'], 'embedding': report['embedding_request']}))
