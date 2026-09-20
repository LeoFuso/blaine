#!/usr/bin/env python3
"""Bounded D1 official-package installation. Run with sudo, never run Codex as root."""
import json
import os
from pathlib import Path
import subprocess
import urllib.request

PACKAGES = {
    "docker-ce": "5:29.8.1-1~ubuntu.26.04~resolute",
    "docker-ce-cli": "5:29.8.1-1~ubuntu.26.04~resolute",
    "containerd.io": "2.3.5-1~ubuntu.26.04~resolute",
    "docker-buildx-plugin": "0.37.1-1~ubuntu.26.04~resolute",
    "docker-compose-plugin": "5.5.1-1~ubuntu.26.04~resolute",
    "alloy": "1.19.2-1",
}


def run(*args, capture=False):
    return subprocess.run(args, check=True, text=True,
                          stdout=subprocess.PIPE if capture else None).stdout


def install_file(path, content):
    path = Path(path)
    if path.is_symlink():
        raise RuntimeError(f"STOP: symlink at {path}")
    if path.exists() and path.read_bytes() != content:
        raise RuntimeError(f"STOP: existing different configuration at {path}")
    if not path.exists():
        path.write_bytes(content)
        path.chmod(0o644)


def main():
    if os.geteuid() != 0:
        raise SystemExit("Run this bounded installer with sudo.")
    release = Path('/etc/os-release').read_text()
    if 'VERSION_CODENAME=resolute' not in release or run('dpkg', '--print-architecture', capture=True).strip() != 'amd64':
        raise SystemExit('STOP: package pins require Ubuntu resolute amd64')
    for name in ['docker.io', 'docker-compose', 'docker-compose-v2', 'podman-docker', 'containerd', 'runc']:
        p = subprocess.run(['dpkg-query', '-W', '-f=${db:Status-Status}', name], capture_output=True, text=True)
        if p.stdout == 'installed':
            raise SystemExit(f'STOP: inspect conflicting runtime package {name} before removal')
    marker = Path('/var/lib/blaine-platform/packages.json')
    if not marker.exists():
        for path in ['/var/lib/docker', '/var/lib/containerd']:
            p = Path(path)
            if p.exists() and any(p.iterdir()):
                raise SystemExit(f'STOP: valuable/unknown existing runtime data at {path}')
    run('systemctl', 'disable', '--now', 'blaine-partial-backup.timer')
    # Do not inspect or retry the failed backup execution.
    Path('/etc/apt/keyrings').mkdir(mode=0o755, exist_ok=True)
    for name, url in [('docker', 'https://download.docker.com/linux/ubuntu/gpg'),
                      ('grafana', 'https://apt.grafana.com/gpg-full.key')]:
        install_file(f'/etc/apt/keyrings/{name}.asc', urllib.request.urlopen(url, timeout=60).read())
    install_file('/etc/apt/sources.list.d/blaine-docker.sources', b'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: resolute\nComponents: stable\nArchitectures: amd64\nSigned-By: /etc/apt/keyrings/docker.asc\n')
    install_file('/etc/apt/sources.list.d/blaine-grafana.list', b'deb [signed-by=/etc/apt/keyrings/grafana.asc] https://apt.grafana.com stable main\n')
    # needrestart list-only: no unrelated service restart or session disruption.
    os.environ.update(DEBIAN_FRONTEND='noninteractive', NEEDRESTART_MODE='l')
    run('apt-get', 'update')
    run('apt-get', 'install', '-y', '--no-install-recommends',
        *[f'{name}={version}' for name, version in PACKAGES.items()])
    marker.parent.mkdir(mode=0o755, exist_ok=True)
    observed = {name: run('dpkg-query', '-W', '-f=${Version}', name, capture=True) for name in PACKAGES}
    marker.write_text(json.dumps({'packages': observed, 'acceptance': 'pending'}, indent=2) + '\n')
    marker.chmod(0o644)
    run('systemctl', 'enable', '--now', 'docker.service')
    run('docker', 'version')
    run('docker', 'compose', 'version')
    print('D1 packages installed. Container/restart/application acceptance is still pending.')


if __name__ == '__main__':
    main()
