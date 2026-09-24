"""E1.0 acceptance deployment only: the production CognitiveTaskV1 workflow with
scripted cognition, a stub semantic reviewer, audit logs and test-only durable
barriers. No model, provider, network or workstation is involved."""
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
from runtime.kernel.contracts import encode, message
from runtime.kernel.event_sinks import JsonlEventPublisher
from runtime.kernel.execution import Capabilities
from runtime.kernel.workflow import create_workflow
import completion_fixtures as fx

DIRECTORY = Path(os.environ['E10_PROBE_DIR'])
FIXTURES = json.loads((DIRECTORY / 'fixtures.json').read_text())
PORT = 39280


def audit(name, value):
    with (DIRECTORY / name).open('ab', buffering=0) as stream:
        stream.write(encode({'pid': os.getpid(), **value}) + b'\n')
        os.fsync(stream.fileno())


def receipt(turn):
    refs = [item['source'] for item in turn['context']
            if item['authority'] == 'artifact' and item['content'].get('name') == 'receipt']
    return refs[0]


def human_request(turn):
    for criterion in turn['contract']['criteria']:
        if 'request' in criterion:
            return criterion['request']
    return next(c['evidence']['request'] for c in turn['completion'] if c['evidence'].get('verifier') == 'human_response')


def action_for(turn):
    step = FIXTURES[turn['task_id']]['script'][str(turn['iteration'])]
    match step:
        case 'cite':
            return fx.write('findings', fx.findings(receipt(turn)))
        case 'fabricate':
            return fx.write('findings', fx.findings(receipt(turn), quote='return Response.serverError(); // fabricated'))
        case 'write-answer':
            return fx.write('answer', 'GOOD')
        case 'human-request':
            return {'type': 'INVOKE_CAPABILITY', 'capability': 'human.request', 'input': {'request': human_request(turn)}}
        case 'effect':
            return {'type': 'INVOKE_CAPABILITY', 'capability': 'fixture.effect', 'input': {'value': 'synthetic effect'}}
        case 'wait':
            return {'type': 'WAIT', 'wait_id': 'continue', 'input_type': 'text'}
        case 'amend-attempt':
            return {'type': 'AMEND_CONTRACT', 'operations': [{'op': 'waive', 'id': 'c1'}]}
    raise ValueError('Script exhausted')


def cognitive(packet):
    turn = packet['payload']
    decision = fx.decision(packet, action_for(turn))
    audit('cognition.jsonl', {'task_id': turn['task_id'], 'iteration': turn['iteration'],
                              'contract_revision': turn['contract']['revision'], 'decision': decision})
    return decision


def reviewer(packet):
    request = packet['payload']
    audit('reviews.jsonl', {'task_id': request['task_id'], 'criterion_id': request['criterion_id'],
                            'contract_revision': request['contract_revision'],
                            'evidence_digest': request['evidence_digest']})
    return message('SemanticReviewResult', {**{k: request[k] for k in (
        'task_id', 'criterion_id', 'contract_revision', 'evidence_digest')},
        'verdict': 'satisfied', 'confidence': 'high', 'rationale': 'Deterministic stub; not model evidence.',
        'evidence_refs': [item['ref'] for item in request['evidence']]})


class Audited(Capabilities):
    def execute(self, request):
        payload = request['payload']
        audit('capabilities.jsonl', {'task_id': payload['task_id'], 'operation_id': payload['operation_id'],
                                     'capability': payload['capability']})
        return super().execute(request)


async def checkpoint(ctx, stage, state):
    marker = f"{stage}/{state['iteration']}"
    if marker in FIXTURES[state['task_id']].get('barriers', []):
        ctx.set('probe', {'marker': marker, 'state': state})
        await ctx.promise('probe/' + marker, type_hint=dict).value()


store = ArtifactStore(DIRECTORY / 'artifacts')
workflow = create_workflow(store, cognitive, Audited(store, DIRECTORY / 'fixture.sqlite'), checkpoint=checkpoint,
                           event_publisher=JsonlEventPublisher(DIRECTORY / 'events.jsonl'), semantic_reviewer=reviewer)


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
