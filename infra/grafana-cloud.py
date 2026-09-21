#!/usr/bin/env python3
"""Operator-controlled Bitwarden -> root-only env -> explicit Alloy activation."""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import urlsplit

FIELDS = ('GRAFANA_CLOUD_OTLP_ENDPOINT', 'GRAFANA_CLOUD_OTLP_USERNAME', 'GRAFANA_CLOUD_OTLP_API_KEY')
ITEM = 'Blaine / Grafana Cloud'
ENV_FILE = Path('/etc/blaine/secrets/grafana-cloud.env')
FLEET_FIELDS = ('GRAFANA_CLOUD_FM_URL', 'GRAFANA_CLOUD_FM_INSTANCE_ID', 'GRAFANA_CLOUD_FM_API_KEY')
FLEET_PROJECT = 'ac68b692-2150-45da-ab69-b4ca0085935a'
FLEET_ENV_FILE = Path('/etc/blaine/secrets/grafana-fleet.env')


def validate_fleet(values):
    if set(values) != set(FLEET_FIELDS):
        raise ValueError('Exactly the three Fleet fields are required')
    for value in values.values():
        if not isinstance(value, str) or not value or re.search(r'[\s\x00"\'`$\\]', value):
            raise ValueError('Invalid Fleet environment value')
    if values[FLEET_FIELDS[0]] != 'https://fleet-management-prod-015.grafana.net':
        raise ValueError('Fleet endpoint differs from the accepted stack')
    if values[FLEET_FIELDS[1]] != '1838998':
        raise ValueError('Fleet instance differs from the accepted Fleet identity')
    token = values[FLEET_FIELDS[2]]
    if len(token) < 20 or any(x in token.lower() for x in ('placeholder', 'replace', 'changeme')):
        raise ValueError('Fleet token is missing or a placeholder')
    return values


def fleet_from_bws():
    # The bootstrap token stays only in memory and the short-lived BWS child env.
    keyring = subprocess.run(['secret-tool', 'lookup', 'service', 'leofuso-lab',
                              'credential', 'bws-access-token'], capture_output=True, text=True, timeout=15)
    if keyring.returncode or not keyring.stdout.strip():
        raise RuntimeError('GNOME Keyring bootstrap unavailable; diagnostics suppressed')
    env = dict(os.environ, BWS_ACCESS_TOKEN=keyring.stdout.strip())
    result = subprocess.run(['/usr/local/bin/bws', 'secret', 'list', FLEET_PROJECT],
                            env=env, capture_output=True, text=True, timeout=45)
    if result.returncode:
        raise RuntimeError('BWS project read failed; diagnostics suppressed')
    rows = [row for row in json.loads(result.stdout) if row.get('key') in FLEET_FIELDS]
    if len(rows) != 3 or len({row['key'] for row in rows}) != 3:
        raise RuntimeError('Fleet fields absent or duplicated in the selected BWS project')
    return validate_fleet({row['key']: row['value'] for row in rows})



def validate(values):
    if set(values) != set(FIELDS):
        raise ValueError('Exactly the three Grafana Cloud fields are required')
    for value in values.values():
        if not isinstance(value, str) or not value or re.search(r'[\s\x00"\'`$\\]', value) or any(x in value.lower() for x in ('placeholder', 'replace', 'changeme', 'example')):
            raise ValueError('Empty, placeholder, or unsafe environment value; exporter remains inactive')
    u = urlsplit(values[FIELDS[0]])
    if u.scheme != 'https' or not u.hostname or not u.hostname.endswith('.grafana.net') or u.username or u.password or u.query or u.fragment or u.path.rstrip('/') != '/otlp':
        raise ValueError('Expected the HTTPS Grafana Cloud OTLP gateway base endpoint ending /otlp')
    if not values[FIELDS[1]].isdigit() or len(values[FIELDS[2]]) < 20:
        raise ValueError('Expected numeric OTLP instance identifier and a real scoped token')
    return values


