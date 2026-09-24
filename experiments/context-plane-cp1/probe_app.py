"""Isolated CP.1 native workflow fixture; recorded cognition, existing local Goose."""
import asyncio
import json
import os
from pathlib import Path
import sys

import restate
from hypercorn.asyncio import serve
from hypercorn.config import Config

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))
from test_kernel_context_plane import Fixture, need
from runtime.kernel.contracts import encode, message
from runtime.kernel.execution import Capabilities
from runtime.kernel.worker import GooseWorker
from runtime.kernel.workflow import create_workflow

OUT = Path(os.environ['CP1_PROBE_DIR'])
config_data = json.loads((OUT / 'config.json').read_text())
f = Fixture(OUT / 'runtime')
# This is a synthetic exact source workload, not a behavioral utility benchmark.
f.spec['objective'] = 'Return only the exact string returned by answer() in the supplied contract.py. No explanation, quotes, or formatting.'
f.spec['completion'][0]['criterion'] = 'Final answer matches the exact accepted bytes; no added newline.'
f.spec_ref = f.store.put_json('control', message('TaskSpec', f.spec))
f.snapshot['payload']['spec_ref'] = f.spec_ref
(OUT / 'spec.json').write_bytes(encode(message('TaskSpec', f.spec)))


def audit(name, value):
    # Explicit fixture evidence only. No snapshot/private policy/provider dumps.
    with (OUT / (name + '.jsonl')).open('ab') as stream:
        stream.write(encode(value) + b'\n')


def cognitive(packet):
    turn = packet['payload']
    index = turn['iteration']
    if index > 3:
        raise restate.TerminalError('CP.1 bounded smoke exhausted')
    ref = next(c['source'] for c in turn['context'] if c['content'] == {'name': 'compiled-context'})
    action = ({'type': 'INVOKE_CAPABILITY', 'capability': 'context.request', 'input': need(base_ref=ref)}
              if index == 2 else {'type': 'INVOKE_CAPABILITY', 'capability': 'worker.run',
                  'input': {'packet_ref': ref, 'artifact': 'draft' if index == 1 else 'answer'}})
    audit('cognition', {'packet': packet, 'packet_bytes': len(encode(packet)), 'recorded_decision': action})
    return message('CognitiveDecision', {k: turn[k] for k in ('task_id', 'task_revision', 'turn_id')} | {'next_action': action})


async def checkpoint(ctx, stage, state):
    if stage == 'effect_persisted':
        observation = f.store.read_json('control', state['observation_ref'])
        audit('capabilities', observation)
        if state['iteration'] == 1:
            f.source.write_text('def answer():\n    return "GOOD"\n')
    if stage.startswith('verification-'):
        audit('verifier', {'iteration': state['iteration'], 'stage': stage,
                          'evaluation': f.store.read_json('control', state['completion_ref'])})


worker = GooseWorker(Path(config_data['goose']), OUT / 'worker-scratch',
    model=config_data['model'], audit=lambda value: audit('workers', {
        'packet': value['packet'], 'packet_bytes': value['packet_bytes'],
        'command': value['command'], 'result': value['result']}))
caps = Capabilities(f.store, OUT / 'runtime' / 'effects.sqlite', worker=worker, context_plane=f.plane)
service = create_workflow(f.store, cognitive, caps, checkpoint=checkpoint)

if __name__ == '__main__':
    config = Config()
    config.bind = ['127.0.0.1:' + str(config_data['endpoint_port'])]
    asyncio.run(serve(restate.app([service]), config))
