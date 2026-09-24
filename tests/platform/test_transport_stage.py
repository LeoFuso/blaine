"""Private edge staging fixtures; no real services, credentials or IDE state."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('transport_stage', ROOT / 'infra/services/transport-stage.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class Staging(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.home = self.root / 'home'
        self.home.mkdir(mode=0o700)
        for name, data in {'runtime/personal_acp.py': b'# fixture',
                           'infra/systemd/user/' + stage.UNIT: (ROOT / 'infra/systemd/user' / stage.UNIT).read_bytes()}.items():
            p = self.repo / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        def git(*args):
            return subprocess.check_output(['git', '-C', str(self.repo), *args], stderr=subprocess.DEVNULL)
        git('init', '-q')
        git('add', '.')
        git('-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', '-c', 'commit.gpgsign=false',
            'commit', '-qm', 'fixture')
        self.commit = git('rev-parse', 'HEAD').decode().strip()
        self.binary = self.root / 'binary'
        self.binary.write_bytes(b'\x7fELFfixture')
        self.key = self.root / 'fixture.key'
        self.key.write_bytes(b'x' * 32)
        self.key.chmod(0o600)
        readiness = self.root / 'readiness.json'
        readiness.write_text('{}')
        readiness.chmod(0o600)
        self.candidate = self.root / 'candidate.json'
        self.candidate.write_text(json.dumps({'listen': '100.64.0.1:7443', 'key_file': str(self.key),
            'python': '/fixture/python', 'repository': str(self.repo), 'readiness_file': str(readiness),
            'deployment_file': '/fixture/runtime.json', 'principal_id': 'fixture', 'allowed_nodes': ['fixture-node']}))
        self.candidate.chmod(0o600)

    def run_stage(self):
        return stage.stage(self.repo, self.binary, self.candidate, self.home, self.commit)

    def test_persistent_paths_pinned_snapshot_identity_and_idempotency(self):
        receipt = self.run_stage()
        base = self.home / '.local/share/blaine/transport'
        config = json.loads((self.home / '.config/blaine/services/transport.json').read_text())
        self.assertFalse(receipt['services_started_or_restarted'])
        self.assertEqual((base / 'hub.key').read_bytes(), self.key.read_bytes())
        self.assertEqual((base / 'hub.key').stat().st_mode & 0o777, 0o600)
        self.assertNotIn(str(self.repo), config['repository'])
        self.assertEqual(config['deployment_file'], '/fixture/runtime.json')
        self.assertEqual(config['allowed_nodes'], ['fixture-node'])
        self.assertEqual((Path(config['repository']) / 'runtime/personal_acp.py').read_bytes(), b'# fixture')
        before = {p: p.stat().st_mtime_ns for p in self.home.rglob('*') if p.is_file()}
        self.assertEqual(self.run_stage(), receipt)
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})

    def test_cannot_rotate_existing_pin_or_replace_same_commit_binary(self):
        self.run_stage()
        target = self.home / '.local/share/blaine/transport/bin/blaine-hub-transport'
        original = target.read_bytes()
        self.key.write_bytes(b'y' * 32)
        with self.assertRaisesRegex(ValueError, 'identity differs'):
            self.run_stage()
        self.key.write_bytes(b'x' * 32)
        self.binary.write_bytes(b'\x7fELFchanged')
        with self.assertRaisesRegex(ValueError, 'release content differs'):
            self.run_stage()
        self.assertEqual(target.read_bytes(), original)

    def test_changed_policy_fails_before_replacing_deployment(self):
        self.run_stage()
        target = self.home / '.config/blaine/services/transport.json'
        before = target.read_bytes()
        cfg = json.loads(self.candidate.read_text())
        cfg['allowed_nodes'].append('not-authorized')
        self.candidate.write_text(json.dumps(cfg))
        with self.assertRaisesRegex(ValueError, 'policy drift'):
            self.run_stage()
        self.assertEqual(target.read_bytes(), before)

    def test_explicit_registry_migration_removes_manual_device_admission(self):
        self.run_stage()
        stage.stage(self.repo, self.binary, self.candidate, self.home, self.commit,
                    'host=/fixture/socket dbname=blaine user=fixture')
        target = self.home / '.config/blaine/services/transport.json'
        cfg = json.loads(target.read_text())
        self.assertEqual(cfg['admission'], 'tailscale-policy')
        self.assertNotIn('allowed_nodes', cfg)
        self.assertNotIn('principal_id', cfg)
        self.assertEqual(cfg['registry_dsn'], 'host=/fixture/socket dbname=blaine user=fixture')
        # Once migrated, use the canonical configuration as source. Idempotent.
        self.candidate.write_text(json.dumps(cfg))
        before = target.read_bytes()
        self.run_stage()
        self.assertEqual(target.read_bytes(), before)

    def test_dirty_source_and_incorrect_revision_fail(self):
        with self.assertRaisesRegex(ValueError, 'commit mismatch'):
            stage.stage(self.repo, self.binary, self.candidate, self.home, 'a' * 40)
        (self.repo / 'runtime/personal_acp.py').write_text('# changed')
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_stage()
        self.assertFalse((self.home / '.local/share/blaine/transport').exists())

    def test_redirected_key_and_target_fail(self):
        saved = self.root / 'saved.key'
        self.key.rename(saved)
        self.key.symlink_to(saved)
        with self.assertRaisesRegex(ValueError, 'redirected'):
            self.run_stage()
        self.key.unlink()
        saved.rename(self.key)
        (self.home / '.local').symlink_to(self.root)
        with self.assertRaisesRegex(ValueError, 'redirected'):
            self.run_stage()

    def test_nonprivate_or_hardlinked_key_fails(self):
        self.key.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'private'):
            self.run_stage()
        self.key.chmod(0o600)
        os.link(self.key, self.root / 'alias.key')
        with self.assertRaisesRegex(ValueError, 'ownership/type'):
            self.run_stage()


if __name__ == '__main__':
    unittest.main()
