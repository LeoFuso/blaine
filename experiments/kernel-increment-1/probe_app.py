"""Test deployment only: scripted cognition, audit, and controlled crash barriers."""
import asyncio
from copy import deepcopy
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

ROOT = Path(os.environ['KERNEL_PROBE_DIR'])
FIXTURES = json.loads((ROOT / 'fixtures.json').read_text())


def audit(name, value):
    with (ROOT / name).open('ab', buffering=0) as stream:
        stream.write(encode({'pid': os.getpid(), **value}) + b'\n')
        os.fsync(stream.fileno())


def cognitive(packet):
    turn = packet['payload']
    fixture = FIXTURES[turn['task_id']]
    actions = deepcopy(fixture['actions'])
    action = actions[turn['iteration'] - 1]
    if action.get('capability') == 'artifact.read':
        action['input']['ref'] = next(item['source'] for item in turn['context']
                                      if item['authority'] == 'artifact' and item['content']['name'] == 'answer')
    decision = ScriptedCognition(actions)(packet)
    audit('cognition.jsonl', {'packet': packet, 'decision': decision})
    return decision


class AuditedCapabilities(Capabilities):
    def execute(self, request):
        audit('capabilities.jsonl', {'request': request})
        result = super().execute(request)
        payload = request['payload']
        if FIXTURES[payload['task_id']].get('lose_effect_response') and payload['capability'] == 'fixture.effect':
            audit('effect-committed.jsonl', {'request': request, 'result': result})
            # Block only this test capability thread after the SQLite effect commits.
            while not (ROOT / 'release-effect').exists():
                time.sleep(0.05)
        return result


async def checkpoint(ctx, point, state):
    marker = f"{point}/{state['iteration']}"
    if marker in FIXTURES[state['task_id']].get('barriers', []):
        ctx.set('probe', {'marker': marker, 'state': state})
        await ctx.promise('probe/' + marker, type_hint=dict).value()


store = ArtifactStore(ROOT / 'artifacts')
workflow = create_workflow(store, cognitive, AuditedCapabilities(store, ROOT / 'fixture.sqlite'), checkpoint=checkpoint)


@workflow.handler()
async def probe_status(ctx: restate.WorkflowSharedContext) -> dict:
    return await ctx.get('probe') or {}


@workflow.handler()
async def release_probe(ctx: restate.WorkflowSharedContext, request: dict) -> dict:
    marker = request['marker']
    if marker not in FIXTURES[ctx.key()].get('barriers', []):
        raise restate.TerminalError('Unknown test barrier', status_code=400)
    await ctx.promise('probe/' + marker, type_hint=dict).resolve({'released': True})
    return {'released': marker}


if __name__ == '__main__':
    config = Config()
    config.bind = ['127.0.0.1:39080']
    asyncio.run(serve(restate.app([workflow]), config))
