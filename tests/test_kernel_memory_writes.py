"""CP.2 deterministic admission/read/compiler proofs, separate from native storage."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from test_kernel_context_plane import Fixture, need
from runtime.kernel import journal
from runtime.kernel.context_plane import ContextPlane
from runtime.kernel.contracts import encode, message
from runtime.kernel.execution import Capabilities, policy_gate, evaluate
from runtime.kernel.memory_writes import MemoryError, MemoryWriteGrant, PersistentMemoryFacade, validate_write
from runtime.kernel.mirix_storage import MirixProcessStore, MirixStorageConfig, PostgresMirixStore


class TestStore:
    """Explicit test double; not registered as a production storage provider."""
    __test__ = False
    def __init__(self):
        self.rows, self.identities = {}, {}
        self.lose_response = False

    def commit(self, entry, token):
        key = (entry['context'], entry['domain'], token)
        if key in self.identities:
            identity = self.identities[key]
            if {k: v for k, v in self.rows[identity].items() if k != 'id'} != entry:
                raise MemoryError('IDEMPOTENCY_CONFLICT')
            return identity, True
        identity = 'test-' + str(len(self.rows))
        self.rows[identity] = {'id': identity, **deepcopy(entry)}
        self.identities[key] = identity
        if self.lose_response:
            self.lose_response = False
            raise ConnectionError('response lost after commit')
        return identity, False

    def read(self, contexts, domains, current, execution, query=None, locator=None):
        return [deepcopy(row) for row in self.rows.values()
                if row['context'] in contexts and row['domain'] in domains
                and (row['retention'] == 'RETAINED' or (row['context'] == current and row['execution'] == execution))
                and (locator is None or row['id'] == locator)
                and (query is None or query.casefold() in row['content'].casefold())]


def configure(f, backend):
    f.spec['capabilities'].append('memory.recordObservation')
    f.spec['autonomy']['allowed'].append('memory.recordObservation')
    f.spec_ref = f.store.put_json('control', message('TaskSpec', f.spec))
    f.state['spec_ref'] = f.spec_ref
    f.snapshot['payload'].update(spec_ref=f.spec_ref, memory_entries=[])
    f.accept_contract()
    def grant(_):
        bound = f.bound()
        return MemoryWriteGrant('control', bound.fingerprint, 'host-operator',
            bound.snapshot['context'], 'private', frozenset({'observe', 'declare'}), True)
    facade = PersistentMemoryFacade(f.authority, backend, grant)
    f.plane = ContextPlane(f.store, f.authority, facade)
    return facade


class MemoryWriteTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.f = Fixture(Path(self.directory.name))
        self.store = TestStore()
        self.memory = configure(self.f, self.store)
        self.request = {'content': 'answer attempt is a hypothesis: Olá.', 'idempotency_key': 'write-1'}

    def observe(self):
        return self.memory.observe(self.f.state, self.f.spec, self.request)

    def declare(self):
        return self.memory.declare(self.f.state, self.f.spec, self.request)

    def test_observation_working_and_human_retained_remain_distinct(self):
        first = self.observe()
        self.assertEqual((first['origin'], first['status'], first['retention']),
                         ('AGENT_OBSERVATION', 'UNVERIFIED', 'WORKING'))
        self.request['idempotency_key'] = 'human-1'
        second = self.declare()
        self.assertEqual((second['origin'], second['status'], second['retention']),
                         ('USER_DECLARATION', 'DECLARED', 'RETAINED'))
        rows, status = self.memory.search(self.f.bound(), 'answer')
        self.assertEqual(status, 'SUCCESS')
        self.assertEqual({r['retention'] for r in rows}, {'WORKING', 'RETAINED'})
        self.assertEqual({r['content'] for r in rows}, {self.request['content']})
        self.assertEqual(evaluate(self.f.spec, self.f.state, self.f.store)['payload']['outcome'], 'unsatisfied')

    def test_forged_provenance_retention_scopes_and_ids_rejected_before_write(self):
        for key in ('origin', 'status', 'retention', 'authority', 'context', 'domain', 'id', 'parent', 'scope',
                    'USER_DECLARATION', 'VERIFIED_SUCCESS', 'VERIFIED_FAILURE', 'operation_class', 'backend'):
            with self.subTest(key=key), self.assertRaises(MemoryError):
                self.memory.observe(self.f.state, self.f.spec, {**self.request, key: 'forged'})
        self.assertEqual(self.store.rows, {})

    def test_human_path_requires_separate_trusted_grant(self):
        grant = self.memory.grants('control')
        self.memory.grants = lambda _: replace(grant, operations=frozenset({'observe'}))
        with self.assertRaisesRegex(MemoryError, 'DENIED'):
            self.declare()
        self.assertEqual(self.observe()['retention'], 'WORKING')

    def test_parent_sibling_foreign_and_stale_grants_denied(self):
        original = self.memory.grants('control')
        for change in ({'context': 'project'}, {'context': 'sibling'}, {'domain': 'foreign'},
                       {'principal': 'worker'}, {'task_id': 'other'}, {'binding_fingerprint': 'stale'},
                       {'local_processing': False}, {'operations': frozenset()}):
            self.memory.grants = lambda _, c=change: replace(original, **c)
            with self.subTest(change=change), self.assertRaisesRegex(MemoryError, 'DENIED'):
                self.observe()
        self.assertEqual(self.store.rows, {})

    def test_scoped_idempotency_replay_and_conflict(self):
        first = self.observe()
        second = self.observe()
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(second['idempotency'], 'REPLAY')
        self.request['content'] = 'changed'
        with self.assertRaisesRegex(MemoryError, 'IDEMPOTENCY_CONFLICT'):
            self.observe()
        self.f.snapshot['payload']['context'] = 'sibling'
        unrelated = self.observe()
        self.assertNotEqual(first['id'], unrelated['id'])
        self.assertEqual(len(self.store.rows), 2)

    def test_same_token_different_security_domain_has_no_collision(self):
        first = self.observe()
        original = self.memory.grants
        self.memory.grants = lambda task: replace(original(task), domain='shared')
        other = self.observe()
        self.assertNotEqual(first['id'], other['id'])
        self.assertEqual(other['idempotency'], 'CREATED')

    def test_response_loss_does_not_claim_success_replay_has_one_effect(self):
        self.store.lose_response = True
        with self.assertRaisesRegex(MemoryError, 'UNKNOWN'):
            self.observe()
        self.assertEqual(len(self.store.rows), 1)
        self.assertEqual(self.observe()['idempotency'], 'REPLAY')
        self.assertEqual(len(self.store.rows), 1)

    def test_replay_rechecks_current_authority(self):
        self.observe()
        self.f.snapshot['payload']['policy_domains'] = []
        with self.assertRaisesRegex(MemoryError, 'DENIED'):
            self.observe()
        self.assertEqual(len(self.store.rows), 1)

    def test_revocation_after_commit_preserves_unknown_effect_semantics(self):
        commit = self.store.commit
        def revoke_after(entry, token):
            result = commit(entry, token)
            self.f.snapshot['payload']['policy_domains'] = []
            return result
        self.store.commit = revoke_after
        with self.assertRaisesRegex(MemoryError, 'UNKNOWN'):
            self.observe()
        self.assertEqual(len(self.store.rows), 1)

    def test_parent_sibling_domain_isolation_and_retained_inheritance(self):
        working = self.observe()
        self.request['idempotency_key'] = 'declared'
        retained = self.declare()
        for context in ('project', 'sibling', 'other'):
            self.f.snapshot['payload']['context'] = context
            for identity in (working['id'], retained['id'], 'nonexistent'):
                self.assertEqual(self.memory.retrieve(self.f.bound(), identity), ([], 'DENIED'))
        self.f.snapshot['payload']['context'] = 'child'
        self.assertEqual(self.memory.retrieve(self.f.bound(), working['id']), ([], 'DENIED'))
        self.assertEqual(self.memory.retrieve(self.f.bound(), retained['id'])[1], 'SUCCESS')
        self.f.snapshot['payload']['security_domains'] = ['shared']
        self.assertEqual(self.memory.retrieve(self.f.bound(), retained['id']), ([], 'DENIED'))

    def test_success_requires_readback_and_storage_metadata_validation(self):
        with patch.object(self.store, 'read', return_value=[]):
            with self.assertRaisesRegex(MemoryError, 'UNKNOWN'):
                self.observe()
        row = next(iter(self.store.rows.values()))
        row['retention'] = 'RETAINED'
        self.assertEqual(self.memory.search(self.f.bound(), 'answer'), ([], 'UNAVAILABLE'))

    def test_backend_cannot_widen_result_scope(self):
        self.observe()
        row = deepcopy(next(iter(self.store.rows.values())))
        row['context'] = 'sibling'
        with patch.object(self.store, 'read', return_value=[row]):
            self.assertEqual(self.memory.search(self.f.bound(), 'answer'), ([], 'UNAVAILABLE'))

    def test_fresh_delta_compiles_new_source_and_preserves_contract(self):
        first = self.f.initial()
        before = self.f.store.read('control', first['admission']['packet_ref'])
        current_contract = deepcopy(self.f.plane.current_contract(self.f.state, self.f.spec))
        receipt = self.observe()
        result = self.f.plane.compile(self.f.state, self.f.spec, 'control/2',
            request=need(base_ref=first['admission']['packet_ref']), previous=first['admission'])
        packet = self.f.store.read('control', result['admission']['packet_ref'])
        self.assertNotIn(receipt['id'].encode(), before)
        self.assertIn(receipt['id'].encode(), packet)
        entries = self.f.store.read_json('control', result['admission']['packet_ref'])['payload']['context']
        memory = [json.loads(e['content']) for e in entries if e['source'].startswith('memory:')]
        self.assertEqual(memory[0]['retention'], 'WORKING')
        self.assertEqual(memory[0]['origin'], 'AGENT_OBSERVATION')
        self.assertNotIn('domain', memory[0])
        self.assertNotIn('embedding_config', memory[0])
        self.assertLessEqual(len(packet), 4096)
        self.assertEqual(current_contract, self.f.plane.current_contract(self.f.state, self.f.spec))

    def test_policy_gate_and_runtime_admission(self):
        initial = self.f.initial()
        decision = message('CognitiveDecision', {'task_id': 'control', 'task_revision': 0,
            'turn_id': 'control/1', 'next_action': {'type': 'INVOKE_CAPABILITY',
                'capability': 'memory.recordObservation', 'input': self.request}})
        self.assertEqual(policy_gate(decision, self.f.state, self.f.spec)['outcome'], 'allow')
        self.assertEqual(policy_gate(decision, self.f.state, self.f.spec, {'capabilities': []})['outcome'], 'deny')
        forged = deepcopy(decision)
        forged['payload']['next_action']['input']['operation_class'] = 'task.compute'
        self.assertEqual(policy_gate(forged, self.f.state, self.f.spec)['outcome'], 'deny')
        self.assertEqual(journal.effect_scope(journal.operation_class('memory.recordObservation')), journal.TARGET_EFFECT)
        caps = Capabilities(self.f.store, self.f.root / 'effects.sqlite', context_plane=self.f.plane)
        request = message('CapabilityRequest', {'task_id': 'control', 'operation_id': 'control/1',
            'capability': 'memory.recordObservation', 'input': self.request})
        self.assertEqual(caps.execute(request)['payload']['outcome'], 'failure')
        result = caps.execute(request, context_runtime=(self.f.state, self.f.spec, initial['admission']))
        self.assertEqual(result['payload']['outcome'], 'success')
        self.assertEqual(result['payload']['artifacts'], {})

    def test_unknown_commit_is_journal_visible_uncertainty(self):
        initial = self.f.initial()
        caps = Capabilities(self.f.store, self.f.root / 'effects.sqlite', context_plane=self.f.plane)
        self.store.lose_response = True
        request = message('CapabilityRequest', {'task_id': 'control', 'operation_id': 'control/1',
            'capability': 'memory.recordObservation', 'input': self.request})
        result = caps.execute(request, context_runtime=(self.f.state, self.f.spec, initial['admission']))
        self.assertEqual(result['payload']['outcome'], 'uncertain')
        self.assertNotIn('response lost', encode(result).decode())

    def test_declaring_does_not_upgrade_existing_observation_identity(self):
        working = self.observe()
        retained = self.declare()  # a distinct, explicitly authorized direct declaration
        self.assertNotEqual(working['id'], retained['id'])
        self.assertEqual(self.store.rows[working['id']]['retention'], 'WORKING')
        self.assertEqual(self.store.rows[retained['id']]['retention'], 'RETAINED')

    def test_working_is_not_reused_by_another_task_in_the_same_context(self):
        from runtime.kernel.context_plane import LocalContextAuthority
        first = self.observe()
        declaration = self.declare()
        state = {**self.f.state, 'task_id': 'next'}
        state['spec_ref'] = self.f.store.put_json('next', message('TaskSpec', self.f.spec))
        snapshot = deepcopy(self.f.snapshot)
        snapshot['payload'].update(task_id='next', spec_ref=state['spec_ref'])
        authority = LocalContextAuthority(lambda _: snapshot, principal='host-operator')
        bound = authority.resolve(state, self.f.spec)
        fresh = PersistentMemoryFacade(authority, self.store,
            lambda _: MemoryWriteGrant('next', bound.fingerprint, 'host-operator', 'task',
                'private', frozenset({'observe'}), True))
        self.assertEqual(fresh.retrieve(bound, first['id']), ([], 'DENIED'))
        self.assertEqual(fresh.retrieve(bound, declaration['id'])[1], 'SUCCESS')
        # The hidden prior working entry must not collide with the new Task's token.
        second = fresh.observe(state, self.f.spec, self.request)
        self.assertNotEqual(first['id'], second['id'])

    def test_storage_configuration_cannot_egress_to_remote_provider(self):
        config = MirixStorageConfig('/usr/bin/python3', '/private/config', 'n', 'o', 'u', 'c')
        for endpoint in ('https://example.com/v1/embeddings', 'http://localhost:9000/v1/embeddings'):
            with self.assertRaisesRegex(MemoryError, 'UNAVAILABLE'):
                PostgresMirixStore(replace(config, embedding_endpoint=endpoint))

    def test_response_loss_reconciliation_does_not_redispatch_or_hide_unknown(self):
        config = MirixStorageConfig('/usr/bin/python3', '/private/config', 'n', 'o', 'u', 'c')
        bridge = MirixProcessStore(config)
        with patch.object(bridge, '_call', side_effect=[MemoryError('UNKNOWN'), ['id', True]]) as call:
            self.assertEqual(bridge.commit({}, 'token'), ['id', True])
            self.assertEqual([c.args[0] for c in call.call_args_list], ['commit', 'lookup'])
        with patch.object(bridge, '_call', side_effect=[MemoryError('UNKNOWN'), MemoryError('UNAVAILABLE')]):
            with self.assertRaisesRegex(MemoryError, 'UNKNOWN'):
                bridge.commit({}, 'token')

    def test_existing_sqlalchemy_uri_is_normalized_without_changing_identity(self):
        from types import SimpleNamespace
        credentials = Path(self.directory.name) / 'config'
        config = MirixStorageConfig('/usr/bin/python3', str(credentials), 'n', 'o', 'u', 'c')
        driver = Mock()
        for scheme in ('postgresql+pg8000', 'postgresql+psycopg2', 'postgresql'):
            uri = scheme + '://fixture:fixture%40password@127.0.0.1:5432/mirix'
            credentials.write_text(f'[recall_storage]\nuri={uri}\n[archival_storage]\nuri={uri}\n')
            credentials.chmod(0o600)
            with patch.dict('sys.modules', {'psycopg2': SimpleNamespace(connect=driver)}):
                PostgresMirixStore(config).connect()
            self.assertEqual(driver.call_args.args,
                             ('postgresql://fixture:fixture%40password@127.0.0.1:5432/mirix',))
        for suffix in ('?host=remote.example', '#fragment'):
            uri = 'postgresql://fixture@127.0.0.1/mirix' + suffix
            credentials.write_text(f'[recall_storage]\nuri={uri}\n[archival_storage]\nuri={uri}\n')
            with patch.dict('sys.modules', {'psycopg2': SimpleNamespace(connect=driver)}), self.assertRaises(MemoryError):
                PostgresMirixStore(config).connect()
        self.assertEqual(driver.call_count, 3)

    def test_exact_memory_content_does_not_satisfy_completion_evidence(self):
        self.request['content'] = 'GOOD'  # exactly the Task's desired evidence bytes
        self.declare()
        self.assertEqual(evaluate(self.f.spec, self.f.state, self.f.store)['payload']['outcome'], 'unsatisfied')
        self.assertNotIn('answer', self.f.state['artifacts'])

    def test_embeddings_never_enter_source_provenance_or_compiler(self):
        self.observe()
        row = next(iter(self.store.rows.values()))
        row['embedding'] = [1.0] * 8
        self.assertEqual(self.memory.search(self.f.bound(), 'answer'), ([], 'UNAVAILABLE'))

    def test_reconstructed_facade_reads_working_without_changing_retention(self):
        receipt = self.observe()
        fresh = PersistentMemoryFacade(self.f.authority, self.store, self.memory.grants)
        rows, status = fresh.retrieve(self.f.bound(), receipt['id'])
        self.assertEqual(status, 'SUCCESS')
        self.assertEqual(rows[0]['retention'], 'WORKING')
        # This is reconstruction of the facade, not native persistence acceptance.


class MemoryWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_unknown_memory_effect_blocks_completion_even_with_good_artifact(self):
        from tests.completion_harness import Crash, Harness
        from tests.completion_fixtures import decision
        with tempfile.TemporaryDirectory() as directory:
            f = Fixture(Path(directory))
            backend = TestStore()
            backend.lose_response = True
            configure(f, backend)
            def cognitive(packet):
                first = packet['payload']['iteration'] == 1
                return decision(packet, {'type': 'INVOKE_CAPABILITY',
                    'capability': 'memory.recordObservation' if first else 'artifact.write',
                    'input': {'content': 'GOOD', 'idempotency_key': 'unknown'} if first else
                             {'name': 'answer', 'content': 'GOOD'}})
            async def checkpoint(ctx, stage, state):
                if stage.startswith('verification-') and state['iteration'] == 2:
                    raise Crash()
            caps = Capabilities(f.store, f.root / 'effects.sqlite', context_plane=f.plane)
            harness = Harness(f.store, cognitive, caps, checkpoint=checkpoint)
            with self.assertRaises(Crash):
                await harness.invoke('control', message('TaskSpec', f.spec))
            state = harness.state('control')
            evaluation = f.store.read_json('control', state['completion_ref'])['payload']
            self.assertFalse(evaluation['legality']['legal'])
            self.assertNotEqual(state['lifecycle'], 'COMPLETED')
            self.assertEqual(f.store.read('control', state['artifacts']['answer']), b'GOOD')
            facts = journal.read(f.store, 'control', state['journal_head'], state['journal_length'])
            self.assertTrue(any(e.get('outcome') == 'uncertain' and
                                e['operation_id'] == 'control/1' for _, e in facts))
            self.assertEqual(len(backend.rows), 1)

    async def test_governed_write_delta_worker_and_journal_replay(self):
        from tests.completion_harness import Harness
        from tests.completion_fixtures import decision
        with tempfile.TemporaryDirectory() as directory:
            f = Fixture(Path(directory))
            backend = TestStore()
            configure(f, backend)
            packets = []
            def worker(packet, operation):
                packets.append(deepcopy(packet))
                return {'outcome': 'success', 'attempt_id': 'fixture',
                        'content': 'DRAFT' if len(packets) == 1 else 'GOOD'}
            def cognitive(packet):
                turn = packet['payload']
                ref = next(c['source'] for c in turn['context']
                           if c['content'] == {'name': 'compiled-context'})
                if turn['iteration'] == 2:
                    capability, value = 'memory.recordObservation', {
                        'content': 'answer hypothesis, still unverified', 'idempotency_key': 'loop-observation'}
                elif turn['iteration'] == 3:
                    capability, value = 'context.request', need(base_ref=ref)
                else:
                    capability, value = 'worker.run', {'packet_ref': ref, 'artifact': 'answer'}
                return decision(packet, {'type': 'INVOKE_CAPABILITY', 'capability': capability, 'input': value})
            caps = Capabilities(f.store, f.root / 'effects.sqlite', worker=worker, context_plane=f.plane)
            harness = Harness(f.store, cognitive, caps)
            result = await harness.invoke('control', message('TaskSpec', f.spec))
            self.assertEqual(result['payload']['outcome'], 'COMPLETED')
            self.assertEqual(len(packets), 2)
            self.assertNotIn(b'loop-observation', encode(packets[0]))
            entries = [json.loads(e['content']) for e in packets[1]['payload']['context']
                       if e['source'].startswith('memory:')]
            self.assertEqual([(e['origin'], e['status'], e['retention']) for e in entries],
                             [('AGENT_OBSERVATION', 'UNVERIFIED', 'WORKING')])
            for packet in packets:
                self.assertLessEqual(len(encode(packet)), 4096)
                self.assertNotIn(b'"domain"', encode(packet))
                self.assertNotIn(b'"embedding_config"', encode(packet))
            state = harness.state('control')
            facts = journal.read(f.store, 'control', state['journal_head'], state['journal_length'])
            admitted = [e for _, e in facts if e['phase'] == 'admitted']
            self.assertEqual([(e['capability'], e['operation_class'], e['contract_revision']) for e in admitted],
                [('worker.run', 'worker.run', 0), ('memory.recordObservation', 'memory.write', 0),
                 ('context.request', 'context.read', 0), ('worker.run', 'worker.run', 0)])
            self.assertEqual(len([e for _, e in facts if e['phase'] == 'observed']), 4)
            evaluation = f.store.read_json('control', state['completion_ref'])['payload']
            self.assertEqual(evaluation['outcome'], 'satisfied')
            self.assertTrue(evaluation['legality']['legal'])
            self.assertEqual(await harness.invoke('control'), result)
            self.assertEqual(len(packets), 2)
            self.assertEqual(len(backend.rows), 1)


if __name__ == '__main__':
    unittest.main()
