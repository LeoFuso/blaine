"""Small JSON contracts. Runtime validation follows the spike's ValueError convention."""
import hashlib
import json
import re
from typing import Literal, NotRequired, TypedDict

MAX_TURNS = 16
MAX_CONTENT = 4096
MAX_PACKET = 16384
MAX_RESULT = 8192
MAX_CHILDREN = 4
SPECIALISTS = {
    "coordinator": "Coordinate the accepted objective using permitted actions.",
    "specialist": "Produce the required exact artifact and request verification.",
}
CAPABILITIES = {"artifact.write", "artifact.read", "fixture.effect", "human.request", "youtrack.read", "worker.run"}


class EvidenceRequirement(TypedDict):
    artifact: str
    sha256: str


class HumanEvidenceRequirement(TypedDict):
    artifact: str
    verifier: Literal["human_response"]
    request: dict


class CompletionCriterion(TypedDict):
    criterion: str
    evidence: EvidenceRequirement | HumanEvidenceRequirement


class Autonomy(TypedDict):
    allowed: list[str]
    child_tasks: NotRequired[int]


class TaskSpec(TypedDict):
    objective: str
    completion: list[CompletionCriterion]
    capabilities: list[str]
    autonomy: Autonomy


class Invoke(TypedDict):
    type: Literal["INVOKE_CAPABILITY"]
    capability: str
    input: dict


class Handoff(TypedDict):
    type: Literal["HANDOFF"]
    specialist: str


class SpawnTask(TypedDict):
    type: Literal["SPAWN_TASK"]
    task_spec: dict


class Wait(TypedDict):
    type: Literal["WAIT"]
    wait_id: str
    input_type: Literal["text", "human_response"]


class Complete(TypedDict):
    type: Literal["COMPLETE"]


NextAction = Invoke | Handoff | SpawnTask | Wait | Complete


class CognitiveDecision(TypedDict):
    task_id: str
    task_revision: int
    turn_id: str
    next_action: NextAction
    reason: NotRequired[str]


class ContextItem(TypedDict):
    source: str
    revision: str
    authority: Literal["task", "artifact", "instruction", "derived"]
    content: object
    unknowns: list[str]


class CognitiveTurn(TypedDict):
    task_id: str
    task_revision: int
    turn_id: str
    iteration: int
    objective: str
    completion: list[CompletionCriterion]
    specialist: str
    instructions: str
    observations: list[dict]
    context: list[ContextItem]
    allowed_capabilities: list[str]
    limits: dict[str, int]


class WaitState(TypedDict):
    wait_id: str
    input_type: Literal["text", "human_response"]
    task_revision: int
    promise: str
    request_ref: NotRequired[str]


class ChildWait(TypedDict):
    child_id: str
    input_type: Literal["TaskResult"]
    task_revision: int


class TaskState(TypedDict):
    task_id: str
    revision: int
    lifecycle: Literal["RUNNING", "WAITING", "COMPLETED", "FAILED"]
    iteration: int
    active_specialist: str
    spec_ref: str
    decision_id: str | None
    decision_ref: str | None
    context_ref: str | None
    observation_ref: str | None
    wait: WaitState | ChildWait | None
    artifacts: dict[str, str]
    human_responses: NotRequired[dict[str, str]]
    completion_ref: str | None
    result_ref: str | None
    remaining_children: int
    children: dict[str, dict]


class CapabilityRequest(TypedDict):
    task_id: str
    operation_id: str
    capability: str
    input: dict


class CapabilityResult(TypedDict):
    operation_id: str
    outcome: Literal["success", "failure"]
    output: dict
    artifacts: dict[str, str]
    error: str | None


class CompletionEvaluation(TypedDict):
    outcome: Literal["satisfied", "unsatisfied", "unknown"]
    criteria: list[dict]


class TaskResult(TypedDict):
    task_id: str
    outcome: Literal["COMPLETED", "FAILED"]
    artifacts: dict[str, str]
    completion_ref: str | None
    concerns: list[str]


def encode(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def message(kind: str, payload: object) -> dict:
    return {"version": 1, "kind": kind, "payload": payload}


def fields(value: object, required: set[str], optional: set[str] = frozenset()) -> dict:
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise ValueError("Invalid object fields")
    return value


def text(value: object, limit: int = MAX_CONTENT) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.encode("utf-8")) > limit:
        raise ValueError("Expected bounded nonblank text")
    return value


def identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("Invalid identifier")
    return value


def child_task_id(parent_id: str, decision_id: str) -> str:
    return "child-" + hashlib.sha256(encode([identifier(parent_id), decision_id])).hexdigest()


def unpack(value: object, kind: str) -> dict:
    obj = fields(value, {"version", "kind", "payload"})
    if type(obj["version"]) is not int or obj["version"] != 1 or obj["kind"] != kind:
        raise ValueError("Unsupported contract version or kind")
    if len(encode(obj)) > MAX_PACKET:
        raise ValueError("Contract exceeds size limit")
    if not isinstance(obj["payload"], dict):
        raise ValueError("Expected object payload")
    return obj["payload"]


