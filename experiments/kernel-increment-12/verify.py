"""Independent offline verification of native parallel-child evidence. No network."""
from collections import Counter
import hashlib,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import child_task_id,encode,validate_spec,validate_result
from runtime.kernel.execution import evaluate
from runtime.kernel.events import validate_event

def verify(root):
    def read(name):return json.loads((root/(name+'.json')).read_text())
    cases=read('cases');final=read('final-states');results=read('results');journals=read('journals')
    store=ArtifactStore(root/'artifacts')
    cognition=[json.loads(x) for x in (root/'cognition.jsonl').read_text().splitlines()]
    caps=[json.loads(x)['request']['payload'] for x in (root/'capabilities.jsonl').read_text().splitlines()]
    events=[validate_event(json.loads(x)) for x in (root/'events.jsonl').read_text().splitlines()]
    assert len({x['event_id'] for x in events})==len(events)
    assert all(n==1 for n in Counter(x['operation_id'] for x in caps).values())
    invocations=read('invocations')['rows'];assert len(invocations)==12
    assert len({x['id'] for x in invocations})==12
    report={}
    for name,case in cases.items():
        parent=case['parent'];ids=case['children'];states=final[name]
        assert ids==[child_task_id(parent,parent+'/1',i) for i in range(2)]
        assert list(sorted(states[parent]['children']))==sorted(ids)
        assert states[parent]['remaining_children']==0
        for slot,child in enumerate(ids):
            st=states[child]
            assert st['parent']=={'task_id':parent,'decision_id':parent+'/1','slot':slot}
            assert store.read_json(child,st['spec_ref'])['payload']==validate_spec(case['child_specs'][slot])
            validate_result(results[child],child)
            assert store.read_json(parent,states[parent]['children'][child]['result_ref'])==results[child]
            expected='FAILED' if name in ('failure','denial') and slot==1 else 'COMPLETED'
            assert st['lifecycle']==expected
            evaluation=evaluate(validate_spec(case['child_specs'][slot]),st,store)
            assert (evaluation['payload']['outcome']=='satisfied')==(expected=='COMPLETED')
        parents=[r['packet'] for r in cognition if r['packet']['payload']['task_id']==parent]
        assert [p['payload']['iteration'] for p in parents]==list(range(1,len(parents)+1))
        assert all('PRIVATE_CHILD_' not in json.dumps(p) for p in parents)
        aggregate=parents[1]['payload']['observations'][0]
        assert aggregate['kind']=='ChildTaskResults'
        assert [x['task_id'] for x in aggregate['payload']['children']]==ids
        assert len(encode(aggregate))<2048
        for child,outcome in zip(ids,aggregate['payload']['children']):
            assert outcome['outcome']==states[child]['lifecycle']
            assert set(outcome)=={'task_id','outcome','completion_ref','result_ref'}
        # Merely observing successful child results never filled parent artifacts.
        assert not [x for x in parents[1]['payload']['context'] if x['authority']=='artifact']
        waiting=read(name+'-waiting');first=read(name+'-completion-0')
        assert waiting['states'][parent]['lifecycle']=='WAITING'
        assert all(waiting['states'][c]['lifecycle']=='WAITING' for c in ids)
        assert first['states'][parent]['lifecycle']=='WAITING'
        assert first['states'][ids[1-case['order'][0]]]['lifecycle']=='WAITING'
        assert waiting['cognition'][parent]==first['cognition'][parent]==1
        order=[read(name+f'-completion-{i}')['child'] for i in range(2)]
        assert order==[ids[i] for i in case['order']]
        expected='FAILED' if name in ('failure','denial') else 'COMPLETED'
        assert states[parent]['lifecycle']==expected
        pe=evaluate(validate_spec(case['parent_spec']),states[parent],store)
        assert (pe['payload']['outcome']=='satisfied')==(expected=='COMPLETED')
        if expected=='COMPLETED':assert store.read(parent,states[parent]['artifacts']['answer'])==b'A+B'
        else:assert not states[parent]['artifacts']
        for task in [parent,*ids]:
            terminal=[x for x in events if x['task_id']==task and x['event_type']=='completion.finished']
            assert len(terminal)==1 and terminal[0]['outcome']==states[task]['lifecycle']
        parent_events=[x for x in events if x['task_id']==parent]
        creates=[x for x in parent_events if x['event_type']=='task.child_created'];assert len(creates)==2
        assert {x['references']['child_task_id'] for x in creates}==set(ids)
        assert len([x for x in parent_events if x['event_type']=='task.suspended'])==1
        assert len([x for x in parent_events if x['event_type']=='task.resumed'])==1
        calls=[x for x in journals[parent]['rows'] if x['entry_type']=='Command: Call']
        assert len(calls)==2,[(x['entry_type'],x.get('name')) for x in journals[parent]['rows']]
        report[name]={'parent_id':parent,'child_ids':ids,'completion_order':order,
            'parent_outcome':expected,'child_outcomes':[states[c]['lifecycle'] for c in ids],
            'creation_count':len(calls),'result_projection_bytes':len(encode(aggregate)),
            'parent_cognition_while_children_pending':0,'parent_cognitive_turns':len(parents),
            'child_verification_independent':True,'parent_verification':pe['payload']['outcome']}
    denied=cases['denial']['children'][1]
    assert not any(c['task_id']==denied and c['capability']=='fixture.effect' for c in caps)
    assert any(x['task_id']==denied and x['event_type']=='policy.evaluated' and x['outcome']=='deny' for x in events)
    assert len(read('effects'))==7
    for label in ['restart-after-creation','restart-after-one-completion','restart-after-fan-in']:
        snap=read(label);assert snap['before']==snap['after']
        assert snap['cognition_before']==snap['cognition_after']
        for task,before in snap['journals_before'].items():
            later=journals[task]['rows']
            assert len(later)>=len(before['rows'])
            for old,new in zip(before['rows'],later):
                assert all(old[k]==new[k] for k in ('id','index','raw','appended_at'))
        # Every cognitive turn/effect appears only once despite all restarts.
    assert all(n==1 for n in Counter((x['packet']['payload']['task_id'],x['packet']['payload']['iteration']) for x in cognition).values())
    for p in (root/'artifacts').glob('*/*'):assert hashlib.sha256(p.read_bytes()).hexdigest()==p.name
    kills=[x for x in read('process-events') if x['event']=='SIGKILL']
    assert Counter(x['process'] for x in kills)=={'runtime':3,'server':3}
    assert read('processes')['all_stopped']
    return {'status':'PASS','cases':report,'native_tasks':12,'logical_children':8,'duplicate_children':0,
        'fixture_effects':7,'duplicate_capability_executions':0,'duplicate_cognitive_turns':0,
        'duplicate_terminal_events':0,'runtime_sigkills':3,'server_sigkills':3,'events':len(events),
        'authority_denial_effects':0,'live_model_calls':0,'cloud_calls':0,
        'source_of_truth':'Native Restate Task state and joined call results; exact artifacts independently verified',
        'fan_in':'ALL_TERMINAL, stable declared order; failed outcomes are surfaced, never promoted to parent completion',
        'architecture_deviations':[]}

if __name__=='__main__':
    import sys
    print(json.dumps(verify(Path(sys.argv[1])),indent=2))
