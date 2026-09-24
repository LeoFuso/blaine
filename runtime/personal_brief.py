"""Execution Brief (PA-3): agreed conversational intent -> one bounded durable Task.

The Personal Agent compiles the recent Conversation into an ExecutionBrief v1 and
the user explicitly confirms it. The brief *requests* authority; it never grants
it. On confirmation the grant, profiles, approval policy and completion contract
are derived deterministically from the operator's reviewed coding policy (the
deployment config), and a canonical TaskRequest is submitted to the existing
Personal Agent control surface. Restate owns the Task from then on.

One bounded coding shape is supported: the Worker authors one file inside the
allowed paths, the kernel writes it (human-approved when policy says so), and
reviewed test profiles plus an existing canonical hermetic suite qualify it.
Completion is decided only by the CompletionVerifier over that evidence.

Nothing here holds a database transaction across model inference or Task
submission: the brief and the write-ahead delegation record are committed first,
then the Task is submitted, then the link advances. Every step is idempotent.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import PurePosixPath

from runtime.kernel.contracts import encode, message, text
from runtime.kernel.conversation import ConversationService
from runtime.kernel.effects import confined
from runtime.kernel.model import strict_json, strip_fenced_json
from runtime.personal_agent import PersonalAgent, task_identity
from runtime.personal_conversation import ConversationModel, history, short_id

CAPABILITIES = ['artifact.write', 'worker.run', 'workspace.read', 'workspace.write', 'workspace.exec']
TASK_TYPE = {'template': 'implementation', 'version': 1}
WORKER_INPUT = 'worker-input'
DRAFT = 'draft'
MAX_TESTS = 2
MAX_INSPECT = 2


class CodingPolicy:
    """The operator's reviewed coding workspaces and exec profiles (deployment config)."""

    def __init__(self, deployment: dict):
        self.workspaces = deployment.get('coding_workspaces') or {}
        self.profiles = deployment.get('exec_profiles') or {}
        for name, spec in self.workspaces.items():
            for key in ('root', 'allowed_paths', 'targeted_profile'):
                if key not in spec:
                    raise ValueError(f'Coding workspace {name} lacks {key}')
            for profile in [spec['targeted_profile'], *spec.get('canonical_profiles', [])]:
                if profile not in self.profiles:
                    raise ValueError(f'Coding workspace {name} names unknown profile {profile}')

    def workspace(self, workspace_id: str) -> dict:
        spec = self.workspaces.get(workspace_id)
        if spec is None:
            raise ValueError('Workspace is not in the reviewed coding policy')
        return spec

    def digest(self, workspace_id: str) -> str:
        spec = self.workspace(workspace_id)
        profiles = {name: self.profiles[name] for name in [spec['targeted_profile'], *spec.get('canonical_profiles', [])]}
        return 'sha256:' + hashlib.sha256(encode({'workspace': {k: v for k, v in spec.items() if k != 'root'},
                                      'profiles': profiles})).hexdigest()

    def describe(self) -> str:
        lines = []
        for name, spec in self.workspaces.items():
            tests = self.profiles[spec['targeted_profile']].get('allowed_args', [])
            lines.append(f"- workspace_id {name}: {spec.get('description', '')}\n"
                         f"  deliverable must be under: {', '.join(spec['allowed_paths'])}\n"
                         f"  readable paths: {', '.join(spec.get('inspect_paths', ['(any file)']))}\n"
                         f"  targeted test files (choose from): {', '.join(tests)}")
        return '\n'.join(lines)


def under(path: str, prefixes: list[str]) -> bool:
    return any(path == p or (p.endswith('/') and path.startswith(p)) for p in prefixes)


