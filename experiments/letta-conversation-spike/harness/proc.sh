#!/usr/bin/env bash
# Tiny pid-file process helper for spike components (never pattern-kills).
#   proc.sh start NAME PIDDIR LOGFILE -- CMD...
#   proc.sh kill  NAME PIDDIR [SIGNAL]
#   proc.sh alive NAME PIDDIR
set -euo pipefail
action=$1 name=$2 dir=$3; shift 3
pidfile="$dir/$name.pid"
case "$action" in
  start)
    log=$1; shift; [[ "$1" == "--" ]] && shift
    if [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then echo "$name already running"; exit 1; fi
    setsid nohup "$@" >>"$log" 2>&1 < /dev/null &
    echo $! > "$pidfile"; echo "$name $!";;
  kill)
    sig=${1:-TERM}
    if [[ -f "$pidfile" ]]; then pid=$(cat "$pidfile"); kill "-$sig" "$pid" 2>/dev/null || true
      for _ in $(seq 50); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
      kill -0 "$pid" 2>/dev/null && echo "$name still alive" || { rm -f "$pidfile"; echo "$name stopped ($sig)"; }
    else echo "$name not running"; fi;;
  alive)
    [[ -f "$pidfile" ]] && kill -0 "$(cat "$pidfile")" 2>/dev/null && echo yes || echo no;;
esac
