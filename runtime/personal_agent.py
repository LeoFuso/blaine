"""Transport-neutral Task controls. No sessions, Task ledger, or model loop."""
import hashlib
import json
from urllib.request import Request, build_opener, ProxyHandler
from urllib.error import HTTPError
from urllib.parse import urlsplit
from uuid import uuid4

from runtime.kernel.contracts import accept_task_request, encode, fields, identifier, message, text
from runtime.kernel.events import safe_prepare, safe_publish
from runtime.task import summarize_objective


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
    return message('TaskRequest', {'task_spec': spec, 'initial_action': {
        'type': 'INVOKE_CAPABILITY', 'capability': 'text.stats',
        'input': {'text': objective}}})


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
        'type': 'INVOKE_CAPABILITY', 'capability': 'human.request', 'input': {'request': human}}})


def local_summary_request(objective, marker, limit_words):
    """PoC Task shape that exercises the deployment's real local cognition.

    The objective is the material to summarize plus a word limit and a marker
    instruction; the local model must produce a summary that embeds the
    objective (its real material) and the marker. Completion uses the bounded
    local_model_summary verifier (objective embedded + marker present + bounded
    word count), the existing artifact evidence path. Unlike
    small_request/decision_request there is no initial_action: the kernel
    invokes its configured cognition adapter (LocalModelCognition in the
    canonical D2 deployment) to decide every turn. A bounded PoC fixture, not a
    general open-ended contract.
    """
    text(objective, 1024)
    identifier(marker)
    if type(limit_words) is not int or limit_words < 1 or limit_words > 40:
        raise ValueError('Expected a bounded summary word limit (1..40)')
    instruction = (f'Summarize the following material in at most {limit_words} words: {objective} '
                   f'End your summary with the exact marker: {marker}')
    spec = message('TaskSpec', {'objective': instruction,
        'completion': [{'criterion': 'Local-model summary of the material, marker present, bounded length',
            'evidence': {'artifact': 'answer', 'verifier': 'local_model_summary',
                         'objective': objective, 'marker': marker, 'max_words': limit_words + 5}}],
        'capabilities': ['artifact.write', 'artifact.read'],
        'autonomy': {'allowed': ['artifact.write', 'artifact.read']}})
    # A bare TaskSpec (no initial_action) so the kernel calls its cognition
    # adapter for every turn, including the first.
    return spec


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
    def __init__(self, binding, publisher=None):
        self.binding, self.publisher = binding, publisher

    def execute(self, request):
        task_id = 'unassigned'
        outcome = 'rejected'
        operation = 'invalid'
        try:
            fields(request, {'operation'}, {'request_id', 'task_request', 'task_id', 'response', 'name'})
            operation = text(request['operation'], 32)
            if operation == 'create':
                fields(request, {'operation', 'request_id', 'task_request'})
                task_id = task_identity(request['request_id'])
                raw = request['task_request']
                spec, parent = accept_task_request(raw, task_id)
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
                outcome = 'submitted'
                # This is transport acceptance, not a claim that TaskSpec is persisted yet.
                return {'task_id': task_id, 'submission': 'SUBMITTED', 'receipt': receipt}
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
                    step_id=operation if operation in {'create', 'inspect', 'result', 'cancel', 'artifact', 'respond', 'workspace-result', 'signal'} else 'invalid',
                    event_type='personal_agent.control', outcome=outcome,
                    producer={'kind': 'deterministic_application', 'component': 'blaine.personal_agent'})
                safe_publish(self.publisher, event)
