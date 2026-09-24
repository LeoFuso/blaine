"""scheduler.py -- strict FIFO host-run scheduler core.

Implements the durable scheduling *semantics* that the Restate object wraps:
submission, strict FIFO queueing, single-active-host-run admission, run
lifecycle, terminal release, bounded interruption, and result normalization.

Two execution paths share this core:

  * in-process (hostless): used by the deterministic unit tests and by the
    CLI for HERMETIC suites, which do not wait behind the host queue; and
  * native Restate: VerificationRun[run_id] / VerificationScheduler[host] in
    ``verification/scheduler_restate.py`` delegate every decision here so the
    queue policy and lifecycle are written once.

The caller never supplies commands. It names a KNOWN SUITE; the repository-owned
suite definition supplies the commands. ``submit(command=...)`` does not exist.

Resource coordination (v0): at most ONE host-bound run is admitted at a time.
All resources a run declares are admitted atomically with the run -- there is
no such thing as partial acquisition, so multi-resource deadlock is impossible
by construction. FIFO fairness holds for admitted queued runs under the
assumptions that running suites terminate or time out and the scheduler itself
remains available.
"""
from __future__ import annotations

import itertools
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from verification.suite import (ProbeResult, Result, Suite, SuiteExecutor, SuiteError,
                                VerificationClass, discover_suites, load_suite)
from verification.worktree import WorktreeError, WorktreeIdentity, resolve

# v0 interruption bound: a run that does not finish within this window is
# interrupted and the slot released so later queued work is not starved.
DEFAULT_RUN_TIMEOUT = 1800.0


class RunState(str, Enum):
    SUBMITTED = 'SUBMITTED'
    QUEUED = 'QUEUED'
    PREFLIGHT = 'PREFLIGHT'
    RUNNING = 'RUNNING'
    COLLECTING_RESULT = 'COLLECTING_RESULT'
    PASS = 'PASS'
    FAIL = 'FAIL'
    BLOCKED = 'BLOCKED'
    INTERRUPTED = 'INTERRUPTED'


TERMINAL = {RunState.PASS, RunState.FAIL, RunState.BLOCKED, RunState.INTERRUPTED}


class SubmitError(ValueError):
    """The submission is not admissible (unknown suite, bad worktree, ...)."""


@dataclass
class QueueEntry:
    run_id: str
    submission: int
    suite_name: str
    submitted_at: float


@dataclass
class RunRecord:
    run_id: str
    suite: Suite
    worktree: WorktreeIdentity
    state: RunState = RunState.SUBMITTED
    prerequisites: dict[str, ProbeResult] = field(default_factory=dict)
    steps: list[Any] = field(default_factory=list)
    result: Result | None = None
    reason: str = ''
    admitted_at: float | None = None
    started_at: float | None = None
    completed_at: float | None = None
    duration: float | None = None

    def progress(self) -> dict:
        """State view for reports; agrees with the scheduler's own bookkeeping."""
        return {'run_id': self.run_id, 'suite': self.suite.name,
                'state': self.state.value, 'result': self.result.value if self.result else None,
                'reason': self.reason,
                'verification_class': self.suite.verification_class.value,
                'resources': list(self.suite.resources),
                'prerequisites': {k: v.to_dict() for k, v in self.prerequisites.items()},
                'steps': [s.to_dict() for s in self.steps],
                'worktree': str(self.worktree.root), 'branch': self.worktree.branch,
                'commit': self.worktree.commit, 'dirty': self.worktree.dirty,
                'admitted_at': self.admitted_at, 'started_at': self.started_at,
                'completed_at': self.completed_at, 'duration': self.duration}


