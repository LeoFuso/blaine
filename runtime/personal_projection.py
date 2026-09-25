"""Conversation projection v1 (PA-4) — the product presentation contract.

One ordered, cursor-addressed view of a Conversation that every client renders:
messages, Execution Briefs, delegated Tasks (phase, steps, criteria, delivery),
human requests, verified results and the Personal Agent's follow-ups.

Derived and read-only (docs/contracts/conversation-projection.md): built only from
the encrypted Conversation store and the Task control surface's ``inspect``. It
never calls a model, never writes Conversation or Task state, never answers a
human request and never decides completion. Bodies are recomputed on every read;
the store keeps only digests and a monotonic cursor.
"""
from __future__ import annotations

import hashlib
import json

from runtime.kernel.contracts import encode
from runtime.kernel.conversation import ConversationService
from runtime.personal_conversation import short_id

TERMINAL = ('COMPLETED', 'FAILED', 'CANCELLED')
PHASES = ('submitting', 'running', 'waiting_human', 'completed', 'failed', 'cancelled', 'unavailable')


def digest(body: dict) -> str:
    return hashlib.sha256(encode(body)).hexdigest()


def _op_number(effect: dict) -> int:
    try:
        return int(str(effect.get('operation_id', '')).rsplit('/', 1)[-1])
    except ValueError:
        return 0


def _summary(result: dict | None) -> str | None:
    parts = [f'{value} {key}' for key, value in (result or {}).items()]
    return ', '.join(parts) or None


def task_steps(view: dict) -> list[dict]:
    """Closed, fact-only steps from receipts and the verifier. No model text."""
    steps = [{'key': 'brief', 'label': 'Execution Brief admitted', 'status': 'done'}]
    for effect in sorted(view.get('effects') or [], key=_op_number):
        key = f"effect:{_op_number(effect)}"
        status = effect.get('status')
        if effect.get('operation_class') == 'workspace.write':
            path = effect.get('path') or 'file'
            label, state = {
                'awaiting_approval': (f'Approval requested: write {path}', 'waiting'),
                'admitted': (f'Write proposed: {path}', 'in_progress'),
                'dispatched': (f'Writing {path}', 'in_progress'),
                'applied': (f'Wrote {path}', 'done'),
                'conflict': (f'Write conflict on {path} (file changed since planning)', 'failed'),
            }.get(status, (f'Write not performed: {path}', 'failed'))
            step = {'key': key, 'label': label, 'status': state}
            if status == 'not_dispatched' and effect.get('reason'):
                step['detail'] = effect['reason'][:200]
            steps.append(step)
            continue
        profile = effect.get('profile') or 'profile'
        if status in ('admitted', 'dispatched', 'running'):
            steps.append({'key': key, 'label': f'Running {profile}', 'status': 'in_progress'})
        elif status == 'completed' and effect.get('exit_code') == 0:
            steps.append({'key': key, 'label': f'{profile} passed', 'status': 'done',
                          **({'detail': _summary(effect.get('result'))} if effect.get('result') else {})})
        else:
            why = f"exit {effect.get('exit_code')}" if status == 'completed' else status
            steps.append({'key': key, 'label': f'{profile} failed', 'status': 'failed',
                          'detail': ', '.join(p for p in (why, _summary(effect.get('result'))) if p)})
    evaluation = (view.get('completion') or {}).get('payload') or {}
    criteria = evaluation.get('criteria') or []
    if criteria:
        satisfied = sum(1 for c in criteria if c.get('status') in ('satisfied', 'waived'))
        lifecycle = view.get('lifecycle')
        state = ('done' if evaluation.get('outcome') == 'satisfied'
                 else 'failed' if lifecycle in TERMINAL else 'in_progress')
        steps.append({'key': 'verifier', 'label': 'CompletionVerifier', 'status': state,
                      'detail': f'{satisfied}/{len(criteria)} criteria satisfied'})
    return steps


def task_phase(link_state: str, view: dict | None) -> str:
    if link_state == 'submitting':
        return 'submitting'
    if view is None or view.get('lifecycle') in (None, 'UNAVAILABLE'):
        return 'unavailable'
    lifecycle = view['lifecycle']
    if lifecycle in TERMINAL:
        return lifecycle.lower()
    if lifecycle == 'WAITING' and (view.get('pending_human_decision') or {}).get('payload'):
        return 'waiting_human'
    return 'running'


