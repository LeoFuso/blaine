"""worktree.py -- establish the identity of the checkout being tested.

Never assume a canonical checkout path. All checkout-local operations resolve
the actual worktree through git. Reports must record the tested worktree,
branch, commit and dirty state.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


class WorktreeError(ValueError):
    """The path is not a usable git worktree."""


@dataclass(frozen=True)
class WorktreeIdentity:
    root: Path
    branch: str
    commit: str
    dirty: bool
    dirty_summary: str


def run_git(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(['git', *args], cwd=cwd, capture_output=True, text=True)
    if completed.returncode != 0:
        raise WorktreeError(f'git {" ".join(args)} failed: {completed.stderr.strip()}')
    return completed.stdout.strip()


def resolve(path: str | Path) -> WorktreeIdentity:
    """Resolve ``path`` to the identity of its git worktree.

    Raises WorktreeError for non-directories and non-git paths.
    """
    target = Path(path).resolve()
    if not target.is_dir():
        raise WorktreeError(f'not a directory: {target}')
    try:
        root_raw = run_git(['rev-parse', '--show-toplevel'], target)
    except WorktreeError:
        raise WorktreeError(f'not a git worktree: {target}') from None
    root = Path(root_raw).resolve()

    try:
        commit = run_git(['rev-parse', 'HEAD'], root)
    except WorktreeError as error:
        raise WorktreeError('worktree has no commit (empty repository)') from error

    try:
        branch = run_git(['branch', '--show-current'], root)
    except WorktreeError:
        branch = ''  # detached HEAD or unborn
    if not branch:
        # detached: report the short commit as the branch identity
        branch = f'detached@{commit[:12]}'

    dirty = bool(run_git(['status', '--porcelain'], root))
    return WorktreeIdentity(root=root, branch=branch, commit=commit,
                            dirty=dirty, dirty_summary='')


def describe(identity: WorktreeIdentity) -> dict:
    return {'worktree': str(identity.root), 'branch': identity.branch,
            'commit': identity.commit, 'dirty': identity.dirty}
