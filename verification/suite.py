"""Suite metadata, discovery and execution for local verification.

A *suite* is a repository-owned unit of qualification. Suites are discovered
additively: every ``*.py`` module in :data:`SUITES_DIR` that exposes a top-level
:data:`SUITE` dict is a suite. Adding a suite means adding a file; no central
registry, manifest or orchestrator file is edited.

The module also owns the verification-class and result enums, prerequisite
probe results, and the execution engine that runs a suite's repository-owned
commands and normalizes them into PASS / FAIL / BLOCKED.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from importlib import import_module
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUITES_DIR = Path(__file__).resolve().parent / 'suites'


class VerificationClass(str, Enum):
    """How much of the Blaine host a suite needs before it can validly run.

    HERMETIC -- runs from a normal checkout/worktree with no pre-existing
                Blaine host services (pytest, unit, contract tests, scripts).
    HOST     -- requires services/resources already configured on the canonical
                Blaine host (Restate, Goose, PostgreSQL, ...).
    FLEET    -- requires another host/device/peer. (Representable, deferred in v0.)
    CI_ONLY  -- semantics specific to GitHub CI/release infrastructure.
                (Representable, deferred in v0.)
    """
    HERMETIC = 'HERMETIC'
    HOST = 'HOST'
    FLEET = 'FLEET'
    CI_ONLY = 'CI_ONLY'


class Result(str, Enum):
    """Normalized qualification outcome.

    PASS    -- verification executed and satisfied its assertions.
    FAIL    -- verification executed and demonstrated incorrect behavior.
    BLOCKED -- verification could not validly execute because a required
               prerequisite or resource was unavailable.
    """
    PASS = 'PASS'
    FAIL = 'FAIL'
    BLOCKED = 'BLOCKED'


class ProbeStatus(str, Enum):
    AVAILABLE = 'AVAILABLE'
    UNAVAILABLE = 'UNAVAILABLE'
    MALFORMED = 'MALFORMED'


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(f'Invalid suite metadata: {detail}')


class SuiteError(ValueError):
    """A request or suite definition is not admissible."""


@dataclass(frozen=True)
class Step:
    """One repository-owned command executed inside the suite worktree.

    ``command`` is a list of arguments (argv); it is never a caller-supplied
    shell string. ``timeout`` is seconds and bounds the step so a hung command
    cannot hold a host slot forever. ``env`` entries are applied on top of the
    current environment and are recorded (names only) in evidence.
    """
    name: str
    command: list[str]
    timeout: float = 1200.0
    env: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require(isinstance(self.name, str) and re.fullmatch(r'[A-Za-z0-9._-]{1,80}', self.name),
                 'step name must be a bounded identifier')
        _require(isinstance(self.command, list) and self.command
                 and all(isinstance(arg, str) and arg.strip() for arg in self.command),
                 'step command must be a non-empty argv list')


@dataclass
class Suite:
    """Repository-owned definition of a named qualification suite."""
    name: str
    verification_class: VerificationClass
    description: str
    steps: list[Step]
    resources: tuple[str, ...] = ()
    prereq_probes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', self.name), 'suite name must be kebab-case')
        _require(isinstance(self.verification_class, VerificationClass), 'verification_class is required')
        _require(isinstance(self.description, str) and self.description.strip(), 'description is required')
        steps = list(self.steps)
        _require(all(isinstance(s, Step) for s in steps), 'steps must be Step instances')
        object.__setattr__(self, 'steps', steps)
        object.__setattr__(self, 'resources', tuple(self.resources))
        object.__setattr__(self, 'prereq_probes', tuple(self.prereq_probes))

    def __hash__(self) -> int:
        return hash(self.name)


class ProbeResult:
    """Outcome of one prerequisite probe.

    ``status`` distinguishes AVAILABLE / UNAVAILABLE / MALFORMED so callers can
    tell "the thing is not here" from "the thing is here but unexpected".
    ``detail`` is a short, human-readable reason that may appear in reports.
    ``detail`` must not contain secrets.
    """
    def __init__(self, status: ProbeStatus, detail: str = '') -> None:
        self.status = status
        self.detail = detail

    @property
    def available(self) -> bool:
        return self.status is ProbeStatus.AVAILABLE

    def to_dict(self) -> dict:
        return {'status': self.status.value, 'detail': self.detail}


PROBES: dict[str, callable] = {}


def register_probe(name: str):
    """Decorator: register a prerequisite probe callable (suite_dir, env) -> ProbeResult."""
    def wrap(function):
        PROBES[name] = function
        return function
    return wrap


def probe(name: str, suite_dir: Path, env: Mapping[str, str]) -> ProbeResult:
    if name not in PROBES:
        return ProbeResult(ProbeStatus.MALFORMED, f'no probe registered for {name!r}')
    try:
        result = PROBES[name](suite_dir, env)
    except Exception as error:  # a probe crashing is a probe defect, not a PASS
        return ProbeResult(ProbeStatus.MALFORMED, f'probe {name} raised: {error.__class__.__name__}: {error}')
    if not isinstance(result, ProbeResult):
        return ProbeResult(ProbeStatus.MALFORMED, f'probe {name} returned {type(result).__name__}')
    return result


def discover_suites() -> dict[str, Suite]:
    """Load every suite module in SUITES_DIR into a {name: Suite} mapping.

    A module is a suite iff it defines a top-level ``SUITE`` object. Modules that
    are helpers, or that define no SUITE, are skipped. Discovery is additive:
    the directory itself is the only shared surface, and it is never edited.
    """
    import verification.suites as package  # re-import so newly added files are seen
    suites: dict[str, Suite] = {}
    for file in sorted(SUITES_DIR.glob('*.py')):
        if file.name.startswith('_'):
            continue
        module_name = f'verification.suites.{file.stem}'
        module = import_module(module_name)
        raw = getattr(module, 'SUITE', None)
        if raw is None:
            continue
        if isinstance(raw, Suite):
            suite: Suite = raw
        elif isinstance(raw, Mapping):
            suite = _suite_from_mapping(raw)
        else:
            raise SuiteError(f'{file.name}: SUITE must be a Suite instance or a mapping')
        if suite.name != file.stem.replace('_', '-'):
            raise SuiteError(f'{file.name}: suite name {suite.name!r} must match the module file name')
        if suite.name in suites:
            raise SuiteError(f'duplicate suite {suite.name!r}')
        suites[suite.name] = suite
    return suites


def _suite_from_mapping(raw: Mapping) -> Suite:
    def steps(value):
        if value is None:
            return []
        result = []
        for item in value:
            if isinstance(item, Mapping):
                result.append(Step(name=item['name'], command=list(item['command']),
                                   timeout=item.get('timeout', 1200.0), env=item.get('env') or {}))
            elif isinstance(item, Step):
                result.append(item)
            else:
                raise SuiteError('steps must be Step instances or mappings')
        return result

    verification_class = raw.get('verification_class', raw.get('class'))
    if verification_class is not None and not isinstance(verification_class, VerificationClass):
        verification_class = VerificationClass(verification_class)
    return Suite(
        name=raw['name'],
        verification_class=verification_class or VerificationClass.HERMETIC,
        description=raw.get('description', ''),
        steps=steps(raw.get('steps')),
        resources=tuple(raw.get('resources', ())),
        prereq_probes=tuple(raw.get('prereq_probes', ())),
    )


def load_suite(name: str) -> Suite:
    """Load one named suite; unknown names raise SuiteError (no arbitrary names)."""
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name):
        raise SuiteError(f'unknown or invalid suite name: {name!r}')
    suites = discover_suites()
    try:
        return suites[name]
    except KeyError:
        raise SuiteError(f'unknown suite: {name!r}') from None


@dataclass
class StepReport:
    name: str
    command: list[str]
    exit_code: int | None
    stdout_tail: str
    stderr_tail: str
    duration: float
    timed_out: bool
    env: Mapping[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {'name': self.name, 'command': self.command, 'exit_code': self.exit_code,
                'stdout_tail': self.stdout_tail, 'stderr_tail': self.stderr_tail,
                'duration': round(self.duration, 3), 'timed_out': self.timed_out,
                'env': sorted(self.env)}


def _tail(data: bytes, limit: int = 4000) -> str:
    text = data.decode('utf-8', 'replace')
    return text if len(text) <= limit else '...\n' + text[-limit:]


class CommandExecutor:
    """Runs suite steps.

    The default implementation shells out with the suite worktree as cwd. Tests
    subclass this and override :meth:`run` to observe execution deterministically
    without touching the host.
    """

    def run(self, step: Step, worktree: Path, env: Mapping[str, str]) -> StepReport:
        import time
        process_env = dict(os.environ)
        process_env.update({str(k): str(v) for k, v in env.items()})
        start = time.monotonic()
        timed_out = False
        try:
            completed = subprocess.run(step.command, cwd=worktree, env=process_env,
                                       capture_output=True, timeout=step.timeout)
            report = StepReport(step.name, list(step.command), completed.returncode,
                                _tail(completed.stdout), _tail(completed.stderr),
                                time.monotonic() - start, timed_out, step.env)
        except subprocess.TimeoutExpired as error:
            timed_out = True
            stdout = error.stdout if isinstance(error.stdout, bytes) else b''
            stderr = error.stderr if isinstance(error.stderr, bytes) else b''
            report = StepReport(step.name, list(step.command), None, _tail(stdout or b''),
                                _tail(stderr or b'') + f'\n[timeout after {step.timeout}s]',
                                time.monotonic() - start, True, step.env)
        return report


def _substitute(command: list[str], env: Mapping[str, str]) -> list[str]:
    """Substitute whole-argument placeholders in argv from ``env``.

    Two forms are supported, both as *entire* arguments (never embedded in a
    longer string):

    - ``$NAME``  classic dollar-prefixed form.
    - ``NAME``   bare form, where ``NAME`` exactly matches an env key and the
                 argument looks like a bare identifier (upper-case, digits,
                 underscores). This keeps suite definitions terse: a suite
                 command may write ``['BLAINE_PYTHON', '-m', 'pytest', ...]``
                 and the executor resolves the python interpreter from env.

    Only arguments present in ``env`` are replaced; anything unresolvable is
    left verbatim so a broken reference is visible rather than silently
    executed. An empty env value also leaves the argument verbatim (an
    explicitly empty tool is a visible misconfiguration, not a hidden skip).
    """
    import re as _re
    bare_re = _re.compile(r'^[A-Z][A-Z0-9_]*$')
    result = []
    for arg in command:
        if isinstance(arg, str):
            if arg.startswith('$') and arg[1:] in env and env[arg[1:]]:
                result.append(env[arg[1:]])
            elif bare_re.fullmatch(arg) and arg in env and env[arg]:
                result.append(env[arg])
            else:
                result.append(arg)
        else:
            result.append(arg)
    return result


class SuiteExecutor:
    """Executes a suite's steps and normalizes the outcome into a Result.

    ``prerequisites`` maps probe name -> ProbeResult. Any UNAVAILABLE or
    MALFORMED prerequisite short-circuits the suite to BLOCKED *before* any
    step runs. ``environment`` supplies toolchain values (resolved by the
    scheduler or CLI) used to substitute ``$NAME`` references in step commands
    and step env. The executor never installs, starts or provisions anything:
    probes only observe, steps only run repository-owned commands.
    """

    def __init__(self, executor: CommandExecutor | None = None) -> None:
        self.executor = executor or CommandExecutor()

    def execute(self, suite: Suite, worktree: Path,
                prerequisites: Mapping[str, ProbeResult],
                environment: Mapping[str, str] = {}) -> tuple[Result, list[StepReport], str]:
        missing = {name: result for name, result in prerequisites.items()
                   if not result.available}
        if missing:
            blocked = ', '.join(f'{name}={r.status.value}' + (f' ({r.detail})' if r.detail else '')
                                for name, r in sorted(missing.items()))
            return Result.BLOCKED, [], blocked
        reports: list[StepReport] = []
        for step in suite.steps:
            command = _substitute(step.command, environment)
            env = {k: _substitute([v], environment)[0] for k, v in step.env.items()}
            reports.append(self.executor.run(Step(step.name, command, step.timeout, env), worktree, env))
        failed = [r for r in reports if (r.exit_code not in (0, None)) or r.timed_out]
        if not failed:
            return Result.PASS, reports, ''
        reason = '; '.join(f"{r.name}: exit={r.exit_code}" + (' (timeout)' if r.timed_out else '')
                           for r in failed)
        return Result.FAIL, reports, reason
