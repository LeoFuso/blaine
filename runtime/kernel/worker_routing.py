"""Small, provider-neutral suitability recommendation; never dispatch authority.

Quality and expected cost-to-success ranks are explicit scripted inputs, not
measurements or invented prices. A future classifier can replace assess().
"""
from dataclasses import asdict, dataclass
from typing import Protocol
from runtime.kernel.frontier import WorkerBinding, nonnegative
from runtime.kernel.contracts import text


@dataclass(frozen=True)
class Workload:
    capabilities: tuple[str, ...]
    minimum_quality: int

    def __post_init__(self):
        nonnegative(self.minimum_quality)
        if type(self.capabilities) is not tuple or not 1 <= len(self.capabilities) <= 8:
            raise ValueError('Bounded capability requirements required')
        for item in self.capabilities:
            text(item, 128)


@dataclass(frozen=True)
class Assessment:
    binding_id: str
    suitability: str
    cost_to_success_rank: int
    reason: str

    def __post_init__(self):
        if self.suitability not in ('UNDERPOWERED', 'JUST_RIGHT', 'OVERKILL'):
            raise ValueError('Unknown suitability')
        nonnegative(self.cost_to_success_rank)
        text(self.binding_id, 128)
        text(self.reason, 256)


class WorkloadClassifier(Protocol):
    def assess(self, workload: Workload, binding: WorkerBinding) -> Assessment: ...


class ScriptedClassifier:
    def __init__(self, cost_to_success_ranks):
        self.ranks = dict(cost_to_success_ranks)

    def assess(self, workload, binding):
        sufficient = set(workload.capabilities) <= set(binding.capabilities) and binding.quality >= workload.minimum_quality
        suitability = ('UNDERPOWERED' if not sufficient else
                       'JUST_RIGHT' if binding.quality == workload.minimum_quality else 'OVERKILL')
        return Assessment(binding.binding_id, suitability, self.ranks[binding.binding_id],
                          'Scripted capability/quality threshold; ordinal expected cost-to-success')


def select(workload, bindings, classifier, authorization):
    """Authorization outcomes are produced separately by Blaine's hard gate.

    Routing only recommends an ID. The selected request must still pass dispatch
    authorization, including a fresh guardrail check. No grants are constructed here.
    """
    if not 1 <= len(bindings) <= 8 or len({b.binding_id for b in bindings}) != len(bindings):
        raise ValueError('Expected unique bounded candidates')
    candidates = []
    for binding in bindings:
        assessment = classifier.assess(workload, binding)
        if assessment.binding_id != binding.binding_id:
            raise ValueError('Classifier changed binding identity')
        candidates.append({'binding': asdict(binding), 'assessment': asdict(assessment),
                           'authorization': authorization[binding.binding_id]})
    adequate = [c for c in candidates if c['assessment']['suitability'] != 'UNDERPOWERED'
                and c['authorization']['outcome'] == 'allow']
    # ADR 0010: prefer a sufficient local binding; otherwise rank expected total
    # cost-to-success. Suitability never turns an OVERKILL candidate into a denial.
    chosen = min(adequate, key=lambda c: (c['binding']['frontier'],
                 c['assessment']['cost_to_success_rank'], c['binding']['binding_id'])) if adequate else None
    return {'version': 1, 'workload': asdict(workload), 'candidates': candidates,
            'outcome': 'selected' if chosen else 'STOP_OR_ESCALATE',
            'selected_binding': chosen['binding']['binding_id'] if chosen else None,
            'classification_source': 'scripted recommendation; not authority or measured pricing'}