def validate_brief(raw: dict, policy: CodingPolicy) -> dict:
    """Strict ExecutionBrief v1 body compiled by the model. Rejected, never repaired."""
    if not isinstance(raw, dict):
        raise ValueError('Brief must be an object')
    allowed = {'workspace_id', 'objective', 'constraints', 'deliverable_path', 'inspect_paths', 'targeted_tests'}
    if raw.keys() - allowed or not {'objective', 'deliverable_path', 'targeted_tests'} <= raw.keys():
        raise ValueError('Brief has unexpected or missing fields')
    workspace_id = raw.get('workspace_id') or (next(iter(policy.workspaces)) if len(policy.workspaces) == 1 else None)
    spec = policy.workspace(workspace_id)
    objective = text(raw['objective'], 600)
    constraints = raw.get('constraints') or []
    if not isinstance(constraints, list) or len(constraints) > 5:
        raise ValueError('Expected at most five constraints')
    constraints = [text(item, 240) for item in constraints]
    path = confined(raw['deliverable_path'])
    if not under(path, spec['allowed_paths']):
        raise ValueError('Deliverable is outside the reviewed allowed paths')
    inspect = raw.get('inspect_paths') or []
    if not isinstance(inspect, list) or len(inspect) > MAX_INSPECT:
        raise ValueError('Expected at most two files to inspect')
    inspect = [confined(p) for p in inspect]
    if any('.git' in PurePosixPath(p).parts for p in inspect) or (
            'inspect_paths' in spec and not all(under(p, spec['inspect_paths']) for p in inspect)):
        raise ValueError('Inspection path is outside the reviewed readable paths')
    tests = raw['targeted_tests']
    reviewed = policy.profiles[spec['targeted_profile']].get('allowed_args', [])
    if not isinstance(tests, list) or not 1 <= len(tests) <= MAX_TESTS or not set(tests) <= set(reviewed):
        raise ValueError('Targeted tests must be chosen from the reviewed profile allowlist')
    return {'workspace_id': workspace_id, 'objective': objective, 'constraints': constraints,
            'deliverable': {'workspace_id': workspace_id, 'path': path}, 'inspect': inspect,
            'targeted_tests': list(tests)}


COMPILE = '''You compile an agreed coding request from the conversation into ONE JSON object.
Output only JSON with exactly these fields:
{"workspace_id": string, "objective": string (<=600 bytes, what the file must achieve),
 "constraints": [<=5 short strings], "deliverable_path": string (the ONE file the worker writes),
 "inspect_paths": [<=2 existing files the worker must read first],
 "targeted_tests": [1..2 test files, chosen ONLY from the reviewed list]}
Use only what the user agreed to. Do not invent capabilities, commands or permissions.
Reviewed coding policy:
'''


