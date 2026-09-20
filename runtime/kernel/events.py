"""Blaine ExecutionEvent v1: diagnostic data, never execution authority.

Only closed metadata is inline. Exact payloads use the existing artifact boundary.
No environment, prompt, response, exception text or arbitrary mapping is accepted.
"""
from datetime import datetime, timezone
import hashlib
import re
from typing import NotRequired, Protocol, TypedDict

from runtime.kernel.contracts import encode, fields, text


class Producer(TypedDict):
    kind: str
    component: str
    component_version: NotRequired[str]
    code_revision: NotRequired[str]


class ExecutionEvent(TypedDict):
    schema_version: int
    event_id: str
    event_type: str
    occurred_at: str
    recorded_at: str
    task_id: str
    run_id: str
    step_id: NotRequired[str]
    attempt_id: NotRequired[str]
    trace_id: NotRequired[str]
    span_id: NotRequired[str]
    parent_event_id: NotRequired[str]
    causation_event_id: NotRequired[str]
    producer: Producer
    references: dict
    outcome: str
    sensitivity: str
    payload: dict
    payload_refs: list[dict]


class ExecutionEventPublisher(Protocol):
    def publish(self, event: ExecutionEvent) -> None:
        """Bounded publication; consumers must deduplicate stable event_id."""


OUTCOMES = {
    'task.started': {'RUNNING'},
    'task.child_created': {'recorded'},
    'task.child_observed': {'COMPLETED', 'FAILED', 'INVALID'},
    'task.suspended': {'WAITING'},
    'task.resumed': {'RUNNING'},
    'cognition.decided': {'recorded'},
    'policy.evaluated': {'allow', 'deny'},
    'capability.finished': {'success', 'failure'},
    'artifact.produced': {'recorded'},
    'verifier.evaluated': {'satisfied', 'unsatisfied', 'unknown'},
    'completion.finished': {'COMPLETED', 'FAILED'},
}
ACTIONS = {'INVOKE_CAPABILITY', 'HANDOFF', 'SPAWN_TASK', 'WAIT', 'COMPLETE'}
REF_KEYS = {'model_call_id', 'capability_call_id', 'artifact_ids', 'human_decision_id',
            'worker_session_id', 'restate_invocation_id', 'decision_id', 'parent_task_id', 'child_task_id'}
ARTIFACT = r'artifact://[A-Za-z0-9_-]{1,80}/sha256:[0-9a-f]{64}'


def validate_event(raw: dict) -> ExecutionEvent:
    required = {'schema_version', 'event_id', 'event_type', 'occurred_at', 'recorded_at',
                'task_id', 'run_id', 'producer', 'references', 'outcome', 'sensitivity', 'payload', 'payload_refs'}
    optional = {'step_id', 'attempt_id', 'trace_id', 'span_id', 'parent_event_id', 'causation_event_id'}
    fields(raw, required, optional)
    if type(raw['schema_version']) is not int or raw['schema_version'] != 1:
        raise ValueError('Unsupported ExecutionEvent version')
    if raw['event_type'] not in OUTCOMES or raw['outcome'] not in OUTCOMES[raw['event_type']]:
        raise ValueError('Unknown event type/outcome')
    if raw['sensitivity'] not in {'NORMAL', 'SENSITIVE'}:
        raise ValueError('SECRET cannot enter telemetry')
    for key in ('event_id', 'task_id', 'run_id', *sorted(optional & raw.keys())):
        text(raw[key], 256)
    for key in ('occurred_at', 'recorded_at'):
        stamp = datetime.fromisoformat(text(raw[key], 40))
        if stamp.tzinfo is None:
            raise ValueError('Timestamp must include timezone')
    if datetime.fromisoformat(raw['recorded_at']) < datetime.fromisoformat(raw['occurred_at']):
        raise ValueError('Recorded time precedes occurrence')
    for key, length in (('trace_id', 32), ('span_id', 16)):
        if key in raw and (not re.fullmatch('[0-9a-f]{'+str(length)+'}', raw[key]) or int(raw[key], 16) == 0):
            raise ValueError('Invalid trace correlation')
    if 'span_id' in raw and 'trace_id' not in raw:
        raise ValueError('Span needs a trace')
    if raw.get('trace_id') in (raw['task_id'], raw['run_id']):
        raise ValueError('Logical and physical identities must be distinct')
    producer = fields(raw['producer'], {'kind', 'component'}, {'component_version', 'code_revision'})
    for value in producer.values():
        text(value, 128)
    refs = fields(raw['references'], set(), REF_KEYS)
    for key, value in refs.items():
        if key == 'artifact_ids':
            if not isinstance(value, list) or len(value) > 16:
                raise ValueError('Artifact reference limit')
            for ref in value:
                if not isinstance(ref, str) or not re.fullmatch(ARTIFACT, ref):
                    raise ValueError('Invalid artifact reference')
        else:
            text(value, 256)
    payload = fields(raw['payload'], set(), {'iteration', 'action', 'capability'})
    if 'iteration' in payload and (type(payload['iteration']) is not int or payload['iteration'] < 0):
        raise ValueError('Invalid iteration')
    if 'action' in payload and payload['action'] not in ACTIONS:
        raise ValueError('Unknown action metadata')
    if 'capability' in payload:
        from runtime.kernel.contracts import CAPABILITIES
        if payload['capability'] not in CAPABILITIES:
            raise ValueError('Unknown capability metadata')
    if not isinstance(raw['payload_refs'], list) or len(raw['payload_refs']) > 16:
        raise ValueError('Payload reference limit')
    for item in raw['payload_refs']:
        fields(item, {'ref', 'sensitivity'})
        if item['sensitivity'] not in {'NORMAL', 'SENSITIVE'}:
            raise ValueError('SECRET payload reference forbidden')
        if not isinstance(item['ref'], str) or not re.fullmatch(ARTIFACT, item['ref']):
            raise ValueError('Invalid payload reference')
        if not item['ref'].startswith('artifact://'+raw['task_id']+'/'):
            raise ValueError('Cross-Task payload reference')
    if len(encode(raw)) > 8192:
        raise ValueError('Event exceeds 8 KiB')
    return raw


def event_identity(run_id: str, step_id: str) -> str:
    return 'event-' + hashlib.sha256(encode([run_id, step_id])).hexdigest()


def make_event(*, task_id, run_id, step_id, event_type, outcome, producer,
               cause=None, references=None, payload=None, payload_refs=(), correlation=None):
    # Executed in a journaled step: these timestamps are retained before publish.
    # Occurrence means observation of the committed semantic result, not a span.
    now = datetime.now(timezone.utc).isoformat()
    event = dict(schema_version=1, event_id=event_identity(run_id, step_id),
        event_type=event_type, occurred_at=now, recorded_at=now, task_id=task_id,
        run_id=run_id, step_id=step_id, producer=producer, references=references or {},
        outcome=outcome, sensitivity='NORMAL', payload=payload or {},
        payload_refs=[{'ref':ref, 'sensitivity':'SENSITIVE'} for ref in payload_refs if ref])
    if cause:
        event['causation_event_id'] = cause
    event.update(correlation or {})
    return validate_event(event)


def safe_prepare(**kwargs):
    try:
        return make_event(**kwargs)
    except Exception:
        # Never copy a possibly sensitive failure message into diagnostics.
        return None


def safe_publish(publisher: ExecutionEventPublisher, event: dict | None) -> str:
    try:
        if event is None:
            return 'invalid_event'
        publisher.publish(validate_event(event))
        return 'published'
    except Exception:
        return 'publication_failed'
