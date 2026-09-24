"""III.4 offline contract only. Trusted harness, not a Python security sandbox."""
from copy import deepcopy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'track-iii-003'))
from capability import Memory, ExecutionContext, Caller, Rejected, response, wire

DOMAINS = {'public', 'personal', 'employer-x'}
KINDS = {'SUMMARY', 'EMBEDDING_STUB', 'SEMANTIC_INDEX_STUB', 'GRAPH_NODE',
         'GRAPH_EDGE', 'ARTIFACT_STUB', 'TOOL_OUTPUT_STUB'}


class SecurityMemory(Memory):
    def __init__(self, fixture):
        f = deepcopy(fixture)
        if any('::' in e['id'] for e in f['entries'] + f['derived']):
            raise Rejected('reserved_fixture_id')
        self.raw = {e['id']: e for e in f['entries']}
        basic = [{k: v for k, v in e.items() if k not in ('domain', 'classification')} for e in f['entries']]
        super().__init__(f['nodes'], basic)  # Validates all topology before visibility.
        self.context_domains = f['context_domains']
        self.policy = f['policy']
        self.declaration_targets = f['declaration_targets']
        self.derived = {}
        for d in f['derived']:
            fields = {'id', 'kind', 'source_ids', 'payload'} | ({'start', 'end'} if d['kind'] == 'GRAPH_EDGE' else set())
            if (set(d) != fields or d['id'] in self.derived or d['id'] in self.raw or d['kind'] not in KINDS
                    or not isinstance(d['source_ids'], list) or not d['source_ids']
                    or any(s not in self.raw for s in d['source_ids'])):
                raise Rejected('invalid_derivation')
            self.derived[d['id']] = d
        for d in self.derived.values():
            if d['kind'] == 'GRAPH_EDGE':
                endpoints = [self.derived.get(d[k]) for k in ('start', 'end')]
                if (any(e is None or e['kind'] != 'GRAPH_NODE' for e in endpoints)
                        or set(d['source_ids']) != {s for e in endpoints for s in e['source_ids']}):
                    raise Rejected('invalid_derivation')
        self._security = {}
        self.cache = []  # Synthetic precomputed fixtures only; no caching worker.

    def begin(self, execution_id, context_id):
        ec = super().begin(execution_id, context_id)
        # Snapshot is issued by trusted setup; no domain argument in request API.
        self._security[ec] = self.context_domains.get(context_id)
        return ec

    def policy_state(self, ec):
        if self.policy is None:
            return 'UNAVAILABLE'
        p = self.policy
        if (not isinstance(p, dict) or set(p) != {'version', 'grants', 'deny_ids'}
                or p['version'] != 'fixture-v1' or not isinstance(p['grants'], dict)
                or set(p['grants']) != DOMAINS or not isinstance(p['deny_ids'], list)
                or any(not isinstance(i, str) or i not in self.raw for i in p['deny_ids'])):
            return 'DENIED'
        for domain, grants in p['grants'].items():
            if (not isinstance(grants, list) or any(not isinstance(g, str) for g in grants)
                    or len(grants) != len(set(grants)) or not set(grants) <= {domain, 'public'}):
                return 'DENIED'
        if (not isinstance(self.context_domains, dict) or set(self.context_domains) != set(self._tree._nodes)
                or any(not isinstance(d, str) or d not in DOMAINS for d in self.context_domains.values())
                or self._security.get(ec) not in DOMAINS
                or self._security[ec] != self.context_domains.get(ec.context_id)):
            return 'DENIED'
        for e in self.raw.values():
            if (not isinstance(e.get('domain'), str) or e.get('domain') not in DOMAINS or
                    e.get('classification') != ('PUBLIC' if e['domain'] == 'public' else 'PRIVATE')):
                return 'DENIED'
        return None

    def allowed_raw(self, ec, entry_id):
        e = self.raw.get(entry_id)
        return bool(e and e['context_id'] in self._tree._lineage(ec.context_id)
                    and e['domain'] in self.policy['grants'][self._security[ec]]
                    and entry_id not in self.policy['deny_ids'])

    def allowed(self, ec, object_id):
        if object_id in self.raw:
            return self.allowed_raw(ec, object_id)
        d = self.derived.get(object_id)
        return bool(d and all(self.allowed_raw(ec, s) for s in d['source_ids']))

    def record(self, object_id):
        if object_id in self.raw:
            return dict(self.raw[object_id], kind='RAW')
        return deepcopy(self.derived[object_id])

    def visible_revision(self, ec):
        # Append-only fixture: count only permitted post-setup writes. No global
        # activity counter, deletion/update/versioning or production cache protocol.
        return sum('::' in i and self.allowed_raw(ec, i) for i in self.raw)

    def cached(self, ec, query):
        key = (query, ec.context_id, self._security[ec], self.policy['version'])
        for c in self.cache:
            if (c.get('query'), c.get('context_id'), c.get('domain'), c.get('policy_version')) == key:
                if (set(c) != {'query', 'context_id', 'domain', 'policy_version', 'revision', 'ids'}
                        or c['revision'] != self.visible_revision(ec) or not isinstance(c['ids'], list)
                        or any(not isinstance(i, str) or not self.allowed(ec, i) for i in c['ids'])):
                    return response('DENIED')
                return self._pack([self.record(i) for i in c['ids']])
        return response('EMPTY')

    def handle(self, ec, caller, request):
        if (not isinstance(ec, ExecutionContext) or ec not in self._executions
                or not isinstance(caller, Caller) or self._callers.get(caller) is not ec):
            return response('DENIED')
        shapes = {'search': {'op', 'query', 'kind'}, 'get': {'op', 'id'},
                  'neighbors': {'op', 'id'}, 'cached': {'op', 'query'}, 'debug': {'op'},
                  'recordObservation': {'op', 'id', 'content'},
                  'declare': {'op', 'id', 'content', 'target_context'}}
        if (not isinstance(request, dict) or not isinstance(request.get('op'), str)
                or request['op'] not in shapes or set(request) != shapes[request['op']]
                or any(not isinstance(v, str) or len(v.encode('utf-8')) > 1024 for v in request.values())):
            return response('DENIED')
        op = request['op']
        if ('id' in request and not 0 < len(request['id'].encode('utf-8')) <= 80
                or op == 'search' and request['kind'] not in KINDS | {'RAW'}):
            return response('DENIED')
        state = self.policy_state(ec)
        if state:
            return response(state)
        if not self.available:
            return response('UNAVAILABLE')
        if op in ('recordObservation', 'declare'):
            domain = self._security[ec]
            target = ec.context_id
            if op == 'declare':
                target = self.declaration_targets.get(caller.caller_id)
                if (caller.caller_class != 'human' or request['target_context'] != target
                        or self.context_domains.get(target) != domain):
                    return response('DENIED')
            elif caller.caller_class not in ('cognition', 'worker'):
                return response('DENIED')
            entry_id = target + '::' + request['id']  # Destination-owned write namespace.
            if (domain == 'public' or domain not in self.policy['grants'][domain] or not request['content']
                    or entry_id in self.raw or entry_id in self.derived):
                return response('DENIED')
            e = dict(id=entry_id, context_id=target, domain=domain, classification='PRIVATE',
                     content=request['content'], created_by=caller.caller_id,
                     provenance='USER_DECLARATION' if op == 'declare' else 'AGENT_OBSERVATION',
                     epistemic_status='DECLARED' if op == 'declare' else 'UNVERIFIED')
            bound = self._executions[ec] if op == 'recordObservation' else self._tree.bind(target)
            self._tree.handle(bound, {'op': 'write', 'entry_id': e['id'], 'content': wire(e).decode()})
            self.raw[e['id']] = e
            return response('RECORDED', receipt={k: v for k, v in e.items() if k != 'content'})
        if op == 'cached':
            return self.cached(ec, request['query'])
        if op == 'get':
            return self._pack([self.record(request['id'])]) if self.allowed(ec, request['id']) else response('DENIED')
        if op == 'neighbors':
            start = self.derived.get(request['id'])
            if not start or start['kind'] != 'GRAPH_NODE' or not self.allowed(ec, start['id']):
                return response('DENIED')
            rows = {}
            for edge in self.derived.values():
                if edge['kind'] == 'GRAPH_EDGE' and edge['start'] == start['id'] and self.allowed(ec, edge['id']):
                    rows[edge['id']] = self.record(edge['id'])
                    rows[edge['end']] = self.record(edge['end'])
            return self._pack(list(rows.values()))
        if op == 'debug':
            return self._pack([{'id': 'diagnostics', 'raw_count': sum(self.allowed(ec, i) for i in self.raw),
                                'derived_count': sum(self.allowed(ec, i) for i in self.derived)}])
        pool = self.raw if request['kind'] == 'RAW' else self.derived
        rows = [self.record(i) for i in pool if self.allowed(ec, i)]
        return self._pack([r for r in rows if r['kind'] == request['kind'] and
                           request['query'] in r.get('content', r.get('payload', ''))])

    def exchange(self, ec, caller, request):
        """Only externally observable payloads; no raw request/ID echo in diagnostics."""
        r = self.handle(ec, caller, request)
        return {'response': r, 'diagnostic': {'status': r['status'],
                'returned_count': len(r['entries']), 'partial': r['partial']}}
