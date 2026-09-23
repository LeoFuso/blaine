#!/usr/bin/env python3
"""Run a command against a disposable Unix-socket-only PostgreSQL fixture.

No production database, ports, credentials, sudo or persistent service is used.
Requires the locally installed PostgreSQL tools (also present on Ubuntu CI).
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

def main():
    if os.geteuid() == 0 or len(sys.argv) < 2:
        raise SystemExit('Run as an ordinary user: with_postgres.py COMMAND [ARGS...]')
    bindir = Path(subprocess.check_output(['pg_config', '--bindir'], text=True).strip())
    with tempfile.TemporaryDirectory(prefix='blaine-registry-test-') as tmp:
        root = Path(tmp)
        data = root / 'data'
        subprocess.run([str(bindir/'initdb'), '-D', str(data), '--no-locale', '--encoding=UTF8',
                        '--auth-local=trust', '--auth-host=reject', '--username=fixture'],
                       check=True, stdout=subprocess.DEVNULL)
        subprocess.run([str(bindir/'pg_ctl'), '-D', str(data), '-l', str(root/'postgres.log'),
                        '-o', f"-h '' -k {root} -p 55432 -F", '-w', 'start'],
                       check=True, stdout=subprocess.DEVNULL)
        try:
            env = dict(os.environ, BLAINE_TEST_POSTGRES_DSN=f'host={root} port=55432 user=fixture dbname=postgres sslmode=disable')
            return subprocess.run(sys.argv[1:], env=env).returncode
        finally:
            subprocess.run([str(bindir/'pg_ctl'), '-D', str(data), '-m', 'immediate', '-w', 'stop'],
                           check=True, stdout=subprocess.DEVNULL)

if __name__ == '__main__':
    raise SystemExit(main())
