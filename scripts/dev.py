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

ENDPOINTS = {
    'ingress': 28080,
    'admin': 29070,
    'runtime': 29080,
    'fabric': 25122,
}

PORTS = tuple(ENDPOINTS.values())
RUNTIME_URI = 'http://127.0.0.1:29080'


def identity(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else [
            Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            os.readlink(f'/proc/{pid}/ns/pid'),
            fields[19],
        ]
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
    req = Request(
        f'http://127.0.0.1:{port}{path}',
        data=data,
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    )

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
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith('RESTATE_')
    }

    with (LOCAL / f'{name}.log').open('ab') as log:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )

    token = identity(process.pid)

    if token is None:
        raise RuntimeError(f'{name} exited during startup')

    (LOCAL / f'{name}.pid.json').write_text(
        json.dumps({
            'pid': process.pid,
            'start': token,
        })
    )


def wait_ready():
    deadline = time.monotonic() + 45

    while time.monotonic() < deadline:
        if not all(owned(name) for name in ('restate', 'runtime')):
            raise RuntimeError(
                'Owned process exited; inspect .local/002/*.log'
            )

        try:
            http(ENDPOINTS['admin'], '/deployments')

            with socket.create_connection(
                ('127.0.0.1', ENDPOINTS['runtime']),
                timeout=1,
            ):
                return
        except (OSError, ValueError):
            time.sleep(.25)

    raise RuntimeError(
        'Readiness timed out; inspect .local/002/*.log'
    )


def flatten_services(deployments):
    services = []

    for deployment in deployments.get('deployments', []):
        endpoint = deployment.get('uri')

        for service in deployment.get('services', []):
            services.append({
                'name': service.get('name'),
                'revision': service.get('revision'),
                'endpoint': endpoint,
            })

    return services


def collect_status():
    restate_pid = owned('restate')
    runtime_pid = owned('runtime')

    result = {
        'status': 'ok',
        'restate': {
            'state': 'running' if restate_pid else 'stopped',
            'pid': restate_pid,
        },
        'runtime': {
            'state': 'running' if runtime_pid else 'stopped',
            'pid': runtime_pid,
        },
        'services': [],
        'endpoints': {
            name: f'127.0.0.1:{port}'
            for name, port in ENDPOINTS.items()
        },
    }

    if not restate_pid or not runtime_pid:
        result['status'] = 'degraded'
        return result

    try:
        deployments = http(ENDPOINTS['admin'], '/deployments')
        result['services'] = flatten_services(deployments)

        if RUNTIME_URI not in json.dumps(deployments):
            result['status'] = 'degraded'
    except (OSError, ValueError):
        result['status'] = 'degraded'

    return result


def print_status(result):
    print('Blaine development stack')
    print()

    restate = result['restate']
    runtime = result['runtime']

    print(
        f"Restate   {restate['state'].upper():<8} "
        f"pid={restate['pid'] or '-'}"
    )
    print(
        f"Runtime   {runtime['state'].upper():<8} "
        f"pid={runtime['pid'] or '-'}"
    )

    if result['services']:
        print()
        print('Services')

        for service in result['services']:
            revision = service['revision']
            endpoint = service['endpoint']

            print(
                f"  {service['name']} "
                f"revision={revision} "
                f"endpoint={endpoint}"
            )

    print()
    print('Endpoints')

    for name, endpoint in result['endpoints'].items():
        print(f'  {name:<8} {endpoint}')

    print()
    print(f"Health: {result['status'].upper()}")


def listener_lines():
    output = subprocess.check_output(
        ['ss', '-ltnp'],
        text=True,
    )

    lines = output.splitlines()

    relevant = [
        line
        for line in lines[1:]
        if any(
            line.split()[3].endswith(f':{port}')
            for port in PORTS
        )
    ]

    return output, relevant


def verify_listeners(output):
    for port in PORTS:
        addresses = [
            line.split()[3]
            for line in output.splitlines()[1:]
            if line.split()[3].endswith(f':{port}')
        ]

        if addresses != [f'127.0.0.1:{port}']:
            raise RuntimeError(
                f'Unexpected listeners on {port}: {addresses}'
            )


def doctor():
    restate_pid = owned('restate')
    runtime_pid = owned('runtime')

    if not restate_pid or not runtime_pid:
        raise RuntimeError(
            'Owned services not running: '
            f'{{"restate": {restate_pid}, "runtime": {runtime_pid}}}'
        )

    wait_ready()

    deployments = http(
        ENDPOINTS['admin'],
        '/deployments',
    )

    if RUNTIME_URI not in json.dumps(deployments):
        raise RuntimeError(
            'Runtime deployment not registered'
        )

    output, relevant = listener_lines()
    verify_listeners(output)

    result = collect_status()

    print_status(result)

    print()
    print('Listener diagnostics')

    for line in relevant:
        print(f'  {line}')

    print()
    print('Doctor: PASS')


def status(json_output=False):
    result = collect_status()

    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print_status(result)

    return result['status'] == 'ok'


def main(argv):
    if not argv:
        raise ValueError(
            'Expected up, down, doctor, or status'
        )

    action = argv[0]
    options = argv[1:]

    LOCAL.mkdir(parents=True, exist_ok=True)

    with (LOCAL / 'control.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        if action == 'down':
            if options:
                raise ValueError('dev-down accepts no arguments')

            for name in ('runtime', 'restate'):
                stop(name)

            print(
                'Stopped owned Milestone 002 processes; '
                'data retained.'
            )
            return 0

        if action == 'doctor':
            if options:
                raise ValueError('doctor accepts no arguments')

            doctor()
            return 0

        if action == 'status':
            if options not in ([], ['--json']):
                raise ValueError(
                    'status accepts only --json'
                )

            healthy = status(
                json_output='--json' in options
            )

            return 0 if healthy else 1

        if action == 'up':
            if options:
                raise ValueError('dev-up accepts no arguments')

            if all(
                owned(name)
                for name in ('runtime', 'restate')
            ):
                print_status(collect_status())
                return 0

            if any(
                owned(name)
                for name in ('runtime', 'restate')
            ):
                raise RuntimeError(
                    'Partial startup; run dev-down before retrying'
                )

            for port in PORTS:
                with socket.socket() as sock:
                    sock.setsockopt(
                        socket.SOL_SOCKET,
                        socket.SO_REUSEADDR,
                        1,
                    )
                    sock.bind(
                        ('127.0.0.1', port)
                    )

            try:
                start(
                    'restate',
                    [
                        str(ROOT / '.local/bin/restate-server'),
                        '--config-file',
                        'runtime/interactive-restate.toml',
                    ],
                )

                start(
                    'runtime',
                    [
                        str(
                            ROOT
                            / '.local/runtime-venv/bin/python'
                        ),
                        '-m',
                        'runtime.interactive',
                    ],
                )

                wait_ready()

                deployments = http(
                    ENDPOINTS['admin'],
                    '/deployments',
                )

                if RUNTIME_URI not in json.dumps(deployments):
                    http(
                        ENDPOINTS['admin'],
                        '/deployments',
                        {'uri': RUNTIME_URI},
                    )

                print_status(collect_status())
                return 0

            except BaseException:
                for name in ('runtime', 'restate'):
                    stop(name)

                raise

        raise ValueError(
            'Expected up, down, doctor, or status'
        )


if __name__ == '__main__':
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as error:
        print(
            f'Error: {error}',
            file=sys.stderr,
        )
        sys.exit(1)
