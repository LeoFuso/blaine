"""Worker execution instrumentation: continuation boundaries, telemetry, control.

Two paths with deliberately different semantics live here.

The telemetry path is diagnostics. It carries no Task authority, must not decide
progression, and must never fail an otherwise valid Task. Every recorder call is
isolated; a failure increments a dropped counter instead of propagating.

The control path is synchronous. A registered observer runs before Blaine allows
the next model continuation, so its verdict can affect that continuation. It is
therefore never queued, batched or exported asynchronously.

A ContinuationBoundary is the point after prior model/tool activity has been
incorporated and before another model continuation begins. It is not a token
boundary, not necessarily a provider turn, and not automatically a supervisor
invocation. Adapters declare, per capability and per granularity, whether they
actually observe or control it; nothing here emulates a boundary a Worker lacks.
"""
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
import hashlib
import time
from typing import Protocol

from runtime.kernel.contracts import encode, identifier, text

# Capability vocabulary. Names describe what a Worker Adapter can actually do at
# the execution boundary, not a provider's internal terminology.
OBSERVE_CONTINUATION = 'continuation.observe'
ADMIT_CONTINUATION = 'continuation.admit'
STEER_CONTINUATION = 'continuation.steer'
INTERRUPT_EXECUTION = 'execution.interrupt'
OBSERVE_MODEL = 'model.observe'
OBSERVE_TOOL = 'tool.observe'
REBIND_MODEL = 'model.rebind'
REBIND_EFFORT = 'effort.rebind'
CAPABILITIES = {OBSERVE_CONTINUATION, ADMIT_CONTINUATION, STEER_CONTINUATION,
                INTERRUPT_EXECUTION, OBSERVE_MODEL, OBSERVE_TOOL, REBIND_MODEL, REBIND_EFFORT}

# Support is an evidence claim, never an aspiration. INFERRED must not be read as
# OBSERVED; UNSUPPORTED must not be compensated for by emulation.
SUPPORT = {'OBSERVED', 'INFERRED', 'UNSUPPORTED'}
# Granularity is the finest boundary at which the capability actually applies.
# 'worker_dispatch' means once per Worker execution, not per model continuation.
GRANULARITY = {'continuation', 'agent_turn', 'worker_dispatch'}
EVIDENCE = {'live', 'fixture', 'protocol', 'source', 'none'}
BOUNDARY_REASONS = {'session_start', 'model_result', 'tool_results', 'external_input'}


class UnsupportedCapability(Exception):
    """Raised when code would use a capability an adapter does not declare."""


@dataclass(frozen=True)
class CapabilityClaim:
    capability: str
    support: str
    granularity: str | None
    evidence: str
    note: str = ''

    def __post_init__(self):
        if self.capability not in CAPABILITIES or self.support not in SUPPORT or self.evidence not in EVIDENCE:
            raise ValueError('Unknown capability, support level or evidence class')
        if self.support == 'UNSUPPORTED':
            if self.granularity is not None:
                raise ValueError('An unsupported capability has no granularity')
        elif self.granularity not in GRANULARITY:
            raise ValueError('A supported capability must state its finest real granularity')
        if self.support != 'UNSUPPORTED' and self.evidence == 'none':
            raise ValueError('A supported capability requires an evidence class')
        if self.note:
            text(self.note, 256)


# Coarser-to-finer ordering. A claim at 'agent_turn' does not satisfy a request
# for 'continuation'; that distinction is the point of the capability model.
_FINENESS = {'worker_dispatch': 0, 'agent_turn': 1, 'continuation': 2}


@dataclass(frozen=True)
class AdapterProfile:
    adapter_id: str
    worker_family: str
    claims: tuple[CapabilityClaim, ...] = ()

    def __post_init__(self):
        identifier(self.adapter_id)
        text(self.worker_family, 128)
        if type(self.claims) is not tuple or len(self.claims) > len(CAPABILITIES):
            raise ValueError('Expected bounded immutable capability claims')
        if len({c.capability for c in self.claims}) != len(self.claims):
            raise ValueError('Duplicate capability claim')

    def claim(self, capability: str) -> CapabilityClaim | None:
        if capability not in CAPABILITIES:
            raise ValueError('Unknown capability')
        return next((c for c in self.claims if c.capability == capability), None)

    def supports(self, capability: str, granularity: str = 'continuation') -> bool:
        """True only for a declared, non-UNSUPPORTED claim at least this fine."""
        if granularity not in GRANULARITY:
            raise ValueError('Unknown granularity')
        found = self.claim(capability)
        return bool(found and found.support != 'UNSUPPORTED'
                    and _FINENESS[found.granularity] >= _FINENESS[granularity])

    def require(self, capability: str, granularity: str = 'continuation') -> CapabilityClaim:
        if not self.supports(capability, granularity):
            raise UnsupportedCapability(f'{self.adapter_id} does not provide {capability} at {granularity}')
        return self.claim(capability)

    def summary(self) -> dict:
        """Machine-readable capability evidence; no inferred value is promoted."""
        return {'version': 1, 'adapter_id': self.adapter_id, 'worker_family': self.worker_family,
                'capabilities': {c.capability: asdict(c) for c in sorted(self.claims, key=lambda c: c.capability)},
                'undeclared': sorted(CAPABILITIES - {c.capability for c in self.claims})}


