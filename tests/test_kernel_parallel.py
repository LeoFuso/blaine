"""Local topology controls; fake futures are not durability evidence."""
import asyncio
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from runtime.kernel import workflow
from runtime.kernel.contracts import (message, validate_spec, child_task_id, child_request,
    accept_task_request, spawn_specs, validate_decision, validate_result)
from runtime.kernel.execution import policy_gate, Capabilities
from runtime.kernel.artifacts import ArtifactStore
from test_kernel import state, decision
from test_kernel_progression import Registry, Context


def spec(value='child', allocation=0, allowed=None):
    return message('TaskSpec', {'objective': 'Produce '+value,
        'completion': [{'criterion':'Exact', 'evidence':{'artifact':'answer','sha256':hashlib.sha256(value.encode()).hexdigest()}}],
        'capabilities':['artifact.write','fixture.effect'],
        'autonomy':{'allowed':allowed if allowed is not None else ['artifact.write','fixture.effect'], 'child_tasks':allocation}})


def batch(*children):
    return {'type':'SPAWN_TASK','task_specs':list(children), 'independent':True}


class ParallelContracts(unittest.TestCase):
    def test_explicit_relationship_and_stable_slot_identity(self):
        for slot in [None,0,1]:
            key=child_task_id('parent','parent/1',slot)
            accepted,parent=accept_task_request(child_request('parent','parent/1',slot,validate_spec(spec())),key)
            self.assertEqual(parent,{'task_id':'parent','decision_id':'parent/1','slot':slot})
            self.assertEqual(accepted,validate_spec(spec()))
        self.assertEqual(len({child_task_id('parent','parent/1',i) for i in [None,0,1]}),3)
        for slot in [-1,4,True,'0']:
            with self.assertRaises(ValueError):child_task_id('parent','parent/1',slot)
        with self.assertRaises(ValueError):accept_task_request(child_request('parent','parent/1',0,validate_spec(spec())),'wrong')
        for raw in [None, [], 'invalid']:
            with self.assertRaises(ValueError):accept_task_request(raw, 'child')

    def test_batch_is_closed_bounded_explicit_and_atomic(self):
        good=batch(spec(),spec())
        self.assertEqual(len(spawn_specs(good)),2)
        for bad in [{**good,'independent':False},{**good,'extra':1},{**good,'task_spec':spec()},
                    {**good,'task_specs':[spec()]},{**good,'task_specs':[spec()]*5}]:
            with self.subTest(bad=bad),self.assertRaises(ValueError):validate_decision(decision(bad))
        p=validate_spec(spec('parent',2));current={**state(),'remaining_children':2}
        self.assertEqual(policy_gate(decision(good),current,p)['outcome'],'allow')
        self.assertEqual(policy_gate(decision(batch(spec(allocation=1),spec())),current,p)['outcome'],'deny')
        p['autonomy']['allowed']=['artifact.write']
        self.assertEqual(policy_gate(decision(good),current,p)['outcome'],'deny')

    def test_stale_malformed_and_transcript_result_rejected(self):
        base={'task_id':'child','outcome':'FAILED','artifacts':{},'completion_ref':None,'concerns':['failed']}
        for obj in [message('TaskResult',{**base,'task_id':'old-child'}),
                    {**message('TaskResult',base),'version':2}, message('TaskResult',{**base,'transcript':['private']})]:
            with self.assertRaises(ValueError):validate_result(obj,'child')


