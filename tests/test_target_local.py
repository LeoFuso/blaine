"""LocalWorktreeProvider honours the E2.0 TargetProvider obligations on a real directory."""
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path

from runtime.kernel import effects
from runtime.kernel.artifacts import ArtifactStore
from runtime.kernel.contracts import message
from runtime.kernel.target_local import LocalWorktreeProvider, summarize

WS = 'wsp-local'


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.root = base / 'repo'
        (self.root / 'tests').mkdir(parents=True)
        (self.root / 'tests' / 'existing.py').write_text('x = 1\n')
        self.provider = LocalWorktreeProvider({WS: self.root}, base / 'data' / 'target.sqlite')
        self.store = ArtifactStore(base / 'artifacts')

    def tearDown(self):
        self.tmp.cleanup()

    def write_request(self, operation, path, content, precondition=None):
        return message('EffectRequest', {'task_id': 'task-a', 'operation_id': operation,
            'operation_class': effects.WRITE, 'operation': 'write_file', 'workspace_id': WS,
            'authority_ref': 'artifact://task-a/sha256:' + '0' * 64, 'contract_revision': 0, 'path': path,
            'precondition': precondition or {'absent': True}, 'precondition_evidence': None,
            'content_ref': 'artifact://task-a/sha256:' + sha(content), 'content_sha256': sha(content),
            'content_bytes': len(content.encode())})

    def exec_request(self, operation, code, timeout=30):
        profile = {'id': 'probe', 'executable': sys.executable, 'args': ['-c', code], 'allowed_args': [],
                   'timeout_seconds': timeout, 'poll_seconds': 0.1, 'output_cap_bytes': 4096,
                   'environment': 'minimal'}
        return message('EffectRequest', {'task_id': 'task-a', 'operation_id': operation,
            'operation_class': effects.EXEC, 'operation': 'run_profile', 'workspace_id': WS,
            'authority_ref': 'artifact://task-a/sha256:' + '0' * 64, 'contract_revision': 0,
            'profile': {'id': 'probe', 'digest': effects.profile_digest(profile)},
            'command': {'executable': sys.executable, 'args': ['-c', code]}, 'timeout_seconds': timeout,
            'poll_seconds': 0.1, 'output_cap_bytes': 4096, 'environment': 'minimal'})

    def settle(self, request, attempts=100):
        for _ in range(attempts):
            polled = effects.poll(self.provider, request, self.store)
            receipt = polled['payload'].get('receipt')
            if receipt and receipt['payload']['state'] != 'running':
                return receipt
            time.sleep(0.1)
        self.fail('process did not finish')


