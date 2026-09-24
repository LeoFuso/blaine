"""tests.py -- deterministic tests for the local verification scheduler.

Covers the required cases: suite discovery (additive), PASS/FAIL/BLOCKED
propagation, verify-don't-provision, FIFO order, single active host run,
terminal release, bounded interruption, worktree identity, named-suite-only,
and report consistency.

Failure cases use fake/subprocess fixtures so they never require breaking the
actual developer host.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verification import report as report_mod
from verification import scheduler as sched_mod
from verification import worktree as worktree_mod
from verification.scheduler import RunState, Scheduler, SubmitError
from verification.suite import (ProbeResult, ProbeStatus, Result, Suite, Step,
                                SuiteExecutor, VerificationClass, discover_suites,
                                load_suite)
from verification.worktree import WorktreeError, WorktreeIdentity


class RecordingExecutor:
    """Fake executor: scripted exit codes, records every run and its env."""

    def __init__(self, exit_code=0, env=None):
        self.exit_code = exit_code
        self.env = env or {}
        self.calls = []

    def run(self, step, worktree, env):
        from verification.suite import StepReport
        self.calls.append({'name': step.name, 'worktree': str(worktree), 'env': dict(env)})
        return StepReport(step.name, list(step.command), self.exit_code, 'ok\n', '', 0.01, False, step.env)


def make_suite(name='test-suite', verification_class=VerificationClass.HERMETIC,
               steps=None, resources=(), probes=()):
    return Suite(name=name, verification_class=verification_class, description='t',
                 steps=steps or [Step('s', ['true'])], resources=resources,
                 prereq_probes=probes)


def identity(root='/tmp/fake-worktree', branch='main', commit='a' * 40, dirty=False):
    return WorktreeIdentity(root=Path(root), branch=branch, commit=commit, dirty=dirty, dirty_summary='')


def ok_probe():
    return {p: ProbeResult(ProbeStatus.AVAILABLE, 'ok') for p in ()}


def missing_probe(name='restate'):
    return {name: ProbeResult(ProbeStatus.UNAVAILABLE, 'not found')}


class DiscoveryTest(unittest.TestCase):
    def test_discovery_is_additive_not_central_registry(self):
        # The real suites are discovered from files in verification/suites.
        suites = discover_suites()
        self.assertIn('completion-contract', suites)
        self.assertIn('completion-contract-native', suites)
        self.assertIn('sample-hermetic', suites)
        # A new suite is discovered by dropping a module in; nothing central edited.
        module = Path('verification/suites/_additive_probe_tmp.py')
        self.assertFalse(module.exists())  # no test pollution left behind

    def test_a_new_suite_file_is_discovered_without_editing_a_registry(self):
        import verification.suites as package
        directory = Path(package.__path__[0])
        module = directory / 'zz_tmp_discovered.py'
        module.write_text(
            'from verification.suite import Suite, Step, VerificationClass\n'
            'SUITE = Suite(name="zz-tmp-discovered", verification_class=VerificationClass.HERMETIC,\n'
            '              description="t", steps=[Step("s", ["true"])])\n')
        try:
            with patch('verification.suite.SUITES_DIR', directory):
                suites = discover_suites()
            self.assertIn('zz-tmp-discovered', suites)
            self.assertEqual(suites['zz-tmp-discovered'].verification_class, VerificationClass.HERMETIC)
        finally:
            module.unlink(missing_ok=True)
            sys.modules.pop('verification.suites.zz_tmp_discovered', None)

    def test_unknown_suite_is_rejected(self):
        from verification.suite import SuiteError
        with self.assertRaises(SuiteError):
            load_suite('no-such-suite')
        with self.assertRaises(SuiteError):
            load_suite('BAD NAME!')


class ResultPropagationTest(unittest.TestCase):
    def test_pass_propagation(self):
        sched = Scheduler(executor=SuiteExecutor(RecordingExecutor(0)), preflight=lambda s, e: {})
        run_id = sched.submit('completion-contract', identity())
        self.assertEqual(sched.record(run_id).result, Result.PASS)
        self.assertEqual(sched.record(run_id).state, RunState.PASS)

    def test_fail_propagation(self):
        sched = Scheduler(executor=SuiteExecutor(RecordingExecutor(2)), preflight=lambda s, e: {})
        run_id = sched.submit('completion-contract', identity())
        self.assertEqual(sched.record(run_id).result, Result.FAIL)
        self.assertEqual(sched.record(run_id).state, RunState.FAIL)
        self.assertIn('exit=2', sched.record(run_id).reason)

    def test_blocked_prerequisite_does_not_run_steps(self):
        executor = RecordingExecutor(0)
        sched = Scheduler(executor=SuiteExecutor(executor),
                          preflight=lambda s, e: missing_probe())
        run_id = sched.submit('completion-contract-native', identity())
        self.assertEqual(sched.queued(), [run_id])
        admitted = sched.tick()
        self.assertEqual(admitted, run_id)
        record = sched.record(run_id)
        self.assertEqual(record.result, Result.BLOCKED)
        self.assertEqual(record.state, RunState.BLOCKED)
        self.assertEqual(executor.calls, [], 'steps must not execute when blocked')
        self.assertEqual(sched.active_run_id(), None, 'blocked run releases the slot')


class VerifyDontProvisionTest(unittest.TestCase):
    def test_missing_prerequisite_does_not_trigger_install_or_configuration(self):
        executor = RecordingExecutor(0)
        env = {}
        sched = Scheduler(executor=SuiteExecutor(executor),
                          preflight=lambda s, e: missing_probe('restate'))
        run_id = sched.submit('completion-contract-native', identity())
        sched.tick()
        self.assertEqual(sched.record(run_id).result, Result.BLOCKED)
        # The probe only observed; nothing was installed/configured and no step ran.
        self.assertEqual(executor.calls, [])
        # Re-probing still reports UNAVAILABLE (the tool is still genuinely absent).
        from verification.probes import probe_restate
        with tempfile.TemporaryDirectory() as d:
            result = probe_restate(Path(d), {'BLAINE_RESTATE_SERVER': str(Path(d) / 'no-such')})
            self.assertEqual(result.status, ProbeStatus.UNAVAILABLE)

    def test_probe_never_raises_into_a_pass(self):
        from verification.suite import probe
        result = probe('no-such-probe-name', Path('.'), {})
        self.assertEqual(result.status, ProbeStatus.MALFORMED)
        self.assertFalse(result.available)


class FifoOrderTest(unittest.TestCase):
    def test_host_runs_execute_in_submission_order(self):
        sched = Scheduler(executor=SuiteExecutor(RecordingExecutor(0)), preflight=lambda s, e: {})
        ids = [sched.submit('completion-contract-native', identity()) for _ in range(3)]
        self.assertEqual(sched.queued(), ids, 'FIFO: queue preserves submission order')
        # Only the head is admitted; the rest stay queued.
        self.assertEqual(sched.tick(), ids[0])
        self.assertEqual(sched.queued(), ids[1:])
        sched.run(ids[0])
        self.assertEqual(sched.tick(), ids[1])
        self.assertEqual(sched.queued(), [ids[2]])
        sched.run(ids[1])
        self.assertEqual(sched.tick(), ids[2])
        sched.run(ids[2])
        self.assertEqual(sched.queued(), [])


class SingleActiveHostRunTest(unittest.TestCase):
    def test_only_one_host_run_is_active_at_a_time(self):
        sched = Scheduler(executor=SuiteExecutor(RecordingExecutor(0)), preflight=lambda s, e: {})
        a = sched.submit('completion-contract-native', identity())
        b = sched.submit('completion-contract-native', identity())
        self.assertIsNone(sched.active_run_id())
        first = sched.tick()
        self.assertEqual(first, a)
        self.assertEqual(sched.active_run_id(), a)
        # While A is active, B cannot be admitted.
        self.assertIsNone(sched.tick())
        self.assertEqual(sched.active_run_id(), a)
        self.assertEqual(sched.queued(), [b])
        sched.run(a)
        # Slot released: B can now be admitted.
        self.assertEqual(sched.tick(), b)
        self.assertEqual(sched.active_run_id(), b)
        sched.run(b)


class TerminalReleaseTest(unittest.TestCase):
    def test_pass_fail_and_blocked_all_release_the_slot(self):
        for outcome, setup in (
                (Result.PASS, lambda: RecordingExecutor(0)),
                (Result.FAIL, lambda: RecordingExecutor(1)),
                (Result.BLOCKED, None)):
            with self.subTest(outcome=outcome):
                if outcome is Result.BLOCKED:
                    sched = Scheduler(executor=SuiteExecutor(RecordingExecutor(0)),
                                      preflight=lambda s, e: missing_probe())
                else:
                    sched = Scheduler(executor=SuiteExecutor(setup()), preflight=lambda s, e: {})
                run_id = sched.submit('completion-contract-native', identity())
                sched.tick()
                if outcome is not Result.BLOCKED:
                    sched.run(run_id)
                self.assertEqual(sched.record(run_id).result, outcome)
                self.assertEqual(sched.active_run_id(), None, 'terminal run must release the slot')
                self.assertEqual(sched.queued(), [])


class InterruptionTest(unittest.TestCase):
    def test_interrupted_run_does_not_starve_later_queued_work(self):
        sched = Scheduler(executor=SuiteExecutor(RecordingExecutor(0)), preflight=lambda s, e: {})
        a = sched.submit('completion-contract-native', identity())
        b = sched.submit('completion-contract-native', identity())
        sched.tick()
        self.assertEqual(sched.active_run_id(), a)
        sched.interrupt(a, 'bounded timeout')
        self.assertEqual(sched.record(a).result, Result.BLOCKED)
        self.assertEqual(sched.active_run_id(), None, 'interrupt releases the slot')
        self.assertEqual(sched.tick(), b, 'later queued work proceeds after interruption')
        sched.run(b)
        self.assertEqual(sched.record(b).result, Result.PASS)


class WorktreeIdentityTest(unittest.TestCase):
    def test_reported_identity_matches_the_tested_checkout(self):
        real = worktree_mod.resolve(str(ROOT))
        sched = Scheduler(executor=SuiteExecutor(RecordingExecutor(0)), preflight=lambda s, e: {})
        run_id = sched.submit('completion-contract', real)
        record = sched.record(run_id)
        self.assertEqual(record.worktree.root, real.root)
        self.assertEqual(record.worktree.commit, real.commit)
        self.assertEqual(record.worktree.branch, real.branch)
        self.assertEqual(record.worktree.dirty, real.dirty)

    def test_report_carries_worktree_and_commit(self):
        real = worktree_mod.resolve(str(ROOT))
        sched = Scheduler(executor=SuiteExecutor(RecordingExecutor(0)), preflight=lambda s, e: {})
        run_id = sched.submit('completion-contract', real)
        rep = report_mod.run_report(sched.record(run_id))
        self.assertEqual(rep['worktree']['commit'], real.commit)
        self.assertEqual(rep['worktree']['root'], str(real.root))
        self.assertEqual(rep['worktree']['dirty'], real.dirty)

    def test_non_worktree_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(WorktreeError):
                worktree_mod.resolve(d)
        with self.assertRaises(SubmitError):
            Scheduler().submit('completion-contract', '/nonexistent/path/xyz')


class NamedSuiteOnlyTest(unittest.TestCase):
    def test_arbitrary_command_submission_is_rejected(self):
        sched = Scheduler()
        with self.assertRaises(SubmitError):
            sched.submit_command('rm -rf /')

    def test_unknown_suite_name_is_rejected(self):
        sched = Scheduler()
        with self.assertRaises(SubmitError):
            sched.submit('arbitrary-shell', identity())

    def test_no_command_parameter_in_submit_signature(self):
        import inspect
        signature = inspect.signature(Scheduler.submit)
        self.assertNotIn('command', signature.parameters)


class ReportConsistencyTest(unittest.TestCase):
    def test_report_agrees_with_scheduler_state(self):
        for outcome, executor in ((Result.PASS, RecordingExecutor(0)),
                                  (Result.FAIL, RecordingExecutor(3))):
            with self.subTest(outcome=outcome):
                sched = Scheduler(executor=SuiteExecutor(executor), preflight=lambda s, e: {})
                run_id = sched.submit('completion-contract', identity(commit='b' * 40, branch='feat/x'))
                rep = report_mod.run_report(sched.record(run_id))
                record = sched.record(run_id)
                self.assertEqual(rep['result'], record.result.value)
                self.assertEqual(rep['state'], record.state.value)
                self.assertEqual(rep['run_id'], run_id)
                self.assertEqual(rep['suite'], record.suite.name)
                self.assertEqual(rep['worktree']['commit'], record.worktree.commit)
                self.assertEqual(rep['verification_class'], record.suite.verification_class.value)
                # JSON is valid and round-trips.
                self.assertEqual(json.loads(json.dumps(rep)), rep)

    def test_report_written_to_unique_per_run_path(self):
        with tempfile.TemporaryDirectory() as d:
            runs = report_mod.local_runs_dir(Path(d))
            e1 = RecordingExecutor(0)
            sched = Scheduler(executor=SuiteExecutor(e1), preflight=lambda s, e: {})
            r1 = sched.submit('completion-contract', identity())
            r2 = sched.submit('completion-contract', identity())
            p1 = report_mod.write_run_report(sched.record(r1), runs)
            p2 = report_mod.write_run_report(sched.record(r2), runs)
            self.assertNotEqual(p1, p2)
            self.assertEqual(json.loads(p1.read_text())['run_id'], r1)
            self.assertEqual(json.loads(p2.read_text())['run_id'], r2)

    def test_report_does_not_record_secrets(self):
        sched = Scheduler(executor=SuiteExecutor(RecordingExecutor(0)), preflight=lambda s, e: {})
        run_id = sched.submit('completion-contract', identity())
        text = json.dumps(report_mod.run_report(sched.record(run_id)))
        self.assertNotIn('SECRET', text.upper().replace('SCHEMA', '').replace('SENSITIV', ''))


class HermeticDirectExecutionTest(unittest.TestCase):
    def test_hermetic_run_does_not_queue_behind_the_host_scheduler(self):
        sched = Scheduler(executor=SuiteExecutor(RecordingExecutor(0)), preflight=lambda s, e: {})
        run_id = sched.submit('completion-contract', identity())
        # Hermetic: executed immediately, never enters the host queue.
        self.assertEqual(sched.queued(), [])
        self.assertEqual(sched.active_run_id(), None)
        self.assertEqual(sched.record(run_id).state, RunState.PASS)


class PlaceholderSubstitutionTest(unittest.TestCase):
    """Whole-argument placeholders ($NAME and bare NAME) resolve from env only."""

    def test_dollar_placeholder(self):
        from verification.suite import _substitute
        out = _substitute(['$BLAINE_PYTHON', '-m', 'pytest'], {'BLAINE_PYTHON': '/venv/bin/python'})
        self.assertEqual(out, ['/venv/bin/python', '-m', 'pytest'])

    def test_bare_identifier_placeholder(self):
        from verification.suite import _substitute
        out = _substitute(['BLAINE_PYTHON', '-m', 'pytest', 'tests'],
                          {'BLAINE_PYTHON': '/venv/bin/python'})
        self.assertEqual(out, ['/venv/bin/python', '-m', 'pytest', 'tests'])

    def test_unresolvable_left_verbatim(self):
        from verification.suite import _substitute
        # No value in env -> left verbatim so a broken reference is visible.
        self.assertEqual(_substitute(['$MISSING'], {}), ['$MISSING'])
        # A literal token that is not an env key is left alone.
        self.assertEqual(_substitute(['-q'], {'Q': 'x'}), ['-q'])

    def test_empty_env_value_left_verbatim(self):
        from verification.suite import _substitute
        # An explicitly empty tool is a visible misconfiguration, not a skip.
        self.assertEqual(_substitute(['BLAINE_PYTHON'], {'BLAINE_PYTHON': ''}), ['BLAINE_PYTHON'])


if __name__ == '__main__':
    unittest.main()
