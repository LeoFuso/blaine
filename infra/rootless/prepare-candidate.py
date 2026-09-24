#!/usr/bin/env python3
"""Stage independent rootless candidate config. Native candidate DB must exist.

No source writes, root actions, service starts or credential output.
"""
import json
import os
from pathlib import Path
import shutil
from urllib.parse import urlsplit, urlunsplit


def candidate_environment(source):
    env = dict(source)
    database = urlsplit(env['DATABASE_URL'])
    assert database.hostname == '127.0.0.1' and database.path == '/blaine_langfuse'
    env.update(DATABASE_URL=urlunsplit(database._replace(path='/blaine_rootless_candidate_20260921')),
               REDIS_CONNECTION_STRING='redis://127.0.0.1:16379/15', REDIS_KEY_PREFIX='blaine-rootless-candidate',
               NEXTAUTH_URL='http://127.0.0.1:13000', CLICKHOUSE_URL='http://127.0.0.1:18123',
               CLICKHOUSE_MIGRATION_URL='clickhouse://127.0.0.1:19000')
    for kind in ['EVENT', 'MEDIA']:
        env[f'LANGFUSE_S3_{kind}_UPLOAD_ENDPOINT'] = 'http://127.0.0.1:18333'
    return env


def main():
    os.umask(0o077)
    root = Path.home() / '.local/share/blaine/rootless-full-candidate-20260921'
    if root.exists():
        raise RuntimeError('candidate already exists; inspect before reuse')
    root.mkdir(mode=0o700)
    for name in ['secrets', 'state', 'state/objects', 'state/clickhouse', 'state/clickhouse/data', 'state/clickhouse/logs', 'redis']:
        (root / name).mkdir(mode=0o700)
    source = Path.home() / '.config/blaine/secrets'
    for name in ['infrastructure.json', 'object-storage.json', 'clickhouse.env']:
        shutil.copyfile(source / name, root / 'secrets' / name)
        (root / 'secrets' / name).chmod(0o400 if name == 'object-storage.json' else 0o600)
    env = candidate_environment(dict(line.split('=', 1) for line in (source / 'langfuse.env').read_text().splitlines() if line))
    (root / 'secrets/langfuse.env').write_text(''.join(f'{key}={value}\n' for key, value in env.items()))
    (root / 'compose.env').write_text(f'BLAINE_PROJECT=blaine-rootless-full-candidate\nBLAINE_STATE_DIR={root}/state\nBLAINE_SECRET_DIR={root}/secrets\nBLAINE_S3_PORT=18333\nBLAINE_CH_HTTP_PORT=18123\nBLAINE_CH_NATIVE_PORT=19000\nBLAINE_WEB_PORT=13000\nBLAINE_WORKER_PORT=13030\n')
    (root / 'redis.conf').write_text(f'bind 127.0.0.1\nport 16379\nprotected-mode yes\ndir {root}/redis\nappendonly yes\nmaxmemory-policy noeviction\ndaemonize no\n')
    print(json.dumps({'candidate_path': str(root), 'postgres_database': 'blaine_rootless_candidate_20260921',
                      'redis_port': 16379, 'production_mutated': False}))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('STOP: candidate config preparation failed; secret diagnostics suppressed') from None
