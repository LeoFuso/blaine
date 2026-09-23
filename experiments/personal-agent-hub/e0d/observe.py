#!/usr/bin/env python3
"""Bounded read-only E0.D evidence; no raw journal, credentials or mutation."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess


def observe(since):
    home = Path.home()
    def run(*args):
        result = subprocess.run(args, capture_output=True, text=True, timeout=15)
        if result.returncode:
            raise SystemExit('Observation unavailable; private diagnostic details suppressed')
        return result.stdout
    inventory = json.loads(run(str(home/'.local/share/blaine/transport/bin/blaine-hub-transport'),
                               '--config', str(home/'.config/blaine/services/transport.json'),
                               'workstation', 'list'))
    events = []
    for line in run('journalctl', '--user', '-u', 'blaine-hub-transport.service',
                    '--since', since, '-o', 'json', '--no-pager').splitlines():
        outer = json.loads(line)
        try:
            message = json.loads(outer.get('MESSAGE', ''))
        except (ValueError, TypeError):
            continue
        if not isinstance(message, dict) or message.get('event') not in ('workstation', 'private_listener_ready', 'private_session'):
            continue
        fields = ('event', 'stage', 'workstation_id', 'peer_node', 'session_id', 'outcome', 'protocol', 'server_id', 'mode')
        safe = {key: message[key] for key in fields if key in message}
        safe['journal_timestamp_us'] = outer.get('__REALTIME_TIMESTAMP')
        events.append(safe)
    services = {}
    for unit in ('blaine-hub-transport.service', 'blaine-runtime.service', 'blaine-restate.service'):
        output = run('systemctl', '--user', 'show', unit, '-p', 'ActiveState', '-p', 'SubState', '-p', 'MainPID')
        services[unit] = dict(line.split('=', 1) for line in output.splitlines() if '=' in line)
    return dict(observed_at=datetime.now(timezone.utc).isoformat(), inventory=inventory,
                events=events, services=services)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--since', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = observe(args.since)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'records': len(result['inventory']), 'events': len(result['events']), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
