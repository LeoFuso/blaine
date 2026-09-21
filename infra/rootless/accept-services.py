#!/usr/bin/env python3
"""Credential-safe integration checks, shared by isolated candidate and cutover.

No host-service control here. Credentials stay in memory and HTTP headers.
Snapshot records hashes/identities only, never object bodies or credentials.
"""
import base64
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import secrets
import time
import urllib.request
from urllib.parse import urlencode


class Services:
    def __init__(self, secret_dir, s3_port=8333, ch_port=8123, web_port=3000, worker_port=3030):
        self.secrets = json.loads((Path(secret_dir) / 'infrastructure.json').read_text())
        self.s3_port, self.ch_port = s3_port, ch_port
        self.web_port, self.worker_port = web_port, worker_port

    def request(self, url, body=None, headers=None):
        req = urllib.request.Request(url, data=body, headers=headers or {})
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.read()

    def s3(self, consumer='admin'):
        import boto3
        from botocore.config import Config
        return boto3.client('s3', endpoint_url=f'http://127.0.0.1:{self.s3_port}', region_name='us-east-1',
                            aws_access_key_id=self.secrets[f's3_{consumer}_key'],
                            aws_secret_access_key=self.secrets[f's3_{consumer}_secret'],
                            config=Config(signature_version='s3v4', s3={'addressing_style': 'path'}))

    def sql(self, sql):
        return self.request(f'http://127.0.0.1:{self.ch_port}/', sql.encode(),
                            {'X-ClickHouse-User': 'langfuse', 'X-ClickHouse-Key': self.secrets['clickhouse_password']}).decode().strip()

    def health(self):
        for port, path in [(self.ch_port, '/ping'), (self.web_port, '/api/public/health'), (self.worker_port, '/api/health')]:
            self.request(f'http://127.0.0.1:{port}{path}')

    def auth(self):
        s = self.secrets
        value = base64.b64encode(('pk-lf-' + s['project_public'] + ':sk-lf-' + s['project_secret']).encode()).decode()
        return {'Authorization': 'Basic ' + value}

    def observations(self, trace_id, since):
        query = urlencode({'traceId': trace_id, 'fields': 'core,basic,usage', 'limit': 10,
                           'fromStartTime': since, 'toStartTime': (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()})
        data = self.request(f'http://127.0.0.1:{self.web_port}/api/public/v2/observations?{query}', headers=self.auth())
        return json.loads(data).get('data', [])

    def roundtrip(self):
        trace_id, span_id = secrets.token_hex(16), secrets.token_hex(8)
        since = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
        n = time.time_ns()
        span = {'traceId': trace_id, 'spanId': span_id, 'name': 'd1-rootless-synthetic-no-model-call',
                'startTimeUnixNano': str(n), 'endTimeUnixNano': str(n + 1000000),
                'attributes': [{'key': 'langfuse.observation.type', 'value': {'stringValue': 'generation'}},
                               {'key': 'gen_ai.request.model', 'value': {'stringValue': 'synthetic-no-call'}}]}
        payload = {'resourceSpans': [{'resource': {'attributes': [{'key': 'service.name', 'value': {'stringValue': 'd1-rootless-acceptance'}}]},
                    'scopeSpans': [{'scope': {'name': 'd1.rootless'}, 'spans': [span]}]}]}
        self.request(f'http://127.0.0.1:{self.web_port}/api/public/otel/v1/traces', json.dumps(payload).encode(),
                     {**self.auth(), 'Content-Type': 'application/json', 'x-langfuse-ingestion-version': '4'})
        deadline = time.monotonic() + 180
        while True:
            rows = self.observations(trace_id, since)
            if len(rows) == 1 and rows[0]['traceId'] == trace_id and rows[0].get('type', '').upper() == 'GENERATION':
                return {'trace_id': trace_id, 'since': since, 'status': 'PASS'}
            if time.monotonic() > deadline:
                raise RuntimeError('synthetic ingestion timeout')
            time.sleep(2)

    def seed(self):
        from botocore.exceptions import ClientError
        admin = self.s3()
        buckets = ['blaine-artifacts', 'langfuse-events', 'langfuse-media']
        existing = {b['Name'] for b in admin.list_buckets()['Buckets']}
        key = 'd1-rootless-acceptance/' + secrets.token_hex(12) + '.txt'
        for bucket in buckets:
            if bucket not in existing:
                admin.create_bucket(Bucket=bucket)
            consumer = 'blaine' if bucket == 'blaine-artifacts' else 'langfuse'
            body = ('D1 rootless retained synthetic object ' + bucket).encode()
            self.s3(consumer).put_object(Bucket=bucket, Key=key, Body=body)
            assert self.s3(consumer).get_object(Bucket=bucket, Key=key)['Body'].read() == body
        for consumer, bucket in [('blaine', 'langfuse-events'), ('langfuse', 'blaine-artifacts')]:
            try:
                self.s3(consumer).get_object(Bucket=bucket, Key=key)
            except ClientError as exc:
                assert exc.response['ResponseMetadata']['HTTPStatusCode'] == 403
            else:
                raise RuntimeError('cross-consumer access unexpectedly allowed')
        self.sql('CREATE DATABASE IF NOT EXISTS blaine_d1_acceptance')
        self.sql('CREATE TABLE IF NOT EXISTS blaine_d1_acceptance.persistence (id String) ENGINE=MergeTree ORDER BY id')
        token = secrets.token_hex(12)
        self.sql(f"INSERT INTO blaine_d1_acceptance.persistence VALUES ('{token}')")
        return {'object_key': key, 'clickhouse_row': token, 'access_separation': 'PASS'}

    def snapshot(self):
        admin = self.s3()
        objects = []
        for bucket in sorted(b['Name'] for b in admin.list_buckets()['Buckets']):
            for page in admin.get_paginator('list_objects_v2').paginate(Bucket=bucket):
                for obj in page.get('Contents', []):
                    body = admin.get_object(Bucket=bucket, Key=obj['Key'])['Body'].read()
                    # Object names can be private; retain identity hashes, not raw names.
                    identity = hashlib.sha256((bucket + '/' + obj['Key']).encode()).hexdigest()
                    objects.append({'bucket': bucket, 'identity_sha256': identity,
                                    'content_sha256': hashlib.sha256(body).hexdigest(), 'bytes': len(body)})
        return {'objects': sorted(objects, key=lambda x: (x['bucket'], x['identity_sha256'])),
                'clickhouse_rows': self.sql('SELECT id FROM blaine_d1_acceptance.persistence ORDER BY id').splitlines(),
                'langfuse_tables': int(self.sql("SELECT count() FROM system.tables WHERE database='langfuse'")),
                'clickhouse_version': self.sql('SELECT version()')}

    def verify_snapshot(self, baseline):
        current = self.snapshot()
        index = {(x['bucket'], x['identity_sha256']): x for x in current['objects']}
        assert all(index.get((x['bucket'], x['identity_sha256'])) == x for x in baseline['objects'])
        assert current['clickhouse_rows'] == baseline['clickhouse_rows']
        assert current['langfuse_tables'] == baseline['langfuse_tables']
        assert current['clickhouse_version'] == baseline['clickhouse_version']
        for trace in baseline.get('retained_traces', []):
            rows = self.observations(trace['trace_id'], trace['since'])
            assert len(rows) == trace['count']
            assert all(row['traceId'] == trace['trace_id'] for row in rows)
        return {'status': 'PASS', 'objects_preserved': len(baseline['objects']),
                'clickhouse_rows_preserved': len(baseline['clickhouse_rows']),
                'langfuse_traces_preserved': len(baseline.get('retained_traces', []))}
