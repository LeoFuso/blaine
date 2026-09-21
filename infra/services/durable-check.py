#!/usr/bin/env python3
"""One-shot acceptance of actual Blaine/Restate. Repeat reads with reboot-check.py."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import uuid

sys.path.insert(0,str(Path.home()/'.local/share/blaine/runtime/app'))
from runtime.personal_agent import PersonalAgent,RestateBinding,small_request,decision_request
from runtime.kernel.contracts import message
from runtime.kernel.human import request_digest

out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
if (out/'durable-summary.json').exists():
    raise SystemExit('Acceptance already recorded; use reboot-check.py for non-mutating verification')
control=PersonalAgent(RestateBinding())
def save(name,value): (out/(name+'.json')).write_text(json.dumps(value,indent=2)+'\n')
def inspect(t): return control.execute({'operation':'inspect','task_id':t})
def until(t,state):
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        result=inspect(t)
        if result['lifecycle']==state and (state=='WAITING' or result.get('result_ref')):return result
        if result['lifecycle'] in ['FAILED','CANCELLED']:raise RuntimeError('Unexpected terminal state '+result['lifecycle'])
        time.sleep(.25)
    raise TimeoutError('Task did not reach '+state)
def unit(name):
    return dict(line.split('=',1) for line in subprocess.check_output(['systemctl','--user','show',name,'-p','MainPID','-p','ActiveState','-p','UnitFileState'],text=True).splitlines())
def http(path,body=None):
    req=urllib.request.Request('http://127.0.0.1:49070'+path,data=json.dumps(body).encode() if body else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)

legacy=json.loads((Path(__file__).resolve().parents[2]/'experiments/daily-driver-d2/evidence/post-sync-native-summary.json').read_text())
legacy_ids=legacy['task_ids']
before={t:inspect(t) for t in legacy_ids}
assert all(v['lifecycle']!='UNAVAILABLE' for v in before.values())
save('restate-retained-legacy-tasks',before)
save('restate-deployments',http('/deployments'))
fixture=out/'durable-fixture.json'
if fixture.exists():f=json.loads(fixture.read_text())
else:
    nonce=uuid.uuid4().hex[:12]
    f={'request_ids':{k:'d1-'+k+'-'+nonce for k in ['waiting','resume','small']},'tasks':{}}
    fixture.write_text(json.dumps(f,indent=2)+'\n')
for kind,rid in f['request_ids'].items():
    raw=small_request('D1 durable service persistence proof') if kind=='small' else decision_request(rid,'Synthetic D1 '+kind+': record the authorized acceptance response?')
    receipt=control.execute({'operation':'create','request_id':rid,'task_request':raw})
    f['tasks'][kind]=receipt['task_id']
    fixture.write_text(json.dumps(f,indent=2)+'\n')
waiting=until(f['tasks']['waiting'],'WAITING')
resume=until(f['tasks']['resume'],'WAITING')
small=until(f['tasks']['small'],'COMPLETED')
save('durable-waiting-before',waiting);save('durable-resume-before',resume);save('durable-small',small)
save('durable-artifact',control.execute({'operation':'artifact','task_id':f['tasks']['small'],'name':'answer'}))
checks=[]
for name in ['blaine-restate.service','blaine-runtime.service']:
    original=unit(name)
    peer='blaine-runtime.service' if name=='blaine-restate.service' else 'blaine-restate.service'
    peer_before=unit(peer)
    if name=='blaine-runtime.service':
        subprocess.run(['systemctl','--user','stop',name],check=True,timeout=90)
        assert unit(name)['MainPID']=='0'
        subprocess.run(['systemctl','--user','start',name],check=True,timeout=180)
    else:subprocess.run(['systemctl','--user','restart',name],check=True,timeout=180)
    current=unit(name)
    assert current['MainPID'] not in ['0',original['MainPID']]
    assert peer_before['MainPID']==unit(peer)['MainPID']
    assert inspect(f['tasks']['waiting'])==waiting
    assert inspect(f['tasks']['resume'])==resume
    assert inspect(f['tasks']['small'])==small
    assert all(inspect(t)==state for t,state in before.items())
    checks.append({'unit':name,'before':original,'after':current,'peer_pid_preserved':True,'same_task_states':True})
    print('Retained Task state after',name,': PASS',flush=True)
pending=resume['pending_human_decision']
response=message('HumanDecisionResponse',{'task_id':f['tasks']['resume'],'request_id':'decision-1',
    'request_revision':0,'request_digest':request_digest(pending),'response_id':'d1-authorized-synthetic-response','value':'YES'})
receipt=control.execute({'operation':'respond','task_id':f['tasks']['resume'],'response':response})
assert receipt['payload']['outcome']=='ACCEPTED'
completed=until(f['tasks']['resume'],'COMPLETED')
save('durable-resumed-completed',completed)
assert inspect(f['tasks']['waiting'])==waiting
save('durable-waiting-after',inspect(f['tasks']['waiting']))
save('durable-summary',{'status':'PASS','restarts':checks,'fixture':f,'legacy_tasks_preserved':len(before),
    'human_wait_retained':True,'separate_task_resumed_after_explicit_response':True,
    'artifact_authority':str(Path.home()/'.local/share/blaine/runtime/data/artifacts')})
print('Durable state, explicit resume and preserved WAITING: PASS',flush=True)
