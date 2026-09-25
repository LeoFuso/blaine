#!/usr/bin/env bash
# Run one Letta App Server generation inside a bwrap sandbox.
#
#   letta_sandbox.sh STATE_DIR [letta CLI args...]   (no args: App Server)
#
# Isolation (spike posture: Letta is hostile-capable middleware):
#   - own network namespace: loopback only, no route off the host;
#   - read-only host filesystem; real $HOME, /run and /tmp hidden (no keyring,
#     dbus, docker, postgres, tailscale or X sockets reachable);
#   - writable: STATE_DIR (Letta HOME + backend state) and the socket directory.
# The only channels out are two Unix sockets bridged on the host side:
#   vllm.sock -> host 127.0.0.1:8000 (Blaine local vLLM)
#   app.sock  <- host clients of the App Server
#
# Environment knobs (defaults are the strict spike posture):
#   LETTA_APP_PORT     in-sandbox App Server port (default 18283)
#   SPIKE_PRIVACY      "on" (default) sets every opt-out; "off" is the negative control
#   SPIKE_STRACE       "1" wraps the server in strace (connect/sendto/execve/etc.)
#   SPIKE_BASE_URL     optional LETTA_BASE_URL (e.g. an in-sandbox egress sink)
#   SPIKE_SINK_PORT    optional in-sandbox HTTP sink port (egress_sink.py)
set -euo pipefail

STATE=$(realpath "$1"); shift
HERE=$(dirname "$(realpath "$0")")
: "${SPIKE_SCRATCH:?}"
NODE_DIR=$(dirname "$(dirname "$(readlink -f "$(command -v node)")")")
ENV_DIR="$SPIKE_SCRATCH/env"
SOCK="$STATE/sock"
APP_PORT=${LETTA_APP_PORT:-18283}
mkdir -p "$STATE/home" "$STATE/work" "$SOCK" "$STATE/logs"
chmod 700 "$STATE" "$STATE/home" "$SOCK"

privacy=()
if [[ "${SPIKE_PRIVACY:-on}" == on ]]; then
  privacy=(--setenv LETTA_CODE_TELEM 0 --setenv DO_NOT_TRACK 1
           --setenv LETTA_DISABLE_MODS 1 --setenv DISABLE_AUTOUPDATER 1
           --setenv LETTA_DISABLE_LSP_DOWNLOAD 1 --setenv SCARF_ANALYTICS false)
fi
extra=()
[[ -n "${SPIKE_BASE_URL:-}" ]] && extra+=(--setenv LETTA_BASE_URL "$SPIKE_BASE_URL")
[[ -n "${SPIKE_SINK_PORT:-}" ]] && extra+=(--setenv SPIKE_SINK_PORT "$SPIKE_SINK_PORT")
[[ -n "${SPIKE_INJECT_PATH:-}" ]] && extra+=(--setenv SPIKE_INJECT_PATH "$SPIKE_INJECT_PATH" --setenv SPIKE_INJECT_WHEN "${SPIKE_INJECT_WHEN:-1}")
[[ -n "${SPIKE_DEBUG:-}" ]] && extra+=(--setenv LETTA_DEBUG 1 --setenv LETTA_LOG_WS_EVENTS 1)

exec bwrap --unshare-net --unshare-pid --unshare-ipc --unshare-uts \
  --ro-bind / / --dev /dev --proc /proc \
  --tmpfs /tmp --tmpfs /run --tmpfs "$HOME" \
  --ro-bind "$NODE_DIR" "$NODE_DIR" \
  --ro-bind "$ENV_DIR" "$ENV_DIR" \
  --ro-bind "$HERE" "$HERE" \
  --bind "$STATE" "$STATE" \
  --clearenv \
  --setenv HOME "$STATE/home" --setenv USER spike --setenv TMPDIR "$STATE/work/tmp" \
  --setenv PATH "$NODE_DIR/bin:/usr/bin:/bin" --setenv LANG C.UTF-8 \
  --setenv LETTA_LOCAL_BACKEND_EXPERIMENTAL 1 \
  --setenv LETTA_SKIP_KEYCHAIN_CHECK 1 \
  --setenv SPIKE_STATE "$STATE" --setenv SPIKE_ENV "$ENV_DIR" --setenv SPIKE_HARNESS "$HERE" \
  --setenv LETTA_APP_PORT "$APP_PORT" --setenv SPIKE_STRACE "${SPIKE_STRACE:-0}" \
  "${privacy[@]}" "${extra[@]}" \
  --chdir "$STATE/work" \
  /bin/bash "$HERE/sandbox_entry.sh" "$@"
