"""Canonical toolchain environment resolution.

Resolves the default values for the ``BLAINE_*`` placeholders that suite
commands use (see :func:`verification.suite._substitute`). A suite declares
*which* tools it needs via its argv; this module answers *where* they live on
the canonical Blaine host.

This is observation-only: it locates an already-configured toolchain. It never
installs, starts or provisions anything. A tool that is not found is left
unresolved, so the resulting command is visibly broken (a step that cannot run)
rather than silently provisioned.

Defaults are the shared, worktree-independent toolchain under
``/home/leofuso/workspace/blaine/.local``. Every value is overridable through
the process environment, which is how tests and isolated run instances point at
their own copies.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

# Where the canonical Blaine host keeps its local toolchain (shared across
# worktrees). Mirrors verification.probes.DEFAULT_TOOLCHAIN.
DEFAULT_TOOLCHAIN = Path('/home/leofuso/workspace/blaine/.local')


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value else default


def resolve_python() -> str:
    """Python interpreter used to run repository-owned commands.

    Preference order:
      1. ``BLAINE_PYTHON`` if set in the environment (explicit override).
      2. The shared runtime venv python (carries pytest, restate-sdk, nox).
      3. The venv python if present, else the active interpreter (``sys.executable``).
    """
    explicit = os.environ.get('BLAINE_PYTHON')
    if explicit:
        return explicit
    venv_python = _env('BLAINE_TOOLCHAIN', str(DEFAULT_TOOLCHAIN))
    candidate = Path(venv_python) / 'runtime-venv' / 'bin' / 'python'
    if candidate.is_file():
        return str(candidate)
    active = _env('PYTHON', '')  # not a conventional name; keep for symmetry
    if active:
        return active
    import sys
    return sys.executable


def resolve_restate_server() -> str:
    """Path to the ``restate-server`` binary, or '' if not found."""
    explicit = os.environ.get('BLAINE_RESTATE_SERVER')
    if explicit:
        return explicit
    toolchain = Path(os.environ.get('BLAINE_TOOLCHAIN') or DEFAULT_TOOLCHAIN)
    candidate = toolchain / 'bin' / 'restate-server'
    return str(candidate) if candidate.is_file() else ''


def toolchain_environment() -> dict[str, str]:
    """The canonical ``BLAINE_*`` environment used for placeholder substitution.

    Returns a dict suitable for :class:`verification.scheduler.Scheduler` and
    :class:`verification.suite.SuiteExecutor`. Only tools that actually exist
    are resolved; the rest are omitted so a missing tool surfaces as a visible
    broken command / BLOCKED prerequisite, never as a silent provision.
    """
    env: dict[str, str] = {'BLAINE_TOOLCHAIN': _env('BLAINE_TOOLCHAIN', str(DEFAULT_TOOLCHAIN))}
    python = resolve_python()
    if python:
        env['BLAINE_PYTHON'] = python
    server = resolve_restate_server()
    if server:
        env['BLAINE_RESTATE_SERVER'] = server
    return env
