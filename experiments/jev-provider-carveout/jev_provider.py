"""Isolated TypeSafe/Jev provider: a routing and classification candidate only.

Jev is not adopted. It is not the default router, it never authorizes an effect,
and it cannot complete a Task. This module plugs a real provider into two
boundaries Blaine already owns and defines elsewhere:

* `WorkloadClassifier.assess` in `runtime/kernel/worker_routing.py`, which
  produces a suitability recommendation that hard authorization still has to admit;
* `BoundaryObserver.inspect` in `runtime/kernel/instrument.py`, the synchronous
  continuation-boundary participant whose assessments cannot change execution.

No new vocabulary is introduced. Suitability stays `UNDERPOWERED`/`JUST_RIGHT`/
`OVERKILL`, usage stays the existing observed-usage shape, and a boundary
assessment stays the existing closed `PROCEED`/`ABSTAIN` record.

The credential is read by the SDK itself from `TYPESAFE_API_KEY`, which stays in
the operator's secret store and outside Git. This module checks only whether that
variable is present; it never reads, copies, logs or retains its value, and no
provider diagnostic text is kept, because a failure message can echo submitted
state back into evidence.
"""
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
import os
import time

from runtime.kernel.contracts import text
from runtime.kernel.frontier import validate_usage
from runtime.kernel.worker_routing import Assessment, Workload

API_KEY_ENV = 'TYPESAFE_API_KEY'        # the SDK's own variable; never read here
DEFAULT_MODEL = 'jev-latest'
DESTINATION = 'https://api.typesafe.ai'
SUITABILITIES = ('UNDERPOWERED', 'JUST_RIGHT', 'OVERKILL')

# Closed failure vocabulary. Provider message text is deliberately discarded:
# it can quote the submitted state, and a category is enough to decide behavior.
FAILURES = {
    'TypeSafeAuthenticationError': 'authentication_failed',
    'TypeSafePermissionDeniedError': 'permission_denied',
    'TypeSafeRateLimitError': 'rate_limited',
    'TypeSafeAPITimeoutError': 'timeout',
    'TypeSafeAPIConnectionError': 'connection_failed',
    'TypeSafeBadRequestError': 'invalid_request',
    'TypeSafeUnprocessableEntityError': 'invalid_request',
    'TypeSafeNotFoundError': 'not_found',
    'TypeSafeInternalServerError': 'provider_unavailable',
    'TypeSafeAPIResponseValidationError': 'invalid_response',
    'TypeSafeAPIError': 'api_error',
    'TypeSafeError': 'provider_error',
}


class JevUnavailable(RuntimeError):
    """A bounded provider failure. It carries a category, never provider text."""

    def __init__(self, category: str):
        self.category = category
        super().__init__(category)


def credential_present() -> bool:
    """Presence check only. The value is never bound to a name in this process."""
    return API_KEY_ENV in os.environ


def failure_category(error: BaseException) -> str:
    for base in type(error).__mro__:
        if base.__name__ in FAILURES:
            return FAILURES[base.__name__]
    return 'unexpected_error'


def bounded_probabilities(raw) -> dict:
    if not isinstance(raw, Mapping) or len(raw) > 16:
        raise ValueError('Unbounded or malformed probability distribution')
    result = {}
    for key, value in raw.items():
        if type(value) not in (int, float) or not 0.0 <= float(value) <= 1.0:
            raise ValueError('Probability outside the unit interval')
        result[text(key, 80)] = round(float(value), 6)
    return result


def normalize_answer(answer) -> dict:
    """Closed projection of one SDK answer. No free provider text is retained."""
    kind = getattr(answer, 'type', None)
    if kind == 'choice':
        value = {'type': 'choice', 'choice': text(answer.choice, 80),
                 'confidence': round(float(answer.confidence), 6)}
    elif kind == 'score':
        value = {'type': 'score', 'score': float(answer.score),
                 'confidence': round(float(answer.confidence), 6)}
    elif kind == 'noul':
        value = {'type': 'noul', 'noul': float(answer.noul)}
    else:
        raise ValueError('Unknown answer type')
    probabilities = getattr(answer, 'probabilities', None)
    if probabilities:
        value['probabilities'] = bounded_probabilities(probabilities)
    if not 0.0 <= value.get('confidence', 0.0) <= 1.0:
        raise ValueError('Confidence outside the unit interval')
    return value


