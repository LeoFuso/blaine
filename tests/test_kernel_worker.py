import hashlib
from pathlib import Path
import tempfile
import unittest
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import message
from runtime.kernel.execution import Capabilities, evaluate, policy_gate
from runtime.kernel.worker import validate_packet


class WorkerTests(unittest.TestCase):
    def test_packet_scope_and_size(self):
        raw=message('WorkerInput',{'task_id':'task','objective':'Transform selected text',
                                  'context':[{'source':'fixture:v1','content':'alpha'}]})
        validate_packet(raw,'task')
        with self.assertRaises(ValueError): validate_packet(raw,'other')
        raw['payload']['context'][0]['content']='x'*5000
        with self.assertRaises(ValueError): validate_packet(raw,'task')

    def test_worker_success_does_not_establish_completion(self):
        with tempfile.TemporaryDirectory() as d:
            store=ArtifactStore(Path(d)/'artifacts')
            packet=message('WorkerInput',{'task_id':'task','objective':'Produce evidence','context':[]})
            ref=store.put_json('task',packet)
            worker=lambda p,o:{'outcome':'success','attempt_id':'fake','content':'wrong'}
            caps=Capabilities(store,Path(d)/'fixture.sqlite',worker=worker)
            result=caps.execute(message('CapabilityRequest',{'task_id':'task','operation_id':'task/1',
                'capability':'worker.run','input':{'packet_ref':ref,'artifact':'answer'}}))
            spec={'completion':[{'criterion':'Exact answer','evidence':{'artifact':'answer','sha256':hashlib.sha256(b'right').hexdigest()}}]}
            state={'task_id':'task','artifacts':result['payload']['artifacts']}
            self.assertEqual(result['payload']['outcome'],'success')
            self.assertEqual(evaluate(spec,state,store)['payload']['outcome'],'unsatisfied')

    def test_worker_packet_requires_admission(self):
        state={'task_id':'task','revision':0,'iteration':1,'lifecycle':'RUNNING','artifacts':{}}
        spec={'capabilities':['worker.run'],'autonomy':{'allowed':['worker.run']}}
        decision=message('CognitiveDecision',{'task_id':'task','task_revision':0,'turn_id':'task/1',
            'next_action':{'type':'INVOKE_CAPABILITY','capability':'worker.run','input':{'packet_ref':'unknown','artifact':'answer'}}})
        self.assertEqual(policy_gate(decision,state,spec)['outcome'],'deny')


if __name__=='__main__': unittest.main()
