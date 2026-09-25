#!/usr/bin/env bash
# Copy concise spike results from scratch state into evidence/, sanitized.
# Scratch paths become $SCRATCH; any App Server capability token found aborts.
set -euo pipefail
: "${SPIKE_SCRATCH:?}"
HERE=$(dirname "$(realpath "$0")")
EV=$(realpath "$HERE/../evidence")
ST="$SPIKE_SCRATCH/state"
mkdir -p "$EV"/{01-local-and-tools,02-delegation-and-crash-b,03-human-decision,04-durability,05-projection,06-concurrency,07-acp-and-relay,08-isolation-egress-mods-memory,09-line-of-work,10-binding-ledgers}
copy() { # src dest
  sed -e "s#$SPIKE_SCRATCH#\$SCRATCH#g" -e "s#$HOME#\$HOME#g" "$1" > "$EV/$2"
}
copy "$ST/s1/probe01.json" 01-local-and-tools/probe01-basic-local-turn.json
copy "$ST/s1/probe02.json" 01-local-and-tools/probe02-default-toolset-vs-allowlist.json
copy "$ST/s1/probe03.json" 01-local-and-tools/probe03-toolset-none.json
copy "$ST/s1/probe05-builtin.json" 01-local-and-tools/probe05-approval-builtin-read.json
copy "$ST/s1/probe05-external.json" 01-local-and-tools/probe05-approval-external-tool.json
copy "$ST/s3/work/unoffered-tools.json" 01-local-and-tools/probe13-unoffered-tool-calls.json
copy "$ST/s3/work/default-conversation-canary.json" 01-local-and-tools/default-conversation-unrestricted-exec-canary.json
printf 'canary written by the scripted model via exec_command in a default (unhardened) conversation:\n%s\n' "$(cat "$ST/s3/work/CANARY-default-conversation")" > "$EV/01-local-and-tools/default-conversation-canary-file.txt"
copy "$ST/s1/probe04.json" 02-delegation-and-crash-b/probe04-discussion-then-delegation.json
for f in crashB-toolcall crashB-anchor crashB-reconcile; do copy "$ST/s2/work/$f.json" "02-delegation-and-crash-b/$f.json"; done
for f in h1a h1b h1c h1d h1e h1c-contaminated h1d-contaminated h1e-contaminated h1b-alwaysask h1c-alwaysask h1d-alwaysask h3; do copy "$ST/s2/work/$f.json" "03-human-decision/$f.json"; done
copy "$ST/s3/work/crash-state.json" 04-durability/crash-a-append-and-update-kills.json
copy "$ST/s3/work/inject-conversation-json.json" 04-durability/inject-conversation-json-truncation.json
for c in C0 C1 C2 C3; do copy "$ST/s3/work/compaction-$c.json" "04-durability/crash-c-compaction-$c.json"; done
copy "$ST/s3/work/second-process.json" 04-durability/second-process-same-state.json
for d in D1 D2 D3; do copy "$ST/s3/work/projector-$d.json" "05-projection/crash-d-projector-$d.json"; done
copy "$ST/s3/work/two-clients.json" 06-concurrency/probe14-two-clients.json
copy "$ST/s2/work/acp-0.8.17.json" 07-acp-and-relay/acp-letta-acp-sdk-0.8.17-override.json
copy "$ST/s2/work/acp-stderr-0.7.8.txt" 07-acp-and-relay/acp-letta-acp-0.1.11-unchanged-stderr.txt
copy "$ST/s2/work/acp-stderr-0.8.17.txt" 07-acp-and-relay/acp-letta-acp-sdk-0.8.17-stderr.txt
copy "$ST/s2/work/relay-frames.jsonl" 07-acp-and-relay/relay-frames.jsonl
copy "$ST/s2/work/relay-host-stderr.txt" 07-acp-and-relay/relay-host-stderr.txt
for e in off-default off-sink on-default on-sink; do copy "$ST/egress-$e/egress-summary.json" "08-isolation-egress-mods-memory/egress-$e.json"; done
grep -h 'letta' "$ST"/egress-off-default/logs/strace-*.txt | grep -E 'sendto|connect' | sed -E -e 's/^[0-9]+ +//' -e "s#$SPIKE_SCRATCH#\$SCRATCH#g" -e "s#$HOME#\$HOME#g" | head -4 > "$EV/08-isolation-egress-mods-memory/egress-off-default-strace-excerpt.txt" || true
copy "$ST/s3/work/mods-disabled.json" 08-isolation-egress-mods-memory/mods-disabled.json
copy "$ST/s3/work/mods-enabled.json" 08-isolation-egress-mods-memory/mods-enabled-positive-control.json
for r in reflection-newagent-default reflection-newagent-off reflection-default; do copy "$ST/s3/work/$r.json" "08-isolation-egress-mods-memory/$r.json"; done
dump=$(ls -t "$ST"/s3/work/dumps/*.json | head -1)
python3 - "$dump" > "$EV/08-isolation-egress-mods-memory/reflection-subagent-request-excerpt.json" <<'PY'
import json, sys
body = json.load(open(sys.argv[1]))
text = lambda m: m['content'] if isinstance(m['content'], str) else ''.join(p.get('text', '') for p in m['content'])
print(json.dumps({'tools': [t['function']['name'] for t in body['tools']], 'system_head': text(body['messages'][0])[:1200],
                  'task_head': text(body['messages'][-1])[:900]}, indent=1))
PY
copy "$ST/s2/work/memory-scope.json" 08-isolation-egress-mods-memory/memory-scope.json
python3 - "$ST/s1/home/.letta/settings.json" > "$EV/08-isolation-egress-mods-memory/settings-toolset-per-conversation-excerpt.json" <<'PY'
import json, sys
s = json.load(open(sys.argv[1]))
print(json.dumps({k: s.get(k) for k in ('reflectionTrigger', 'reflectionStepCount', 'memoryReminderInterval')} |
                 {'agents': [{'toolset': a.get('toolset'), 'toolsetsByConversation': a.get('toolsetsByConversation')} for a in s.get('agents', [])]}, indent=1))
PY
copy "$ST/s2/work/line-of-work.json" 09-line-of-work/probe18-line-of-work.json
for f in bindings.json bindings.ledger.jsonl bindings.deliveries.jsonl; do copy "$ST/s2/work/$f" "10-binding-ledgers/s2-$f"; done
python3 - "$SPIKE_SCRATCH/blaine/b1/shim-calls.jsonl" > "$EV/10-binding-ledgers/blaine-shim-calls-summary.json" <<'PY'
import json, sys
from collections import Counter
rows = [json.loads(l) for l in open(sys.argv[1])]
writes = [r for r in rows if r['op'] not in ('inspect', 'decision_view', 'artifact')]
print(json.dumps({'calls': len(rows), 'by_op_status': Counter(f"{r['op']} {r['status']}" for r in rows).most_common(),
                  'write_calls': writes}, indent=1))
PY
python3 - "$ST/s1/logs/llm-requests.jsonl" "$ST/s2/logs/llm-requests.jsonl" > "$EV/01-local-and-tools/llm-tap-tool-surface-summary.json" <<'PY'
import json, sys
from collections import Counter
out = {}
for path in sys.argv[1:]:
    rows = [json.loads(l) for l in open(path)]
    out[path.split('/state/')[1]] = {'requests': len(rows), 'tool_sets': Counter(json.dumps(r.get('tools')) for r in rows).most_common()}
print(json.dumps(out, indent=1))
PY
for t in "$ST"/*/ws-token; do
  if grep -rqF "$(cat "$t")" "$EV"; then echo "TOKEN LEAK from $t" >&2; exit 1; fi
done
du -sh "$EV"