@dataclass(frozen=True)
class ExecutionIdentity:
    """Correlation identity reusing the identifiers Blaine already owns.

    Levels absent from a given Worker stay None rather than being synthesized.
    """
    task_id: str
    run_id: str
    worker_dispatch_id: str | None = None
    worker_session_id: str | None = None
    agent_turn_id: str | None = None
    model_invocation_id: str | None = None
    capability_call_id: str | None = None

    def __post_init__(self):
        identifier(self.task_id)
        for value in (self.run_id, self.worker_dispatch_id, self.worker_session_id,
                      self.agent_turn_id, self.model_invocation_id, self.capability_call_id):
            if value is not None:
                text(value, 256)

    def attributes(self) -> dict:
        return {'blaine.' + key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class ContinuationBoundary:
    identity: ExecutionIdentity
    index: int
    reason: str
    model_invocations: int = 0
    tool_invocations: int = 0
    last_tool_outcome: str | None = None
    evidence_digest: str | None = None

    def __post_init__(self):
        if type(self.index) is not int or self.index < 0:
            raise ValueError('Boundary index must be a nonnegative integer')
        if self.reason not in BOUNDARY_REASONS:
            raise ValueError('Unknown boundary reason')
        for value in (self.model_invocations, self.tool_invocations):
            if type(value) is not int or value < 0:
                raise ValueError('Invalid boundary counter')
        if self.last_tool_outcome is not None:
            text(self.last_tool_outcome, 64)
        if self.evidence_digest is not None and len(self.evidence_digest) != 64:
            raise ValueError('Evidence digest must be a sha256 hex digest')

    def attributes(self) -> dict:
        return {**self.identity.attributes(), 'blaine.continuation.index': self.index,
                'blaine.continuation.reason': self.reason,
                'blaine.continuation.model_invocations': self.model_invocations,
                'blaine.continuation.tool_invocations': self.tool_invocations,
                **({'blaine.continuation.last_tool_outcome': self.last_tool_outcome}
                   if self.last_tool_outcome else {}),
                **({'blaine.continuation.evidence_digest': self.evidence_digest}
                   if self.evidence_digest else {})}

    def payload(self) -> dict:
        """Journal-safe record using raw field names, so it round-trips exactly."""
        return asdict(self)


def evidence_digest(artifacts: dict) -> str:
    """Stable fingerprint of admitted evidence, so progress is observable without content."""
    return hashlib.sha256(encode(sorted((artifacts or {}).items()))).hexdigest()


# ---------------------------------------------------------------- telemetry path

SPAN_KINDS = {'worker_session', 'agent_turn', 'model_invocation', 'tool_execution',
              'verifier', 'boundary_control'}


def span_name(kind: str, attributes: dict) -> str:
    """OpenTelemetry GenAI `<operation> <target>`, or an explicit Blaine name.

    Every backend derives the same name from the same attributes, so a span is not
    named differently depending on which recorder a deployment selected.
    """
    operation = attributes.get(GEN_AI_OPERATION)
    target = attributes.get(GEN_AI_REQUEST_MODEL) or attributes.get(GEN_AI_TOOL_NAME)
    return f'{operation} {target}' if operation and target else 'blaine.' + kind


class Span(Protocol):
    def set(self, **attributes) -> None: ...
    def fail(self, reason: str) -> None: ...


class Recorder(Protocol):
    """Backend-independent emission seam. No vendor type crosses this boundary."""
    def span(self, name: str, *, kind: str, attributes: dict): ...
    def event(self, name: str, *, attributes: dict) -> None: ...
    def count(self, name: str, value: int = 1, attributes: dict | None = None) -> None: ...


class _NullSpan:
    def set(self, **attributes): pass
    def fail(self, reason): pass


_NULL_SPAN = _NullSpan()


class NullRecorder:
    """Default. Instrumentation off means no allocation and no observable work."""
    dropped_total = 0

    @contextmanager
    def span(self, name, *, kind, attributes):
        yield _NULL_SPAN

    def event(self, name, *, attributes): pass

    def count(self, name, value=1, attributes=None): pass


class MemoryRecorder:
    """Ordered in-process records for tests and acceptance evidence only."""
    def __init__(self):
        self.records: list[dict] = []
        self.counters: dict[str, int] = {}
        self.dropped_total = 0
        self._stack: list[str] = []

    class _Span:
        def __init__(self, record):
            self.record = record

        def set(self, **attributes):
            self.record['attributes'].update(attributes)

        def fail(self, reason):
            self.record['status'] = 'error'
            self.record['error'] = reason

    @contextmanager
    def span(self, name, *, kind, attributes):
        if kind not in SPAN_KINDS:
            raise ValueError('Unknown span kind')
        name = name or span_name(kind, attributes)
        record = {'type': 'span', 'name': name, 'kind': kind, 'parent': self._stack[-1] if self._stack else None,
                  'attributes': dict(attributes), 'status': 'ok', 'order': len(self.records)}
        self.records.append(record)
        self._stack.append(name)
        try:
            yield self._Span(record)
        except Exception as error:
            record['status'] = 'error'
            record['error'] = type(error).__name__
            raise
        finally:
            self._stack.pop()
            record['closed_at_order'] = len(self.records)

    def event(self, name, *, attributes):
        self.records.append({'type': 'event', 'name': name, 'parent': self._stack[-1] if self._stack else None,
                             'attributes': dict(attributes), 'order': len(self.records)})

    def count(self, name, value=1, attributes=None):
        self.counters[name] = self.counters.get(name, 0) + value


class SafeRecorder:
    """Telemetry can never fail Worker execution; failures become a dropped count."""
    def __init__(self, recorder: Recorder):
        self.recorder = recorder
        self.dropped_total = 0

    def _drop(self):
        self.dropped_total += 1
        try:
            self.recorder.count('blaine.telemetry.dropped')
        except Exception:
            pass  # a broken counter must not become a second failure

    @contextmanager
    def span(self, name, *, kind, attributes):
        try:
            manager = self.recorder.span(name, kind=kind, attributes=attributes)
            entered = manager.__enter__()
        except Exception:
            self._drop()
            yield _NULL_SPAN
            return
        try:
            yield _SafeSpan(entered, self)
        except Exception as error:
            try:
                if manager.__exit__(type(error), error, error.__traceback__):
                    return
            except Exception:
                self._drop()
            raise
        else:
            try:
                manager.__exit__(None, None, None)
            except Exception:
                self._drop()

    def event(self, name, *, attributes):
        try:
            self.recorder.event(name, attributes=attributes)
        except Exception:
            self._drop()

    def count(self, name, value=1, attributes=None):
        try:
            self.recorder.count(name, value, attributes)
        except Exception:
            self.dropped_total += 1


class _SafeSpan:
    def __init__(self, span, owner):
        self.span, self.owner = span, owner

    def set(self, **attributes):
        try:
            self.span.set(**attributes)
        except Exception:
            self.owner._drop()

    def fail(self, reason):
        try:
            self.span.fail(reason)
        except Exception:
            self.owner._drop()


# ----------------------------------------------------------------- control path

CONTROL_OUTCOMES = {'PROCEED', 'ABSTAIN'}
CONTROL_POLICIES = {'PROCEED_ON_ERROR', 'FAIL_ON_ERROR'}


class ControlPathError(Exception):
    """A control-path failure under FAIL_ON_ERROR. Never silently discarded."""


class BoundaryObserver(Protocol):
    observer_id: str

    def inspect(self, boundary: ContinuationBoundary) -> dict:
        """Return a bounded assessment. It cannot authorize any Worker action."""


class NoopObserver:
    """Default synchronous participant: proves the hook without semantic cost."""
    observer_id = 'noop'

    def inspect(self, boundary):
        return {'outcome': 'PROCEED'}


def validate_assessment(raw: dict, observer_id: str) -> dict:
    value = fields_assessment(raw)
    if value['outcome'] not in CONTROL_OUTCOMES:
        raise ValueError('Unknown control outcome')
    return {'observer_id': observer_id, **value}


def fields_assessment(raw: dict) -> dict:
    """Closed assessment metadata. No prompt, response or free provider payload."""
    if not isinstance(raw, dict):
        raise ValueError('Expected an assessment object')
    allowed = {'outcome', 'label', 'score', 'detail', 'latency_ms', 'input_tokens', 'output_tokens', 'model'}
    unknown = set(raw) - allowed
    if unknown or 'outcome' not in raw:
        raise ValueError('Unknown or missing assessment fields')
    value = {'outcome': raw['outcome']}
    for key in ('label', 'detail', 'model'):
        if raw.get(key) is not None:
            value[key] = text(raw[key], 256)
    if raw.get('score') is not None:
        score = raw['score']
        if type(score) not in (int, float) or not 0.0 <= float(score) <= 1.0:
            raise ValueError('Score must be a probability')
        value['score'] = float(score)
    for key in ('latency_ms', 'input_tokens', 'output_tokens'):
        if raw.get(key) is not None:
            if type(raw[key]) is not int or raw[key] < 0:
                raise ValueError('Invalid observation counter')
            value[key] = raw[key]
    return value


@dataclass
class ControlPath:
    """Synchronous boundary admission. Observers run before the next continuation.

    This increment admits PROCEED/ABSTAIN only. An intervention that changes
    execution semantics would additionally require a declared capability and a
    durable admission record, which is deliberately not introduced here.
    """
    observers: Sequence[BoundaryObserver] = ()
    policy: str = 'PROCEED_ON_ERROR'
    budget_ms: int = 2000
    recorder: Recorder = field(default_factory=NullRecorder)

    def __post_init__(self):
        if self.policy not in CONTROL_POLICIES:
            raise ValueError('Unknown control failure policy')
        if type(self.budget_ms) is not int or not 0 < self.budget_ms <= 60000:
            raise ValueError('Control budget must be a bounded positive millisecond value')
        if len(self.observers) > 4:
            raise ValueError('Expected a bounded observer set')
        for observer in self.observers:
            identifier(observer.observer_id)
        self._poisoned: set[str] = set()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='blaine-control') if self.observers else None

    def close(self):
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)

    def admit(self, boundary: ContinuationBoundary) -> dict:
        """Run every observer synchronously, then report an explicit admission."""
        assessments, failures = [], []
        self.recorder.event('blaine.continuation.boundary', attributes=boundary.attributes())
        for observer in self.observers:
            identity = observer.observer_id
            if identity in self._poisoned:
                failures.append({'observer_id': identity, 'failure': 'skipped_poisoned'})
                continue
            started = time.monotonic()
            with self.recorder.span('boundary_control ' + identity, kind='boundary_control',
                                    attributes={**boundary.attributes(), 'blaine.control.observer_id': identity}) as span:
                try:
                    future = self._pool.submit(observer.inspect, boundary)
                    assessment = validate_assessment(future.result(timeout=self.budget_ms / 1000), identity)
                except FutureTimeout:
                    # The abandoned call keeps the single worker thread, so this
                    # observer is not consulted again in this control path.
                    self._poisoned.add(identity)
                    failures.append({'observer_id': identity, 'failure': 'budget_exceeded'})
                    span.fail('budget_exceeded')
                    continue
                except Exception as error:
                    failures.append({'observer_id': identity, 'failure': 'observer_error',
                                     'error_type': type(error).__name__})
                    span.fail('observer_error')
                    continue
                assessment['latency_ms'] = assessment.get('latency_ms', int((time.monotonic() - started) * 1000))
                span.set(**{'blaine.control.outcome': assessment['outcome']})
                assessments.append(assessment)
        record = {'version': 1, 'boundary': boundary.payload(), 'policy': self.policy,
                  'assessments': assessments, 'failures': failures,
                  'outcome': 'PROCEED', 'admitted_intervention': None}
        if failures:
            # A control-path failure is always reported, whichever policy applies.
            self.recorder.event('blaine.control.failed', attributes={
                **boundary.attributes(), 'blaine.control.failures': len(failures),
                'blaine.control.policy': self.policy})
            if self.policy == 'FAIL_ON_ERROR':
                raise ControlPathError('Control observer failed under FAIL_ON_ERROR')
        return record


