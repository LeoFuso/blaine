#!/usr/bin/env python3
"""Bounded live D1 service acceptance. No backup, disk, reboot, or cloud calls.

Run after Ansible staging and secret initialization, using Python with boto3.
Evidence contains only versions, health, digests, and synthetic identifiers.
"""
import base64
from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

COMPOSE = ['docker', 'compose', '-f', '/etc/blaine/infra/compose.yaml']
EVIDENCE = Path('/var/lib/blaine-platform/infrastructure-acceptance.json')
report = {'status': 'INCOMPLETE', 'backup': 'PAUSED', 'reboot': 'PENDING', 'checks': {}}


def command(args):
    p = subprocess.run(args, text=True, capture_output=True, timeout=600)
    if p.returncode:
        # Dependency errors can contain connection strings. Do not print raw logs.
        raise RuntimeError(f'Command failed: {args[0]} {args[1]}; output suppressed')
    return p.stdout.strip()


def request(url, payload=None, headers=None):
    data = json.dumps(payload).encode() if payload is not None else None
    h = {'Content-Type': 'application/json', **(headers or {})}
    with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=h), timeout=15) as r:
        return r.read()


def wait_for(fn, seconds=180):
    end = time.monotonic() + seconds
    while True:
        try:
            value = fn()
            if value:
                return value
        except (OSError, urllib.error.HTTPError, RuntimeError):
            pass
        if time.monotonic() >= end:
            raise RuntimeError('Bounded readiness/persistence acceptance timed out')
        time.sleep(2)


def health():
    for endpoint in ['http://127.0.0.1:8123/ping', 'http://127.0.0.1:3000/api/public/health',
                     'http://127.0.0.1:3030/api/health', 'http://127.0.0.1:12345/-/healthy']:
        wait_for(lambda: request(endpoint))
    return True