class ParallelProgression(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, failed=False, invalid=False, reverse=False):
        with tempfile.TemporaryDirectory() as d:
            store=ArtifactStore(Path(d)/'artifacts');caps=Capabilities(store,Path(d)/'effects.sqlite')
            futures={};packets=[];joined=[]
            class Parent(Context):
                def key(self):return 'control'
                def set(self,k,v):self.saved[k]=deepcopy(v)
                def workflow_call(self,fn,key,arg):
                    accepted,parent=accept_task_request(arg,key)
                    self_case.assertEqual(parent['task_id'],'control')
                    futures[key]=asyncio.get_running_loop().create_future()
                    return futures[key]
            self_case=self
            async def checkpoint(ctx,stage,current):
                if stage=='children_created':
                    self.assertEqual(len(futures),2) # all launched before first join
                    self.assertEqual(current['lifecycle'],'WAITING')
                    self.assertEqual(len(packets),1)
                if stage=='children_joined':joined.append(deepcopy(current))
            def cognitive(packet):
                packets.append(packet);t=packet['payload']
                if t['iteration']==1:action=batch(spec('A'),spec('B'))
                elif failed:action={'type':'COMPLETE'}
                else:action={'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'answer','content':'parent'}}
                return message('CognitiveDecision',{k:t[k] for k in ('task_id','task_revision','turn_id')}|{'next_action':action})
            with patch.object(workflow.restate,'Workflow',Registry):service=workflow.create_workflow(store,cognitive,caps,checkpoint=checkpoint)
            ctx=Parent();task=asyncio.create_task(service.run(ctx,spec('parent',2)))
            await asyncio.sleep(0)
            self.assertEqual(len(futures),2)
            keys=list(futures)
            for pos in ([1,0] if reverse else [0,1]):
                key=keys[pos];outcome='FAILED' if failed and pos==1 else 'COMPLETED'
                ref=store.put_json(key,message('CompletionEvaluation',{'outcome':'satisfied','criteria':[]}))
                result=message('TaskResult',{'task_id':'stale' if invalid and pos==0 else key,'outcome':outcome,
                    'artifacts':{},'completion_ref':ref,'concerns':[]})
                futures[key].set_result(result);await asyncio.sleep(0)
                if pos==([1,0] if reverse else [0,1])[0]:
                    self.assertEqual(len(packets),1)
                    self.assertFalse(task.done())
            result=await task
            self.assertEqual(result['payload']['outcome'],'FAILED' if failed or invalid else 'COMPLETED')
            if not invalid:
                observed=packets[1]['payload']['observations'][0]['payload']['children']
                self.assertEqual([x['task_id'] for x in observed],keys)
                self.assertEqual(joined[0]['artifacts'],{})
                self.assertEqual(store.read_json('control',joined[0]['completion_ref'])['payload']['outcome'],'unsatisfied')
                self.assertLess(len(str(observed)),2048)
            return result

    async def test_all_success_parent_independent_completion(self):await self.run_case()
    async def test_opposite_order_same_fan_in(self):await self.run_case(reverse=True)
    async def test_failure_truthful_not_parent_success(self):await self.run_case(failed=True)
    async def test_invalid_result_fails_parent_without_completion(self):await self.run_case(invalid=True)

    async def test_existing_single_child_path_and_independent_state(self):
        with tempfile.TemporaryDirectory() as d:
            store=ArtifactStore(Path(d)/'artifacts');caps=Capabilities(store,Path(d)/'effects.sqlite');contexts={};packets=[]
            class LocalContext(Context):
                def __init__(self,key):super().__init__();self.identity=key;contexts[key]=self
                def key(self):return self.identity
                def set(self,k,v):self.saved[k]=deepcopy(v)
                def workflow_call(self,fn,key,arg):return asyncio.create_task(fn(LocalContext(key),arg))
            def cognitive(packet):
                packets.append(packet);t=packet['payload']
                if t['task_id']=='control' and t['iteration']==1:
                    action={'type':'SPAWN_TASK','task_spec':spec('child')}
                else:
                    action={'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'answer','content':'parent' if t['task_id']=='control' else 'child'}}
                return message('CognitiveDecision',{k:t[k] for k in ('task_id','task_revision','turn_id')}|{'next_action':action})
            with patch.object(workflow.restate,'Workflow',Registry):service=workflow.create_workflow(store,cognitive,caps)
            result=await service.run(LocalContext('control'),spec('parent',1))
            self.assertEqual(result['payload']['outcome'],'COMPLETED')
            key=child_task_id('control','control/1')
            self.assertEqual(contexts[key].saved['task']['payload']['parent']['slot'],None)
            parent_second=[p for p in packets if p['payload']['task_id']=='control'][1]
            self.assertEqual(parent_second['payload']['observations'][0]['kind'],'TaskResult')
            self.assertEqual(parent_second['payload']['observations'][0]['payload']['task_id'],key)
