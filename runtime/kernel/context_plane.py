"""CP.1: deployment-bound local reads and deterministic worker projections.

This module holds no Task lifecycle and accepts no serialized access grants.
Admissions are returned only to the owning workflow's journal, never inferred
from packet fields or membership in the public artifact map. MIRIX is deliberately
not an eligible provider until its processing scope and entry metadata qualify.
"""
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat

from runtime.kernel import completion, journal
from runtime.kernel.contracts import MAX_CONTENT, encode, fields, message, text, unpack
from runtime.kernel.worker import validate_packet


WORKER_BYTES = 4096
DELTA_BYTES = 4096
SOURCE_BYTES = 16384
REQUEST_BYTES = 1024


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class ContextError(ValueError):
    """Only safe state names cross the caller/telemetry boundary."""
    def __init__(self, status):
        self.status = status
        super().__init__('Context Plane: ' + status)


def validate_need(raw):
    """Closed v1 information need; locators narrow, never select authority."""
    try:
        need = fields(unpack(raw, 'ContextRequest'), {'question', 'form'},
                      {'locator', 'exact', 'base_ref', 'max_bytes'})
        text(need['question'], 256)
        if need['form'] not in ('exact-source', 'lexical-source', 'current-evidence', 'prior-context'):
            raise ValueError()
        for key in ('locator', 'exact', 'base_ref'):
            if key in need:
                text(need[key], 256)
        if need['form'] in ('exact-source', 'current-evidence') and 'locator' not in need:
            raise ValueError()
        if need['form'] == 'lexical-source' and 'exact' not in need:
            raise ValueError()
        if need['form'] == 'prior-context' and 'exact' in need:
            raise ValueError()
        if 'max_bytes' in need and (type(need['max_bytes']) is not int or not 256 <= need['max_bytes'] <= WORKER_BYTES):
            raise ValueError()
        if len(encode(raw)) > REQUEST_BYTES:
            raise ValueError()
        return deepcopy(need)
    except (ValueError, TypeError, KeyError):
        raise ContextError('INVALID_CONTEXT') from None


def lineage(nodes, current):
    """Validate the whole configured tree, including inaccessible branches."""
    parents = {}
    for node in nodes:
        fields(node, {'id', 'parent', 'kind'})
        text(node['id'], 80)
        text(node['kind'], 80)
        if node['id'] in parents:
            raise ValueError()
        parents[node['id']] = node['parent']
    if not parents or len(parents) > 128 or sum(p is None for p in parents.values()) != 1:
        raise ValueError()
    for start in parents:
        visited = set()
        while start is not None:
            if start not in parents or start in visited:
                raise ValueError()
            visited.add(start)
            start = parents[start]
    result = []
    while current is not None:
        result.append(current)
        current = parents[current]
    return result


@dataclass(frozen=True)
class BoundContext:
    """Internal coherent snapshot. The serialized reference is never this grant."""
    snapshot: dict
    fingerprint: str
    readable: frozenset

    def eligible(self, owner, domain):
        return (owner in self.readable and domain in self.snapshot['security_domains']
                and domain in self.snapshot['policy_domains'])


