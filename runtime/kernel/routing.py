"""Policy C: local-first execution with bounded, trusted escalation.

Every eligible Task starts on the local binding and runs the ordinary bounded
loop. Extra local turns are a cost, not a failure: a Task that self-corrects
under verifier and policy constraints and finally satisfies its completion
contract completed locally, however many turns it took.

Escalation is reached only through deterministic conditions observable from
existing state. No model is asked whether it feels stuck, and nothing here
predicts escalation; that is deliberate, because the evidence needed to justify a
pre-router does not exist yet and this policy is what produces it.

Two authority kinds are kept apart, following ADR 0024:

* requested capability authority is declared in the TaskSpec, and effective
  authority is that request intersected with an external grant;
* binding authority is never TaskSpec data. Cognition may reach an escalation
  condition, but only the trusted boundary decides admissibility, and only a
  deployment supplies the binding that admission uses.

Escalation is an execution outcome, not a diagnosis: it records that local
execution required another tier, never that the local model was incapable.
"""
from dataclasses import dataclass
import hashlib

from runtime.kernel.contracts import MAX_TURNS, encode, fields, identifier, text

POLICY = 'local-first-bounded-escalation'
POLICY_VERSION = 1
LOCAL_BINDING = 'local'
# Below MAX_TURNS on purpose, so an admitted escalation still has budget to
# continue inside the same Task rather than inheriting an exhausted loop.
LOCAL_TURN_BUDGET = 8
REPEATED_REJECTION_LIMIT = 3

ESCALATION_REASONS = {'local_turn_budget_reached', 'repeated_verifier_rejection'}
ADMISSIONS = {'admitted', 'denied_no_grant', 'denied_not_authorized', 'denied_binding_unavailable'}


def validate_grant(value: object) -> dict:
    """An externally supplied execution grant. Never produced by cognition.

    It bounds capability authority and names the binding an escalation may use.
    It does not itself dispatch anything: a remote dispatch still answers to the
    frontier authority contract when that path exists.
    """
    grant = fields(value, {'capabilities'}, {'escalation_binding'})
    allowed = grant['capabilities']
    if not isinstance(allowed, list) or len(allowed) > 16 or len(set(allowed)) != len(allowed):
        raise ValueError('Expected a bounded unique capability grant')
    for capability in allowed:
        text(capability, 128)
    binding = grant.get('escalation_binding')
    if binding is not None:
        identifier(binding)
    return {'capabilities': sorted(allowed), 'escalation_binding': binding}


def effective_capabilities(spec: dict, grant: dict | None) -> set[str]:
    """Requested authority intersected with what was granted externally."""
    requested = set(spec.get('capabilities', ())) & set(spec['autonomy']['allowed'])
    return requested if grant is None else requested & set(grant['capabilities'])


def narrow_grant(parent: dict | None, requested: dict | None) -> dict | None:
    """Derive a child grant. A child may only narrow, never widen.

    An unbounded parent cannot hand out a bound it does not itself carry, so an
    absent parent grant yields an absent child grant rather than a fabricated one.
    """
    if parent is None:
        return None
    if requested is None:
        return dict(parent)
    narrowed = sorted(set(requested['capabilities']) & set(parent['capabilities']))
    binding = requested.get('escalation_binding')
    if binding is not None and binding != parent.get('escalation_binding'):
        raise ValueError('Child Task cannot obtain a binding its parent lacks')
    return {'capabilities': narrowed, 'escalation_binding': binding}


def verifier_signature(evaluation: dict, artifacts: dict) -> str:
    """Digest of one rejection together with the evidence that produced it.

    The admitted artifacts are part of the signature on purpose. Without them a
    static completion contract yields the same shape on every refusal, so any
    Task that had not finished would look stuck immediately. Including evidence
    means a repeat signals that the Task refused and produced nothing new, while
    a Task still changing its evidence is working and answers to the turn budget.
    """
    payload = evaluation['payload']
    shape = [payload['outcome'], [(item['criterion'], item['outcome']) for item in payload['criteria']],
             sorted((artifacts or {}).items())]
    return hashlib.sha256(encode(shape)).hexdigest()


def escalation_condition(iteration: int, verifier_history: list[str]) -> str | None:
    """Deterministic conditions only, computed from state Blaine already keeps."""
    if iteration >= LOCAL_TURN_BUDGET:
        return 'local_turn_budget_reached'
    recent = verifier_history[-REPEATED_REJECTION_LIMIT:]
    if len(recent) == REPEATED_REJECTION_LIMIT and len(set(recent)) == 1:
        return 'repeated_verifier_rejection'
    return None


def admit_escalation(grant: dict | None, deployed_binding: str | None) -> dict:
    """The trusted boundary decides. A recommendation is never an admission.

    Both sides must agree: the grant names a binding the operator authorized, and
    the deployment actually provides that binding. A grant naming a binding this
    deployment does not implement is refused rather than silently substituted.
    """
    if grant is None:
        outcome = 'denied_no_grant'
    elif not grant.get('escalation_binding'):
        outcome = 'denied_not_authorized'
    elif deployed_binding is None or deployed_binding != grant['escalation_binding']:
        outcome = 'denied_binding_unavailable'
    else:
        outcome = 'admitted'
    return {'outcome': outcome, 'binding': deployed_binding if outcome == 'admitted' else None}


@dataclass(frozen=True)
class RoutingRecord:
    """Authoritative per-Task routing evidence, retained as an artifact.

    Telemetry may be lost and durable runtime state is retained for seven days,
    so anything a later routing experiment needs is recorded here instead.
    """
    task_id: str
    outcome: str
    externally_bounded: bool
    effective_capabilities: tuple[str, ...]
    initial_binding: str
    final_binding: str
    local_turns: int
    total_turns: int
    escalated: bool
    escalation_iteration: int | None
    escalation_reason: str | None
    escalation_admission: str | None
    completion_ref: str | None
    result_ref: str | None
    context_refs: tuple[str, ...]
    concerns: tuple[str, ...]
    usage: dict | None

    def payload(self) -> dict:
        return {
            'version': 1, 'policy': POLICY, 'policy_version': POLICY_VERSION,
            'task_id': self.task_id, 'outcome': self.outcome,
            'externally_bounded': self.externally_bounded,
            'effective_capabilities': list(self.effective_capabilities),
            'initial_binding': self.initial_binding, 'final_binding': self.final_binding,
            'started_local': self.initial_binding == LOCAL_BINDING,
            'local_turns': self.local_turns, 'total_turns': self.total_turns,
            'max_turns': MAX_TURNS, 'local_turn_budget': LOCAL_TURN_BUDGET,
            'escalated': self.escalated, 'escalation_iteration': self.escalation_iteration,
            'escalation_reason': self.escalation_reason,
            'escalation_admission': self.escalation_admission,
            # Escalation records that another tier was required. It is not a
            # claim about model capability; classification is deferred to C1.
            'escalation_interpretation': 'local execution required another tier; cause unclassified',
            'completion_ref': self.completion_ref, 'result_ref': self.result_ref,
            'context_refs': list(self.context_refs), 'concerns': list(self.concerns),
            'usage': self.usage,
        }
