#!/usr/bin/env python3
"""Linux spike process ownership: PID + kernel start time, serialized by flock."""
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
from urllib.request import Request, build_opener, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / '.local/002'
PORTS = (28080, 29070, 29080, 25122)


def identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else [
            Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            os.readlink(f'/proc/{pid}/ns/pid'), fields[19]]
    except FileNotFoundError:
        return None


def owned(name):
    path = LOCAL / f'{name}.pid.json'
    if not path.exists():
        return None
    record = json.loads(path.read_text())
    return record['pid'] if identity(record['pid']) == record['start'] else None


def http(port, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(f'http://127.0.0.1:{port}{path}', data=data,
                  headers={'Content-Type': 'application/json', 'Accept': 'application/json'})
    with build_opener(ProxyHandler({})).open(req, timeout=2) as response:
        return json.load(response)


def stop(name):
    pid = owned(name)
    if pid:
        os.kill(pid, signal.SIGTERM)
        end = time.monotonic() + 10
        while owned(name) and time.monotonic() < end:
            time.sleep(.1)
        if owned(name):
            os.kill(pid, signal.SIGKILL)
            end = time.monotonic() + 5
            while owned(name) and time.monotonic() < end:
                time.sleep(.1)
        if owned(name):
            raise RuntimeError(f'{name} did not stop; retaining PID record')
    (LOCAL / f'{name}.pid.json').unlink(missing_ok=True)


def start(name, command):
    env = {k: v for k, v in os.environ.items() if not k.startswith('RESTATE_')}
    with (LOCAL / f'{name}.log').open('ab') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=log, start_new_session=True)
    token = identity(process.pid)
    if token is None:
        raise RuntimeError(f'{name} exited during startup')
    (LOCAL / f'{name}.pid.json').write_text(json.dumps({'pid': process.pid, 'start': token}))


def wait_ready():
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if not all(owned(name) for name in ('restate', 'runtime')):
            raise RuntimeError('Owned process exited; inspect .local/002/*.log')
        try:
            http(29070, '/deployments')
            with socket.create_connection(('127.0.0.1', 29080), timeout=1):
                return
        except (OSError, ValueError):
            time.sleep(.25)
    raise RuntimeError('Readiness timed out; inspect .local/002/*.log')


def doctor():
    result = {name: owned(name) for name in ('restate', 'runtime')}
    if not all(result.values()):
        raise RuntimeError(f'Owned services not running: {result}')
    wait_ready()
    deployments = http(29070, '/deployments')
    if 'http://127.0.0.1:29080' not in json.dumps(deployments):
        raise RuntimeError('Runtime deployment not registered')
    result['deployments'] = deployments
    result['listeners'] = subprocess.check_output(['ss', '-ltnp'], text=True)
    # Verify every configured listener exists exclusively on loopback.
    for port in PORTS:
        addresses = [line.split()[3] for line in result['listeners'].splitlines()[1:]
                     if line.split()[3].endswith(f':{port}')]
        if addresses != [f'127.0.0.1:{port}']:
            raise RuntimeError(f'Unexpected listeners on {port}: {addresses}')
    print(json.dumps(result, indent=2))


def main(action):
    LOCAL.mkdir(parents=True, exist_ok=True)
    with (LOCAL / 'control.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if action == 'down':
            for name in ('runtime', 'restate'):
                stop(name)
            print('Stopped owned Milestone 002 processes; data retained.')
        elif action in ('doctor', 'status'):
            doctor()
        elif action == 'up':
            if all(owned(name) for name in ('runtime', 'restate')):
                doctor()
                return
            if any(owned(name) for name in ('runtime', 'restate')):
                raise RuntimeError('Partial startup; run dev-down before retrying')
            for port in PORTS:
                with socket.socket() as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(('127.0.0.1', port))  # Refuse occupied ports; never adopt/kill their owners.
            try:
                start('restate', [str(ROOT / '.local/bin/restate-server'), '--config-file',
                                  'runtime/interactive-restate.toml'])
                start('runtime', [str(ROOT / '.local/runtime-venv/bin/python'), '-m', 'runtime.interactive'])
                wait_ready()
                deployments = http(29070, '/deployments')
                if 'http://127.0.0.1:29080' not in json.dumps(deployments):
                    http(29070, '/deployments', {'uri': 'http://127.0.0.1:29080'})
                doctor()
            except BaseException:
                for name in ('runtime', 'restate'):
                    stop(name)
                raise
        else:
            raise ValueError('Expected up, down, doctor, or status')


if __name__ == '__main__':
    try:
        main(sys.argv[1])
    except Exception as error:
        print(f'Error: {error}', file=sys.stderr)
        sys.exit(1)
