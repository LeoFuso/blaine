"""CP.2 adapter over existing MIRIX PostgreSQL raw memory + local embeddings.

The optional driver lives in the existing MIRIX environment. A fixed child-process
bridge keeps it out of the kernel toolchain. No HTTP listener or worker tool is
introduced. Schema installation is an explicit trusted operation, never a read side
effect. Only the native qualification/authorized deployment may install it.
"""
from dataclasses import asdict, dataclass
import configparser
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import urllib.request
import uuid

from runtime.kernel.contracts import encode, fields, text
from runtime.kernel.memory_writes import MemoryError


@dataclass(frozen=True)
class MirixStorageConfig:
    python: str
    credentials_file: str
    namespace: str
    organization: str
    user: str
    client: str
    embedding_model: str = 'BAAI/bge-m3'
    embedding_endpoint: str = 'http://127.0.0.1:8001/v1/embeddings'

    def validate(self):
        for value in (self.namespace, self.organization, self.user, self.client):
            text(value, 128)
        # CP.2 has exactly the existing local route, no selectable provider egress.
        if self.embedding_endpoint != 'http://127.0.0.1:8001/v1/embeddings' or self.embedding_model != 'BAAI/bge-m3':
            raise MemoryError('UNAVAILABLE')
        if not Path(self.python).is_absolute() or not Path(self.credentials_file).is_absolute():
            raise MemoryError('UNAVAILABLE')