# ------------------------------------------- OpenTelemetry GenAI attribute names
# Plain strings from the OpenTelemetry GenAI semantic conventions. Using the
# standard names here avoids inventing Blaine equivalents while keeping the
# kernel free of any OpenTelemetry import or backend dependency.
GEN_AI_OPERATION = 'gen_ai.operation.name'
GEN_AI_PROVIDER = 'gen_ai.provider.name'
GEN_AI_REQUEST_MODEL = 'gen_ai.request.model'
GEN_AI_RESPONSE_MODEL = 'gen_ai.response.model'
GEN_AI_RESPONSE_ID = 'gen_ai.response.id'
GEN_AI_RESPONSE_FINISH_REASONS = 'gen_ai.response.finish_reasons'
GEN_AI_USAGE_INPUT = 'gen_ai.usage.input_tokens'
GEN_AI_USAGE_OUTPUT = 'gen_ai.usage.output_tokens'
GEN_AI_USAGE_CACHE_READ = 'gen_ai.usage.cache_read.input_tokens'
GEN_AI_USAGE_CACHE_WRITE = 'gen_ai.usage.cache_creation.input_tokens'
GEN_AI_AGENT_ID = 'gen_ai.agent.id'
GEN_AI_CONVERSATION_ID = 'gen_ai.conversation.id'
GEN_AI_TOOL_NAME = 'gen_ai.tool.name'
GEN_AI_TOOL_TYPE = 'gen_ai.tool.type'
GEN_AI_TOOL_CALL_ID = 'gen_ai.tool.call.id'
# Reasoning effort has no stable GenAI attribute yet, so it stays explicitly
# Blaine-namespaced rather than pretending to be a standardized key.
BLAINE_REASONING_EFFORT = 'blaine.model.reasoning_effort'
BLAINE_OUTPUT_DIGEST = 'blaine.model.output_sha256'