class BriefService:
    def __init__(self, store: ConversationService, model: ConversationModel, agent: PersonalAgent,
                 policy: CodingPolicy):
        self.store, self.model, self.agent, self.policy = store, model, agent, policy

    # ------------------------------------------------------------ propose
    def propose(self, conversation_id: str) -> dict:
        messages = self.store.list_messages(conversation_id, limit=500)
        if not any(m['role'] == 'human' for m in messages):
            raise ValueError('Nothing has been discussed yet')
        source_seq = messages[-1]['seq']
        brief_id = short_id('brf', conversation_id, str(source_seq), length=20)
        existing = self.store.get_brief(conversation_id, brief_id)
        if existing is not None:
            return existing
        turns = history(messages)
        # No transaction is open here; the Conversation is already durable.
        raw = self.model.complete([{'role': 'system', 'content': COMPILE + self.policy.describe()}, *turns,
                                   {'role': 'user', 'content': 'Compile the agreed request now. JSON only.'}],
                                  max_tokens=600, temperature=0)
        body = validate_brief(strict_json(strip_fenced_json(raw)), self.policy)
        payload = message('ExecutionBrief', {'brief_id': brief_id, 'conversation_id': conversation_id,
            'source_seq': source_seq, **body, 'requested': self.requested(body['workspace_id'])})
        return self.store.save_brief(conversation_id, brief_id, payload)

    def requested(self, workspace_id: str) -> dict:
        spec = self.policy.workspace(workspace_id)
        return {'capabilities': CAPABILITIES, 'workspaces': [workspace_id],
                'profiles': [spec['targeted_profile'], *spec.get('canonical_profiles', [])],
                'ask_before': list(spec.get('ask_before', []))}

    def reject(self, conversation_id: str, brief_id: str) -> dict:
        brief = self.require(conversation_id, brief_id)
        if brief['status'] == 'proposed':
            self.store.set_brief_status(conversation_id, brief_id, 'rejected')
        return self.store.get_brief(conversation_id, brief_id)

    def require(self, conversation_id: str, brief_id: str) -> dict:
        brief = self.store.get_brief(conversation_id, brief_id)
        if brief is None:
            raise ValueError('Unknown brief')
        return brief

    # ------------------------------------------------------------ confirm
    def confirm(self, conversation_id: str, brief_id: str) -> dict:
        """The user's explicit execute act. Idempotent; safe to repeat after a crash."""
        brief = self.require(conversation_id, brief_id)
        if brief['status'] == 'rejected':
            raise ValueError('The brief was rejected')
        body = brief['payload']['payload']
        # Re-validate against the *current* policy: a brief carries no authority.
        validate_brief({'workspace_id': body['workspace_id'], 'objective': body['objective'],
                        'constraints': body['constraints'], 'deliverable_path': body['deliverable']['path'],
                        'inspect_paths': body['inspect'], 'targeted_tests': body['targeted_tests']}, self.policy)
        request_id = 'pa3-' + hashlib.sha256(f'{conversation_id}\x1f{brief_id}'.encode()).hexdigest()[:40]
        task_id = task_identity(request_id)
        delegation_id = short_id('dlg', conversation_id, brief_id)
        summary = json.dumps({'brief_id': brief_id, 'task_id': task_id, 'objective': body['objective'],
                              'deliverable': body['deliverable'], 'targeted_tests': body['targeted_tests']})
        # 1. Write-ahead: committed before submission, so a crash cannot orphan the Task.
        self.store.begin_delegation(conversation_id, task_id, delegation_id, summary, brief_id)
        # 2. Submission (no local transaction open). Same request id => same Task.
        created = self.agent.execute({'operation': 'create', 'request_id': request_id,
                                      'task_request': self.task_request(task_id, body)})
        # 3. Advance provenance.
        self.store.advance_link(conversation_id, task_id, 'linked')
        self.store.set_brief_status(conversation_id, brief_id, 'confirmed', task_id)
        return {'task_id': task_id, 'submission': created.get('submission'), 'delegation_message_id': delegation_id,
                'brief': self.store.get_brief(conversation_id, brief_id)}

    def reconcile(self, link: dict) -> None:
        """Finish a write-ahead delegation whose submission outcome was not recorded."""
        brief = self.require(link['conversation_id'], link['brief_id'])
        body = brief['payload']['payload']
        state = self.agent.execute({'operation': 'inspect', 'task_id': link['task_id']})
        if state.get('lifecycle') == 'UNAVAILABLE':
            request_id = 'pa3-' + hashlib.sha256(
                f"{link['conversation_id']}\x1f{link['brief_id']}".encode()).hexdigest()[:40]
            self.agent.execute({'operation': 'create', 'request_id': request_id,
                                'task_request': self.task_request(link['task_id'], body)})
        self.store.advance_link(link['conversation_id'], link['task_id'], 'linked')
        self.store.set_brief_status(link['conversation_id'], link['brief_id'], 'confirmed', link['task_id'])

    # ------------------------------------------------------------ Task shape
    def task_request(self, task_id: str, body: dict) -> dict:
        workspace_id = body['workspace_id']
        spec = self.policy.workspace(workspace_id)
        path = body['deliverable']['path']
        targeted = spec['targeted_profile']
        canonical = list(spec.get('canonical_profiles', []))
        packet = message('WorkerInput', {'task_id': task_id,
            'objective': text(f"Author the complete file {path}. {body['objective']}"[:1000], 1024),
            'context': [c for c in [
                {'source': 'execution-brief:constraints',
                 'content': '\n'.join(body['constraints'])[:2000]} if body['constraints'] else None,
                {'source': 'execution-brief:acceptance',
                 'content': (f"Only {path} may change. It must pass: {', '.join(body['targeted_tests'])}. "
                             'Read the admitted artifacts for the exact APIs; do not invent imports.')[:2000]},
            ] if c],
            'output': {'kind': 'file', 'path': path}})
        packet_text = encode(packet).decode()
        reads = ''.join(f'workspace.read {{form:"file",workspace_id:"{workspace_id}",path:"{p}",artifact:"source-{i}"}}; '
                        for i, p in enumerate(body['inspect'], 1))
        procedure = (f"Execution Brief: {body['objective']} Procedure: 1) {reads or 'no reads; '}"
                     f"2) worker.run packet_ref=<{WORKER_INPUT} ref>, artifact={DRAFT}, context_refs=<source refs>; "
                     f"3) workspace.write {path} in {workspace_id} with content_ref=<{DRAFT} ref> and precondition "
                     f"absent (new file) or the read receipt; 4) workspace.exec {targeted} args {body['targeted_tests']}; "
                     + ''.join(f'{5 + i}) workspace.exec {name}; ' for i, name in enumerate(canonical))
                     + 'then COMPLETE. If a step fails, fix the draft and repeat from 2.')
        objective = procedure.encode()[:1024].decode(errors='ignore')
        digest = hashlib.sha256(packet_text.encode()).hexdigest()
        criterion = 'The human-confirmed Execution Brief is admitted as the Worker input'
        task_spec = message('TaskSpec', {'objective': objective,
            'completion': [{'criterion': criterion, 'evidence': {'artifact': WORKER_INPUT, 'sha256': digest}}],
            'capabilities': CAPABILITIES, 'autonomy': {'allowed': CAPABILITIES}})
        template = {'source': 'task_type', 'ref': f"{TASK_TYPE['template']}@{TASK_TYPE['version']}"}
        policy_ref = {'source': 'operator_rule', 'ref': f'coding-policy:{workspace_id}',
                      'source_digest': self.policy.digest(workspace_id)}
        allowed = spec['allowed_paths']
        criteria = [
            {'id': 'c1', 'requirement': criterion, 'level': 'REQUIRED', 'provenance': {'source': 'user'},
             'verifier': {'kind': 'artifact_digest', 'version': 1, 'artifact': WORKER_INPUT, 'sha256': digest}},
            {'id': 'no-unauthorized-effect', 'level': 'REQUIRED', 'provenance': {**template, 'invariant': True},
             'requirement': 'Only authorized target effects were admitted, inside the Task workspace, and all are reconciled.',
             'verifier': {'kind': 'capability_journal', 'version': 1, 'predicates': [
                 {'name': 'no_target_effect', 'allowed': ['worker.run', 'workspace.write', 'workspace.exec']},
                 {'name': 'workspace_subset'}, {'name': 'admitted_before_observed'}, {'name': 'effects_reconciled'}]}},
            {'id': 'change-made', 'level': 'REQUIRED', 'provenance': {'source': 'user'},
             'requirement': f'{path} was written with evidence, and nothing outside the allowed paths changed.',
             'verifier': {'kind': 'change_set', 'version': 1, 'workspace_id': workspace_id, 'predicates': [
                 {'name': 'changed', 'paths': [path]}, {'name': 'only_paths', 'allowed': allowed},
                 {'name': 'evidence_complete'}]}},
            {'id': 'tests-pass', 'level': 'REQUIRED', 'provenance': {'source': 'user'},
             'requirement': f"The targeted tests {', '.join(body['targeted_tests'])} passed after the last change.",
             'verifier': {'kind': 'capability_result', 'version': 1, 'operation_class': 'workspace.exec',
                          'profile': targeted, 'predicates': [{'name': 'exit_code', 'equals': 0},
                              {'name': 'result_after_last_change'}, {'name': 'cleanup_confirmed'}]}},
        ] + [
            {'id': f'canonical-{i}', 'level': 'REQUIRED', 'provenance': policy_ref,
             'requirement': f'The existing canonical hermetic suite profile {name} passed after the last change.',
             'verifier': {'kind': 'capability_result', 'version': 1, 'operation_class': 'workspace.exec',
                          'profile': name, 'predicates': [{'name': 'exit_code', 'equals': 0},
                              {'name': 'result_after_last_change'}, {'name': 'cleanup_confirmed'}]}}
            for i, name in enumerate(canonical, 1)]
        contract = message('CompletionContract', {'task_id': task_id, 'revision': 0, 'previous_ref': None,
            'amendment_ref': None, 'task_type': TASK_TYPE, 'criteria': criteria})
        grant = {'capabilities': CAPABILITIES, 'workspaces': [workspace_id], 'profiles': [targeted, *canonical],
                 'escalation_binding': None}
        if spec.get('ask_before'):
            grant['ask_before'] = list(spec['ask_before'])
        return message('TaskRequest', {'task_spec': task_spec, 'grant': grant, 'contract': contract,
            'initial_action': {'type': 'INVOKE_CAPABILITY', 'capability': 'artifact.write',
                               'input': {'name': WORKER_INPUT, 'content': packet_text}}})