@dataclass(frozen=True)
class JevProvider:
    """One authenticated call boundary. It executes no Task work and grants nothing.

    `client_factory` is injectable so offline controls never construct a real
    client or touch the network.
    """
    model: str = DEFAULT_MODEL
    timeout_s: float = 10.0
    client_factory: Callable[[], object] | None = None

    def client(self):
        if self.client_factory is not None:
            return self.client_factory()
        if not credential_present():
            raise JevUnavailable('credential_absent')
        from typesafe_sdk import TypeSafeClient  # imported late: optional dependency
        # The SDK reads the credential from its own environment variable.
        return TypeSafeClient(model=self.model, timeout=self.timeout_s)

    def ask(self, state, questions) -> dict:
        """Return bounded metadata using the existing observed-usage vocabulary.

        Cost stays UNKNOWN because the provider exposes no cost field; inventing
        one would break the rule that unobservable usage is never estimated.
        """
        started = time.monotonic()
        try:
            client = self.client()
            try:
                response = client.system_one(state=state, questions=questions)
            finally:
                close = getattr(client, 'close', None)
                if callable(close):
                    close()
        except JevUnavailable:
            raise
        except BaseException as error:
            raise JevUnavailable(failure_category(error)) from None
        latency_ms = max(0, int((time.monotonic() - started) * 1000))
        usage = getattr(response, 'usage', None)
        answers = {text(name, 80): normalize_answer(answer)
                   for name, answer in dict(response.answers).items()}
        if not answers or len(answers) > 8:
            raise JevUnavailable('invalid_response')
        return {'version': 1, 'provider': 'typesafe', 'destination': DESTINATION,
                'model': text(response.model, 128), 'latency_ms': latency_ms,
                'usage': validate_usage({'model_calls': 1,
                                         'input_tokens': getattr(usage, 'input_tokens', None),
                                         'output_tokens': getattr(usage, 'output_tokens', None),
                                         'cost_microusd': None}),
                'cost_observability': 'UNKNOWN; the provider exposes no cost field',
                'answers': answers}


def choice_question(instructions: str, criteria: Mapping) -> dict:
    """The SDK accepts a raw question mapping, so importing it here is avoided.

    Keeping the dependency inside the client boundary lets every offline control
    run without the provider package installed.
    """
    return {'type': 'choice', 'instructions': instructions, 'criteria': dict(criteria)}


SUITABILITY_CRITERIA = {
    'UNDERPOWERED': 'The binding lacks a required capability or its declared quality is below the minimum.',
    'JUST_RIGHT': 'The binding covers every required capability at about the minimum declared quality.',
    'OVERKILL': 'The binding covers every required capability with declared quality above the minimum.',
}
SUITABILITY_INSTRUCTIONS = (
    'Judge how well this worker binding fits the declared workload requirement. '
    'Use only the declared capabilities and the declared integer quality levels. '
    'Do not consider price, speed, vendor or availability.'
)


def routing_state(workload: Workload, binding) -> dict:
    """Declared metadata only. No Task objective, context or artifact is sent."""
    return {'required_capabilities': sorted(workload.capabilities),
            'minimum_quality': workload.minimum_quality,
            'binding_capabilities': sorted(binding.capabilities),
            'binding_quality': binding.quality}


@dataclass(frozen=True)
class JevWorkloadClassifier:
    """Replaces only the suitability judgement inside the existing routing seam.

    Expected cost-to-success ranks stay explicit scripted deployment inputs. The
    provider is never asked to invent prices it cannot observe, and it never sees
    authorization state: `select` still applies Blaine's separate hard gate.

    One call is made per candidate binding, so a routing decision over N bindings
    costs N provider calls. That is a reason to keep this a candidate.
    """
    provider: JevProvider
    cost_to_success_ranks: Mapping[str, int]
    # Optional bounded sink for call metadata the Assessment has no field for.
    # It receives identity, latency and usage, never submitted state or answers.
    record: Callable[[dict], None] | None = None

    def assess(self, workload: Workload, binding) -> Assessment:
        result = self.provider.ask(routing_state(workload, binding), {'suitability': choice_question(
            SUITABILITY_INSTRUCTIONS, dict.fromkeys(SUITABILITIES) | SUITABILITY_CRITERIA)})
        if self.record is not None:
            self.record({'binding_id': binding.binding_id, 'model': result['model'],
                         'latency_ms': result['latency_ms'], 'usage': result['usage'],
                         'cost_observability': result['cost_observability']})
        answer = result['answers'].get('suitability', {})
        if answer.get('type') != 'choice' or answer['choice'] not in SUITABILITIES:
            raise JevUnavailable('invalid_response')
        return Assessment(binding.binding_id, answer['choice'],
                          self.cost_to_success_ranks[binding.binding_id],
                          f"{result['model']} suitability, confidence "
                          f"{answer['confidence']:.3f}; rank is a scripted deployment input")


