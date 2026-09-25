"""Transport-neutral Task controls. No sessions, Task ledger, or model loop."""
import hashlib
import json
import time
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
from urllib.parse import urlsplit
from uuid import uuid4

from runtime.kernel.contracts import accept_task_request, encode, fields, identifier, message, text
from runtime.kernel.events import safe_prepare, safe_publish
from runtime.task import summarize_objective

# The Personal Agent binding speaks for the Task's user over its private session;
# it has no operator or project-policy principal to establish.
USER_ACTOR = {'kind': 'user', 'via': 'modify-constraints', 'binding': 'personal-agent'}


def task_identity(request_id):
    return 'task-' + hashlib.sha256(identifier(request_id).encode()).hexdigest()


def small_request(objective):
    """A deterministic local operation with independently verifiable exact output."""
    text(objective, 1024)
    content = encode(summarize_objective(objective)).decode()
    spec = message('TaskSpec', {'objective': objective,
        'completion': [{'criterion': 'Exact deterministic objective summary',
            'evidence': {'artifact': 'answer', 'sha256': hashlib.sha256(content.encode()).hexdigest()}}],
        'capabilities': ['text.stats'], 'autonomy': {'allowed': ['text.stats']}})
    # Trusted envelope: the grant bounds effective authority to exactly what this
    # intake intends, and authorizes no escalation binding.
    return message('TaskRequest', {'task_spec': spec, 'initial_action': {
        'type': 'INVOKE_CAPABILITY', 'capability': 'text.stats',
        'input': {'text': objective}},
        'grant': {'capabilities': ['text.stats'], 'escalation_binding': None}})


def decision_request(request_id, question):
    task_id = task_identity(request_id)
    human = message('HumanDecisionRequest', {'task_id': task_id, 'origin_task_id': task_id,
        'request_id': 'decision-1', 'revision': 0, 'question': question,
        'allowed_responses': ['YES', 'NO']})
    spec = message('TaskSpec', {'objective': question,
        'completion': [{'criterion': 'Scoped human response recorded', 'evidence': {
            'artifact': 'response', 'verifier': 'human_response', 'request': human}}],
        'capabilities': ['human.request'], 'autonomy': {'allowed': ['human.request']}})
    return message('TaskRequest', {'task_spec': spec, 'initial_action': {
        'type': 'INVOKE_CAPABILITY', 'capability': 'human.request', 'input': {'request': human}},
        'grant': {'capabilities': ['human.request'], 'escalation_binding': None}})


class ControlRejected(ValueError):
    """A definite rejection, without copying a private server error body."""


class RestateBinding:
    def __init__(self, ingress='http://127.0.0.1:48080'):
        url = urlsplit(ingress)
        if (url.scheme != 'http' or url.hostname != '127.0.0.1' or url.username
                or url.password or url.path or url.query or url.fragment):
            raise ValueError('D2 requires a loopback Restate ingress; use trusted SSH for remote ACP')
        self.ingress = ingress
        self.opener = build_opener(ProxyHandler({}))

    def call(self, task_id, handler, body=None):
        identifier(task_id)
        path = f'/CognitiveTaskV1/{task_id}/{handler}'
        request = Request(self.ingress + path, data=encode(body) if body is not None else None,
            headers={'Content-Type': 'application/json'} if body is not None else {}, method='POST')
        try:
            with self.opener.open(request, timeout=10) as response:
                return json.load(response)
        except HTTPError as error:
            if 400 <= error.code < 500:
                raise ControlRejected(f'Control request rejected (HTTP {error.code})') from error
            raise


