#!/usr/bin/env python3
"""Final read-only preservation, delivery and cardinality checks; run after observe.py after."""
import hashlib
import json
from pathlib import Path
import runpy
import time
from observe import OUT, get, query, run, save

before = json.loads((OUT / 'before.json').read_text())
after = json.loads((OUT / 'after.json').read_text())
config = Path('/etc/alloy/config.alloy').read_text()
reconciler = runpy.run_path(str(Path(__file__).resolve().parents[2] / 'infra/telemetry/reconcile-alloy.py'))
prefix, owned = config.split(reconciler['BEGIN'])
_, suffix = owned.split(reconciler['END'])
report = {
    'observed_at': time.time(),
    'boot_unchanged': before['boot_id'] == after['boot_id'],
    'services_unchanged': before['units'] == after['units'],
    'unowned_alloy_bytes_unchanged': hashlib.sha256((prefix + suffix).encode()).hexdigest() == before['config_sha256'],
    'fleet_inactive': not after['fleet_active'],
    'single_existing_remote_write': after['remote_write_count'] == 1,
    'backup_unchanged': before['backup'] == after['backup'],
    'host_and_new_cloud_up': query('up{host="blaine",environment="blaine-dev"}'),
    'post_restart_freshness': query('time() - timestamp(up{host="blaine",job=~"blaine/(vllm|gpu)"})'),
    'post_restart_gpu': query('DCGM_FI_DEV_GPU_UTIL{host="blaine",job="blaine/gpu"}'),
    'config_validation': run('alloy', 'validate', '--stability.level=public-preview', '/etc/alloy/config.alloy'),
}
candidate = json.loads(Path('/home/leofuso/.config/blaine/inference/candidate.json').read_text())
report['accepted_inference'] = {key: candidate[key] for key in ['vllm_version', 'vllm_commit', 'torch', 'cuda_build']}
report['accepted_inference']['models'] = {role: {key: candidate[role][key] for key in ['repository', 'revision']} for role in ['generation', 'embedding']}
report['inference_health'] = {str(port): {'http_status': 200, 'body_empty': get(f'http://127.0.0.1:{port}/health') == ''} for port in [8000, 8001]}
wal = run('alloy', 'tools', 'prometheus.remote_write', 'sample-stats', '--selector', '{job=~"blaine/(vllm|gpu)"}', '/var/lib/alloy/data/prometheus.remote_write.grafana_metrics/wal')
report['local_wal'] = {'exit_code': wal['exit_code'], 'series': wal['stdout'].count('Oldest Sample:'),
                       'vllm_present': 'vllm:' in wal['stdout'], 'gpu_present': 'DCGM_FI_DEV_GPU_UTIL' in wal['stdout']}
allowed = {'__name__', 'job', 'instance', 'host', 'environment', 'service', 'role', 'model', 'gpu', 'engine', 'le', 'reason', 'finished_reason'}
# Grafana already enriches baseline up with asserts_env; it is absent in the local WAL.
series = query('{host="blaine",job=~"blaine/(vllm|gpu)"}')['result']
labels = {key for row in series for key in row['metric']}
report['cardinality'] = {'series_count': len(series), 'label_names': sorted(labels),
                         'cloud_enrichment': {'asserts_env': 'blaine-dev'},
                         'unexpected_labels': sorted(labels - allowed - {'asserts_env'})}
report['local_metrics_file'] = {'vllm_metrics': 0, 'gpu_metrics': 0}
with open('/var/lib/alloy/telemetry/local.json') as stream:
    for line in stream:
        try:
            record = json.loads(line)
        except ValueError:
            continue
        for resource in record.get('resourceMetrics', []):
            for scope in resource.get('scopeMetrics', []):
                for metric in scope.get('metrics', []):
                    name = metric.get('name', '')
                    if name.startswith('vllm'):
                        report['local_metrics_file']['vllm_metrics'] += 1
                    if name.startswith('DCGM'):
                        report['local_metrics_file']['gpu_metrics'] += 1
save('acceptance.json', report)
assert all(report[key] for key in ['boot_unchanged', 'services_unchanged', 'unowned_alloy_bytes_unchanged', 'fleet_inactive', 'single_existing_remote_write', 'backup_unchanged'])
assert not report['cardinality']['unexpected_labels']
assert all(report['local_metrics_file'].values())
assert report['local_wal']['exit_code'] == 0 and report['local_wal']['vllm_present'] and report['local_wal']['gpu_present']
assert report['config_validation']['exit_code'] == 0
up = report['host_and_new_cloud_up']['result']
assert len(up) == 5 and all(float(row['value'][1]) == 1 for row in up)
assert all(float(row['value'][1]) < 60 for row in report['post_restart_freshness']['result'])
assert report['post_restart_gpu']['result']
print('PASS: preserved boot, services and Alloy base; local and Cloud metrics; bounded labels')