def model_attributes(*, provider, request_model, response_model=None, response_id=None,
                     finish_reason=None, usage=None, reasoning_effort=None, output_digest=None) -> dict:
    """Metadata only. Prompts and completions are never attributes by default."""
    usage = usage or {}
    attributes = {GEN_AI_OPERATION: 'chat', GEN_AI_PROVIDER: text(provider, 128),
                  GEN_AI_REQUEST_MODEL: text(request_model, 128)}
    for key, value in ((GEN_AI_RESPONSE_MODEL, response_model), (GEN_AI_RESPONSE_ID, response_id),
                       (BLAINE_REASONING_EFFORT, reasoning_effort), (BLAINE_OUTPUT_DIGEST, output_digest)):
        if value is not None:
            attributes[key] = text(value, 128)
    if finish_reason is not None:
        attributes[GEN_AI_RESPONSE_FINISH_REASONS] = (text(finish_reason, 64),)
    for key, name in ((GEN_AI_USAGE_INPUT, 'input_tokens'), (GEN_AI_USAGE_OUTPUT, 'output_tokens'),
                      (GEN_AI_USAGE_CACHE_READ, 'cached_input_tokens'),
                      (GEN_AI_USAGE_CACHE_WRITE, 'cache_write_input_tokens')):
        value = usage.get(name)
        if value is not None:
            if type(value) is not int or value < 0:
                raise ValueError('Invalid token usage observation')
            attributes[key] = value
    return attributes


