"""Policy, the three bounded capabilities, and independent exact-byte verification."""
import hashlib
import json
from pathlib import Path
import sqlite3

from runtime.kernel.human import human_requirement, validate_request, validate_response
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import (
    CAPABILITIES, MAX_CONTENT, SPECIALISTS, CapabilityRequest, CompletionEvaluation,
    TaskSpec, TaskState, encode, fields, identifier, message, text, unpack, validate_decision, validate_spec,
    child_task_id, spawn_specs,
)


def policy_gate(raw: dict, state: TaskState, spec: TaskSpec) -> dict:
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
            if capability not in CAPABILITIES or capability not in spec["capabilities"] or capability not in spec["autonomy"]["allowed"]:
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
                requirement = human_requirement(spec, request['request_id'])
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
            else:
                fields(value, {"value"})
                text(value["value"], 256)
        elif action['type'] == 'WAIT' and action['input_type'] == 'human_response':
            if 'human.request' not in set(spec['capabilities']) & set(spec['autonomy']['allowed']):
                raise ValueError('Human interaction denied')
            requirement = human_requirement(spec, action['wait_id'])
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
            authority = set(spec['capabilities']) & set(spec['autonomy']['allowed'])
            for slot, child in children:
                if not set(child['autonomy']['allowed']) <= authority:
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
    def __init__(self, store: ArtifactStore, fixture_database: Path, card_reader=None, worker=None):
        self.store = store
        self.card_reader = card_reader
        self.worker = worker
        self.fixture_database = fixture_database
        fixture_database.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(fixture_database) as db:
            db.execute("CREATE TABLE IF NOT EXISTS effects (operation_id TEXT PRIMARY KEY, request BLOB NOT NULL, receipt TEXT NOT NULL)")

    def execute(self, request: dict) -> dict:
        """Called only after admission; fixture row is the effect, not a Task ledger."""
        request: CapabilityRequest = unpack(request, "CapabilityRequest")
        operation = request["operation_id"]
        task_id = request["task_id"]
        value = request["input"]
        artifacts = {}
        try:
            match request["capability"]:
                case 'worker.run':
                    from runtime.kernel.worker import validate_packet
                    if self.worker is None:
                        raise ValueError('Worker adapter is not configured')
                    raw = self.store.read(task_id, value['packet_ref'])
                    if len(raw) > MAX_CONTENT:
                        raise ValueError('Worker input artifact exceeds budget')
                    packet = json.loads(raw)
                    validate_packet(packet, task_id)
                    result = self.worker(packet, operation)
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
            return message("CapabilityResult", {"operation_id": operation, "outcome": "failure",
                           "output": {}, "artifacts": {}, "error": str(error)})


def evaluate(spec: TaskSpec, state: TaskState, store: ArtifactStore) -> dict:
    findings = []
    for criterion in spec["completion"]:
        expected = criterion["evidence"]
        ref = state["artifacts"].get(expected["artifact"])
        outcome, detail = "unsatisfied", "Required artifact is missing"
        if ref:
            try:
                content = store.read(state["task_id"], ref)
                if expected.get('verifier') == 'human_response':
                    request = expected['request']
                    accepted = state.get('human_responses', {}).get(request['payload']['request_id'])
                    if ref != accepted:
                        raise ValueError('Artifact was not accepted through the human input boundary')
                    validate_response(json.loads(content), request, state['task_id'])
                    outcome, detail = 'satisfied', 'Scoped response accepted and allowed value independently verified'
                else:
                    outcome = "satisfied" if hashlib.sha256(content).hexdigest() == expected["sha256"] else "unsatisfied"
                    detail = "Exact artifact digest verified" if outcome == "satisfied" else "Artifact does not match accepted digest"
            except (OSError, ValueError) as error:
                outcome, detail = "unknown", str(error)
        findings.append({"criterion": criterion["criterion"], "outcome": outcome,
                         "evidence_ref": ref, "detail": detail})
    outcomes = {item["outcome"] for item in findings}
    result: CompletionEvaluation = {
        "outcome": "unsatisfied" if "unsatisfied" in outcomes else "unknown" if "unknown" in outcomes else "satisfied",
        "criteria": findings,
    }
    return message("CompletionEvaluation", result)
