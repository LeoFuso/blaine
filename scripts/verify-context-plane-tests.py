#!/usr/bin/env python3
"""Retain bounded CP.1 and relevant kernel/D2 regression results (no platform suite)."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = ['test_kernel*.py', 'test_personal*.py', 'test_acp.py',
            'test_host_connection.py', 'test_direct_readiness.py']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    for index, pattern in enumerate(PATTERNS):
        command = [sys.executable, '-W', 'ignore::ResourceWarning', '-m', 'unittest',
                   'discover', '-s', 'tests', '-p', pattern, '-v']
        try:
            run = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60)
            output, code = run.stdout + run.stderr, run.returncode
        except subprocess.TimeoutExpired as error:
            output, code = (error.stdout or b'') + (error.stderr or b'') + b'\nTIMEOUT\n', 124
        name = f'suite-{index + 1}.txt'
        (args.output / name).write_bytes(output)
        results.append({'pattern': pattern, 'exit_code': code, 'log': name,
                        'sha256': hashlib.sha256(output).hexdigest()})
    files = [*sorted((ROOT / 'runtime/kernel').glob('*.py')), ROOT / 'tests/test_kernel_context_plane.py']
    summary = {'status': 'PASS' if all(r['exit_code'] == 0 for r in results) else 'FAIL',
               'suites': results, 'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'source_sha256'}, indent=2))
    if summary['status'] != 'PASS': raise SystemExit(1)


if __name__ == '__main__': main()
