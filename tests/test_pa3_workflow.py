"""PA-3 end to end through the real workflow: a confirmed Execution Brief becomes one
durable Task whose Worker proposal is written by the local worktree provider after
human approval, qualified by real processes, and completed only by the verifier.

Cognition and the Worker are scripted (no model); the provider, the files, the
processes, PolicyGate, the approval boundary and the CompletionVerifier are real.
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from runtime.kernel import journal
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.conversation import ConversationService
from runtime.personal_agent import human_response, task_identity
from runtime.personal_brief import BriefService, CodingPolicy
from runtime.personal_delivery import render, result_facts
from runtime.personal_runtime import target_effects

import completion_fixtures as fx
from completion_harness import Harness
from test_completion_workflow import Audited, Base, Cognition

WS = 'wsp-pa3'
DELIVERABLE = 'tests/test_greeting.py'
SOURCE = 'def greet(name):\n    return f"Hello, {name}!"\n'
TEST_FILE = ('import unittest\nfrom pkg.greeting import greet\n\n\nclass Greeting(unittest.TestCase):\n'
             '    def test_greets_by_name(self):\n        self.assertEqual(greet("Ada"), "Hello, Ada!")\n\n\n'
             'if __name__ == "__main__":\n    unittest.main()\n')
BRIEF = {'workspace_id': WS, 'objective': 'Add a unittest for pkg.greeting.greet.', 'constraints': ['stdlib only'],
         'deliverable_path': DELIVERABLE, 'inspect_paths': ['pkg/greeting.py'], 'targeted_tests': [DELIVERABLE]}


class SlowPolls:
    """Harness sleeps are instantaneous; give real processes wall-clock time to finish."""
    def __init__(self, provider):
        self.provider, self.provider_id = provider, provider.provider_id

    def __getattr__(self, name):
        return getattr(self.provider, name)

    def query(self, operation_id, request_digest):
        found = self.provider.query(operation_id, request_digest)
        if found.get('found') and found['receipt']['payload']['state'] == 'running':
            time.sleep(0.05)
        return found


class ScriptedWorker:
    def __init__(self):
        self.calls = []

    def __call__(self, packet, operation_id, attachments=()):
        self.calls.append((packet, list(attachments)))
        return {'attempt_id': 'worker-test', 'operation_id': operation_id, 'outcome': 'success', 'exit_code': 0,
                'content': TEST_FILE, 'public_stdout': TEST_FILE, 'stderr_bytes': 0}


class PA3Workflow(Base):
    def setUp(self):
        super().setUp()
        self.repo = self.root / 'repo'
        (self.repo / 'pkg').mkdir(parents=True)
        (self.repo / 'tests').mkdir()
        (self.repo / 'pkg' / '__init__.py').write_text('')
        (self.repo / 'pkg' / 'greeting.py').write_text(SOURCE)
        self.deployment = {
            'coding_workspaces': {WS: {'root': str(self.repo), 'allowed_paths': ['tests/'], 'inspect_paths': ['pkg/'],
                                       'targeted_profile': 'targeted-tests', 'canonical_profiles': ['canonical-suite'],
                                       'ask_before': ['workspace.write']}},
            'exec_profiles': {
                'targeted-tests': {'executable': sys.executable, 'args': ['-m', 'unittest'],
                                   'allowed_args': [DELIVERABLE], 'timeout_seconds': 60, 'poll_seconds': 0.1},
                'canonical-suite': {'executable': sys.executable, 'args': ['-c', 'print("result: PASS")'],
                                    'timeout_seconds': 60, 'poll_seconds': 0.1}}}
        keys = tempfile.TemporaryDirectory()
        self.addCleanup(keys.cleanup)
        os.environ['BLAINE_CONVERSATION_KEY_DIR'] = keys.name
        self.addCleanup(os.environ.pop, 'BLAINE_CONVERSATION_KEY_DIR', None)

    def request(self):
        task_id = task_identity('pa3-e2e')
        briefs = BriefService(ConversationService(self.root / 'conv'), None, None, CodingPolicy(self.deployment))
        from runtime.personal_brief import validate_brief
        return task_id, briefs.task_request(task_id, validate_brief(BRIEF, briefs.policy))

    async def test_confirmed_brief_runs_to_verified_completion(self):
        task_id, request = self.request()
        provider, profiles = target_effects(self.root, self.deployment)
        worker = ScriptedWorker()
        script = {
            2: lambda t: {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.read',
                          'input': {'form': 'file', 'workspace_id': WS, 'path': 'pkg/greeting.py', 'artifact': 'source-1'}},
            3: lambda t: {'type': 'INVOKE_CAPABILITY', 'capability': 'worker.run',
                          'input': {'packet_ref': ref(t, 'worker-input'), 'artifact': 'draft',
                                    'context_refs': [ref(t, 'source-1')]}},
            4: lambda t: {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.write',
                          'input': {'workspace_id': WS, 'path': DELIVERABLE, 'precondition': {'absent': True},
                                    'content_ref': ref(t, 'draft')}},
            5: lambda t: {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.exec',
                          'input': {'workspace_id': WS, 'profile': 'targeted-tests', 'args': [DELIVERABLE]}},
            6: lambda t: {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.exec',
                          'input': {'workspace_id': WS, 'profile': 'canonical-suite'}},
        }
        holder = []
        cognition = Cognition(script)
        capabilities = Audited(self.store, self.root / 'fixture.sqlite', holder)
        capabilities.worker = worker
        harness = Harness(self.store, cognition, capabilities, target_provider=SlowPolls(provider),
                          exec_profiles=profiles)
        holder.append(harness)

        # The write waits for the human, through the existing approval boundary.
        self.assertIsNone(await harness.invoke(task_id, request))
        view = await harness.call(task_id, 'inspect')
        self.assertEqual(view['lifecycle'], 'WAITING')
        self.assertFalse((self.repo / DELIVERABLE).exists())
        self.assertIn('workspace.write', view['pending_human_decision']['payload']['question'])
        await harness.call(task_id, 'submit_human_response', human_response(view, task_id, 'APPROVE'))
        result = await harness.invoke(task_id)

        self.assertEqual(result['payload']['outcome'], 'COMPLETED')
        self.assertEqual((self.repo / DELIVERABLE).read_text(), TEST_FILE)
        evaluation = self.store.read_json(task_id, result['payload']['completion_ref'])['payload']
        self.assertEqual({c['id']: c['status'] for c in evaluation['criteria']},
                         dict.fromkeys(['c1', 'no-unauthorized-effect', 'change-made', 'tests-pass', 'canonical-1'],
                                       'satisfied'))
        self.assertTrue(evaluation['legality']['legal'])
        self.assertEqual(cognition.calls, [2, 3, 4, 5, 6])  # turn 1 was the deterministic brief admission
        packet, attachments = worker.calls[0]
        self.assertEqual(packet['payload']['output'], {'kind': 'file', 'path': DELIVERABLE})
        self.assertEqual([a['content'] for a in attachments], [SOURCE])  # only admitted artifacts

        entries = [e for _, e in journal.read(self.store, task_id, harness.state(task_id)['journal_head'],
                                              harness.state(task_id)['journal_length'])]
        admitted = [e.get('operation_class') for e in entries if e['phase'] == 'admitted']
        self.assertEqual(admitted, ['task.artifact.write', 'workspace.read', 'worker.run', 'workspace.write',
                                    'workspace.exec', 'workspace.exec'])
        self.assertEqual(len([e for e in entries if e['phase'] == 'dispatched']), 3)  # write + two execs

        view = await harness.call(task_id, 'inspect')
        by_class = {(e['operation_class'], e.get('profile')): e for e in view['effects']}
        write = by_class[('workspace.write', None)]
        self.assertEqual((write['status'], write['path'], write['before']), ('applied', DELIVERABLE, {'absent': True}))
        tests = by_class[('workspace.exec', 'targeted-tests')]
        self.assertEqual((tests['status'], tests['exit_code']), ('completed', 0))
        self.assertEqual(by_class[('workspace.exec', 'canonical-suite')]['result'], {'verification': 'PASS'})

        facts = result_facts({**view, 'completion': {'payload': evaluation}}, TEST_FILE)
        self.assertEqual(facts['verifier_outcome'], 'satisfied')
        self.assertEqual([c['path'] for c in facts['changed_files']], [DELIVERABLE])
        self.assertIn('+from pkg.greeting import greet', facts['diff']['unified'])
        self.assertIn('COMPLETED', render(facts))

    async def test_denied_write_never_touches_the_workspace(self):
        task_id, request = self.request()
        provider, profiles = target_effects(self.root, self.deployment)
        script = {
            2: lambda t: {'type': 'INVOKE_CAPABILITY', 'capability': 'worker.run',
                          'input': {'packet_ref': ref(t, 'worker-input'), 'artifact': 'draft'}},
            3: lambda t: {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.write',
                          'input': {'workspace_id': WS, 'path': DELIVERABLE, 'precondition': {'absent': True},
                                    'content_ref': ref(t, 'draft')}},
            4: lambda t: {'type': 'WAIT', 'wait_id': 'hold', 'input_type': 'text'},
        }
        holder = []
        capabilities = Audited(self.store, self.root / 'fixture.sqlite', holder)
        capabilities.worker = ScriptedWorker()
        harness = Harness(self.store, Cognition(script), capabilities, target_provider=SlowPolls(provider),
                          exec_profiles=profiles)
        holder.append(harness)
        self.assertIsNone(await harness.invoke(task_id, request))
        view = await harness.call(task_id, 'inspect')
        await harness.call(task_id, 'submit_human_response', human_response(view, task_id, 'DENY'))
        self.assertIsNone(await harness.invoke(task_id))
        self.assertFalse((self.repo / DELIVERABLE).exists())
        effect = next(iter(harness.state(task_id)['effects'].values()))
        self.assertEqual(effect['status'], 'not_dispatched')

    async def test_write_outside_the_granted_workspace_is_denied_before_dispatch(self):
        task_id, request = self.request()
        provider, profiles = target_effects(self.root, self.deployment)
        script = {
            2: lambda t: {'type': 'INVOKE_CAPABILITY', 'capability': 'worker.run',
                          'input': {'packet_ref': ref(t, 'worker-input'), 'artifact': 'draft'}},
            3: lambda t: {'type': 'INVOKE_CAPABILITY', 'capability': 'workspace.exec',
                          'input': {'workspace_id': WS, 'profile': 'targeted-tests', 'args': ['tests/other.py']}},
            4: lambda t: {'type': 'WAIT', 'wait_id': 'hold', 'input_type': 'text'},
        }
        holder = []
        capabilities = Audited(self.store, self.root / 'fixture.sqlite', holder)
        capabilities.worker = ScriptedWorker()
        harness = Harness(self.store, Cognition(script), capabilities, target_provider=SlowPolls(provider),
                          exec_profiles=profiles)
        holder.append(harness)
        self.assertIsNone(await harness.invoke(task_id, request))
        state = harness.state(task_id)
        denied = [e for _, e in journal.read(self.store, task_id, state['journal_head'], state['journal_length'])
                  if e['phase'] == 'denied']
        self.assertEqual([e['operation_class'] for e in denied], ['workspace.exec'])


def ref(turn, name):
    return fx_ref(turn, name)


def fx_ref(turn, name):
    return next(item['source'] for item in turn['context']
                if item['authority'] == 'artifact' and item['content'].get('name') == name)
