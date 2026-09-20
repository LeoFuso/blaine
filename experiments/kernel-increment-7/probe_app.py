"""Real Goose worker; scripted Loop decisions and a controlled interruption observer."""
import asyncio
import json
import os
from pathlib import Path
import restate
from hypercorn.asyncio import serve
from hypercorn.config import Config
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.cognition import ScriptedCognition
from runtime.kernel.contracts import encode
from runtime.kernel.execution import Capabilities
from runtime.kernel.worker import GooseWorker
from runtime.kernel.workflow import create_workflow
from capture import start_capture

ROOT=Path(os.environ['KERNEL_PROBE_DIR'])
FIXTURES=json.loads((ROOT/'fixtures.json').read_text())


def audit(name,value):
    with (ROOT/name).open('ab',buffering=0) as f:
        f.write(encode({'pid':os.getpid(),**value})+b'\n');os.fsync(f.fileno())


def cognitive(packet):
    actions=json.loads(json.dumps(FIXTURES[packet['payload']['task_id']]['actions']))
    for action in [actions[packet['payload']['iteration']-1]]:
        if action.get('capability')=='worker.run':
            action['input']['packet_ref']=next(x['source'] for x in packet['payload']['context']
                if x['authority']=='artifact' and x['content']['name']=='worker_packet')
    result=ScriptedCognition(actions)(packet)
    audit('cognition.jsonl',{'packet':packet,'decision':result});return result


class Audited(Capabilities):
    def execute(self,request):
        result=super().execute(request)
        audit('capabilities.jsonl',{'request':request,'result':result});return result


def started(data):
    audit('workers-started.jsonl',data)


store=ArtifactStore(ROOT/'artifacts')
worker=GooseWorker(Path('/home/leofuso/.local/bin/goose'),ROOT/'worker-scratch',
                  audit=lambda value:audit('workers.jsonl',value),proxy='http://127.0.0.1:39111',started=started)
workflow=create_workflow(store,cognitive,Audited(store,ROOT/'fixture.sqlite',worker=worker))
if __name__=='__main__':
    server=start_capture(ROOT,audit)
    config=Config();config.bind=['127.0.0.1:39080']
    asyncio.run(serve(restate.app([workflow]),config))
