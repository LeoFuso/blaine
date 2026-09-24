#!/usr/bin/env python3
"""Bounded root-only offline copy. Never stops services or changes source data.

Requires full candidate evidence, stopped rootful Blaine, fresh destination leaves,
and the observed namespace mapping. Preserves all source data for rollback.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[2]
DEST = Path('/home/leofuso/.local/share/blaine/infra')


def paths(root):
    yield root
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in sorted(dirs + files):
            yield Path(base) / name


def fingerprint(root, uid, gid, device=None):
    digest = hashlib.sha256()
    count = size = 0
    if device is None:
        device = os.stat('/').st_dev
    for path in sorted(paths(root)):
        s = path.lstat()
        if s.st_uid != uid or s.st_gid != gid or s.st_dev != device:
            raise RuntimeError('unexpected source/destination ownership or filesystem')
        rel = str(path.relative_to(root))
        digest.update(json.dumps([rel, stat.S_IFMT(s.st_mode), stat.S_IMODE(s.st_mode)]).encode())
        if stat.S_ISLNK(s.st_mode):
            link = os.readlink(path)
            if os.path.isabs(link) or not path.resolve().is_relative_to(root):
                raise RuntimeError('non-internal source symlink')
            digest.update(link.encode())
        elif stat.S_ISREG(s.st_mode):
            content = hashlib.sha256()
            with path.open('rb') as f:
                while chunk := f.read(1024 * 1024):
                    content.update(chunk)
            digest.update(content.digest())
            size += s.st_size
        elif not stat.S_ISDIR(s.st_mode):
            raise RuntimeError('unexpected special file')
        count += 1
    return {'sha256': digest.hexdigest(), 'entries': count, 'bytes': size}


def main():
    if os.geteuid() != 0:
        raise RuntimeError('bounded sudo required')
    candidate = json.loads((ROOT / 'experiments/d1-rootless-docker-adoption/evidence/full-candidate.json').read_text())
    if candidate['status'] != 'PASS':
        raise RuntimeError('full candidate PASS required')
    active = subprocess.run(['systemctl', 'is-active', '--quiet', 'blaine-infra.service']).returncode
    if active == 0:
        raise RuntimeError('rootful owner still active')
    endpoint = subprocess.check_output(['docker', 'context', 'inspect', 'default', '--format', '{{.Endpoints.docker.Host}}'], text=True).strip()
    if endpoint != 'unix:///var/run/docker.sock':
        raise RuntimeError('unexpected legacy endpoint')
    running = subprocess.check_output(['docker', '--context', 'default', 'ps', '-q', '--filter', 'label=com.docker.compose.project=blaine-infra'], text=True).strip()
    if running:
        raise RuntimeError('rootful Blaine containers still running')
    pids = subprocess.check_output(['pgrep', '-u', '1000', '-x', 'dockerd'], text=True).split()
    if len(pids) != 1:
        raise RuntimeError('ambiguous rootless daemon')
    for name in ['uid_map', 'gid_map']:
        mapping = [list(map(int, line.split())) for line in Path('/proc', pids[0], name).read_text().splitlines()]
        if mapping != [[0, 1000, 1], [1, 100000, 65536]]:
            raise RuntimeError('namespace mapping changed')
    if DEST.resolve() != DEST or DEST.stat().st_uid != 1000 or stat.S_IMODE(DEST.stat().st_mode) != 0o700:
        raise RuntimeError('unsafe destination parent')
    specs = [('objects', 1000, 1000), ('clickhouse/data', 101, 100100), ('clickhouse/logs', 101, 100100)]
    if any((DEST / name).exists() or (DEST / name).is_symlink() for name, _, _ in specs):
        raise RuntimeError('destination leaves exist; never overwrite retained state')
    srcs = {}
    for name, uid, _ in specs:
        src = Path('/srv/blaine/infra') / name
        if src.resolve() != src:
            raise RuntimeError('source root symlink')
        srcs[name] = fingerprint(src, uid, uid)
    parent = DEST / 'clickhouse'
    if parent.exists() or parent.is_symlink():
        raise RuntimeError('fresh clickhouse destination parent required')
    parent.mkdir(mode=0o700)
    os.chown(parent, 1000, 1000)
    report = {'status': 'INCOMPLETE', 'source_changed': False, 'copies': {}}
    for name, uid, mapped in specs:
        src, dst = Path('/srv/blaine/infra') / name, DEST / name
        shutil.copytree(src, dst, symlinks=True)
        for path in paths(dst):
            os.chown(path, mapped, mapped, follow_symlinks=False)
        copied = fingerprint(dst, mapped, mapped)
        source_after = fingerprint(src, uid, uid)
        if copied != srcs[name] or source_after != srcs[name]:
            raise RuntimeError('copy/source fingerprint mismatch; stop and retain both trees')
        report['copies'][name] = {'source': srcs[name], 'destination': copied, 'host_uid_gid': mapped}
    report['status'] = 'PASS'
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('STOP: offline copy refused or failed; both trees retained, source not modified') from None
