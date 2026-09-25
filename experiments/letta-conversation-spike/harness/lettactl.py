#!/usr/bin/env python3
"""Host-side control of one sandboxed Letta App Server state directory.

  lettactl.py init  STATE --host-port P   create state, capability token, host bridges
  lettactl.py start STATE                 start one server generation, wait until ready
  lettactl.py kill  STATE [--signal KILL|TERM]
  lettactl.py stop  STATE                 kill server and host bridges
  lettactl.py pids  STATE

The capability token is a spike-local random value (not a Blaine secret); only
its sha256 is passed to the server. Clients read STATE/ws-token.
"""
import argparse
import hashlib
import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PY = sys.executable


def load(state):
    path = state / 'control.json'
    return json.loads(path.read_text()) if path.exists() else {}


def save(state, data):
    (state / 'control.json').write_text(json.dumps(data, indent=2) + '\n')


def alive(pid):
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        return Path(f'/proc/{pid}/stat').read_text().split()[2] != 'Z'
    except OSError:
        return False


def server_pid(bwrap_pid):
    """The node App Server process (host pid) under this bwrap generation."""
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():
            continue
        try:
            cmd = (proc / 'cmdline').read_bytes().split(b'\0')
        except OSError:
            continue
        if cmd and cmd[0].endswith(b'node') and any(part.endswith(b'letta.js') for part in cmd) and b'server' in cmd:
            # confirm ancestry
            pid = int(proc.name)
            parent = pid
            for _ in range(8):
                try:
                    parent = int((Path(f'/proc/{parent}/stat').read_text().rsplit(')', 1)[1].split())[1])
                except (OSError, ValueError, IndexError):
                    break
                if parent == bwrap_pid:
                    return pid
    return None


def spawn(argv, log, env=None):
    with open(log, 'ab') as out:
        return subprocess.Popen(argv, stdout=out, stderr=out, env=env, start_new_session=True).pid


def spawn_tap(state):
    # HTTP-aware tap: records the tool surface and message shapes Letta sends the model.
    return spawn([PY, str(HERE / 'llm_tap.py'), '--unix', str(state / 'sock/vllm.sock'),
                  '--upstream', '127.0.0.1:8000', '--out', str(state / 'logs/llm-requests.jsonl')],
                 state / 'logs/host-bridge-vllm.jsonl')


def ready(port, token, timeout):
    """Upgrade handshake succeeds (101) with the capability token."""
    deadline = time.time() + timeout
    key = 'dGhlIHNhbXBsZSBub25jZQ=='
    while time.time() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=2) as sock:
                sock.sendall((f'GET / HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n'
                              f'Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n'
                              f'Sec-WebSocket-Version: 13\r\nAuthorization: Bearer {token}\r\n\r\n').encode())
                sock.settimeout(3)
                head = sock.recv(64)
                if head.startswith(b'HTTP/1.1 101'):
                    return True
        except OSError:
            pass
        time.sleep(0.5)
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['init', 'start', 'kill', 'stop', 'pids', 'retap'])
    parser.add_argument('state', type=Path)
    parser.add_argument('--host-port', type=int)
    parser.add_argument('--signal', default='KILL', choices=['KILL', 'TERM'])
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    state = args.state.resolve()
    data = load(state)

    if args.command == 'init':
        if state.exists() and any(state.iterdir()):
            raise SystemExit('state exists; use a new directory')
        (state / 'sock').mkdir(parents=True)
        (state / 'logs').mkdir()
        os.chmod(state, 0o700)
        token = secrets.token_urlsafe(32)
        (state / 'ws-token').write_text(token)
        os.chmod(state / 'ws-token', 0o600)
        (state / 'ws-token.sha256').write_text(hashlib.sha256(token.encode()).hexdigest())
        data = {'host_port': args.host_port, 'generations': []}
        data['bridge_vllm'] = spawn_tap(state)
        data['bridge_app'] = spawn([PY, str(HERE / 'uds_bridge.py'), 'tcp-to-unix', '--listen',
            f'127.0.0.1:{args.host_port}', '--unix', str(state / 'sock/app.sock'), '--label', 'app-host'],
            state / 'logs/host-bridge-app.jsonl')
        save(state, data)
        print(json.dumps({'state': str(state), 'host_port': args.host_port}))
    elif args.command == 'start':
        env = dict(os.environ)
        gen = len(data['generations']) + 1
        pid = spawn(['bash', str(HERE / 'letta_sandbox.sh'), str(state)], state / f'logs/server-{gen}.txt', env)
        entry = {'generation': gen, 'bwrap_pid': pid, 'started_at': time.time()}
        data['generations'].append(entry)
        save(state, data)
        token = (state / 'ws-token').read_text()
        ok = ready(data['host_port'], token, args.timeout)
        entry['server_pid'] = server_pid(pid)
        entry['ready'] = ok
        entry['ready_after_s'] = round(time.time() - entry['started_at'], 2)
        save(state, data)
        print(json.dumps(entry))
        if not ok:
            raise SystemExit(1)
    elif args.command == 'kill':
        entry = data['generations'][-1]
        target = entry.get('server_pid') or server_pid(entry['bwrap_pid'])
        sig = signal.SIGKILL if args.signal == 'KILL' else signal.SIGTERM
        if target and alive(target):
            os.kill(target, sig)
        deadline = time.time() + 20
        while time.time() < deadline and alive(entry['bwrap_pid']):
            time.sleep(0.1)
        entry['killed'] = {'signal': args.signal, 'pid': target, 'at': time.time(),
                           'namespace_gone': not alive(entry['bwrap_pid'])}
        save(state, data)
        print(json.dumps(entry['killed']))
    elif args.command == 'stop':
        for entry in data.get('generations', []):
            # Signalling the outer bwrap does not reach the pid namespace; stop the
            # server itself so the entry script reaps its bridges and the namespace ends.
            target = server_pid(entry['bwrap_pid']) or entry.get('server_pid')
            if target and alive(target):
                os.kill(target, signal.SIGTERM)
            deadline = time.time() + 15
            while time.time() < deadline and alive(entry['bwrap_pid']):
                time.sleep(0.2)
            if alive(entry['bwrap_pid']):
                os.kill(entry['bwrap_pid'], signal.SIGKILL)
        for name in ('bridge_vllm', 'bridge_app'):
            if data.get(name) and alive(data[name]):
                os.kill(data[name], signal.SIGTERM)
        print('stopped')
    elif args.command == 'retap':
        if data.get('bridge_vllm') and alive(data['bridge_vllm']):
            os.kill(data['bridge_vllm'], signal.SIGTERM)
            time.sleep(0.5)
        data['bridge_vllm'] = spawn_tap(state)
        save(state, data)
        print(json.dumps({'bridge_vllm': data['bridge_vllm']}))
    else:
        print(json.dumps({k: (v, alive(v)) if isinstance(v, int) else v for k, v in data.items()}, indent=1))


if __name__ == '__main__':
    main()
