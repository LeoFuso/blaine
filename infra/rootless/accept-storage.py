#!/usr/bin/env python3
"""Synthetic rootless storage compatibility only, NOT full migration acceptance.

Run as operator using Python with boto3. No live secrets or source data access.
Retains stopped candidate and private state; never deletes volumes or data.
"""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.request

BASE = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('preflight', Path(__file__).with_name('preflight.py'))
preflight = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preflight)


def run(args, env=None):
    p = subprocess.run(args, capture_output=True, text=True, env=env, timeout=420)
    if p.returncode:
        raise RuntimeError(f'command failed: {args[0]}; output suppressed')
    return p.stdout.strip()


def main():
    import boto3
    from botocore.config import Config
    preflight.daemon()
    # A daemon restart must not affect unrelated rootless containers.
    if run(['docker', '--context', 'rootless', 'ps', '-q']):
        raise RuntimeError('STOP: rootless containers already running')
    for port in (18333, 18123, 19000):
        import socket
        with socket.socket() as s:
            s.bind(('127.0.0.1', port))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root = Path.home() / '.local/share/blaine' / ('rootless-storage-candidate-' + stamp)
    root.mkdir(parents=True, mode=0o700)
    os.umask(0o077)
    sec = root / 'secrets'
    state = root / 'state'
    for p in (sec, state, state / 'objects', state / 'clickhouse', state / 'clickhouse/data', state / 'clickhouse/logs'):
        p.mkdir(mode=0o700)
    key, password = secrets.token_hex(12), secrets.token_hex(32)
    (sec / 'object-storage.json').write_text(json.dumps({'identities': [{'name': 'candidate', 'credentials': [{'accessKey': key, 'secretKey': password}], 'actions': ['Admin', 'Read', 'Write', 'List']}]}))
    (sec / 'object-storage.json').chmod(0o400)
    (sec / 'clickhouse.env').write_text(f'CLICKHOUSE_USER=candidate\nCLICKHOUSE_PASSWORD={password}\nCLICKHOUSE_DB=candidate\n')
    (sec / 'langfuse.env').write_text('')  # config parse only; NEVER start Langfuse against live dependencies
    env = dict(os.environ, BLAINE_PROJECT='blaine-rootless-storage-candidate', BLAINE_STATE_DIR=str(state),
               BLAINE_SECRET_DIR=str(sec), BLAINE_S3_PORT='18333', BLAINE_CH_HTTP_PORT='18123', BLAINE_CH_NATIVE_PORT='19000',
               BLAINE_WEB_PORT='13000', BLAINE_WORKER_PORT='13030')
    compose = ['docker', '--context', 'rootless', 'compose', '-f', str(BASE / 'infra/compose/rootless.yaml')]
    def mutate(args):
        preflight.daemon()
        return run(args, env)
    run([*compose, 'config', '--quiet'], env)
    # Only fresh empty candidate leaves, never /srv or production directories.
    mutate(['docker', '--context', 'rootless', 'run', '--rm', '--network', 'none', '--user', '0:0',
            '--cap-drop', 'ALL', '--cap-add', 'CHOWN', '--security-opt', 'no-new-privileges',
            '-v', f'{state}/clickhouse/data:/data', '-v', f'{state}/clickhouse/logs:/logs',
            '--entrypoint', '/bin/sh', 'chrislusf/seaweedfs:4.47', '-c', 'chown 101:101 /data /logs'])
    report = {'scope': 'synthetic storage compatibility; full candidate NOT RUN', 'state_path': str(root),
              'observed_at': stamp, 'checks': {}, 'status': 'INCOMPLETE'}
    evidence = BASE / 'experiments/d1-rootless-docker-adoption/evidence/storage-candidate.json'
    try:
        mutate([*compose, 'up', '-d', '--wait', '--wait-timeout', '180', 'object-storage', 'clickhouse'])
        client = boto3.client('s3', endpoint_url='http://127.0.0.1:18333', region_name='us-east-1',
                              aws_access_key_id=key, aws_secret_access_key=password,
                              config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))
        client.create_bucket(Bucket='rootless-candidate')
        body = b'Blaine D1 rootless isolated persistence probe\n'
        client.put_object(Bucket='rootless-candidate', Key='identity.txt', Body=body)
        def sql(q):
            req = urllib.request.Request('http://127.0.0.1:18123/', data=q.encode(),
                                         headers={'X-ClickHouse-User': 'candidate', 'X-ClickHouse-Key': password})
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.read().decode().strip()
        sql('CREATE TABLE candidate.persistence (id String) ENGINE=MergeTree ORDER BY id')
        sql("INSERT INTO candidate.persistence VALUES ('rootless-storage-identity')")
        def check():
            assert client.get_object(Bucket='rootless-candidate', Key='identity.txt')['Body'].read() == body
            assert sql('SELECT id FROM candidate.persistence') == 'rootless-storage-identity'
            ids = run([*compose, 'ps', '-q'], env).split()
            health = [run(['docker', '--context', 'rootless', 'inspect', '--format', '{{.State.Health.Status}}', cid]) for cid in ids]
            assert len(health) == 2 and all(h == 'healthy' for h in health)
        check()
        report['checks']['initial_storage'] = 'PASS'
        report['checks']['object_sha256'] = hashlib.sha256(body).hexdigest()
        report['checks']['clickhouse_version'] = sql('SELECT version()')
        mutate([*compose, 'restart', '--timeout', '60'])
        mutate([*compose, 'up', '-d', '--wait', '--wait-timeout', '180', 'object-storage', 'clickhouse'])
        check()
        report['checks']['compose_restart_persistence'] = 'PASS'
        preflight.daemon()
        run(['systemctl', '--user', 'restart', 'docker.service'])
        # Bounded observation of restart-policy recovery; no Compose up may hide failure.
        deadline = time.monotonic() + 180
        while True:
            try:
                check()
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise RuntimeError('daemon restart recovery failed') from None
                time.sleep(2)
        report['checks']['docker_restart_automatic_storage_recovery'] = 'PASS'
        report['checks']['ownership'] = {str(p.relative_to(state)): {'uid': p.stat().st_uid, 'gid': p.stat().st_gid,
                                           'mode': oct(p.stat().st_mode & 0o777)}
                                        for p in [state / 'objects', state / 'clickhouse/data', state / 'clickhouse/logs']}
        report['status'] = 'PASS'
    finally:
        mutate([*compose, 'stop', '--timeout', '60', 'object-storage', 'clickhouse'])
        report['candidate_left'] = 'stopped; all data and private fixture secrets retained'
        evidence.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('STOP: candidate validation failed; secret-bearing output suppressed') from None
