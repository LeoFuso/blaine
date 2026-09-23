"""Shell bootstrap fixtures. Python is a CI test dependency, never an installer dependency."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'install-jetbrains-agent.sh'


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'home with spaces'
        self.home.mkdir()
        self.commands = self.root / 'commands'
        self.commands.mkdir()
        # Deliberately no python/python3 in the workstation PATH.
        for name in ('id', 'mktemp', 'rm', 'cp', 'chmod', 'mv', 'mkdir', 'sha256sum', 'shasum'):
            actual = shutil.which(name)
            if actual:
                (self.commands / name).symlink_to(actual)
        self.script('uname', 'case "$1" in -s) echo "$TEST_OS";; -m) echo "$TEST_ARCH";; esac')
        self.script('curl', '''[ "${TEST_FAIL_DOWNLOAD:-}" != yes ] || exit 22
while [ "$#" -gt 0 ]; do
 case "$1" in https:*) url=$1;; -o) shift; dest=$1;; esac
 shift
done
printf '%s\\n' "$url" >> "$TEST_URLS"
case "$url" in */checksums.txt) cp "$TEST_MANIFEST" "$dest";; *) cp "$TEST_PAYLOAD" "$dest";; esac''')
        self.payload = self.root / 'payload'
        self.payload.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$TEST_EXECUTED"
case "$1" in
 version) printf 'blaine 0.1.0-alpha.2 protocol=1 commit=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa go=go1.27.1 platform=%s/%s\\n' "$TEST_GOOS" "$TEST_GOARCH";;
 integration) [ "${TEST_BAD_CONFIG:-}" != yes ] || exit 2;;
 *) exit 99;;
esac
''')
        self.manifest = self.root / 'checksums.txt'
        self.executed = self.root / 'executed'
        self.env = {**os.environ, 'HOME': str(self.home), 'PATH': str(self.commands),
                    'TEST_OS': 'Linux', 'TEST_ARCH': 'x86_64', 'TEST_GOOS': 'linux', 'TEST_GOARCH': 'amd64',
                    'TEST_PAYLOAD': str(self.payload), 'TEST_MANIFEST': str(self.manifest),
                    'TEST_URLS': str(self.root / 'urls'), 'TEST_EXECUTED': str(self.executed)}
        self.checksum()

    def script(self, name, body):
        p = self.commands / name
        p.write_text('#!/bin/sh\n' + body + '\n')
        p.chmod(0o755)

    def checksum(self):
        digest = hashlib.sha256(self.payload.read_bytes()).hexdigest()
        self.manifest.write_text(digest + '  blaine-' + self.env['TEST_GOOS'] + '-' + self.env['TEST_GOARCH'] + '\n')

    def invoke(self, *args):
        return subprocess.run(['/bin/sh', '-s', '--', *args], input=SCRIPT.read_text(),
                              env=self.env, text=True, capture_output=True)

    def test_four_target_selection_install_and_integration(self):
        for system, goos in (('Darwin', 'darwin'), ('Linux', 'linux')):
            for machine, arch in (('arm64', 'arm64'), ('x86_64', 'amd64')):
                self.env.update(TEST_OS=system, TEST_GOOS=goos, TEST_ARCH=machine, TEST_GOARCH=arch)
                self.checksum()
                result = self.invoke()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('checksum: verified', result.stdout)
                self.assertIn('integration jetbrains install', self.executed.read_text())
                self.assertIn('/v0.1.0-alpha.2/blaine-' + goos + '-' + arch, (self.root / 'urls').read_text())
                self.assertTrue((self.home / '.local/bin/blaine').is_file())

    def test_corrupt_download_never_executes_or_replaces(self):
        target = self.home / '.local/bin/blaine'
        target.parent.mkdir(parents=True)
        target.write_text('existing version')
        self.payload.write_text('unverified executable')
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.executed.exists())
        self.assertEqual(target.read_text(), 'existing version')

    def test_missing_duplicate_invalid_checksum(self):
        valid = self.manifest.read_text()
        for data in ('', valid * 2, 'invalid  blaine-linux-amd64\n'):
            self.manifest.write_text(data)
            self.assertNotEqual(self.invoke().returncode, 0)
            self.assertFalse(self.executed.exists())

    def test_failed_download(self):
        self.env['TEST_FAIL_DOWNLOAD'] = 'yes'
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse(self.executed.exists())
        self.assertFalse((self.home / '.local').exists())

    def test_check_and_repeat_existing_version(self):
        self.assertEqual(self.invoke().returncode, 0)
        self.assertEqual(self.invoke().returncode, 0)
        urls = (self.root / 'urls').read_bytes()
        result = self.invoke('--check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / 'urls').read_bytes(), urls)
        self.assertIn('integration jetbrains check', self.executed.read_text())

    def test_config_preflight_fails_before_binary_install(self):
        self.env['TEST_BAD_CONFIG'] = 'yes'
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertFalse((self.home / '.local/bin/blaine').exists())
        self.assertNotIn('integration jetbrains install', self.executed.read_text())

    def test_unsupported_and_removed_candidate_argument(self):
        self.env['TEST_OS'] = 'Windows'
        self.assertNotEqual(self.invoke().returncode, 0)
        self.assertNotEqual(self.invoke('--candidate-dir').returncode, 0)
        self.assertFalse(self.executed.exists())

    def test_macos_sha_tool(self):
        (self.commands / 'sha256sum').unlink()
        if not (self.commands / 'shasum').exists():
            self.skipTest('shasum not present on build host')
        self.assertEqual(self.invoke().returncode, 0)


if __name__ == '__main__':
    unittest.main()
