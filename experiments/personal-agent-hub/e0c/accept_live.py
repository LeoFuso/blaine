#!/usr/bin/env python3
"""Read-only development-host observations. Never contacts another tailnet device.

This is NOT second-workstation/remote ACP acceptance. It requires the already
authenticated development host `blaine`, and retains only selected observations.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from runtime.host_connection import readiness


def command(argv, **kwargs):
    return subprocess.run(argv, capture_output=True, timeout=15, **kwargs)


def network():
    result = command(['tailscale', 'status', '--json'])
    assert result.returncode == 0, 'local daemon unavailable'
    status = json.loads(result.stdout)
    assert status['BackendState'] == 'Running'
    own = status['Self']
    assert own['DNSName'].split('.')[0] == 'blaine', 'not the designated host'
    return own


def run(binary):
    before = network()
    known_hosts = Path.home()/'.ssh'/'known_hosts'
    native_trust_before = known_hosts.read_bytes() if known_hosts.exists() else None
    prefs_result = command(['tailscale', 'debug', 'prefs'])
    assert prefs_result.returncode == 0
    prefs = json.loads(prefs_result.stdout)
    own_addresses = set(before['TailscaleIPs'])
    short_resolved = {row[4][0] for row in socket.getaddrinfo('blaine', 22, type=socket.SOCK_STREAM)}
    qualified = before['DNSName'].rstrip('.')
    resolved = {row[4][0] for row in socket.getaddrinfo(qualified, 22, type=socket.SOCK_STREAM)}
    assert resolved and resolved.issubset(own_addresses), 'refuse to contact a different workstation'
    with socket.create_connection((qualified, 22), timeout=5) as connection:
        connection.settimeout(5)
        banner = connection.recv(256).decode('ascii').strip()
    result = {'observed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'tailscale_version': command(['tailscale','version']).stdout.decode().splitlines()[0],
              'target': {'host':'blaine','ssh_user':'leofuso'},
              'tailscale_ssh_enabled': prefs.get('RunSSH') is True,
              'short_name_resolves_to_own_tailnet': short_resolved.issubset(own_addresses),
              'qualified_magicdns_resolves_to_own_tailnet': True,
              'self_route_ssh_banner': banner,
              'self_route_is_remote_peer_proof': False,
              'second_workstation': 'PENDING: no device designated; no other device contacted'}
    with tempfile.TemporaryDirectory(prefix='blaine-e0c-live-') as temporary:
        base = Path(temporary)
        env = dict(os.environ, XDG_CONFIG_HOME=str(base/'config'), XDG_STATE_HOME=str(base/'state'))
        result['connect_attempts'] = []
        for _ in range(2):
            attempt = command([str(binary), 'connect', '--non-interactive', '--host', 'blaine'], env=env)
            assert attempt.returncode == 3
            assert b'REMOTE_UNAVAILABLE' in attempt.stderr and b'Host handshake verified' not in attempt.stdout
            assert not (base/'config').exists() and not (base/'state').exists()
            result['connect_attempts'].append({'exit_code':attempt.returncode,'state':'REMOTE_UNAVAILABLE','profile_persisted':False})
        doctor = command([str(binary), 'doctor', '--json'], env=env)
        report = json.loads(doctor.stdout)
        assert doctor.returncode == 2 and report['overall'] == 'NOT_READY'
        assert not (base/'config').exists() and not (base/'state').exists()
        result['doctor'] = {'exit_code':doctor.returncode,'overall':report['overall'],'read_only':True}
        # Copy the host boundary outside the checkout; no production installation.
        installed = base/'host-home'/'.local'/'bin'/'blaine-host-connection'
        installed.parent.mkdir(parents=True, mode=0o700)
        shutil.copy2(ROOT/'runtime/host_connection.py', installed)
        installed.chmod(0o700)
        spoof_env = dict(env, SSH_CONNECTION='100.64.0.2 123 100.64.0.1 22', BLAINE_PEER_ID='spoofed')
        attempts=[]
        for operation in ('handshake','acp'):
            attempt = command([str(installed),operation],env=spoof_env)
            assert attempt.returncode==2 and attempt.stdout==b'' and b'PEER_UNVERIFIED' in attempt.stderr
            attempts.append({'operation':operation,'exit_code':2,'stdout_bytes':0,'state':'PEER_UNVERIFIED'})
        result['local_host_boundary_processes'] = attempts
    result['readiness'] = readiness({'deployment_id':'dp_14peR41suUIf4mt0pR1oRy1',
                                    'generation_model':'nvidia/Qwen3.8-27B-NVFP4',
                                    'embeddings_model':'BAAI/bge-m3'})
    assert result['readiness']['mirix'] != 'PASS'
    after=network()
    result['network_unchanged'] = all(before.get(k)==after.get(k) for k in ('ID','PublicKey','TailscaleIPs','Online','DNSName'))
    assert result['network_unchanged']
    native_trust_after = known_hosts.read_bytes() if known_hosts.exists() else None
    result['ssh_known_hosts_unchanged'] = native_trust_before == native_trust_after
    after_prefs = command(['tailscale', 'debug', 'prefs'])
    assert after_prefs.returncode == 0
    result['tailscale_preferences_unchanged'] = prefs == json.loads(after_prefs.stdout)
    assert result['ssh_known_hosts_unchanged'] and result['tailscale_preferences_unchanged']
    result['result']='PARTIAL: local observations only; trusted second-peer binding and remote ACP remain pending'
    return result


if __name__ == '__main__':
    print(json.dumps(run(Path(sys.argv[1]).resolve()),indent=2))
