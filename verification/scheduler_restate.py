"""scheduler_restate.py -- native Restate durable scheduler (v0).

Implements the durable scheduling identity on top of the semantics in
``verification/scheduler.py``:

  * VerificationScheduler[host] -- a VirtualObject that owns the queued host
    runs, the single active host run, FIFO ordering, admission and lifecycle
    transition coordination. ``submit`` is ``exclusive`` so at most one host
    run is admitted at a time. Admission is atomic: the head entry is
    dequeued and the slot claimed before anything is dispatched. No partial
    resource acquisition exists.
  * VerificationRun[run_id]     -- a Workflow that owns one run's execution:
    preflight, step execution (via ``ctx.run_typed``), result collection and
    the terminal PASS / FAIL / BLOCKED transition.

Durable call topology (avoids workflow→VirtualObject calls, which are
unreliable in restate-sdk-python 1.0.5 protocol v6):

  submit (VirtualObject, exclusive)
    → _full_dispatch (shared)
      → run.main (Workflow) via ctx.object_call  [VO→WF, works in v6]
      → release slot, admit next FIFO head

The run's terminal state is journaled in the workflow and readable via its
shared ``status`` handler; the scheduler observes it after the blocking
object_call returns.

Restate SDK notes (restate-sdk-python 1.0.5, protocol v6):
  * ObjectContext.set and WorkflowContext.set are synchronous.
  * ObjectContext.get and WorkflowContext.get must be awaited.
  * ctx.get(name, type_hint=...) -- the second positional arg is a serde,
    not a type; passing a bare ``list`` or ``dict`` as serde raises
    AttributeError. Always use type_hint for non-default types.
  * workflow_send / object_call require a registered handler reference.
  * workflow_send is synchronous (returns SendHandle; do not await).
"""
from __future__ import annotations

import os
import re
import tempfile
from datetime import timedelta
from pathlib import Path

import restate

from verification import scheduler as core
from verification.suite import Result, VerificationClass

HOST = 'blaine'
RUN_WORKFLOW = 'VerificationRun'


def scheduler_name(host: str) -> str:
    label = ''.join(ch if ch.isalnum() else '_' for ch in (host or HOST)).strip('_') or 'blaine'
    return 'VerificationScheduler_' + label


# --- in-process helpers (shared with the core) -------------------------------

def resolve_identity(worktree: str) -> dict:
    from verification.worktree import WorktreeError, resolve
    try:
        identity = resolve(worktree)
    except WorktreeError as error:
        raise restate.TerminalError(f'invalid worktree: {error}', status_code=400) from error
    return {'root': str(identity.root), 'branch': identity.branch,
            'commit': identity.commit, 'dirty': identity.dirty}


