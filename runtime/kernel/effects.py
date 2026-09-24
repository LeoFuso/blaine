"""E2.0 provider-independent target effects.

A target effect is never "the tool said success". The kernel admits an intent
(PolicyGate), lowers it deterministically into an EffectRequest whose identity is
the existing capability ``operation_id`` plus the request digest, dispatches it to
a deployment-injected TargetProvider, and admits only a validated EffectReceipt.
A lost response, an unreachable provider or an unconfirmed cancellation yields an
explicit ``uncertain`` outcome, which is reconciled from the provider's receipt
for that operation, never by blind redispatch and never from a matching hash alone.

Semantic operations only (``workspace.write`` / ``workspace.exec``); mapping them
onto a real provider (IntelliJ MCP) belongs to the E2.A/E2.B adapter.
See docs/contracts/target-effects.md.
"""
from dataclasses import dataclass
import hashlib
import math
from pathlib import PurePosixPath
import re
from typing import Protocol

from runtime.kernel.contracts import encode, fields, identifier, message, text, unpack
from runtime.kernel.journal import ref

WRITE, EXEC = 'workspace.write', 'workspace.exec'
OPERATIONS = {WRITE: 'write_file', EXEC: 'run_profile'}
MAX_WRITE_BYTES = 65536
MAX_ARGS = 16
MAX_OUTPUT_BYTES = 1048576
DEFAULT_POLL_SECONDS = 1.0
WRITE_STATES = ('applied', 'conflict', 'rejected')
EXEC_STATES = ('running', 'completed', 'timed_out', 'canceled', 'rejected', 'not_started')
TERMINAL_STATES = ('applied', 'conflict', 'rejected', 'completed', 'timed_out', 'canceled', 'not_started')
# Reconciliation of an uncertain effect. Only the provider's receipt for this
# operation establishes APPLIED; a matching target hash alone does not.
APPLIED, NOT_APPLIED, DIFFERENT_STATE, STILL_UNKNOWN = 'APPLIED', 'NOT_APPLIED', 'DIFFERENT_STATE', 'STILL_UNKNOWN'
RECONCILED = (APPLIED, NOT_APPLIED, DIFFERENT_STATE, STILL_UNKNOWN)
DIGEST = r'[0-9a-f]{64}'


class ProviderUnavailable(Exception):
    """The provider could not be reached; the request was not delivered by this call."""


class ResponseLost(Exception):
    """The request may have been delivered; its outcome is unknown to the caller."""


class TargetProvider(Protocol):
    """Hub-side provider boundary (future: IntelliJ MCP via the capability relay).

    Obligations a provider must meet to be admitted for effects:
    - ``dispatch`` is idempotent per ``operation_id`` + request digest: a repeat
      returns the existing receipt and never re-executes; a different request
      under the same identity is rejected.
    - A write atomically checks its precondition and commits (compare-and-swap).
    - ``query`` answers from a durable receipt store; ``authoritative`` absence
      means the provider guarantees it never executed that operation.
    """
    provider_id: str

    def read(self, workspace_id: str, path: str) -> dict: ...
    def dispatch(self, request: dict, payload: dict) -> dict: ...
    def query(self, operation_id: str, request_digest: str) -> dict: ...
    def observe(self, workspace_id: str, path: str) -> dict: ...
    def cancel(self, operation_id: str, request_digest: str, reason: str) -> dict: ...


@dataclass(frozen=True)
class ExecProfile:
    """A reviewed command profile: exact executable and fixed args, never shell text."""
    id: str
    executable: str
    args: tuple[str, ...]
    allowed_args: tuple[str, ...] = ()
    timeout_seconds: float = 120.0
    poll_seconds: float = DEFAULT_POLL_SECONDS
    output_cap_bytes: int = MAX_OUTPUT_BYTES
    environment: str = 'minimal'

    def payload(self) -> dict:
        return {'id': identifier(self.id), 'executable': text(self.executable, 512), 'args': list(self.args),
                'allowed_args': list(self.allowed_args), 'timeout_seconds': self.timeout_seconds,
                'poll_seconds': self.poll_seconds, 'output_cap_bytes': self.output_cap_bytes,
                'environment': self.environment}


