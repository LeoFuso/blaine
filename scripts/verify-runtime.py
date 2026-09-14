"""Live local spike verification; owns and stops only the processes it starts."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
E = ROOT / '.local/evidence'
E.mkdir(parents=True, exist_ok=True)
PREFIX = str(time.time_ns())
PORTS = {8080: 18080, 9070: 19070, 9080: 19080, 5122: 15122}
processes = {}
logs = []


def save(name, value):
    (E / (name + '.json')).write_text(json.dumps(value, indent=2) + '\n')


def request(port, path, body=None, post=False, timeout=190):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f'http://127.0.0.1:{PORTS[port]}/{path}', data=data,
                                 headers={'Content-Type': 'application/json'} if body is not None else {},
                                 method='POST' if post or body is not None else 'GET')
    req.add_header('Accept', 'application/json')
    try:
        response = urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout)
    except urllib.error.HTTPError as error:
        save('http-error', {'url': req.full_url, 'status': error.code, 'body': error.read().decode()})
        raise
    with response as response:
        return json.load(response)


def ready(port):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(('127.0.0.1', PORTS[port]), timeout=1):
                return
        except OSError:
            time.sleep(.2)
    raise TimeoutError(f'port {port} not ready')


def start(name):
    log = (E / f'{name}.log').open('a')
    logs.append(log)
    config_path = E / 'restate-verification.toml'
    config = (ROOT / 'runtime/restate.toml').read_text().replace('.local/restate-data', '.local/restate-verification-data')
    for original, replacement in PORTS.items():
        config = config.replace(str(original), str(replacement))
    config_path.write_text(config)
    command = (['.local/bin/restate-server', '--config-file', str(config_path)] if name == 'restate' else
               ['.local/runtime-venv/bin/python', '-c', "import asyncio; from hypercorn.asyncio import serve; from hypercorn.config import Config; from runtime.app import app; config = Config(); config.bind = ['127.0.0.1:19080']; asyncio.run(serve(app, config))"])
    env = {key: value for key, value in os.environ.items() if not key.startswith('RESTATE_')}
    processes[name] = subprocess.Popen(command, stdout=log, stderr=log, env=env)
    ready(9070 if name == 'restate' else 9080)
    assert processes[name].poll() is None, f'{name} exited during startup'


def query(sql):
    return request(9070, 'query', {'query': sql})


def inspect(label, invocation):
    inv = query(f"select * from sys_invocation where id = '{invocation}'")
    journal = query(f"select * from sys_journal where id = '{invocation}' order by index")
    save(label + '-invocation', inv)
    save(label + '-journal', journal)
    assert inv['rows'], inv
    assert journal['rows'], journal
    rows = journal['rows']
    assert sum(row.get('name') == 'summarize-objective' for row in rows) == 1
    assert any(row['entry_type'] == 'Notification: Run' for row in rows)
    assert any(row['entry_type'] == 'Command: Sleep' for row in rows)
    return journal


def check_result(value, task):
    assert value == {'task_id': task, 'status': 'COMPLETED', 'result': {
        'objective': 'hello world', 'word_count': 2,
        'sha256': 'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9'}}, value


def experiment(label, crash=None):
    task = label + '-' + PREFIX
    sent = request(8080, f'TaskWorkflow/{task}/run/send', {'objective': 'hello world', 'delay_seconds': 120 if crash else 5})
    save(label + '-send', sent)
    deadline = time.monotonic() + 30
    while True:
        before = request(8080, f'TaskWorkflow/{task}/status', post=True)
        if before.get('phase') == 'durable-timer':
            break
        assert time.monotonic() < deadline, before
        time.sleep(.1)
    assert before['task_id'] == task and before['status'] == 'RUNNING'
    assert before['operation_result']['word_count'] == 2
    save(label + '-before', before)
    before_journal = inspect(label + '-before', sent['invocationId'])
    if crash:
        old = processes[crash]
        old.kill()
        assert old.wait(timeout=10) == -signal.SIGKILL
        start(crash)
        save(label + '-crash', {'signal': 'SIGKILL', 'old_pid': old.pid,
             'new_pid': processes[crash].pid, 'task_id': task,
             'resubmitted': False, 'reregistered': False})
    result = request(8080, f'restate/workflow/TaskWorkflow/{task}/attach')
    save(label + '-after', result)
    check_result(result, task)
    status = request(8080, f'TaskWorkflow/{task}/status', post=True)
    save(label + '-status-after', status)
    check_result(status, task)
    after_journal = inspect(label + '-after', sent['invocationId'])
    for before_row in before_journal['rows']:
        after_row = next(row for row in after_journal['rows'] if row['index'] == before_row['index'])
        assert (before_row['raw'], before_row['appended_at']) == (after_row['raw'], after_row['appended_at'])
    if not crash:
        try:
            request(8080, f'TaskWorkflow/{task}/run', {'objective': 'different objective', 'delay_seconds': 0})
        except urllib.error.HTTPError as error:
            assert error.code == 409
            save(label + '-duplicate', {'http_status': error.code, 'task_id': task})
        else:
            raise AssertionError('Duplicate workflow unexpectedly accepted')
        check_result(request(8080, f'restate/workflow/TaskWorkflow/{task}/attach'), task)
    print(label + ': PASS', flush=True)


try:
    for port in (8080, 9070, 9080, 5122):
        with socket.socket() as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind(('127.0.0.1', PORTS[port]))
    start('restate')
    start('runtime')
    deployments = request(9070, 'deployments')
    save('deployments-before', deployments)
    if not deployments.get('deployments'):
        save('verification-deployment', request(9070, 'deployments', {'uri': 'http://127.0.0.1:19080'}))
    (E / 'listeners.txt').write_text(subprocess.check_output(['ss', '-ltnp', '( sport = :18080 or sport = :19070 or sport = :19080 or sport = :15122 )'], text=True))
    save('missing-status', request(8080, f'TaskWorkflow/missing-{PREFIX}/status', post=True))
    experiment('happy')
    experiment('runtime', 'runtime')
    experiment('server', 'restate')
    save('summary', {'happy_path': 'PASS', 'status': 'PASS', 'runtime_recovery': 'PASS', 'restate_recovery': 'PASS', 'prefix': PREFIX})
finally:
    for process in processes.values():
        if process.poll() is None:
            process.terminate()
    for process in processes.values():
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    for log in logs:
        log.close()
