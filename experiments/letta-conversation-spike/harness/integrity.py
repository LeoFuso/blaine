#!/usr/bin/env python3
"""File-level integrity check of Letta local-backend conversation state.

  integrity.py STATE_DIR [CONVERSATION_ID ...]

For each conversation directory: every messages.jsonl line parses; entry types;
message ids unique; user otids unique (duplicate user turn detection); tool calls
paired with returns; compaction entries and whether the pre-compaction messages
are still in the transcript; conversation.json parses and its
in_context_message_ids all exist in the transcript; trailing partial line.
Prints one JSON object per conversation.
"""
import base64
import json
import sys
from collections import Counter
from pathlib import Path


def conversation_dirs(state):
    root = Path(state) / 'home/.letta/lc-local-backend/conversations'
    for d in sorted(root.iterdir()):
        name = base64.urlsafe_b64decode(d.name + '=' * (-len(d.name) % 4)).decode(errors='replace')
        yield name, d


def check(name, d):
    report = {'conversation': name, 'dir': d.name}
    path = d / 'messages.jsonl'
    if not path.exists():
        report['messages_jsonl'] = 'absent'
        return report
    raw = path.read_bytes()
    report['bytes'] = len(raw)
    report['ends_with_newline'] = raw.endswith(b'\n')
    lines = raw.split(b'\n')
    if lines and lines[-1] == b'':
        lines = lines[:-1]
    entries, bad = [], []
    for i, line in enumerate(lines):
        try:
            entries.append(json.loads(line))
        except ValueError:
            bad.append({'line': i + 1, 'bytes': len(line), 'head': line[:80].decode(errors='replace')})
    report['lines'] = len(lines)
    report['unparseable_lines'] = bad
    report['entry_types'] = dict(Counter(e.get('type') for e in entries))
    messages = [e['message'] for e in entries if e.get('type') == 'message' and isinstance(e.get('message'), dict)]
    compaction_messages = [e['message'] for e in entries if e.get('type') == 'compaction' and isinstance(e.get('message'), dict)]
    ids = Counter(m.get('id') for m in messages)
    report['messages'] = len(messages)
    report['duplicate_message_ids'] = [k for k, v in ids.items() if v > 1]
    otids = Counter(m.get('otid') for m in messages if m.get('role') == 'user' and m.get('otid'))
    report['duplicate_user_otids'] = [k for k, v in otids.items() if v > 1]
    calls, returns = [], set()
    for m in messages:
        for part in (m.get('content') if isinstance(m.get('content'), list) else []):
            if isinstance(part, dict) and part.get('type') in ('toolCall', 'tool_call', 'tool_use'):
                calls.append(part.get('id') or part.get('toolCallId'))
        if m.get('role') in ('toolResult', 'tool') and (m.get('toolCallId') or m.get('tool_call_id')):
            returns.add(m.get('toolCallId') or m.get('tool_call_id'))
    report['tool_calls'] = len(calls)
    report['tool_calls_without_return'] = [c for c in calls if c not in returns]
    compactions = [e for e in entries if e.get('type') not in ('message', 'session')]
    report['non_message_entries'] = [{'type': e.get('type'), 'keys': sorted(e)[:8]} for e in compactions][:10]
    report['compaction_summaries'] = len(compaction_messages)
    conv_path = d / 'conversation.json'
    try:
        conv = json.loads(conv_path.read_text())
        in_ctx = conv.get('in_context_message_ids') or []
        known = set(ids) | {m.get('id') for m in compaction_messages}
        report['conversation_json'] = 'ok'
        report['in_context'] = len(in_ctx)
        report['in_context_missing_from_transcript'] = [i for i in in_ctx if i not in known]
    except (OSError, ValueError) as error:
        report['conversation_json'] = f'error: {type(error).__name__}'
    return report


def main():
    state = sys.argv[1]
    wanted = set(sys.argv[2:])
    for name, d in conversation_dirs(state):
        if wanted and not any(name.endswith(w) for w in wanted):
            continue
        print(json.dumps(check(name, d)))


if __name__ == '__main__':
    main()
