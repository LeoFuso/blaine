"""Increment 3 deployment: real Qwen, scripted control and invalid-response fixtures."""
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
from runtime.kernel.model import LocalModelCognition
from runtime.kernel.workflow import create_workflow

ROOT = Path(os.environ['KERNEL_PROBE_DIR'])
CONTENT = 'QWEN_EVIDENCE_V1'


def audit(name, data):
    with (ROOT / name).open('ab', buffering=0) as stream:
        stream.write(encode({'pid': os.getpid(), **data}) + b'\n')
        os.fsync(stream.fileno())


model = LocalModelCognition(audit=lambda row: audit('model.jsonl', row))
script = ScriptedCognition([{'type':'INVOKE_CAPABILITY','capability':'artifact.write','input':{'name':'answer','content':CONTENT}}, {'type':'COMPLETE'}])


def cognitive(packet):
    task = packet['payload']['task_id']
    if task in ('malformed', 'unsupported'):
        content = 'not json' if task == 'malformed' else json.dumps({'version':1,'kind':'CognitiveDecision','payload':{
            'task_id':task,'task_revision':0,'turn_id':task+'/1','next_action':{'type':'DELETE_ALL'}}})
        adapter = LocalModelCognition(transport=lambda _: {'choices':[{'finish_reason':'stop','message':{'content':content}}]},
                                      audit=lambda row: audit('invalid-model.jsonl', row))
    else:
        adapter = script if task == 'scripted' else model
    result = adapter(packet)
    audit('cognition.jsonl', {'packet':packet,'decision':result})
    return result


class AuditedCapabilities(Capabilities):
    def execute(self, request):
        audit('capabilities.jsonl', {'request':request})
        return super().execute(request)


store = ArtifactStore(ROOT / 'artifacts')
workflow = create_workflow(store, cognitive, AuditedCapabilities(store, ROOT / 'fixture.sqlite'))
if __name__ == '__main__':
    config = Config(); config.bind = ['127.0.0.1:39080']
    asyncio.run(serve(restate.app([workflow]), config))
