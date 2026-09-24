"""Local worktree TargetProvider: the first real E2.0 provider (PA-3).

Operates on operator-configured local checkouts (normally dedicated git
worktrees). It satisfies the ``effects.TargetProvider`` obligations:

- ``dispatch`` is idempotent per operation id + request digest, backed by a
  durable SQLite receipt store; a different request under the same identity is
  rejected, and a repeat returns the stored receipt without re-executing.
- A write is an atomic compare-and-swap against its precondition (temp file +
  ``os.replace`` + readback), recorded as an intent before the file changes so a
  crash between the change and its receipt is still attributable.
- ``query`` answers from the receipt store; absence is authoritative.
- Exec runs a reviewed profile's exact argv (no shell) in its own process group
  under a small supervisor that records the exit status durably, so a runtime
  restart does not lose a finished process.

The provider holds no Task authority. PolicyGate, the pinned authority and any
human approval decide what reaches it; it only performs and attests.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import signal
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

from runtime.kernel import effects
from runtime.kernel.contracts import message

MINIMAL_PATH = '/usr/local/bin:/usr/bin:/bin'
CODE_ROOT = Path(__file__).resolve().parents[2]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LocalWorktreeProvider:
    provider_id = 'local-worktree'

    def __init__(self, workspaces: dict[str, str | Path], database: Path):
        self.roots = {identifier: Path(root).resolve(strict=True) for identifier, root in workspaces.items()}
        for root in self.roots.values():
            if not root.is_dir():
                raise ValueError('A workspace root must be an existing directory')
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.processes = self.database.parent / 'target-processes'
        self.processes.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self.db() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS receipts (
                    operation_id TEXT PRIMARY KEY, request_digest TEXT NOT NULL,
                    phase TEXT NOT NULL, request TEXT NOT NULL, receipt TEXT, pid INTEGER);''')

    def db(self):
        return sqlite3.connect(self.database, timeout=30, isolation_level='IMMEDIATE')

    # ------------------------------------------------------------------ paths
    def root(self, workspace_id: str) -> Path:
        root = self.roots.get(workspace_id)
        if root is None:
            raise ValueError('Unknown workspace')
        return root

    def target(self, workspace_id: str, path: str) -> Path:
        """Confined, symlink-safe path inside the workspace root."""
        effects.confined(path)
        root = self.root(workspace_id)
        candidate = root / path
        parent = candidate.parent.resolve()
        if parent != root and root not in parent.parents:
            raise ValueError('Path escapes the workspace')
        if candidate.is_symlink():
            raise ValueError('Symbolic links are not written or read through')
        if '.git' in Path(path).parts:
            raise ValueError('Repository metadata is not a workspace file')
        return candidate

    def state_of(self, file: Path) -> dict:
        return {'exists': False} if not file.exists() else {'exists': True, 'sha256': _sha(file.read_bytes())}

    # ------------------------------------------------------------------ reads
    def read(self, workspace_id, path):
        file = self.target(workspace_id, path)
        if not file.exists():
            return {'exists': False, 'content': ''}
        data = file.read_bytes()
        if len(data) > effects.MAX_WRITE_BYTES:
            raise ValueError('File exceeds the read cap')
        return {'exists': True, 'content': data.decode('utf-8')}

    def observe(self, workspace_id, path):
        return self.state_of(self.target(workspace_id, path))

    # ------------------------------------------------------------------ receipts
    def receipt(self, request, state, **body):
        payload = request['payload']
        return message('EffectReceipt', {'task_id': payload['task_id'], 'operation_id': payload['operation_id'],
            'request_digest': effects.request_digest(request), 'provider': self.provider_id,
            'operation_class': payload['operation_class'], 'state': state, **body})

    def dispatch(self, request, payload):
        operation, digest = request['payload']['operation_id'], effects.request_digest(request)
        with self._lock:
            with self.db() as db:
                row = db.execute('SELECT request_digest, phase, receipt FROM receipts WHERE operation_id=?',
                                 (operation,)).fetchone()
                if row:
                    if row[0] != digest:
                        raise ValueError('Operation identity reused with a different request')
                    if row[1] == 'done':
                        return json.loads(row[2])
            if row:
                # An intent without a receipt: settle it from the target, never redo it.
                found = self.query(operation, digest)
                if found.get('found'):
                    return found['receipt']
            if request['payload']['operation_class'] == effects.WRITE:
                return self.write(request, payload, digest)
            return self.start(request, digest)

    def write(self, request, payload, digest):
        p = request['payload']
        file = self.target(p['workspace_id'], p['path'])
        content = payload['content'].encode('utf-8')
        if _sha(content) != p['content_sha256']:
            raise ValueError('Write payload does not match the admitted content')
        target = {'workspace_id': p['workspace_id'], 'path': p['path']}
        before = self.state_of(file)
        before = {'absent': True} if not before['exists'] else {'sha256': before['sha256']}
        if before != p['precondition']:
            receipt = self.receipt(request, 'conflict', write={**target, 'before': before},
                                   detail='Target changed since the planning evidence')
            self.record(p['operation_id'], digest, request, receipt)
            return receipt
        # Intent first: a crash after the replace is attributable to this operation.
        with self.db() as db:
            db.execute('INSERT INTO receipts (operation_id, request_digest, phase, request) VALUES (?, ?, ?, ?)',
                       (p['operation_id'], digest, 'writing', json.dumps(request)))
        file.parent.mkdir(parents=True, exist_ok=True)
        staging = file.with_name(f'.{file.name}.blaine-{_sha(p["operation_id"].encode())[:12]}')
        staging.write_bytes(content)
        os.replace(staging, file)
        readback = _sha(file.read_bytes())
        receipt = self.receipt(request, 'applied', write={**target, 'before': before,
                               'after': {'sha256': readback}, 'readback_sha256': readback})
        self.record(p['operation_id'], digest, request, receipt)
        return receipt

    def record(self, operation, digest, request, receipt, pid=None, phase='done'):
        with self.db() as db:
            db.execute('INSERT OR REPLACE INTO receipts (operation_id, request_digest, phase, request, receipt, pid) '
                       'VALUES (?, ?, ?, ?, ?, ?)',
                       (operation, digest, phase, json.dumps(request), json.dumps(receipt), pid))

    # ------------------------------------------------------------------ exec
    def paths(self, operation):
        stem = hashlib.sha256(operation.encode()).hexdigest()[:24]
        return self.processes / f'{stem}.out', self.processes / f'{stem}.exit'

    def start(self, request, digest):
        p = request['payload']
        root = self.root(p['workspace_id'])
        output, status = self.paths(p['operation_id'])
        # Intent first: an operation recorded without a pid provably never started.
        with self.db() as db:
            db.execute('INSERT INTO receipts (operation_id, request_digest, phase, request) VALUES (?, ?, ?, ?)',
                       (p['operation_id'], digest, 'starting', json.dumps(request)))
        env = {'PATH': MINIMAL_PATH, 'HOME': os.environ.get('HOME', '/tmp'), 'LANG': 'C.UTF-8',
               'PYTHONDONTWRITEBYTECODE': '1'}
        # The supervisor starts from this module's own code root, never from the
        # workspace: a workspace may itself contain a ``runtime`` package (e.g. a
        # Blaine worktree) that would shadow this module. The profile's process
        # then runs in the workspace with the workspace's own imports.
        command = [sys.executable, '-m', 'runtime.kernel.target_local', 'supervise', str(output), str(status),
                   str(root), '--', p['command']['executable'], *p['command']['args']]
        process = subprocess.Popen(command, cwd=CODE_ROOT, env=env,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=True)
        receipt = self.receipt(request, 'running', exec={'started': True, 'cleanup': 'running'})
        self.record(p['operation_id'], digest, request, receipt, pid=process.pid, phase='running')
        return receipt

    def finished(self, request, output: Path, status: Path) -> dict | None:
        if not status.exists():
            return None
        exit_record = json.loads(status.read_text())
        cap = request['payload']['output_cap_bytes']
        data = output.read_bytes() if output.exists() else b''
        truncated = len(data) > cap
        text = data[-cap:].decode('utf-8', errors='replace')
        while len(text.encode()) > cap:
            text = text[1:]
        body = {'started': True, 'cleanup': 'confirmed', 'output': text, 'truncated': truncated, 'merged': True,
                'result': summarize(text)}
        if exit_record.get('signal'):
            body['signal'] = exit_record['signal']
        else:
            body['exit_code'] = exit_record['exit_code']
        return self.receipt(request, 'completed', exec=body)

    def query(self, operation_id, request_digest):
        with self.db() as db:
            row = db.execute('SELECT request_digest, phase, request, receipt, pid FROM receipts WHERE operation_id=?',
                             (operation_id,)).fetchone()
        if not row or row[0] != request_digest:
            return {'found': False, 'authoritative': True}
        digest, phase, raw_request, raw_receipt, pid = row
        request = json.loads(raw_request)
        if phase == 'done':
            return {'found': True, 'receipt': json.loads(raw_receipt)}
        if phase == 'writing':
            # The intent exists; the file decides what happened, attributably.
            p = request['payload']
            current = self.state_of(self.target(p['workspace_id'], p['path']))
            if current.get('sha256') == p['content_sha256']:
                receipt = self.receipt(request, 'applied', write={'workspace_id': p['workspace_id'], 'path': p['path'],
                    'before': p['precondition'], 'after': {'sha256': p['content_sha256']},
                    'readback_sha256': p['content_sha256']})
                self.record(operation_id, digest, request, receipt)
                return {'found': True, 'receipt': receipt}
            with self.db() as db:
                db.execute('DELETE FROM receipts WHERE operation_id=? AND phase=?', (operation_id, 'writing'))
            return {'found': False, 'authoritative': True}
        if phase == 'starting':
            receipt = self.receipt(request, 'not_started', exec={'started': False, 'cleanup': 'not_applicable'},
                                   detail='Recorded intent; the process was never started')
            self.record(operation_id, digest, request, receipt)
            return {'found': True, 'receipt': receipt}
        output, status = self.paths(operation_id)
        receipt = self.finished(request, output, status)
        if receipt is None and not alive(pid):
            time.sleep(0.2)  # the supervisor writes its status just before exiting
            receipt = self.finished(request, output, status)
            if receipt is None:
                receipt = self.receipt(request, 'canceled', exec={'started': True, 'cleanup': 'confirmed'},
                                       detail='Supervisor ended without recording an exit status')
        if receipt is None:
            return {'found': True, 'receipt': json.loads(raw_receipt)}
        self.record(operation_id, digest, request, receipt)
        return {'found': True, 'receipt': receipt}

    def cancel(self, operation_id, request_digest, reason):
        found = self.query(operation_id, request_digest)
        if not found.get('found'):
            raise effects.ResponseLost('No record of this operation')
        receipt = found['receipt']
        if receipt['payload']['state'] != 'running':
            return {'receipt': receipt}
        with self.db() as db:
            raw_request, pid = db.execute('SELECT request, pid FROM receipts WHERE operation_id=?',
                                          (operation_id,)).fetchone()
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        deadline = time.monotonic() + 5
        while alive(pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        if alive(pid):
            raise effects.ResponseLost('Kill sent; process group still alive')
        request = json.loads(raw_request)
        stopped = self.receipt(request, 'timed_out' if reason == 'timeout' else 'canceled',
                               exec={'started': True, 'cleanup': 'confirmed', 'signal': 'SIGKILL'})
        self.record(operation_id, request_digest, request, stopped)
        return {'receipt': stopped}


def alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        finished, _ = os.waitpid(pid, os.WNOHANG)
        if finished == pid:
            return False
    except ChildProcessError:
        pass  # not our child (e.g. after a runtime restart); fall back to a signal probe
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    status = Path(f'/proc/{pid}/stat')
    return not (status.exists() and ') Z ' in status.read_text())


PYTEST_SUMMARY = re.compile(r'(\d+) (passed|failed|errors?|skipped)')


def summarize(output: str) -> dict:
    """Small, flat, best-effort structured result from well-known tool summaries."""
    result = {}
    tail = output.strip().splitlines()[-3:]
    for line in tail:
        for count, word in PYTEST_SUMMARY.findall(line):
            result[{'error': 'errors'}.get(word, word)] = int(count)
    verdict = re.search(r'"result":\s*"(PASS|FAIL|BLOCKED)"', output)  # verification.cli JSON report
    if verdict:
        result['verification'] = verdict.group(1)
    for line in tail:
        match = re.search(r'\b(PASS|FAIL|BLOCKED)\b', line)
        if match and 'verification' not in result:
            result['verification'] = match.group(1)
    return result


def supervise(output: str, status: str, cwd: str, argv: list[str]) -> int:
    """Run argv (exact, no shell) in cwd, capture merged output, record the exit durably."""
    env = {k: v for k, v in os.environ.items() if k != 'PYTHONPATH'}
    with open(output, 'wb') as sink:
        try:
            process = subprocess.Popen(argv, cwd=cwd, stdout=sink, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL, env=env)
            code = process.wait()
            record = {'exit_code': code} if code >= 0 else {'signal': signal.Signals(-code).name}
        except OSError as error:
            sink.write(f'cannot start: {error}\n'.encode())
            record = {'exit_code': 127}
    staging = status + '.tmp'
    Path(staging).write_text(json.dumps(record))
    os.replace(staging, status)
    return 0


if __name__ == '__main__':
    if len(sys.argv) >= 6 and sys.argv[1] == 'supervise' and sys.argv[5] == '--':
        sys.exit(supervise(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[6:]))
    sys.exit(2)
