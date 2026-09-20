"""Deterministic controls; these are not model inference evidence."""
import unittest
from actions import derive, schema, validate, ProjectedProvider

class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.state={'lifecycle':'RUNNING','active_specialist':'coordinator'}
        self.spec={'capabilities':['human.request','artifact.write'],'autonomy':{'allowed':['human.request','artifact.write']}}
        self.context={'clarification':{'status':'missing'},'specialist':'coordinator'}
    def test_initial_multiple_legal_actions(self):
        p=derive(self.state,self.spec,self.context,choice=True)
        self.assertEqual(p['actions'],['REQUEST_HUMAN','PRODUCE_ARTIFACT','COMPLETE','HANDOFF'])
    def test_resolved_removes_duplicate_but_not_completion_or_rewrite(self):
        self.context['clarification']['status']='resolved'
        self.assertEqual(derive(self.state,self.spec,self.context)['actions'],['PRODUCE_ARTIFACT','COMPLETE'])
    def test_waiting_no_cognition(self):
        self.state['lifecycle']='WAITING'
        p=derive(self.state,self.spec,self.context)
        self.assertFalse(p['actions'])
        with self.assertRaises(ValueError):ProjectedProvider('unused',lambda _:self.fail('inference')).decide({},p['actions'])
    def test_capability_policy_masks(self):
        self.spec['autonomy']['allowed']=[]
        self.assertEqual(derive(self.state,self.spec,self.context)['actions'],['COMPLETE'])
    def test_schema_contains_only_current_actions(self):
        self.assertEqual([s['properties']['action']['const'] for s in schema(['PRODUCE_ARTIFACT','COMPLETE'])['oneOf']],['PRODUCE_ARTIFACT','COMPLETE'])
    def test_unknown_runtime_fields_rejected(self):
        p=derive(self.state,self.spec,self.context)
        for raw in ({'action':'WAIT','purpose':'retention_period'}, {'action':'COMPLETE','version':1},
                    {'action':'PRODUCE_ARTIFACT'}, {'action':'UNKNOWN'}, {'action':'COMPLETE','task_id':'x'}):
            with self.subTest(raw=raw),self.assertRaises(ValueError):validate(raw,p,self.context)
    def test_choice_not_selected_by_policy(self):
        p=derive(self.state,self.spec,self.context,choice=True)
        self.assertEqual(validate({'action':'HANDOFF','specialist':'specialist'},p,self.context)['action'],'HANDOFF')
        self.assertEqual(validate({'action':'REQUEST_HUMAN','purpose':'retention_period','question':'Retention?',
            'response':{'kind':'choice','choices':['30 days','90 days']}},p,self.context)['action'],'REQUEST_HUMAN')
if __name__=='__main__':unittest.main()
