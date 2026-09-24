"""E2.0 acceptance deployment only: the production CognitiveTaskV1 workflow with a
deterministic FixtureTarget provider, scripted cognition and test-only barriers.
No real filesystem target, IDE, terminal, model or network is involved."""
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT), str(ROOT / 'tests')]

import restate
from hypercorn.asyncio import serve
from hypercorn.config import Config

from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode
from runtime.kernel.event_sinks import JsonlEventPublisher
from runtime.kernel.execution import Capabilities
from runtime.kernel.workflow import create_workflow
import completion_fixtures as fx
import effect_fixtures as ef

DIRECTORY = Path(os.environ['E20_PROBE_DIR'])
FIXTURES = json.loads((DIRECTORY / 'fixtures.json').read_text())
PORT = 39380


def audit(name, value):
    with (DIRECTORY / name).open('ab', buffering=0) as stream:
        stream.write(encode({'pid': os.getpid(), **value}) + b'\n')
        os.fsync(stream.fileno())


def action_for(turn):
    match FIXTURES[turn['task_id']]['script'][str(turn['iteration'])]:
        case 'read':
            return ef.read()
        case 'draft':
            return ef.draft()
        case 'write':
            return ef.write(ef.artifact_ref(turn, 'draft'), receipt_ref=ef.latest_receipt(turn))
        case 'run':
            return ef.run('unit-tests')
        case 'run-slow':
            return ef.run('slow-build')
        case 'wait':
            return {'type': 'WAIT', 'wait_id': 'continue', 'input_type': 'text'}
    raise ValueError('Script exhausted')


def cognitive(packet):
    turn = packet['payload']
    decision = fx.decision(packet, action_for(turn))
    audit('cognition.jsonl', {'task_id': turn['task_id'], 'iteration': turn['iteration'], 'decision': decision})
    return decision


async def checkpoint(ctx, stage, state):
    marker = f"{stage}/{state['iteration']}"
    if marker in FIXTURES[state['task_id']].get('barriers', []):
        ctx.set('probe', {'marker': marker, 'state': state})
        await ctx.promise('probe/' + marker, type_hint=dict).value()


store = ArtifactStore(DIRECTORY / 'artifacts')
workflow = create_workflow(store, cognitive, Capabilities(store, DIRECTORY / 'fixture.sqlite'), checkpoint=checkpoint,
                           event_publisher=JsonlEventPublisher(DIRECTORY / 'events.jsonl'),
                           target_provider=ef.FixtureTarget(DIRECTORY / 'target.sqlite'), exec_profiles=ef.PROFILES)


@workflow.handler()
async def probe_status(ctx: restate.WorkflowSharedContext) -> dict:
    return await ctx.get('probe') or {}


@workflow.handler()
async def release_probe(ctx: restate.WorkflowSharedContext, request: dict) -> dict:
    if request['marker'] not in FIXTURES[ctx.key()].get('barriers', []):
        raise restate.TerminalError('Unknown test barrier', status_code=400)
    await ctx.promise('probe/' + request['marker'], type_hint=dict).resolve({'released': True})
    return {'released': request['marker']}


if __name__ == '__main__':
    config = Config()
    config.bind = [f'127.0.0.1:{PORT}']
    asyncio.run(serve(restate.app([workflow]), config))
