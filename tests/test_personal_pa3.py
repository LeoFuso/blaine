"""PA-3 Personal Agent services: conversation, Execution Brief, staged delivery."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from runtime.kernel import completion
from runtime.kernel.journal import mutating
from runtime.kernel.contracts import accept_task_request, encode, message, validate_decision
from runtime.kernel.conversation import ConversationService
from runtime.kernel.execution import policy_gate
from runtime.kernel.human import request_digest
from runtime.kernel.routing import effective_capabilities
from runtime.kernel.worker import goose_reply, strip_outer_fence, validate_packet
from runtime.personal_agent import human_response, task_identity
from runtime.personal_brief import BriefService, CodingPolicy
from runtime.personal_conversation import ConversationModel, PersonalConversation, short_id
from runtime.personal_delivery import ResultDelivery, ResultInterpreter

CID = 'thread-01'


def deployment(root):
    return {
        'cognition': {'endpoint': 'http://127.0.0.1:8000/v1', 'model': 'local-test'},
        'coding_workspaces': {'blaine-pa3-target': {
            'root': str(root), 'description': 'test worktree', 'allowed_paths': ['tests/'],
            'inspect_paths': ['runtime/'], 'targeted_profile': 'targeted-tests',
            'canonical_profiles': ['canonical-suite'], 'ask_before': ['workspace.write']}},
        'exec_profiles': {
            'targeted-tests': {'executable': '/usr/bin/python3', 'args': ['-m', 'unittest'],
                               'allowed_args': ['tests/test_human_response_bounds.py']},
            'canonical-suite': {'executable': '/usr/bin/python3', 'args': ['-m', 'verification.cli', 'run',
                                'completion-contract', '--worktree', '.']}},
    }


class ScriptedModel(ConversationModel):
    def __init__(self, replies):
        self.replies, self.calls, self.model = list(replies), [], 'local-test'

    def complete(self, messages, max_tokens=700, temperature=0.3):
        self.calls.append(messages)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class FakeAgent:
    """Stands in for the Restate-backed control surface; records every call."""
    def __init__(self):
        self.calls, self.views, self.created, self.fail_create = [], {}, {}, None

    def execute(self, request):
        self.calls.append(request)
        op = request['operation']
        if op == 'create':
            if self.fail_create:
                error, self.fail_create = self.fail_create, None
                raise error
            task_id = task_identity(request['request_id'])
            existing = task_id in self.created
            self.created[task_id] = request['task_request']
            self.views.setdefault(task_id, {'task_id': task_id, 'lifecycle': 'RUNNING'})
            return {'task_id': task_id, 'submission': 'EXISTING' if existing else 'SUBMITTED'}
        if op == 'inspect':
            return self.views.get(request['task_id'], {'task_id': request['task_id'], 'lifecycle': 'UNAVAILABLE'})
        if op == 'artifact':
            return {'content': 'import unittest\n'}
        raise AssertionError(op)


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        os.environ['BLAINE_CONVERSATION_KEY_DIR'] = str(self.base / 'keys')
        self.addCleanup(os.environ.pop, 'BLAINE_CONVERSATION_KEY_DIR', None)
        self.store = ConversationService(self.base / 'data')
        self.policy = CodingPolicy(deployment(self.base / 'repo'))
        self.agent = FakeAgent()

    def discuss(self):
        self.store.create_conversation(CID)
        self.store.add_message(CID, 'human', 'Add bounded tests for human.validate_response', message_id='m1')
        self.store.add_message(CID, 'agent', 'Agreed: new file tests/test_human_response_bounds.py', message_id='m2')


BRIEF = json.dumps({'workspace_id': 'blaine-pa3-target',
                    'objective': 'Add unittest cases proving validate_response rejects stale revisions and values '
                                 'outside the allowed set.',
                    'constraints': ['Standard library unittest only'],
                    'deliverable_path': 'tests/test_human_response_bounds.py',
                    'inspect_paths': ['runtime/kernel/human.py'],
                    'targeted_tests': ['tests/test_human_response_bounds.py']})


class ConversationTests(Base):
    def test_converse_persists_both_turns_and_is_idempotent_per_message(self):
        model = ScriptedModel(['Happy to help.'])
        service = PersonalConversation(self.store, model)
        first = service.converse(CID, 'm1', 'Hello Blaine')
        again = service.converse(CID, 'm1', 'Hello Blaine')
        self.assertEqual(first['reply']['content'], 'Happy to help.')
        self.assertEqual(again['reply']['id'], first['reply']['id'])
        self.assertEqual(len(model.calls), 1)
        self.assertEqual([m['role'] for m in self.store.list_messages(CID)], ['human', 'agent'])
        self.assertEqual(self.agent.calls, [])  # a conversation turn creates no Task

    def test_model_failure_keeps_the_human_turn_and_a_retry_answers_it(self):
        model = ScriptedModel([OSError('model down'), 'Now I can answer.'])
        service = PersonalConversation(self.store, model)
        with self.assertRaises(OSError):
            service.converse(CID, 'm1', 'Hello')
        self.assertEqual([m['role'] for m in self.store.list_messages(CID)], ['human'])
        self.assertEqual(service.converse(CID, 'm1', 'Hello')['reply']['content'], 'Now I can answer.')

    def test_delegations_enter_history_as_system_facts_and_task_state_is_visible(self):
        self.discuss()
        self.store.begin_delegation(CID, 'task-' + 'e' * 64, 'dlg-x', '{"objective": "tests"}', 'brf-x')
        self.agent.views['task-' + 'e' * 64] = {'lifecycle': 'WAITING', 'pending_human_decision': {'payload': {
            'question': 'Approve workspace.write tests/t.py?'}}, 'effects': [
            {'operation_class': 'workspace.exec', 'profile': 'targeted', 'status': 'completed', 'exit_code': 1}]}
        model = ScriptedModel(['It is waiting for your approval.'])
        PersonalConversation(self.store, model, self.agent).converse(CID, 'm3', 'Is the task running?')
        sent = model.calls[0]
        self.assertIn('lifecycle WAITING', sent[1]['content'])
        self.assertIn('approval card', sent[1]['content'])
        self.assertIn('run targeted: completed exit 1', sent[1]['content'])
        delegations = [t for t in sent if 'Blaine created this durable Task' in t['content']]
        self.assertEqual([t['role'] for t in delegations], ['user'])  # a fact, never the assistant's words

    def test_message_cursor(self):
        self.discuss()
        messages = self.store.list_messages(CID)
        self.assertEqual([m['id'] for m in self.store.list_messages(CID, after=messages[0]['seq'])], ['m2'])


class BriefTests(Base):
    def service(self, replies=(BRIEF,)):
        return BriefService(self.store, ScriptedModel(replies), self.agent, self.policy)

    def test_proposal_is_validated_encrypted_and_requests_only_policy_authority(self):
        self.discuss()
        brief = self.service().propose(CID)
        body = brief['payload']['payload']
        self.assertEqual(brief['status'], 'proposed')
        self.assertEqual(body['deliverable'], {'workspace_id': 'blaine-pa3-target',
                                               'path': 'tests/test_human_response_bounds.py'})
        self.assertEqual(body['requested']['profiles'], ['targeted-tests', 'canonical-suite'])
        self.assertEqual(body['requested']['ask_before'], ['workspace.write'])
        raw = (self.base / 'data' / 'conversation.sqlite').read_bytes()
        self.assertNotIn(b'validate_response rejects stale', raw)
        self.assertEqual(self.agent.calls, [])  # proposing is not executing

    def test_model_cannot_widen_the_brief(self):
        self.discuss()
        for bad in ({**json.loads(BRIEF), 'capabilities': ['shell']},
                    {**json.loads(BRIEF), 'deliverable_path': 'runtime/kernel/human.py'},
                    {**json.loads(BRIEF), 'targeted_tests': ['tests/test_everything.py']},
                    {**json.loads(BRIEF), 'inspect_paths': ['../../etc/passwd']},
                    {**json.loads(BRIEF), 'workspace_id': 'other'}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.service([json.dumps(bad)]).propose(CID)

    def test_confirm_submits_one_canonical_task_request_with_write_ahead_provenance(self):
        self.discuss()
        service = self.service()
        brief = service.propose(CID)
        confirmed = service.confirm(CID, brief['brief_id'])
        task_id = confirmed['task_id']
        link = self.store.link(CID, task_id)
        self.assertEqual((link['state'], link['brief_id']), ('linked', brief['brief_id']))
        self.assertEqual(self.store.get_brief(CID, brief['brief_id'])['status'], 'confirmed')
        # The kernel accepts it exactly as intake would.
        raw = self.agent.created[task_id]
        spec, parent, grant = accept_task_request(raw, task_id)
        self.assertIsNone(parent)
        self.assertEqual(grant['workspaces'], ['blaine-pa3-target'])
        self.assertEqual(grant['ask_before'], ['workspace.write'])
        admissible = effective_capabilities(spec, grant)
        contract = completion.accept_contract(spec, None, completion.envelope_contract(raw), task_id,
                                              mutating(admissible))
        self.assertEqual([c['id'] for c in contract['criteria']],
                         ['c1', 'no-unauthorized-effect', 'change-made', 'tests-pass', 'canonical-1'])
        self.assertLessEqual(len(encode(raw)), 16384)
        # The deterministic first action publishes the confirmed WorkerInput; c1 pins it.
        action = raw['payload']['initial_action']
        validate_decision(message('CognitiveDecision', {'task_id': task_id, 'task_revision': 0,
                                                        'turn_id': task_id + '/1', 'next_action': action}))
        packet = json.loads(action['input']['content'])
        validate_packet(packet, task_id)
        self.assertEqual(packet['payload']['output'], {'kind': 'file', 'path': 'tests/test_human_response_bounds.py'})
        self.assertEqual(contract['criteria'][0]['verifier']['sha256'],
                         __import__('hashlib').sha256(action['input']['content'].encode()).hexdigest())
        # Repeating the confirmation is the same Task, not a second one.
        self.assertEqual(service.confirm(CID, brief['brief_id'])['task_id'], task_id)
        self.assertEqual(len(self.agent.created), 1)

    def test_submission_lost_after_write_ahead_is_reconciled_without_a_second_task(self):
        self.discuss()
        service = self.service()
        brief = service.propose(CID)
        self.agent.fail_create = OSError('submission uncertain')
        with self.assertRaises(OSError):
            service.confirm(CID, brief['brief_id'])
        [link] = self.store.open_delegations()
        self.assertEqual(link['state'], 'submitting')
        ResultDelivery(self.store, self.agent, ResultInterpreter(None), service).tick()
        self.assertEqual(self.store.link(CID, link['task_id'])['state'], 'linked')
        self.assertEqual(list(self.agent.created), [link['task_id']])

    def test_one_running_task_per_workspace(self):
        self.discuss()
        service = self.service([BRIEF, BRIEF])
        first = service.confirm(CID, service.propose(CID)['brief_id'])
        self.store.add_message(CID, 'human', 'Execute it again', message_id='m9')
        second = service.propose(CID)
        with self.assertRaisesRegex(ValueError, 'busy'):
            service.confirm(CID, second['brief_id'])
        self.assertEqual(list(self.agent.created), [first['task_id']])
        # Retrying the same brief is the same Task, not a second writer.
        self.assertEqual(service.confirm(CID, self.store.link(CID, first['task_id'])['brief_id'])['task_id'],
                         first['task_id'])
        self.agent.views[first['task_id']] = {'lifecycle': 'COMPLETED'}
        self.assertNotEqual(service.confirm(CID, second['brief_id'])['task_id'], first['task_id'])

    def test_rejected_brief_cannot_execute(self):
        self.discuss()
        service = self.service()
        brief = service.propose(CID)
        service.reject(CID, brief['brief_id'])
        with self.assertRaises(ValueError):
            service.confirm(CID, brief['brief_id'])
        self.assertEqual(self.agent.created, {})


class DeliveryTests(Base):
    def delegate(self):
        self.discuss()
        service = BriefService(self.store, ScriptedModel([BRIEF]), self.agent, self.policy)
        return service.confirm(CID, service.propose(CID)['brief_id'])['task_id']

    def complete(self, task_id):
        self.agent.views[task_id] = {
            'task_id': task_id, 'lifecycle': 'COMPLETED', 'revision': 9, 'contract_revision': 0,
            'artifacts': {'draft': 'artifact://x/sha256:' + '1' * 64},
            'completion': {'payload': {'outcome': 'satisfied', 'legality': {'legal': True},
                                       'criteria': [{'id': 'tests-pass', 'status': 'satisfied', 'detail': 'exit 0'}]}},
            'result': {'payload': {'outcome': 'COMPLETED', 'concerns': []}},
            'effects': [{'operation_class': 'workspace.write', 'status': 'applied', 'path': 'tests/t.py',
                         'before': {'absent': True}, 'after': {'sha256': '2' * 64}},
                        {'operation_class': 'workspace.exec', 'status': 'completed', 'profile': 'targeted-tests',
                         'args': ['-m', 'unittest', 'tests/t.py'], 'exit_code': 0, 'result': {}}]}

    def test_nothing_is_delivered_while_the_task_runs(self):
        task_id = self.delegate()
        delivery = ResultDelivery(self.store, self.agent, ResultInterpreter(ScriptedModel([])))
        self.assertEqual(delivery.tick(), 0)
        self.assertEqual(self.store.link(CID, task_id)['state'], 'linked')

    def test_terminal_task_is_delivered_once_with_facts_then_a_grounded_follow_up(self):
        task_id = self.delegate()
        self.complete(task_id)
        model = ScriptedModel(['Done: tests/t.py was added and its tests passed.'])
        delivery = ResultDelivery(self.store, self.agent, ResultInterpreter(model))
        self.assertEqual(delivery.tick(), 1)
        self.assertEqual(delivery.tick(), 0)
        roles = [m['role'] for m in self.store.list_messages(CID)]
        self.assertEqual(roles[-2:], ['result', 'agent'])
        self.assertEqual(roles.count('result'), 1)
        result = json.loads(self.store.get_message(CID, short_id('res', CID, task_id))['content'])
        self.assertEqual(result['facts']['verifier_outcome'], 'satisfied')
        self.assertEqual(result['facts']['diff']['path'], 'tests/t.py')
        self.assertIn('+import unittest', result['facts']['diff']['unified'])
        self.assertEqual(self.store.link(CID, task_id)['state'], 'surfaced')
        # The interpreter saw only the verified facts.
        self.assertIn('"verifier_outcome": "satisfied"', model.calls[0][1]['content'])

    def test_crash_between_stages_resumes_without_duplicates(self):
        task_id = self.delegate()
        self.complete(task_id)

        class Dies(ResultInterpreter):
            def interpret(self, facts):
                raise SystemExit('bridge died during inference')
        with self.assertRaises(SystemExit):
            ResultDelivery(self.store, self.agent, Dies(None)).tick()
        self.assertEqual(self.store.link(CID, task_id)['state'], 'result_recorded')
        restarted = ConversationService(self.base / 'data')
        ResultDelivery(restarted, self.agent, ResultInterpreter(ScriptedModel(['Recovered summary.']))).tick()
        roles = [m['role'] for m in restarted.list_messages(CID)]
        self.assertEqual((roles.count('result'), roles[-1]), (1, 'agent'))
        self.assertEqual(restarted.link(CID, task_id)['state'], 'surfaced')

    def test_model_failure_falls_back_to_marked_deterministic_text(self):
        task_id = self.delegate()
        self.complete(task_id)
        ResultDelivery(self.store, self.agent, ResultInterpreter(ScriptedModel([ValueError('bad')]))).tick()
        followup = self.store.get_message(CID, short_id('fup', CID, task_id))['content']
        self.assertIn('deterministic summary', followup)
        self.assertIn('COMPLETED', followup)


class HumanResponseTests(unittest.TestCase):
    def state(self):
        request = message('HumanDecisionRequest', {'task_id': 'task-a', 'origin_task_id': 'task-a',
            'request_id': 'approve-4', 'revision': 0, 'question': 'Approve workspace.write?',
            'allowed_responses': ['APPROVE', 'DENY']})
        return {'pending_human_decision': request}, request

    def test_envelope_answers_exactly_the_pending_request(self):
        state, request = self.state()
        envelope = human_response(state, 'task-a', 'APPROVE', 'approve-4')['payload']
        self.assertEqual((envelope['request_id'], envelope['request_revision'], envelope['value']),
                         ('approve-4', 0, 'APPROVE'))
        self.assertEqual(envelope['request_digest'], request_digest(request))
        self.assertEqual(envelope['response_id'], human_response(state, 'task-a', 'APPROVE')['payload']['response_id'])

    def test_stale_or_invalid_answers_are_refused(self):
        state, _ = self.state()
        for args in (('APPROVE', 'approve-3'), ('MAYBE', None)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                human_response(state, 'task-a', *args)
        with self.assertRaises(ValueError):
            human_response({'pending_human_decision': None}, 'task-a', 'APPROVE')


class WorkerCodingTests(unittest.TestCase):
    def packet(self, **extra):
        return message('WorkerInput', {'task_id': 'task', 'objective': 'Write the file', 'context': [], **extra})

    def test_file_output_form_is_confined(self):
        validate_packet(self.packet(output={'kind': 'file', 'path': 'tests/test_x.py'}), 'task')
        for output in ({'kind': 'file', 'path': '../x.py'}, {'kind': 'shell', 'path': 'x'}, {'kind': 'file'}):
            with self.subTest(output=output), self.assertRaises(ValueError):
                validate_packet(self.packet(output=output), 'task')

    def test_file_replies_come_verbatim_from_the_json_transcript(self):
        body = 'x = 1\n' * 80  # long enough that Goose's text renderer would shorten it
        transcript = {'messages': [{'role': 'user', 'content': [{'type': 'text', 'text': 'go'}]},
                                   {'role': 'assistant', 'content': [{'type': 'text', 'text': body}]}],
                      'metadata': {'status': 'completed'}}
        self.assertEqual(goose_reply(json.dumps(transcript).encode()), body)
        for bad in ({**transcript, 'metadata': {'status': 'failed'}},
                    {**transcript, 'messages': transcript['messages'][:1]},
                    {**transcript, 'messages': [{'role': 'assistant', 'content': [{'type': 'toolRequest'}]}]}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                goose_reply(json.dumps(bad).encode())

    def test_outer_fence_is_removed_once(self):
        self.assertEqual(strip_outer_fence('```python\nx = 1\n```\n'), 'x = 1\n')
        self.assertEqual(strip_outer_fence('x = 1\n'), 'x = 1\n')

    def test_worker_context_must_be_admitted_artifacts(self):
        state = {'task_id': 'task', 'revision': 0, 'iteration': 2, 'lifecycle': 'RUNNING',
                 'artifacts': {'worker-input': 'artifact://task/sha256:' + 'a' * 64,
                               'source-1': 'artifact://task/sha256:' + 'b' * 64}}
        spec = {'objective': 'x', 'completion': [], 'capabilities': ['worker.run'],
                'autonomy': {'allowed': ['worker.run']}}

        def decide(refs):
            action = {'type': 'INVOKE_CAPABILITY', 'capability': 'worker.run',
                      'input': {'packet_ref': state['artifacts']['worker-input'], 'artifact': 'draft',
                                'context_refs': refs}}
            return policy_gate(message('CognitiveDecision', {'task_id': 'task', 'task_revision': 0,
                                                             'turn_id': 'task/2', 'next_action': action}), state, spec)
        self.assertEqual(decide([state['artifacts']['source-1']])['outcome'], 'allow')
        self.assertEqual(decide(['artifact://task/sha256:' + 'c' * 64])['outcome'], 'deny')


if __name__ == '__main__':
    unittest.main()
