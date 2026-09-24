"""Prerequisite probes for host-bound suites.

Probes only *observe*: they detect installed tools, service health, and
versions. They must NEVER install, start, configure or provision anything.

A missing prerequisite is UNAVAILABLE, which feeds BLOCKED semantics. A
surprising shape is MALFORMED, which also feeds BLOCKED (never PASS).

Only probes justified by an actual initial suite are implemented: the
completion-contract host suite requires the restate toolchain. Do not add
speculative probes for future subsystems.
"""
from __future__ import annotations

from pathlib import Path

from verification.suite import ProbeResult, ProbeStatus, register_probe

# Where the canonical Blaine host keeps its local toolchain (shared across
# worktrees). Overridable per-suite via step env for isolated test instances.
DEFAULT_TOOLCHAIN = Path('/home/leofuso/workspace/blaine/.local')


@register_probe('restate')
def probe_restate(_suite_dir: Path, env) -> ProbeResult:
    """The restate toolchain: restate-server binary + the Python SDK.

    The suite's own venv (BLAINE_VENV) carries the SDK; the server binary is
    expected in the canonical toolchain unless BLAINE_RESTATE_SERVER points at
    a specific binary (e.g. an isolated test instance).
    """
    try:
        toolchain = Path(env.get('BLAINE_TOOLCHAIN') or DEFAULT_TOOLCHAIN)
        server = Path(env.get('BLAINE_RESTATE_SERVER') or (toolchain / 'bin' / 'restate-server'))
        if not server.is_file():
            return ProbeResult(ProbeStatus.UNAVAILABLE, f'restate-server not found at {server}')
        venv = Path(env.get('BLAINE_VENV') or (toolchain / 'runtime-venv'))
        python = venv / 'bin' / 'python'
        if not python.is_file():
            return ProbeResult(ProbeStatus.UNAVAILABLE, f'runtime venv python not found at {python}')
        # Version check of the server binary: it must answer with a semver.
        completed = __import__('subprocess').run([str(server), '--version'], capture_output=True, text=True, timeout=10)
        if completed.returncode != 0 or not completed.stdout.strip():
            return ProbeResult(ProbeStatus.MALFORMED, f'restate-server --version failed: {completed.stderr.strip()[:200]}')
        version = completed.stdout.strip().splitlines()[-1]
        return ProbeResult(ProbeStatus.AVAILABLE, version)
    except FileNotFoundError as error:
        return ProbeResult(ProbeStatus.UNAVAILABLE, str(error))
    except Exception as error:  # unexpected failure is a probe defect
        return ProbeResult(ProbeStatus.MALFORMED, f'{error.__class__.__name__}: {error}')
