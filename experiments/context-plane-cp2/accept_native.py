#!/usr/bin/env python3
"""CP.2 bounded native qualification. Run only through its trusted HOST suite.

Uses the existing MIRIX database/embedding service. Installs only the CP.2 metadata
schema; provisions no service. Restarts only accepted blaine-mirix.service. Synthetic
records have a fresh private namespace and are removed explicitly after assertions.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.request
import uuid
from dataclasses import asdict, replace

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_kernel_context_plane import Fixture, need
from test_kernel_memory_writes import configure
from runtime.kernel.context_plane import ContextPlane
from runtime.kernel.contracts import encode, message
from runtime.kernel.execution import Capabilities, policy_gate, evaluate
from runtime.kernel.memory_writes import MemoryError, PersistentMemoryFacade
from runtime.kernel.mirix_storage import MirixProcessStore, MirixStorageConfig

PYTHON = str(Path.home() / 'workspace/mirix/.venv/bin/python')
CREDENTIALS = str(Path.home() / '.mirix/config')


def db_support(config, action):
    """Fixed supporting assertions/fixture teardown; facade readback is primary."""
    code = r'''
import json,sys
from runtime.kernel.mirix_storage import MirixStorageConfig,PostgresMirixStore
request=json.load(sys.stdin); c=MirixStorageConfig(**request['config'])
db=PostgresMirixStore(c).connect();out={}
try:
 with db,db.cursor() as cur:
  action=request['action']
  if action=='identity':
   cur.execute("SELECT c.organization_id,u.id,c.id FROM clients c JOIN users u ON u.organization_id=c.organization_id WHERE NOT c.is_deleted AND NOT u.is_deleted ORDER BY c.id,u.id LIMIT 1")
   row=cur.fetchone();assert row
   out={'organization':row[0],'user':row[1],'client':row[2]}
  elif action=='support':
   stage='support-query'
   cur.execute("SELECT e.raw_id,e.metadata,r.filter_tags,r.context_embedding::text,r.context FROM blaine_memory_entry_v1 e JOIN raw_memory r ON r.id=e.raw_id WHERE e.namespace=%s ORDER BY e.raw_id",(c.namespace,))
   rows=cur.fetchall();stage='support-row-count';assert len(rows)==4
   for identity,metadata,tags,vector,content in rows:
    stage='support-vector'
    embedding=json.loads(vector)
    assert len(embedding)==4096 and any(v!=0 for v in embedding)
    stage='support-metadata'
    assert tags['blaine']==metadata
    stage='support-partition'
    assert tags['scope']==PostgresMirixStore(c)._partition(metadata['context'],metadata['domain'])
   # The FK protects BOTH statuses against an age-selected/raw cleanup delete.
   protected=0
   stage='support-cleanup-refusal'
   for identity,*_ in rows:
    cur.execute('SAVEPOINT retention_check')
    try:
     cur.execute('DELETE FROM raw_memory WHERE id=%s',(identity,))
    except Exception as error:
     # PostgreSQL may distinguish RESTRICT (23001) from a generic FK violation
     # (23503). Require the exact CP.2 guard, not just any integrity error.
     if error.pgcode not in ('23001','23503') or error.diag.constraint_name!='blaine_memory_entry_v1_raw_id_fkey':
      raise
     protected+=1
    finally:
     cur.execute('ROLLBACK TO SAVEPOINT retention_check')
   out={'rows':len(rows),'local_embeddings':len(rows),'dimensions':4096,'cleanup_deletes_refused':protected}
  elif action=='cleanup':
   cur.execute('DELETE FROM blaine_memory_entry_v1 WHERE namespace=%s RETURNING raw_id',(c.namespace,))
   ids=[r[0] for r in cur.fetchall()]
   cur.execute('DELETE FROM raw_memory WHERE id=ANY(%s) AND organization_id=%s AND user_id=%s',(ids,c.organization,c.user))
   out={'removed_synthetic_records':cur.rowcount}
  else: raise ValueError()
finally: db.close()
print(json.dumps(out))
'''
    code = ('import json,sys\nstage="database-support"\ntry:\n' + textwrap.indent(code, ' ') +
            '\nexcept Exception as error:\n'
            ' print(json.dumps({"stage":stage,"error_type":type(error).__name__,"sqlstate":getattr(error,"pgcode",None)}))\n'
            ' sys.exit(1)\n')
    result = subprocess.run([PYTHON, '-c', code], cwd=ROOT,
        input=encode({'config': asdict(config), 'action': action}), capture_output=True, timeout=30,
        env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    if result.returncode:
        # Only fixed stage, exception class and SQLSTATE; never exception text/SQL.
        safe = json.loads(result.stdout) if result.stdout else {'stage': 'support-process'}
        raise AssertionError('Native database support check failed: ' + json.dumps(safe))
    return json.loads(result.stdout)


class LostCommitReply(MirixProcessStore):
    """Kill only the owned writer after native commit, before it returns a receipt."""
    def _call(self, operation, value):
        if operation != 'commit' or getattr(self, 'lost', False):
            return super()._call(operation, value)
        self.lost = True
        code = """
