"""UI-2.6 tests: the bridge's read-only Task event projection.

The /task/<id>/events endpoint tails the deployment's retained ExecutionEvent
log (events.jsonl) and projects closed NORMAL metadata only. The bridge owns
no Task state, no lifecycle and no event log of its own: this module exercises
the pure projection helper against a real log shape, not a live server.
"""
import json
import os
import unittest

from runtime.personal_http import read_task_events


def fake_log(tmp_path):
    events = [
        {'schema_version': 1, 'event_id': 'e1', 'event_type': 'task.started',
         'task_id': 'task-a', 'sensitivity': 'NORMAL', 'step_id': 'start',
         'outcome': 'RUNNING', 'payload': {'iteration': 0},
         'producer': {'component': 'blaine.kernel.workflow'},
         'occurred_at': '2026-09-23T18:13:59.000000+00:00'},
        {'schema_version': 1, 'event_id': 'e2', 'event_type': 'cognition.decided',
         'task_id': 'task-b', 'sensitivity': 'NORMAL', 'step_id': 'cognition/1',
         'outcome': 'recorded', 'payload': {'iteration': 1},
         'producer': {'component': 'blaine.kernel.workflow'},
         'occurred_at': '2026-09-23T18:14:01.000000+00:00'},
        {'schema_version': 1, 'event_id': 'e3', 'event_type': 'capability.finished',
         'task_id': 'task-a', 'sensitivity': 'NORMAL', 'step_id': 'capability/1',
         'outcome': 'success', 'payload': {'iteration': 1},
         'producer': {'component': 'blaine.kernel.execution'},
         'occurred_at': '2026-09-23T18:14:02.000000+00:00'},
        {'schema_version': 1, 'event_id': 'e4', 'event_type': 'artifact.produced',
         'task_id': 'task-a', 'sensitivity': 'NORMAL', 'step_id': 'artifacts/1',
         'outcome': 'recorded', 'payload': {'iteration': 1},
         'producer': {'component': 'blaine.kernel.artifacts.ArtifactStore'},
         'occurred_at': '2026-09-23T18:14:02.500000+00:00'},
        {'schema_version': 1, 'event_id': 'e5', 'event_type': 'verifier.evaluated',
         'task_id': 'task-a', 'sensitivity': 'NORMAL', 'step_id': 'verification/effect/1',
         'outcome': 'satisfied', 'payload': {'iteration': 1},
         'producer': {'component': 'blaine.kernel.execution.evaluate'},
         'occurred_at': '2026-09-23T18:14:03.000000+00:00'},
        {'schema_version': 1, 'event_id': 'e6', 'event_type': 'completion.finished',
         'task_id': 'task-a', 'sensitivity': 'NORMAL', 'step_id': 'completion',
         'outcome': 'COMPLETED', 'payload': {'iteration': 1},
         'producer': {'component': 'blaine.kernel.workflow'},
         'occurred_at': '2026-09-23T18:14:03.500000+00:00'},
    ]
    path = os.path.join(tmp_path, 'events.jsonl')
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write('\n'.join(json.dumps(e) for e in events) + '\n')
    return path


class TaskEventProjection(unittest.TestCase):
    def setUp(self):
        import tempfile
        import runtime.personal_http as bridge
        self.tmp = tempfile.TemporaryDirectory()
        self._orig = bridge.EVENTS_FILE
        bridge.EVENTS_FILE = str(fake_log(self.tmp.name))

    def tearDown(self):
        import runtime.personal_http as bridge
        bridge.EVENTS_FILE = self._orig
        self.tmp.cleanup()

    def test_projects_only_the_requested_task_in_order(self):
        result = read_task_events('task-a', 0)
        types = [e['event_type'] for e in result['events']]
        self.assertEqual(types, ['task.started', 'capability.finished',
                                 'artifact.produced', 'verifier.evaluated',
                                 'completion.finished'])
        # task-b's cognition event must not leak into task-a's projection
        self.assertNotIn('cognition.decided', types)

    def test_cursor_is_a_monotonic_line_position(self):
        full = read_task_events('task-a', 0)
        self.assertEqual(full['next'], 6)
        tail = read_task_events('task-a', 4)
        self.assertEqual([e['event_type'] for e in tail['events']],
                         ['verifier.evaluated', 'completion.finished'])
        # Sequences keep advancing, so a client never re-reads a line.
        self.assertEqual([e['seq'] for e in tail['events']], [5, 6])
        # A cursor past the end yields an empty, stable projection.
        self.assertEqual(read_task_events('task-a', 6)['events'], [])

    def test_iteration_is_carried_from_the_authoritative_payload(self):
        result = read_task_events('task-a', 0)
        iterations = [e['iteration'] for e in result['events']]
        self.assertEqual(iterations, [0, 1, 1, 1, 1])

    def test_only_closed_metadata_is_projected(self):
        for event in read_task_events('task-a', 0)['events']:
            self.assertEqual(set(event), {'seq', 'event_type', 'step_id',
                                          'outcome', 'iteration', 'occurred_at',
                                          'producer'})
            self.assertNotIn('payload', event)
            self.assertNotIn('payload_refs', event)

    def test_unknown_task_is_an_empty_projection_not_an_error(self):
        result = read_task_events('task-nope', 0)
        self.assertEqual(result['events'], [])
        self.assertEqual(result['next'], 6)

    def test_invalid_cursor_and_identity_rejected(self):
        for bad in (-1, 1.5, 'x'):
            with self.assertRaises(ValueError):
                read_task_events('task-a', bad)
        with self.assertRaises(ValueError):
            read_task_events('not a task id', 0)


if __name__ == '__main__':
    unittest.main()
