#!/usr/bin/env python3
"""Disposable Blaine stack for the spike (repository convention: isolated Restate).

  blaine_stack.py start DIR     Restate 1.7.9 (ingress 58080, admin 59070, node 55122),
                                unchanged runtime app (59080), control shim (59090)
  blaine_stack.py kill DIR NAME SIGKILL one component (restate|runtime|shim)
  blaine_stack.py restart DIR NAME
  blaine_stack.py stop DIR
  blaine_stack.py status DIR

Uses this worktree's `runtime/` unchanged. Never touches canonical ports/state.
"""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SCRATCH = Path(os.environ.get('SPIKE_SCRATCH', ''))
PORTS = {'ingress': 58080, 'admin': 59070, 'node': 55122, 'runtime': 59080, 'shim': 59090}
OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def http(url, body=None, timeout=5):
    request = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                     headers={'Content-Type': 'application/json'} if body is not None else {})
    with OPENER.open(request, timeout=timeout) as response:
        return json.load(response)


def port_open(port):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=1):
            return True
    except OSError:
        return False


def until(check, what, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if check():
                return
        except OSError:
            pass
        time.sleep(0.3)
    raise SystemExit(f'{what} not ready')


def commands(root):
    py = str(SCRATCH / 'pyenv/bin/python')
    env = {'PYTHONPATH': str(REPO), 'PYTHONDONTWRITEBYTECODE': '1', 'PATH': '/usr/bin:/bin',
           'SPIKE_BLAINE_DATA': str(root / 'data'), 'SPIKE_RUNTIME_PORT': str(PORTS['runtime']),
           'SPIKE_SHIM_PORT': str(PORTS['shim']), 'SPIKE_INGRESS': f"http://127.0.0.1:{PORTS['ingress']}",
           'SPIKE_SHIM_EVENTS': str(root / 'shim-events.jsonl'), 'SPIKE_SHIM_CALLS': str(root / 'shim-calls.jsonl')}
    return {
        'restate': ([str(SCRATCH / 'bin/restate-server'), '--config-file', str(root / 'restate.toml')], env),
        'runtime': ([py, str(HERE / 'spike_runtime.py')], env),
        'shim': ([py, str(HERE / 'control_shim.py')], env),
    }


def load(root):
    path = root / 'stack.json'
    return json.loads(path.read_text()) if path.exists() else {'processes': {}, 'events': []}


def save(root, data):
    (root / 'stack.json').write_text(json.dumps(data, indent=1) + '\n')


def alive(pid):
    try:
        os.kill(pid, 0)
        return Path(f'/proc/{pid}/stat').read_text().split()[2] != 'Z'
    except OSError:
        return False


def launch(root, data, name):
    argv, env = commands(root)[name]
    gen = sum(1 for e in data['events'] if e.get('start') == name) + 1
    with open(root / f'{name}-{gen}.txt', 'ab') as log:
        pid = subprocess.Popen(argv, cwd=REPO, env=env, stdout=log, stderr=log, start_new_session=True).pid
    data['processes'][name] = pid
    data['events'].append({'start': name, 'pid': pid, 'generation': gen, 'at': time.time()})
    ready = {'restate': lambda: http(f"http://127.0.0.1:{PORTS['admin']}/deployments") is not None,
             'runtime': lambda: port_open(PORTS['runtime']),
             'shim': lambda: port_open(PORTS['shim'])}[name]
    until(ready, name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['start', 'kill', 'restart', 'stop', 'status'])
    parser.add_argument('root', type=Path)
    parser.add_argument('name', nargs='?')
    args = parser.parse_args()
    root = args.root.resolve()
    data = load(root)
    if args.command == 'start':
        if root.exists() and any(root.iterdir()):
            raise SystemExit('use a new directory')
        root.mkdir(parents=True, exist_ok=True)
        for name in ('ingress', 'admin', 'node', 'runtime', 'shim'):
            if port_open(PORTS[name]):
                raise SystemExit(f'port {PORTS[name]} busy')
        (root / 'restate.toml').write_text(f'''cluster-name = "blaine-letta-spike"
node-name = "letta-spike"
base-dir = "{root / 'restate-data'}"
bind-ip = "127.0.0.1"
bind-port = {PORTS['node']}
advertised-host = "127.0.0.1"
listen-mode = "tcp"
auto-provision = true
default-journal-retention = "7 days"
[admin]
bind-address = "127.0.0.1:{PORTS['admin']}"
[ingress]
bind-address = "127.0.0.1:{PORTS['ingress']}"
''')
        for name in ('restate', 'runtime'):
            launch(root, data, name)
        registration = http(f"http://127.0.0.1:{PORTS['admin']}/deployments", {'uri': f"http://127.0.0.1:{PORTS['runtime']}"}, timeout=30)
        data['registration'] = {'id': registration.get('id'), 'services': [s['name'] for s in registration.get('services', [])]}
        launch(root, data, 'shim')
        save(root, data)
        print(json.dumps({'processes': data['processes'], 'registration': data['registration']}))
    elif args.command in ('kill', 'restart'):
        pid = data['processes'].get(args.name)
        if pid and alive(pid):
            os.kill(pid, signal.SIGKILL)
            while alive(pid):
                time.sleep(0.05)
            data['events'].append({'sigkill': args.name, 'pid': pid, 'at': time.time()})
        if args.command == 'restart':
            launch(root, data, args.name)
        save(root, data)
        print(json.dumps({args.name: data['processes'].get(args.name), 'events': data['events'][-2:]}))
    elif args.command == 'stop':
        for name, pid in data['processes'].items():
            if alive(pid):
                os.kill(pid, signal.SIGTERM)
        time.sleep(2)
        for name, pid in data['processes'].items():
            if alive(pid):
                os.kill(pid, signal.SIGKILL)
        print('stopped')
    else:
        print(json.dumps({n: (p, alive(p)) for n, p in data['processes'].items()}))


if __name__ == '__main__':
    sys.exit(main())
