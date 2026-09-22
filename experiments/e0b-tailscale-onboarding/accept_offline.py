#!/usr/bin/env python3
"""E0.A ACP/standalone regression, with E0.B connect/doctor expectations.
No installation, login or real Tailscale command is invoked (PATH is empty).
"""
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_line(stream):
    assert select.select([stream], [], [], 3)[0], 'fixture readiness timeout'
    return stream.readline()


def run(binary):
    with tempfile.TemporaryDirectory(prefix='blaine-e0b-offline-') as directory:
        root = Path(directory)
        installed = root / 'blaine'
        shutil.copy2(binary, installed)
        (root / 'home').mkdir()
        (root / 'empty-path').mkdir()
        env = {'HOME': str(root / 'home'), 'PATH': str(root / 'empty-path'),
               'XDG_CONFIG_HOME': str(root / 'home' / 'config'),
               'XDG_STATE_HOME': str(root / 'home' / 'state')}

        def invoke(*args, data=b''):
            return subprocess.run([str(installed), *args], input=data, env=env,
                                  cwd=root, capture_output=True, timeout=8)

        version = invoke('version')
        version_json = invoke('version', '--json')
        assert version.returncode == version_json.returncode == 0
        assert not version.stderr and not version_json.stderr
        metadata = json.loads(version_json.stdout)
        doctor = invoke('doctor')
        doctor_json = invoke('doctor', '--json')
        assert doctor.returncode == doctor_json.returncode == 2
        report = json.loads(doctor_json.stdout)
        assert report['overall'] == 'NOT_READY'
        assert all(c['status'] == 'UNKNOWN' for c in report['checks']
                   if c['id'] in ['remote_blaine', 'restate', 'mirix', 'qwen', 'intellij_acp'])
        assert list((root / 'home').iterdir()) == [], 'doctor created config/state'

        for command in ['disconnect']:
            result = invoke(command)
            assert result.returncode == 2 and json.loads(result.stdout)['status'] == 'NOT_IMPLEMENTED'
        missing = invoke('connect', '--non-interactive')
        assert missing.returncode == 2 and b'Network prerequisite ready' not in missing.stdout
        assert next(c for c in report['checks'] if c['id'] == 'tailscale')['code'] == 'INSTALL_REQUIRED'
        for args in [('acp',), ('acp', '--unknown'), ('acp', '--fixture', 'invalid'),
                     ('acp', '--fixture', 'echo', 'extra')]:
            result = invoke(*args)
            assert result.returncode in (2, 64) and result.stdout == b'' and result.stderr

        payload = (b'{"jsonrpc":"2.0","id":1,"method":"initialize"}\r\n'
                   + bytes(range(256))) * 1000
        echoed = invoke('acp', '--fixture', 'echo', data=payload)
        assert echoed.returncode == 0 and echoed.stdout == payload
        assert b'fixture child diagnostic' in echoed.stderr and b'fixture exited: 0' in echoed.stderr
        empty = invoke('acp', '--fixture', 'echo')
        assert empty.returncode == 0 and empty.stdout == b'' and empty.stderr
        exited = invoke('acp', '--fixture', 'exit-23')
        assert exited.returncode == 23 and exited.stdout == b''

        # Prove duplex streaming before EOF, not just buffered communicate().
        process = subprocess.Popen([str(installed), 'acp', '--fixture', 'echo'],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   cwd=root, env=env, bufsize=0)
        try:
            for chunk in [b'partial', b'\x00\xff\n', 'λ without newline'.encode()]:
                process.stdin.write(chunk)
                received = b''
                while len(received) < len(chunk):
                    assert select.select([process.stdout], [], [], 3)[0], 'stream blocked until EOF'
                    received += os.read(process.stdout.fileno(), len(chunk) - len(received))
                assert received == chunk
            process.stdin.close()
            process.stdin = None
            remaining, diagnostics = process.communicate(timeout=3)
            assert remaining == b'' and process.returncode == 0 and diagnostics
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()

        cleanup = []
        for sig in [signal.SIGINT, signal.SIGTERM]:
            process = subprocess.Popen([str(installed), 'acp', '--fixture', 'wait'],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       env=env, cwd=root, bufsize=0)
            try:
                first, second = read_line(process.stderr), read_line(process.stderr)
                child_ids = sorted({int(pid) for entry in Path(f'/proc/{process.pid}/task').glob('*/children')
                                    for pid in entry.read_text().split()})
                assert child_ids, 'no live subprocess observed'
                process.send_signal(sig)
                out, err = process.communicate(timeout=3)
                assert process.returncode == 130 and out == b''
                assert all(not Path(f'/proc/{pid}').exists() for pid in child_ids), 'unreaped direct child'
                cleanup.append({'signal': sig.name, 'exit': process.returncode,
                                'direct_children_observed': len(child_ids), 'children_reaped': True,
                                'stdout_bytes': len(out), 'stderr': (first + second + err).decode()})
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        timeout = invoke('acp', '--fixture', 'wait')
        assert timeout.returncode == 124 and timeout.stdout == b''
        oversize = invoke('acp', '--fixture', 'echo', data=b'x' * ((1 << 20) + 2))
        assert oversize.returncode == 1 and b'input limit exceeded' in oversize.stderr
        assert list((root / 'home').iterdir()) == [], 'client persisted state'
        return {
            'result': 'PASS', 'scope': 'Linux amd64 runtime; no network/IDE/remote ACP',
            'standalone': {'copied_outside_checkout': True, 'PATH_contains_no_commands': True,
                           'home_unchanged': True, 'binary_sha256': digest(installed.read_bytes())},
            'version_default': version.stdout.decode(), 'version_json': metadata,
            'doctor_exit': doctor.returncode, 'doctor_default': doctor.stdout.decode(), 'doctor_json': report,
            'stdio': {'input_bytes': len(payload), 'stdout_bytes': len(echoed.stdout),
                      'input_sha256': digest(payload), 'stdout_sha256': digest(echoed.stdout),
                      'stderr': echoed.stderr.decode(), 'exit': echoed.returncode,
                      'empty_input_pass': True, 'streaming_before_eof_pass': True,
                      'malformed_invocations_stdout_empty': True, 'exit_23_propagated': True,
                      'byte_limit_exit': oversize.returncode, 'deadline_exit': timeout.returncode},
            'signals': cleanup,
        }


if __name__ == '__main__':
    result = run(Path(sys.argv[1]).resolve())
    print(json.dumps(result, indent=2))