def validate_spec(value: object) -> TaskSpec:
    spec = fields(unpack(value, "TaskSpec"), {"objective", "completion"}, {"capabilities", "autonomy"})
    text(spec["objective"], 1024)
    criteria = spec["completion"]
    if not isinstance(criteria, list) or not 1 <= len(criteria) <= 8:
        raise ValueError("Expected 1..8 completion criteria")
    for item in criteria:
        fields(item, {"criterion", "evidence"})
        text(item["criterion"], 512)
        evidence = item["evidence"]
        if isinstance(evidence, dict) and evidence.get('verifier') == 'human_response':
            from runtime.kernel.human import validate_request
            fields(evidence, {'artifact', 'verifier', 'request'})
            validate_request(evidence['request'])
        else:
            fields(evidence, {'artifact', 'sha256'})
            if not isinstance(evidence['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', evidence['sha256']):
                raise ValueError('Expected exact SHA-256 completion evidence')
        identifier(evidence['artifact'])
    human_ids = [x['evidence']['request']['payload']['request_id'] for x in criteria
                 if x['evidence'].get('verifier') == 'human_response']
    if len(set(human_ids)) != len(human_ids):
        raise ValueError('Duplicate human request identity')
    capabilities = spec.get("capabilities", [])
    autonomy = fields(spec.get("autonomy", {"allowed": []}), {"allowed"}, {"child_tasks"})
    child_tasks = autonomy.get("child_tasks", 0)
    if type(child_tasks) is not int or not 0 <= child_tasks <= MAX_CHILDREN:
        raise ValueError("Invalid child Task allocation")
    for names in (capabilities, autonomy["allowed"]):
        if not isinstance(names, list) or len(names) > 8:
            raise ValueError("Expected bounded capability list")
        for name in names:
            text(name, 80)
            if name not in CAPABILITIES:
                raise ValueError("Unsupported capability grant/requirement")
    return {**spec, "capabilities": capabilities, "autonomy": autonomy}


def validate_decision(value: object) -> CognitiveDecision:
    decision = fields(unpack(value, "CognitiveDecision"),
                      {"task_id", "task_revision", "turn_id", "next_action"}, {"reason"})
    identifier(decision["task_id"])
    if type(decision["task_revision"]) is not int or decision["task_revision"] < 0:
        raise ValueError("Invalid Task revision")
    text(decision["turn_id"], 100)
    if "reason" in decision:
        text(decision["reason"], 256)
    action = decision["next_action"]
    if not isinstance(action, dict):
        raise ValueError("Invalid NextAction")
    match action.get("type"):
        case "INVOKE_CAPABILITY":
            fields(action, {"type", "capability", "input"})
            text(action["capability"], 80)
            if not isinstance(action["input"], dict):
                raise ValueError("Capability input must be an object")
        case "HANDOFF":
            fields(action, {"type", "specialist"})
            identifier(action["specialist"])
        case "SPAWN_TASK":
            fields(action, {"type", "task_spec"})
            validate_spec(action["task_spec"])
        case "WAIT":
            fields(action, {"type", "wait_id", "input_type"})
            identifier(action["wait_id"])
            if action["input_type"] not in ("text", "human_response"):
                raise ValueError("Unsupported wait input type")
        case "COMPLETE":
            fields(action, {"type"})
        case _:
            raise ValueError("Unknown NextAction")
    return decision


def validate_result(value: object, task_id: str) -> TaskResult:
    result = fields(unpack(value, "TaskResult"),
                    {"task_id", "outcome", "artifacts", "completion_ref", "concerns"})
    if len(encode(value)) > MAX_RESULT or result["task_id"] != identifier(task_id):
        raise ValueError("Oversized or misaddressed TaskResult")
    if result["outcome"] not in ("COMPLETED", "FAILED"):
        raise ValueError("Invalid TaskResult outcome")
    refs = result["artifacts"]
    if not isinstance(refs, dict) or len(refs) > 16:
        raise ValueError("Invalid TaskResult artifacts")
    for name in refs:
        identifier(name)
    for ref in [*refs.values(), *([result["completion_ref"]] if result["completion_ref"] is not None else [])]:
        if not isinstance(ref, str) or not re.fullmatch(r"artifact://" + re.escape(task_id) + r"/sha256:[0-9a-f]{64}", ref):
            raise ValueError("Invalid TaskResult evidence reference")
    if result["outcome"] == "COMPLETED" and result["completion_ref"] is None:
        raise ValueError("Completed TaskResult requires verifier evidence")
    if not isinstance(result["concerns"], list) or len(result["concerns"]) > 8:
        raise ValueError("Invalid TaskResult concerns")
    for concern in result["concerns"]:
        text(concern, 512)
    return result
