"""Depth-invariant authentication of the accepted BAMF tip."""
from pathlib import Path

from ..native_contracts import AuthenticatedGeneration, invalid
from ..native_custody import _accepted_generation, accepted_pointer


def authenticated_current_generation(run_dir: Path) -> AuthenticatedGeneration:
    """Authenticate only the accepted tip for latency-sensitive current queries."""
    run_dir = Path(run_dir).expanduser().resolve()
    before = accepted_pointer(run_dir)
    generation = _accepted_generation(
        run_dir, before["manifest_sha256"], before["acceptance_sha256"])
    manifest = generation.manifest
    if (manifest["run_id"] != before["run_id"]
            or manifest["generation"] != before["generation"]):
        invalid("CONTROL_PLANE_NATIVE_HISTORY_LINEAGE_DRIFT")
    after = accepted_pointer(run_dir)
    if after != before:
        invalid("CONTROL_PLANE_NATIVE_HISTORY_POINTER_CHANGED")
    return generation


__all__ = ("authenticated_current_generation",)