def validate_profile(value: object) -> dict:
    profile = fields(value, {'id', 'executable', 'args', 'allowed_args', 'timeout_seconds', 'poll_seconds',
                             'output_cap_bytes', 'environment'})
    identifier(profile['id'])
    text(profile['executable'], 512)
    if any(token in profile['executable'] for token in (' ', ';', '|', '&', '$', '`')):
        raise ValueError('A profile names an exact executable, not shell text')
    for key in ('args', 'allowed_args'):
        if not isinstance(profile[key], list) or len(profile[key]) > MAX_ARGS:
            raise ValueError('Expected bounded profile arguments')
        for token in profile[key]:
            text(token, 256)
    for key in ('timeout_seconds', 'poll_seconds'):
        if not isinstance(profile[key], (int, float)) or not 0 < profile[key] <= 3600:
            raise ValueError('Invalid profile bound')
    if type(profile['output_cap_bytes']) is not int or not 0 < profile['output_cap_bytes'] <= MAX_OUTPUT_BYTES:
        raise ValueError('Invalid output cap')
    if profile['environment'] != 'minimal':
        raise ValueError('Only the minimal environment policy exists')
    return profile


def profile_digest(profile: dict) -> str:
    return 'sha256:' + hashlib.sha256(encode(validate_profile(profile))).hexdigest()


def max_polls(profile: dict) -> int:
    return max(1, math.ceil(profile['timeout_seconds'] / profile['poll_seconds']))