@dataclass
class ShadowClassifier:
    """Routing keeps using the accepted classifier; the candidate only observes.

    The returned Assessment is always the accepted one, so no routing outcome can
    change while Jev remains a candidate. Candidate judgements, agreement and
    bounded provider failures are recorded for the later comparison and never
    applied. This is the shape the 20-30 real-Task carveout needs; it is not a
    benchmark program and it runs nothing by itself.
    """
    accepted: object
    candidate: object
    record: Callable[[dict], None] = lambda observation: None
    observations: list = field(default_factory=list)
    breaker: CandidateBreaker | None = None

    def assess(self, workload: Workload, binding) -> Assessment:
        decision = self.accepted.assess(workload, binding)
        observation = {'binding_id': binding.binding_id,
                       'workload': {'required_capabilities': sorted(workload.capabilities),
                                    'minimum_quality': workload.minimum_quality},
                       'accepted_suitability': decision.suitability,
                       'candidate_suitability': None, 'agreement': None,
                       'candidate_failure': None}
        if self.breaker is not None and self.breaker.open:
            # Once the provider has refused us, stop spending calls on it. The
            # comparison keeps accumulating rows so the gap stays visible.
            observation['candidate_failure'] = 'circuit_open_' + self.breaker.account_status
        else:
            try:
                shadow = self.candidate.assess(workload, binding)
                if shadow.binding_id != binding.binding_id:
                    raise JevUnavailable('candidate_changed_binding_identity')
                observation['candidate_suitability'] = shadow.suitability
                observation['candidate_reason'] = shadow.reason
                observation['agreement'] = shadow.suitability == decision.suitability
                if self.breaker is not None:
                    self.breaker.record_success()
            except JevUnavailable as error:
                observation['candidate_failure'] = error.category
                if self.breaker is not None:
                    self.breaker.record_failure(error.category)
        self.observations.append(observation)
        self.record(observation)
        return decision  # the accepted judgement, unchanged


BOUNDARY_INSTRUCTIONS = (
    'Classify the progress of an automated work loop from these counters alone. '
    'Answer productive when tool activity and evidence are advancing, '
    'inconclusive when there is not yet enough signal, and stalled when repeated '
    'activity is producing no new evidence.'
)
BOUNDARY_CRITERIA = {'productive': None, 'inconclusive': None, 'stalled': None}


@dataclass(frozen=True)
class JevBoundaryObserver:
    """Synchronous continuation-boundary participant. It authorizes nothing.

    Its classification becomes a recorded label, never an intervention: the
    outcome stays inside the existing `PROCEED`/`ABSTAIN` vocabulary, so a
    provider failure or an unexpected answer cannot change Worker execution.
    """
    provider: JevProvider
    observer_id: str = 'jev-boundary-observer'

    def inspect(self, boundary) -> dict:
        state = {'continuation_index': boundary.index, 'reason': boundary.reason,
                 'model_invocations': boundary.model_invocations,
                 'tool_invocations': boundary.tool_invocations,
                 'last_tool_outcome': boundary.last_tool_outcome,
                 'evidence_digest_present': boundary.evidence_digest is not None}
        try:
            result = self.provider.ask(state, {'progress': choice_question(
                BOUNDARY_INSTRUCTIONS, dict(BOUNDARY_CRITERIA))})
        except JevUnavailable as error:
            # An unavailable supervisor abstains; it never blocks a continuation.
            return {'outcome': 'ABSTAIN', 'detail': error.category}
        answer = result['answers'].get('progress', {})
        if answer.get('type') != 'choice':
            return {'outcome': 'ABSTAIN', 'detail': 'invalid_response'}
        assessment = {'outcome': 'PROCEED', 'label': answer['choice'],
                      'score': answer['confidence'], 'latency_ms': result['latency_ms'],
                      'model': result['model']}
        for name in ('input_tokens', 'output_tokens'):
            if result['usage'].get(name) is not None:
                assessment[name] = result['usage'][name]
        return assessment


