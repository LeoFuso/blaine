"""Conversation projection v1: entries, phases, human requests, cursor and replay."""
import json
import unittest

from runtime.kernel.conversation import ConversationService
from runtime.personal_brief import BriefService
from runtime.personal_delivery import ResultDelivery, ResultInterpreter
from runtime.personal_projection import ConversationProjection

from test_personal_pa3 import BRIEF, CID, Base, ScriptedModel

APPROVAL = {'version': 1, 'kind': 'HumanDecisionRequest', 'payload': {
    'task_id': 'x', 'origin_task_id': 'x', 'request_id': 'approve-4', 'revision': 0,
    'question': 'Approve workspace.write tests/test_human_response_bounds.py?', 'allowed_responses': ['APPROVE', 'DENY']}}


class ProjectionTests(Base):
    def setUp(self):
        super().setUp()
        self.discuss()
        self.briefs = BriefService(self.store, ScriptedModel([BRIEF]), self.agent, self.policy)
        self.projection = ConversationProjection(self.store, self.agent)

    def by_kind(self, entries, kind):
        return [e for e in entries if e['kind'] == kind]

    def test_a_proposed_brief_is_an_entry_after_the_turns_it_was_compiled_from(self):
        brief = self.briefs.propose(CID)
        entries = self.projection.read(CID)['entries']
        self.assertEqual([(e['kind'], e['entry_id']) for e in entries],
                         [('message', 'm1'), ('message', 'm2'), ('brief', brief['brief_id'])])
        self.assertEqual(entries[2]['status'], 'proposed')
        self.assertEqual(entries[2]['deliverable']['path'], 'tests/test_human_response_bounds.py')

    def test_task_phase_steps_and_a_pending_human_request_come_only_from_backend_facts(self):
        task_id = self.briefs.confirm(CID, self.briefs.propose(CID)['brief_id'])['task_id']
        self.agent.views[task_id] = {'task_id': task_id, 'lifecycle': 'WAITING', 'revision': 3,
            'pending_human_decision': {**APPROVAL, 'payload': {**APPROVAL['payload'], 'task_id': task_id}},
            'effects': [{'operation_id': f'{task_id}/4', 'operation_class': 'workspace.write',
                         'status': 'awaiting_approval', 'path': 'tests/test_human_response_bounds.py'}]}
        entries = self.projection.read(CID)['entries']
        [task] = self.by_kind(entries, 'task')
        self.assertEqual((task['phase'], task['delivery']), ('waiting_human', 'pending'))
        self.assertEqual([s['label'] for s in task['steps']],
                         ['Execution Brief admitted', 'Approval requested: write tests/test_human_response_bounds.py'])
        [request] = self.by_kind(entries, 'human_request')
        self.assertEqual((request['status'], request['options'], request['request_id']),
                         ('pending', ['APPROVE', 'DENY'], 'approve-4'))
        kinds = [e['kind'] for e in entries]
        self.assertEqual(kinds.index('human_request'), kinds.index('task') + 1)
        # Once the Task stops waiting, the request keeps its identity and is resolved.
        self.agent.views[task_id] = {'task_id': task_id, 'lifecycle': 'RUNNING', 'revision': 5, 'effects': [
            {'operation_id': f'{task_id}/4', 'operation_class': 'workspace.write', 'status': 'applied',
             'path': 'tests/test_human_response_bounds.py'},
            {'operation_id': f'{task_id}/5', 'operation_class': 'workspace.exec', 'status': 'completed',
             'profile': 'targeted-tests', 'exit_code': 1, 'result': {'failed': 1}}]}
        after = self.projection.read(CID)['entries']
        [request] = self.by_kind(after, 'human_request')
        self.assertEqual(request['status'], 'resolved')
        [task] = self.by_kind(after, 'task')
        self.assertEqual(task['phase'], 'running')
        self.assertEqual(task['steps'][-1], {'key': 'effect:5', 'label': 'targeted-tests failed',
                                             'status': 'failed', 'detail': 'exit 1, 1 failed'})

    def test_cursor_is_idempotent_and_only_changed_entries_are_reemitted(self):
        first = self.projection.read(CID)
        self.assertEqual(len(first['entries']), 2)
        again = self.projection.read(CID, first['cursor'])
        self.assertEqual((again['entries'], again['cursor']), ([], first['cursor']))
        # A second reader (another process) sees the same seqs; nothing is bumped twice.
        other = ConversationProjection(ConversationService(self.base / 'data'), self.agent)
        self.assertEqual(other.read(CID, first['cursor'])['entries'], [])
        self.store.add_message(CID, 'human', 'next', message_id='m5')
        delta = self.projection.read(CID, first['cursor'])
        self.assertEqual([e['entry_id'] for e in delta['entries']], ['m5'])
        self.assertGreater(delta['cursor'], first['cursor'])
        # Replay from 0 returns the full current state, latest bodies only.
        self.assertEqual([e['entry_id'] for e in self.projection.read(CID)['entries']], ['m1', 'm2', 'm5'])

    def test_result_and_followup_entries_complete_the_task_story(self):
        task_id = self.briefs.confirm(CID, self.briefs.propose(CID)['brief_id'])['task_id']
        self.agent.views[task_id] = {'task_id': task_id, 'lifecycle': 'COMPLETED', 'revision': 9,
            'artifacts': {}, 'effects': [],
            'completion': {'payload': {'outcome': 'satisfied', 'legality': {'legal': True},
                                       'criteria': [{'id': 'c1', 'status': 'satisfied'},
                                                    {'id': 'tests-pass', 'status': 'satisfied'}]}},
            'result': {'payload': {'outcome': 'COMPLETED', 'concerns': []}}}
        cursor = self.projection.read(CID)['cursor']
        ResultDelivery(self.store, self.agent, ResultInterpreter(ScriptedModel(['All green.']))).tick()
        delta = self.projection.read(CID, cursor)['entries']
        kinds = {e['kind']: e for e in delta}
        self.assertEqual(kinds['task']['delivery'], 'surfaced')
        self.assertEqual(kinds['task']['criteria'], {'satisfied': 2, 'total': 2, 'items': [
            {'id': 'c1', 'status': 'satisfied'}, {'id': 'tests-pass', 'status': 'satisfied'}]})
        self.assertEqual((kinds['result']['task_id'], kinds['result']['verifier']), (task_id, 'satisfied'))
        self.assertEqual((kinds['followup']['task_id'], kinds['followup']['text']), (task_id, 'All green.'))
        order = [e['kind'] for e in self.projection.read(CID)['entries']]
        self.assertEqual(order[-3:], ['task', 'result', 'followup'])

    def test_unreachable_control_surface_is_reported_not_invented(self):
        task_id = self.briefs.confirm(CID, self.briefs.propose(CID)['brief_id'])['task_id']
        del self.agent.views[task_id]
        [task] = self.by_kind(self.projection.read(CID)['entries'], 'task')
        self.assertEqual(task['phase'], 'unavailable')

    def test_projection_holds_no_plaintext(self):
        self.projection.read(CID)
        raw = (self.base / 'data' / 'conversation.sqlite').read_bytes()
        self.assertNotIn(b'Add bounded tests for human.validate_response', raw)

    def test_unknown_conversation_is_empty(self):
        self.assertEqual(self.projection.read('nope', 3), {'conversation_id': 'nope', 'cursor': 3, 'entries': []})


if __name__ == '__main__':
    unittest.main()
