#!/usr/bin/env python3
"""Bounded root handoff: sanitized inventory and private copies, never cutover.

No writes to source secrets/data. Destination writes run after dropping root.
No Docker socket use, database operations, service control, or secret output.
"""
from collections import Counter
import json
import os
from pathlib import Path
import pwd
import stat
import subprocess
import sys

NAMES = ('infrastructure.json', 'object-storage.json', 'clickhouse.env', 'langfuse.env')


def materialize(root, values):
    """Runs as the operator; immutable existing files must match exactly."""
    root = Path(root)
    if root.resolve() != root:
        raise RuntimeError('symlink destination')
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    s = root.stat()
    if s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) != 0o700:
        raise RuntimeError('destination must be operator-owned 0700')
    if set(values) != set(NAMES):
        raise RuntimeError('unexpected secret file set')
    for name in NAMES:
        path = root / name
        if path.is_symlink():
            raise RuntimeError('symlink file')
        if path.exists():
            s = path.stat()
            if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or stat.S_IMODE(s.st_mode) not in (0o400, 0o600):
                raise RuntimeError('unsafe existing file')
            if path.read_text() != values[name]:
                raise RuntimeError('existing secret differs; refusing overwrite')
    for name in NAMES:
        path = root / name
        if not path.exists():
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400 if name == 'object-storage.json' else 0o600)
            with os.fdopen(fd, 'w') as f:
                f.write(values[name])
                f.flush()
                os.fsync(f.fileno())


def inventory(path):
    p = Path(path)
    if p.resolve() != p:
        raise RuntimeError('symlink source')
    if not p.is_dir():
        raise RuntimeError('missing source data directory')
    owners, modes = Counter(), Counter()
    count = size = 0
    device = os.stat('/').st_dev
    for base, dirs, files in os.walk(p):
        for name in ['.', *dirs, *files]:
            q = Path(base) / name
            s = q.lstat()
            if s.st_dev != device:
                raise RuntimeError('unexpected filesystem requires review')
            if name in dirs and not stat.S_ISLNK(s.st_mode):
                continue  # counted when visited as '.'
            owners[f'{s.st_uid}:{s.st_gid}'] += 1
            modes[oct(stat.S_IMODE(s.st_mode))] += 1
            count += 1
            if stat.S_ISREG(s.st_mode):
                size += s.st_size
    return {'entries': count, 'regular_file_bytes': size, 'owners': dict(owners), 'modes': dict(modes)}


def main():
    if sys.argv[1:] == ['--receive']:
        if os.geteuid() == 0:
            raise RuntimeError('receiver must be unprivileged')
        account = pwd.getpwuid(os.getuid())
        materialize(Path(account.pw_dir) / '.config/blaine/secrets', json.load(sys.stdin))
        return
    if sys.argv[1:] or os.geteuid() != 0:
        raise RuntimeError('run with bounded sudo, no arguments')
    account = pwd.getpwnam('leofuso')
    if account.pw_uid != 1000 or account.pw_dir != '/home/leofuso':
        raise RuntimeError('operator identity changed; review mapping')
    values, metadata = {}, {}
    source = Path('/etc/blaine/secrets')
    s = source.stat()
    if source.resolve() != source or s.st_uid != 0 or stat.S_IMODE(s.st_mode) != 0o700:
        raise RuntimeError('source secret directory must remain root-owned 0700')
    for name in NAMES:
        p = Path('/etc/blaine/secrets') / name
        if p.resolve() != p:
            raise RuntimeError('symlink source secret')
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd) as f:
            s = os.fstat(f.fileno())
            if not stat.S_ISREG(s.st_mode) or stat.S_IMODE(s.st_mode) not in (0o400, 0o600):
                raise RuntimeError('unexpected source secret permissions')
            values[name] = f.read()
            metadata[name] = {'uid': s.st_uid, 'gid': s.st_gid, 'mode': oct(stat.S_IMODE(s.st_mode))}
    data = {p: inventory(p) for p in ['/srv/blaine/infra/objects', '/srv/blaine/infra/clickhouse/data', '/srv/blaine/infra/clickhouse/logs']}
    result = subprocess.run(['/usr/bin/python3', str(Path(__file__).resolve()), '--receive'],
                            input=json.dumps(values), text=True, capture_output=True,
                            user=account.pw_uid, group=account.pw_gid, extra_groups=[], cwd='/tmp')
    if result.returncode:
        raise RuntimeError('private copy failed; values and child output suppressed')
    print(json.dumps({'source_secret_metadata': metadata, 'source_data_inventory': data,
                      'private_secret_copy': 'PASS', 'source_data_mutated': False,
                      'cutover': 'NOT PERFORMED'}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('STOP: inventory/private materialization failed; no credential diagnostics emitted') from None
