#!/usr/bin/env python3
"""Prepare only the explicitly authorized existing volume; never format/repair.

Requires local root authentication. Preserves historical file bytes and metadata,
creates only /blaine on the volume, and records a before/after inventory digest.
Does not deploy services, select live backup sources, or start a backup.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile

import backup

UUID = "2415dac3-9d47-470f-8e00-2766bfbb821e"
MOUNT = Path("/srv/blaine-backup")
STATE = Path("/var/lib/blaine-backup")
OPTIONS = "nofail,noatime,nodev,nosuid,noexec,x-systemd.device-timeout=10s"
ENTRY = f"UUID={UUID} {MOUNT} ext4 {OPTIONS} 0 0"
REQUIRED_HISTORY = {"home", "inventory", "shell", "system"}


def fstab_text(current):
    matches = []
    for line in current.splitlines():
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        if len(fields) > 1 and (UUID in fields[0] or fields[1] == str(MOUNT)):
            matches.append(fields)
    if matches:
        if matches != [ENTRY.split()]:
            raise backup.Refused("existing fstab entry contradicts the authorized mount; review manually")
        return current
    return current + ("" if current.endswith("\n") else "\n") + "# Blaine D1: preserve historical data; manage only /blaine\n" + ENTRY + "\n"


def historical_inventory(root):
    """Hash metadata and all regular bytes without following links or atime writes.

    Keep only the aggregate in evidence; historical filenames and contents never
    enter Git or stdout. Exclude exactly the authorized new subtree.
    """
    digest = hashlib.sha256()
    counts = {"entries": 0, "regular_bytes": 0}
    device = root.stat().st_dev
    top = sorted(p.name for p in root.iterdir() if p.name != "blaine")
    def visit(path):
        info = path.lstat()
        if info.st_dev != device:
            raise backup.Refused("historical tree contains a nested filesystem")
        metadata = [str(path.relative_to(root)), info.st_ino, info.st_mode, info.st_uid,
                    info.st_gid, info.st_nlink, info.st_size, info.st_mtime_ns,
                    info.st_ctime_ns, info.st_atime_ns]
        xattrs = hashlib.sha256()
        for key in sorted(os.listxattr(path, follow_symlinks=False)):
            xattrs.update(key.encode() + b"\0" + os.getxattr(path, key, follow_symlinks=False))
        metadata.append(xattrs.hexdigest())
        if stat.S_ISREG(info.st_mode):
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NOATIME | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as stream:
                metadata.append(hashlib.file_digest(stream, "sha256").hexdigest())
            counts["regular_bytes"] += info.st_size
        elif stat.S_ISLNK(info.st_mode):
            metadata.append(os.readlink(path))
        digest.update(json.dumps(metadata, ensure_ascii=True).encode() + b"\n")
        counts["entries"] += 1
        if stat.S_ISDIR(info.st_mode):
            for child in sorted(path.iterdir()):
                visit(child)
    for name in top:
        visit(root / name)
    return {"sha256": digest.hexdigest(), **counts, "required_top_directories_present":
            {name: (root / name).is_dir() and not (root / name).is_symlink() for name in sorted(REQUIRED_HISTORY)}}


def capacity():
    info = os.statvfs(MOUNT)
    return {"total_bytes": info.f_blocks * info.f_frsize, "available_bytes": info.f_bavail * info.f_frsize}


def main():
    if os.geteuid() != 0:
        raise backup.Refused("run this bounded preparation command with local sudo authentication")
    os.umask(0o077)
    original = Path("/etc/fstab").read_text()
    desired = fstab_text(original)
    devices = backup.run(["blkid", "-t", "UUID=" + UUID, "-o", "device"], stdout=subprocess.PIPE).stdout.decode().splitlines()
    if len(devices) != 1:
        raise backup.Refused("authorized UUID is not unique")
    kind = backup.run(["blkid", "-s", "TYPE", "-o", "value", devices[0]], stdout=subprocess.PIPE).stdout.decode().strip()
    if kind != "ext4":
        raise backup.Refused("authorized filesystem is not ext4")
    mounted = subprocess.run(["findmnt", "-rn", "-S", "UUID=" + UUID, "-o", "TARGET"], capture_output=True, text=True)
    targets = mounted.stdout.splitlines()
    if targets and targets != [str(MOUNT)]:
        raise backup.Refused("authorized filesystem is mounted elsewhere; no remount or unmount attempted")
    if not targets:
        if MOUNT.exists() and (MOUNT.is_symlink() or not MOUNT.is_dir() or any(MOUNT.iterdir())):
            raise backup.Refused("mountpoint is not an empty plain directory")
        MOUNT.mkdir(mode=0o755, exist_ok=True)
        backup.plain_directory(MOUNT)
        backup.run(["mount", "-t", "ext4", "-o", "noatime,nodev,nosuid,noexec", "UUID=" + UUID, str(MOUNT)])
    backup.mount_identity(MOUNT, UUID)
    current_options = backup.run(["findmnt", "-rn", "--mountpoint", str(MOUNT), "-o", "OPTIONS"], stdout=subprocess.PIPE).stdout.decode().strip().split(",")
    if "noatime" not in current_options:
        raise backup.Refused("mount must use noatime before inspecting historical metadata")
    STATE.mkdir(mode=0o700, exist_ok=True)
    backup.plain_directory(STATE)
    before = historical_inventory(MOUNT)
    if not all(before["required_top_directories_present"].values()):
        raise backup.Refused("expected historical directories are missing; no correction attempted")
    baseline_file = STATE / "historical-baseline.json"
    subtree = MOUNT / "blaine"
    if subtree.exists() or subtree.is_symlink():
        if not baseline_file.exists() or json.loads(baseline_file.read_text()) != before:
            raise backup.Refused("existing Blaine subtree has no matching preparation baseline")
        info = subtree.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise backup.Refused("existing Blaine subtree has unexpected type/ownership/permissions")
    else:
        backup.atomic_json(baseline_file, before)
    available_before = capacity()
    if available_before["available_bytes"] < 1024 ** 3:
        raise backup.Refused("less than one GiB free before subtree preparation")
    subtree.mkdir(mode=0o700, exist_ok=True)
    after = historical_inventory(MOUNT)
    if before != after:
        raise backup.Refused("historical inventory changed; stop and inspect, never repair automatically")
    if desired != original:
        saved = STATE / "fstab.before-d1"
        if not saved.exists():
            with saved.open("x") as stream:
                stream.write(original)
        fd, temporary = tempfile.mkstemp(prefix=".fstab-blaine-d1-", dir="/etc")
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(desired)
                stream.flush()
                os.fsync(stream.fileno())
            backup.run(["findmnt", "--verify", "--tab-file", temporary], stdout=subprocess.DEVNULL)
            if Path("/etc/fstab").read_text() != original:
                raise backup.Refused("fstab changed concurrently; no replacement attempted")
            os.chmod(temporary, stat.S_IMODE(Path("/etc/fstab").stat().st_mode))
            os.replace(temporary, "/etc/fstab")
        finally:
            Path(temporary).unlink(missing_ok=True)
    result = {"stage": "volume-preparation", "result": "PASS", "filesystem_uuid": UUID,
              "mount": str(MOUNT), "subtree": str(subtree), "before": before, "after": after,
              "capacity_before": available_before, "capacity_after": capacity(),
              "persistent_fstab_entry": ENTRY, "backup_executed": False, "services_deployed": False}
    # Public summary contains aggregates only. Full disk contents are never printed.
    backup.atomic_json(STATE / "volume-preparation.json", result)
    backup.atomic_json(Path("/run/blaine-d1-volume-result.json"), result)
    os.chmod("/run/blaine-d1-volume-result.json", 0o644)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        reason = str(error) if isinstance(error, backup.Refused) else type(error).__name__
        raise SystemExit("STOP: " + reason)
