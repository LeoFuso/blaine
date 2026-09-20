#!/usr/bin/env python3
"""Local secret creation and native dependency preparation; never print secrets."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile

ROOT = Path('/etc/blaine/secrets')
CHANGED = False


def private_write(path, text, mode=0o600):
    global CHANGED
    if path.is_symlink():
        raise RuntimeError('Refusing a symlink destination')
    if path.exists() and path.read_text() == text and path.stat().st_mode & 0o777 == mode:
        return
    CHANGED = True
    fd, name = tempfile.mkstemp(prefix='.blaine-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def pg(sql):
    # Native peer authentication; no shell, credential arguments, or service changes.
    p = subprocess.run(['/usr/bin/psql', '-XAt', '-v', 'ON_ERROR_STOP=1', '-d', 'postgres'],
                       input=sql, text=True, capture_output=True, user='postgres',
                       group='postgres', extra_groups=[], cwd='/tmp')
    if p.returncode:
        raise RuntimeError('Native PostgreSQL setup failed; SQL/credentials suppressed')
    return p.stdout.strip()


def initialize():
    if os.geteuid() != 0:
        raise RuntimeError('Requires bounded sudo')
    if ROOT.is_symlink():
        raise RuntimeError('Refusing symlink secret directory')
    ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    ROOT.chmod(0o700)
    marker = ROOT / 'infrastructure.json'
    if not marker.exists():
        if pg("SELECT rolname FROM pg_roles WHERE rolname='blaine_langfuse';") or pg("SELECT datname FROM pg_database WHERE datname='blaine_langfuse';"):
            raise RuntimeError('STOP: existing unmanaged Langfuse database/role')
        p = subprocess.run(['redis-cli', '-n', '15', 'DBSIZE'], capture_output=True, text=True, check=True)
        if p.stdout.strip() != '0':
            raise RuntimeError('STOP: Redis DB 15 is occupied; choose a free logical namespace')
        s = {k: secrets.token_hex(32) for k in ['postgres_password', 'clickhouse_password',
             'salt', 'encryption_key', 'nextauth_secret', 'admin_password', 'project_secret',
             's3_admin_secret', 's3_blaine_secret', 's3_langfuse_secret']}
        s.update({k: secrets.token_hex(12) for k in ['s3_admin_key', 's3_blaine_key', 's3_langfuse_key', 'project_public']})
        private_write(marker, json.dumps(s) + '\n')
    s = json.loads(marker.read_text())
    if not pg("SELECT rolname FROM pg_roles WHERE rolname='blaine_langfuse';"):
        pg("CREATE ROLE blaine_langfuse LOGIN PASSWORD '" + s['postgres_password'] + "';")
    owner = pg("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='blaine_langfuse';")
    if owner and owner != 'blaine_langfuse':
        raise RuntimeError('STOP: unexpected existing database owner')
    if not owner:
        pg('CREATE DATABASE blaine_langfuse OWNER blaine_langfuse;')
    pg("ALTER DATABASE blaine_langfuse SET timezone TO 'UTC';")
    identities = []
    for consumer, actions in [('admin', ['Admin', 'Read', 'Write', 'List', 'Tagging']),
                              ('blaine', ['Read:blaine-artifacts', 'Write:blaine-artifacts', 'List:blaine-artifacts', 'Tagging:blaine-artifacts']),
                              ('langfuse', [f'{action}:{bucket}' for action in ['Read', 'Write', 'List', 'Tagging'] for bucket in ['langfuse-events', 'langfuse-media']])]:
        identities.append({'name': consumer, 'credentials': [{'accessKey': s[f's3_{consumer}_key'],
                           'secretKey': s[f's3_{consumer}_secret']}], 'actions': actions})
    private_write(ROOT / 'object-storage.json', json.dumps({'identities': identities}) + '\n', 0o400)
    # Image runs directly as its service UID; host parent remains root-only 0700.
    os.chown(ROOT / 'object-storage.json', 1000, 1000)
    ch = {'CLICKHOUSE_DB': 'langfuse', 'CLICKHOUSE_USER': 'langfuse', 'CLICKHOUSE_PASSWORD': s['clickhouse_password']}
    private_write(ROOT / 'clickhouse.env', ''.join(f'{k}={v}\n' for k, v in ch.items()))
    env = {
        'DATABASE_URL': f"postgresql://blaine_langfuse:{s['postgres_password']}@127.0.0.1:5432/blaine_langfuse",
        'NEXTAUTH_URL': 'http://127.0.0.1:3000', 'NEXTAUTH_SECRET': s['nextauth_secret'],
        'SALT': s['salt'], 'ENCRYPTION_KEY': s['encryption_key'], 'TELEMETRY_ENABLED': 'false',
        'NEXT_TELEMETRY_DISABLED': '1', 'LANGFUSE_IN_APP_AGENT_ENABLED': 'false',
        'LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES': 'false', 'AUTH_DISABLE_SIGNUP': 'true',
        'CLICKHOUSE_MIGRATION_URL': 'clickhouse://127.0.0.1:9000',
        'CLICKHOUSE_URL': 'http://127.0.0.1:8123', 'CLICKHOUSE_CLUSTER_ENABLED': 'false',
        **ch, 'REDIS_CONNECTION_STRING': 'redis://127.0.0.1:6379/15',
        'REDIS_KEY_PREFIX': 'blaine-langfuse', 'LANGFUSE_S3_BATCH_EXPORT_ENABLED': 'false',
        'LANGFUSE_INIT_ORG_ID': 'blaine-local', 'LANGFUSE_INIT_ORG_NAME': 'Blaine Local',
        'LANGFUSE_INIT_PROJECT_ID': 'blaine-synthetic', 'LANGFUSE_INIT_PROJECT_NAME': 'Synthetic acceptance only',
        'LANGFUSE_INIT_PROJECT_PUBLIC_KEY': 'pk-lf-' + s['project_public'],
        'LANGFUSE_INIT_PROJECT_SECRET_KEY': 'sk-lf-' + s['project_secret'],
        'LANGFUSE_INIT_USER_EMAIL': 'operator@blaine.invalid', 'LANGFUSE_INIT_USER_NAME': 'Local operator',
        'LANGFUSE_INIT_USER_PASSWORD': s['admin_password'],
    }
    for kind, bucket in [('EVENT', 'langfuse-events'), ('MEDIA', 'langfuse-media')]:
        for key, value in {'BUCKET': bucket, 'REGION': 'us-east-1', 'ENDPOINT': 'http://127.0.0.1:8333',
                           'ACCESS_KEY_ID': s['s3_langfuse_key'], 'SECRET_ACCESS_KEY': s['s3_langfuse_secret'],
                           'FORCE_PATH_STYLE': 'true'}.items():
            env[f'LANGFUSE_S3_{kind}_UPLOAD_{key}'] = value
    private_write(ROOT / 'langfuse.env', ''.join(f'{k}={v}\n' for k, v in env.items()))
    print('changed' if CHANGED else 'converged')


if __name__ == '__main__':
    try:
        initialize()
    except Exception as exc:
        raise SystemExit(str(exc)) from None
