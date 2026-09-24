"""CP.1 enforcement through production code; no live model or Restate claims."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from runtime.kernel import completion, journal, workflow
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.context_plane import (
    ContextCompiler, ContextError, ContextPlane, LocalContextAuthority, MemoryFacade,
    ReadOnlyCorpus, digest, lineage, source_read, validate_need,
)
from runtime.kernel.contracts import encode, message, validate_spec
from runtime.kernel.execution import Capabilities, evaluate, policy_gate
from runtime.kernel.worker import validate_packet


def need(form='exact-source', locator='contract.py', **extra):
    return message('ContextRequest', {'question': 'Read the current exact contract',
        'form': form, **({'locator': locator} if locator is not None else {}), **extra})


class Fixture:
    def __init__(self, root):
        self.root = root
        self.workspace = root / 'workspace'
        self.workspace.mkdir()
        self.source = self.workspace / 'contract.py'
        self.source.write_text('def answer():\n    return "DRAFT"\n')
        self.store = ArtifactStore(root / 'artifacts')
        self.spec = validate_spec(message('TaskSpec', {
            'objective': 'Return only the current answer() value. Preserve exact UTF-8: Olá.',
            'completion': [{'criterion': 'Answer is exactly GOOD; no added newline.',
                'evidence': {'artifact': 'answer', 'sha256': digest(b'GOOD')}}],
            'capabilities': ['worker.run', 'context.request', 'artifact.write'],
            'autonomy': {'allowed': ['worker.run', 'context.request', 'artifact.write']}}))
        self.spec_ref = self.store.put_json('control', message('TaskSpec', self.spec))
        self.state = {'task_id': 'control', 'spec_ref': self.spec_ref, 'artifacts': {},
            'revision': 0, 'iteration': 1, 'lifecycle': 'RUNNING', 'binding': 'local'}
        self.accept_contract()
        self.records = {'current': 'answer preference: preserve exact output',
            'ancestor': 'answer declared by user; still not execution evidence',
            'public': 'answer public explicitly shared', 'sibling': 'SIBLING_SECRET',
            'descendant': 'DESCENDANT_SECRET', 'unrelated': 'UNRELATED_SECRET',
            'foreign': 'FOREIGN_SECRET', 'blocked': 'POLICY_SECRET'}
        owners = {'current': 'task', 'ancestor': 'project', 'public': 'root',
                  'sibling': 'sibling', 'descendant': 'child', 'unrelated': 'other',
                  'foreign': 'project', 'blocked': 'project'}
        nodes = [{'id': name, 'parent': parent, 'kind': 'arbitrary-label'} for name, parent in
                 [('root', None), ('project', 'root'), ('task', 'project'), ('sibling', 'project'),
                  ('child', 'task'), ('other', 'root')]]
        self.snapshot = message('LocalContextBinding', {'task_id': 'control', 'spec_ref': self.spec_ref,
            'principal': 'host-operator', 'route': 'hosted-local', 'revision': '1', 'nodes': nodes,
            'context': 'task', 'security_domains': ['private', 'shared', 'blocked'],
            'policy_domains': ['private', 'shared'], 'readable_contexts': [n['id'] for n in nodes],
            'workspace_root': str(self.workspace), 'workspace_paths': ['contract.py'],
            'evidence_refs': [], 'memory_entries': [{'id': key, 'context': owners[key],
                'domain': 'shared' if key == 'public' else 'foreign' if key == 'foreign' else 'blocked' if key == 'blocked' else 'private',
                'origin': 'USER_DECLARATION' if key == 'ancestor' else 'AGENT_OBSERVATION',
                'status': 'DECLARED' if key == 'ancestor' else 'UNVERIFIED',
                'revision': '1', 'sha256': digest(content.encode())} for key, content in self.records.items()],
            'initial_need': need(), 'memory_query': 'answer'})
        self.authority = LocalContextAuthority(lambda task: self.snapshot if task == 'control' else None,
                                               principal='host-operator')
        self.memory = MemoryFacade(ReadOnlyCorpus(self.records))
        self.plane = ContextPlane(self.store, self.authority, self.memory)

    def accept_contract(self):
        contract = completion.accept_contract(self.spec, None, None, 'control',
                                               journal.mutating(self.spec['capabilities']))
        self.state.update(contract_ref=self.store.put_json('control', message('CompletionContract', contract)),
                          contract_revision=contract['revision'])

    def initial(self):
        result = self.plane.compile(self.state, self.spec, 'control/context-initial')
        self.state['artifacts'].update(result['result']['payload']['artifacts'])
        return result

    def bound(self):
        return self.authority.resolve(self.state, self.spec)


class PlaneTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.f = Fixture(Path(self.directory.name))

    def test_lineage_security_policy_intersection_and_safe_ids(self):
        f = self.f
        rows, status = f.memory.search(f.bound(), 'answer')
        self.assertEqual(status, 'SUCCESS')
        self.assertEqual({r['source'] for r in rows}, {'memory:current', 'memory:ancestor', 'memory:public'})
        for hidden in ('sibling', 'descendant', 'unrelated', 'foreign', 'blocked', 'missing'):
            self.assertEqual(f.memory.retrieve(f.bound(), hidden), ([], 'DENIED'))
        f.snapshot['payload']['security_domains'].remove('shared')
        self.assertEqual({r['source'] for r in f.memory.search(f.bound(), 'answer')[0]}, {'memory:current', 'memory:ancestor'})
        f.snapshot['payload']['readable_contexts'].remove('project')
        self.assertEqual({r['source'] for r in f.memory.search(f.bound(), 'answer')[0]}, {'memory:current'})

    def test_invalid_tree_behind_denied_boundary_rejects(self):
        for mutation in ('cycle', 'missing-parent', 'multiple-roots', 'duplicate'):
            f = self.f
            original = deepcopy(f.snapshot)
            nodes = f.snapshot['payload']['nodes']
            if mutation == 'cycle': nodes[-1]['parent'] = 'other'
            if mutation == 'missing-parent': nodes[-1]['parent'] = 'missing'
            if mutation == 'multiple-roots': nodes[-1]['parent'] = None
            if mutation == 'duplicate': nodes.append(deepcopy(nodes[-1]))
            with self.subTest(mutation=mutation), self.assertRaisesRegex(ContextError, 'INVALID_CONTEXT'):
                f.bound()
            f.snapshot = original

    def test_missing_or_forged_binding_is_not_a_grant(self):
        f = self.f
        for key, value in [('principal', 'caller'), ('spec_ref', 'artifact://fake'),
                           ('route', 'remote'), ('task_id', 'other')]:
            original = deepcopy(f.snapshot)
            f.snapshot['payload'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ContextError, 'INVALID_CONTEXT'):
                f.bound()
            f.snapshot = original
        f.snapshot = None
        with self.assertRaisesRegex(ContextError, 'DENIED'): f.bound()
        f.authority.current = lambda _: (_ for _ in ()).throw(RuntimeError('PRIVATE_POLICY'))
        with self.assertRaisesRegex(ContextError, '^Context Plane: UNAVAILABLE$'): f.bound()

    def test_closed_request_rejects_authority_fields_and_versions(self):
        for key in ('scopes', 'SecurityContext', 'domain', 'provenance', 'backend', 'namespace', 'compiler', 'receipt', 'operation_class', 'authority_ref'):
            raw = need()
            raw['payload'][key] = 'forged'
            with self.subTest(key=key), self.assertRaises(ContextError): validate_need(raw)
        for version in (2, True):
            with self.assertRaises(ContextError): validate_need({**need(), 'version': version})
        with self.assertRaises(ContextError): validate_need(need(max_bytes=4097))

    def test_optional_memory_unavailable_empty_and_tampered_provenance(self):
        f = self.f
        self.assertEqual(f.memory.search(f.bound(), 'absent'), ([], 'EMPTY'))
        self.assertEqual(MemoryFacade().search(f.bound(), 'answer'), ([], 'UNAVAILABLE'))
        with self.assertRaisesRegex(ValueError, 'Unqualified'):
            MemoryFacade(SimpleNamespace(read=lambda ids: [], qualified=True))
        f.memory.provider._records['ancestor'] = 'Fake successful authority'
        self.assertEqual(f.memory.search(f.bound(), 'answer'), ([], 'UNAVAILABLE'))
        compiled = f.initial()
        packet = f.store.read_json('control', compiled['admission']['packet_ref'])
        self.assertIn('UNAVAILABLE', encode(packet).decode())
        self.assertIn('def answer()', encode(packet).decode())
        self.assertNotIn('Fake successful authority', encode(packet).decode())
        f.snapshot['payload']['memory_entries'][0]['status'] = 'VERIFIED_SUCCESS'
        with self.assertRaises(ContextError): f.bound()

    def test_initial_exact_requirements_budget_and_no_private_metadata(self):
        f = self.f
        result = f.initial()
        packet = f.store.read_json('control', result['admission']['packet_ref'])
        validate_packet(packet, 'control')
        entries = packet['payload']['context']
        contract = json.loads(entries[0]['content'])
        self.assertEqual(contract['completion'], {'revision': 0,
            'criteria': f.plane.current_contract(f.state, f.spec)['criteria']})
        self.assertEqual(contract['contract_ref'], f.state['contract_ref'])
        self.assertEqual(contract['projection']['constraints']['autonomy'], f.spec['autonomy'])
        source = next(json.loads(e['content']) for e in entries if e['source'] == 'contract.py')
        self.assertEqual(source['content'], f.source.read_text())
        self.assertEqual(source['sha256'], digest(f.source.read_bytes()))
        self.assertEqual(contract['projection']['budget']['output_bytes'], len(encode(packet)))
        self.assertLessEqual(len(encode(packet)), 4096)
        self.assertLessEqual(len(entries), 4)
        for secret in ('SIBLING_SECRET', 'DESCENDANT_SECRET', 'FOREIGN_SECRET', 'POLICY_SECRET',
                       'UNRELATED_SECRET', 'host-operator', str(f.workspace), 'security_domains'):
            self.assertNotIn(secret, encode(result['result']).decode() + encode(packet).decode())
        self.assertTrue(any(e['source'].startswith('memory:') for e in entries))

    def test_one_fresh_replacement_delta_and_current_policy(self):
        f = self.f
        first = f.initial()
        f.source.write_text('def answer():\n    return "GOOD"\n')
        with self.assertRaisesRegex(ContextError, 'STALE'):
            f.plane.guard_worker(f.state, f.spec, first['admission'], first['admission']['packet_ref'], 'control/1')
        # Memory changes between operations are freshly queried too.
        f.memory.provider._records['current'] = 'stale DERIVED_TRAP'
        delta = f.plane.compile(f.state, f.spec, 'control/2',
            request=need(base_ref=first['admission']['packet_ref']), previous=first['admission'])
        packet = f.store.read_json('control', delta['admission']['packet_ref'])
        self.assertIn('GOOD', encode(packet).decode())
        self.assertNotIn('DRAFT', encode(packet).decode())
        self.assertNotIn('DERIVED_TRAP', encode(packet).decode())
        encoded_delta = f.store.read('control', delta['result']['payload']['output']['delta_ref'])
        self.assertLessEqual(len(encoded_delta), 4096)
        self.assertEqual(json.loads(encoded_delta)['payload']['output_bytes'], len(encoded_delta))
        self.assertEqual(json.loads(encoded_delta)['payload']['replaces'], 'all-context')
        with self.assertRaisesRegex(ContextError, 'DENIED'):
            f.plane.compile(f.state, f.spec, 'control/3', request=need(base_ref=delta['admission']['packet_ref']), previous=delta['admission'])
        f.snapshot['payload']['policy_domains'] = []
        f.state['iteration'] = 3
        with self.assertRaisesRegex(ContextError, 'STALE'):
            f.plane.guard_worker(f.state, f.spec, delta['admission'], delta['admission']['packet_ref'], 'control/3')

    def test_workspace_allowlist_symlinks_exact_and_lexical(self):
        f = self.f
        (f.workspace / 'secret').write_text('WORKSPACE_SECRET')
        for locator in ('secret', 'missing', '../secret', '/etc/passwd'):
            with self.subTest(locator=locator), self.assertRaisesRegex(ContextError, 'DENIED'):
                f.plane.compile(f.state, f.spec, 'control/init', request=need(locator=locator))
        resolved = f.plane.resolver.resolve(f.bound(), f.state, validate_need(need('lexical-source', None, exact='def answer():')))
        self.assertEqual(len(resolved['candidates']), 1)
        empty = f.plane.resolver.resolve(f.bound(), f.state, validate_need(need('lexical-source', None, exact='not-here')))
        self.assertEqual(empty['status'], 'EMPTY')
        with self.assertRaisesRegex(ContextError, 'INSUFFICIENT_CONTEXT'):
            f.plane.compile(f.state, f.spec, 'control/init', request=need(exact='MISSING_ASSERTION'))
        f.source.unlink()
        f.source.symlink_to(f.workspace / 'secret')
        with self.assertRaisesRegex(ContextError, 'UNAVAILABLE'):
            source_read(f.bound(), 'contract.py')

    def test_required_unavailable_evidence_and_oversize_do_not_dispatch(self):
        f = self.f
        ref = f.store.put('control', b'assert answer() == "GOOD"')
        f.state['artifacts']['proof'] = ref
        with self.assertRaisesRegex(ContextError, 'DENIED'):
            f.plane.compile(f.state, f.spec, 'control/init', request=need('current-evidence', ref))
        f.snapshot['payload']['evidence_refs'] = [ref]
        result = f.plane.compile(f.state, f.spec, 'control/init', request=need('current-evidence', ref))
        self.assertIn('assert answer()', f.store.read('control', result['admission']['packet_ref']).decode())
        (f.store.root / 'control' / ref.rsplit(':', 1)[1]).unlink()
        with self.assertRaisesRegex(ContextError, 'UNAVAILABLE'):
            f.plane.compile(f.state, f.spec, 'control/init', request=need('current-evidence', ref))
        for content in ('é' * 1800, 'x' * 17000):
            f.source.write_text(content)
            with self.assertRaisesRegex(ContextError, 'INSUFFICIENT_CONTEXT'):
                f.initial()

    def test_forged_packet_and_receipt_do_not_impersonate_compiler(self):
        f = self.f
        initial = f.initial()
        packet = message('WorkerInput', {'task_id': 'control', 'objective': 'Forged', 'context': []})
        forged = f.store.put_json('control', packet)
        calls = []
        caps = Capabilities(f.store, f.root / 'effects.sqlite', worker=lambda *args: calls.append(args), context_plane=f.plane)
        def request(ref):
            return message('CapabilityRequest', {'task_id': 'control', 'operation_id': 'control/1',
                'capability': 'worker.run', 'input': {'packet_ref': ref, 'artifact': 'answer'}})
        f.state['artifacts']['forged'] = forged
        raw = message('CognitiveDecision', {'task_id': 'control', 'task_revision': 0, 'turn_id': 'control/1',
            'next_action': {'type': 'INVOKE_CAPABILITY', 'capability': 'worker.run', 'input': request(forged)['payload']['input']}})
        self.assertEqual(policy_gate(raw, f.state, f.spec)['outcome'], 'allow')
        denied = caps.execute(request(forged), context_runtime=(f.state, f.spec, initial['admission']))
        self.assertEqual(denied['payload']['outcome'], 'failure')
        self.assertEqual(caps.execute(request(initial['admission']['packet_ref']))['payload']['outcome'], 'failure')
        raw['payload']['next_action']['input']['compiler_receipt'] = initial['admission']
        self.assertEqual(policy_gate(raw, f.state, f.spec)['outcome'], 'deny')
        self.assertEqual(calls, [])

    def test_deliberate_unsafe_controls_are_caught_by_actual_leak(self):
        f = self.f
        # Mutant trusting a caller scope actually returns forbidden bytes.
        unsafe_rows = f.memory.provider.read(['sibling'])
        self.assertIn('SIBLING_SECRET', encode(unsafe_rows).decode())
        self.assertNotIn('SIBLING_SECRET', encode(f.memory.retrieve(f.bound(), 'sibling')).decode())
        # Mutant trusting only artifact membership actually delivers forged input.
        forged = message('WorkerInput', {'task_id': 'control', 'objective': 'UNCOMPILED_SENTINEL', 'context': []})
        ref = f.store.put_json('control', forged)
        leaked = []
        worker = lambda p, o: leaked.append(p) or {'outcome': 'success', 'attempt_id': 'mutant', 'content': 'wrong'}
        caps = Capabilities(f.store, f.root / 'mutant.sqlite', worker=worker)  # deliberately unsafe for CP
        caps.execute(message('CapabilityRequest', {'task_id': 'control', 'operation_id': 'control/1',
            'capability': 'worker.run', 'input': {'packet_ref': ref, 'artifact': 'answer'}}))
        self.assertIn('UNCOMPILED_SENTINEL', encode(leaked).decode())

    def test_new_delta_resolves_narrowed_current_authority(self):
        f = self.f
        first = f.initial()
        f.snapshot['payload']['revision'] = '2'
        f.snapshot['payload']['policy_domains'] = []
        f.source.write_text('def answer():\n    return "GOOD"\n')
        current = f.plane.compile(f.state, f.spec, 'control/2',
            request=need(base_ref=first['admission']['packet_ref']), previous=first['admission'])
        self.assertNotEqual(first['admission']['binding'], current['admission']['binding'])
        packet = f.store.read('control', current['admission']['packet_ref']).decode()
        self.assertIn('GOOD', packet)
        self.assertNotIn('memory:', packet)
        self.assertNotIn('DRAFT', packet)
        self.assertEqual(current['result']['payload']['output']['memory'], 'EMPTY')

    def test_compiler_revalidates_candidates_before_selection(self):
        f = self.f
        bound = f.bound()
        request = validate_need(need())
        resolved = f.plane.resolver.resolve(bound, f.state, request, include_memory=True)
        f.memory.provider._records['current'] = 'corrupted PRIVATE_PROVIDER_ERROR'
        packet, selected, stats = f.plane.compiler.compile(bound, f.state, f.spec,
            request, resolved, 'control/context-initial', mode='initial', contract=f.plane.current_contract(f.state, f.spec))
        self.assertIn('def answer()', encode(packet).decode())
        self.assertNotIn('PRIVATE_PROVIDER_ERROR', encode(packet).decode())
        self.assertTrue(stats['partial'])
        f.source.write_text('changed')
        with self.assertRaisesRegex(ContextError, 'STALE'):
            f.plane.compiler.compile(bound, f.state, f.spec, request, resolved, 'control/context-initial', mode='initial', contract=f.plane.current_contract(f.state, f.spec))

    def test_exact_utf8_recipient_limits_and_no_criteria_trimming(self):
        f = self.f
        with self.assertRaisesRegex(ContextError, 'INSUFFICIENT_CONTEXT'):
            f.plane.compile(f.state, f.spec, 'control/context-initial', request=need(max_bytes=256))
        f.spec['completion'] = [{'criterion': 'é' * 240,
            'evidence': {'artifact': 'answer' + str(i), 'sha256': digest(b'GOOD')}} for i in range(8)]
        f.state['spec_ref'] = f.store.put_json('control', message('TaskSpec', f.spec))
        f.snapshot['payload']['spec_ref'] = f.state['spec_ref']
        f.accept_contract()
        with self.assertRaisesRegex(ContextError, 'INSUFFICIENT_CONTEXT'): f.initial()

    def test_changed_binding_during_compilation_refuses_admission(self):
        f = self.f
        original = f.plane.compiler.compile
        def changing(*args, **kwargs):
            result = original(*args, **kwargs)
            f.snapshot['payload']['revision'] = '2'
            return result
        with patch.object(f.plane.compiler, 'compile', changing):
            with self.assertRaisesRegex(ContextError, 'STALE'): f.initial()

    def test_policy_gate_requires_existing_capability_authority(self):
        f = self.f
        f.initial()
        action = {'type': 'INVOKE_CAPABILITY', 'capability': 'context.request',
                  'input': need(base_ref=f.state['artifacts']['compiled-context'])}
        raw = message('CognitiveDecision', {'task_id': 'control', 'task_revision': 0,
            'turn_id': 'control/1', 'next_action': action})
        self.assertEqual(policy_gate(raw, f.state, f.spec)['outcome'], 'allow')
        self.assertEqual(policy_gate(raw, f.state, f.spec, {'capabilities': ['worker.run']})['outcome'], 'deny')
        denied_spec = {**f.spec, 'autonomy': {'allowed': ['worker.run']}}
        self.assertEqual(policy_gate(raw, f.state, denied_spec)['outcome'], 'deny')
        for field in ('operation_class', 'authority_ref'):
            forged = deepcopy(raw)
            forged['payload']['next_action']['input']['payload'][field] = 'task.compute'
            self.assertEqual(policy_gate(forged, f.state, f.spec)['outcome'], 'deny')
            forged = deepcopy(raw)
            forged['payload']['next_action'][field] = 'task.compute'
            self.assertEqual(policy_gate(forged, f.state, f.spec)['outcome'], 'deny')
        self.assertEqual(journal.operation_class('context.request'), 'context.read')
        self.assertFalse(journal.mutating(['context.request']))

    def test_provider_exceptions_are_safe_and_do_not_hide_source(self):
        f = self.f
        with patch.object(f.memory.provider, 'read', side_effect=RuntimeError('PRIVATE_PROVIDER_ERROR')):
            result = f.initial()
        packet = f.store.read('control', result['admission']['packet_ref']).decode()
        self.assertIn('UNAVAILABLE', packet)
        self.assertIn('def answer()', packet)
        self.assertNotIn('PRIVATE_PROVIDER_ERROR', packet)


class Registry:
    def __init__(self, *args): self.handlers = {}
    def main(self, **kwargs):
        def accept(fn): self.run = fn; return fn
        return accept
    def handler(self, **kwargs):
        def accept(fn): self.handlers[fn.__name__] = fn; return fn
        return accept


class JournalContext:
    """Recorded run_typed observations; demonstrates replay, not Restate recovery."""
    def __init__(self, journal=None):
        self.saved = {}
        self.journal = {} if journal is None else deepcopy(journal)
        self.physical = []
    def promise(self, name, type_hint=None):
        async def peek(): return None
        return SimpleNamespace(peek=peek)
    def key(self): return 'control'
    def request(self): return SimpleNamespace(id='cp1-fixture-invocation')
    def set(self, key, value): self.saved[key] = deepcopy(value)
    async def run_typed(self, name, fn, *options, **kwargs):
        if name not in self.journal:
            self.physical.append(name)
            self.journal[name] = deepcopy(fn(**kwargs))
        return deepcopy(self.journal[name])


class WorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_authoritative_amendment_invalidates_packet_and_delta_reads_current_contract(self):
        from tests.completion_harness import Harness
        from tests.completion_fixtures import amendment, decision
        with tempfile.TemporaryDirectory() as directory:
            f = Fixture(Path(directory))
            packets, turns, amendments = [], [], []
            def worker(packet, operation):
                packets.append(deepcopy(packet))
                return {'outcome': 'success', 'attempt_id': 'fixture',
                        'content': 'DRAFT' if len(packets) == 1 else 'GOOD'}
            def cognitive(packet):
                turns.append(deepcopy(packet))
                turn = packet['payload']
                ref = next(c['source'] for c in turn['context'] if c['content'] == {'name': 'compiled-context'})
                if turn['iteration'] == 2:
                    return decision(packet, {'type': 'HANDOFF', 'specialist': 'specialist'})
                action = ({'type': 'INVOKE_CAPABILITY', 'capability': 'context.request',
                           'input': need(base_ref=ref)} if turn['iteration'] == 3 else
                          {'type': 'INVOKE_CAPABILITY', 'capability': 'worker.run',
                           'input': {'packet_ref': ref, 'artifact': 'answer' if turn['iteration'] == 1 else 'amended-answer'}})
                return decision(packet, action)
            async def checkpoint(ctx, stage, state):
                if stage == 'outcome' and state['iteration'] == 2:
                    amendments.append(await harness.call('control', 'amend_contract', amendment('control', [
                        {'op': 'rebind', 'id': 'c1', 'verifier': {'kind': 'artifact_digest', 'version': 1,
                         'artifact': 'amended-answer', 'sha256': digest(b'GOOD')}}])))
                if stage == 'amended':
                    initial = next(value for kind, name, value in ctx.runtime.journal
                                   if kind == 'run' and name == 'context-plane/initial')
                    admission = initial['admission']
                    with self.assertRaisesRegex(ContextError, 'STALE'):
                        f.plane.guard_worker(state, f.spec, admission, admission['packet_ref'],
                                             f"control/{state['iteration']}")
                    # The initial compiler API also projects current runtime state,
                    # independently of whether this invocation requests a delta.
                    fresh = f.plane.compile(state, f.spec, 'control/current-initial')
                    self.assertEqual(fresh['admission']['contract_revision'], 1)
            caps = Capabilities(f.store, f.root / 'effects.sqlite', worker=worker, context_plane=f.plane)
            harness = Harness(f.store, cognitive, caps, checkpoint=checkpoint)
            result = await harness.invoke('control', message('TaskSpec', f.spec))
            self.assertEqual(result['payload']['outcome'], 'COMPLETED')
            self.assertEqual(amendments[0]['payload']['outcome'], 'SUBMITTED')
            self.assertEqual(len(packets), 2)
            self.assertEqual([p['payload']['contract']['revision'] for p in turns], [0, 0, 1, 1])
            projections = [json.loads(p['payload']['context'][0]['content']) for p in packets]
            self.assertEqual([p['completion']['revision'] for p in projections], [0, 1])
            self.assertEqual([p['completion']['criteria'][0]['verifier']['artifact'] for p in projections],
                             ['answer', 'amended-answer'])
            state = harness.state('control')
            self.assertEqual(projections[1]['contract_ref'], state['contract_ref'])
            self.assertNotEqual(projections[0]['contract_ref'], state['contract_ref'])
            for packet in packets:
                self.assertLessEqual(len(encode(packet)), 4096)
            entries = journal.read(f.store, 'control', state['journal_head'], state['journal_length'])
            admitted = [e for _, e in entries if e['phase'] == 'admitted']
            self.assertEqual([(e['capability'], e['operation_class'], e['contract_revision']) for e in admitted],
                             [('worker.run', 'worker.run', 0), ('context.request', 'context.read', 1),
                              ('worker.run', 'worker.run', 1)])
            self.assertEqual(len([e for _, e in entries if e['phase'] == 'observed']), 3)
            evaluation = f.store.read_json('control', state['completion_ref'])
            self.assertEqual(evaluation['version'], 2)
            self.assertEqual(evaluation['payload']['contract_revision'], 1)
            self.assertEqual(evaluation['payload']['outcome'], 'satisfied')
            self.assertTrue(evaluation['payload']['legality']['legal'])
            self.assertEqual(journal.effect_scope('context.read'), journal.TARGET_READ)
            # E1.0's ordered journal replays amendment peeks and applications.
            self.assertEqual(await harness.invoke('control'), result)
            self.assertEqual(len(packets), 2)

    async def test_early_and_second_delta_and_duplicate_dispatch_are_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Fixture(Path(directory))
            observed, delivered = [], []
            def worker(packet, operation):
                delivered.append(packet)
                return {'outcome': 'success', 'attempt_id': 'fixture', 'content': 'wrong'}
            def cognitive(packet):
                turn = packet['payload']
                index = turn['iteration']
                ref = next(c['source'] for c in turn['context'] if c['content'] == {'name': 'compiled-context'})
                if index in (1, 4, 5):
                    action = {'type': 'INVOKE_CAPABILITY', 'capability': 'context.request', 'input': need(base_ref=ref)}
                elif index in (2, 3):
                    action = {'type': 'INVOKE_CAPABILITY', 'capability': 'worker.run', 'input': {'packet_ref': ref, 'artifact': 'answer'}}
                else:
                    raise workflow.restate.TerminalError('Fixture complete')
                return message('CognitiveDecision', {k: turn[k] for k in ('task_id', 'task_revision', 'turn_id')} | {'next_action': action})
            async def checkpoint(ctx, stage, state):
                if stage == 'effect_persisted':
                    observed.append(f.store.read_json('control', state['observation_ref'])['payload'])
            caps = Capabilities(f.store, f.root / 'effects.sqlite', worker=worker, context_plane=f.plane)
            with patch.object(workflow.restate, 'Workflow', Registry):
                service = workflow.create_workflow(f.store, cognitive, caps, checkpoint=checkpoint)
            result = await service.run(JournalContext(), message('TaskSpec', f.spec))
            self.assertEqual(result['payload']['outcome'], 'FAILED')
            self.assertEqual([o['outcome'] for o in observed], ['failure', 'success', 'failure', 'success', 'failure'])
            self.assertEqual(len(delivered), 1)
            self.assertEqual(f.store.read_json('control', result['payload']['completion_ref'])['payload']['outcome'], 'unsatisfied')

    async def test_physical_cognition_rechecks_authority_after_reconstruction(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Fixture(Path(directory))
            calls = []
            caps = Capabilities(f.store, f.root / 'effects.sqlite', worker=lambda *args: None, context_plane=f.plane)
            async def checkpoint(ctx, stage, state):
                if stage == 'before_cognition': f.snapshot = None
            with patch.object(workflow.restate, 'Workflow', Registry):
                service = workflow.create_workflow(f.store, lambda p: calls.append(p), caps, checkpoint=checkpoint)
            result = await service.run(JournalContext(), message('TaskSpec', f.spec))
            self.assertEqual(result['payload']['outcome'], 'FAILED')
            self.assertEqual(calls, [])

    async def test_new_admitted_delta_can_use_changed_binding_after_decision(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Fixture(Path(directory))
            seen = []
            def worker(packet, operation):
                seen.append(packet)
                return {'outcome': 'success', 'attempt_id': 'fixture', 'content': 'DRAFT' if len(seen) == 1 else 'GOOD'}
            def cognitive(packet):
                turn = packet['payload']
                ref = next(c['source'] for c in turn['context'] if c['content'] == {'name': 'compiled-context'})
                action = ({'type': 'INVOKE_CAPABILITY', 'capability': 'context.request', 'input': need(base_ref=ref)}
                    if turn['iteration'] == 2 else {'type': 'INVOKE_CAPABILITY', 'capability': 'worker.run', 'input': {'packet_ref': ref, 'artifact': 'answer'}})
                return message('CognitiveDecision', {k: turn[k] for k in ('task_id', 'task_revision', 'turn_id')} | {'next_action': action})
            async def checkpoint(ctx, stage, state):
                if stage == 'decision' and state['iteration'] == 2:
                    f.snapshot['payload']['revision'] = '2'
                    f.snapshot['payload']['policy_domains'] = []
                    f.source.write_text('def answer():\n    return "GOOD"\n')
            caps = Capabilities(f.store, f.root / 'effects.sqlite', worker=worker, context_plane=f.plane)
            with patch.object(workflow.restate, 'Workflow', Registry):
                service = workflow.create_workflow(f.store, cognitive, caps, checkpoint=checkpoint)
            result = await service.run(JournalContext(), message('TaskSpec', f.spec))
            self.assertEqual(result['payload']['outcome'], 'COMPLETED')
            self.assertNotIn('memory:', encode(seen[1]).decode())
            self.assertNotIn('DRAFT', encode(seen[1]).decode())

    async def test_initial_worker_fresh_delta_exact_completion_and_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            f = Fixture(Path(directory))
            worker_packets, turns = [], []
            def worker(packet, operation):
                worker_packets.append(deepcopy(packet))
                content = 'DRAFT' if len(worker_packets) == 1 else 'GOOD'
                return {'outcome': 'success', 'attempt_id': 'recording-' + str(len(worker_packets)), 'content': content}
            def cognitive(packet):
                turns.append(deepcopy(packet))
                turn = packet['payload']
                ref = next(c['source'] for c in turn['context'] if c['content'] == {'name': 'compiled-context'})
                action = ({'type': 'INVOKE_CAPABILITY', 'capability': 'context.request', 'input': need(base_ref=ref)}
                          if len(turns) == 2 else {'type': 'INVOKE_CAPABILITY', 'capability': 'worker.run',
                                                    'input': {'packet_ref': ref, 'artifact': 'answer'}})
                return message('CognitiveDecision', {k: turn[k] for k in ('task_id', 'task_revision', 'turn_id')} | {'next_action': action})
            async def checkpoint(ctx, stage, state):
                if stage == 'effect_persisted' and state['iteration'] == 1:
                    f.source.write_text('def answer():\n    return "GOOD"\n')
                    self.assertEqual(state['lifecycle'], 'RUNNING')
            caps = Capabilities(f.store, f.root / 'effects.sqlite', worker=worker, context_plane=f.plane)
            with patch.object(workflow.restate, 'Workflow', Registry):
                service = workflow.create_workflow(f.store, cognitive, caps, checkpoint=checkpoint)
            ctx = JournalContext()
            result = await service.run(ctx, message('TaskSpec', f.spec))
            self.assertEqual(result['payload']['outcome'], 'COMPLETED')
            self.assertEqual(len(worker_packets), 2)
            self.assertIn('DRAFT', encode(worker_packets[0]).decode())
            self.assertIn('GOOD', encode(worker_packets[1]).decode())
            self.assertNotIn('DRAFT', encode(worker_packets[1]).decode())
            self.assertEqual(f.store.read_json('control', result['payload']['completion_ref'])['payload']['outcome'], 'satisfied')
            for packet in worker_packets: self.assertLessEqual(len(encode(packet)), 4096)
            for packet in turns: self.assertLessEqual(len(encode(packet)), 16384)
            for name, value in ctx.journal.items():
                if name.startswith('capability/'):
                    self.assertLessEqual(len(encode(value['result'])), 4096)
            # Private admission/snapshot never appear in ordinary Task status.
            self.assertNotIn('security_domains', encode(ctx.saved).decode())
            self.assertNotIn('snapshot_ref', encode(ctx.saved).decode())
            # Full replay with revoked authority consumes historical observations.
            f.snapshot = None
            replay = JournalContext(ctx.journal)
            self.assertEqual(await service.run(replay, message('TaskSpec', f.spec)), result)
            self.assertEqual(replay.physical, [])
            self.assertEqual(len(worker_packets), 2)
            self.assertEqual(len(turns), 3)
            # Partial replay before physical delivery must consult CURRENT authority.
            partial = {}
            for name, value in ctx.journal.items():
                if name == 'capability/3':
                    break
                partial[name] = value
            denied_ctx = JournalContext(partial)
            # Stop after the denied effect to keep this assertion focused on delivery.
            async def stop(ctx, stage, state):
                if stage == 'effect_persisted' and state['iteration'] == 3:
                    raise workflow.restate.TerminalError('Fixture stopped after delivery denial')
            with patch.object(workflow.restate, 'Workflow', Registry):
                denied_service = workflow.create_workflow(f.store, cognitive, caps, checkpoint=stop)
            denied = await denied_service.run(denied_ctx, message('TaskSpec', f.spec))
            self.assertEqual(denied['payload']['outcome'], 'FAILED')
            self.assertEqual(denied_ctx.journal['capability/3']['result']['payload']['outcome'], 'failure')
            self.assertEqual(len(worker_packets), 2)


if __name__ == '__main__': unittest.main()
