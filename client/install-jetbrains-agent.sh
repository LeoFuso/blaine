#!/bin/sh
# Development scaffolding, not ACP Registry distribution. Python parses JSON;
# curl fetches only official release assets. No sudo or network configuration.
set -eu
command -v python3 >/dev/null 2>&1 || {
  echo 'Blaine installer requires Python 3. No files changed.' >&2
  exit 1
}
exec python3 - "$@" <<'PY'
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys
import tempfile

RELEASE = "v0.1.0-alpha.1"
REPOSITORY = "https://github.com/LeoFuso/blaine"
CONFIG_LIMIT = 1024 * 1024


def run(args):
    return subprocess.run(args, check=True, capture_output=True, text=True,
                          timeout=15).stdout.strip()


def detect():
    system = platform.system()
    arch = {"x86_64": "amd64", "amd64": "amd64", "arm64": "arm64",
            "aarch64": "arm64"}.get(platform.machine().lower())
    if system not in ("Darwin", "Linux") or arch is None:
        raise ValueError("Unsupported platform; use macOS or Linux/WSL amd64/arm64")
    wsl = system == "Linux" and "microsoft" in platform.release().lower()
    return system.lower(), arch, wsl


def targets(home, wsl):
    binary = home / ".local/bin/blaine"
    entry = {"command": str(binary), "args": ["acp"]}
    ide_home = home
    if wsl:
        distro = os.environ.get("WSL_DISTRO_NAME", "")
        if not distro or any(ord(c) < 32 for c in distro):
            raise ValueError("WSL_DISTRO_NAME unavailable; Windows IDE registration unresolved")
        # Fixed PowerShell program: no shell interpolation of usernames or paths.
        info = json.loads(run(["powershell.exe", "-NoProfile", "-NonInteractive",
                               "-Command", "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
                               "@{home=[Environment]::GetFolderPath('UserProfile'); "
                               "launcher=(Join-Path $env:WINDIR 'System32\\wsl.exe')} | ConvertTo-Json -Compress"]).lstrip("\ufeff"))
        ide_home = Path(run(["wslpath", "-u", info["home"]]))
        if not ide_home.is_absolute() or not ide_home.is_dir():
            raise ValueError("Windows user profile unavailable through WSL interop")
        entry = {"command": info["launcher"], "args": ["--distribution", distro,
                 "--exec", str(binary), "acp"]}
    return binary, ide_home / ".jetbrains/acp.json", entry


def safe_path(path, directory=False):
    # Refuse linked paths rather than modify an unexpected config or executable.
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ValueError("Symlink path refused: " + str(component))
    if path.exists():
        s = path.stat()
        kind = stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)
        if not kind or s.st_uid != os.getuid() or (not directory and s.st_nlink != 1):
            raise ValueError("Expected user-owned regular path: " + str(path))


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key; configuration left unchanged")
        result[key] = value
    return result


