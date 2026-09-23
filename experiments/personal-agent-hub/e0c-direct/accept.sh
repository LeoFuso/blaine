#!/usr/bin/env bash
# One candidate, rerunnable acceptance. No source build, SCP, daemon or IDE edit.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
case "$(uname -s)/$(uname -m)" in
  Darwin/arm64) asset=blaine-darwin-arm64;;
  Darwin/x86_64) asset=blaine-darwin-amd64;;
  Linux/x86_64) asset=blaine-linux-amd64;;
  Linux/aarch64) asset=blaine-linux-arm64;;
  *) echo 'STOP: unbuilt platform' >&2; exit 2;;
esac
if command -v sha256sum >/dev/null 2>&1; then
  sha256sum --check checksums.txt
else
  shasum -a 256 --check checksums.txt
fi
mkdir -p "$HOME/.local/bin"
if [[ -e "$HOME/.local/bin/blaine" && ! -e "$HOME/.local/bin/blaine.before-e0c-direct" ]]; then
  cp -p -- "$HOME/.local/bin/blaine" "$HOME/.local/bin/blaine.before-e0c-direct"
fi
# A rename prevents a running executable from being truncated during an upgrade.
cp -- "$asset" "$HOME/.local/bin/blaine.e0c-candidate"
chmod 755 "$HOME/.local/bin/blaine.e0c-candidate"
mv -f -- "$HOME/.local/bin/blaine.e0c-candidate" "$HOME/.local/bin/blaine"
client="$HOME/.local/bin/blaine"
# Downloads may be on DrvFS (/mnt/c). Keep Unix FIFOs and reports in the native
# user home, separate from private installation state; check before live probes.
report="$(mktemp -d "$HOME/blaine-e0c-reports-XXXXXX")"
if ! mkfifo "$report/stdio-preflight" || [[ ! -p "$report/stdio-preflight" ]]; then
  echo "STOP: acceptance requires FIFO support in the native user home; reports: $report" >&2
  exit 2
fi
rm "$report/stdio-preflight"
"$client" version --json | tee "$report/version.json"
# Doctor is read-only and correctly remains NOT_READY before E0.D–F.
set +e
"$client" doctor --json > "$report/doctor.json"
doctor_code=$?
set -e
if [[ "$doctor_code" != 2 ]]; then echo "STOP: unexpected doctor exit $doctor_code"; exit 2; fi
for attempt in 1 2; do
  echo "Direct acceptance $attempt/2; close other Blaine processes first."
  set +e
  "$client" connect --verify-transport | tee "$report/connect-$attempt.jsonl"
  code=${PIPESTATUS[0]}
  set -e
  if [[ "$code" != 0 ]]; then
    echo "STOP: client exit $code. Send only $report; never send the private installation state."
    echo 'If the result is TRANSPORT_DENIED, the host operator must authorize the displayed new node ID.'
    echo 'After that review, rerun this same script; no new download is needed.'
    exit "$code"
  fi
done
# Exercise the exact local ACP launcher and real remote session under OS signals.
for signal_name in INT TERM; do
  fifo="$report/acp-$signal_name.in"
  mkfifo "$fifo"
  exec 3<>"$fifo"
  "$client" acp < "$fifo" > "$report/acp-$signal_name.jsonl" 2> "$report/acp-$signal_name.stderr" &
  agent_pid=$!
  trap 'kill -TERM "$agent_pid" 2>/dev/null || true; exec 3>&-' EXIT
  printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":1,"clientCapabilities":{}}}' '{"jsonrpc":"2.0","id":2,"method":"session/new","params":{"cwd":"/e0c-no-workspace-access","mcpServers":[]}}' >&3
  ready=false
  for tick in {1..60}; do
    if grep -q '"sessionId"[[:space:]]*:' "$report/acp-$signal_name.jsonl"; then ready=true; break; fi
    if ! kill -0 "$agent_pid" 2>/dev/null; then break; fi
    sleep 1
  done
  if [[ "$ready" != true ]]; then echo "STOP: ACP session not ready; see $report"; exit 3; fi
  kill -s "$signal_name" "$agent_pid"
  for tick in {1..5}; do
    if ! kill -0 "$agent_pid" 2>/dev/null; then break; fi
    sleep 1
  done
  if kill -0 "$agent_pid" 2>/dev/null; then
    kill -KILL "$agent_pid"
    echo "STOP: ACP did not exit after SIG$signal_name"; exit 3
  fi
  set +e
  wait "$agent_pid"
  code=$?
  set -e
  trap - EXIT
  exec 3>&-
  rm "$fifo"
  printf '{"signal":"SIG%s","exit":%s}\n' "$signal_name" "$code" | tee "$report/signal-$signal_name.json"
  if [[ "$code" != 130 ]]; then echo 'STOP: unexpected ACP cancellation exit'; exit 3; fi
done
printf 'PASS transport/ACP signal batch. Real JetBrains launch/auth and Task independence are separate evidence.\nReports: %s\n' "$report"