class ConversationProjection:
    def __init__(self, store: ConversationService, agent):
        self.store, self.agent = store, agent
        self._final: dict[str, dict] = {}  # terminal Task views never change; per-process cache

    # -------------------------------------------------------------- sources
    def task_view(self, task_id: str) -> dict | None:
        if task_id in self._final:
            return self._final[task_id]
        try:
            view = self.agent.execute({'operation': 'inspect', 'task_id': task_id})
        except (OSError, ValueError, KeyError):
            return None
        if view.get('lifecycle') in TERMINAL:
            self._final[task_id] = view
        return view

    # -------------------------------------------------------------- build
    def build(self, conversation_id: str) -> list[dict]:
        """Current entries in Conversation order: (order key, entry)."""
        messages = self.store.list_messages(conversation_id, limit=5000)
        position = {m['id']: m['seq'] for m in messages}
        links = {link['message_id']: link for link in self.store.list_task_links(conversation_id)}
        # Follow-up ids are deterministic per (Conversation, Task) — see ResultDelivery.
        followups = {short_id('fup', conversation_id, link['task_id']): link['task_id'] for link in links.values()}
        entries: list[tuple[tuple, dict]] = []
        for message in messages:
            role, anchor = message['role'], (message['seq'], 0)
            if role in ('human', 'agent') and not message['id'].startswith('fup-'):
                entries.append((anchor, {'entry_id': message['id'], 'kind': 'message', 'role': role,
                                         'text': message['content'], 'created_at': message['created_at']}))
            elif role == 'agent':
                entries.append((anchor, {'entry_id': message['id'], 'kind': 'followup',
                                         'task_id': followups.get(message['id']),
                                         'text': message['content'], 'created_at': message['created_at'],
                                         'grounded': 'deterministic summary' not in message['content']}))
            elif role == 'result':
                result = json.loads(message['content'])
                facts = result.get('facts') or {}
                entries.append((anchor, {'entry_id': message['id'], 'kind': 'result',
                    'task_id': facts.get('task_id'), 'lifecycle': facts.get('lifecycle'),
                    'verifier': facts.get('verifier_outcome'), 'criteria': facts.get('criteria', []),
                    'changed_files': facts.get('changed_files', []), 'runs': facts.get('test_runs', []),
                    'diff': facts.get('diff'), 'markdown': result.get('markdown', ''),
                    'created_at': message['created_at']}))
            elif role == 'delegation' and message['id'] in links:
                entries.extend(self.task_entries(anchor, links[message['id']], conversation_id))
        for brief in self.store.list_briefs(conversation_id):
            body = brief['payload']['payload']
            entries.append(((body.get('source_seq', 0), 1), {'entry_id': brief['brief_id'], 'kind': 'brief',
                'status': brief['status'], 'task_id': brief['task_id'], 'objective': body['objective'],
                'deliverable': body['deliverable'], 'inspect': body['inspect'],
                'targeted_tests': body['targeted_tests'], 'constraints': body['constraints'],
                'requested': body['requested']}))
        # Human requests that are no longer pending keep their identity and say so.
        live = {entry['entry_id'] for _, entry in entries}
        for entry_id in self.store.projection_entry_ids(conversation_id):
            if entry_id.startswith('hr:') and entry_id not in live:
                _, task_id, request_id, revision = entry_id.split(':', 3)
                link = next((l for l in links.values() if l['task_id'] == task_id), None)
                view = self.task_view(task_id) if link else None
                anchor = (position.get(link['message_id'], 0), 1) if link else (0, 1)
                entries.append((anchor, {'entry_id': entry_id, 'kind': 'human_request', 'task_id': task_id,
                    'request_id': request_id, 'revision': int(revision),
                    'status': 'closed' if (view or {}).get('lifecycle') in TERMINAL else 'resolved'}))
        entries.sort(key=lambda item: item[0])
        return [entry for _, entry in entries]

    def task_entries(self, anchor: tuple, link: dict, conversation_id: str) -> list[tuple[tuple, dict]]:
        task_id = link['task_id']
        view = self.task_view(task_id) if link['state'] != 'submitting' else None
        brief = self.store.get_brief(conversation_id, link['brief_id']) if link.get('brief_id') else None
        body = (brief or {}).get('payload', {}).get('payload', {})
        evaluation = ((view or {}).get('completion') or {}).get('payload') or {}
        criteria = evaluation.get('criteria') or []
        phase = task_phase(link['state'], view)
        task = {'entry_id': f'task:{task_id}', 'kind': 'task', 'task_id': task_id,
                'brief_id': link.get('brief_id'), 'delegation_message_id': link['message_id'],
                'objective': body.get('objective'), 'deliverable': body.get('deliverable'),
                'phase': phase, 'lifecycle': (view or {}).get('lifecycle'),
                'steps': task_steps(view) if view else [{'key': 'brief', 'label': 'Submitting', 'status': 'in_progress'}],
                'criteria': {'satisfied': sum(1 for c in criteria if c.get('status') in ('satisfied', 'waived')),
                             'total': len(criteria),
                             'items': [{'id': c.get('id'), 'status': c.get('status')} for c in criteria]},
                'delivery': {'submitting': 'pending', 'linked': 'pending'}.get(link['state'], link['state']),
                'revision': (view or {}).get('revision')}
        out = [(anchor, task)]
        human = ((view or {}).get('pending_human_decision') or {}).get('payload')
        if human and phase == 'waiting_human':
            out.append(((anchor[0], 1), {
                'entry_id': f"hr:{task_id}:{human['request_id']}:{human['revision']}", 'kind': 'human_request',
                'task_id': task_id, 'request_id': human['request_id'], 'revision': human['revision'],
                'status': 'pending', 'question': human.get('question'),
                'options': list(human.get('allowed_responses') or [])}))
        return out

    # -------------------------------------------------------------- read
    def read(self, conversation_id: str, after: int = 0) -> dict:
        """Entries changed since ``after`` (full bodies), and the new cursor."""
        if type(after) is not int or after < 0:
            raise ValueError('after must be a non-negative integer cursor')
        if self.store.get_conversation(conversation_id) is None:
            return {'conversation_id': conversation_id, 'cursor': after, 'entries': []}
        entries = self.build(conversation_id)
        stamped = self.store.stamp_projection(conversation_id, {e['entry_id']: digest(e) for e in entries})
        changed = [{**entry, 'seq': stamped[entry['entry_id']]} for entry in entries
                   if stamped[entry['entry_id']] > after]
        cursor = max([after, *(e['seq'] for e in changed)])
        return {'conversation_id': conversation_id, 'cursor': cursor, 'entries': changed}
