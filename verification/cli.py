"""Canonical local verification CLI.

Drives the scheduler core without a Restate server for the paths that do not
require one, and prints a machine-readable summary. This is the thin, stable
launcher that nox sessions and agent prompts invoke.

Commands
--------
list
    List discovered suites (additive; no central registry).
run SUITE
    Execute a HERMETIC suite directly in the resolved worktree. HERMETIC suites
    never queue behind the host scheduler; they run immediately. A HOST suite
    submitted here is rejected with a clear message -- use the Restate
    scheduler for host-bound work.
submit SUITE
    Submit a HOST suite to the Restate scheduler (requires a running server).
    v0: prints the submission; durable execution is owned by Restate.

The worktree is always resolved from git (never assumed); reports record the
tested worktree and commit.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from verification.report import summarize, write_run_report, local_runs_dir
from verification.scheduler import Scheduler, SubmitError
from verification.suite import (Result, VerificationClass, discover_suites,
                                SuiteError)
from verification.toolchain import toolchain_environment
from verification.worktree import WorktreeError, resolve


def _print(payload, summary: str) -> None:
    print(summary)
    print(json.dumps(payload, indent=2, sort_keys=True))


def cmd_list(_args) -> int:
    suites = discover_suites()
    rows = []
    for name in sorted(suites):
        suite = suites[name]
        rows.append({
            'name': name,
            'class': suite.verification_class.value,
            'resources': list(suite.resources),
            'prereq_probes': list(suite.prereq_probes),
            'description': suite.description,
        })
    print(f'{len(rows)} suites discovered (additive; no central registry):')
    for row in rows:
        probes = ', '.join(row['prereq_probes']) or '-'
        resources = ', '.join(row['resources']) or '-'
        print(f"  {row['name']:<28} {row['class']:<9} probes=[{probes}] resources=[{resources}]")
        print(f"      {row['description']}")
    return 0


def cmd_run(args) -> int:
    environment = toolchain_environment()
    if args.worktree:
        worktree = args.worktree
    else:
        worktree = str(Path.cwd())
    try:
        identity = resolve(worktree)
    except WorktreeError as error:
        print(f'error: cannot resolve worktree: {error}', file=sys.stderr)
        return 2
    scheduler = Scheduler(environment=environment)
    try:
        run_id = scheduler.submit(args.suite, identity)
    except SubmitError as error:
        print(f'error: {error}', file=sys.stderr)
        return 2
    record = scheduler.record(run_id)
    if record.suite.verification_class is not VerificationClass.HERMETIC:
        print(f'error: suite {record.suite.name!r} is {record.suite.verification_class.value}; '
              f'it must be submitted to the Restate host scheduler, not run directly.',
              file=sys.stderr)
        return 2
    runs_dir = local_runs_dir(identity.root)
    path = write_run_report(record, runs_dir)
    report = __import__('json').loads(path.read_text())
    summary = (f"[{record.state.value}] suite={record.suite.name} worktree={identity.root} "
               f"commit={identity.commit[:12]} dirty={identity.dirty} -> {path}")
    _print(report, summary)
    return 0 if record.result is Result.PASS else 1


def cmd_submit(args) -> int:
    # v0: host-bound work is scheduled by Restate (verification.scheduler_restate).
    print('error: HOST suites are scheduled by the Restate scheduler.\n'
          'See docs/verification.md for the canonical host submission command.',
          file=sys.stderr)
    return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='blaine-verification', description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)

    sub.add_parser('list', help='list discovered suites').set_defaults(func=cmd_list)

    p_run = sub.add_parser('run', help='run a HERMETIC suite in a worktree')
    p_run.add_argument('suite')
    p_run.add_argument('--worktree', default=None,
                       help='git worktree path (default: current directory)')
    p_run.set_defaults(func=cmd_run)

    p_sub = sub.add_parser('submit', help='submit a HOST suite (Restate)')
    p_sub.add_argument('suite')
    p_sub.add_argument('--worktree', default=None)
    p_sub.set_defaults(func=cmd_submit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == '__main__':
    raise SystemExit(main())
