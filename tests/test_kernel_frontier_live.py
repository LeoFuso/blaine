"""Offline controls for the one-shot live binding. Never invokes Codex."""
import importlib.util,json,subprocess,sys,tempfile,unittest
import hashlib
from contextlib import closing
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('live_binding_tests',ROOT/'experiments/kernel-increment-11/live/binding.py')
binding=importlib.util.module_from_spec(spec);spec.loader.exec_module(binding)
fixture_spec=importlib.util.spec_from_file_location('corrected_codex_fixtures',ROOT/'experiments/kernel-increment-11/offline-event-diagnostic/diagnose.py')
fixtures=importlib.util.module_from_spec(fixture_spec);fixture_spec.loader.exec_module(fixtures)

class LiveBoundaryTests(unittest.TestCase):
    def test_normalization_is_only_closed_json_serialization(self):
        self.assertEqual(binding.normalize('{"organization":"FLOWER", "marker":"MASKED_01"}'),'{"marker":"MASKED_01","organization":"FLOWER"}')
        for raw in ('{"organization":"FLOWER"}','{"organization":"FLOWER","marker":"MASKED_01","extra":1}',
                    '{"organization":"FLOWER","marker":"a","marker":"b"}','not json'):
            with self.assertRaises((ValueError,TypeError)):binding.normalize(raw)

    def test_claim_is_exclusive_persistent_and_never_reset(self):
        with tempfile.TemporaryDirectory() as d:
            receipt=Path(d)/'attempt.json';r=SimpleNamespace(worker_dispatch_id='dispatch:fixture/2',context_digest='a'*64)
            binding.claim_dispatch(receipt,r)
            with self.assertRaises(FileExistsError):binding.claim_dispatch(receipt,r)
            self.assertEqual(json.loads(receipt.read_text())['worker_dispatch_id'],r.worker_dispatch_id)

    def test_blaine_owns_process_group_termination(self):
        p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],start_new_session=True)
        try:binding.stop_process(p);self.assertIsNotNone(p.poll())
        finally:
            if p.poll() is None:p.kill();p.wait()

    def test_command_pins_worker_model_and_empty_workspace(self):
        command=binding.command()
        self.assertIn('--ephemeral',command);self.assertIn('gpt-6-astra',command)
        self.assertIn('/probe',command);self.assertIn('--die-with-parent',command)
        self.assertIn('read-only',command);self.assertNotIn(str(ROOT),command)
        self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',command)

    def test_corrected_adapter_case_matrix_no_cli_execution(self):
        success={'clean_completed_shape','unknown_item_error_before_result',
                 'unknown_item_error_after_result','unsupported_nonterminal_claim'}
        for name in fixtures.CASES:
            with self.subTest(name=name):
                result=fixtures.exercise(name)
                self.assertEqual(result['adapter_outcome'],'executed' if name in success else 'rejected')
                self.assertEqual(result['normalized_result_written'],name in success)
                self.assertFalse(result['synthetic_private_detail_retained'])
                self.assertIsNotNone(result['retained_observation'])
                self.assertEqual(result['live_worker_dispatches'],0)

    def test_sensitive_error_values_and_unknown_fields_never_retained(self):
        marker='SYNTHETIC_CREDENTIAL_AND_UNPROJECTED_CONTEXT'
        error={'type':'item.completed','item':{'id':marker,'type':'error',
            'message':'Authorization: Bearer '+marker,'extra':{'secret':marker}}}
        stream=b'\n'.join(json.dumps(v).encode() for v in (fixtures.START,error,fixtures.MESSAGE,fixtures.COMPLETED))
        observed,content=binding.observe_stream(stream,exit_code=0)
        self.assertEqual(observed['normalized_outcome'],'success')
        self.assertNotIn(marker,json.dumps(observed))
        diagnostic=observed['diagnostics'][0]
        self.assertIsNone(diagnostic['item_id'])
        self.assertEqual(diagnostic['message']['retention'],'structure_only')
        self.assertNotIn('Authorization',json.dumps(observed))
        self.assertEqual(diagnostic['classification_source'],binding.PROTOCOL)

    def test_strict_event_shape_bounds_and_terminal_consistency(self):
        bad_streams=[b'[]',b'{"type":"turn.completed","type":"turn.failed"}',b'\xff',
            b'\n'.join([b'{}']*129),b'x'*262145,
            json.dumps({'type':'item.completed','item':None}).encode()]
        for stream in bad_streams:
            observed,content=binding.observe_stream(stream,exit_code=0)
            self.assertNotEqual(observed['normalized_outcome'],'success');self.assertIsNone(content)
        for events in ((fixtures.START,fixtures.MESSAGE,fixtures.COMPLETED,fixtures.COMPLETED),
                       (fixtures.START,fixtures.MESSAGE,fixtures.COMPLETED,fixtures.FAILED),
                       (fixtures.START,fixtures.MESSAGE,fixtures.COMPLETED,fixtures.TOP_ERROR),
                       (fixtures.START,fixtures.FAILED,fixtures.MESSAGE,fixtures.COMPLETED)):
            observed,content=binding.observe_stream(b'\n'.join(json.dumps(v).encode() for v in events),exit_code=0)
            self.assertEqual(observed['terminal_status'],'conflicting');self.assertIsNone(content)

    def test_valid_terminal_does_not_repair_invalid_result(self):
        for value in ('not JSON','{"organization":"FLOWER"}',
                      '{"organization":"FLOWER","marker":"a","marker":"b"}'):
            msg={'type':'item.completed','item':{'type':'agent_message','text':value}}
            observed,content=binding.observe_stream(b'\n'.join(json.dumps(v).encode() for v in
                (fixtures.START,msg,fixtures.COMPLETED)),exit_code=0)
            self.assertIsNone(content);self.assertIn('invalid_result_contract',observed['rejection_reasons'])
            self.assertNotIn(value,json.dumps(observed))

    def test_worker_protocol_success_still_requires_independent_evidence(self):
        from runtime.kernel.artifacts import ArtifactStore
        from runtime.kernel.contracts import message
        from runtime.kernel.execution import Capabilities,evaluate
        stream=b'\n'.join(json.dumps(v).encode() for v in (fixtures.START,fixtures.MESSAGE,fixtures.COMPLETED))
        observed,content=binding.observe_stream(stream,exit_code=0)
        self.assertEqual(observed['normalized_outcome'],'success')
        with tempfile.TemporaryDirectory() as d:
            store=ArtifactStore(Path(d)/'artifacts');state={'task_id':'task','artifacts':{}}
            spec={'completion':[{'criterion':'Exact result','evidence':{'artifact':'answer','sha256':hashlib.sha256(content.encode()).hexdigest()}}]}
            self.assertNotEqual(evaluate(spec,state,store)['payload']['outcome'],'satisfied')
            packet=store.put_json('task',message('WorkerInput',{'task_id':'task','objective':'Synthetic echo','context':[]}))
            # Close the existing constructor's fixture DB without changing kernel code.
            import sqlite3
            connect=sqlite3.connect
            with patch('runtime.kernel.execution.sqlite3.connect',side_effect=lambda *a,**k:closing(connect(*a,**k))):
                caps=Capabilities(store,Path(d)/'fixture.sqlite',worker=lambda p,o:{'outcome':'success','attempt_id':'synthetic','content':content})
            result=caps.execute(message('CapabilityRequest',{'task_id':'task','operation_id':'task/1',
                'capability':'worker.run','input':{'packet_ref':packet,'artifact':'answer'}}))
            state['artifacts']=result['payload']['artifacts']
            self.assertEqual(evaluate(spec,state,store)['payload']['outcome'],'satisfied')
            spec['completion'][0]['evidence']['sha256']=hashlib.sha256(b'different required content').hexdigest()
            self.assertEqual(evaluate(spec,state,store)['payload']['outcome'],'unsatisfied')

    def test_existing_failure_and_unknown_settlement_semantics_unchanged(self):
        from test_kernel_frontier import fixture
        from runtime.kernel.frontier import authorize,DispatchBudget,reserve,invoke,settle
        authority,proposal,kw=fixture();_,request=authorize(proposal,authority,DispatchBudget(),**kw)
        budget=reserve(DispatchBudget(),request)
        class FailedBinding:
            def dispatch(self,request):raise RuntimeError('Known worker failure, not proof of non-execution')
        result=invoke(request,FailedBinding(),guardrails=kw['guardrails'],authority=authority)
        self.assertEqual(result['status'],'unknown')
        self.assertEqual(settle(budget,request,result['status']),budget)
        success=settle(budget,request,'executed')
        self.assertEqual(success.completed_effects,1)
        self.assertEqual(settle(success,request,'executed'),success)

    def test_corrected_observation_never_retroactively_completes_failed_task(self):
        verifier=fixtures.load('experiments/kernel-increment-11/live/verify.py','corrected_verifier_test')
        root=ROOT/'experiments/kernel-increment-11/evidence/live-authorized/acceptance'
        target=root/'worker-observation.json';original=json.loads(target.read_text())
        # Synthetic in-memory overlay only; no historical file or artifact is written.
        stream=b'\n'.join(json.dumps(v).encode() for v in
            (fixtures.START,fixtures.MESSAGE,fixtures.ITEM_ERROR,fixtures.COMPLETED))
        observed,_=binding.observe_stream(stream,exit_code=0)
        overlay={**original,**observed,'observation_version':2,'unexpected_items':[]}
        read_text=Path.read_text
        def read(path,*a,**k):
            return json.dumps(overlay) if path==target else read_text(path,*a,**k)
        with patch.object(Path,'read_text',read):
            report=verifier.verify(root)
            self.assertEqual(report['status'],'STOP')
            self.assertEqual(report['task_lifecycle'],'FAILED')
            self.assertEqual(report['pending_dispatches'],1)
            self.assertEqual(report['diagnostics'][0]['classification'],'non_terminal_diagnostic')
            for version in (3,2.0,True):
                overlay['observation_version']=version
                with self.assertRaises(AssertionError):verifier.verify(root)
