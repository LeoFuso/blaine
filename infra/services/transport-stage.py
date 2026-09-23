#!/usr/bin/env python3
"""Stage the private edge in existing user-service paths; never control services.

Explicitly adopts the candidate's existing pinned key. No new key, credentials,
runtime state, network rule, package installation or durable service mutation.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile

UNIT = 'blaine-hub-transport.service'


def regular(path, private=False):
    if path.resolve() != path:
        raise ValueError('redirected source or target')
    s = path.stat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_nlink != 1:
        raise ValueError('unsafe file ownership/type')
    if private and stat.S_IMODE(s.st_mode) & 0o077:
        raise ValueError('private file required')
    return path.read_bytes()


def directory(path):
    if path.resolve() != path:
        raise ValueError('redirected destination')
    if not path.exists():
        directory(path.parent)
        path.mkdir(mode=0o700)
    if path.stat().st_uid != os.getuid() or not path.is_dir() or path.stat().st_mode & 0o022:
        raise ValueError('user-owned directory required')


def install(path, data, mode=0o600, immutable=False):
    directory(path.parent)
    if path.is_symlink():
        raise ValueError('redirected file')
    if path.exists():
        old = regular(path, private=True)
        if old == data and stat.S_IMODE(path.stat().st_mode) == mode:
            return
        if immutable:
            raise ValueError('existing immutable content differs')
    fd, tmp = tempfile.mkstemp(prefix='.transport-stage-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as f:
            os.fchmod(f.fileno(), mode)
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def stage(repo, binary, candidate, home, commit):
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('exact source commit required')
    def git(*args):
        return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.DEVNULL)
    if git('rev-parse', 'HEAD').decode().strip() != commit:
        raise ValueError('source commit mismatch')
    git('diff', '--exit-code', commit, '--', 'runtime', 'client', 'infra/services/transport-stage.py',
        'infra/systemd/user/' + UNIT)
    cfg = json.loads(regular(candidate, private=True))
    fields = {'listen', 'key_file', 'python', 'repository', 'readiness_file', 'deployment_file', 'principal_id', 'allowed_nodes'}
    if set(cfg) != fields or not cfg['allowed_nodes'] or not cfg['principal_id']:
        raise ValueError('explicit candidate policy required')
    for k in ('key_file', 'python', 'repository', 'readiness_file', 'deployment_file'):
        if not Path(cfg[k]).is_absolute():
            raise ValueError('absolute deployment paths required')
    key = regular(Path(cfg['key_file']), private=True)
    if len(key) != 32:
        raise ValueError('invalid existing key')
    executable = regular(binary)
    if not executable.startswith(b'\x7fELF'):
        raise ValueError('Linux host executable required')
    readiness = regular(Path(cfg['readiness_file']), private=True)
    json.loads(readiness)
    base = home / '.local/share/blaine/transport'
    config = home / '.config/blaine/services'
    release = base / 'releases' / commit
    key_path = base / 'hub.key'
    # Validate any existing key before installing other material. Never rotate pins.
    if key_path.exists() or key_path.is_symlink():
        if regular(key_path, private=True) != key:
            raise ValueError('existing Hub identity differs')
    for path in (base, config, release, home / '.config/systemd/user'):
        if path.resolve() != path:
            raise ValueError('redirected installation')
    if (config / 'transport.json').exists():
        old = json.loads(regular(config / 'transport.json', private=True))
        if any(old[k] != cfg[k] for k in ('listen', 'principal_id', 'allowed_nodes', 'deployment_file', 'python')):
            raise ValueError('deployment policy drift requires explicit review')
    files, content = {}, {}
    for raw in git('ls-tree', '-r', '--name-only', '-z', commit, '--', 'runtime').split(b'\0'):
        if not raw:
            continue
        name = raw.decode()
        data = git('show', commit + ':' + name)
        files[name] = hashlib.sha256(data).hexdigest()
        content[name] = data
    receipt = {'source_commit': commit, 'binary_sha256': hashlib.sha256(executable).hexdigest(),
               'runtime_files': files, 'unit': UNIT, 'key_adopted_without_rotation': True,
               'services_started_or_restarted': False}
    receipt_bytes = (json.dumps(receipt, indent=2) + '\n').encode()
    if (release / 'deployment.json').exists():
        if regular(release / 'deployment.json', private=True) != receipt_bytes:
            raise ValueError('source release content differs')
    for name, data in content.items():
        install(release / 'app' / name, data, immutable=True)
    install(key_path, key, immutable=True)
    install(config / 'transport-readiness.json', readiness)
    install(base / 'bin/blaine-hub-transport', executable, mode=0o700)
    cfg.update(key_file=str(key_path), repository=str(release / 'app'),
               readiness_file=str(config / 'transport-readiness.json'))
    install(config / 'transport.json', (json.dumps(cfg, indent=2) + '\n').encode())
    install(home / '.config/systemd/user' / UNIT, git('show', commit + ':infra/systemd/user/' + UNIT))
    install(release / 'deployment.json', receipt_bytes, immutable=True)
    return {k: receipt[k] for k in ('source_commit', 'binary_sha256', 'unit', 'key_adopted_without_rotation', 'services_started_or_restarted')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--binary', type=Path, required=True)
    parser.add_argument('--candidate-config', type=Path, required=True)
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    if os.geteuid() == 0:
        raise ValueError('run as the existing non-root service owner')
    print(json.dumps(stage(args.repository.resolve(), args.binary.absolute(), args.candidate_config.absolute(),
                           Path.home(), args.commit)))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError):
        raise SystemExit('STOP: transport staging validation failed; private data suppressed') from None
