#!/usr/bin/env python3
"""Read-only E0.B acceptance. Never install/login/logout or contact a Blaine host.
Raw Tailscale JSON stays in memory; retain only an explicit privacy projection.
Requires an already authenticated native Linux workstation and strace.
"""
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

binary = Path(sys.argv[1]).resolve()

def native():
    result = subprocess.run(['tailscale', 'status', '--json'], capture_output=True, timeout=10)
    assert result.returncode == 0, 'Native status unavailable; raw diagnostics withheld'
    return json.loads(result.stdout)

def projection(status):
    version = status['Version']
    assert re.fullmatch(r'\d+\.\d+\.\d+(?:-t[0-9a-f]+-g[0-9a-f]+)?', version)
    return {'version': version, 'backend': status['BackendState'], 'tun': status['TUN'],
            'self_online': status['Self']['Online'], 'tailnet_visible': bool(status['CurrentTailnet']),
            'address_count': len(status['TailscaleIPs']), 'health_warning_count': len(status.get('Health') or [])}

before = native()
assert before['BackendState'] == 'Running' and before['Self']['Online'], 'Requires an already connected host'
with tempfile.TemporaryDirectory(prefix='blaine-e0b-live-') as directory:
    # Fresh client locations prove connect/doctor persist no Blaine state.
    env = dict(os.environ, XDG_CONFIG_HOME=directory+'/config', XDG_STATE_HOME=directory+'/state', XDG_RUNTIME_DIR='')
    def invoke(*args):
        return subprocess.run([str(binary), *args], env=env, capture_output=True, text=True, timeout=20)
    report_run = invoke('doctor', '--json')
    human = invoke('doctor')
    assert report_run.returncode == human.returncode == 2
    report = json.loads(report_run.stdout)
    assert report['overall'] == 'NOT_READY'
    checks = {c['id']: c for c in report['checks']}
    assert checks['tailscale']['status'] == 'PASS'
    for c in report['checks']:
        assert all(c[k] in human.stdout for k in ['id', 'status', 'code', 'summary', 'remediation'])
    assert not report_run.stderr and not human.stderr
    runs = []
    for args in [('connect',), ('connect', '--non-interactive')]:
        result = subprocess.run(['strace', '-f', '-e', 'trace=execve', '-s', '256', str(binary), *args],
                                env=env, capture_output=True, text=True, timeout=20)
        assert result.returncode == 0 and 'Network prerequisite ready.' in result.stdout
        executions = [line for line in result.stderr.splitlines() if 'execve(' in line]
        # Permit exactly the client and one read-only native status invocation.
        assert len(executions) == 2, 'Unexpected child process count'
        assert '"status", "--json"' in executions[1] and '/tailscale"' in executions[1]
        runs.append({'args': list(args), 'exit': result.returncode, 'stdout': result.stdout,
                     'external_commands': [['tailscale', 'status', '--json']], 'mutation_commands': 0})
    assert list(Path(directory).iterdir()) == [], 'Blaine wrote client state'
after = native()
assert before['Self']['ID'] == after['Self']['ID'], 'Device identity changed'
assert before['TailscaleIPs'] == after['TailscaleIPs'], 'Device addresses changed'
assert projection(before) == projection(after), 'Network state changed'
print(json.dumps({'result': 'PASS', 'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  'platform': {'os': sys.platform, 'kernel': os.uname().release, 'architecture': os.uname().machine,
                               'wsl': False, 'distribution': 'Ubuntu 26.04.1 LTS'},
                  'before': projection(before), 'after': projection(after),
                  'same_device_and_addresses': True, 'client_state_written': False,
                  'doctor_exit': report_run.returncode, 'doctor_json': report, 'doctor_human': human.stdout,
                  'connect_runs': runs, 'no_logout_or_tailnet_disruption': True}, indent=2))