def bw(*args):
    p = subprocess.run(['bw', *args], text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError('Bitwarden operation failed; no vault output displayed')
    return json.loads(p.stdout)


def atomic(path, data, mode):
    if path.is_symlink() or path.parent.is_symlink():
        raise RuntimeError('Refusing symlink secret/config destination')
    fd, name = tempfile.mkstemp(prefix='.blaine-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['status', 'placeholder', 'materialize', 'write-env', 'activate', 'deactivate', 'materialize-fleet', 'write-fleet-env', 'activate-fleet'])
    action = p.parse_args().action
    if action == 'activate-fleet':
        raise RuntimeError('STOP: Alloy 1.19.2 native Fleet registration failure prevents local startup; offline-start acceptance is required before activation')
    if action == 'materialize-fleet':
        values = fleet_from_bws()
        subprocess.run(['sudo', '-n', '/usr/bin/python3', '/usr/local/lib/blaine/grafana-cloud.py', 'write-fleet-env'],
                       input=json.dumps(values), text=True, check=True)
        return
    if action in ('status', 'placeholder', 'materialize'):
        status = bw('status')['status']
        if action == 'status':
            print('Bitwarden vault status: ' + status)
            return
        if status != 'unlocked':
            raise RuntimeError('Vault is not authenticated and unlocked; use bw login/bw unlock locally')
        if action == 'placeholder':
            # Get only this item, never enumerate or dump the vault.
            existing = subprocess.run(['bw', 'get', 'item', ITEM], capture_output=True, text=True)
            if existing.returncode == 0:
                print('Named item already exists; unchanged.')
                return
            if existing.stderr.strip() != 'Not found.':
                raise RuntimeError('Could not establish item absence; no item created')
            item = {'type': 2, 'name': ITEM, 'secureNote': {'type': 0},
                    'fields': [{'name': k, 'value': 'REPLACE_ME_NOT_ACTIVE', 'type': 1 if k.endswith('API_KEY') else 0} for k in FIELDS]}
            bw('create', 'item', base64.b64encode(json.dumps(item).encode()).decode())
            print('Placeholder item created; exporter inactive.')
            return
        item = bw('get', 'item', ITEM)
        values = validate({f['name']: f['value'] for f in item.get('fields', []) if f['name'] in FIELDS})
        # BW_SESSION remains solely in this operator process; sudo receives selected fields on stdin.
        subprocess.run(['sudo', '-n', '/usr/bin/python3', '/usr/local/lib/blaine/grafana-cloud.py', 'write-env'],
                       input=json.dumps(values), text=True, check=True)
        return
    if os.geteuid() != 0:
        raise RuntimeError('This action requires bounded sudo')
    if action in ('write-env', 'write-fleet-env'):
        if action == 'write-fleet-env':
            values = validate_fleet(json.load(sys.stdin))
            destination, fields = FLEET_ENV_FILE, FLEET_FIELDS
        else:
            values = validate(json.load(sys.stdin))
            destination, fields = ENV_FILE, FIELDS
        parent = destination.parent
        if parent.resolve() != parent or (parent.exists() and (parent.stat().st_uid != 0 or parent.stat().st_mode & 0o077)):
            raise RuntimeError('Runtime secret directory must be private and root-owned')
        ENV_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        atomic(destination, ''.join(f'{k}={values[k]}\n' for k in fields), 0o600)
        print('Runtime environment materialized; exporter remains inactive.')
        return
    base = Path('/etc/blaine/infra/alloy-local.alloy').read_text()
    env = os.environ.copy()
    if action == 'activate':
        if ENV_FILE.is_symlink() or ENV_FILE.stat().st_mode & 0o077 or ENV_FILE.stat().st_uid != 0:
            raise RuntimeError('Runtime secret file must be root-owned mode 0600')
        values = validate(dict(line.split('=', 1) for line in ENV_FILE.read_text().splitlines() if line))
        env.update(values)
        base = base.replace('[otelcol.exporter.file.local.input]', '[otelcol.exporter.file.local.input, otelcol.exporter.otlphttp.grafana_cloud.input]')
        base += '\n' + Path('/etc/blaine/infra/cloud.alloy.inactive').read_text()
    candidate = Path('/etc/alloy/blaine-candidate.alloy')
    atomic(candidate, base, 0o644)
    result = subprocess.run(['alloy', 'validate', '--stability.level=public-preview', str(candidate)], env=env, capture_output=True)
    if result.returncode:
        candidate.unlink()
        raise RuntimeError('Candidate validation failed; active config unchanged; output suppressed')
    os.replace(candidate, '/etc/alloy/config.alloy')
    subprocess.run(['systemctl', 'restart', 'alloy'], check=True)
    marker = Path('/etc/blaine/infra/cloud.enabled')
    if action == 'activate':
        atomic(marker, 'Explicit operator activation; delivery verification required.\n', 0o600)
    else:
        marker.unlink(missing_ok=True)
    print('Exporter activation applied; delivery must be verified.' if action == 'activate' else 'Remote exporter inactive; local telemetry retained.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
