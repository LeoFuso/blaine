"""Codex app-server 0.155.1 execution observation, mapped to Blaine boundaries.

This is an observation adapter, not a reimplementation of the Codex agent loop.
Codex keeps its own thread/turn lifecycle; Blaine only normalizes what the
protocol actually exposes and declares honestly what it cannot do.

Measured protocol facts (live, CLI 0.155.1, `codex app-server generate-json-schema`
plus recorded stdio sessions):

* `thread/tokenUsage/updated` is emitted exactly once per model invocation and
  carries that invocation's own token breakdown in `tokenUsage.last`. It is the
  last event before the next model invocation begins, which makes it the
  observable continuation boundary marker.
* `item/started` / `item/completed` bound each tool item, with status, exit code
  and duration for command execution.
* `turn/steer` is accepted while a tool is running and its input is consumed at
  the next continuation boundary, immediately after the boundary marker.
* `turn/interrupt` ends the turn with status `interrupted`; an in-flight tool
  item receives no terminal `item/completed`, so its span must close as unknown.
* Approval `ServerRequest`s block Codex until the client answers, but they occur
  before a tool runs, not at a continuation boundary.
* `model` and `effort` are only accepted by `turn/start`, so rebinding is a turn
  granularity control, never a continuation-granularity one.

Raw model text, reasoning, command strings and tool payloads are not copied into
observations. Only bounded metadata, identities, digests and counters are kept.
"""
from dataclasses import dataclass, field
import hashlib

from runtime.kernel.instrument import (
    ADMIT_CONTINUATION, AdapterProfile, CapabilityClaim, INTERRUPT_EXECUTION,
    OBSERVE_CONTINUATION, OBSERVE_MODEL, OBSERVE_TOOL, REBIND_EFFORT, REBIND_MODEL,
    STEER_CONTINUATION,
)

PROTOCOL = 'codex-app-server/0.155.1'
BOUNDARY_MARKER = 'thread/tokenUsage/updated'
# Notifications this observer understands. Anything else is counted, not copied.
KNOWN = {'thread/started', 'thread/status/changed', 'turn/started', 'turn/completed',
         'item/started', 'item/completed', BOUNDARY_MARKER, 'thread/queue/changed'}
TOOL_ITEMS = {'commandExecution', 'mcpToolCall', 'dynamicToolCall', 'webSearch', 'fileChange',
              'functionCallOutput', 'imageView', 'imageGeneration'}
APPROVAL_REQUESTS = {'item/commandExecution/requestApproval', 'item/fileChange/requestApproval',
                     'item/permissions/requestApproval', 'applyPatchApproval', 'execCommandApproval'}

CAPABILITIES = AdapterProfile('codex-app-server', 'codex-cli-0.155.1', (
    CapabilityClaim(OBSERVE_CONTINUATION, 'OBSERVED', 'continuation', 'live',
                    'thread/tokenUsage/updated marks one boundary per model invocation.'),
    CapabilityClaim(OBSERVE_MODEL, 'OBSERVED', 'continuation', 'live',
                    'Per-invocation input/cached/output/reasoning tokens are reported.'),
    CapabilityClaim(OBSERVE_TOOL, 'OBSERVED', 'continuation', 'live',
                    'Item lifecycle exposes tool status, exit code and duration.'),
    CapabilityClaim(STEER_CONTINUATION, 'OBSERVED', 'continuation', 'live',
                    'turn/steer is accepted mid-tool and consumed at the next boundary.'),
    CapabilityClaim(INTERRUPT_EXECUTION, 'OBSERVED', 'agent_turn', 'live',
                    'turn/interrupt ends the active turn as interrupted.'),
    # The boundary marker is a notification: Codex does not await a client reply
    # there. The only blocking client callback is tool approval, which happens
    # before a tool runs rather than before the next model continuation.
    CapabilityClaim(ADMIT_CONTINUATION, 'UNSUPPORTED', None, 'none',
                    'Codex never waits for the client at a continuation boundary.'),
    CapabilityClaim(REBIND_MODEL, 'OBSERVED', 'agent_turn', 'protocol',
                    'turn/start accepts a model override; no mid-turn rebinding exists.'),
    CapabilityClaim(REBIND_EFFORT, 'OBSERVED', 'agent_turn', 'protocol',
                    'turn/start accepts an effort override; no mid-turn rebinding exists.'),
))


def digest(value: object) -> str:
    return hashlib.sha256(repr(value).encode('utf-8', errors='replace')).hexdigest()


@dataclass
class Observation:
    protocol: str = PROTOCOL
    thread_id: str | None = None
    turn_id: str | None = None
    turn_status: str | None = None
    boundaries: list = field(default_factory=list)
    model_invocations: list = field(default_factory=list)
    tool_invocations: list = field(default_factory=list)
    steering: list = field(default_factory=list)
    approvals: list = field(default_factory=list)
    unknown_events: int = 0
    malformed_events: int = 0
    open_tool_items: list = field(default_factory=list)

    def summary(self) -> dict:
        return {'protocol': self.protocol, 'thread_id': self.thread_id, 'turn_id': self.turn_id,
                'turn_status': self.turn_status, 'boundaries': self.boundaries,
                'model_invocations': self.model_invocations, 'tool_invocations': self.tool_invocations,
                'steering': self.steering, 'approvals': self.approvals,
                'unknown_events': self.unknown_events, 'malformed_events': self.malformed_events,
                'unterminated_tool_items': self.open_tool_items,
                'capabilities': CAPABILITIES.summary()}