class WriteTest(Base):
    def test_new_file_is_written_by_compare_and_swap_and_is_idempotent(self):
        request = self.write_request('task-a/2', 'tests/test_new.py', 'def test_x():\n    assert True\n')
        first = effects.attempt(self.provider, request, {'content': 'def test_x():\n    assert True\n'}, self.store)
        self.assertEqual(first['payload']['kind'], 'receipt')
        self.assertEqual(first['payload']['receipt']['payload']['state'], 'applied')
        self.assertEqual((self.root / 'tests/test_new.py').read_text(), 'def test_x():\n    assert True\n')
        again = effects.attempt(self.provider, request, {'content': 'def test_x():\n    assert True\n'}, self.store)
        self.assertEqual(again['payload']['delivery'], 'recovered')
        other = self.write_request('task-a/2', 'tests/test_new.py', 'different\n')
        with self.assertRaises(ValueError):
            self.provider.dispatch(other, {'content': 'different\n'})

    def test_stale_precondition_is_a_conflict_and_nothing_is_written(self):
        request = self.write_request('task-a/3', 'tests/existing.py', 'x = 2\n', {'sha256': sha('x = 0\n')})
        result = effects.attempt(self.provider, request, {'content': 'x = 2\n'}, self.store)
        self.assertEqual(result['payload']['receipt']['payload']['state'], 'conflict')
        self.assertEqual((self.root / 'tests/existing.py').read_text(), 'x = 1\n')

    def test_existing_file_rewrite_against_its_digest(self):
        request = self.write_request('task-a/4', 'tests/existing.py', 'x = 2\n', {'sha256': sha('x = 1\n')})
        result = effects.attempt(self.provider, request, {'content': 'x = 2\n'}, self.store)
        self.assertEqual(result['payload']['receipt']['payload']['state'], 'applied')
        self.assertEqual(self.provider.observe(WS, 'tests/existing.py'), {'exists': True, 'sha256': sha('x = 2\n')})

    def test_crash_between_replace_and_receipt_is_attributable(self):
        request = self.write_request('task-a/5', 'tests/crash.py', 'y = 1\n')
        digest = effects.request_digest(request)
        with sqlite3.connect(self.provider.database) as db:
            db.execute('INSERT INTO receipts (operation_id, request_digest, phase, request) VALUES (?, ?, ?, ?)',
                       ('task-a/5', digest, 'writing', json.dumps(request)))
        # The replace happened; the receipt was never recorded.
        (self.root / 'tests/crash.py').write_text('y = 1\n')
        found = self.provider.query('task-a/5', digest)
        self.assertTrue(found['found'])
        self.assertEqual(found['receipt']['payload']['state'], 'applied')
        reconciled = effects.reconcile(self.provider, request, self.store)
        self.assertEqual(reconciled['payload']['state'], effects.APPLIED)

    def test_crash_before_replace_is_authoritatively_not_applied(self):
        request = self.write_request('task-a/6', 'tests/never.py', 'z = 1\n')
        digest = effects.request_digest(request)
        with sqlite3.connect(self.provider.database) as db:
            db.execute('INSERT INTO receipts (operation_id, request_digest, phase, request) VALUES (?, ?, ?, ?)',
                       ('task-a/6', digest, 'writing', json.dumps(request)))
        self.assertEqual(self.provider.query('task-a/6', digest), {'found': False, 'authoritative': True})
        self.assertEqual(effects.reconcile(self.provider, request, self.store)['payload']['state'], effects.NOT_APPLIED)

    def test_paths_are_confined(self):
        outside = Path(self.tmp.name) / 'outside.py'
        outside.write_text('secret\n')
        os.symlink(outside, self.root / 'tests' / 'link.py')
        (self.root / '.git').mkdir()
        for path in ('../outside.py', '/etc/passwd', 'tests/link.py', '.git/config', 'tests/../../outside.py'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.provider.read(WS, path)
        with self.assertRaises(ValueError):
            self.provider.read('other-workspace', 'tests/existing.py')
        self.assertEqual(self.provider.read(WS, 'tests/existing.py'), {'exists': True, 'content': 'x = 1\n'})
        self.assertEqual(self.provider.read(WS, 'tests/missing.py'), {'exists': False, 'content': ''})


class ExecTest(Base):
    def test_profile_runs_without_shell_and_reports_exit_and_summary(self):
        request = self.exec_request('task-a/7', "import os; print('cwd', os.getcwd()); print('3 passed in 0.01s')")
        started = effects.attempt(self.provider, request, {}, self.store)
        self.assertIn(started['payload']['receipt']['payload']['state'], ('running', 'completed'))
        receipt = self.settle(request)
        body = receipt['payload']['exec']
        self.assertEqual(receipt['payload']['state'], 'completed')
        self.assertEqual(body['exit_code'], 0)
        self.assertEqual(body['cleanup'], 'confirmed')
        self.assertEqual(body['result'], {'passed': 3})
        output = self.store.read('task-a', body['output_ref']).decode()
        self.assertIn(str(self.root), output)

    def test_failing_process_is_completed_with_its_exit_code(self):
        request = self.exec_request('task-a/8', "import sys; print('1 failed, 2 passed'); sys.exit(1)")
        effects.attempt(self.provider, request, {}, self.store)
        receipt = self.settle(request)
        self.assertEqual(receipt['payload']['exec']['exit_code'], 1)
        self.assertEqual(receipt['payload']['exec']['result'], {'failed': 1, 'passed': 2})

    def test_cancel_kills_the_process_group(self):
        request = self.exec_request('task-a/9', 'import time; time.sleep(30)')
        effects.attempt(self.provider, request, {}, self.store)
        stopped = effects.cancel(self.provider, request, self.store, 'timeout')
        self.assertEqual(stopped['payload']['kind'], 'receipt')
        self.assertEqual(stopped['payload']['receipt']['payload']['state'], 'timed_out')
        self.assertEqual(stopped['payload']['receipt']['payload']['exec']['cleanup'], 'confirmed')

    def test_unknown_operation_is_authoritatively_absent(self):
        self.assertEqual(self.provider.query('task-a/none', 'sha256:' + '1' * 64),
                         {'found': False, 'authoritative': True})

    def test_summary_is_small_and_flat(self):
        self.assertEqual(summarize('...\n5 passed, 1 skipped in 0.2s\n'), {'passed': 5, 'skipped': 1})
        self.assertEqual(summarize('run x\nresult: PASS\n'), {'verification': 'PASS'})
        self.assertEqual(summarize('{\n  "reason": "",\n  "result": "FAIL",\n  "x": 1\n}\n'), {'verification': 'FAIL'})


if __name__ == '__main__':
    unittest.main()
