import unittest
from runtime.kernel.youtrack import YouTrackRead
from runtime.kernel.execution import policy_gate
from runtime.kernel.contracts import message


class CardTests(unittest.TestCase):
    def test_scope_rejected_before_transport(self):
        calls=[]
        adapter=YouTrackRead(lambda issue: calls.append(issue), frozenset({'TEST-1'}))
        with self.assertRaises(ValueError): adapter('OTHER-1')
        self.assertEqual(calls, [])

    def test_bounded_coordination_snapshot_not_task_state(self):
        raw={'id':'TEST-1','url':'https://example.invalid/issue/TEST-1','summary':'Card',
             'description':'x'*10000,'state':'Done','private_unselected_field':'sentinel'}
        result=YouTrackRead(lambda _:raw,frozenset({'TEST-1'}))('TEST-1')
        self.assertEqual(len(result['description']),1600)
        self.assertEqual(result['authority'],'human_coordination')
        self.assertNotIn('state',result)
        self.assertNotIn('sentinel',str(result))

    def test_task_policy_must_grant_card_capability(self):
        raw=message('CognitiveDecision',{'task_id':'task','task_revision':0,'turn_id':'task/1',
            'next_action':{'type':'INVOKE_CAPABILITY','capability':'youtrack.read','input':{'issue_id':'TEST-1'}}})
        state={'task_id':'task','revision':0,'iteration':1,'lifecycle':'RUNNING'}
        spec={'capabilities':['youtrack.read'],'autonomy':{'allowed':[]}}
        self.assertEqual(policy_gate(raw,state,spec)['outcome'],'deny')
        spec['autonomy']['allowed']=['youtrack.read']
        self.assertEqual(policy_gate(raw,state,spec)['outcome'],'allow')


if __name__=='__main__': unittest.main()
