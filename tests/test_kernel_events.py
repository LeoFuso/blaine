"""ExecutionEvent contract, sink replay and authority regression controls."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

from runtime.kernel import workflow
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.cognition import ScriptedCognition
from runtime.kernel.contracts import message
from runtime.kernel.event_sinks import JsonlEventPublisher
from runtime.kernel.events import make_event, validate_event, safe_publish
from runtime.kernel.execution import Capabilities
from test_kernel_progression import Registry, Context


def sample(**changes):
    event = make_event(task_id='test', run_id='run:invocation', step_id='start',
        event_type='task.started', outcome='RUNNING', producer={'kind':'deterministic_application','component':'test'})
    event.update(changes)
    return event


class EventContractTests(unittest.TestCase):
    def test_closed_version_and_fields(self):
        validate_event(sample())
        for changes in ({'schema_version':2},{'schema_version':True},{'extra':'value'},
                        {'event_type':'made.up'}, {'outcome':'whatever'}, {'occurred_at':'yesterday'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_event(sample(**changes))

    def test_no_unrestricted_payloads_or_secret_class(self):
        for changes in ({'sensitivity':'SECRET'}, {'payload':{'raw':'SECRET_FIXTURE_DO_NOT_EMIT'}},
                        {'payload':{'capability':'SECRET_FIXTURE_DO_NOT_EMIT'}},
                        {'payload_refs':[{'ref':'artifact://test/sha256:'+'a'*64,'sensitivity':'SECRET'}]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate_event(sample(**changes))

    def test_trace_is_optional_and_independent(self):
        self.assertNotIn('trace_id',sample())
        event=sample(trace_id='a'*32,span_id='b'*16)
        validate_event(event)
        for changes in ({'run_id':'a'*32},{'trace_id':'0'*32},{'span_id':'bad'}):
            with self.assertRaises(ValueError):validate_event(event|changes)

    def test_provenance_and_reference_validation(self):
        for changes in ({'producer':{}},{'producer':{'kind':'test','component':'test','raw':{}}},
                        {'payload_refs':[{'ref':'artifact://other/sha256:'+'a'*64,'sensitivity':'SENSITIVE'}]}):
            with self.assertRaises(ValueError):validate_event(sample(**changes))

    def test_sink_exact_one_record_and_restart_dedup(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'events.jsonl';event=sample()
            JsonlEventPublisher(path).publish(event)
            JsonlEventPublisher(path).publish(deepcopy(event))
            lines=path.read_text().splitlines()
            self.assertEqual(len(lines),1);self.assertEqual(validate_event(json.loads(lines[0])),event)
            with self.assertRaises(ValueError):JsonlEventPublisher(path).publish(event|{'task_id':'other'})

    def test_bad_event_not_emitted(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'events.jsonl'
            self.assertEqual(safe_publish(JsonlEventPublisher(path),sample(payload={'raw':'SECRET_FIXTURE_DO_NOT_EMIT'})),'publication_failed')
            self.assertFalse(path.exists())


class EventWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def run_task(self, publisher, contents=('DRAFT','GOOD'), denied=False):
        with tempfile.TemporaryDirectory() as d:
            store=ArtifactStore(Path(d)/'artifacts');caps=Capabilities(store,Path(d)/'effects.sqlite')
            actions=[{'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'answer','content':value}} for value in contents]
            if denied:actions.insert(0,{'type':'INVOKE_CAPABILITY','capability':'fixture.effect','input':{'value':'SECRET_FIXTURE_DO_NOT_EMIT'}})
            spec=message('TaskSpec',{'objective':'Produce GOOD','completion':[{'criterion':'Exact','evidence':{'artifact':'answer','sha256':hashlib.sha256(b'GOOD').hexdigest()}}],
                'capabilities':['artifact.write'],'autonomy':{'allowed':['artifact.write']}})
            ctx=Context();ctx.request=lambda:SimpleNamespace(id='invocation')
            with patch.object(workflow.restate,'Workflow',Registry):
                service=workflow.create_workflow(store,ScriptedCognition(actions),caps,event_publisher=publisher)
            result=await service.run(ctx,spec)
            self.assertEqual(result['payload']['outcome'],'COMPLETED')
            return result

    async def test_sequence_causality_and_independent_verification(self):
        events=[]
        class Publisher:
            def publish(self,event):events.append(deepcopy(event))
        await self.run_task(Publisher())
        self.assertTrue(all(validate_event(e) for e in events))
        self.assertEqual({e['task_id'] for e in events},{'control'})
        self.assertEqual({e['run_id'] for e in events},{'run:invocation'})
        self.assertEqual(events[0]['event_type'],'task.started')
        self.assertEqual(events[-1]['event_type'],'completion.finished')
        for prior,current in zip(events,events[1:]):self.assertEqual(current['causation_event_id'],prior['event_id'])
        verifiers=[e['outcome'] for e in events if e['event_type']=='verifier.evaluated']
        self.assertEqual(verifiers,['unsatisfied','unsatisfied','unsatisfied','satisfied'])
        self.assertEqual(len([e for e in events if e['event_type']=='capability.finished']),2)
        self.assertTrue(all('content' not in e['payload'] for e in events))
        self.assertTrue(any(e['payload_refs'] for e in events))

    async def test_publisher_failure_has_no_authority(self):
        class Broken:
            def publish(self,event):raise OSError('SECRET_FIXTURE_DO_NOT_EMIT')
        normal=await self.run_task(None)
        failed=await self.run_task(Broken())
        self.assertEqual(normal,failed)

    async def test_policy_denial_has_no_effect_event(self):
        events=[]
        class Publisher:
            def publish(self,event):events.append(deepcopy(event))
        await self.run_task(Publisher(),contents=('GOOD',),denied=True)
        self.assertEqual([e['outcome'] for e in events if e['event_type']=='policy.evaluated'],['deny','allow'])
        self.assertEqual(len([e for e in events if e['event_type']=='capability.finished']),1)
        self.assertNotIn('SECRET_FIXTURE_DO_NOT_EMIT',json.dumps(events))
