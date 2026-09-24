"""TaskResult delivery into the originating Conversation (PA-3).

``ResultDelivery`` observes delegated Tasks through the Personal Agent control
surface and, once a Task is terminal, delivers its authoritative outcome to the
Conversation that delegated it. It owns no Task lifecycle, never retries or
steers a Task, and never decides completion (Restate and the CompletionVerifier
did). It is a projection plus an idempotent, staged append:

    stage 1  terminal Task -> deterministic TaskResult facts -> ``result`` message
             (id ``res-<hash>``) + link ``result_recorded``        [one short commit]
    stage 2  ResultInterpreter asks the local model to explain those facts
             (no transaction open; deterministic fallback on failure)
    stage 3  ``agent`` follow-up (id ``fup-<hash>``) + link ``surfaced`` [one short commit]

A crash between stages is resumed by the next tick; deterministic message ids
and forward-only link states make every stage safe to repeat.
"""
from __future__ import annotations

import difflib
import json
import threading
import time

from runtime.kernel.conversation import ConversationService
from runtime.personal_agent import PersonalAgent
from runtime.personal_conversation import ConversationModel, short_id

TERMINAL = ('COMPLETED', 'FAILED', 'CANCELLED')
DIFF_BYTES = 12000


def result_facts(view: dict, draft: str | None) -> dict:
    """Authoritative facts only: lifecycle, verifier verdicts, effect receipts."""
    completion = (view.get('completion') or {}).get('payload') or {}
    result = (view.get('result') or {}).get('payload') or {}
    effects = view.get('effects') or []
    writes = [e for e in effects if e.get('operation_class') == 'workspace.write']
    execs = [e for e in effects if e.get('operation_class') == 'workspace.exec']
    changed = [{'path': e.get('path'), 'status': e.get('status'), 'before': e.get('before'), 'after': e.get('after')}
               for e in writes]
    facts = {
        'task_id': view.get('task_id'), 'lifecycle': view.get('lifecycle'), 'revision': view.get('revision'),
        'contract_revision': view.get('contract_revision'),
        # CompletionEvaluation v2: per-criterion verdicts and the legality decision.
        'verifier_outcome': completion.get('outcome'),
        'legal_completion': (completion.get('legality') or {}).get('legal'),
        'criteria': [{'id': c.get('id'), 'status': c.get('status'), 'detail': c.get('detail')}
                     for c in completion.get('criteria', [])][:16],
        'result_outcome': result.get('outcome'), 'concerns': (result.get('concerns') or [])[:4],
        'changed_files': changed,
        'test_runs': [{'profile': e.get('profile'), 'args': e.get('args'), 'status': e.get('status'),
                       'exit_code': e.get('exit_code'), 'result': e.get('result')} for e in execs],
    }
    applied = [e for e in writes if e.get('status') == 'applied']
    if draft is not None and applied:
        path = applied[-1].get('path') or 'file'
        before_absent = (applied[-1].get('before') or {}).get('absent') is True
        lines = difflib.unified_diff([] if before_absent else [], draft.splitlines(keepends=True),
                                     fromfile='/dev/null' if before_absent else f'a/{path}', tofile=f'b/{path}')
        diff = ''.join(lines)
        facts['diff'] = {'path': path, 'new_file': before_absent, 'unified': diff[:DIFF_BYTES],
                         'truncated': len(diff) > DIFF_BYTES}
    return facts


def render(facts: dict) -> str:
    """Deterministic human-readable rendering of the facts (no model involved)."""
    lines = [f"**Blaine Task result** `{facts['task_id'][:24]}…` — **{facts['lifecycle']}**"]
    if facts.get('verifier_outcome'):
        lines.append(f"CompletionVerifier: **{facts['verifier_outcome']}**")
    for item in facts['criteria']:
        lines.append(f"- `{item['id']}` {item['status']}" + (f" — {item['detail']}" if item.get('detail') else ''))
    for change in facts['changed_files']:
        lines.append(f"Changed: `{change['path']}` ({change['status']})")
    for run in facts['test_runs']:
        lines.append(f"Ran `{run['profile']}` {' '.join(run['args'] or [])}: exit {run['exit_code']} "
                     f"{json.dumps(run['result']) if run.get('result') else ''}".rstrip())
    for concern in facts['concerns']:
        lines.append(f"Concern: {concern}")
    return '\n'.join(lines)