def read_config(path):
    safe_path(path)
    if not path.exists():
        return None, {"default_mcp_settings": {"use_custom_mcp": False,
                                               "use_idea_mcp": False},
                      "agent_servers": {}}
    if path.stat().st_size > CONFIG_LIMIT:
        raise ValueError("ACP configuration exceeds 1 MiB; review manually")
    original = path.read_bytes()
    doc = json.loads(original, object_pairs_hook=unique_object,
                     parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-JSON constant")))
    if not isinstance(doc, dict) or not isinstance(doc.get("agent_servers", {}), dict):
        raise ValueError("ACP configuration must contain an agent_servers object")
    if "default_mcp_settings" in doc and not isinstance(doc["default_mcp_settings"], dict):
        raise ValueError("Invalid default_mcp_settings object")
    for agent in doc.get("agent_servers", {}).values():
        if not isinstance(agent, dict):
            raise ValueError("Invalid agent entry; configuration left unchanged")
    return original, doc


def merge(doc, entry):
    agents = doc.setdefault("agent_servers", {})
    names = [name for name in agents if name.casefold() in ("blaine", "blaine e0.c candidate")]
    if len(names) > 1:
        raise ValueError("Multiple Blaine entries; refusing ambiguous registration")
    name = names[0] if names else "Blaine"
    exists = name in agents
    previous = agents.get(name, {})
    matches = all(previous.get(k) == v for k, v in entry.items())
    agents[name] = {**previous, **entry}
    return name, exists, matches


def version(binary):
    safe_path(binary)
    return json.loads(run([str(binary), "version", "--json"]))


def download(url, destination):
    subprocess.run(["curl", "-fsSL", "--proto", "=https", "--proto-redir", "=https",
                    "--connect-timeout", "15", "--max-time", "300", "--max-filesize",
                    "268435456", "-o", str(destination), url], check=True)


def verified_payload(asset, release, candidate, stage):
    if candidate:
        manifest = candidate / "checksums.txt"
        source = candidate / asset
        safe_path(manifest)
        safe_path(source)
    else:
        base = REPOSITORY + "/releases/download/" + release
        manifest, source = stage / "checksums.txt", stage / asset
        download(base + "/checksums.txt", manifest)
        download(base + "/" + asset, source)
    if manifest.stat().st_size > 65536:
        raise ValueError("Checksum manifest too large")
    matches = []
    for line in manifest.read_text().splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip("*") == asset:
            matches.append(fields[0])
    if len(matches) != 1 or not re.fullmatch(r"[0-9a-fA-F]{64}", matches[0]):
        raise ValueError("Expected exactly one SHA-256 entry for " + asset)
    # Copy and hash the exact bytes to be executed/installed, not a mutable source.
    payload = stage / "verified-blaine"
    digest = hashlib.sha256()
    with source.open("rb") as src, payload.open("wb") as dst:
        while chunk := src.read(1024 * 1024):
            digest.update(chunk)
            dst.write(chunk)
    if digest.hexdigest() != matches[0].lower():
        raise ValueError("SHA-256 mismatch; nothing installed or executed")
    payload.chmod(0o700)
    return payload, digest.hexdigest()


def atomic_write(path, data, mode):
    safe_path(path)
    fd, name = tempfile.mkstemp(prefix=".blaine-install-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as output:
            os.fchmod(output.fileno(), mode)
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextlib.contextmanager
def lock(directory):
    path = directory / ".blaine-install.lock"
    safe_path(path)
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Blaine development JetBrains ACP installer (no sudo)")
    parser.add_argument("--check", action="store_true", help="Read-only local status; no downloads")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--release", default=None, help="Explicit official v0.x.y-alpha.N release")
    source.add_argument("--candidate-dir", type=Path, help="Explicit local acceptance package with checksums.txt")
    args = parser.parse_args(argv)
    release = args.release or RELEASE
    if not re.fullmatch(r"v0\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)-alpha\.[1-9][0-9]*", release):
        raise ValueError("Expected an explicit v0.x.y-alpha.N release tag")
    system, arch, wsl = detect()
    asset = "blaine-" + system + "-" + arch
    home = Path.home()
    binary, config, entry = targets(home, wsl)
    for path in (binary, config, config.with_name("acp.json.blaine-backup")):
        safe_path(path)
        safe_path(path.parent, directory=True)
    original, doc = read_config(config)
    name, registered, matches = merge(doc, entry)
    print("Platform:", "wsl" if wsl else system, arch)
    print("Source:", "local acceptance candidate" if args.candidate_dir else release)
    print("Asset:", asset)
    print("Executable:", binary)
    print("ACP config:", config)
    print("Registration:", "present" if registered else "absent")
    print("Expected executable/arguments:", "matches" if matches else "not configured or different")
    installed = None
    if binary.exists():
        installed = version(binary)
        print("Installed:", installed.get("client_version"), "commit=" + str(installed.get("build_commit")))
    else:
        print("Installed: absent")
    if args.check:
        return
    if os.geteuid() == 0:
        raise ValueError("Run as the workstation user, without sudo")
    if not args.candidate_dir and release == RELEASE:
        print("NOTE: v0.1.0-alpha.1 uses the historical SSH transport; not direct-tsnet acceptance.")
        if installed and installed.get("client_version") != release[1:]:
            raise ValueError("Refusing to replace another client with the historical alpha; use --candidate-dir")
    with tempfile.TemporaryDirectory(prefix="blaine-installer-") as temp:
        # macOS temporary directories may start with the OS-owned /var symlink.
        payload, digest = verified_payload(asset, release, args.candidate_dir, Path(temp).resolve())
        metadata = version(payload)
        if (metadata.get("os") != system or metadata.get("arch") != arch or
                not re.fullmatch(r"[0-9a-f]{40}", str(metadata.get("build_commit", ""))) or
                metadata.get("protocol_version") != 1 or
                (not args.candidate_dir and metadata.get("client_version") != release[1:])):
            raise ValueError("Verified binary metadata does not match requested platform/release/protocol")
        print("SHA-256 verified:", digest)
        config.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        binary.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with lock(config.parent):
            current, _ = read_config(config)
            if current != original:
                raise ValueError("ACP config changed during download; rerun with IDE configuration closed")
            # Store at most one backup, only when configuration actually changes.
            if not matches:
                if original is not None:
                    atomic_write(config.with_name("acp.json.blaine-backup"), original, 0o600)
            content = payload.read_bytes()
            if not binary.exists() or binary.read_bytes() != content:
                atomic_write(binary, content, 0o755)
            if not matches:
                atomic_write(config, (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode(), 0o600)
    print("Installed:", metadata["client_version"], "commit=" + metadata["build_commit"])
    print("Open JetBrains AI Chat and select " + name + ". Restart the IDE if needed.")
    print("For E0.C, disable Pass custom MCP servers and Pass IntelliJ MCP server for Blaine in Agents settings.")
    if wsl:
        print("Windows IDE -> wsl.exe -> Linux blaine acp registered; real IDE interoperability is still an acceptance gate.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        # Do not dump configuration, environment, subprocess output or credentials.
        if isinstance(error, subprocess.SubprocessError):
            message = "Download, version check or Windows interop failed; installation not completed"
        else:
            message = str(error)
        print("STOP: " + message, file=sys.stderr)
        sys.exit(1)
PY