def load_suite(suite_name: str):
    """Load a named suite from an optional override directory.

    The override is imported as a fresh module path so a scratch directory
    does not have to be importable as ``verification.suites``.
    """
    import importlib
    import verification.suite as _s
    override = os.environ.get('BLAINE_VERIFICATION_SUITES_DIR')
    if not override:
        from verification.suite import SuiteError, load_suite as _load
        try:
            return _load(suite_name)
        except SuiteError as error:
            raise restate.TerminalError(str(error), status_code=400) from error
    directory = Path(override)
    if not isinstance(suite_name, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', suite_name):
        raise restate.TerminalError(f'unknown or invalid suite name: {suite_name!r}', status_code=400)
    stem = suite_name.replace('-', '_')
    module_path = directory / f'{stem}.py'
    if not module_path.exists():
        raise restate.TerminalError(f'unknown suite: {suite_name!r}', status_code=400)
    spec = importlib.util.spec_from_file_location(f'_vn_suite_{stem}', str(module_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    raw = getattr(module, 'SUITE', None)
    if raw is None:
        raise restate.TerminalError(f'unknown suite: {suite_name!r} (no SUITE)', status_code=400)
    suite = raw if isinstance(raw, _s.Suite) else _s._suite_from_mapping(raw)
    if suite.name != stem.replace('_', '-'):
        raise restate.TerminalError(f'suite name {suite.name!r} does not match file', status_code=400)
    return suite


def environment_for(suite, host: str) -> dict:
    from verification.probes import DEFAULT_TOOLCHAIN
    env = dict(os.environ)
    env.setdefault('BLAINE_PYTHON', str(DEFAULT_TOOLCHAIN / 'runtime-venv' / 'bin' / 'python'))
    env.setdefault('BLAINE_RESTATE_SERVER', str(DEFAULT_TOOLCHAIN / 'bin' / 'restate-server'))
    env.setdefault('BLAINE_E10_OUTPUT',
                   os.path.join(tempfile.gettempdir(), f'e10-{suite.name}-{os.getpid()}'))
    return env


def probe(name: str, environment: dict):
    from verification import probes  # noqa: F401 register on first use
    from verification.suite import probe as _probe
    return _probe(name, Path('.'), environment)


def run_step(step, worktree: str, environment: dict) -> dict:
    """Execute one repository-owned step; returns a StepReport dict."""
    from verification import suite as _s
    from verification.suite import Step
    command = list(step.command)
    command = _s._substitute(command, environment)
    env = {k: _s._substitute([v], environment)[0] for k, v in (step.env or {}).items()}
    report = _s.CommandExecutor().run(Step(step.name, command, step.timeout, env),
                                      Path(worktree), env)
    return report.to_dict()


def summarize(steps: list[dict]) -> tuple[Result, str]:
    failed = [s for s in steps if (s['exit_code'] not in (0, None)) or s['timed_out']]
    if not failed:
        return Result.PASS, ''
    reason = '; '.join(f"{s['name']}: exit={s['exit_code']}"
                       + (' (timeout)' if s['timed_out'] else '') for s in failed)
    return Result.FAIL, reason


# --- the durable objects -----------------------------------------------------

def build_run(host: str = HOST) -> restate.Workflow:
    """VerificationRun[run_id] -- one run's durable execution."""
    run_workflow = restate.Workflow(RUN_WORKFLOW)

    @run_workflow.main(workflow_retention=timedelta(days=7))
    async def main(ctx: restate.WorkflowContext, request: dict) -> dict:
        run_id = ctx.key()
        suite = load_suite(request['suite'])
        identity = resolve_identity(request['worktree'])
        ctx.set('run', {'run_id': run_id, 'suite': request['suite'],
                        'state': core.RunState.SUBMITTED.value, 'worktree': identity})
        ctx.set('report', {'run_id': run_id, 'suite': request['suite'],
                           'state': core.RunState.SUBMITTED.value, 'worktree': identity,
                           'host': request.get('host', host)})

        environment = environment_for(suite, host)
        prerequisites = {p: probe(p, environment) for p in suite.prereq_probes}
        blocked = {n: r for n, r in prerequisites.items() if not r.available}

        if blocked:
            reason = 'missing prerequisites: ' + ', '.join(
                f'{n}={r.status.value}' + (f' ({r.detail})' if r.detail else '')
                for n, r in sorted(blocked.items()))
            result, steps = Result.BLOCKED, []
        else:
            ctx.set('run', {**(await ctx.get('run', type_hint=dict) or {}),
                            'state': core.RunState.RUNNING.value})
            steps = []
            for step in suite.steps:
                steps.append(await ctx.run_typed(f'step-{step.name}', run_step,
                                                 step=step, worktree=identity['root'],
                                                 environment=environment))
            ctx.set('run', {**(await ctx.get('run', type_hint=dict) or {}),
                            'state': core.RunState.COLLECTING_RESULT.value})
            result, reason = summarize(steps)

        ctx.set('report', {
            'schema_version': 1, 'run_id': run_id, 'suite': suite.name,
            'result': result.value, 'reason': reason,
            'verification_class': suite.verification_class.value,
            'state': result.value, 'host': request.get('host', host),
            'worktree': identity, 'resources': list(suite.resources),
            'prerequisites': {k: v.to_dict() for k, v in prerequisites.items()},
            'steps': steps,
        })
        ctx.set('run', {**(await ctx.get('run', type_hint=dict) or {}),
                        'state': result.value, 'result': result.value})
        return await ctx.get('report', type_hint=dict) or {}

    @run_workflow.handler()
    async def status(ctx: restate.WorkflowSharedContext) -> dict:
        return await ctx.get('run', type_hint=dict) or {'run_id': ctx.key(), 'state': 'NOT_FOUND'}

    run_workflow.main_handler = main
    return run_workflow


def _get_handler_ref(workflow, handler_name: str):
    """Extract the registered handler wrapper for a named workflow handler."""
    for name, handler in workflow.handlers.items():
        if handler.name == handler_name:
            # The handler object has a 'fn' attribute which is the wrapper.
            return handler.fn if hasattr(handler, 'fn') else handler
    return None


def build_services(host: str = HOST):
    """Return the [scheduler, run] service list for composition.

    Used by the canonical deployment to compose the verification services
    alongside other services in a single Restate app endpoint.
    """
    scheduler, run = _build_scheduler_and_run(host)
    return [scheduler, run]


def build_app(host: str = HOST):
    """Deployment: scheduler object and run workflow.

    The scheduler's ``_full_dispatch`` does the full admission→execution→
    release cycle in a single shared handler call. The blocking
    ``object_call`` to the run's main handler (VirtualObject→Workflow)
    works in protocol v6. After the run returns, the slot is released and
    the next FIFO head is admitted recursively.
    """
    scheduler, run = _build_scheduler_and_run(host)
    return restate.app([scheduler, run])


def _build_scheduler_and_run(host: str):
    run = build_run(host)
    run_main = run.main_handler
    name = scheduler_name(host)
    scheduler = restate.VirtualObject(name)

    @scheduler.handler(kind='exclusive')
    async def submit(ctx, request: dict) -> dict:
        suite_name = request.get('suite')
        worktree = request.get('worktree')
        if not suite_name or not worktree:
            raise restate.TerminalError(
                'submission requires a known suite name and a worktree; '
                'arbitrary commands are not admissible', status_code=400)
        load_suite(suite_name)
        resolve_identity(worktree)
        queue = list(await ctx.get('queue', type_hint=list) or [])
        run_id = f'run-{ctx.uuid().hex[:16]}'
        ctx.set('queue', queue + [{'run_id': run_id, 'suite': suite_name,
                                   'worktree': worktree}])
        await _full_dispatch(ctx)
        return {'run_id': run_id, 'state': 'QUEUED', 'suite': suite_name,
                'worktree': worktree}

    @scheduler.handler(kind='shared')
    async def status(ctx) -> dict:
        queue = list(await ctx.get('queue', type_hint=list) or [])
        active = await ctx.get('active', type_hint=str)
        return {'queue': [q['run_id'] for q in queue], 'active': active, 'host': host}

    async def _full_dispatch(ctx) -> None:
        """Admit the FIFO head, execute it (blocking), and release the slot.

        The object_call to the run's main handler blocks until the run
        reaches its terminal state (the workflow returns the report).
        After the run returns, the slot is released and the next head is
        admitted recursively. If the queue is empty, the slot is released
        and the function returns.
        """
        if await ctx.get('active', type_hint=str):
            return
        queue = list(await ctx.get('queue', type_hint=list) or [])
        if not queue:
            return
        entry = queue.pop(0)
        ctx.set('queue', queue)
        ctx.set('active', entry['run_id'])
        # Durable blocking call to the run's main handler (VO→WF).
        if run_main is not None:
            await ctx.object_call(run_main, entry['run_id'],
                                  {'suite': entry['suite'], 'worktree': entry['worktree'],
                                   'scheduler': name, 'host': host})
        # Run is terminal; release the slot.
        ctx.set('active', None)
        # Admit the next head (strict FIFO).
        await _full_dispatch(ctx)

    return scheduler, run
