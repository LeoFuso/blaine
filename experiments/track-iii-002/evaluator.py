"""III.2 executable specification only. No production API or process sandbox.

The trusted harness constructs the tree and issues bindings. The caller can only
send a closed request to handle() with its issued binding; it cannot call bind().
"""
from dataclasses import dataclass
from types import MappingProxyType


class Rejected(ValueError):
    """Stable denial code; never includes record contents."""


@dataclass(frozen=True)
class ContextNode:
    id: str
    parent_id: str | None
    kind: str
    inherit_parent: bool


@dataclass(frozen=True)
class ScopedEntry:
    id: str
    context_id: str
    content: str


@dataclass(frozen=True, eq=False)
class BoundContext:
    """Opaque identity: constructing another instance does not confer authority."""


def nonempty(value):
    return isinstance(value, str) and bool(value)


class ContextTree:
    def __init__(self, nodes, entries):
        parsed = {}
        for row in nodes:
            if (not isinstance(row, dict) or
                    set(row) != {'id', 'parent_id', 'kind', 'inherit_parent'} or
                    not nonempty(row['id']) or not isinstance(row['kind'], str) or
                    type(row['inherit_parent']) is not bool or
                    (row['parent_id'] is not None and not nonempty(row['parent_id']))):
                raise Rejected('invalid_node')
            node = ContextNode(**row)
            if node.id in parsed:
                raise Rejected('duplicate_context_id')
            parsed[node.id] = node
        for node in parsed.values():
            if node.parent_id == node.id:
                raise Rejected('self_parent')
            if node.parent_id is not None and node.parent_id not in parsed:
                raise Rejected('missing_parent')
        # Validate the entire structural tree, even beyond a denied read edge.
        for start in sorted(parsed):
            seen = set()
            current = start
            while current is not None:
                if current in seen:
                    raise Rejected('cycle')
                seen.add(current)
                current = parsed[current].parent_id
        if sum(n.parent_id is None for n in parsed.values()) != 1:
            raise Rejected('root_count')
        loaded = {}
        for row in entries:
            if (not isinstance(row, dict) or set(row) != {'id', 'context_id', 'content'} or
                    not nonempty(row['id']) or not nonempty(row['context_id']) or
                    not isinstance(row['content'], str)):
                raise Rejected('invalid_entry')
            entry = ScopedEntry(**row)
            if entry.context_id not in parsed:
                raise Rejected('unknown_entry_context')
            if entry.id in loaded:
                raise Rejected('duplicate_entry_id')
            loaded[entry.id] = entry
        self._nodes = MappingProxyType(parsed)
        self._entries = loaded
        self._bindings = {}

    def bind(self, context_id):
        """Trusted harness only: not an operation in the caller request language."""
        if not isinstance(context_id, str) or context_id not in self._nodes:
            raise Rejected('unknown_context')
        binding = BoundContext()
        self._bindings[binding] = context_id
        return binding

    def _lineage(self, context_id):
        lineage = set()
        current = context_id
        while current is not None:
            lineage.add(current)
            node = self._nodes[current]
            current = node.parent_id if node.inherit_parent else None
        return lineage

    def handle(self, binding, request):
        """Only caller-facing operation: exact shapes, binding-owned context."""
        if not isinstance(binding, BoundContext) or binding not in self._bindings:
            raise Rejected('untrusted_binding')
        context_id = self._bindings[binding]
        shapes = {'read': {'op'}, 'get': {'op', 'entry_id'},
                  'write': {'op', 'entry_id', 'content'}}
        if not isinstance(request, dict) or not isinstance(request.get('op'), str):
            raise Rejected('invalid_request')
        op = request['op']
        if op not in shapes or set(request) != shapes[op]:
            raise Rejected('invalid_request')
        if op != 'read' and not nonempty(request['entry_id']):
            raise Rejected('invalid_request')
        if op == 'write':
            if not isinstance(request['content'], str):
                raise Rejected('invalid_request')
            if request['entry_id'] in self._entries:
                raise Rejected('duplicate_entry_id')
            entry = ScopedEntry(request['entry_id'], context_id, request['content'])
            self._entries[entry.id] = entry
            return entry
        allowed = self._lineage(context_id)
        if op == 'get':
            entry = self._entries.get(request['entry_id'])
            if entry is None or entry.context_id not in allowed:
                raise Rejected('not_visible')
            return entry
        return sorted((e for e in self._entries.values() if e.context_id in allowed),
                      key=lambda e: e.id)
