"""CP.2 local governed Memory facade. No worker-selected authority or backend.

Storage is injected by the trusted application. BoundContext is produced by the
existing Context Plane authority, never deserialized from a worker request.
"""
from dataclasses import dataclass
import hashlib

from runtime.kernel.context_plane import ContextError, MemoryFacade, SOURCE_BYTES, digest
from runtime.kernel.contracts import encode, fields, text


class MemoryError(ContextError):
    pass


def validate_write(value):
    """Only source text and a bounded retry token cross the worker boundary."""
    try:
        fields(value, {'content', 'idempotency_key'})
        text(value['content'], 4096)
        text(value['idempotency_key'], 80)
        if len(value['content'].encode()) > 4096:
            raise ValueError()
        return dict(value)
    except (ValueError, TypeError, KeyError):
        raise MemoryError('INVALID_MEMORY_WRITE') from None


@dataclass(frozen=True)
class MemoryWriteGrant:
    """Private deployment-issued grant, resolved on every call, including retries."""
    task_id: str
    binding_fingerprint: str
    principal: str
    context: str
    domain: str
    operations: frozenset
    local_processing: bool


class PersistentMemoryFacade(MemoryFacade):
    """Blaine-owned CP.2 facade, also consumed by CP.1 Resolver/Compiler.

    `grants` is trusted runtime code returning a MemoryWriteGrant, not serialized
    Task data. `declare` is an operator application API, never a worker capability.
    """
    def __init__(self, authority, store, grants):
        self.authority, self.store, self.grants = authority, store, grants

    def _admit(self, state, spec, operation):
        bound = self.authority.resolve(state, spec)
        try:
            grant = self.grants(state['task_id'])
            if (type(grant) is not MemoryWriteGrant or
                    grant.task_id != state['task_id'] or
                    grant.binding_fingerprint != bound.fingerprint or
                    grant.principal != bound.snapshot['principal'] or
                    grant.context != bound.snapshot['context'] or
                    not bound.eligible(grant.context, grant.domain) or
                    operation not in grant.operations or not grant.local_processing):
                raise ValueError()
            if state['lifecycle'] != 'RUNNING':
                raise ValueError()
            return bound, grant
        except Exception:
            raise MemoryError('DENIED') from None

    def observe(self, state, spec, request):
        # Capability authority is checked by PolicyGate and again at this boundary.
        if 'memory.recordObservation' not in spec['capabilities'] or 'memory.recordObservation' not in spec['autonomy']['allowed']:
            raise MemoryError('DENIED')
        return self._write(state, spec, request, 'observe')

    def declare(self, state, spec, request):
        """Trusted operator entry point; no model capability maps to this method."""
        return self._write(state, spec, request, 'declare')

    def _write(self, state, spec, request, operation):
        value = validate_write(request)
        bound, grant = self._admit(state, spec, operation)
        origin, status, retention = (('AGENT_OBSERVATION', 'UNVERIFIED', 'WORKING')
                                    if operation == 'observe' else
                                    ('USER_DECLARATION', 'DECLARED', 'RETAINED'))
        entry = {'context': grant.context, 'domain': grant.domain, 'origin': origin,
                 'status': status, 'retention': retention, 'content': value['content'],
                 'creator': grant.principal, 'execution': state['task_id'],
                 'sha256': digest(value['content'].encode()), 'version': 1}
        token = hashlib.sha256(encode([operation, state['task_id'] if retention == 'WORKING' else None,
                                      value['idempotency_key']])).hexdigest()
        try:
            identity, replay = self.store.commit(entry, token)
        except MemoryError:
            raise
        except Exception:
            # A transport failure may follow a commit. Existing durable work retries
            # the same identity; no receipt means neither success nor known rollback.
            raise MemoryError('UNKNOWN') from None
        # Re-resolve runtime authority AFTER storage, then use the same facade reads
        # used by context consumers. A returned backend row is not a commit receipt.
        try:
            current, _ = self._admit(state, spec, operation)
            rows, result = self.retrieve(current, identity)
            if (result != 'SUCCESS' or len(rows) != 1 or
                    any(rows[0][key] != entry[key] for key in ('sha256', 'origin', 'status', 'retention'))):
                raise ValueError()
        except Exception:
            # Authority can change after a committed effect. Do not label that
            # effect a known failure merely because its receipt is now unreadable.
            raise MemoryError('UNKNOWN') from None
        return {'id': identity, 'result': 'RECORDED', 'idempotency': 'REPLAY' if replay else 'CREATED',
                'origin': origin, 'status': status, 'retention': retention,
                'authority': 'derived_knowledge'}

    def _read(self, bound, query=None, locator=None):
        try:
            if query is not None:
                text(query, 256)
            if locator is not None:
                text(locator, 80)
            domains = sorted(set(bound.snapshot['security_domains']) & set(bound.snapshot['policy_domains']))
            contexts = sorted(bound.readable)
            if not domains or not contexts:
                return [], 'DENIED' if locator is not None else 'EMPTY'
            rows = self.store.read(contexts, domains, bound.snapshot['context'], bound.snapshot['task_id'], query, locator)
            if not isinstance(rows, list) or len(rows) > 32:
                raise ValueError()
            candidates, seen = [], set()
            for entry in rows:
                fields(entry, {'id', 'context', 'domain', 'origin', 'status', 'retention', 'content',
                               'creator', 'execution', 'sha256', 'version'})
                if (entry['version'] != 1 or type(entry['version']) is not int or
                        not bound.eligible(entry['context'], entry['domain']) or
                        (entry['origin'], entry['status'], entry['retention']) not in
                        {('AGENT_OBSERVATION', 'UNVERIFIED', 'WORKING'),
                         ('USER_DECLARATION', 'DECLARED', 'RETAINED')} or
                        entry['retention'] == 'WORKING' and (entry['context'] != bound.snapshot['context']
                            or entry['execution'] != bound.snapshot['task_id'])):
                    raise ValueError()
                text(entry['content'], SOURCE_BYTES)
                text(entry['id'], 80)
                if entry['id'] in seen or digest(entry['content'].encode()) != entry['sha256']:
                    raise ValueError()
                if locator is not None and entry['id'] != locator:
                    raise ValueError()
                if query is not None and query.casefold() not in entry['content'].casefold():
                    raise ValueError()
                seen.add(entry['id'])
                candidates.append({'source': 'memory:' + entry['id'], 'content': entry['content'],
                    'revision': entry['sha256'], 'sha256': entry['sha256'], 'kind': 'memory',
                    'origin': entry['origin'], 'status': entry['status'], 'retention': entry['retention'],
                    'uncertainty': 'Derived knowledge; not completion evidence, authority or an override of Task constraints.'})
            return sorted(candidates, key=lambda row: row['source']), ('SUCCESS' if candidates else
                    'DENIED' if locator is not None else 'EMPTY')
        except Exception:
            return [], 'UNAVAILABLE'
