#!/usr/bin/env python3
"""Reconcile only the bounded platform block; retain every byte of the active base."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile
import time
from urllib.request import urlopen

BEGIN = '// BEGIN BLAINE GPU VLLM TELEMETRY\n'
END = '// END BLAINE GPU VLLM TELEMETRY\n'


def compose(current, fragment):
    if current.count(BEGIN) != current.count(END) or current.count(BEGIN) > 1:
        raise ValueError('Malformed platform telemetry ownership markers')
    if BEGIN in current:
        before, owned = current.split(BEGIN)
        _, after = owned.split(END)
    else:
        before, after = current, ''
    base = before + after
    if base.count('prometheus.remote_write "grafana_metrics"') != 1 or 'otelcol.receiver.prometheus "local"' not in base:
        raise ValueError('Accepted metrics integration points unavailable')
    if any(token in base for token in ['prometheus.scrape "vllm"', 'prometheus.scrape "gpu"', 'remotecfg {']):
        raise ValueError('Conflicting scrape ownership or Fleet activation; stop for review')
    return before + BEGIN + fragment.rstrip() + '\n' + END + after


def atomic(path, data):
    assert path.resolve() == path, 'Refuse redirected config path'
    fd, name = tempfile.mkstemp(prefix='.platform-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o644)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    active = Path('/etc/alloy/config.alloy')
    fragment = Path('/etc/blaine/infra/platform-telemetry.alloy')
    assert os.geteuid() == 0
    assert active.resolve() == active and fragment.resolve() == fragment
    original = active.read_text()
    desired = compose(original, fragment.read_text())
    candidate = Path('/etc/alloy/blaine-platform-candidate.alloy')
    atomic(candidate, desired)
    try:
        result = subprocess.run(['alloy', 'validate', '--stability.level=public-preview', str(candidate)], capture_output=True)
        if result.returncode:
            raise RuntimeError('Alloy validation failed; active config unchanged; diagnostics suppressed')
        if original == desired:
            print('UNCHANGED; Alloy validation passed')
            return
        if not args.apply:
            print('CHANGE REQUIRED; Alloy validation passed; no activation')
            return
        assert active.read_text() == original, 'Concurrent Alloy edit detected; not overwriting'
        atomic(Path('/etc/alloy/blaine-before-platform.alloy'), original)
        atomic(active, desired)
        try:
            subprocess.run(['systemctl', 'restart', 'alloy'], check=True, capture_output=True, timeout=60)
            for attempt in range(20):
                try:
                    with urlopen('http://127.0.0.1:12345/-/ready', timeout=2) as response:
                        assert response.status == 200
                    break
                except Exception:
                    if attempt == 19:
                        raise
                    time.sleep(0.5)
        except Exception:
            # Never overwrite an intervening edit when restoring this transaction.
            if active.read_text() == desired:
                atomic(active, original)
                subprocess.run(['systemctl', 'restart', 'alloy'], check=True, capture_output=True, timeout=60)
            raise RuntimeError('Alloy activation failed; restoration attempted if still owned') from None
        print('CHANGED; Alloy validation, restart and readiness passed')
    finally:
        candidate.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