INTERPRET = '''You are Blaine, the user's Personal Agent. A delegated Task has finished.
Explain its outcome to the user in 2-4 sentences, grounded ONLY in the verified facts
below: lifecycle, CompletionVerifier verdicts, the file actually changed and the tests
actually run. Do not claim anything the facts do not show. If it failed, say what
failed. Do not repeat the full diff. No private reasoning.'''


class ResultInterpreter:
    def __init__(self, model: ConversationModel | None):
        self.model = model

    def interpret(self, facts: dict) -> tuple[str, bool]:
        """(text, grounded_by_model). Falls back to deterministic text on any failure."""
        compact = {k: v for k, v in facts.items() if k != 'diff'}
        if 'diff' in facts:
            compact['diff_summary'] = {'path': facts['diff']['path'], 'new_file': facts['diff']['new_file'],
                                       'added_lines': facts['diff']['unified'].count('\n+') }
        if self.model is not None:
            try:
                return self.model.complete([{'role': 'system', 'content': INTERPRET},
                                            {'role': 'user', 'content': json.dumps(compact)}],
                                           max_tokens=400, temperature=0.2), True
            except (OSError, ValueError, KeyError, TypeError):
                pass
        verdict = facts.get('verifier_outcome') or facts['lifecycle']
        return (f"The delegated Task finished {facts['lifecycle']} (verifier: {verdict}). "
                f"See the verified result above for the changed files and test runs."), False


class ResultDelivery:
    def __init__(self, store: ConversationService, agent: PersonalAgent, interpreter: ResultInterpreter,
                 briefs=None):
        self.store, self.agent, self.interpreter, self.briefs = store, agent, interpreter, briefs
        self._stop = threading.Event()

    def tick(self) -> int:
        delivered = 0
        for link in self.store.open_delegations():
            try:
                delivered += self.advance(link)
            except (OSError, ValueError, KeyError, TypeError):
                continue  # observed again on the next tick; never blocks other Conversations
        return delivered

    def advance(self, link: dict) -> int:
        conversation_id, task_id = link['conversation_id'], link['task_id']
        if link['state'] == 'submitting':
            if self.briefs is not None and link.get('brief_id'):
                self.briefs.reconcile(link)
            return 0
        result_id = short_id('res', conversation_id, task_id)
        if link['state'] == 'linked':
            view = self.agent.execute({'operation': 'inspect', 'task_id': task_id})
            if view.get('lifecycle') not in TERMINAL:
                return 0
            draft = None
            if 'draft' in (view.get('artifacts') or {}):
                try:
                    draft = self.agent.execute({'operation': 'artifact', 'task_id': task_id, 'name': 'draft'})['content']
                except (OSError, ValueError, KeyError):
                    draft = None
            facts = result_facts(view, draft)
            content = json.dumps({'kind': 'TaskResult', 'version': 1, 'facts': facts, 'markdown': render(facts)})
            self.store.record_result(conversation_id, task_id, result_id, content)   # stage 1
        recorded = self.store.get_message(conversation_id, result_id)
        if recorded is None:
            return 0
        facts = json.loads(recorded['content'])['facts']
        text, grounded = self.interpreter.interpret(facts)                         # stage 2 (no txn)
        followup = text if grounded else text + '\n\n_(deterministic summary — the local model was unavailable)_'
        self.store.record_followup(conversation_id, task_id, short_id('fup', conversation_id, task_id),
                                   followup)                                      # stage 3
        return 1

    def run_forever(self, interval: float = 3.0) -> None:
        while not self._stop.is_set():
            self.tick()
            self._stop.wait(interval)

    def stop(self) -> None:
        self._stop.set()

    def start(self, interval: float = 3.0) -> threading.Thread:
        thread = threading.Thread(target=self.run_forever, args=(interval,), name='result-delivery', daemon=True)
        thread.start()
        return thread