class Scheduler:
    """Strict FIFO, single-active-host-run scheduler.

    Parameters
    ----------
    executor:
        SuiteExecutor (or subclass) that runs steps. Tests inject a fake to
        observe execution without touching the host.
    preflight:
        Callable(suite) -> dict[probe_name, ProbeResult]. Defaults to running the
        suite's declared probes against the local environment.
    run_timeout:
        Bounded interruption window for a single run (seconds).
    """

    def __init__(self, executor: SuiteExecutor | None = None, preflight=None,
                 run_timeout: float = DEFAULT_RUN_TIMEOUT,
                 environment: Mapping[str, str] | None = None) -> None:
        self.executor = executor or SuiteExecutor()
        self.preflight = preflight or _default_preflight
        self.run_timeout = run_timeout
        self.environment = dict(environment or {})
        self.queue: deque[QueueEntry] = deque()
        self.active: RunRecord | None = None
        self.runs: dict[str, RunRecord] = {}
        self._counter = itertools.count(1)
        self._admissions = 0

    # -- submission ---------------------------------------------------------
    def submit(self, suite_name: str, worktree: str | WorktreeIdentity) -> str:
        """Submit a KNOWN suite for the given worktree. Returns the run_id.

        The worktree is resolved and validated here; the suite commands always
        come from the repository-owned definition, never from the caller.
        """
        try:
            suite = load_suite(suite_name)
            identity = worktree if isinstance(worktree, WorktreeIdentity) else resolve(worktree)
        except (SuiteError, WorktreeError) as error:
            raise SubmitError(str(error)) from error
        run_id = f'run-{next(self._counter)}'
        record = RunRecord(run_id=run_id, suite=suite, worktree=identity,
                           state=RunState.SUBMITTED)
        self.runs[run_id] = record
        if suite.verification_class is VerificationClass.HERMETIC:
            # Hermetic work does not queue behind the host scheduler.
            self._advance(record)
            return run_id
        self.queue.append(QueueEntry(run_id, next(self._counter), suite_name, time.time()))
        record.state = RunState.QUEUED
        return run_id

    def submit_command(self, command) -> None:  # noqa: D102 - guardrail, not an API
        raise SubmitError('the scheduler only accepts named suites; arbitrary commands are not admissible')

    # -- queue inspection ---------------------------------------------------
    def queued(self) -> list[str]:
        return [entry.run_id for entry in self.queue]

    def active_run_id(self) -> str | None:
        return self.active.run_id if self.active else None

    def record(self, run_id: str) -> RunRecord:
        return self.runs[run_id]

    # -- admission (single active host run; atomic) --------------------------
    def tick(self, now: float | None = None) -> str | None:
        """Admit the next queued run if no host run is active. Returns run_id or None.

        Admission is atomic: the run is admitted with its full declared resource
        set, or it is not admitted at all. With at most one active host run, no
        run can hold one resource and wait for another.
        """
        if self.active is not None or not self.queue:
            return None
        entry = self.queue.popleft()  # strict FIFO head; admitted atomically
        record = self.runs[entry.run_id]
        record.state = RunState.PREFLIGHT
        record.prerequisites = self.preflight(record.suite, self.environment)
        blocked = {name: r for name, r in record.prerequisites.items() if not r.available}
        if blocked:
            record.result = Result.BLOCKED
            record.reason = 'missing prerequisites: ' + ', '.join(
                f'{n}={r.status.value}' + (f' ({r.detail})' if r.detail else '') for n, r in sorted(blocked.items()))
            record.state = RunState.BLOCKED
            record.completed_at = now or time.time()
            self._release()
            return record.run_id
        record.admitted_at = now or time.time()
        self._admissions += 1
        self.active = record
        record.state = RunState.RUNNING
        record.started_at = record.admitted_at
        return record.run_id

    # -- execution (called by the run owner after admission) -----------------
    def run(self, run_id: str) -> None:
        """Execute an admitted run to a terminal state, releasing the slot."""
        record = self.runs[run_id]
        if self.active is not record:
            raise ValueError(f'{run_id} is not the active run')
        record.state = RunState.RUNNING
        try:
            result, reports, reason = self.executor.execute(record.suite, record.worktree.root,
                                                            record.prerequisites, self.environment)
        except Exception as error:  # execution defect is a truthful FAIL, never a hang
            record.result = Result.FAIL
            record.reason = f'executor error: {error.__class__.__name__}: {error}'
            record.state = RunState.FAIL
            record.completed_at = time.time()
            record.duration = (record.completed_at or 0) - (record.started_at or 0)
            self._release()
            return
        record.state = RunState.COLLECTING_RESULT
        record.steps = reports
        record.result = result
        record.reason = reason
        record.state = RunState(result.value)
        record.completed_at = time.time()
        record.duration = (record.completed_at or 0) - (record.started_at or 0)
        self._release()

    def interrupt(self, run_id: str, reason: str = '') -> None:
        """Bounded interruption: record the run INTERRUPTED and release the slot.

        An interrupted run never holds the slot, so later queued work proceeds.
        """
        record = self.runs[run_id]
        if self.active is not record:
            return
        record.result = Result.BLOCKED
        record.reason = f'interrupted: {reason}' if reason else 'interrupted'
        record.state = RunState.INTERRUPTED
        record.completed_at = time.time()
        record.duration = (record.completed_at or 0) - (record.started_at or 0)
        self._release()

    # -- internals -----------------------------------------------------------
    def _advance(self, record: RunRecord) -> None:
        """Drive a hermetic run through its lifecycle synchronously."""
        record.state = RunState.PREFLIGHT
        record.prerequisites = self.preflight(record.suite, self.environment)
        blocked = {name: r for name, r in record.prerequisites.items() if not r.available}
        if blocked:
            record.result = Result.BLOCKED
            record.reason = 'missing prerequisites: ' + ', '.join(
                f'{n}={r.status.value}' + (f' ({r.detail})' if r.detail else '') for n, r in sorted(blocked.items()))
            record.state = RunState.BLOCKED
            record.completed_at = time.time()
            return
        record.state = RunState.RUNNING
        record.started_at = time.time()
        result, reports, reason = self.executor.execute(record.suite, record.worktree.root,
                                                        record.prerequisites, self.environment)
        record.state = RunState.COLLECTING_RESULT
        record.steps = reports
        record.result = result
        record.reason = reason
        record.state = RunState(result.value)
        record.completed_at = time.time()
        record.duration = (record.completed_at or 0) - (record.started_at or 0)

    def _release(self) -> None:
        self.active = None


def _default_preflight(suite: Suite, environment: Mapping[str, str]) -> dict[str, ProbeResult]:
    from verification import probes  # noqa: F401  register probes on first use
    import os
    from verification.suite import probe
    env = {**os.environ, **environment}
    return {name: probe(name, Path('.'), env) for name in suite.prereq_probes}
