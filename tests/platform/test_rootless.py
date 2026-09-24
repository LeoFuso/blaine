"""Rootless migration secret handoff boundaries, using only synthetic fixtures."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'infra/rootless' / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


bootstrap = module('bootstrap_secrets', 'bootstrap-secrets.py')
preflight = module('rootless_preflight', 'preflight.py')
candidate = module('rootless_candidate', 'prepare-candidate.py')
copy_state = module('rootless_copy', 'copy-stopped-state.py')


class RootlessSecretTests(unittest.TestCase):
    def fingerprint(self, root, uid, gid):
        # Fixtures may be tmpfs; production calls enforce the host root device.
        return copy_state.fingerprint(root, uid, gid, device=root.stat().st_dev)

    def values(self):
        return {name: 'synthetic-test-value\n' for name in bootstrap.NAMES}

    def test_private_copy_is_idempotent_without_rewriting_existing_secrets(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'secrets'
            bootstrap.materialize(p, self.values())
            before = {f.name: f.stat().st_mtime_ns for f in p.iterdir()}
            bootstrap.materialize(p, self.values())
            self.assertEqual(before, {f.name: f.stat().st_mtime_ns for f in p.iterdir()})
            self.assertEqual(p.stat().st_mode & 0o777, 0o700)
            for f in p.iterdir():
                self.assertEqual(f.stat().st_uid, os.getuid())
                self.assertEqual(f.stat().st_mode & 0o777, 0o400 if f.name == 'object-storage.json' else 0o600)

    def test_conflict_never_overwrites_existing_value(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'secrets'
            bootstrap.materialize(p, self.values())
            changed = self.values()
            changed['langfuse.env'] = 'different-synthetic-value'
            with self.assertRaises(RuntimeError):
                bootstrap.materialize(p, changed)
            self.assertEqual((p / 'langfuse.env').read_text(), self.values()['langfuse.env'])

    def test_symlink_file_and_ancestor_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p / 'target').mkdir(mode=0o700)
            (p / 'link').symlink_to(p / 'target')
            with self.assertRaises(RuntimeError):
                bootstrap.materialize(p / 'link' / 'secrets', self.values())
            secret = p / 'target' / 'langfuse.env'
            secret.symlink_to(p / 'outside')
            with self.assertRaises(RuntimeError):
                bootstrap.materialize(p / 'target', self.values())
            self.assertFalse((p / 'outside').exists())

    def test_broad_permissions_are_rejected_instead_of_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'secrets'
            bootstrap.materialize(p, self.values())
            (p / 'langfuse.env').chmod(0o640)
            with self.assertRaises(RuntimeError):
                bootstrap.materialize(p, self.values())
            with self.assertRaises(RuntimeError):
                preflight.private(p / 'langfuse.env')

    def test_rootful_context_named_rootless_is_rejected(self):
        with patch.object(os, 'getuid', return_value=1000), patch.object(preflight.subprocess, 'check_output', return_value='unix:///var/run/docker.sock'):
            with self.assertRaises(RuntimeError):
                preflight.daemon()

    def test_expected_socket_without_rootless_security_is_rejected(self):
        with patch.object(os, 'getuid', return_value=1000), patch.object(preflight.subprocess, 'check_output', side_effect=['unix:///run/user/1000/docker.sock', '["name=seccomp"]']):
            with self.assertRaises(RuntimeError):
                preflight.daemon()

    def test_candidate_dependencies_are_isolated_without_rotating_identity(self):
        source = {'DATABASE_URL': 'postgresql://synthetic:fixture@127.0.0.1:5432/blaine_langfuse',
                  'SALT': 'synthetic-salt', 'ENCRYPTION_KEY': 'synthetic-key',
                  'REDIS_CONNECTION_STRING': 'redis://127.0.0.1:6379/15',
                  'CLICKHOUSE_URL': 'http://127.0.0.1:8123'}
        result = candidate.candidate_environment(source)
        self.assertEqual(result['SALT'], source['SALT'])
        self.assertEqual(result['ENCRYPTION_KEY'], source['ENCRYPTION_KEY'])
        self.assertIn('/blaine_rootless_candidate_20260921', result['DATABASE_URL'])
        self.assertIn(':16379/', result['REDIS_CONNECTION_STRING'])
        self.assertIn(':18123', result['CLICKHOUSE_URL'])
        self.assertEqual(result['LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT'], 'http://127.0.0.1:18333')
        self.assertEqual(result['LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT'], 'http://127.0.0.1:18333')
        self.assertIn('/blaine_langfuse', source['DATABASE_URL'])

    def test_offline_fingerprint_covers_bytes_and_preserves_relative_symlinks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'data').write_text('synthetic-original')
            (root / 'link').symlink_to('data')
            before = self.fingerprint(root, os.getuid(), os.getgid())
            self.assertEqual(before['entries'], 3)
            self.assertEqual(os.readlink(root / 'link'), 'data')
            (root / 'data').write_text('synthetic-changed')
            after = self.fingerprint(root, os.getuid(), os.getgid())
            self.assertNotEqual(before['sha256'], after['sha256'])

    def test_offline_copy_refuses_external_links_and_unexpected_owners(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(RuntimeError):
                self.fingerprint(root, os.getuid() + 1, os.getgid())
            (root / 'outside').symlink_to('/etc/passwd')
            with self.assertRaises(RuntimeError):
                self.fingerprint(root, os.getuid(), os.getgid())

    def test_offline_copy_refuses_special_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            os.mkfifo(root / 'pipe', 0o600)
            with self.assertRaises(RuntimeError):
                self.fingerprint(root, os.getuid(), os.getgid())

    def test_offline_copy_refuses_unexpected_filesystem(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(RuntimeError):
                copy_state.fingerprint(root, os.getuid(), os.getgid(), device=root.stat().st_dev + 1)


if __name__ == '__main__':
    unittest.main()