class PersonalAgent:
    # Bounded wait for a Task admitted by another caller to become inspectable.
    admission_polls = 50
    admission_poll_seconds = 0.1

    def __init__(self, binding, publisher=None):
        self.binding, self.publisher = binding, publisher

    def admitted_state(self, task_id):
        """Inspect until the admitted run has initialized, or give up (None)."""
        for attempt in range(self.admission_polls):
            state = self.binding.call(task_id, 'inspect')
            if state['lifecycle'] != 'UNAVAILABLE':
                return state
            if attempt + 1 < self.admission_polls:
                time.sleep(self.admission_poll_seconds)
        return None

    def execute(self, request):
        task_id = 'unassigned'
        outcome = 'rejected'
        operation = 'invalid'
        try:
            fields(request, {'operation'}, {'request_id', 'task_request', 'task_id', 'response', 'name', 'amendment'})
            operation = text(request['operation'], 32)
            if operation == 'create':
                fields(request, {'operation', 'request_id', 'task_request'})
                task_id = task_identity(request['request_id'])
                raw = request['task_request']
                spec, parent, _grant = accept_task_request(raw, task_id)
                if parent is not None:
                    raise ValueError('Child Tasks are submitted by their parent runtime')
                for criterion in spec['completion']:
                    evidence = criterion['evidence']
                    if evidence.get('verifier') == 'human_response' and evidence['request']['payload']['task_id'] != task_id:
                        raise ValueError('Human request Task identity mismatch')
                digest = hashlib.sha256(encode(raw)).hexdigest()
                before = self.binding.call(task_id, 'inspect')
                if before['lifecycle'] != 'UNAVAILABLE':
                    if before.get('request_digest') != digest:
                        raise ValueError('Request identity already belongs to different input')
                    outcome = 'accepted'
                    return {'task_id': task_id, 'submission': 'EXISTING', 'state': before}
                outcome = 'uncertain'
                receipt = self.binding.call(task_id, 'run/send', raw)
                # The workflow key admits exactly one main invocation, atomically. Only
                # this caller's own admission is SUBMITTED (transport acceptance, not a
                # claim that TaskSpec is persisted yet). A concurrent or earlier caller
                # won otherwise: this input was discarded, so converge on that Task.
                if isinstance(receipt, dict) and receipt.get('status') == 'Accepted':
                    outcome = 'submitted'
                    return {'task_id': task_id, 'submission': 'SUBMITTED', 'receipt': receipt}
                before = self.admitted_state(task_id)
                if before is None:
                    raise ValueError(f'Submission uncertain for {task_id}: another request was admitted '
                                     'first and is not yet inspectable; retry the same request_id and input')
                if before.get('request_digest') != digest:
                    raise ValueError('Request identity already belongs to different input')
                outcome = 'accepted'
                return {'task_id': task_id, 'submission': 'EXISTING', 'state': before}
            task_id = identifier(request.get('task_id'))
            if operation in ('inspect', 'result', 'cancel'):
                fields(request, {'operation', 'task_id'})
                result = self.binding.call(task_id, 'cancel' if operation == 'cancel' else 'inspect')
            elif operation == 'artifact':
                fields(request, {'operation', 'task_id', 'name'})
                identifier(request['name'])
                result = self.binding.call(task_id, 'artifact', {'name': request['name']})
            elif operation in ('respond', 'workspace-result', 'signal'):
                fields(request, {'operation', 'task_id', 'response'})
                handler = {'respond': 'submit_human_response', 'workspace-result': 'submit_workspace_result',
                           'signal': 'submit_input'}[operation]
                result = self.binding.call(task_id, handler, request['response'])
            elif operation == 'amend':
                # This binding's principal is the Task's user, so it can only ever
                # establish user authority. The amendment content is forwarded as
                # untrusted data; the kernel rejects any authority field inside it.
                fields(request, {'operation', 'task_id', 'amendment'})
                result = self.binding.call(task_id, 'amend_contract', message(
                    'CompletionContractAmendmentSubmission', {'actor': USER_ACTOR, 'amendment': request['amendment']}))
            else:
                raise ValueError('Unsupported Task control operation')
            outcome = 'accepted'
            return result
        except ControlRejected:
            outcome = 'rejected'
            raise
        except OSError as error:
            if outcome == 'uncertain':
                raise ValueError(f'Submission uncertain for {task_id}; retry the same request_id and input') from error
            raise
        finally:
            if self.publisher:
                event = safe_prepare(task_id=task_id, run_id='control-' + uuid4().hex,
                    step_id=operation if operation in {'create', 'inspect', 'result', 'cancel', 'artifact', 'respond', 'workspace-result', 'signal', 'amend'} else 'invalid',
                    event_type='personal_agent.control', outcome=outcome,
                    producer={'kind': 'deterministic_application', 'component': 'blaine.personal_agent'})
                safe_publish(self.publisher, event)
