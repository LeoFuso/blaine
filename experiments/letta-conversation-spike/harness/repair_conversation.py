#!/usr/bin/env python3
"""Rebuild a truncated/corrupt Letta local conversation.json (or its dangling context) from the transcript.

  repair_conversation.py STATE CONVERSATION_ID [--dry-run]

Run only while the App Server is stopped. Uses the transcript (messages.jsonl,
append-only and intact in the observed failure) as the source: id and agent from
the entries, timestamps from the first/last entries, in-context ids = messages
after the last compaction entry (compaction summary first). This is spike glue
that depends on Letta's private on-disk format.
"""
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    state, conv = sys.argv[1], sys.argv[2]
    key = f'conversation:{conv}'
    d = Path(state) / 'home/.letta/lc-local-backend/conversations' / base64.urlsafe_b64encode(key.encode()).decode().rstrip('=')
    target = d / 'conversation.json'
    entries = [json.loads(line) for line in (d / 'messages.jsonl').read_text().splitlines() if line.strip()]
    known = {e['message']['id'] for e in entries if isinstance(e.get('message'), dict)}
    existing = None
    try:
        existing = json.loads(target.read_text())
        dangling = [i for i in existing.get('in_context_message_ids') or [] if i not in known]
        if not dangling:
            print(json.dumps({'status': 'conversation.json parses and its context is consistent; nothing to do'}))
            return
    except (OSError, ValueError):
        pass
    messages, in_context, agent = [], [], None
    for entry in entries:
        message = entry.get('message')
        if not isinstance(message, dict):
            continue
        agent = agent or (message.get('metadata') or {}).get('agent_id')
        if entry.get('type') == 'compaction':
            in_context = [message['id']]
            continue
        if message['id'] not in in_context:
            in_context.append(message['id'])
        messages.append(entry)
    header = next(e for e in entries if e.get('type') == 'session')
    now = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    if existing:  # keep every field Letta wrote; only the context list is rebuilt
        existing['in_context_message_ids'] = in_context
        existing['updated_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        if '--dry-run' not in sys.argv:
            tmp = target.with_suffix('.json.repair')
            tmp.write_text(json.dumps(existing, indent=2) + '\n')
            tmp.replace(target)
        print(json.dumps({'status': 'context rebuilt (dangling in_context ids)', 'in_context': len(in_context)}))
        return
    record = {'id': conv, 'agent_id': agent, 'archived': False, 'archived_at': None,
              'created_at': header['timestamp'], 'updated_at': now,
              'last_message_at': messages[-1]['timestamp'] if messages else None,
              'summary': None, 'in_context_message_ids': in_context}
    if '--dry-run' not in sys.argv:
        tmp = target.with_suffix('.json.repair')
        tmp.write_text(json.dumps(record, indent=2) + '\n')
        tmp.replace(target)
    print(json.dumps({'status': 'rebuilt', 'agent_id': agent, 'in_context': len(in_context), 'messages': len(messages)}))


if __name__ == '__main__':
    main()
