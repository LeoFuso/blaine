"""Offline III.3 capability model; not a production API or hostile-code sandbox."""
from dataclasses import dataclass
import json
from pathlib import Path
import sys

# Consume the accepted experiment unchanged; no production imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'track-iii-002'))
from evaluator import ContextTree, Rejected

BUDGET = 2048


def wire(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def response(status, entries=None, partial=False, reason=None, receipt=None):
    return {'status': status, 'entries': entries or [], 'partial': partial,
            'reason': reason, 'receipt': receipt}


@dataclass(frozen=True, eq=False)
class ExecutionContext:
    execution_id: str
    context_id: str


@dataclass(frozen=True, eq=False)
class Caller:
    caller_id: str
    caller_class: str


class Memory:
    def __init__(self, nodes, entries):
        stored = []
        for entry in entries:
            if (set(entry) != {'id', 'context_id', 'content', 'provenance', 'created_by', 'epistemic_status'}
                    or entry['provenance'] not in ('USER_DECLARATION', 'AGENT_OBSERVATION')
                    or entry['epistemic_status'] != ('DECLARED' if entry['provenance'] == 'USER_DECLARATION' else 'UNVERIFIED')
                    or not all(isinstance(v, str) and v for v in entry.values())):
                raise Rejected('invalid_memory_fixture')
            stored.append({'id': entry['id'], 'context_id': entry['context_id'],
                           'content': wire(entry).decode('utf-8')})
        self._tree = ContextTree(nodes, stored)
        self._executions = {}
        self._callers = {}
        self.available = True  # Trusted fault switch, never a caller field.

    def begin(self, execution_id, context_id):
        """Trusted harness only; not exposed by handle()."""
        if not isinstance(execution_id, str) or not execution_id or len(execution_id) > 80:
            raise Rejected('invalid_execution')
        bound = self._tree.bind(context_id)
        execution = ExecutionContext(execution_id, context_id)
        self._executions[execution] = bound
        return execution

    def participant(self, execution, caller_id, caller_class):
        """Trusted harness issuance, including one fixed human declaration target."""
        if execution not in self._executions or caller_class not in ('human', 'cognition', 'worker', 'verifier'):
            raise Rejected('invalid_caller')
        if not isinstance(caller_id, str) or not caller_id or len(caller_id) > 80:
            raise Rejected('invalid_caller')
        caller = Caller(caller_id, caller_class)
        self._callers[caller] = execution
        return caller

    def _pack(self, entries):
        if not entries:
            return response('EMPTY')
        selected = []
        for entry in sorted(entries, key=lambda e: e['id']):
            # Reserve the longer boolean spelling (false) while testing the cap.
            if len(wire(response('SUCCESS_WITH_RESULTS', selected + [entry]))) <= BUDGET:
                selected.append(entry)
        return response('SUCCESS_WITH_RESULTS', selected, partial=len(selected) != len(entries))

    def handle(self, execution, caller, request):
        if (not isinstance(execution, ExecutionContext) or execution not in self._executions
                or not isinstance(caller, Caller) or self._callers.get(caller) is not execution):
            return response('DENIED', reason='untrusted_binding')
        shapes = {'search': {'op', 'query'}, 'get': {'op', 'entry_id'},
                  'recordObservation': {'op', 'entry_id', 'content'},
                  'declare': {'op', 'entry_id', 'content', 'target_context'}}
        if (not isinstance(request, dict) or not isinstance(request.get('op'), str)
                or request['op'] not in shapes or set(request) != shapes[request['op']]):
            return response('DENIED', reason='invalid_request')
        op = request['op']
        if op == 'search':
            if not isinstance(request['query'], str) or len(request['query'].encode('utf-8')) > 256:
                return response('DENIED', reason='invalid_request')
        elif not isinstance(request['entry_id'], str) or not 0 < len(request['entry_id'].encode('utf-8')) <= 80:
            return response('DENIED', reason='invalid_request')
        if op in ('recordObservation', 'declare'):
            if not isinstance(request['content'], str) or not 0 < len(request['content'].encode('utf-8')) <= 16384:
                return response('DENIED', reason='invalid_request')
            if op == 'recordObservation' and caller.caller_class not in ('cognition', 'worker'):
                return response('DENIED', reason='caller_operation')
            if op == 'declare' and (caller.caller_class != 'human' or request['target_context'] != 'project-a'):
                return response('DENIED', reason='declaration_authority')
        if not self.available:
            return response('UNAVAILABLE', reason='capability_unavailable')
        bound = self._executions[execution]
        try:
            if op == 'search':
                scoped = self._tree.handle(bound, {'op': 'read'})
                entries = [json.loads(e.content) for e in scoped]
                # Filtering is strictly after lineage enforcement, before packing.
                return self._pack([e for e in entries if request['query'] in e['content']])
            if op == 'get':
                entry = self._tree.handle(bound, {'op': 'get', 'entry_id': request['entry_id']})
                return self._pack([json.loads(entry.content)])
            target = execution.context_id if op == 'recordObservation' else 'project-a'
            provenance = 'AGENT_OBSERVATION' if op == 'recordObservation' else 'USER_DECLARATION'
            entry = {'id': request['entry_id'], 'context_id': target, 'content': request['content'],
                     'provenance': provenance, 'created_by': caller.caller_id,
                     'epistemic_status': 'UNVERIFIED' if provenance == 'AGENT_OBSERVATION' else 'DECLARED'}
            write_binding = bound if op == 'recordObservation' else self._tree.bind('project-a')
            self._tree.handle(write_binding, {'op': 'write', 'entry_id': entry['id'],
                                            'content': wire(entry).decode('utf-8')})
            return response('RECORDED', receipt={k: v for k, v in entry.items() if k != 'content'})
        except Rejected:
            return response('DENIED', reason='not_permitted')
