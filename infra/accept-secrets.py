#!/usr/bin/env python3
"""Acceptance for the secret-delivery standard. Prints state, never a value.

Two properties matter most and are checked by observation rather than by reading
the implementation: a consumer starts from its local credential alone, and a
consumer receives only the secrets declared for it.
"""
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('blaine_secrets', ROOT / 'secrets.py')
secrets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(secrets)

CONSUMER = 'jev'
PROBE = ('import json,os,sys;'
         'print(json.dumps({"declared_present": "TYPESAFE_API_KEY" in os.environ,'
         '"bootstrap_present": "BWS_ACCESS_TOKEN" in os.environ,'
         '"other_consumer_present": "GRAFANA_CLOUD_METRICS_API_KEY" in os.environ,'
         '"declared_length": len(os.environ.get("TYPESAFE_API_KEY",""))}))')


def blocked_tools(directory: Path) -> Path:
    """Shims that fail loudly, so any runtime secret-manager call is a failure."""
    directory.mkdir(parents=True, exist_ok=True)
    for name in ('secret-tool', 'bws'):
        shim = directory / name
        shim.write_text('#!/bin/sh\necho "RUNTIME SECRET MANAGER ACCESS" >&2\nexit 97\n')
        shim.chmod(0o700)
    return directory


def main() -> int:
    document = secrets.load_declarations()
    consumer, path = secrets.consumer_of(document, CONSUMER)
    report = {'version': 1, 'consumer': CONSUMER,
              'source_of_truth': document['source']['provider'],
              'remote_access_policy': document['source']['access'],
              'local_credential': secrets.inspect(path, consumer['secrets'])}
    with tempfile.TemporaryDirectory() as temporary:
        shims = blocked_tools(Path(temporary) / 'bin')
        # A startup that reaches Bitwarden or the keyring now fails with exit 97.
        environment = {'PATH': f'{shims}:/usr/bin:/bin', 'HOME': os.environ['HOME'],
                       'LANG': 'C.UTF-8', 'GRAFANA_CLOUD_METRICS_API_KEY': 'inherited-fixture-value',
                       'BWS_ACCESS_TOKEN': 'inherited-fixture-bootstrap'}
        result = subprocess.run([sys.executable, str(ROOT / 'secrets.py'), 'run', CONSUMER, '--',
                                 sys.executable, '-c', PROBE],
                                env=environment, capture_output=True, text=True, timeout=60)
        observed = json.loads(result.stdout) if result.returncode == 0 else {}
        report['boot_independence'] = {
            'secret_manager_tools': 'replaced by shims that fail with exit 97',
            'consumer_exit_code': result.returncode,
            'runtime_secret_manager_invoked': 'RUNTIME SECRET MANAGER ACCESS' in result.stderr,
            'interactive_session_required': False,
            'declared_credential_available': observed.get('declared_present'),
            'declared_credential_non_empty': bool(observed.get('declared_length')),
        }
        report['least_secret'] = {
            'bootstrap_token_reaches_consumer': observed.get('bootstrap_present'),
            'other_consumer_secret_reaches_consumer': observed.get('other_consumer_present'),
        }
    runtime_reads_remote = report['boot_independence']['runtime_secret_manager_invoked']
    report['outcome'] = 'PASS' if (
        report['local_credential']['safe']
        and report['boot_independence']['consumer_exit_code'] == 0
        and report['boot_independence']['declared_credential_available']
        and report['boot_independence']['declared_credential_non_empty']
        and not runtime_reads_remote
        and not report['least_secret']['bootstrap_token_reaches_consumer']
        and not report['least_secret']['other_consumer_secret_reaches_consumer']) else 'FAIL'
    report['values_printed'] = False
    (ROOT / 'validation-secret-delivery.json').write_text(json.dumps(report, indent=1) + '\n')
    print(json.dumps(report, indent=1))
    return 0 if report['outcome'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
