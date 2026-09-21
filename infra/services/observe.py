#!/usr/bin/env python3
"""Credential-free service, API and resource evidence for D1 acceptance/reboot."""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import urllib.request

p = argparse.ArgumentParser()
p.add_argument('--output', type=Path, required=True)
p.add_argument('--candidate', action='store_true')
a = p.parse_args()
def command(argv):
    r = subprocess.run(argv, text=True, capture_output=True)
    return {'exit_code': r.returncode, 'stdout': r.stdout.strip()}
names = (['qwen-candidate', 'embedding-candidate'] if a.candidate else
         ['generation', 'embedding', 'mirix', 'restate', 'runtime'])
out = {'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip(), 'services': {}}
for name in names:
    unit = 'blaine-' + name + '.service'
    r = command(['systemctl', '--user', 'show', unit, '-p', 'MainPID', '-p', 'ControlGroup',
        '-p', 'ActiveState', '-p', 'SubState', '-p', 'UnitFileState', '-p', 'MemoryCurrent',
        '-p', 'MemoryPeak', '-p', 'MemoryHigh', '-p', 'MemoryMax', '-p', 'MemorySwapMax',
        '-p', 'CPUQuotaPerSecUSec', '-p', 'NRestarts', '-p', 'InvocationID'])
    row = dict(line.split('=',1) for line in r['stdout'].splitlines() if '=' in line)
    group = Path('/sys/fs/cgroup') / row.get('ControlGroup', '').lstrip('/')
    if row.get('ControlGroup') and group.is_dir():
        for field in ['memory.events', 'memory.swap.current', 'memory.pressure', 'cpu.stat', 'cgroup.procs']:
            if (group / field).exists(): row[field] = (group / field).read_text()
    out['services'][unit] = row
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
out['http'] = {}
for base, paths in [('http://127.0.0.1:8000',['/health','/v1/models']),
                    ('http://127.0.0.1:8001',['/health','/v1/models']),
                    ('http://127.0.0.1:8531',['/health']),
                    ('http://127.0.0.1:49070',['/deployments'])]:
    for path in paths:
        url = base + path
        try:
            with opener.open(url, timeout=3) as r:
                raw = r.read(131072)
                out['http'][url] = {'status': r.status, 'body': json.loads(raw) if raw else None}
        except OSError as e: out['http'][url] = {'error': type(e).__name__}
out['gpu'] = command(['nvidia-smi','--query-gpu=name,driver_version,memory.used,memory.total','--format=csv,noheader'])
out['gpu_processes'] = command(['nvidia-smi','--query-compute-apps=pid,process_name,used_memory','--format=csv,noheader'])
out['meminfo'] = {k:v.strip() for k,v in (line.split(':',1) for line in Path('/proc/meminfo').read_text().splitlines())
                  if k in ['MemTotal','MemAvailable','SwapTotal','SwapFree']}
out['containers'] = command(['docker','--context','rootless','ps','--format','{{.Names}} {{.Status}}'])
out['linger'] = command(['loginctl','show-user','leofuso','-p','Linger'])
out['backup_timer'] = command(['systemctl','is-enabled','blaine-partial-backup.timer'])
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(out, indent=2)+'\n')
print('Evidence written:', a.output)