def confined(path: object) -> str:
    """Workspace-relative POSIX path: no absolute, parent, NUL, URL or backslash."""
    text(path, 512)
    candidate = PurePosixPath(path)
    if (candidate.is_absolute() or '..' in candidate.parts or candidate == PurePosixPath('.')
            or '\\' in path or '\x00' in path or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:', path)):
        raise ValueError('Expected a confined workspace-relative path')
    return path


def validate_read_input(value: dict) -> dict:
    fields(value, {'form', 'workspace_id', 'path', 'artifact'})
    if value['form'] != 'file':
        raise ValueError('Unsupported workspace.read form')
    identifier(value['workspace_id'])
    confined(value['path'])
    identifier(value['artifact'])
    return value


def validate_write_input(value: dict) -> dict:
    fields(value, {'workspace_id', 'path', 'precondition', 'content_ref'})
    identifier(value['workspace_id'])
    confined(value['path'])
    ref(value['content_ref'])
    precondition = value['precondition']
    if not isinstance(precondition, dict) or len(precondition) != 1:
        raise ValueError('A write names exactly one precondition')
    kind, expected = next(iter(precondition.items()))
    if kind == 'absent':
        if expected is not True:
            raise ValueError('absent precondition must be true')
    elif kind == 'sha256':
        if not isinstance(expected, str) or not re.fullmatch(DIGEST, expected):
            raise ValueError('Expected exact SHA-256 precondition')
    elif kind == 'receipt':
        ref(expected)
    else:
        raise ValueError('Precondition must be absent, sha256 or an admitted read receipt')
    return value


def validate_exec_input(value: dict) -> dict:
    fields(value, {'workspace_id', 'profile'}, {'args'})
    identifier(value['workspace_id'])
    identifier(value['profile'])
    args = value.get('args', [])
    if not isinstance(args, list) or len(args) > MAX_ARGS:
        raise ValueError('Expected bounded structured arguments')
    for token in args:
        text(token, 256)
    return value


def admit_exec(value: dict, authority: dict) -> dict:
    """PolicyGate check for a profile: pinned in authority, arguments allowlisted."""
    profile = (authority.get('profiles') or {}).get(value['profile'])
    if profile is None:
        raise ValueError('Command profile is not in effective authority')
    if not set(value.get('args', [])) <= set(profile['allowed_args']):
        raise ValueError('Arguments outside the reviewed profile')
    return profile


def read_receipt_precondition(receipt: dict, value: dict) -> str:
    if (receipt.get('workspace_id') != value['workspace_id'] or receipt['source']['path'] != value['path']
            or receipt.get('truncated') or receipt.get('state') != 'SUCCESS'):
        raise ValueError('Precondition receipt is not a whole-file read of this target')
    return receipt['response_sha256']


def lower(task_id: str, operation_id: str, capability: str, value: dict, state: dict, store,
          authority_ref: str, authority: dict, receipts: set[str]) -> dict:
    """Deterministic EffectRequest. The worker proposes; this code decides the effect."""
    base = {'task_id': task_id, 'operation_id': operation_id, 'operation_class': capability,
            'operation': OPERATIONS[capability], 'workspace_id': value['workspace_id'],
            'authority_ref': authority_ref, 'contract_revision': state['contract_revision']}
    if capability == WRITE:
        if value['content_ref'] not in state['artifacts'].values():
            raise ValueError('Write content must be an admitted Task artifact')
        content = store.read(task_id, value['content_ref'])
        if len(content) > MAX_WRITE_BYTES:
            raise ValueError('Write exceeds the size cap')
        content.decode('utf-8')
        kind, expected = next(iter(value['precondition'].items()))
        evidence = None
        if kind == 'receipt':
            if expected not in receipts:
                raise ValueError('Precondition receipt was not admitted by this Task')
            evidence = expected
            expected = read_receipt_precondition(unpack(store.read_json(task_id, expected), 'WorkspaceReadReceipt'), value)
            kind = 'sha256'
        return message('EffectRequest', {**base, 'path': value['path'],
            'precondition': {'absent': True} if kind == 'absent' else {'sha256': expected},
            'precondition_evidence': evidence, 'content_ref': value['content_ref'],
            'content_sha256': hashlib.sha256(content).hexdigest(), 'content_bytes': len(content)})
    profile = admit_exec(value, authority)
    return message('EffectRequest', {**base, 'profile': {'id': profile['id'], 'digest': profile_digest(profile)},
        'command': {'executable': profile['executable'], 'args': [*profile['args'], *value.get('args', [])]},
        'timeout_seconds': profile['timeout_seconds'], 'poll_seconds': profile['poll_seconds'],
        'output_cap_bytes': profile['output_cap_bytes'], 'environment': profile['environment']})


def request_digest(request: dict) -> str:
    return 'sha256:' + hashlib.sha256(encode(request)).hexdigest()


def validate_receipt(raw: object, request: dict, store) -> dict:
    """Admit a provider receipt only if it answers this exact request consistently."""
    payload = request['payload']
    receipt = fields(unpack(raw, 'EffectReceipt'), {'task_id', 'operation_id', 'request_digest', 'provider',
                                                    'operation_class', 'state'}, {'write', 'exec', 'detail'})
    if (receipt['task_id'] != payload['task_id'] or receipt['operation_id'] != payload['operation_id']
            or receipt['request_digest'] != request_digest(request)
            or receipt['operation_class'] != payload['operation_class']):
        raise ValueError('Receipt does not answer this effect request')
    if 'detail' in receipt:
        text(receipt['detail'], 512)
    if payload['operation_class'] == WRITE:
        if receipt['state'] not in WRITE_STATES:
            raise ValueError('Invalid write receipt state')
        write = fields(receipt.get('write'), {'workspace_id', 'path', 'before'}, {'after', 'readback_sha256'})
        if (write['workspace_id'], write['path']) != (payload['workspace_id'], payload['path']):
            raise ValueError('Write receipt names another target')
        expected = payload['precondition']
        if receipt['state'] == 'applied':
            if (write['before'] != expected or write.get('after') != {'sha256': payload['content_sha256']}
                    or write.get('readback_sha256') != payload['content_sha256']):
                raise ValueError('Applied receipt contradicts its precondition, content or readback')
        elif receipt['state'] == 'conflict':
            if write['before'] == expected or 'after' in write:
                raise ValueError('A conflict must show a different current state and no write')
        return receipt
    if receipt['state'] not in EXEC_STATES:
        raise ValueError('Invalid exec receipt state')
    exec_ = fields(receipt.get('exec'), {'started', 'cleanup'},
                   {'exit_code', 'signal', 'output', 'output_ref', 'output_sha256', 'output_bytes',
                    'truncated', 'merged', 'result'})
    if exec_['cleanup'] not in ('confirmed', 'unknown', 'running', 'not_applicable'):
        raise ValueError('Invalid cleanup state')
    if receipt['state'] == 'completed' and type(exec_.get('exit_code')) is not int and 'signal' not in exec_:
        raise ValueError('A completed process reports an exit code or signal')
    if receipt['state'] in ('not_started', 'rejected') and exec_['started']:
        raise ValueError('An unstarted process cannot have started')
    if 'output' in exec_:
        output = exec_['output']
        if not isinstance(output, str) or len(output.encode()) > payload['output_cap_bytes']:
            raise ValueError('Output exceeds its cap')
    if 'result' in exec_:
        result = exec_['result']
        if not isinstance(result, dict) or len(result) > 16 or any(
                not isinstance(v, (int, str, bool)) or isinstance(v, str) and len(v) > 256 for v in result.values()):
            raise ValueError('Structured result must be a small flat object')
    return receipt


def normalize(receipt: dict, store, task_id: str) -> dict:
    """Move bulky output into the artifact store; the journal holds references only."""
    if 'exec' in receipt and 'output' in receipt['exec']:
        exec_ = dict(receipt['exec'])
        data = exec_.pop('output').encode('utf-8')
        exec_.update(output_ref=store.put(task_id, data), output_sha256=hashlib.sha256(data).hexdigest(),
                     output_bytes=len(data), merged=exec_.get('merged', True))
        receipt = {**receipt, 'exec': exec_}
    return message('EffectReceipt', receipt)


def outcome(kind: str, **payload) -> dict:
    return message('EffectOutcome', {'kind': kind, **payload})


def attempt(provider: TargetProvider | None, request: dict, payload: dict, store) -> dict:
    """The journaled dispatch step. Idempotent across Restate retries.

    It first asks the provider for an existing receipt of this operation, so a
    retry after a crash between commit and journaling recovers the receipt instead
    of executing again. Only authoritative absence permits dispatch.
    """
    task_id = request['payload']['task_id']
    if provider is None:
        return outcome('not_dispatched', reason='No target provider is deployed')
    digest = request_digest(request)
    try:
        found = provider.query(request['payload']['operation_id'], digest)
        if found.get('found'):
            return outcome('receipt', delivery='recovered',
                           receipt=normalize(validate_receipt(found['receipt'], request, store), store, task_id))
        if not found.get('authoritative'):
            return outcome('uncertain', reason='Provider cannot say whether this operation ran')
        raw = provider.dispatch(request, payload)
        return outcome('receipt', delivery='dispatched',
                       receipt=normalize(validate_receipt(raw, request, store), store, task_id))
    except ResponseLost as error:
        return outcome('uncertain', reason=f'Response lost after dispatch: {error}'[:512])
    except ProviderUnavailable as error:
        return outcome('uncertain', reason=f'Provider unavailable: {error}'[:512])
    except (ValueError, TypeError, KeyError) as error:
        return outcome('uncertain', reason=f'Provider answer rejected: {error}'[:512])


def poll(provider: TargetProvider, request: dict, store) -> dict:
    task_id = request['payload']['task_id']
    try:
        found = provider.query(request['payload']['operation_id'], request_digest(request))
    except ProviderUnavailable as error:
        return outcome('uncertain', reason=f'Provider unavailable: {error}'[:512])
    if not found.get('found'):
        return outcome('uncertain', reason='Provider lost track of a running operation')
    try:
        return outcome('receipt', delivery='polled',
                       receipt=normalize(validate_receipt(found['receipt'], request, store), store, task_id))
    except (ValueError, TypeError, KeyError) as error:
        return outcome('uncertain', reason=f'Provider answer rejected: {error}'[:512])


CANCEL_REASONS = ('requested', 'timeout')


def cancel(provider: TargetProvider, request: dict, store, reason: str) -> dict:
    """Stop a running operation. CANCELED never means "did not happen" unless proven.

    Outcomes: the provider confirms it stopped (a receipt ``canceled``/``timed_out``
    with ``started`` and ``cleanup`` stated), it completed first (its completion
    receipt wins), or the cancellation could not be confirmed (``uncertain``).
    """
    task_id = request['payload']['task_id']
    try:
        if reason not in CANCEL_REASONS:
            raise ValueError('Unknown cancellation reason')
        answer = provider.cancel(request['payload']['operation_id'], request_digest(request), reason)
        receipt = normalize(validate_receipt(answer['receipt'], request, store), store, task_id)
    except (ProviderUnavailable, ResponseLost) as error:
        return outcome('uncertain', reason=f'{reason}; stop not confirmed: {error}'[:512])
    except (ValueError, TypeError, KeyError) as error:
        return outcome('uncertain', reason=f'{reason}; provider answer rejected: {error}'[:512])
    state = receipt['payload']['state']
    if state == 'running':
        return outcome('uncertain', reason=f'{reason}; provider still reports the process running')
    return outcome('receipt', delivery='completed_first' if state == 'completed' else 'stopped', receipt=receipt)


def reconcile(provider: TargetProvider | None, request: dict, store) -> dict:
    """Decide what an uncertain effect did, from deterministic provider evidence only."""
    payload = request['payload']
    task_id = payload['task_id']
    if provider is None:
        return message('EffectReconciliation', {'state': STILL_UNKNOWN, 'detail': 'No target provider is deployed'})
    try:
        found = provider.query(payload['operation_id'], request_digest(request))
        if found.get('found'):
            receipt = normalize(validate_receipt(found['receipt'], request, store), store, task_id)
            if receipt['payload']['state'] == 'running':
                return message('EffectReconciliation', {'state': STILL_UNKNOWN,
                    'detail': 'The process was started and its end is not yet confirmed'})
            return message('EffectReconciliation', {'state': APPLIED, 'receipt': receipt,
                'detail': f"Provider receipt for this operation: {receipt['payload']['state']}"})
        if found.get('authoritative'):
            return message('EffectReconciliation', {'state': NOT_APPLIED,
                'detail': 'Provider states authoritatively that this operation never ran'})
        if payload['operation_class'] == WRITE:
            current = provider.observe(payload['workspace_id'], payload['path'])
            observed = {'absent': True} if not current.get('exists') else {'sha256': current['sha256']}
            if observed not in (payload['precondition'], {'sha256': payload['content_sha256']}):
                return message('EffectReconciliation', {'state': DIFFERENT_STATE, 'observation': observed,
                    'detail': 'Target matches neither the precondition nor the intended content'})
            return message('EffectReconciliation', {'state': STILL_UNKNOWN, 'observation': observed,
                'detail': 'No receipt; the target state alone cannot attribute the write'})
        return message('EffectReconciliation', {'state': STILL_UNKNOWN, 'detail': 'No receipt for this process'})
    except (ProviderUnavailable, ResponseLost) as error:
        return message('EffectReconciliation', {'state': STILL_UNKNOWN, 'detail': f'Provider unavailable: {error}'[:512]})
    except (ValueError, TypeError, KeyError) as error:
        return message('EffectReconciliation', {'state': STILL_UNKNOWN, 'detail': f'Provider answer rejected: {error}'[:512]})


def read(provider: TargetProvider | None, task_id: str, operation_id: str, value: dict, store) -> dict:
    """TARGET_READ through the provider: content as an artifact plus a read receipt."""
    if provider is None:
        raise ValueError('No target provider is deployed')
    try:
        answer = provider.read(value['workspace_id'], value['path'])
    except (ProviderUnavailable, ResponseLost) as error:
        raise ValueError(f'Read unavailable: {error}') from error
    if not answer.get('exists'):
        raise ValueError('Target file does not exist')
    content = text(answer['content'], MAX_WRITE_BYTES) if answer['content'] else ''
    data = content.encode('utf-8')
    content_ref = store.put(task_id, data)
    lines = content.split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    receipt = message('WorkspaceReadReceipt', {'task_id': task_id, 'operation_id': operation_id,
        'request_sha256': hashlib.sha256(encode(value)).hexdigest(), 'workspace_id': value['workspace_id'],
        'provider': {'kind': provider.provider_id}, 'operation': 'read_file', 'state': 'SUCCESS',
        'source': {'view': 'provider_file', 'class': 'project', 'path': value['path'], 'lines': [1, max(len(lines), 1)]},
        'response_ref': content_ref, 'response_sha256': hashlib.sha256(data).hexdigest(),
        'response_bytes': len(data), 'truncated': False})
    return {'content_ref': content_ref, 'receipt_ref': store.put_json(task_id, receipt), 'content': content}


def approval_request(task_id: str, request_id: str, request: dict) -> dict:
    """A deterministic HumanDecisionRequest for one effect, through the existing boundary."""
    payload = request['payload']
    target = payload.get('path') or payload.get('profile', {}).get('id')
    return message('HumanDecisionRequest', {'task_id': task_id, 'origin_task_id': task_id, 'request_id': request_id,
        'revision': 0, 'question': (f"Approve {payload['operation_class']} {target} in {payload['workspace_id']} "
                                    f"(operation {payload['operation_id']}, request {request_digest(request)[7:23]})?"),
        'allowed_responses': ['APPROVE', 'DENY']})
