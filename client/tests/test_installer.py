"""Isolated installer contract tests: no real user config, IDE, or network."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "install-jetbrains-agent.sh"
installer = types.ModuleType("installer")
exec(compile(SCRIPT.read_text().split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0],
             str(SCRIPT), "exec"), installer.__dict__)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / "user with spaces"
        self.home.mkdir()
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        self.binary = self.home / ".local/bin/blaine"
        self.config = self.home / ".jetbrains/acp.json"
        self.metadata = {"client_version": "0.1.0-e0c-direct", "os": "linux",
                         "arch": "amd64", "protocol_version": 1, "build_commit": "a" * 40}
        self.payload()
        for context in (patch.object(installer.Path, "home", return_value=self.home),
                        patch.object(installer, "detect", return_value=("linux", "amd64", False)),
                        patch.object(installer.os, "geteuid", return_value=1000)):
            context.start()
            self.addCleanup(context.stop)

    def payload(self):
        data = ("#!/bin/sh\nprintf '%s\\n' '" + json.dumps(self.metadata) + "'\n").encode()
        asset = self.candidate / "blaine-linux-amd64"
        asset.write_bytes(data)
        (self.candidate / "checksums.txt").write_text(hashlib.sha256(data).hexdigest() + "  " + asset.name + "\n")

    def install(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            installer.main(["--candidate-dir", str(self.candidate), *args])
        return out.getvalue()

    def write_config(self, data):
        self.config.parent.mkdir(exist_ok=True)
        self.config.write_bytes(data)

    def test_install_merge_idempotence_and_bounded_backup(self):
        other = {"command": "/path with spaces/other", "args": ["--acp"], "env": {"EXISTING": "keep"}}
        doc = {"agent_servers": {"Other": other}, "default_mcp_settings": {"use_idea_mcp": True}, "extension": [1]}
        original = json.dumps(doc).encode()
        self.write_config(original)
        self.install()
        merged = json.loads(self.config.read_bytes())
        self.assertEqual(merged["agent_servers"].pop("Blaine"), {"command": str(self.binary), "args": ["acp"]})
        self.assertEqual(merged, doc)
        backup = self.config.with_name("acp.json.blaine-backup")
        self.assertEqual(backup.read_bytes(), original)
        times = (self.config.stat().st_mtime_ns, backup.stat().st_mtime_ns, self.binary.stat().st_mtime_ns)
        self.install()
        self.assertEqual(times, (self.config.stat().st_mtime_ns, backup.stat().st_mtime_ns, self.binary.stat().st_mtime_ns))
        self.assertEqual(self.binary.stat().st_mode & 0o777, 0o755)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len(list(self.config.parent.glob("*backup*"))), 1)

    def test_updates_prior_candidate_name_without_duplicate(self):
        self.write_config(b'{"agent_servers":{"Blaine E0.C candidate":{"command":"/old","args":[],"env":{"KEEP":"yes"}}}}')
        self.install()
        agents = json.loads(self.config.read_bytes())["agent_servers"]
        self.assertEqual(list(agents), ["Blaine E0.C candidate"])
        self.assertEqual(agents["Blaine E0.C candidate"]["env"], {"KEEP": "yes"})
        self.assertEqual(agents["Blaine E0.C candidate"]["command"], str(self.binary))

    def test_invalid_configuration_untouched_before_download_or_execution(self):
        for data in (b'{broken', b'[]', b'{"agent_servers":[]}',
                     b'{"agent_servers":{"Other":false}}', b'{"agent_servers":{},"agent_servers":{}}',
                     b'{"extension":NaN}', b'{"default_mcp_settings":[]}',
                     b'{"agent_servers":{"Blaine":{},"Blaine E0.C candidate":{}}}'):
            with self.subTest(data=data):
                self.write_config(data)
                with patch.object(installer, "verified_payload") as fetch:
                    with self.assertRaises(ValueError):
                        self.install()
                    fetch.assert_not_called()
                self.assertEqual(self.config.read_bytes(), data)
                self.assertFalse(self.binary.exists())

    def test_checksum_failure_never_executes_payload_or_modifies_config(self):
        sentinel = self.root / "executed"
        (self.candidate / "blaine-linux-amd64").write_text("#!/bin/sh\ntouch '" + str(sentinel) + "'\n")
        self.write_config(b'{"agent_servers":{}}')
        with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
            self.install()
        self.assertFalse(sentinel.exists())
        self.assertFalse(self.binary.exists())
        self.assertEqual(self.config.read_bytes(), b'{"agent_servers":{}}')

    def test_missing_and_duplicate_checksum_entries_rejected(self):
        manifest = self.candidate / "checksums.txt"
        original = manifest.read_text()
        for data in ("", original * 2, "invalid  blaine-linux-amd64\n"):
            manifest.write_text(data)
            with self.assertRaisesRegex(ValueError, "exactly one SHA-256"):
                self.install()
        self.assertFalse(self.binary.exists())

    def test_platform_metadata_mismatch(self):
        self.metadata["arch"] = "arm64"
        self.payload()
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.install()
        self.assertFalse(self.binary.exists())

    def test_check_is_read_only_and_reports_registration(self):
        before = list(self.home.rglob("*"))
        self.assertIn("Installed: absent", self.install("--check"))
        self.assertEqual(before, list(self.home.rglob("*")))
        self.install()
        before = {p: p.stat().st_mtime_ns for p in self.home.rglob("*")}
        self.assertIn("Expected executable/arguments: matches", self.install("--check"))
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in self.home.rglob("*")})

    def test_symlink_config_parent_binary_and_hardlink_rejected(self):
        real = self.root / "real.json"
        real.write_text('{}')
        self.config.parent.mkdir()
        self.config.symlink_to(real)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.install()
        self.config.unlink()
        os.link(real, self.config)
        with self.assertRaisesRegex(ValueError, "regular path"):
            self.install()
        self.config.unlink()
        self.config.parent.rmdir()
        self.config.parent.symlink_to(self.candidate, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            self.install()

    def test_config_changed_during_fetch_not_overwritten(self):
        real_fetch = installer.verified_payload
        def fetch(*args):
            result = real_fetch(*args)
            self.write_config(b'{"agent_servers":{"New":{"command":"new"}}}')
            return result
        with patch.object(installer, "verified_payload", side_effect=fetch):
            with self.assertRaisesRegex(ValueError, "changed during download"):
                self.install()
        self.assertIn(b'New', self.config.read_bytes())
        self.assertFalse(self.binary.exists())

    def test_official_release_urls_and_version_guard(self):
        self.metadata["client_version"] = installer.RELEASE[1:]
        self.payload()
        urls = []
        def download(url, target):
            urls.append(url)
            target.write_bytes((self.candidate / target.name).read_bytes())
        with patch.object(installer, "download", side_effect=download), contextlib.redirect_stdout(io.StringIO()):
            installer.main([])
        self.assertEqual(urls, [installer.REPOSITORY + "/releases/download/" + installer.RELEASE + "/" + n
                               for n in ("checksums.txt", "blaine-linux-amd64")])
        self.metadata["client_version"] = "0.1.0-e0c-direct"
        self.payload()
        self.install()
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaisesRegex(ValueError, "Refusing to replace"):
            installer.main([])


class PlatformTests(unittest.TestCase):
    def test_all_four_targets_and_unsupported_platforms(self):
        for system in ("Darwin", "Linux"):
            for machine, expected in (("arm64", "arm64"), ("aarch64", "arm64"), ("x86_64", "amd64")):
                with patch.object(installer.platform, "system", return_value=system), \
                     patch.object(installer.platform, "machine", return_value=machine), \
                     patch.object(installer.platform, "release", return_value="kernel"):
                    self.assertEqual(installer.detect(), (system.lower(), expected, False))
        with patch.object(installer.platform, "system", return_value="Windows"):
            with self.assertRaises(ValueError):
                installer.detect()

    def test_windows_ide_wsl_launch_uses_argument_array(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"WSL_DISTRO_NAME": "Ubuntu"}), \
                 patch.object(installer, "run", side_effect=[json.dumps({"home": "C:\\Users\\User Name",
                                   "launcher": "C:\\Windows\\System32\\wsl.exe"}), tmp]) as run:
                binary, config, entry = installer.targets(Path("/home/user name"), True)
                self.assertEqual(config, Path(tmp) / ".jetbrains/acp.json")
                self.assertEqual(entry["args"], ["--distribution", "Ubuntu", "--exec", str(binary), "acp"])
                self.assertEqual(run.call_args_list[1].args[0], ["wslpath", "-u", "C:\\Users\\User Name"])

    def test_shell_entrypoint_supports_pipe_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(["sh", "-s", "--", "--check"], input=SCRIPT.read_text(),
                                    text=True, capture_output=True, env={**os.environ, "HOME": tmp})
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Installed: absent", result.stdout)
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
