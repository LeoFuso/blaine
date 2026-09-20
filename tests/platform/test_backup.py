"""Run: python3 -m unittest discover -s tests/platform -v

Real PostgreSQL fixture uses two private /tmp clusters, Unix sockets only, no
live credentials, and no production mount bypass exposed by the backup CLI.
"""
from contextlib import contextmanager
import importlib.util
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("backup", ROOT / "infra/backup/backup.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
sys.modules["backup"] = backup
PG = Path("/usr/lib/postgresql/18/bin")


class GuardTests(unittest.TestCase):
    def test_subtree_is_pinned_and_historical_paths_are_outside_destination(self):
        previous = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
        try:
            with tempfile.TemporaryDirectory(prefix="blaine-d1-") as tmp:
                root = Path(tmp)
                (root / "home").mkdir()
                (root / "home/proof").write_bytes(b"historical")
                (root / "blaine").mkdir(mode=0o700)
                os.chdir(root)
                with backup.owned_subtree():
                    self.assertEqual(Path.cwd(), root / "blaine")
                    Path("blaine-partial-backups").mkdir()
                self.assertEqual((root / "home/proof").read_bytes(), b"historical")
                self.assertFalse((root / "blaine-partial-backups").exists())
                os.fchdir(previous)
        finally:
            os.fchdir(previous)
            os.close(previous)

    def test_missing_or_symlink_subtree_is_never_created_or_followed(self):
        previous = os.open(".", os.O_RDONLY | os.O_DIRECTORY)
        try:
            with tempfile.TemporaryDirectory(prefix="blaine-d1-") as tmp:
                os.chdir(tmp)
                with self.assertRaises(OSError):
                    with backup.owned_subtree():
                        self.fail("missing subtree accepted")
                Path("blaine").symlink_to("/tmp")
                with self.assertRaises(OSError):
                    with backup.owned_subtree():
                        self.fail("symlink accepted")
                os.fchdir(previous)
        finally:
            os.fchdir(previous)
            os.close(previous)

    def test_insufficient_space_and_readonly_fail_before_writes(self):
        for free, flags in [(1024, 0), (1024 ** 4, os.ST_RDONLY)]:
            info = SimpleNamespace(f_bavail=free, f_frsize=1, f_flag=flags)
            with patch.object(backup.os, "statvfs", return_value=info), self.assertRaises(backup.Refused):
                backup.free_space({"min_free_bytes": 1024 ** 3})
        info = SimpleNamespace(f_bavail=2 * 1024 ** 3, f_frsize=1, f_flag=0)
        with patch.object(backup.os, "statvfs", return_value=info), self.assertRaises(backup.Refused):
            backup.free_space({"min_free_bytes": 1024 ** 3}, estimated_bytes=2 * 1024 ** 3)

    def test_real_unmounted_directory_fails_without_destination_writes(self):
        with tempfile.TemporaryDirectory(prefix="blaine-d1-") as tmp:
            root = Path(tmp)
            mount = root / "destination"
            mount.mkdir()
            state = root / "status"
            state.mkdir()
            config = root / "config.json"
            config.write_text(json.dumps({"mount": str(mount), "filesystem_uuid": "wrong-uuid",
                                          "status_directory": str(state)}))
            result = subprocess.run(["python3", str(ROOT / "infra/backup/backup.py"),
                                     "partial-backup", "--config", str(config)], capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(list(mount.iterdir()), [])
            status = json.loads((state / "status.json").read_text())
            self.assertEqual(status["result"], "failed")
            self.assertTrue(status["failure_reason"])
            self.assertNotIn("last_success", status)
            status["last_success"] = "2026-09-19T12:00:00+00:00"
            (state / "status.json").write_text(json.dumps(status))
            subprocess.run(["python3", str(ROOT / "infra/backup/backup.py"),
                            "partial-backup", "--config", str(config)], capture_output=True, check=False)
            self.assertEqual(json.loads((state / "status.json").read_text())["last_success"], status["last_success"])

    def test_lock_contention_preserves_active_status(self):
        with tempfile.TemporaryDirectory(prefix="blaine-d1-") as tmp:
            root = Path(tmp)
            config = root / "config.json"
            config.write_text(json.dumps({"status_directory": str(root)}))
            (root / "status.json").write_text('{"result": "running"}')
            with (root / "backup.lock").open("w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = subprocess.run(["python3", str(ROOT / "infra/backup/backup.py"),
                                         "partial-backup", "--config", str(config)], capture_output=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn(b"holds the lock", result.stderr)
            self.assertEqual(json.loads((root / "status.json").read_text()), {"result": "running"})

    def test_mount_rejects_wrong_uuid_root_bind_and_readonly(self):
        with tempfile.TemporaryDirectory(prefix="blaine-d1-") as tmp:
            root = Path(tmp)
            good = {"target": tmp, "uuid": "expected", "fstype": "ext4", "fsroot": "/", "options": "rw"}
            for changes in [{"uuid": "wrong"}, {"fsroot": "/subdir"}, {"options": "ro"}, {"fstype": "tmpfs"}]:
                result = subprocess.CompletedProcess([], 0, json.dumps({"filesystems": [good | changes]}).encode())
                with self.subTest(changes=changes), patch.object(backup, "run", return_value=result):
                    with self.assertRaises(backup.Refused):
                        backup.mount_identity(root, "expected")
            result = subprocess.CompletedProcess([], 0, json.dumps({"filesystems": [good | {"target": "/"}]}).encode())
            with patch.object(backup, "run", return_value=result), self.assertRaises(backup.Refused):
                backup.mount_identity(Path("/"), "expected")

    def test_symlink_destination_rejected(self):
        with tempfile.TemporaryDirectory(prefix="blaine-d1-") as tmp:
            link = Path(tmp) / "link"
            link.symlink_to(tmp)
            with self.assertRaises(backup.Refused):
                with backup.destination({"mount": str(link), "filesystem_uuid": "expected"}):
                    self.fail("guard yielded")

    def test_symlink_and_special_file_artifacts_rejected(self):
        with tempfile.TemporaryDirectory(prefix="blaine-d1-") as tmp:
            root = Path(tmp)
            (root / "link").symlink_to("/etc/passwd")
            with self.assertRaises(backup.Refused):
                list(backup.safe_files(root))
            (root / "link").unlink()
            os.mkfifo(root / "fifo")
            with self.assertRaises(backup.Refused):
                list(backup.safe_files(root))

    def test_cli_has_no_fixture_or_mount_bypass(self):
        result = subprocess.run(["python3", str(ROOT / "infra/backup/backup.py"), "--help"], capture_output=True)
        self.assertNotIn(b"--skip", result.stdout)
        self.assertNotIn(b"--fixture", result.stdout)


@contextmanager
def cluster(root, user):
    data = root / "data"
    socket = root / "socket"
    socket.mkdir(parents=True)
    log = root / "postgres.log"
    def command(*args):
        result = subprocess.run([str(PG / args[0]), *args[1:]], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        return result.stdout
    command("initdb", "-D", str(data), "--username", user, "--auth-local=trust", "--auth-host=reject", "--no-locale")
    command("pg_ctl", "-D", str(data), "-l", str(log), "-o", f"-h '' -k {socket} -p 15432", "-w", "start")
    config = {"bin": str(PG), "host": str(socket), "port": 15432, "user": user, "databases": ["d1fixture"]}
    try:
        yield config
    finally:
        command("pg_ctl", "-D", str(data), "-m", "fast", "-w", "stop")


@unittest.skipUnless((PG / "initdb").exists(), "native PostgreSQL 18 binaries required")
class RestoreTests(unittest.TestCase):
    def test_postgres_and_kernel_object_restore_retention_and_corruption(self):
        # Import the actual kernel store, not an imitation of its layout.
        from runtime.kernel.artifacts import ArtifactStore
        with tempfile.TemporaryDirectory(prefix="blaine-d1-") as tmp:
            root = Path(tmp)
            artifacts = root / "source-artifacts"
            store = ArtifactStore(artifacts)
            payload = b"ACME durable D1 synthetic object\x00\xff\n"
            ref = store.put("d1fixture", payload)
            output = root / "snapshots"
            output.mkdir()
            with cluster(root / "source", "d1source") as source, cluster(root / "restored", "d1restore") as restored:
                config = {"coverage": backup.COVERAGE, "postgres": source,
                          "artifact_roots": {"kernel": str(artifacts)}, "keep_last": 2}
                def sql(pgconfig, database, query):
                    return backup.run(backup.pg({"postgres": pgconfig}, "psql", database)
                                      + ["-X", "--set", "ON_ERROR_STOP=1", "-Atc", query], stdout=subprocess.PIPE).stdout.decode().strip()
                sql(source, "postgres", "CREATE DATABASE d1fixture")
                sql(source, "d1fixture", "CREATE TABLE proof (id integer PRIMARY KEY, value text NOT NULL); INSERT INTO proof VALUES (1, 'ACME durable D1 row'); CREATE EXTENSION vector; CREATE TABLE embedding (v vector(3)); INSERT INTO embedding VALUES ('[1,2,3]')")
                sql(source, "d1fixture", "CREATE TABLE d1_proof (id integer PRIMARY KEY, value text); INSERT INTO d1_proof VALUES (1, 'ACME physical SSD proof')")
                generation = backup.snapshot(config, output)
                snapshot = output / generation
                manifest = backup.verify(snapshot, str(PG))
                self.assertFalse(manifest["complete_durable_brain"])
                self.assertEqual(manifest["restore_test"], "not-performed")
                backup.run(backup.pg({"postgres": restored}, "psql", "postgres")
                           + ["-X", "--set", "ON_ERROR_STOP=1", "--file", str(snapshot / "postgres/globals.sql")], stdout=subprocess.DEVNULL)
                backup.run(backup.pg({"postgres": restored}, "pg_restore", "postgres")
                           + ["--create", "--exit-on-error", str(snapshot / "postgres/d1fixture.dump")], stdout=subprocess.DEVNULL)
                self.assertEqual(sql(restored, "d1fixture", "SELECT value FROM proof WHERE id=1"), "ACME durable D1 row")
                self.assertEqual(sql(restored, "d1fixture", "SELECT v FROM embedding"), "[1,2,3]")
                self.assertEqual(sql(restored, "d1fixture", "SELECT tableowner FROM pg_tables WHERE tablename='proof'"), "d1source")
                self.assertEqual(sql(restored, "postgres", "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='d1fixture'"), "d1source")
                restored_objects = root / "restored-artifacts"
                shutil.copytree(snapshot / "artifacts/kernel", restored_objects)
                self.assertEqual(ArtifactStore(restored_objects).read("d1fixture", ref), payload)
                restore_spec = importlib.util.spec_from_file_location("restore_generation", ROOT / "infra/backup/restore-generation.py")
                restore_module = importlib.util.module_from_spec(restore_spec)
                restore_spec.loader.exec_module(restore_module)
                drill = restore_module.restore(snapshot, "d1fixture")
                self.assertEqual(drill["result"], "PASS")
                self.assertTrue(drill["synthetic_row_verified"])
                self.assertEqual(drill["artifact_count"], 1)
                # Prove selected database dump did not overwrite the source.
                self.assertEqual(sql(source, "d1fixture", "SELECT count(*) FROM proof"), "1")
                for _ in range(2):
                    backup.snapshot(config, output)
                self.assertFalse(snapshot.exists())
                self.assertEqual(len(list(output.iterdir())), 2)
                # Corrupt a retained snapshot: verification and retention fail
                # before deleting any existing generation.
                retained = sorted(output.iterdir())
                (retained[0] / "postgres/globals.sql").write_text("corrupted")
                with self.assertRaises(backup.Refused):
                    backup.verify(retained[0], str(PG))
                with self.assertRaises(backup.Refused):
                    backup.prune(output, 1, str(PG))
                self.assertTrue(all(p.exists() for p in retained))

    def test_failed_dump_is_unpublished_and_does_not_prune(self):
        with tempfile.TemporaryDirectory(prefix="blaine-d1-") as tmp:
            root = Path(tmp)
            artifacts = root / "artifacts"
            artifacts.mkdir()
            output = root / "snapshots"
            output.mkdir()
            config = {"coverage": backup.COVERAGE, "keep_last": 1, "artifact_roots": {"kernel": str(artifacts)},
                      "postgres": {"bin": str(PG), "host": str(root), "port": 15432, "user": "absent", "databases": ["d1fixture"]}}
            with patch.object(backup, "source_capacity", return_value={}), self.assertRaises(backup.Refused):
                backup.snapshot(config, output)
            self.assertFalse(any(backup.GENERATION.fullmatch(p.name) for p in output.iterdir()))
            self.assertEqual(len(list(output.glob(".incomplete-*"))), 1)


if __name__ == "__main__":
    unittest.main()
