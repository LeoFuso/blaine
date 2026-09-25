#!/usr/bin/env bash
# One egress observation run in a fresh state (network-less sandbox + strace).
#   egress_run.sh NAME HOST_PORT PRIVACY(on|off) SINK(yes|no)
# Actions: provider connect (CLI), server start, agent + conversation + 2 turns,
# wait past one telemetry flush interval (2 min), SIGTERM (final flush), summarize.
set -euo pipefail
name=$1 port=$2 privacy=$3 sink=$4
HERE=$(dirname "$(realpath "$0")")
SRC=$(realpath "$HERE/../src")
S="$SPIKE_SCRATCH/state/egress-$name"
export SPIKE_PRIVACY=$privacy SPIKE_STRACE=1
if [[ "$sink" == yes ]]; then export SPIKE_SINK_PORT=18099 SPIKE_BASE_URL=http://127.0.0.1:18099; fi
python3 "$HERE/lettactl.py" init "$S" --host-port "$port" >/dev/null
sleep 1
timeout 120 bash "$HERE/letta_sandbox.sh" "$S" connect openai-compatible --base-url http://127.0.0.1:18000/v1 --api-key spike-local-no-key >/dev/null 2>&1 || true
python3 "$HERE/lettactl.py" start "$S" >/dev/null
node "$SRC/setup.mjs" agent "$S" "$port" "$S/agent.json" >/dev/null
node "$SRC/probe03b_blaine_only.mjs" "$S" "$port" "$(jq -r .agent_id "$S/agent.json")" "$(jq -r .default_runtime.conversation_id "$S/agent.json")" >/dev/null 2>&1 || true
sleep 135
python3 "$HERE/lettactl.py" kill "$S" --signal TERM >/dev/null
sleep 3
python3 "$HERE/lettactl.py" stop "$S" >/dev/null
python3 "$HERE/egress_summary.py" "$S" > "$S/egress-summary.json"
cat "$S/egress-summary.json"
