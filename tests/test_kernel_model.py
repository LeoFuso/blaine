import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.context import reconstruct
from runtime.kernel.contracts import message, MAX_PACKET
from runtime.kernel.model import LocalModelCognition, decision_schema
from test_kernel import spec, state, decision


class ModelBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.packet = reconstruct(state(), spec(), ArtifactStore(Path(self.temp.name)))

    def response(self, content, **extra):
        return {'choices': [{'finish_reason': 'stop', 'message': {'content': content, **extra}}], 'usage': {'prompt_tokens': 100}}

    def test_only_validated_decision_and_bounded_packet_cross_boundary(self):
        raw = decision({'type': 'COMPLETE'})
        transport, audit = Mock(return_value=self.response(json.dumps(raw))), Mock()
        adapter = LocalModelCognition(transport=transport, audit=audit)
        self.assertEqual(adapter(self.packet), raw)
        request = transport.call_args.args[0]
        self.assertEqual(json.loads(request['messages'][1]['content']), self.packet)
        self.assertNotIn('tools', request)
        self.assertNotIn('response_format', request)
        self.assertNotIn('structured_outputs', request)
        self.assertNotIn('extra_body', request)
        guidance = json.loads(request['messages'][0]['content'].split('emit an instance, not the schema):\n')[1])
        self.assertIn('version', guidance['required'])
        self.assertEqual(guidance['properties']['version'], {'const': 1})
        self.assertNotIn('reasoning', audit.call_args.args[0])
        self.assertEqual(audit.call_args.args[0]['usage']['prompt_tokens'], 100)

    def test_raw_invoke_is_preserved_without_complete_fallback(self):
        raw = decision({'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write',
                        'input': {'name': 'answer', 'content': 'verified'}})
        response = self.response(json.dumps(raw))
        self.assertEqual(LocalModelCognition(transport=lambda _: response)(self.packet), raw)
        for invalid in ({k:v for k,v in raw.items() if k != 'version'},
                        {k:v for k,v in raw.items() if k != 'kind'},
                        {**raw, 'version': '1'}, {**raw, 'version': True},
                        {**raw, 'version': 2}, {**raw, 'extra': 'not admitted'},
                        decision({'type': 'UNSUPPORTED'})):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                LocalModelCognition(transport=lambda _: self.response(json.dumps(invalid)))(self.packet)

    def test_malformed_unknown_stale_and_native_tools_never_return_decisions(self):
        stale = decision({'type': 'COMPLETE'}); stale['payload']['task_revision'] = 99
        responses = [self.response('not json'), self.response(json.dumps(decision({'type': 'DELETE_ALL'}))),
                     self.response(json.dumps(stale)), self.response(json.dumps(decision({'type': 'COMPLETE'})), tool_calls=[{}]),
                     self.response('{"version":1,"version":2}'), self.response('x' * (MAX_PACKET+1))]
        for response in responses:
            with self.subTest(response=response), self.assertRaises(ValueError):
                LocalModelCognition(transport=lambda _: response)(self.packet)

    def test_input_budget_and_local_endpoint_enforced(self):
        with self.assertRaises(ValueError):
            LocalModelCognition(endpoint='https://external.example/v1')
        transport = Mock()
        bad = message('CognitiveTurn', {'content': 'x' * MAX_PACKET})
        with self.assertRaises(ValueError):
            LocalModelCognition(transport=transport)(bad)
        transport.assert_not_called()

    def test_schema_keeps_five_actions(self):
        schema = decision_schema(self.packet['payload'])
        actions = schema['properties']['payload']['properties']['next_action']['anyOf']
        self.assertEqual({x['properties']['type']['const'] for x in actions},
                         {'INVOKE_CAPABILITY','HANDOFF','SPAWN_TASK','WAIT','COMPLETE'})