def main():
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError
    if os.geteuid() != 0:
        raise RuntimeError('Requires bounded sudo; never run Codex as root')
    s = json.loads(Path('/etc/blaine/secrets/infrastructure.json').read_text())
    assert command(['systemctl', 'is-active', 'docker']) == 'active'
    report['checks']['docker_version'] = command(['docker', 'version', '--format', '{{.Server.Version}}'])
    report['checks']['compose_version'] = command(['docker', 'compose', 'version', '--short'])
    command([*COMPOSE, 'config', '--quiet'])
    # Refuse to restart unrelated Docker workloads.
    ids = command(['docker', 'ps', '-q']).splitlines()
    for cid in ids:
        project = command(['docker', 'inspect', '--format', '{{index .Config.Labels "com.docker.compose.project"}}', cid])
        if project != 'blaine-infra':
            raise RuntimeError('STOP: unrelated running Docker workload; no Docker restart performed')
    hello = command(['docker', 'run', '--rm', '--network', 'none', '--read-only', '--cap-drop=ALL',
                     '--security-opt', 'no-new-privileges', 'hello-world:linux'])
    assert 'Hello from Docker!' in hello
    report['checks']['isolated_container'] = 'PASS'
    report['checks']['hello_image_digest'] = command(['docker', 'image', 'inspect', '--format', '{{json .RepoDigests}}', 'hello-world:linux'])

    command([*COMPOSE, 'up', '-d', '--wait', 'object-storage', 'clickhouse'])

    def s3(consumer):
        return boto3.client('s3', endpoint_url='http://127.0.0.1:8333', region_name='us-east-1',
                            aws_access_key_id=s[f's3_{consumer}_key'], aws_secret_access_key=s[f's3_{consumer}_secret'],
                            config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}, retries={'max_attempts': 2}))

    admin = s3('admin')
    buckets = ['blaine-artifacts', 'langfuse-events', 'langfuse-media']
    existing = {b['Name'] for b in admin.list_buckets()['Buckets']}
    for bucket in buckets:
        if bucket not in existing:
            admin.create_bucket(Bucket=bucket)
    token = secrets.token_hex(12)
    key = f'd1-acceptance/{token}.txt'
    for bucket in buckets:
        consumer = 'blaine' if bucket == 'blaine-artifacts' else 'langfuse'
        body = ('D1 synthetic persistence: ' + bucket + '/' + token).encode()
        s3(consumer).put_object(Bucket=bucket, Key=key, Body=body)
        assert s3(consumer).get_object(Bucket=bucket, Key=key)['Body'].read() == body
    for consumer, bucket in [('langfuse', 'blaine-artifacts'), ('blaine', 'langfuse-events')]:
        try:
            s3(consumer).get_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            assert exc.response['ResponseMetadata']['HTTPStatusCode'] == 403
        else:
            raise RuntimeError('STOP: cross-consumer namespace access was allowed')
    report['checks']['buckets_and_access_separation'] = buckets

    def clickhouse(sql):
        # Authentication in headers, never process arguments or evidence.
        headers = {'X-ClickHouse-User': 'langfuse', 'X-ClickHouse-Key': s['clickhouse_password']}
        req = urllib.request.Request('http://127.0.0.1:8123/', data=sql.encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read().decode().strip()

    report['checks']['clickhouse_version'] = clickhouse('SELECT version()')
    assert report['checks']['clickhouse_version'] == '26.4.5.143'
    assert clickhouse('SELECT timezone()') == 'UTC'
    # Separate synthetic database, never customize Langfuse tables.
    clickhouse('CREATE DATABASE IF NOT EXISTS blaine_d1_acceptance')
    clickhouse('CREATE TABLE IF NOT EXISTS blaine_d1_acceptance.persistence (id String) ENGINE=MergeTree ORDER BY id')
    clickhouse(f"INSERT INTO blaine_d1_acceptance.persistence VALUES ('{token}')")

    command(['systemctl', 'enable', '--now', 'blaine-infra.service', 'alloy.service'])
    health()
    report['checks']['langfuse_web_worker_health'] = 'PASS'
    migrations = clickhouse("SELECT count() FROM system.tables WHERE database='langfuse'")
    assert int(migrations) > 5
    report['checks']['langfuse_initialized_table_count'] = int(migrations)
    auth = base64.b64encode(('pk-lf-' + s['project_public'] + ':sk-lf-' + s['project_secret']).encode()).decode()
    headers = {'Authorization': 'Basic ' + auth}
    trace_id = secrets.token_hex(16)
    now = datetime.now(timezone.utc)
    n = time.time_ns()
    root_span = secrets.token_hex(8)
    def span(name, span_id, parent=None, kind='span'):
        value = {'traceId': trace_id, 'spanId': span_id, 'name': name,
                 'startTimeUnixNano': str(n), 'endTimeUnixNano': str(n + 1000000),
                 'attributes': [{'key': 'langfuse.observation.type', 'value': {'stringValue': kind}},
                                {'key': 'langfuse.trace.name', 'value': {'stringValue': 'd1-synthetic-trace'}},
                                {'key': 'gen_ai.request.model', 'value': {'stringValue': 'synthetic-no-call'}}]}
        if parent:
            value['parentSpanId'] = parent
        return value
    payload = {'resourceSpans': [{'resource': {'attributes': [{'key': 'service.name', 'value': {'stringValue': 'blaine-d1-synthetic'}}]},
        'scopeSpans': [{'scope': {'name': 'd1.acceptance'}, 'spans': [span('d1-synthetic-trace', root_span),
                      span('synthetic-no-model-call', secrets.token_hex(8), root_span, 'generation')]}]}]}
    report['phase'] = 'Langfuse OTLP v4 roundtrip'
    request('http://127.0.0.1:3000/api/public/otel/v1/traces', payload,
            {**headers, 'x-langfuse-ingestion-version': '4'})
    observation_url = 'http://127.0.0.1:3000/api/public/v2/observations?' + urlencode({
        'traceId': trace_id, 'fields': 'core,basic,usage', 'limit': 10,
        'fromStartTime': (now - timedelta(minutes=1)).isoformat(),
        'toStartTime': (now + timedelta(minutes=1)).isoformat()})
    def observations_present():
        data = json.loads(request(observation_url, headers=headers)).get('data', [])
        return len(data) == 2 and all(row['traceId'] == trace_id for row in data) and any(row.get('type', '').upper() == 'GENERATION' for row in data)
    wait_for(observations_present)
    report['checks']['langfuse_dependency_roundtrip'] = {'trace_id': trace_id, 'result': 'PASS'}

    report['phase'] = 'Alloy telemetry'
    n = time.time_ns()
    otlp = {'resourceSpans': [{'resource': {'attributes': [{'key': 'service.name', 'value': {'stringValue': 'blaine-d1-synthetic'}}]},
             'scopeSpans': [{'scope': {'name': 'd1.acceptance'}, 'spans': [{'traceId': secrets.token_hex(16),
             'spanId': secrets.token_hex(8), 'name': 'd1-local-otlp-smoke', 'startTimeUnixNano': str(n), 'endTimeUnixNano': str(n + 1000000)}]}]}]}
    request('http://127.0.0.1:4318/v1/traces', otlp)
    local = Path('/var/lib/alloy/telemetry/local.json')
    wait_for(lambda: local.exists() and 'd1-local-otlp-smoke' in local.read_text())
    wait_for(lambda: 'node_cpu_seconds_total' in local.read_text(), seconds=90)
    report['checks']['alloy_local_metrics_otlp'] = 'PASS'

    for unit in ['blaine-infra.service', 'docker.service', 'alloy.service']:
        report['phase'] = 'restart ' + unit
        command(['systemctl', 'restart', unit])
        health()
        for bucket in buckets:
            assert admin.get_object(Bucket=bucket, Key=key)['Body'].read() == ('D1 synthetic persistence: ' + bucket + '/' + token).encode()
        assert clickhouse(f"SELECT count() FROM blaine_d1_acceptance.persistence WHERE id='{token}'") == '1'
        assert observations_present()
        assert 'd1-local-otlp-smoke' in local.read_text()
        report['checks']['restart_' + unit] = 'healthy; synthetic persistent state retained'
    report['checks']['images'] = json.loads(command([*COMPOSE, 'images', '--format', 'json']))
    report['checks']['native_postgresql'] = command(['pg_isready', '-h', '127.0.0.1'])
    assert command(['redis-cli', 'PING']) == 'PONG'
    report['checks']['native_redis'] = 'PONG'
    for port in [3000, 3030, 4317, 4318, 8123, 8333, 9000, 12345]:
        lines = command(['ss', '-H', '-lnt', f'sport = :{port}']).splitlines()
        assert lines and all(line.split()[3] == f'127.0.0.1:{port}' for line in lines)
    report['checks']['loopback_listeners'] = 'PASS'
    report['phase'] = 'complete'
    report['status'] = 'PASS'


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        report['status'] = 'STOP'
        # Never serialize exception details from SDKs containing auth or payloads.
        report['failure_type'] = type(exc).__name__
        print('D1 acceptance stopped; inspect the last successful check. Secret-bearing diagnostics suppressed.', file=sys.stderr)
    finally:
        report['observed_at'] = datetime.now(timezone.utc).isoformat()
        if os.geteuid() == 0:
            EVIDENCE.parent.mkdir(mode=0o755, exist_ok=True)
            EVIDENCE.write_text(json.dumps(report, indent=2) + '\n')
            EVIDENCE.chmod(0o644)
        print(json.dumps(report, indent=2))
    sys.exit(0 if report['status'] == 'PASS' else 1)
