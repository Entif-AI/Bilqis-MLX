"""Current accepted feature-context binding under durable B13 checkpoint authority."""
from __future__ import annotations

from pathlib import Path

from .feature.checkpoint_artifact import require_checkpoint_feature_commitment
from .feature_authority import authenticate_checkpointed_bamf_generation_feature_context
from .publication.accepted_authority_checkpoint import require_accepted_authority_checkpoint
from .records import invalid


def bind_checkpoint_feature_context(run_dir: Path, parent, hydration, artifact_path=None):
    """Bind current feature bytes without replaying accepted feature ancestry."""
    if parent is not hydration.student:
        invalid("BAMF_ACCEPTED_FEATURE_CONTEXT_STALE")
    checkpoint = require_accepted_authority_checkpoint(
        parent.run_id, hydration.manifest_sha256)
    commitment, feature_artifact_path = require_checkpoint_feature_commitment(
        Path(run_dir), checkpoint)
    return authenticate_checkpointed_bamf_generation_feature_context(
        parent, artifact_path, feature_artifact_path, commitment)


__all__ = ("bind_checkpoint_feature_context",)
