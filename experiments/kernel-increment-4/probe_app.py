"""Live Increment 4 deployment; no ingestion and no kernel/adapter modification."""
import asyncio
import os
from pathlib import Path
import restate
from hypercorn.asyncio import serve
from hypercorn.config import Config
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode
from runtime.kernel.execution import Capabilities, policy_gate
from runtime.kernel.memory import MirixContext
from runtime.kernel.model import LocalModelCognition
from runtime.kernel.workflow import create_workflow

ROOT = Path(os.environ['KERNEL_PROBE_DIR'])


def audit(name, data):
    with (ROOT / name).open('ab', buffering=0) as stream:
        stream.write(encode({'pid': os.getpid(), **data}) + b'\n')
        os.fsync(stream.fileno())


wire = LocalModelCognition()


def transport(body):
    response = wire.request(body)
    # Deliberately omit any provider reasoning fields/private chain-of-thought.
    safe = {k: response.get(k) for k in ('id', 'model', 'created', 'usage')}
    safe['choices'] = [{'finish_reason': c.get('finish_reason'),
                        'content': c.get('message', {}).get('content')}
                       for c in response.get('choices', [])]
    audit('wire.jsonl', {'endpoint': wire.endpoint + '/chat/completions',
                          'request': body, 'raw_response_safe': safe})
    return response


model = LocalModelCognition(transport=transport, audit=lambda row: audit('model.jsonl', row))


def cognitive(packet):
    decision = model(packet)
    audit('cognition.jsonl', {'packet': packet, 'decision': decision})
    return decision


def memory(request):
    provider = MirixContext('client-df3da0d9', 'probe-leofuso',
        filter_tags={'experiment': 'kernel-increment-4-v1', 'fixture': request['task_id']},
        audit=lambda row: audit('memory.jsonl', row))
    return provider(request)


class AuditedCapabilities(Capabilities):
    def execute(self, request):
        result = super().execute(request)
        audit('capabilities.jsonl', {'request': request, 'result': result})
        return result


store = ArtifactStore(ROOT / 'artifacts')


async def checkpoint(ctx, stage, state):
    if stage == 'decision':
        decision = store.read_json(state['task_id'], state['decision_ref'])
        spec = store.read_json(state['task_id'], state['spec_ref'])['payload']
        audit('policy.jsonl', {'task_id': state['task_id'], 'decision_id': state['decision_id'],
                              'gate': policy_gate(decision, state, spec)})


workflow = create_workflow(store, cognitive, AuditedCapabilities(store, ROOT / 'fixture.sqlite'),
                           providers=(memory,), checkpoint=checkpoint)
if __name__ == '__main__':
    audit('process.jsonl', {'event': 'fresh_runtime_started'})
    config = Config(); config.bind = ['127.0.0.1:39080']
    asyncio.run(serve(restate.app([workflow]), config))