class LocalContextAuthority:
    """Trusted single-host application configuration, selected afresh per operation.

    `current` is deployment code, not a ContextProvider or request field. It must
    return one coherent immutable revision and must not mutate during an operation.
    Snapshots may be selected from the existing ArtifactStore by this application.
    No distributed authentication or concurrent administration is claimed here.
    """
    def __init__(self, current, *, principal):
        self.current = current
        self.principal = principal

    def resolve(self, state, spec):
        try:
            raw = self.current(state['task_id'])
        except Exception:
            raise ContextError('UNAVAILABLE') from None
        if raw is None:
            raise ContextError('DENIED')
        try:
            snapshot = deepcopy(fields(unpack(raw, 'LocalContextBinding'), {
                'task_id', 'spec_ref', 'principal', 'route', 'revision', 'nodes', 'context',
                'security_domains', 'policy_domains', 'readable_contexts', 'workspace_root',
                'workspace_paths', 'evidence_refs', 'memory_entries', 'initial_need', 'memory_query'}))
            if (snapshot['task_id'] != state['task_id'] or snapshot['spec_ref'] != state['spec_ref']
                    or snapshot['principal'] != self.principal or snapshot['route'] != 'hosted-local'
                    or state.get('parent') or state.get('initial_action')
                    or state.get('binding', 'local') != 'local'):
                raise ValueError()
            text(snapshot['revision'], 80)
            ancestry = lineage(snapshot['nodes'], snapshot['context'])
            for key in ('security_domains', 'policy_domains', 'readable_contexts', 'workspace_paths', 'evidence_refs'):
                values = snapshot[key]
                if not isinstance(values, list) or len(values) > 128 or len(set(values)) != len(values):
                    raise ValueError()
                for value in values:
                    text(value, 256)
            if not set(snapshot['readable_contexts']) <= {n['id'] for n in snapshot['nodes']}:
                raise ValueError()
            root = Path(snapshot['workspace_root'])
            if not root.is_absolute() or root.is_symlink() or root.resolve() != root:
                raise ValueError()
            for path in snapshot['workspace_paths']:
                safe_path(path)
            if len(snapshot['workspace_paths']) > 32 or len(snapshot['memory_entries']) > 32:
                raise ValueError()
            ids = set()
            for entry in snapshot['memory_entries']:
                fields(entry, {'id', 'context', 'domain', 'origin', 'status', 'revision', 'sha256'})
                for value in entry.values():
                    text(value, 128)
                if entry['id'] in ids or entry['context'] not in {n['id'] for n in snapshot['nodes']}:
                    raise ValueError()
                ids.add(entry['id'])
                if (entry['origin'], entry['status']) not in (
                        ('USER_DECLARATION', 'DECLARED'), ('AGENT_OBSERVATION', 'UNVERIFIED')):
                    raise ValueError()
                if len(entry['sha256']) != 64 or any(c not in '0123456789abcdef' for c in entry['sha256']):
                    raise ValueError()
            validate_need(snapshot['initial_need'])
            if snapshot['memory_query'] is not None:
                text(snapshot['memory_query'], 256)
            # Bind accepted bytes, not merely a caller-provided artifact name.
            expected = 'artifact://' + state['task_id'] + '/sha256:' + digest(encode(message('TaskSpec', spec)))
            if expected != snapshot['spec_ref']:
                raise ValueError()
            return BoundContext(snapshot, digest(encode(raw)),
                                frozenset(ancestry) & frozenset(snapshot['readable_contexts']))
        except (ValueError, TypeError, KeyError, OSError):
            raise ContextError('INVALID_CONTEXT') from None


def safe_path(path):
    p = PurePosixPath(path)
    if p.is_absolute() or not p.parts or any(part in ('..', '.') for part in p.parts) or str(p) != path:
        raise ValueError()
    return p.parts


