"""Derive the mechanically enforceable change window for long-lived branches."""
from __future__ import annotations

from pathlib import Path
import subprocess

GOVERNANCE_ADOPTION_COMMIT = "f3c33e2ef06650a04914d2660ca9cc5e14f0f08b"


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=check)


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    return _git(root, "merge-base", "--is-ancestor", ancestor, descendant, check=False).returncode == 0


def effective_base(root: Path, requested_base: str, head: str = "HEAD") -> str:
    """Return the base from which post-adoption enforcement should measure.

    A branch that existed before the governance merge adopts the rule when its
    first-parent history first contains the governance commit. In that case the
    first parent of the adoption merge is the temporal boundary: older feature
    work remains visible history, while the adoption merge and every later edit
    are checked. Branches already descended from the governance commit use their
    ordinary merge-base.
    """
    ordinary = _git(root, "merge-base", requested_base, head).stdout.strip()
    if not _is_ancestor(root, GOVERNANCE_ADOPTION_COMMIT, head):
        return ordinary

    first_parent = _git(root, "rev-list", "--first-parent", "--reverse", head).stdout.splitlines()
    adoption_point = next(
        (commit for commit in first_parent
         if _is_ancestor(root, GOVERNANCE_ADOPTION_COMMIT, commit)),
        None,
    )
    if not adoption_point or adoption_point == GOVERNANCE_ADOPTION_COMMIT:
        return ordinary

    parent = _git(root, "rev-parse", f"{adoption_point}^1", check=False)
    return parent.stdout.strip() if parent.returncode == 0 and parent.stdout.strip() else ordinary
