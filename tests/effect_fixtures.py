"""Deterministic E2.0 target provider and fixtures. No real filesystem, IDE or process.

FixtureTarget honours the TargetProvider obligations (operation-id idempotent
dispatch, atomic compare-and-swap writes, a durable receipt store) and lets tests
inject the failures the kernel must survive. State lives in SQLite so a real
Restate runtime can be killed and restarted against the same world.
"""
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from runtime.kernel import effects
from runtime.kernel.contracts import message

WORKSPACE = 'wsp-e2-fixture'
CONFIG = 'service/config/limits.properties'
BEFORE = 'max.retries=3\ntimeout.seconds=30\n'
AFTER = 'max.retries=5\ntimeout.seconds=30\n'
SHA = {name: hashlib.sha256(value.encode()).hexdigest() for name, value in (('before', BEFORE), ('after', AFTER))}
PROFILES = {
    'unit-tests': effects.ExecProfile(id='unit-tests', executable='./gradlew', args=('--no-daemon', 'test'),
                                      allowed_args=('--offline',), timeout_seconds=3, poll_seconds=0.5,
                                      output_cap_bytes=65536),
    'slow-build': effects.ExecProfile(id='slow-build', executable='./gradlew', args=('--no-daemon', 'build'),
                                      timeout_seconds=1, poll_seconds=0.5, output_cap_bytes=65536),
}


