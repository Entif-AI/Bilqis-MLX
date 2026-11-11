"""Generation-zero custody for the exact admitted executable Factory release."""
from __future__ import annotations

from pathlib import Path

from ..records import invalid


def _release_receipt(release_sha256: str) -> dict:
    return {
        "factory_release_sha256": release_sha256,
        "factory_release_file": f"factory-releases/{release_sha256}.json",
    }


def _require_release_root_shape(run_dir: Path, release_sha256: str) -> None:
    root = Path(run_dir) / "factory-releases"
    if not root.exists() and not root.is_symlink():
        return
    if root.is_symlink() or not root.is_dir():
        invalid("BAMF_INITIAL_FACTORY_RELEASE_CUSTODY_INVALID")
    expected = f"{release_sha256}.json"
    entries = tuple(root.iterdir())
    if any(
            entry.name != expected
            or entry.is_symlink()
            or not entry.is_file()
            for entry in entries):
        invalid("BAMF_INITIAL_FACTORY_RELEASE_CUSTODY_INVALID")


def persist_prepared_initial_factory_release(run_dir: Path, prepared) -> dict:
    """Persist the exact prepared release before generation-zero pointer install."""
    expected = prepared.candidate.run_identity.factory_release_sha256
    release = prepared.release
    if release.release_sha256 != expected:
        invalid("BAMF_INITIAL_FACTORY_RELEASE_CUSTODY_INVALID")
    _require_release_root_shape(run_dir, expected)
    from bilqis_mlx.runtime.admission import _persist_executable_factory_release

    relative = _persist_executable_factory_release(Path(run_dir), release)
    receipt = _release_receipt(expected)
    if relative != receipt["factory_release_file"]:
        invalid("BAMF_INITIAL_FACTORY_RELEASE_CUSTODY_INVALID")
    _require_release_root_shape(run_dir, expected)
    return receipt


def require_initial_factory_release(run_dir: Path, student):
    """Cold-verify release custody from accepted/sealed student identity only."""
    expected = student.run_identity.factory_release_sha256
    _require_release_root_shape(run_dir, expected)
    receipt = _release_receipt(expected)
    from bilqis_mlx.runtime.admission import _read_executable_factory_release_artifact

    release = _read_executable_factory_release_artifact(Path(run_dir), receipt)
    if release.release_sha256 != expected:
        invalid("BAMF_INITIAL_FACTORY_RELEASE_CUSTODY_INVALID")
    _require_release_root_shape(run_dir, expected)
    return release


__all__ = (
    "persist_prepared_initial_factory_release",
    "require_initial_factory_release",
)