def source_read(bound, path):
    """Exact allowlist before open; no directory enumeration or symlink traversal."""
    if path not in bound.snapshot['workspace_paths']:
        raise ContextError('DENIED')
    descriptors = []
    try:
        parts = safe_path(path)
        fd = os.open(bound.snapshot['workspace_root'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        descriptors.append(fd)
        for part in parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            descriptors.append(fd)
        fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        descriptors.append(fd)
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ContextError('UNAVAILABLE')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            data = stream.read(SOURCE_BYTES + 1)
        if len(data) > SOURCE_BYTES:
            raise ContextError('INSUFFICIENT_CONTEXT')
        return data.decode('utf-8')
    except (OSError, UnicodeError, ValueError) as error:
        if isinstance(error, ContextError):
            raise
        raise ContextError('UNAVAILABLE') from None
    finally:
        for fd in reversed(descriptors):
            os.close(fd)


class ReadOnlyCorpus:
    """Qualified CP.1 in-process transport, not MIRIX or a new memory product.

    Only explicitly selected IDs are processed. It performs no global search,
    statistics, logging, embeddings or network calls. Deployment owns the corpus;
    independent metadata/digests in the binding qualify every returned row.
    """
    def __init__(self, records):
        self._records = deepcopy(records)

    def read(self, ids):
        return [{'id': key, 'content': self._records[key]} for key in ids if key in self._records]


class MemoryFacade:
    """Blaine-owned read-only search/retrieve; no raw provider exposed to workers."""
    def __init__(self, provider=None):
        # Provider-supplied claims of scope isolation are not qualification.
        if provider is not None and type(provider) is not ReadOnlyCorpus:
            raise ValueError('Unqualified Memory provider')
        self.provider = provider

    def _read(self, bound, query=None, locator=None):
        eligible = {e['id']: e for e in bound.snapshot['memory_entries']
                    if bound.eligible(e['context'], e['domain'])}
        if locator is not None:
            if locator not in eligible:
                return [], 'DENIED'
            eligible = {locator: eligible[locator]}
        if self.provider is None:
            return [], 'UNAVAILABLE'
        try:
            rows = self.provider.read(sorted(eligible))
            if not isinstance(rows, list) or len(rows) != len(eligible):
                raise ValueError()
            candidates, seen = [], set()
            for row in rows:
                fields(row, {'id', 'content'})
                entry = eligible[row['id']]
                text(row['content'], SOURCE_BYTES)
                if row['id'] in seen or digest(row['content'].encode()) != entry['sha256']:
                    raise ValueError()
                seen.add(row['id'])
                if query is not None and query.casefold() not in row['content'].casefold():
                    continue
                candidates.append({'source': 'memory:' + entry['id'], 'content': row['content'],
                    'revision': entry['revision'], 'sha256': entry['sha256'], 'kind': 'memory',
                    'origin': entry['origin'], 'status': entry['status'],
                    'uncertainty': 'Historical context; not completion evidence or authority.'})
            return candidates, 'SUCCESS' if candidates else 'EMPTY'
        except Exception:
            return [], 'UNAVAILABLE'

    def search(self, bound, query):
        return self._read(bound, query=query)

    def retrieve(self, bound, locator):
        return self._read(bound, locator=locator)


class ContextResolver:
    """Route only the explicit need, with optional deployment-selected Memory."""
    def __init__(self, store, memory=None):
        self.store = store
        self.memory = memory or MemoryFacade()

    def resolve(self, bound, state, need, *, include_memory=False):
        candidates = []
        form = need['form']
        if form in ('exact-source', 'lexical-source'):
            paths = ([need['locator']] if 'locator' in need else sorted(bound.snapshot['workspace_paths']))
            for path in paths:
                content = source_read(bound, path)
                if form == 'lexical-source' and need['exact'] not in content:
                    continue
                if 'exact' in need and need['exact'] not in content:
                    raise ContextError('INSUFFICIENT_CONTEXT')
                candidates.append({'source': path, 'content': content, 'kind': 'source',
                    'sha256': digest(content.encode()), 'revision': digest(content.encode()),
                    'extent': 'whole-file', 'uncertainty': 'Exact source bytes; runtime behavior unverified.'})
        elif form == 'current-evidence':
            ref = need['locator']
            if ref not in bound.snapshot['evidence_refs'] or ref not in state['artifacts'].values():
                raise ContextError('DENIED')
            try:
                data = self.store.read(state['task_id'], ref)
                if len(data) > SOURCE_BYTES:
                    raise ContextError('INSUFFICIENT_CONTEXT')
                if 'exact' in need and need['exact'] not in data.decode():
                    raise ContextError('INSUFFICIENT_CONTEXT')
                candidates.append({'source': ref, 'content': data.decode(), 'kind': 'evidence',
                    'revision': digest(data), 'sha256': digest(data), 'extent': 'whole-artifact',
                    'uncertainty': 'Exact artifact bytes; Task completion requires independent evaluation.'})
            except (OSError, ValueError, UnicodeError) as error:
                if isinstance(error, ContextError):
                    raise
                raise ContextError('UNAVAILABLE') from None
        else:
            candidates, status = (self.memory.retrieve(bound, need['locator']) if 'locator' in need
                                  else self.memory.search(bound, need['question']))
            if status not in ('SUCCESS', 'EMPTY'):
                raise ContextError(status)
        required = len(candidates)
        status = 'SUCCESS' if candidates else 'EMPTY'
        memory_status = 'NOT_REQUESTED'
        if include_memory and bound.snapshot['memory_query'] is not None:
            optional, memory_status = self.memory.search(bound, bound.snapshot['memory_query'])
            candidates += optional
        return {'candidates': candidates, 'required': required, 'status': status,
                'memory_status': memory_status}

    def validate(self, bound, state, candidate):
        """Compiler and delivery independently recheck permission and exact bytes."""
        if candidate['kind'] == 'source':
            return digest(source_read(bound, candidate['source']).encode()) == candidate['sha256']
        if candidate['kind'] == 'evidence':
            ref = candidate['source']
            if ref not in bound.snapshot['evidence_refs'] or ref not in state['artifacts'].values():
                return False
            try:
                return digest(self.store.read(state['task_id'], ref)) == candidate['sha256']
            except (OSError, ValueError):
                raise ContextError('UNAVAILABLE') from None
        rows, status = self.memory.retrieve(bound, candidate['source'].removeprefix('memory:'))
        return status == 'SUCCESS' and rows == [candidate]


class ContextCompiler:
    """Deterministic exact selection; never summarizes mandatory material."""
    def __init__(self, resolver):
        self.resolver = resolver

    def compile(self, bound, state, spec, need, resolved, operation, *, mode, contract):
        limit = min(WORKER_BYTES, need.get('max_bytes', WORKER_BYTES))
        candidates = resolved['candidates']
        # Validate before selection; invalid optional material never suppresses source.
        required = candidates[:resolved['required']]
        optional = candidates[resolved['required']:]
        if not required:
            raise ContextError('INSUFFICIENT_CONTEXT')
        for candidate in required:
            if not self.resolver.validate(bound, state, candidate):
                raise ContextError('STALE')
        optional = [c for c in optional if self.resolver.validate(bound, state, c)]
        stats = {'limit_bytes': limit, 'output_bytes': 0, 'considered': len(candidates),
                 'considered_bytes': sum(len(encode(c)) for c in candidates),
                 'selected': 0, 'selected_bytes': 0, 'partial': False, 'truncated': False}
        metadata = {'version': 1, 'mode': mode, 'operation': operation, 'need': need['question'],
                    'memory': resolved['memory_status'], 'budget': stats,
                    'constraints': {'capabilities': spec['capabilities'], 'autonomy': spec['autonomy']},
                    'authority': 'Projection only; requirements and exact evidence govern.'}
        requirements = {'contract_ref': state['contract_ref'],
                        'completion': {'revision': contract['revision'], 'criteria': contract['criteria']},
                        'projection': metadata}

        def render(selected):
            stats.update(selected=len(selected), selected_bytes=sum(len(encode(c)) for c in selected),
                         partial=len(selected) < len(candidates) or resolved['memory_status'] == 'UNAVAILABLE')
            packet = message('WorkerInput', {'task_id': state['task_id'], 'objective': spec['objective'],
                'context': [{'source': 'task:accepted-requirements', 'content': encode(requirements).decode()}]
                           + [{'source': c['source'], 'content': encode({k: v for k, v in c.items() if k != 'source'}).decode()}
                              for c in selected]})
            # output_bytes includes its own encoded digits and every other field.
            for _ in range(8):
                size = len(encode(packet))
                if size == stats['output_bytes']:
                    break
                stats['output_bytes'] = size
                packet['payload']['context'][0]['content'] = encode(requirements).decode()
            validate_packet(packet, state['task_id'])
            if len(encode(packet)) > limit:
                raise ValueError()
            return packet

        selected = list(required)
        try:
            packet = render(selected)
        except ValueError:
            raise ContextError('INSUFFICIENT_CONTEXT') from None
        for candidate in optional:
            try:
                proposed = render(selected + [candidate])
            except ValueError:
                continue
            selected.append(candidate)
            packet = proposed
        packet = render(selected)
        return packet, deepcopy(selected), deepcopy(stats)


class ContextPlane:
    """Composition owned by an opt-in hosted create_workflow deployment."""
    def __init__(self, store, authority, memory=None):
        self.store = store
        self.authority = authority
        self.resolver = ContextResolver(store, memory)
        self.compiler = ContextCompiler(self.resolver)

    def guard_binding(self, state, spec, fingerprint):
        bound = self.authority.resolve(state, spec)
        if bound.fingerprint != fingerprint:
            raise ContextError('STALE')
        return bound

    def current_contract(self, state, spec):
        """Read the runtime-owned revision; never reconstruct truth from TaskSpec."""
        try:
            contract = completion.validate_contract(
                self.store.read_json(state['task_id'], state['contract_ref']),
                state['task_id'], journal.mutating(spec['capabilities']))
            if contract['revision'] != state['contract_revision']:
                raise ContextError('STALE')
            return contract
        except (KeyError, OSError, ValueError) as error:
            if isinstance(error, ContextError):
                raise
            raise ContextError('INVALID_CONTEXT') from None

    def compile(self, state, spec, operation, *, request=None, previous=None):
        bound = self.authority.resolve(state, spec)
        contract = self.current_contract(state, spec)
        need = validate_need(request or bound.snapshot['initial_need'])
        mode = 'delta' if previous is not None else 'initial'
        if previous is not None:
            if need.get('base_ref') != previous['packet_ref'] or previous['mode'] != 'initial':
                raise ContextError('DENIED')
        elif 'base_ref' in need:
            raise ContextError('INVALID_CONTEXT')
        resolved = self.resolver.resolve(bound, state, need, include_memory=True)
        if resolved['status'] == 'EMPTY':
            raise ContextError('EMPTY')
        packet, selected, budget = self.compiler.compile(bound, state, spec, need, resolved, operation, mode=mode, contract=contract)
        self.guard_binding(state, spec, bound.fingerprint)
        packet_ref = self.store.put_json(state['task_id'], packet)
        # This is private journal data, not a public artifact/receipt. The workflow
        # independently holds it and never accepts it from a capability payload.
        admission = {'version': 1, 'task_id': state['task_id'], 'operation': operation,
                     'packet_ref': packet_ref, 'packet_sha256': digest(encode(packet)),
                     'binding': bound.fingerprint, 'spec_ref': state['spec_ref'], 'mode': mode,
                     'sources': selected, 'budget': budget,
                     'contract_ref': state['contract_ref'], 'contract_revision': contract['revision']}
        output = {'status': 'SUCCESS', 'packet_ref': packet_ref, 'budget': budget,
                  'memory': resolved['memory_status']}
        if previous is not None:
            # Replacement, not old+new concatenation. Delta carries new exact
            # sources and a reference to the separately bounded active input.
            delta = message('ContextDelta', {'base_ref': previous['packet_ref'],
                'operation': operation, 'replaces': 'all-context', 'active_ref': packet_ref,
                'context': packet['payload']['context'], 'status': 'SUCCESS',
                'limit_bytes': DELTA_BYTES, 'output_bytes': 0})
            for _ in range(8):
                size = len(encode(delta))
                if delta['payload']['output_bytes'] == size:
                    break
                delta['payload']['output_bytes'] = size
            if len(encode(delta)) > min(DELTA_BYTES, need.get('max_bytes', DELTA_BYTES)):
                raise ContextError('INSUFFICIENT_CONTEXT')
            output['delta_ref'] = self.store.put_json(state['task_id'], delta)
            output['delta_bytes'] = len(encode(delta))
        # Retain the deployment snapshot in the artifact boundary; its reference
        # stays private with the admission, never in TaskState.artifacts.
        admission['snapshot_ref'] = self.store.put_json(state['task_id'], message('LocalContextBinding', bound.snapshot))
        admission['execution_context'] = message('ExecutionContextRef', {
            'task_id': state['task_id'], 'operation_id': operation,
            'binding_ref': admission['snapshot_ref']})
        result = message('CapabilityResult', {'operation_id': operation, 'outcome': 'success',
            'output': output, 'artifacts': {'compiled-context': packet_ref}, 'error': None})
        if len(encode(result)) > MAX_CONTENT:
            raise ContextError('INSUFFICIENT_CONTEXT')
        return {'result': result, 'admission': admission}

    def guard_worker(self, state, spec, admission, packet_ref, operation):
        if (not admission or admission['task_id'] != state['task_id']
                or admission['spec_ref'] != state['spec_ref'] or admission['packet_ref'] != packet_ref
                or operation != f"{state['task_id']}/{state['iteration']}"
                or admission['operation'] == operation):
            raise ContextError('DENIED')
        if (admission.get('contract_ref') != state.get('contract_ref')
                or admission.get('contract_revision') != state.get('contract_revision')):
            raise ContextError('STALE')
        self.current_contract(state, spec)
        bound = self.guard_binding(state, spec, admission['binding'])
        try:
            packet = self.store.read(state['task_id'], packet_ref)
            if digest(packet) != admission['packet_sha256']:
                raise ContextError('DENIED')
            for candidate in admission['sources']:
                if not self.resolver.validate(bound, state, candidate):
                    raise ContextError('STALE')
        except (OSError, ValueError) as error:
            if isinstance(error, ContextError):
                raise
            raise ContextError('UNAVAILABLE') from None
        self.guard_binding(state, spec, bound.fingerprint)


def failure(operation, error):
    return message('CapabilityResult', {'operation_id': operation, 'outcome': 'failure',
        'output': {'status': error.status}, 'artifacts': {}, 'error': str(error)})