class FixtureTarget:
    provider_id = 'fixture-target'

    def __init__(self, database: Path):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS files (workspace_id TEXT, path TEXT, content TEXT, PRIMARY KEY (workspace_id, path));
                CREATE TABLE IF NOT EXISTS receipts (operation_id TEXT PRIMARY KEY, request_digest TEXT, receipt TEXT);
                CREATE TABLE IF NOT EXISTS processes (operation_id TEXT PRIMARY KEY, profile TEXT, polls INTEGER);
                CREATE TABLE IF NOT EXISTS executions (operation_id TEXT, kind TEXT);
                CREATE TABLE IF NOT EXISTS faults (name TEXT PRIMARY KEY, value TEXT);''')

    def db(self):
        return sqlite3.connect(self.database, timeout=30, isolation_level='IMMEDIATE')

    # ---------------------------------------------------------------- world control (tests only)
    def put_file(self, path, content, workspace=WORKSPACE):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO files VALUES (?, ?, ?)', (workspace, path, content))

    def file(self, path, workspace=WORKSPACE):
        with self.db() as db:
            row = db.execute('SELECT content FROM files WHERE workspace_id=? AND path=?', (workspace, path)).fetchone()
        return row[0] if row else None

    def set_fault(self, name, value):
        with self.db() as db:
            if value is None:
                db.execute('DELETE FROM faults WHERE name=?', (name,))
            else:
                db.execute('INSERT OR REPLACE INTO faults VALUES (?, ?)', (name, json.dumps(value)))

    def fault(self, name, default=None):
        with self.db() as db:
            row = db.execute('SELECT value FROM faults WHERE name=?', (name,)).fetchone()
        return json.loads(row[0]) if row else default

    def executions(self, operation_id=None):
        with self.db() as db:
            rows = db.execute('SELECT operation_id, kind FROM executions').fetchall()
        return [r for r in rows if operation_id is None or r[0] == operation_id]

    def behave(self, profile, polls=1, exit_code=0, result=None, output='BUILD SUCCESSFUL', stop='confirmed',
               operation=None):
        """Scripted process behaviour for a profile, or for one operation (which wins)."""
        self.set_fault(('exec-op:' + operation) if operation else ('exec:' + profile),
                       {'polls': polls, 'exit_code': exit_code, 'result': result or {}, 'output': output, 'stop': stop})

    def behaviour(self, operation, profile):
        return self.fault('exec-op:' + operation) or self.fault('exec:' + profile, {'polls': 1, 'exit_code': 0})

    # ---------------------------------------------------------------- TargetProvider
    def reachable(self):
        if self.fault('unavailable'):
            raise effects.ProviderUnavailable('fixture provider unreachable')

    def read(self, workspace_id, path):
        self.reachable()
        content = self.file(path, workspace_id)
        return {'exists': content is not None, 'content': content or ''}

    def observe(self, workspace_id, path):
        self.reachable()
        content = self.file(path, workspace_id)
        return {'exists': False} if content is None else {'exists': True, 'sha256': hashlib.sha256(content.encode()).hexdigest()}

    def receipt(self, request, state, **body):
        payload = request['payload']
        return message('EffectReceipt', {'task_id': payload['task_id'], 'operation_id': payload['operation_id'],
            'request_digest': effects.request_digest(request), 'provider': self.provider_id,
            'operation_class': payload['operation_class'], 'state': state, **body})

    def dispatch(self, request, payload):
        self.reachable()
        operation, digest = request['payload']['operation_id'], effects.request_digest(request)
        with self.db() as db:
            row = db.execute('SELECT request_digest, receipt FROM receipts WHERE operation_id=?', (operation,)).fetchone()
            if row:
                if row[0] != digest:
                    raise ValueError('Operation identity reused with a different request')
                return json.loads(row[1])
            if request['payload']['operation_class'] == effects.WRITE:
                receipt = self.write(db, request, payload)
            else:
                receipt = self.start(db, request)
            db.execute('INSERT INTO receipts VALUES (?, ?, ?)', (operation, digest, json.dumps(receipt)))
        committed = self.fault('after_commit')
        if committed == 'crash':
            # The effect is committed; the runtime dies before Restate records the step.
            from completion_harness import Crash
            self.set_fault('after_commit', None)
            raise Crash('runtime died after the provider committed')
        if committed == 'lose_response':
            self.set_fault('after_commit', None)
            raise effects.ResponseLost('fixture reply dropped after commit')
        if committed == 'block':
            # Hold the reply after commit so a real runtime can be killed here.
            (self.database.parent / 'effect-committed').write_text(operation)
            while not (self.database.parent / 'release-effect').exists():
                time.sleep(0.05)
        return receipt

    def write(self, db, request, payload):
        """Atomic compare-and-swap inside one IMMEDIATE transaction."""
        p = request['payload']
        external = self.fault('external_edit')
        if external:
            db.execute('INSERT OR REPLACE INTO files VALUES (?, ?, ?)', (p['workspace_id'], p['path'], external))
            db.execute("INSERT OR REPLACE INTO faults VALUES ('external_edit', 'null')")
        row = db.execute('SELECT content FROM files WHERE workspace_id=? AND path=?', (p['workspace_id'], p['path'])).fetchone()
        before = {'absent': True} if row is None else {'sha256': hashlib.sha256(row[0].encode()).hexdigest()}
        target = {'workspace_id': p['workspace_id'], 'path': p['path'], 'before': before}
        if before != p['precondition']:
            return self.receipt(request, 'conflict', write=target, detail='Target changed since the planning evidence')
        db.execute('INSERT OR REPLACE INTO files VALUES (?, ?, ?)', (p['workspace_id'], p['path'], payload['content']))
        db.execute('INSERT INTO executions VALUES (?, ?)', (p['operation_id'], 'write'))
        readback = db.execute('SELECT content FROM files WHERE workspace_id=? AND path=?', (p['workspace_id'], p['path'])).fetchone()[0]
        digest = hashlib.sha256(readback.encode()).hexdigest()
        return self.receipt(request, 'applied', write={**target, 'after': {'sha256': digest}, 'readback_sha256': digest})

    def start(self, db, request):
        p = request['payload']
        db.execute('INSERT INTO processes VALUES (?, ?, 0)', (p['operation_id'], p['profile']['id']))
        db.execute('INSERT INTO executions VALUES (?, ?)', (p['operation_id'], 'exec'))
        return self.receipt(request, 'running', exec={'started': True, 'cleanup': 'running'})

    def query(self, operation_id, request_digest):
        self.reachable()
        with self.db() as db:
            row = db.execute('SELECT request_digest, receipt FROM receipts WHERE operation_id=?', (operation_id,)).fetchone()
            if not row or row[0] != request_digest:
                return {'found': False, 'authoritative': self.fault('receipts_authoritative', True)}
            receipt = json.loads(row[1])
            if receipt['payload']['state'] == 'running':
                process = db.execute('SELECT profile, polls FROM processes WHERE operation_id=?', (operation_id,)).fetchone()
                behaviour = self.behaviour(operation_id, process[0])
                polls = process[1] + 1
                db.execute('UPDATE processes SET polls=? WHERE operation_id=?', (polls, operation_id))
                if polls >= behaviour['polls']:
                    receipt['payload'].update(state='completed', exec={'started': True, 'cleanup': 'confirmed',
                        'exit_code': behaviour['exit_code'], 'output': behaviour.get('output', ''),
                        'result': behaviour.get('result', {}), 'truncated': False, 'merged': True})
                    db.execute('UPDATE receipts SET receipt=? WHERE operation_id=?', (json.dumps(receipt), operation_id))
            return {'found': True, 'receipt': receipt}

    def cancel(self, operation_id, request_digest, reason):
        self.reachable()
        with self.db() as db:
            row = db.execute('SELECT receipt FROM receipts WHERE operation_id=?', (operation_id,)).fetchone()
            receipt = json.loads(row[0])
            if receipt['payload']['state'] != 'running':
                return {'receipt': receipt}  # it completed before the cancellation won
            process = db.execute('SELECT profile FROM processes WHERE operation_id=?', (operation_id,)).fetchone()
            if self.behaviour(operation_id, process[0]).get('stop') == 'unknown':
                raise effects.ResponseLost('kill sent; process state not confirmed')
            receipt['payload'].update(state='timed_out' if reason == 'timeout' else 'canceled',
                                      exec={'started': True, 'cleanup': 'confirmed', 'signal': 'SIGKILL'})
            db.execute('UPDATE receipts SET receipt=? WHERE operation_id=?', (json.dumps(receipt), operation_id))
            return {'receipt': receipt}


# -------------------------------------------------------------------- Task fixtures
def change_spec(capabilities=('workspace.read', 'artifact.write', 'workspace.write', 'workspace.exec')):
    capabilities = list(capabilities)
    return message('TaskSpec', {'objective': 'Raise max.retries to 5 only if the observed file is unchanged, then prove tests pass.',
        'completion': [{'criterion': 'The exact new configuration was drafted.',
                        'evidence': {'artifact': 'draft', 'sha256': SHA['after']}}],
        'capabilities': capabilities, 'autonomy': {'allowed': capabilities}})


def change_contract(task_id):
    template = {'source': 'task_type', 'ref': 'implementation@1'}
    criteria = [
        {'id': 'c1', 'requirement': 'The exact new configuration was drafted.', 'level': 'REQUIRED',
         'provenance': {'source': 'user'},
         'verifier': {'kind': 'artifact_digest', 'version': 1, 'artifact': 'draft', 'sha256': SHA['after']}},
        {'id': 'no-unauthorized-effect', 'level': 'REQUIRED', 'provenance': {**template, 'invariant': True},
         'requirement': 'Only authorized target effects were admitted, inside the Task workspace, and all are reconciled.',
         'verifier': {'kind': 'capability_journal', 'version': 1, 'predicates': [
             {'name': 'no_target_effect', 'allowed': ['workspace.write', 'workspace.exec']},
             {'name': 'workspace_subset'}, {'name': 'admitted_before_observed'}, {'name': 'effects_reconciled'}]}},
        {'id': 'change-made', 'level': 'REQUIRED', 'provenance': template,
         'requirement': 'Exactly the configuration file changed, to the requested content, with evidence.',
         'verifier': {'kind': 'change_set', 'version': 1, 'workspace_id': WORKSPACE, 'predicates': [
             {'name': 'changed', 'paths': [CONFIG]}, {'name': 'expected_content', 'path': CONFIG, 'sha256': SHA['after']},
             {'name': 'only_paths', 'allowed': [CONFIG]}, {'name': 'evidence_complete'}]}},
        {'id': 'write-respected-state', 'level': 'REQUIRED', 'provenance': template,
         'requirement': 'The write applied against the state it was planned from.',
         'verifier': {'kind': 'capability_result', 'version': 1, 'operation_class': 'workspace.write', 'path': CONFIG,
                      'predicates': [{'name': 'state', 'equals': 'applied'}, {'name': 'resulting_digest', 'sha256': SHA['after']}]}},
        {'id': 'tests-pass', 'level': 'REQUIRED', 'provenance': {'source': 'user'},
         'requirement': 'The reviewed unit-test profile passed after the last change.',
         'verifier': {'kind': 'capability_result', 'version': 1, 'operation_class': 'workspace.exec', 'profile': 'unit-tests',
                      'predicates': [{'name': 'exit_code', 'equals': 0}, {'name': 'result_field', 'field': 'failures', 'equals': 0},
                                     {'name': 'result_after_last_change'}, {'name': 'cleanup_confirmed'}]}},
    ]
    return message('CompletionContract', {'task_id': task_id, 'revision': 0, 'previous_ref': None, 'amendment_ref': None,
        'task_type': {'template': 'implementation', 'version': 1}, 'criteria': criteria})


def change_request(task_id, ask_before=(), profiles=('unit-tests',)):
    spec = change_spec()
    grant = {'capabilities': spec['payload']['capabilities'], 'workspaces': [WORKSPACE], 'profiles': list(profiles)}
    if ask_before:
        grant['ask_before'] = list(ask_before)
    return message('TaskRequest', {'task_spec': spec, 'grant': grant, 'contract': change_contract(task_id)})


def read(artifact='current'):
    return {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.read',
            'input': {'form': 'file', 'workspace_id': WORKSPACE, 'path': CONFIG, 'artifact': artifact}}


def draft(content=AFTER):
    return {'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write', 'input': {'name': 'draft', 'content': content}}


def write(content_ref, receipt_ref=None, sha256=None, path=CONFIG):
    precondition = {'receipt': receipt_ref} if receipt_ref else {'sha256': sha256} if sha256 else {'absent': True}
    return {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.write',
            'input': {'workspace_id': WORKSPACE, 'path': path, 'precondition': precondition, 'content_ref': content_ref}}


def run(profile='unit-tests', args=()):
    value = {'workspace_id': WORKSPACE, 'profile': profile}
    if args:
        value['args'] = list(args)
    return {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.exec', 'input': value}


def latest_receipt(turn):
    refs = [item['source'] for item in turn['context']
            if item['authority'] == 'artifact' and item['content'].get('name') == 'receipt']
    return refs[-1]


def artifact_ref(turn, name):
    return next(item['source'] for item in turn['context']
                if item['authority'] == 'artifact' and item['content'].get('name') == name)
