#!/usr/bin/env bash
# Runs inside the bwrap sandbox (see letta_sandbox.sh). Starts the socket
# bridges, runs the App Server (or a one-off letta CLI command) as a child and
# waits for it; when it exits (normally, SIGTERM or SIGKILL) the bridges are
# killed and the pid namespace ends.
set -uo pipefail
mkdir -p "$TMPDIR"
SOCK="$SPIKE_STATE/sock"
GEN=$(date +%s%N)
bridges=()
python3 "$SPIKE_HARNESS/uds_bridge.py" tcp-to-unix --listen 127.0.0.1:18000 \
  --unix "$SOCK/vllm.sock" --label vllm 2>>"$SPIKE_STATE/logs/bridge-vllm.jsonl" & bridges+=($!)
python3 "$SPIKE_HARNESS/uds_bridge.py" tcp-to-unix --listen 127.0.0.1:18001 \
  --unix "$SOCK/hostile.sock" --label hostile 2>>"$SPIKE_STATE/logs/bridge-hostile.jsonl" & bridges+=($!)
if [[ $# -eq 0 ]]; then
  python3 "$SPIKE_HARNESS/uds_bridge.py" unix-to-tcp --unix "$SOCK/app.sock" \
    --connect "127.0.0.1:$LETTA_APP_PORT" --label app 2>>"$SPIKE_STATE/logs/bridge-app.jsonl" & bridges+=($!)
fi
if [[ -n "${SPIKE_SINK_PORT:-}" ]]; then
  python3 "$SPIKE_HARNESS/egress_sink.py" --port "$SPIKE_SINK_PORT" \
    --out "$SPIKE_STATE/logs/egress-sink.jsonl" 2>/dev/null & bridges+=($!)
fi
LETTA=(node "$SPIKE_ENV/node_modules/@letta-ai/letta-code/letta.js")
if [[ $# -gt 0 ]]; then
  cmd=("${LETTA[@]}" "$@")
else
  auth=()
  if [[ -f "$SPIKE_STATE/ws-token.sha256" ]]; then
    auth=(--ws-auth capability-token --ws-token-sha256 "$(cat "$SPIKE_STATE/ws-token.sha256")")
  fi
  cmd=("${LETTA[@]}" server --listen "ws://127.0.0.1:$LETTA_APP_PORT" "${auth[@]}")
fi
if [[ "$SPIKE_STRACE" == 1 ]]; then
  cmd=(strace -f -tt -s 200 -e trace=connect,sendto,sendmsg,execve,bind \
       -o "$SPIKE_STATE/logs/strace-$GEN.txt" "${cmd[@]}")
elif [[ "$SPIKE_STRACE" == inject ]]; then
  # Fault injection: SIGKILL at entry of the Nth write() to one file (after its O_TRUNC open).
  cmd=(strace -f -qq -P "$SPIKE_INJECT_PATH" -e trace=openat,write \
       -e "inject=write:signal=KILL:when=${SPIKE_INJECT_WHEN:-1}" \
       -o "$SPIKE_STATE/logs/inject-$GEN.txt" "${cmd[@]}")
fi
"${cmd[@]}" &
main=$!
wait "$main"
status=$?
kill "${bridges[@]}" 2>/dev/null
exit "$status"