def tool_attributes(*, name, call_id=None, tool_type='function', outcome=None, exit_code=None) -> dict:
    attributes = {GEN_AI_OPERATION: 'execute_tool', GEN_AI_TOOL_NAME: text(name, 128),
                  GEN_AI_TOOL_TYPE: text(tool_type, 64)}
    if call_id is not None:
        attributes[GEN_AI_TOOL_CALL_ID] = text(call_id, 256)
    if outcome is not None:
        attributes['blaine.tool.outcome'] = text(outcome, 64)
    if exit_code is not None:
        if type(exit_code) is not int:
            raise ValueError('Invalid tool exit code')
        attributes['blaine.tool.exit_code'] = exit_code
    return attributes


@dataclass(frozen=True)
class Instrumentation:
    """One deployment-selected bundle passed through the kernel by reference.

    `enabled` is false for the default, so an uninstrumented deployment adds no
    journal entry, no span and no observable work to Worker execution.
    """
    recorder: Recorder = field(default_factory=NullRecorder)
    control: ControlPath | None = None
    profile: AdapterProfile | None = None

    @property
    def enabled(self) -> bool:
        return not isinstance(self.recorder, NullRecorder) or self.control is not None

    def admit(self, *, payload: dict) -> dict:
        """Journaled boundary admission; recovery replays this exact record.

        Telemetry failures are contained. Only a deliberate FAIL_ON_ERROR control
        policy is allowed to surface, because that is an execution decision.
        """
        boundary = ContinuationBoundary(identity=ExecutionIdentity(**payload['identity']),
                                        **{k: v for k, v in payload.items() if k != 'identity'})
        if self.control is not None:
            return self.control.admit(boundary)
        self.recorder.event('blaine.continuation.boundary', attributes=boundary.attributes())
        return {'version': 1, 'boundary': boundary.payload(), 'policy': None,
                'assessments': [], 'failures': [], 'outcome': 'PROCEED', 'admitted_intervention': None}


def safe(recorder: Recorder | None) -> Recorder:
    if recorder is None or isinstance(recorder, (NullRecorder, SafeRecorder)):
        return recorder or NullRecorder()
    return SafeRecorder(recorder)
