"""Controlled test bridge to the already-authenticated MCP connector, read only."""
import asyncio
import json
import os
from pathlib import Path
import time
import restate
from hypercorn.asyncio import serve
from hypercorn.config import Config
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.cognition import ScriptedCognition
from runtime.kernel.contracts import encode
from runtime.kernel.execution import Capabilities
from runtime.kernel.workflow import create_workflow
from runtime.kernel.youtrack import YouTrackRead

ROOT=Path(os.environ['KERNEL_PROBE_DIR'])
FIXTURES=json.loads((ROOT/'fixtures.json').read_text())


def audit(name,value):
    with (ROOT/name).open('ab',buffering=0) as f:
        f.write(encode({'pid':os.getpid(),**value})+b'\n'); os.fsync(f.fileno())


def read(issue):
    (ROOT/'connector-request.json').write_bytes(encode({'tool':'get_issue','issueId':issue,'recentCommentsCount':0}))
    # Experiment controller supplies the actual connector response, not a model.
    deadline=time.monotonic()+120
    while not (ROOT/'connector-response.json').exists():
        if time.monotonic()>deadline: raise ValueError('Controlled connector bridge timed out')
        time.sleep(.1)
    return json.loads((ROOT/'connector-response.json').read_text())


def cognitive(packet):
    result=ScriptedCognition(FIXTURES[packet['payload']['task_id']]['actions'])(packet)
    audit('cognition.jsonl',{'packet':packet,'decision':result})
    return result


class Audited(Capabilities):
    def execute(self,request):
        result=super().execute(request)
        audit('capabilities.jsonl',{'request':request,'result':result})
        return result


store=ArtifactStore(ROOT/'artifacts')
workflow=create_workflow(store,cognitive,Audited(store,ROOT/'fixture.sqlite',
    card_reader=YouTrackRead(read,frozenset({'NCP-2'}))))
if __name__=='__main__':
    config=Config();config.bind=['127.0.0.1:39080']
    asyncio.run(serve(restate.app([workflow]),config))