import json,os,signal,sys
from runtime.kernel.mirix_storage import MirixStorageConfig,PostgresMirixStore
r=json.load(sys.stdin)
PostgresMirixStore(MirixStorageConfig(**r['config'])).commit(**r['value'])
os.kill(os.getpid(),signal.SIGKILL)
"""
        result = subprocess.run([self.config.python, '-c', code], cwd=ROOT,
            input=encode({'config': asdict(self.config), 'value': value}),
            capture_output=True, timeout=90, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        if result.returncode != -9:
            raise AssertionError('Owned writer did not reach post-commit SIGKILL')
        raise MemoryError('UNKNOWN')


def main():
    report = {'status': 'RUNNING', 'checks': {}, 'restart': None,
              'scope': 'CP.2 synthetic local native persistence; no cloud cognition',
              'production_deployment': False}
    namespace = 'cp2-native-' + uuid.uuid4().hex
    output = ROOT / '.local/verification/cp2-native' / namespace
    output.mkdir(parents=True)
    config = None
    installed = False
    def check(name, condition):
        report['checks'][name] = bool(condition)
        if not condition:
            raise AssertionError(name)
    try:
        config = MirixStorageConfig(PYTHON, CREDENTIALS, namespace, 'probe', 'probe', 'probe')
        config = replace(config, **db_support(config, 'identity'))
        store = MirixProcessStore(config)
        check('schema_v1', store.install() == {'schema': 1})
        installed = True
        with tempfile.TemporaryDirectory(prefix='cp2-native-') as temporary:
            f = Fixture(Path(temporary))
            memory = configure(f, LostCommitReply(config))
            original_snapshot = json.loads(json.dumps(f.snapshot))
            first = f.initial()
            first_bytes = f.store.read('control', first['admission']['packet_ref'])
            contract_before = f.plane.current_contract(f.state, f.spec)
            value = {'content': 'answer hypothesis X failed: Olá.', 'idempotency_key': 'native-write'}
            decision = message('CognitiveDecision', {'task_id': 'control', 'task_revision': 0,
                'turn_id': 'control/1', 'next_action': {'type': 'INVOKE_CAPABILITY',
                    'capability': 'memory.recordObservation', 'input': value}})
            check('policy_admits_observation', policy_gate(decision, f.state, f.spec)['outcome'] == 'allow')
            caps = Capabilities(f.store, f.root / 'effects.sqlite', context_plane=f.plane)
            request = message('CapabilityRequest', {'task_id': 'control', 'operation_id': 'control/1',
                'capability': 'memory.recordObservation', 'input': value})
            result = caps.execute(request, context_runtime=(f.state, f.spec, first['admission']))
            check('runtime_write_success', result['payload']['outcome'] == 'success')
            check('post_commit_sigkill_reconciled', result['payload']['output']['idempotency'] == 'REPLAY')
            working = result['payload']['output']
            check('observation_working_unverified', (working['origin'], working['status'], working['retention']) ==
                  ('AGENT_OBSERVATION', 'UNVERIFIED', 'WORKING'))
            # Same governed operation, fresh backend process and connection.
            replay = memory.observe(f.state, f.spec, value)
            check('scoped_replay', replay['id'] == working['id'] and replay['idempotency'] == 'REPLAY')
            try:
                memory.observe(f.state, f.spec, {**value, 'content': 'changed'})
            except MemoryError as error:
                check('changed_payload_conflict', error.status == 'IDEMPOTENCY_CONFLICT')
            else:
                check('changed_payload_conflict', False)
            grant_provider = memory.grants
            memory.grants = lambda task: replace(grant_provider(task), operations=frozenset({'observe'}))
            try:
                memory.declare(f.state, f.spec, value)
            except MemoryError as error:
                check('ungranted_human_declaration_denied', error.status == 'DENIED')
            else:
                check('ungranted_human_declaration_denied', False)
            memory.grants = grant_provider
            # Explicit operator declaration directly at the project; no promotion.
            f.snapshot['payload']['context'] = 'project'
            declaration = {'content': 'answer preference: preserve exact text.', 'idempotency_key': 'human-declaration'}
            retained = memory.declare(f.state, f.spec, declaration)
            check('human_retained', (retained['origin'], retained['status'], retained['retention']) ==
                  ('USER_DECLARATION', 'DECLARED', 'RETAINED'))
            replay = memory.declare(f.state, f.spec, declaration)
            check('retained_scoped_replay', replay['id'] == retained['id'] and replay['idempotency'] == 'REPLAY')
            try:
                memory.declare(f.state, f.spec, {**declaration, 'content': 'changed human declaration'})
            except MemoryError as error:
                check('retained_changed_payload_conflict', error.status == 'IDEMPOTENCY_CONFLICT')
            else:
                check('retained_changed_payload_conflict', False)
            f.snapshot['payload']['context'] = 'sibling'
            sibling = memory.observe(f.state, f.spec, value)
            check('same_token_unrelated_context', sibling['id'] != working['id'])
            f.snapshot['payload']['context'] = 'task'
            f.snapshot['payload']['security_domains'].append('foreign')
            f.snapshot['payload']['policy_domains'].append('foreign')
            memory.grants = lambda task: replace(grant_provider(task), domain='foreign')
            foreign = memory.observe(f.state, f.spec,
                {'content': 'answer FOREIGN_PROTECTED_SENTINEL', 'idempotency_key': 'native-write'})
            check('same_token_unrelated_domain', foreign['id'] != working['id'] and foreign['idempotency'] == 'CREATED')
            memory.grants = grant_provider
            f.snapshot = json.loads(json.dumps(original_snapshot))
            rows, status = memory.search(f.bound(), 'answer')
            check('facade_committed_readback', status == 'SUCCESS' and len(rows) == 2)
            check('exact_source_readback', any(r['content'] == value['content'] for r in rows))
            check('unrelated_before_restart', memory.retrieve(f.bound(), sibling['id']) == ([], 'DENIED') and
                  memory.retrieve(f.bound(), foreign['id']) == ([], 'DENIED'))
            before = encode(rows)
            report['pre_restart_facade_sha256'] = hashlib.sha256(before).hexdigest()
            report['native_support'] = db_support(config, 'support')
            check('scoped_embeddings_and_retention_guard', report['native_support']['cleanup_deletes_refused'] == 4)
            # Only this accepted service; no host reboot or unrelated restarts.
            invocation = subprocess.run(['systemctl', '--user', 'show', 'blaine-mirix.service',
                                         '--property=InvocationID', '--value'],
                                        capture_output=True, timeout=10, check=True).stdout.strip()
            check('mirix_has_service_invocation', bool(invocation))
            restart = subprocess.run(['systemctl', '--user', 'restart', 'blaine-mirix.service'],
                                     capture_output=True, timeout=120)
            check('mirix_restart_command', restart.returncode == 0)
            deadline = time.monotonic() + 60
            healthy = False
            while time.monotonic() < deadline:
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8531/health', timeout=3) as response:
                        healthy = response.status == 200
                    if healthy:
                        break
                except Exception:
                    pass
                time.sleep(0.5)
            check('mirix_healthy_after_restart', healthy)
            reconstructed = subprocess.run(['systemctl', '--user', 'show', 'blaine-mirix.service',
                                            '--property=InvocationID', '--value'],
                                           capture_output=True, timeout=10, check=True).stdout.strip()
            check('mirix_service_reconstructed', bool(reconstructed) and reconstructed != invocation)
            report['restart'] = 'blaine-mirix.service only; fresh facade/backend processes and binding afterward'
            fresh = PersistentMemoryFacade(f.authority, MirixProcessStore(config), memory.grants)
            after, status = fresh.search(f.bound(), 'answer')
            check('post_restart_facade_exact', status == 'SUCCESS' and encode(after) == before)
            check('post_restart_working', fresh.retrieve(f.bound(), working['id'])[0][0]['retention'] == 'WORKING')
            check('post_restart_retained', fresh.retrieve(f.bound(), retained['id'])[0][0]['retention'] == 'RETAINED')
            replay = fresh.observe(f.state, f.spec, value)
            check('post_restart_working_replay', replay['id'] == working['id'] and replay['idempotency'] == 'REPLAY')
            check('post_restart_forbidden', all(fresh.retrieve(f.bound(), identity) == ([], 'DENIED')
                  for identity in (sibling['id'], foreign['id'], 'nonexistent')))
            f.snapshot['payload']['context'] = 'project'
            check('parent_cannot_read_child', fresh.retrieve(f.bound(), working['id']) == ([], 'DENIED'))
            replay = fresh.declare(f.state, f.spec, declaration)
            check('post_restart_retained_replay', replay['id'] == retained['id'] and replay['idempotency'] == 'REPLAY')
            f.snapshot['payload']['context'] = 'child'
            check('descendant_inherits_retained_only', fresh.retrieve(f.bound(), retained['id'])[1] == 'SUCCESS'
                  and fresh.retrieve(f.bound(), working['id']) == ([], 'DENIED'))
            f.snapshot = json.loads(json.dumps(original_snapshot))
            f.plane = ContextPlane(f.store, f.authority, fresh)
            delta = f.plane.compile(f.state, f.spec, 'control/2',
                request=need(base_ref=first['admission']['packet_ref']), previous=first['admission'])
            packet = f.store.read_json('control', delta['admission']['packet_ref'])
            compiled = [json.loads(e['content']) for e in packet['payload']['context'] if e['source'].startswith('memory:')]
            check('fresh_bounded_delta', len(encode(packet)) <= 4096 and encode(packet) != first_bytes)
            check('provenance_and_retention_compiled', {(r['origin'], r['status'], r['retention']) for r in compiled} == {
                ('AGENT_OBSERVATION', 'UNVERIFIED', 'WORKING'), ('USER_DECLARATION', 'DECLARED', 'RETAINED')})
            check('no_raw_embedding_or_scope_to_worker', all('embedding_config' not in r and 'domain' not in r for r in compiled)
                  and 'FOREIGN_PROTECTED_SENTINEL' not in encode(packet).decode())
            check('completion_contract_unchanged', f.plane.current_contract(f.state, f.spec) == contract_before and
                  evaluate(f.spec, f.state, f.store)['payload']['outcome'] == 'unsatisfied')
            report['compiled_packet_bytes'] = len(encode(packet))
            report['post_restart_facade_sha256'] = hashlib.sha256(encode(after)).hexdigest()
        report['status'] = 'PASS'
    except Exception as error:
        report['status'] = 'FAIL'
        report['error_type'] = type(error).__name__
        # Named assertions are safe; arbitrary exception text may contain source/DSN.
        if isinstance(error, AssertionError):
            report['failed_check'] = str(error)
    finally:
        if config and installed:
            try:
                report['fixture_teardown'] = db_support(config, 'cleanup')
            except Exception:
                report['fixture_teardown'] = 'FAILED; only synthetic namespace may remain'
                report['status'] = 'FAIL'
        (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps({'status': report['status'], 'checks': len(report['checks']), 'evidence': str(output / 'qualification.json')}))
    return 0 if report['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
