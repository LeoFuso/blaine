#!/usr/bin/env python3
"""Sanitized, read-only platform snapshot. Run as root for protected Cloud read access."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / 'evidence'
UNITS = ['blaine-generation', 'blaine-embedding', 'blaine-mirix', 'blaine-restate', 'blaine-runtime']


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


HTTP = build_opener(NoRedirect)


def get(url):
    with HTTP.open(url, timeout=30) as response:
        return response.read().decode()


def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return {'exit_code': result.returncode, 'stdout': result.stdout.strip()}


def save(name, data):
    path = OUT / name
    path.write_text(json.dumps(data, indent=2) + '\n')
    if os.geteuid() == 0:
        os.chown(path, 1000, 1000)


def query(expression):
    materializer = runpy.run_path(str(ROOT / 'infra/grafana-cloud.py'))
    path = materializer['METRICS_ENV_FILE']
    assert path.resolve() == path and path.stat().st_uid == 0 and not path.stat().st_mode & 0o077
    values = materializer['validate_metrics'](dict(line.split('=', 1) for line in path.read_text().splitlines() if line))
    auth = 'Basic ' + base64.b64encode(('3602220:' + values['GRAFANA_CLOUD_METRICS_API_KEY']).encode()).decode()
    request = Request('https://prometheus-prod-40-prod-sa-east-1.grafana.net/api/prom/api/v1/query?' + urlencode({'query': expression}), headers={'Authorization': auth})
    with HTTP.open(request, timeout=30) as response:
        data = json.load(response)
    assert data['status'] == 'success'
    return {'query': expression, 'status': data['status'], 'result': data['data']['result']}


def inventory(port):
    data = get(f'http://127.0.0.1:{port}/metrics')
    samples = [line for line in data.splitlines() if line and not line.startswith('#')]
    return {'endpoint': f'http://127.0.0.1:{port}/metrics', 'bytes': len(data),
            'families': [line for line in data.splitlines() if line.startswith(('# TYPE ', '# HELP '))],
            'label_names': sorted(set(re.findall(r'(\w+)=', data))), 'sample_count': len(samples),
            'operational_samples': [line for line in samples if (line.startswith(('vllm:', 'DCGM_')) and 'cache_config_info' not in line)]}


def snapshot():
    config = Path('/etc/alloy/config.alloy').read_text()
    units = {unit: run('runuser', '-u', 'leofuso', '--', 'env', 'XDG_RUNTIME_DIR=/run/user/1000', 'systemctl', '--user', 'show', unit, '-p', 'MainPID', '-p', 'NRestarts', '-p', 'ActiveState', '-p', 'ActiveEnterTimestamp') for unit in UNITS}
    metrics = get('http://127.0.0.1:12345/metrics')
    return {'observed_at': time.time(), 'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            'units': units, 'alloy': run('systemctl', 'show', 'alloy', '-p', 'MainPID', '-p', 'ActiveState', '-p', 'NRestarts'),
            'alloy_ready': get('http://127.0.0.1:12345/-/ready').strip(),
            'config_sha256': hashlib.sha256(config.encode()).hexdigest(),
            'scrapes': re.findall(r'prometheus.scrape "([^"]+)"', config),
            'fleet_active': 'remotecfg {' in config,
            'remote_write_count': config.count('prometheus.remote_write "'),
            'alloy_metrics': [line for line in metrics.splitlines() if not line.startswith('#') and (('prometheus_remote_storage_' in line and 'grafana_metrics' in line) or 'prometheus_forwarded_samples_total' in line)],
            'gpu': run('nvidia-smi', '--query-gpu=name,driver_version,memory.total,memory.used,memory.free,utilization.gpu,utilization.memory,temperature.gpu,power.draw,power.limit,clocks.sm,clocks.mem', '--format=csv'),
            'exporter_units': run('systemctl', 'list-unit-files', '*dcgm*', '*gpu*export*'),
            'cloud_up': query('up{host="blaine",environment="blaine-dev"}'),
            'host_cpu': query('count(node_cpu_seconds_total{host="blaine",environment="blaine-dev"})'),
            'backup': run('systemctl', 'show', 'blaine-partial-backup.timer', '-p', 'ActiveState', '-p', 'UnitFileState')}


if __name__ == '__main__':
    phase = sys.argv[1]
    assert phase in ('before', 'after')
    save(phase + '.json', snapshot())
    for role, port in [('generation', 8000), ('embedding', 8001)]:
        save(role + '-' + phase + '.json', inventory(port))
    print('Saved sanitized', phase, 'snapshot and live vLLM inventories.')
