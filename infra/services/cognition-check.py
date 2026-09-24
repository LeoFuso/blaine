#!/usr/bin/env python3
"""Exercise the actual deployed cognition and MIRIX context inside a durable Task."""
import hashlib,json
from pathlib import Path
import sys,time,uuid
sys.path.insert(0,str(Path.home()/'.local/share/blaine/runtime/app'))
from runtime.personal_agent import PersonalAgent,RestateBinding
from runtime.kernel.contracts import message
out=Path(sys.argv[1]); f=json.loads((out/'mirix-fixture.json').read_text())
raw=message('TaskSpec',{
 'objective':f"For project {f['project']}, retrieve its release marker from semantic memory and write only that exact marker into artifact answer, with no newline.",
 'completion':[{'criterion':'Exact known semantic fact recalled','evidence':{'artifact':'answer','sha256':hashlib.sha256(f['marker'].encode()).hexdigest()}}],
 'capabilities':['artifact.write'],'autonomy':{'allowed':['artifact.write']}})
p=out/'cognition-fixture.json'
if p.exists():fixture=json.loads(p.read_text())
else:
 fixture={'request_id':'d1-cognition-'+uuid.uuid4().hex[:12],'task_request':raw}
 p.write_text(json.dumps(fixture,indent=2)+'\n')
control=PersonalAgent(RestateBinding())
receipt=control.execute({'operation':'create','request_id':fixture['request_id'],'task_request':fixture['task_request']})
task=receipt['task_id']; fixture['task_id']=task
p.write_text(json.dumps(fixture,indent=2)+'\n')
deadline=time.monotonic()+150
while time.monotonic()<deadline:
 state=control.execute({'operation':'inspect','task_id':task})
 if state['lifecycle'] in ['COMPLETED','FAILED','CANCELLED','WAITING']:break
 time.sleep(.5)
(out/'cognition-state.json').write_text(json.dumps(state,indent=2)+'\n')
assert state['lifecycle']=='COMPLETED',state['lifecycle']
answer=control.execute({'operation':'artifact','task_id':task,'name':'answer'})
assert answer['content']==f['marker']
(out/'cognition-artifact.json').write_text(json.dumps(answer,indent=2)+'\n')
(out/'cognition-summary.json').write_text(json.dumps({'status':'PASS','task_id':task,'memory_id':f['memory_ids'],'objective_did_not_contain_marker':True,'artifact_matches_known_fact':True},indent=2)+'\n')
print('Actual durable Task recalled MIRIX fact through local cognition: PASS',task)
