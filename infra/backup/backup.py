#!/usr/bin/env python3
"""D1 partial backup: PostgreSQL and the existing immutable kernel file store.

This does not implement S3 backup or certify durable-brain coverage. No mount,
format, live restore, shell evaluation, credential output, or cloud transport.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import uuid

COVERAGE = "postgresql-and-kernel-artifacts-only"
GENERATION = re.compile(r"\d{8}T\d{6}Z-[0-9a-f]{12}")
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,80}")
DIGEST = re.compile(r"[0-9a-f]{64}")


class Refused(RuntimeError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat()


def run(command, **kwargs):
    result = subprocess.run(command, stderr=subprocess.PIPE, **kwargs)
    if result.returncode:
        # Database diagnostics can contain data/credentials. Do not journal them.
        raise Refused(f"{Path(command[0]).name} failed (exit {result.returncode}); inspect access and server logs locally")
    return result


def plain_directory(path):
    path = Path(path)
    if not path.is_absolute() or path.resolve() != path or not path.is_dir():
        raise Refused("directory must exist, be absolute, and contain no symlinks")
    return path


def mount_identity(path, expected_uuid):
    if not expected_uuid or not re.fullmatch(r"[A-Za-z0-9-]+", expected_uuid):
        raise Refused("expected filesystem UUID is not configured")
    result = run(["findmnt", "--json", "--mountpoint", str(path),
                  "--output", "TARGET,UUID,FSTYPE,FSROOT,OPTIONS"], stdout=subprocess.PIPE)
    mounts = json.loads(result.stdout).get("filesystems", [])
    if len(mounts) != 1:
        raise Refused("destination is not one exact mounted filesystem")
    mount = mounts[0]
    if (mount["target"] != str(path) or mount["uuid"] != expected_uuid
            or mount["fstype"] not in {"ext4", "xfs"}
            or mount["fsroot"] != "/" or "rw" not in mount["options"].split(",")):
        raise Refused("destination filesystem identity/type/root/writability mismatch")
    if path.stat().st_dev == Path("/").stat().st_dev:
        raise Refused("backup filesystem is the root filesystem")


@contextmanager
def destination(config):
    """Pin the verified mount as cwd; a detach cannot redirect writes to root.

    No destination directories are created before this guard. No test bypass.
    Tests call snapshot() directly on their private scratch directory.
    """
    path = plain_directory(config["mount"])
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    previous = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
    try:
        mount_identity(path, config["filesystem_uuid"])
        if os.fstat(fd).st_dev != path.stat().st_dev or os.fstat(fd).st_ino != path.stat().st_ino:
            raise Refused("mount changed during validation")
        os.fchdir(fd)
        # Recheck after pinning. All backup writes below are relative to cwd.
        mount_identity(path, config["filesystem_uuid"])
        yield
    finally:
        os.fchdir(previous)
        os.close(previous)
        os.close(fd)


def atomic_json(path, value):
    temporary = path.with_name(path.name + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pg(config, tool, database=None):
    pgconfig = config["postgres"]
    if not str(pgconfig["host"]).startswith("/"):
        raise Refused("D1 PostgreSQL backup requires a local Unix socket")
    command = [str(Path(pgconfig["bin"]) / tool), "--no-password",
               "--host", pgconfig["host"], "--port", str(pgconfig["port"]),
               "--username", pgconfig["user"]]
    if pgconfig.get("os_user"):
        command = ["/usr/sbin/runuser", "-u", pgconfig["os_user"], "--", *command]
    if database:
        command += ["--dbname", database]
    return command


def safe_files(root):
    """Reject symlinks, special files and nested mounts before reading/removal."""
    device = root.stat().st_dev
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            path = Path(directory) / name
            info = path.lstat()
            if info.st_dev != device or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise Refused("snapshot tree contains a link, mount or special file")
            if stat.S_ISREG(info.st_mode):
                yield path


def verify(root, pg_bin):
    if root.is_symlink() or not root.is_dir():
        raise Refused("invalid snapshot directory")
    files = {str(p.relative_to(root)): p for p in safe_files(root)}
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("coverage") != COVERAGE or manifest.get("complete_durable_brain") is not False:
        raise Refused("unknown backup coverage")
    expected = manifest["files"]
    if set(files) != set(expected) | {"manifest.json"}:
        raise Refused("snapshot file set mismatch")
    for name, digest in expected.items():
        if sha256(files[name]) != digest:
            raise Refused("snapshot checksum mismatch")
        if name.endswith(".dump"):
            run([str(Path(pg_bin) / "pg_restore"), "--list", str(files[name])], stdout=subprocess.DEVNULL)
    return manifest


def prune(root, keep, pg_bin):
    generations = [p for p in root.iterdir() if GENERATION.fullmatch(p.name)]
    # Validate every candidate BEFORE deleting anything. Failed/incomplete and
    # foreign directories are retained for explicit operator inspection.
    created = {p: verify(p, pg_bin)["created_at"] for p in generations}
    generations.sort(key=lambda p: created[p])
    for candidate in generations[:-keep]:
        shutil.rmtree(candidate)


def snapshot(config, root):
    """Write only beneath caller's guarded root; also used by isolated fixtures."""
    if config.get("coverage") != COVERAGE:
        raise Refused("explicit partial coverage acknowledgement is required; S3 is not implemented")
    databases = config["postgres"]["databases"]
    if not databases or len(set(databases)) != len(databases) or any(not IDENTIFIER.fullmatch(d) for d in databases):
        raise Refused("explicit distinct simple database names required")
    keep = config["keep_last"]
    if type(keep) is not int or not 1 <= keep <= 365:
        raise Refused("keep_last must be between 1 and 365")
    sources = config["artifact_roots"]
    if not sources:
        raise Refused("explicit kernel artifact sources required; no S3 source discovered")
    for name, path in sources.items():
        if not IDENTIFIER.fullmatch(name):
            raise Refused("invalid artifact source label")
        plain_directory(path)
    generation = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12]
    partial = root / (".incomplete-" + generation)
    partial.mkdir(mode=0o700)
    (partial / "postgres").mkdir(mode=0o700)
    with (partial / "postgres/globals.sql").open("xb") as output:
        run(pg(config, "pg_dumpall") + ["--globals-only", "--no-role-passwords"], stdout=output)
    for database in databases:
        with (partial / "postgres" / (database + ".dump")).open("xb") as output:
            run(pg(config, "pg_dump", database) + ["--format=custom", "--create"], stdout=output)
    for name, source in sources.items():
        source = Path(source)
        for path in sorted(safe_files(source)):
            relative = path.relative_to(source)
            if len(relative.parts) != 2 or not IDENTIFIER.fullmatch(relative.parts[0]) or not DIGEST.fullmatch(relative.name):
                raise Refused("artifact source is not a quiescent kernel content-addressed store")
            target = partial / "artifacts" / name / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            with os.fdopen(fd, "rb") as input_stream, target.open("xb") as output_stream:
                if not stat.S_ISREG(os.fstat(input_stream.fileno()).st_mode):
                    raise Refused("artifact changed to a special file")
                shutil.copyfileobj(input_stream, output_stream)
            if sha256(target) != relative.name:
                raise Refused("artifact content hash mismatch")
    manifest = {"version": 1, "created_at": now(), "coverage": COVERAGE,
                "complete_durable_brain": False, "restore_test": "not-performed",
                "databases": databases, "artifact_sources": list(sources),
                "files": {str(p.relative_to(partial)): sha256(p) for p in safe_files(partial)}}
    atomic_json(partial / "manifest.json", manifest)
    verify(partial, config["postgres"]["bin"])
    # Flush payloads and directory entries before reporting publication.
    for path in safe_files(partial):
        with path.open("rb") as stream:
            os.fsync(stream.fileno())
    for directory, _, _ in os.walk(partial, topdown=False):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    final = root / generation
    partial.rename(final)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    prune(root, keep, config["postgres"]["bin"])
    return generation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["preflight", "partial-backup", "status", "verify"])
    parser.add_argument("--config", default="/etc/blaine/backup.json")
    parser.add_argument("--generation")
    args = parser.parse_args()
    os.umask(0o077)
    status = None
    state_path = None
    try:
        config = json.loads(Path(args.config).read_text())
        state = plain_directory(config["status_directory"])
        state_path = state / "status.json"
        if state_path.is_symlink():
            raise Refused("status file must not be a symlink")
        status = json.loads(state_path.read_text()) if state_path.exists() else {}
        if args.action == "status":
            if status.get("last_success"):
                status["age_seconds"] = int((datetime.now(timezone.utc) - datetime.fromisoformat(status["last_success"])).total_seconds())
            print(json.dumps(status or {"result": "never-attempted"}, indent=2))
            return
        fd = os.open(state / "backup.lock", os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "w"):
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Refused("another backup/verification holds the lock")
            status.update(last_attempt=now(), action=args.action, destination=config["mount"],
                          result="running", failure_reason=None, coverage=COVERAGE,
                          complete_durable_brain=False)
            if args.action == "partial-backup":
                status["last_backup_attempt"] = now()
            atomic_json(state_path, status)
            try:
                with destination(config):
                    root = Path("blaine-partial-backups")
                    if root.is_symlink():
                        raise Refused("backup namespace must not be a symlink")
                    if args.action == "partial-backup":
                        root.mkdir(mode=0o700, exist_ok=True)
                        if root.stat().st_uid != os.geteuid() or root.stat().st_mode & 0o022:
                            raise Refused("backup namespace must be owned by the backup user and not writable by others")
                        if root.stat().st_dev != Path(".").stat().st_dev:
                            raise Refused("backup namespace is a different mounted filesystem")
                        generation = snapshot(config, root)
                        status.update(last_success=now(), generation=generation,
                                      verification="checksums-and-pg-archive-catalog; restore-not-proven")
                    elif args.action == "verify":
                        if not args.generation or not GENERATION.fullmatch(args.generation):
                            raise Refused("verify requires an explicit generation")
                        verify(root / args.generation, config["postgres"]["bin"])
                        status.update(last_verification=now(), verified_generation=args.generation,
                                      verification="checksums-and-pg-archive-catalog; restore-not-proven")
                status.update(result="ok", finished_at=now())
            except Exception as error:
                reason = str(error) if isinstance(error, Refused) else type(error).__name__
                status.update(result="failed", finished_at=now(), failure_reason=reason)
                raise
            finally:
                atomic_json(state_path, status)
        print(json.dumps(status, indent=2))
    except Exception as error:
        # Print only controlled errors; unexpected exceptions may include secrets.
        reason = str(error) if isinstance(error, Refused) else type(error).__name__
        print(f"backup refused/failed: {reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