# Categories in which the provider actively refused us. A refusal may mean
# exhausted credit, a revoked key or a denied account; the API does not
# distinguish them, and it exposes no balance, so they are treated alike.
REFUSALS = frozenset({'authentication_failed', 'permission_denied', 'rate_limited',
                      'api_error', 'provider_error', 'not_found'})
# Categories where we simply could not reach a verdict. These are not refusals,
# but a run made only of them cannot be called healthy either.
INCONCLUSIVE = frozenset({'timeout', 'connection_failed', 'provider_unavailable',
                          'invalid_response', 'unexpected_error'})


@dataclass
class CandidateBreaker:
    """Self-disabling circuit for an unadopted paid candidate.

    Nothing is declared in advance, because this provider exposes no balance and
    no credit header: the breaker reacts to observed refusals instead of
    predicting exhaustion.

    It therefore prevents wasted calls and repeated failures after the provider
    starts refusing. It does **not** prevent the final credit from being spent,
    and it cannot warn before exhaustion. Claiming otherwise would require a
    balance the API does not publish or a budget the operator declares.

    State is reported in the vocabulary Blaine already uses for paid work, so
    `runtime.kernel.frontier.global_denial` yields its usual reason categories.
    An `unknown` state denies exactly like `exhausted`, which is the existing
    conservative rule rather than a new one.
    """
    threshold: int = 3
    warn: Callable[[dict], None] | None = None
    account_status: str = 'not_configured'
    consecutive_refusals: int = 0
    consecutive_inconclusive: int = 0
    calls: int = 0
    refusals: int = 0
    tripped_on: str | None = None

    def guardrails(self):
        """Express the breaker through the existing hard-guardrail contract."""
        from runtime.kernel.frontier import GlobalGuardrails
        # The state rides on account_status rather than kill_switch, so the
        # denial reason distinguishes an exhausted account from an unknown one.
        # kill_switch stays an operator control, not something a breaker asserts.
        return GlobalGuardrails(frontier_enabled=True, kill_switch=False,
                                account_status=self.account_status,
                                source='observed provider refusals; no balance is published')

    @property
    def open(self) -> bool:
        return self.account_status in ('exhausted', 'unknown')

    def record_success(self) -> None:
        self.calls += 1
        self.consecutive_refusals = 0
        self.consecutive_inconclusive = 0
        self.account_status = 'available'

    def record_failure(self, category: str) -> None:
        self.calls += 1
        if category in REFUSALS:
            self.refusals += 1
            self.consecutive_refusals += 1
            self.consecutive_inconclusive = 0
        else:
            self.consecutive_inconclusive += 1
            self.consecutive_refusals = 0
        if self.consecutive_refusals >= self.threshold:
            self._trip('exhausted', category)
        elif self.consecutive_inconclusive >= self.threshold:
            # Not a refusal, but no verdict either. Unknown denies, by the
            # existing rule that an unobservable ceiling is never a permission.
            self._trip('unknown', category)

    def _trip(self, status: str, category: str) -> None:
        if self.open:
            return
        self.account_status = status
        self.tripped_on = category
        if self.warn is not None:
            # A warning is diagnostics. It must never decide anything, and a
            # broken warning channel must not keep the breaker from opening.
            try:
                self.warn(self.report())
            except Exception:
                pass

    def report(self) -> dict:
        return {'candidate': 'jev', 'account_status': self.account_status,
                'circuit_open': self.open, 'tripped_on': self.tripped_on,
                'calls': self.calls, 'refusals': self.refusals,
                'threshold': self.threshold,
                'balance_observability': 'UNKNOWN; the provider publishes no balance or credit header',
                'protects_against': 'wasted calls and repeated failures after refusals begin',
                'does_not_protect_against': 'spending the final credit; exhaustion is only visible once refused'}

    def reset(self) -> None:
        """Explicit operator action after topping up or fixing the account."""
        self.account_status = 'available'
        self.consecutive_refusals = self.consecutive_inconclusive = 0
        self.tripped_on = None
