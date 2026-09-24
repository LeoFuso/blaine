"""Policy, the three bounded capabilities, and independent exact-byte verification."""
import hashlib
import json
from pathlib import Path
import sqlite3

from runtime.kernel.human import validate_request
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import (
    CAPABILITIES, MAX_CONTENT, SPECIALISTS, CapabilityRequest,
    TaskSpec, TaskState, encode, fields, identifier, message, text, unpack, validate_decision, validate_spec,
    child_task_id, spawn_specs,
)


def policy_gate(raw: dict, state: TaskState, spec: TaskSpec, grant: dict | None = None,
                contract: dict | None = None, authority: dict | None = None) -> dict:
    """Admissibility under effective authority.

    Effective capability authority is the TaskSpec's request intersected with an
    externally supplied grant. An absent grant preserves existing behaviour, and
    the routing evidence records that the Task was not externally bounded.
    Human requests are admissible only as fixed by the current Completion
    Contract revision; the contract never grants capability authority.
    """
    from runtime.kernel.completion import human_binding, lower_spec
    from runtime.kernel.routing import effective_capabilities
    admissible = effective_capabilities(spec, grant)

    def target_scope(value):
        if authority is None or value['workspace_id'] not in authority['workspaces']:
            raise ValueError('Target workspace is not in effective authority')

    def human(request_id):
        return human_binding(contract or lower_spec(spec, state['task_id'], state.get('parent')), request_id)
    try:
        decision = validate_decision(raw)
        if (decision["task_id"] != state["task_id"] or
                decision["task_revision"] != state["revision"] or
                decision["turn_id"] != f'{state["task_id"]}/{state["iteration"]}'):
            raise ValueError("Stale or misaddressed decision")
        if state["lifecycle"] != "RUNNING":
            raise ValueError("Task is not running")
        action = decision["next_action"]
        if action["type"] == "INVOKE_CAPABILITY":
            capability = action["capability"]
            if capability not in CAPABILITIES or capability not in admissible:
                raise ValueError("Capability denied")
            value = action["input"]
            if capability == "artifact.write":
                fields(value, {"name", "content"})
                identifier(value["name"])
                text(value["content"])
                if value["name"] not in state["artifacts"] and len(state["artifacts"]) >= 16:
                    raise ValueError("Artifact limit reached")
            elif capability == "artifact.read":
                fields(value, {"ref"})
                if value["ref"] not in state["artifacts"].values():
                    raise ValueError("Artifact read outside admitted evidence")
            elif capability == 'human.request':
                fields(value, {'request'})
                request = validate_request(value['request'])
                requirement = human(request['request_id'])
                if request['task_id'] != state['task_id'] or value['request'] != requirement['request']:
                    raise ValueError('Human interaction outside accepted scope')
            elif capability == 'youtrack.read':
                fields(value, {'issue_id'})
                text(value['issue_id'], 80)
            elif capability == 'worker.run':
                fields(value, {'packet_ref', 'artifact'})
                identifier(value['artifact'])
                if value['packet_ref'] not in state['artifacts'].values():
                    raise ValueError('Worker packet outside admitted artifacts')
                if value['artifact'] not in state['artifacts'] and len(state['artifacts']) >= 16:
                    raise ValueError('Artifact limit reached')
            elif capability == 'context.request':
                from runtime.kernel.context_plane import validate_need
                validate_need(value)
                if 'compiled-context' not in state['artifacts']:
                    raise ValueError('Context Plane is not active')
            elif capability == 'text.stats':
                fields(value, {'text'})
                text(value['text'], 1024)
            elif capability == 'workspace.read' and isinstance(value, dict) and 'form' in value:
                from runtime.kernel.effects import validate_read_input
                validate_read_input(value)
                target_scope(value)
                if value['artifact'] not in state['artifacts'] and len(state['artifacts']) >= 16:
                    raise ValueError('Artifact limit reached')
            elif capability == 'workspace.read':
                from runtime.kernel.workspace import validate_read
                validate_read(value)
                # Scope is the exact persisted intake action, not all project access.
                if action != state.get('initial_action'):
                    raise ValueError('Workspace read outside accepted operation scope')
            elif capability in ('workspace.write', 'workspace.exec'):
                # A proposal is not authority: the pinned effective authority decides,
                # and no new target effect starts while an earlier one is unknown.
                from runtime.kernel.effects import admit_exec, validate_exec_input, validate_write_input
                open_effects = sorted(op for op, effect in (state.get('effects') or {}).items()
                                      if effect['status'] == 'uncertain')
                if open_effects:
                    raise ValueError(f'Uncertain target effects must be reconciled first: {open_effects}')
                if capability == 'workspace.write':
                    validate_write_input(value)
                    target_scope(value)
                    if value['content_ref'] not in state['artifacts'].values():
                        raise ValueError('Write content must be an admitted Task artifact')
                else:
                    validate_exec_input(value)
                    target_scope(value)
                    admit_exec(value, authority)
            else:
                fields(value, {"value"})
                text(value["value"], 256)
        elif action['type'] == 'WAIT' and action['input_type'] == 'human_response':
            if 'human.request' not in admissible:
                raise ValueError('Human interaction denied')
            requirement = human(action['wait_id'])
            request = requirement['request']
            if request['payload']['task_id'] != state['task_id']:
                raise ValueError('Human wait Task mismatch')
            request_name = 'human-request-' + action['wait_id']
            expected_ref = 'artifact://' + state['task_id'] + '/sha256:' + hashlib.sha256(encode(request)).hexdigest()
            if state['artifacts'].get(request_name) != expected_ref:
                raise ValueError('Human request must be published before waiting')
        elif action["type"] == "HANDOFF" and action["specialist"] not in SPECIALISTS:
            raise ValueError("Ineligible HANDOFF target")
        elif action["type"] == "SPAWN_TASK":
            children = spawn_specs(action)
            cost = sum(1 + child['autonomy'].get('child_tasks', 0) for _, child in children)
            if cost > state.get('remaining_children', 0):
                raise ValueError('Child Task allocation exhausted')
            # A child may only narrow effective authority, so the parent's own
            # external bound propagates rather than being reset by the request.
            for slot, child in children:
                if not set(child['autonomy']['allowed']) <= admissible:
                    raise ValueError('Child Task cannot expand parent authority')
                for criterion in child['completion']:
                    evidence = criterion['evidence']
                    if evidence.get('verifier') == 'human_response':
                        request = evidence['request']['payload']
                        if (request['origin_task_id'] != state['task_id'] or
                                request['task_id'] != child_task_id(state['task_id'], decision['turn_id'], slot)):
                            raise ValueError('Human child request must bind to its parent and derived child identity')
        return {"outcome": "allow", "reason": None}
    except (ValueError, TypeError) as error:
        return {"outcome": "deny", "reason": str(error)}