class MirixProcessStore:
    def __init__(self, config):
        config.validate()
        self.config = config

    def _call(self, operation, value):
        request = {'config': asdict(self.config), 'operation': operation, 'value': value}
        try:
            result = subprocess.run([self.config.python, '-m', 'runtime.kernel.mirix_storage'],
                cwd=Path(__file__).resolve().parents[2], input=encode(request),
                capture_output=True, timeout=90, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            if result.returncode != 0 or len(result.stdout) > 1024 * 1024:
                raise ValueError()
            response = json.loads(result.stdout)
            if response.get('error') in ('IDEMPOTENCY_CONFLICT', 'UNAVAILABLE', 'UNKNOWN'):
                raise MemoryError(response['error'])
            return response['result']
        except MemoryError:
            raise
        except Exception:
            raise MemoryError('UNKNOWN' if operation == 'commit' else 'UNAVAILABLE') from None

    def install(self):
        return self._call('install', {})

    def commit(self, entry, token):
        value = {'entry': entry, 'token': token}
        try:
            return self._call('commit', value)
        except MemoryError as error:
            if error.status != 'UNKNOWN':
                raise
            # One read-only reconciliation after response loss. Never redispatch a
            # write without fresh runtime admission; durable work owns later retries.
            try:
                return self._call('lookup', value)
            except MemoryError as reconciliation:
                if reconciliation.status == 'IDEMPOTENCY_CONFLICT':
                    raise
                raise MemoryError('UNKNOWN') from None

    def read(self, contexts, domains, current, execution, query=None, locator=None):
        return self._call('read', {'contexts': contexts, 'domains': domains, 'current': current,
                                   'execution': execution, 'query': query, 'locator': locator})


SCHEMA = '''
CREATE TABLE IF NOT EXISTS blaine_memory_entry_v1 (
 namespace TEXT NOT NULL,
 context_id TEXT NOT NULL,
 domain_id TEXT NOT NULL,
 token_hash TEXT NOT NULL,
 request_hash TEXT NOT NULL,
 raw_id VARCHAR PRIMARY KEY REFERENCES raw_memory(id) ON DELETE RESTRICT,
 metadata JSONB NOT NULL,
 UNIQUE(namespace, context_id, domain_id, token_hash),
 CHECK(metadata->>'version' = '1'),
 CHECK(metadata->>'context' = context_id AND metadata->>'domain' = domain_id),
 CHECK((metadata->>'origin' = 'AGENT_OBSERVATION' AND metadata->>'status' = 'UNVERIFIED'
        AND metadata->>'retention' = 'WORKING') OR
       (metadata->>'origin' = 'USER_DECLARATION' AND metadata->>'status' = 'DECLARED'
        AND metadata->>'retention' = 'RETAINED'))
);
'''


class PostgresMirixStore:
    """Private adapter implementation. Not a worker-facing storage contract."""
    def __init__(self, config):
        config.validate()
        self.config = config

    def connect(self):
        # Same approved database identity/private credential source as mirix-launch.
        import psycopg2
        from urllib.parse import urlsplit
        source = Path(self.config.credentials_file)
        for path in (source, source.parent):
            info = path.stat()
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
                raise MemoryError('UNAVAILABLE')
        config = configparser.ConfigParser()
        config.read(source)
        uri = config['recall_storage']['uri']
        target = urlsplit(uri)
        if uri != config['archival_storage']['uri'] or target.hostname != '127.0.0.1' or target.path != '/mirix':
            raise MemoryError('UNAVAILABLE')
        return psycopg2.connect(uri, connect_timeout=5, options='-c statement_timeout=15000')

    def install(self):
        # Add metadata to the approved substrate; never create a database/service.
        db = self.connect()
        try:
            with db, db.cursor() as cur:
                cur.execute(SCHEMA)
            return {'schema': 1}
        finally:
            db.close()

    def lookup(self, entry, token):
        db = self.connect()
        try:
            with db, db.cursor() as cur:
                cur.execute('''SELECT raw_id, request_hash FROM blaine_memory_entry_v1
                    WHERE namespace=%s AND context_id=%s AND domain_id=%s AND token_hash=%s''',
                    (self.config.namespace, entry['context'], entry['domain'], token))
                row = cur.fetchone()
                if not row:
                    raise MemoryError('UNKNOWN')
                if row[1] != hashlib.sha256(encode(entry)).hexdigest():
                    raise MemoryError('IDEMPOTENCY_CONFLICT')
                return [row[0], True]
        finally:
            db.close()

    def _partition(self, context, domain):
        return 'blaine-cp2:' + hashlib.sha256(encode([self.config.namespace, context, domain])).hexdigest()

    def _embedding(self, content):
        # Refuse redirects and proxies: even a local HTTP redirect is not an egress grant.
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
        req = urllib.request.Request(self.config.embedding_endpoint,
            data=encode({'model': self.config.embedding_model, 'input': content}),
            headers={'Content-Type': 'application/json'})
        with opener.open(req, timeout=45) as response:
            body = response.read(131073)
        if len(body) > 131072:
            raise MemoryError('UNAVAILABLE')
        vector = json.loads(body)['data'][0]['embedding']
        if (len(vector) != 1024 or any(type(n) not in (int, float) or not math.isfinite(n) for n in vector)):
            raise MemoryError('UNAVAILABLE')
        # MIRIX's current native raw vector column pads to MAX_EMBEDDING_DIM=4096.
        return vector + [0.0] * (4096 - len(vector))

    def commit(self, entry, token):
        fields(entry, {'context', 'domain', 'origin', 'status', 'retention', 'content',
                       'creator', 'execution', 'sha256', 'version'})
        for key in ('context', 'domain', 'creator', 'execution'):
            text(entry[key], 128)
        text(entry['content'], 4096)
        if (entry['version'] != 1 or
                (entry['origin'], entry['status'], entry['retention']) not in {
                    ('AGENT_OBSERVATION', 'UNVERIFIED', 'WORKING'), ('USER_DECLARATION', 'DECLARED', 'RETAINED')} or
                hashlib.sha256(entry['content'].encode()).hexdigest() != entry['sha256']):
            raise MemoryError('UNAVAILABLE')
        if len(token) != 64 or any(c not in '0123456789abcdef' for c in token):
            raise MemoryError('UNAVAILABLE')
        scope = (self.config.namespace, entry['context'], entry['domain'], token)
        request_hash = hashlib.sha256(encode(entry)).hexdigest()
        lock = int.from_bytes(hashlib.sha256(encode(scope)).digest()[:8], 'big', signed=True)
        db = self.connect()
        try:
            with db, db.cursor() as cur:
                # Scope-specific retry serialization; unrelated contexts never query
                # one another's keys/IDs. No global semantic deduplication.
                cur.execute('SELECT pg_advisory_xact_lock(%s)', (lock,))
                cur.execute('''SELECT raw_id, request_hash FROM blaine_memory_entry_v1
                    WHERE namespace=%s AND context_id=%s AND domain_id=%s AND token_hash=%s''', scope)
                existing = cur.fetchone()
                if existing:
                    if existing[1] != request_hash:
                        raise MemoryError('IDEMPOTENCY_CONFLICT')
                    return [existing[0], True]
                # Existing identities only. No automatic tenant/user provisioning.
                cur.execute('SELECT 1 FROM users WHERE id=%s AND organization_id=%s AND NOT is_deleted',
                            (self.config.user, self.config.organization))
                if not cur.fetchone():
                    raise MemoryError('UNAVAILABLE')
                cur.execute('SELECT 1 FROM clients WHERE id=%s AND organization_id=%s AND NOT is_deleted',
                            (self.config.client, self.config.organization))
                if not cur.fetchone():
                    raise MemoryError('UNAVAILABLE')
                identity = 'cp2-' + uuid.uuid4().hex
                metadata = {k: v for k, v in entry.items() if k != 'content'}
                partition = self._partition(entry['context'], entry['domain'])
                tags = {'scope': partition, 'blaine': metadata}
                vector = self._embedding(entry['content'])
                embedding_config = {'embedding_model': self.config.embedding_model,
                    'embedding_endpoint_type': 'hugging-face', 'embedding_dim': 1024,
                    'embedding_endpoint': 'http://127.0.0.1:8001/v1'}
                cur.execute('''INSERT INTO raw_memory
                    (id, context, filter_tags, last_modify, embedding_config, context_embedding,
                     occurred_at, created_at, updated_at, is_deleted, _created_by_id,
                     organization_id, user_id)
                    VALUES (%s,%s,%s::json,%s::json,%s::json,%s::vector,
                            now(),now(),now(),false,%s,%s,%s)''',
                    (identity, entry['content'], json.dumps(tags), json.dumps({'operation': 'blaine-cp2'}),
                     json.dumps(embedding_config), json.dumps(vector), self.config.client,
                     self.config.organization, self.config.user))
                cur.execute('''INSERT INTO blaine_memory_entry_v1
                    (namespace,context_id,domain_id,token_hash,request_hash,raw_id,metadata)
                    VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb)''',
                    (*scope, request_hash, identity, json.dumps(metadata)))
            # Raw source, vector, provenance and retry identity commit atomically.
            return [identity, False]
        finally:
            db.close()

    def read(self, contexts, domains, current, execution, query=None, locator=None):
        if not contexts or not domains:
            return []
        db = self.connect()
        try:
            with db, db.cursor() as cur:
                # Authorization before search, stats, content loading and result limits.
                cur.execute('''SELECT e.raw_id, e.metadata, r.context, r.filter_tags
                    FROM blaine_memory_entry_v1 e JOIN raw_memory r ON r.id=e.raw_id
                    WHERE e.namespace=%s AND e.context_id=ANY(%s) AND e.domain_id=ANY(%s)
                      AND (e.metadata->>'retention'='RETAINED' OR
                           (e.context_id=%s AND e.metadata->>'execution'=%s))
                      AND r.organization_id=%s AND r.user_id=%s AND NOT r.is_deleted
                      AND (%s IS NULL OR e.raw_id=%s)
                      AND (%s IS NULL OR strpos(lower(r.context),lower(%s))>0)
                    ORDER BY e.raw_id LIMIT 33''',
                    (self.config.namespace, contexts, domains, current, execution, self.config.organization,
                     self.config.user, locator, locator, query, query))
                result = []
                for identity, metadata, content, tags in cur.fetchall():
                    if tags != {'scope': self._partition(metadata['context'], metadata['domain']), 'blaine': metadata}:
                        raise MemoryError('UNAVAILABLE')
                    result.append({'id': identity, **metadata, 'content': content})
                return result
        finally:
            db.close()


def main():
    try:
        raw = json.loads(sys.stdin.buffer.read(65537))
        fields(raw, {'config', 'operation', 'value'})
        adapter = PostgresMirixStore(MirixStorageConfig(**raw['config']))
        operation, value = raw['operation'], raw['value']
        if operation == 'install':
            fields(value, set()); result = adapter.install()
        elif operation == 'commit':
            fields(value, {'entry', 'token'}); result = adapter.commit(**value)
        elif operation == 'lookup':
            fields(value, {'entry', 'token'}); result = adapter.lookup(**value)
        elif operation == 'read':
            fields(value, {'contexts', 'domains', 'current', 'execution', 'query', 'locator'}); result = adapter.read(**value)
        else:
            raise MemoryError('UNAVAILABLE')
        response = {'result': result}
    except MemoryError as error:
        response = {'error': error.status}
    except Exception:
        # Never print connection details, raw SQL parameters, source text or traceback.
        response = {'error': 'UNKNOWN' if locals().get('operation') == 'commit' else 'UNAVAILABLE'}
    sys.stdout.buffer.write(encode(response))


if __name__ == '__main__':
    main()
