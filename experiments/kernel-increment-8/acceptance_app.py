"""Increment 8 acceptance instrumentation over the production CognitiveTask workflow."""
import asyncio
from copy import deepcopy
import os
from pathlib import Path
import sys
import time
import restate
from hypercorn.asyncio import serve
from hypercorn.config import Config
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import encode, message
from runtime.kernel.execution import Capabilities, policy_gate
from runtime.kernel.procedure import ProcedureContext
from runtime.kernel.model import LocalModelCognition
from runtime.kernel.semantic_provider import JsonSemanticDecisionProvider, validate_admissibility
from runtime.kernel.semantic_bridge import SemanticDecisionBridge
from runtime.kernel.semantic_provider import current_actions
from runtime.kernel.workflow import create_workflow

ROOT = Path(os.environ['KERNEL_PROBE_DIR'])
MODE = 'production'
STATE = {}

def audit(name, data):
    with (ROOT / name).open('ab', buffering=0) as stream:
        stream.write(encode({'pid': os.getpid(), 'time_ns': time.time_ns(), **data}) + b'\n')
        os.fsync(stream.fileno())

wire = LocalModelCognition()

def transport(body):
    # Invocation count includes attempts, not merely responses. Fixed diagnostic budget.
    log = ROOT / 'call-start.jsonl'
    if log.exists() and len(log.read_text().splitlines()) >= 6:
        raise restate.TerminalError('Bounded experiment inference budget exhausted')
    started = time.time_ns()
    audit('call-start.jsonl', {'request': body, 'endpoint': wire.endpoint + '/chat/completions'})
    response = wire.request(body)
    safe = {k: response.get(k) for k in ('id', 'model', 'created', 'usage')}
    safe['choices'] = [{'finish_reason': c.get('finish_reason'), 'content': c.get('message', {}).get('content')}
                       for c in response.get('choices', [])]
    audit('wire.jsonl', {'endpoint': wire.endpoint + '/chat/completions', 'request': body,
        'started_ns': started, 'elapsed_seconds': (time.time_ns()-started)/1e9, 'raw_response_safe': safe})
    return response

provider = JsonSemanticDecisionProvider(wire.model, transport)
store = ArtifactStore(ROOT / 'artifacts')
bridge = SemanticDecisionBridge(provider, store, purpose='retention_period', request_id='retention',
    artifact='answer', audit=lambda row: audit('semantic.jsonl', row))
procedure = ProcedureContext(Path(__file__).with_name('speckit-semantic-clarification.md'),
    'https://raw.githubusercontent.com/github/spec-kit/main/templates/commands/clarify.md#adapted-excerpt',
    frozenset({'procedure'}))

def cognitive(packet):
    state = deepcopy(STATE[packet['payload']['task_id']])
    if state['task_id'] == 'incomplete-effect':
        # Explicit deterministic negative fixture, never counted as model inference.
        turn = packet['payload']
        content = 'DRAFT' if turn['iteration'] == 1 else 'VERIFIED_RESULT'
        if turn['iteration'] > 2:
            raise restate.TerminalError('Negative control exceeded two scripted turns')
        command = message('CognitiveDecision', {k: turn[k] for k in ('task_id', 'task_revision', 'turn_id')} |
            {'next_action': {'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write',
                'input': {'name': 'answer', 'content': content}}})
        audit('scripted.jsonl', {'provider': 'deterministic negative fixture', 'state': state,
            'packet': packet, 'decision': command})
        return command
    spec = store.read_json(state['task_id'], state['spec_ref'])['payload']
    context = bridge.project(packet)
    projection = current_actions(context, packet['payload']['allowed_capabilities'])
    audit('turns.jsonl', {'state': state, 'packet': packet, 'projection': projection, 'cognition_invoked': True})
    command = bridge(packet)
    audit('cognition.jsonl', {'packet': packet, 'decision': command})
    return command

class AuditedCapabilities(Capabilities):
    def execute(self, request):
        result = super().execute(request)
        audit('capabilities.jsonl', {'request': request, 'result': result})
        return result

async def checkpoint(ctx, stage, state):
    if stage == 'before_cognition': STATE[state['task_id']] = deepcopy(state)
    # These evidence steps are journaled: replayed hook executions don't inflate transition counts.
    def record():
        row = {'stage': stage, 'state': state}
        if stage == 'decision':
            row['gate'] = policy_gate(store.read_json(state['task_id'], state['decision_ref']), state,
                store.read_json(state['task_id'], state['spec_ref'])['payload'])
        if stage == 'suspended': row.update(cognition_invoked=False, awaited_event=state['wait'])
        if stage.startswith('verification-'):
            row['evaluation'] = store.read_json(state['task_id'], state['completion_ref'])
        audit('states.jsonl', row)
        return None
    await ctx.run_typed(f'experiment-audit/{stage}/{state["iteration"]}', record)
    if stage == 'effect_persisted' and state['task_id'] == 'procedure' and 'answer' in state['artifacts'] and (ROOT/'pause-after-artifact').exists():
        (ROOT/'paused-state.json').write_bytes(encode(state))
        await asyncio.Event().wait()

workflow = create_workflow(store, cognitive, AuditedCapabilities(store, ROOT/'fixture.sqlite'),
    providers=(procedure,), checkpoint=checkpoint)
if __name__ == '__main__':
    audit('process.jsonl', {'event': 'fresh_runtime_started', 'mode': MODE})
    config = Config(); config.bind = ['127.0.0.1:39080']
    asyncio.run(serve(restate.app([workflow]), config))