class Capabilities:
    def __init__(self, store: ArtifactStore, fixture_database: Path, card_reader=None, worker=None,
                 recorder=None, context_plane=None):
        self.store = store
        self.card_reader = card_reader
        self.worker = worker
        self.context_plane = context_plane
        # Optional diagnostics only. No capability outcome depends on it.
        from runtime.kernel.instrument import safe
        self.recorder = safe(recorder)
        self.fixture_database = fixture_database
        fixture_database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(fixture_database) as db:
            db.execute("CREATE TABLE IF NOT EXISTS effects (operation_id TEXT PRIMARY KEY, request BLOB NOT NULL, receipt TEXT NOT NULL)")

    def dispatch_worker(self, packet: dict, operation: str, task_id: str) -> dict:
        """One external Worker execution. A worker session is not a Task.

        The session span measures the dispatch Blaine actually owns. Boundaries
        internal to the Worker are only observable when its adapter exposes them.
        """
        from runtime.kernel.instrument import ExecutionIdentity
        with self.recorder.span('invoke_agent worker', kind='worker_session', attributes={
                **ExecutionIdentity(task_id=task_id, run_id=None,
                                    worker_dispatch_id='dispatch:' + operation).attributes(),
                'gen_ai.operation.name': 'invoke_agent',
                'gen_ai.agent.id': getattr(self.worker, 'adapter_id', 'worker')}) as span:
            result = self.worker(packet, operation)
            if isinstance(result, dict):
                span.set(**{'blaine.worker.outcome': str(result.get('outcome')),
                            'blaine.worker_session_id': str(result.get('attempt_id'))})
                if result.get('outcome') != 'success':
                    span.fail('worker_outcome_' + str(result.get('outcome')))
            return result

    def execute(self, request: dict, *, context_runtime=None) -> dict:
        """Called only after admission; fixture row is the effect, not a Task ledger."""
        request: CapabilityRequest = unpack(request, "CapabilityRequest")
        operation = request["operation_id"]
        task_id = request["task_id"]
        value = request["input"]
        artifacts = {}
        try:
            match request["capability"]:
                case 'text.stats':
                    from runtime.task import summarize_objective
                    output = summarize_objective(value['text'])
                    artifacts['answer'] = self.store.put_json(task_id, output)
                case 'workspace.read':
                    from runtime.kernel.workspace import validate_read
                    validate_read(value)
                    ref = self.store.put_json(task_id, message('WorkspaceReadRequest', {
                        'task_id': task_id, 'operation_id': operation, **value}))
                    output = {'request_ref': ref, 'delivery': 'authorized ACP client read'}
                case 'worker.run':
                    from runtime.kernel.worker import validate_packet
                    if self.worker is None:
                        raise ValueError('Worker adapter is not configured')
                    raw = self.store.read(task_id, value['packet_ref'])
                    if len(raw) > MAX_CONTENT:
                        raise ValueError('Worker input artifact exceeds budget')
                    packet = json.loads(raw)
                    validate_packet(packet, task_id)
                    if self.context_plane is not None:
                        from runtime.kernel.context_plane import ContextError
                        if context_runtime is None:
                            raise ContextError('DENIED')
                        state, spec, admission = context_runtime
                        if state['task_id'] != task_id:
                            raise ContextError('DENIED')
                        self.context_plane.guard_worker(state, spec, admission, value['packet_ref'], operation)
                    result = self.dispatch_worker(packet, operation, task_id)
                    ref = self.store.put_json(task_id, result)
                    output = {'worker_outcome':result['outcome'], 'attempt_id':result['attempt_id'],
                              'evidence_ref':ref}
                    if result['outcome'] == 'success':
                        text(result['content'])
                        artifacts[value['artifact']] = self.store.put(task_id, result['content'].encode())
                    else:
                        return message('CapabilityResult', {'operation_id':operation, 'outcome':'failure',
                            'output':output, 'artifacts':{}, 'error':'Worker did not produce an admitted result'})
                case 'youtrack.read':
                    if self.card_reader is None:
                        raise ValueError('YouTrack transport is not configured')
                    output = self.card_reader(value['issue_id'])
                case "artifact.write":
                    ref = self.store.put(task_id, value["content"].encode("utf-8"))
                    artifacts[value["name"]] = ref
                    output = {"ref": ref, "sha256": ref.rsplit(":", 1)[1]}
                case "artifact.read":
                    content = self.store.read(task_id, value["ref"])
                    if len(content) > MAX_CONTENT:
                        raise ValueError("Artifact exceeds read budget")
                    output = {"ref": value["ref"], "content": content.decode("utf-8"),
                              "sha256": hashlib.sha256(content).hexdigest(), "authority": "artifact"}
                case 'human.request':
                    human = validate_request(value['request'])
                    if human['task_id'] != task_id:
                        raise ValueError('Human request Task mismatch')
                    ref = self.store.put_json(task_id, value['request'])
                    artifacts['human-request-' + human['request_id']] = ref
                    output = {'request_ref': ref, 'request_id': human['request_id'],
                              'delivery': 'controlled-input adapter; no external notification'}
                case "fixture.effect":
                    encoded = encode(request)
                    receipt = {"effect_id": operation, "value": value["value"]}
                    with sqlite3.connect(self.fixture_database) as db:
                        db.execute("INSERT OR IGNORE INTO effects VALUES (?, ?, ?)",
                                   (operation, encoded, json.dumps(receipt)))
                        stored, result = db.execute("SELECT request, receipt FROM effects WHERE operation_id = ?", (operation,)).fetchone()
                        if stored != encoded:
                            raise ValueError("Operation identity reused with different input")
                    output = json.loads(result)
                case _:
                    raise ValueError("Unknown capability")
            return message("CapabilityResult", {"operation_id": operation, "outcome": "success",
                           "output": output, "artifacts": artifacts, "error": None})
        except (ValueError, FileNotFoundError, UnicodeError) as error:
            if self.context_plane is not None:
                from runtime.kernel.context_plane import ContextError, failure
                return failure(operation, error if isinstance(error, ContextError) else ContextError('UNAVAILABLE'))
            return message("CapabilityResult", {"operation_id": operation, "outcome": "failure",
                           "output": {}, "artifacts": {}, "error": str(error)})


def evaluate(spec: TaskSpec, state: TaskState, store: ArtifactStore) -> dict:
    """v1 CompletionEvaluation over the lowered revision 0, for existing readers.

    Verdicts come from the same Completion Contract verifiers; the workflow itself
    decides completion only through ``completion.evaluate_contract``/``legality``.
    """
    from runtime.kernel.completion import assess, lower_spec, project_v1
    contract = lower_spec(spec, state['task_id'], state.get('parent'))
    facts = {'error': None, 'analysis': None, 'authorities': {}, 'receipts': set()}
    return project_v1(contract, assess(contract, state, store, facts))