CONTROL_REQUESTS = {'turn/steer': 'steer', 'turn/interrupt': 'interrupt'}


def observe(records, *, capture_content=False, limit=4096):
    """Map an ordered app-server message stream onto continuation boundaries.

    `records` is the ordered stdio conversation. Each entry carries `_dir` of
    `in` or `out`, so a control request Blaine sent can be correlated with the
    continuation that consumed it. Partial metadata, unknown notification types
    and malformed records are counted, never promoted into a claimed capability.
    """
    observation = Observation()
    if not isinstance(records, list) or len(records) > limit:
        observation.malformed_events += 1
        return observation
    pending_tools, index = {}, 0
    tools_since_boundary, control_requests = [], {}
    for record in records:
        if not isinstance(record, dict):
            observation.malformed_events += 1
            continue
        method, params = record.get('method'), record.get('params')
        if record.get('_dir') == 'out':
            kind = CONTROL_REQUESTS.get(method)
            if kind == 'steer':
                control_requests[record.get('id')] = len(observation.steering)
                observation.steering.append({'control': 'turn/steer', 'phase': 'requested',
                    'requested_at_ms': record.get('_t_ms'), 'boundary_index_at_request': index,
                    'tool_active_at_request': bool(pending_tools)})
            elif kind == 'interrupt':
                observation.approvals.append({'control': 'turn/interrupt', 'at_ms': record.get('_t_ms'),
                    'boundary_index': index, 'blocking': False, 'boundary_relation': 'active_execution'})
            continue
        if method is None:
            slot = control_requests.pop(record.get('id'), None)
            if slot is not None:
                observation.steering[slot].update(phase='accepted', accepted_at_ms=record.get('_t_ms'),
                    turn_id=(record.get('result') or {}).get('turnId'))
            continue
        if not isinstance(method, str):
            observation.malformed_events += 1
            continue
        if method in APPROVAL_REQUESTS:
            # A synchronous, blocking client callback, before a tool executes.
            observation.approvals.append({'method': method, 'at_ms': record.get('_t_ms'),
                                          'blocking': True, 'boundary_index': index,
                                          'boundary_relation': 'pre_tool_execution'})
            continue
        if method not in KNOWN:
            observation.unknown_events += 1
            continue
        if not isinstance(params, dict):
            observation.malformed_events += 1
            continue
        if method == 'thread/started':
            observation.thread_id = params.get('threadId') or (params.get('thread') or {}).get('id')
        elif method == 'turn/started':
            observation.turn_id = (params.get('turn') or {}).get('id')
        elif method == 'turn/completed':
            turn = params.get('turn') or {}
            observation.turn_status = turn.get('status')
        elif method in ('item/started', 'item/completed'):
            item = params.get('item')
            if not isinstance(item, dict):
                observation.malformed_events += 1
                continue
            kind, item_id = item.get('type'), item.get('id')
            if method == 'item/started' and kind in TOOL_ITEMS:
                pending_tools[item_id] = {'item_id': item_id, 'tool_type': kind,
                                          'started_at_ms': record.get('_t_ms'), 'boundary_index': index}
            elif method == 'item/completed' and kind in TOOL_ITEMS:
                call = pending_tools.pop(item_id, {'item_id': item_id, 'tool_type': kind,
                                                   'boundary_index': index, 'started_at_ms': None})
                call.update(status=item.get('status'), exit_code=item.get('exitCode'),
                            duration_ms=item.get('durationMs'), completed_at_ms=record.get('_t_ms'),
                            tool_name=item.get('tool') or kind,
                            request_digest=digest(item.get('command') or item.get('arguments')))
                if capture_content:
                    call['command'] = item.get('command')
                observation.tool_invocations.append(call)
                tools_since_boundary.append(call)
            elif method == 'item/completed' and kind == 'userMessage':
                # Steering consumption: injected input appears immediately after
                # the boundary marker that ends the previous model invocation.
                outstanding = next((entry for entry in observation.steering
                                    if entry.get('phase') == 'accepted' and 'consumed_at_ms' not in entry), None)
                if outstanding is not None:
                    outstanding.update(phase='consumed', consumed_at_ms=record.get('_t_ms'),
                                       consumed_at_boundary_index=index)
        elif method == BOUNDARY_MARKER:
            usage = (params.get('tokenUsage') or {}).get('last')
            usage = usage if isinstance(usage, dict) else {}
            observation.model_invocations.append({
                'model_invocation_index': index, 'turn_id': params.get('turnId'),
                'input_tokens': usage.get('inputTokens'), 'output_tokens': usage.get('outputTokens'),
                'cached_input_tokens': usage.get('cachedInputTokens'),
                'cache_write_input_tokens': usage.get('cacheWriteInputTokens'),
                'reasoning_output_tokens': usage.get('reasoningOutputTokens'),
                'observed_at_ms': record.get('_t_ms')})
            observation.boundaries.append({
                'index': index, 'reason': 'tool_results' if tools_since_boundary else 'model_result',
                'model_invocations': index + 1, 'tool_invocations': len(observation.tool_invocations),
                'tools_in_previous_continuation': [c['item_id'] for c in tools_since_boundary],
                'observed_at_ms': record.get('_t_ms'), 'marker': BOUNDARY_MARKER,
                'synchronous_admission': False})
            tools_since_boundary = []
            index += 1
    # An interrupted turn leaves a tool item without a terminal event. Report it
    # as unterminated rather than inventing a success or failure outcome.
    observation.open_tool_items = [{**call, 'status': 'unterminated'} for call in pending_tools.values()]
    return observation
