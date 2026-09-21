#!/usr/bin/env python3
"""Read-only rootless activation checks; never display credentials."""
import json
import os
from pathlib import Path
import socket
import stat
import subprocess


def private(path, directory=False):
    p = Path(path)
    if p.resolve() != p:
        raise RuntimeError('STOP: symlink in private runtime path')
    s = p.stat()
    if s.st_uid != os.getuid() or s.st_mode & 0o077:
        raise RuntimeError('STOP: runtime config must be private and operator-owned')
    if directory != stat.S_ISDIR(s.st_mode):
        raise RuntimeError('STOP: unexpected runtime path type')
    if not directory and not stat.S_ISREG(s.st_mode):
        raise RuntimeError('STOP: expected regular runtime file')


def daemon():
    if os.getuid() == 0:
        raise RuntimeError('STOP: run as the normal operator')
    endpoint = subprocess.check_output(
        ['docker', 'context', 'inspect', 'rootless', '--format', '{{.Endpoints.docker.Host}}'], text=True).strip()
    if endpoint != f'unix:///run/user/{os.getuid()}/docker.sock':
        raise RuntimeError('STOP: unexpected rootless endpoint')
    options = json.loads(subprocess.check_output(
        ['docker', '--context', 'rootless', 'info', '--format', '{{json .SecurityOptions}}'], text=True))
    if 'name=rootless' not in options:
        raise RuntimeError('STOP: daemon is not rootless')


def main():
    daemon()
    root = Path(os.environ['BLAINE_SECRET_DIR'])
    private(root, directory=True)
    for name in ['infrastructure.json', 'object-storage.json', 'clickhouse.env', 'langfuse.env']:
        private(root / name)
    # User units cannot order against native system-manager services. Bounded
    # Compose readiness follows these probes; a failed boot is visible, not hidden.
    for port in [5432, 6379]:
        with socket.create_connection(('127.0.0.1', port), timeout=5):
            pass
    print('PASS: rootless daemon, private secrets, native dependency TCP readiness')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('STOP: rootless preflight failed; inspect daemon, private file metadata and native dependencies') from None
