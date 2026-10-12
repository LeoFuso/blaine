#!/usr/bin/env python3
"""Operator-run E0.C transport spike. No installation, profile or policy changes.
Python 3 standard library only. Run on the designated Mac or inside Ubuntu WSL2.
Raw SSH diagnostics/authentication URLs are never retained in the JSON report.
"""
import json
import os
from pathlib import Path
import platform
import selectors
import shlex
import shutil
import signal
import subprocess
import tempfile
import time

TARGET = 'leofuso@blaine'


def remote(code):
    return 'python3 -c ' + shlex.quote(code)


def kill_group(p):
    try:
        os.killpg(p.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run(argv, data=b'', timeout=30):
    # Real file descriptors, with no shell or text decoding in transport.
    with tempfile.TemporaryFile() as src, tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        src.write(data)
        src.seek(0)
        p = subprocess.Popen(argv, stdin=src, stdout=out, stderr=err, start_new_session=True)
        try:
            p.wait(timeout=timeout)
        finally:
            kill_group(p)
            p.wait()
        out.seek(0)
        err.seek(0)
        return p.returncode, out.read(), err.read()


def cancellation(base, sig):
    # Bounded remote probe: self-expires even if the client loses its connection.
    code = ('import os,sys,signal; signal.alarm(45); '
            'print(os.getpid(),flush=True); sys.stdin.buffer.read()')
    with tempfile.TemporaryFile() as errors:
        p = subprocess.Popen(base + [remote(code)], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=errors, start_new_session=True)
        remote_pid = None
        try:
            with selectors.DefaultSelector() as sel:
                sel.register(p.stdout, selectors.EVENT_READ)
                if not sel.select(20):
                    raise RuntimeError('remote probe did not become ready')
                line = os.read(p.stdout.fileno(), 64)
            if not line.strip().isdigit():
                raise RuntimeError('unexpected remote probe output')
            remote_pid = int(line.strip())
            os.killpg(p.pid, sig)
            try:
                p.wait(timeout=5)
                exited = True
            except subprocess.TimeoutExpired:
                exited = False
            # Mirror Blaine's unconditional local process-group cleanup.
            kill_group(p)
            p.wait()
            p.stdin.close()
            p.stdout.close()
            time.sleep(1)
            # Only inspect the exact probe process; never kill by name or guess.
            check = 'import os,sys; sys.exit(1 if os.path.exists("/proc/%d") else 0)' % remote_pid
            rc, out, err = run(base + [remote(check)])
            remote_gone = rc == 0 and not out and not err
            try:
                os.killpg(p.pid, 0)
                group_gone = False
            except ProcessLookupError:
                group_gone = True
            return {'signal': sig.name, 'leader_exited': exited,
                    'posix_group_absent': group_gone, 'remote_probe_absent': remote_gone,
                    'remote_pid': remote_pid, 'exit_code': p.returncode,
                    'status': 'PASS' if exited and group_gone and remote_gone else 'PARTIAL'}
        finally:
            kill_group(p)
            p.wait()
            if p.stdin and not p.stdin.closed:
                p.stdin.close()
            if p.stdout and not p.stdout.closed:
                p.stdout.close()


def main():
    wsl = 'microsoft' in platform.release().lower()
    if platform.system() != 'Darwin' and not wsl:
        raise RuntimeError('Run only on the designated Mac or inside Ubuntu WSL2')
    cli = shutil.which('tailscale.exe' if wsl else 'tailscale')
    if wsl and not cli:
        candidate = Path('/mnt/c/Program Files/Tailscale/tailscale.exe')
        if candidate.is_file():
            cli = str(candidate)
    if not cli:
        raise RuntimeError('Tailscale CLI unavailable; no installation or topology change attempted')
    base = [cli, 'ssh', TARGET]
    report = {'scope': 'E0.C transport spike, not Blaine handshake/ACP acceptance',
              'platform': platform.system(), 'architecture': platform.machine(), 'wsl': wsl,
              'cli': cli, 'target': TARGET, 'checks': [],
              'limitations': ['Host-key source requires separate implementation review; success alone is not proof.',
                              'Synthetic remote probes do not prove production dispatcher cleanup.']}
    if wsl:
        report['limitations'].append('POSIX group checks cannot certify cleanup of Windows-native descendants; Windows process inspection remains required.')
    print('Authenticate in your browser if prompted. Do not share authorization URLs.', flush=True)
    print('If asked to manually accept a host fingerprint, cancel; do not accept it.', flush=True)
    # Inherit terminal so normal Tailscale check-mode prompts remain usable.
    auth = subprocess.run(base + ['hostname; id -un'])
    if auth.returncode:
        raise RuntimeError('Interactive transport probe failed; stop here')
    rc, out, err = run(base + ['hostname; id -un'])
    identity = rc == 0 and out.splitlines() == [b'blaine', b'leofuso'] and not err
    report['checks'].append({'name': 'remote_host_and_account', 'status': 'PASS' if identity else 'FAIL'})
    if not identity:
        raise RuntimeError('Unexpected host/account or transport output; stop here')
    payload = bytes(range(256)) * 4096
    probe = remote('import sys; data=sys.stdin.buffer.read(); sys.stdout.buffer.write(data); sys.stdout.buffer.flush(); sys.stderr.buffer.write(b"E0C-STDERR\\n"); sys.exit(23)')
    rc, out, err = run(base + [probe], payload)
    for name, ok in [('binary_roundtrip_1MiB', out == payload),
                     ('stderr_isolation', err == b'E0C-STDERR\n'), ('remote_exit_23', rc == 23)]:
        report['checks'].append({'name': name, 'status': 'PASS' if ok else 'FAIL'})
    for sig in [signal.SIGINT, signal.SIGTERM, signal.SIGKILL]:
        report['checks'].append({'name': 'cancellation', **cancellation(base, sig)})
    report['status'] = 'PARTIAL' if wsl or any(x['status'] != 'PASS' for x in report['checks']) else 'PASS_SCOPED_PROBES'
    # Unique file, no credentials or raw transport diagnostics.
    fd, name = tempfile.mkstemp(prefix='blaine-e0c-transport-', suffix='.json', dir='.')
    with os.fdopen(fd, 'w') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps(report, indent=2))
    print('Report:', name)


if __name__ == '__main__':
    try:
        main()
    except (Exception, KeyboardInterrupt) as exc:
        print('STOP:', str(exc) if not isinstance(exc, KeyboardInterrupt) else 'operator cancelled')
        print('No transport acceptance claimed. Remote cancellation probes self-expire within 45 seconds.')
        raise SystemExit(2)
