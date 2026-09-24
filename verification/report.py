"""report.py -- machine-readable qualification reports.

Ordinary runs write to a worktree-safe, Git-ignored local location
(``.local/verification/runs``). Reports are unique per run_id so concurrent
worktrees never overwrite each other. Milestone/handoff evidence is promoted
explicitly with :func:`promote`; it is never auto-committed.

A report records run_id, suite, result, worktree/commit/dirty, timing, the
verification class, declared resources, prerequisite results, executed commands,
child exit codes, tool versions and the failure/block reason. It must not record
secrets or raw proprietary context.
"""
from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from verification.scheduler import RunRecord
from verification.suite import VerificationClass

SCHEMA_VERSION = 1


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_report(record: RunRecord) -> dict:
    progress = record.progress()
    return {
        'schema_version': SCHEMA_VERSION,
        'generated_at': _utcnow(),
        'run_id': record.run_id,
        'suite': record.suite.name,
        'verification_class': record.suite.verification_class.value,
        'result': record.result.value if record.result else progress['state'],
        'reason': record.reason,
        'resources': list(record.suite.resources),
        'prerequisites': progress['prerequisites'],
        'steps': progress['steps'],
        'worktree': {'root': progress['worktree'], 'branch': progress['branch'],
                     'commit': progress['commit'], 'dirty': progress['dirty']},
        'timing': {'admitted_at': record.admitted_at, 'started_at': record.started_at,
                   'completed_at': record.completed_at, 'duration': record.duration},
        'state': progress['state'],
        'environment': {'python': platform.python_version(), 'os': platform.platform(),
                        'hostname': os.uname().nodename},
    }


def write_run_report(record: RunRecord, runs_dir: Path) -> Path:
    """Write the report to a unique per-run path and return it."""
    runs_dir = runs_dir / record.run_id
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / 'report.json'
    path.write_text(json.dumps(run_report(record), indent=2, sort_keys=True) + '\n')
    return path


def local_runs_dir(root: Path) -> Path:
    """Git-ignored, worktree-local location for ordinary run reports."""
    return root / '.local' / 'verification' / 'runs'


def promote(record: RunRecord, destination: Path) -> Path:
    """Explicitly retain a run's report as milestone/handoff evidence.

    ``destination`` is a caller-named path (e.g. a directory inside a tracked
    ``evidence/`` folder). This is the only mechanism that moves a report toward
    retention; ordinary runs are never auto-promoted.
    """
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f'{record.run_id}.json'
    path.write_text(json.dumps(run_report(record), indent=2, sort_keys=True) + '\n')
    return path


def summarize(report: dict) -> str:
    """Human-readable one-line summary of a report."""
    work = report['worktree']
    parts = [f"{report['run_id']}: {report['suite']} -> {report['result']}",
             f"[{report['verification_class']}]"]
    if report['reason']:
        parts.append(f"reason: {report['reason']}")
    parts.append(f"worktree={work['root']} commit={work['commit'][:12]} dirty={work['dirty']}")
    return ' '.join(parts)
