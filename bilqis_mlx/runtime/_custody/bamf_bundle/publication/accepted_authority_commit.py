"""Publication-time commit of one durable B13 accepted-authority checkpoint."""
from __future__ import annotations

from pathlib import Path

from ..feature.checkpoint_artifact import mint_accepted_feature_artifact_commitment
from ..records import canonical, invalid, sha
from .accepted_authority_checkpoint import (
    compare_and_swap_protected_accepted_authority_tip,
    issue_accepted_authority_checkpoint,
    require_accepted_authority_checkpoint,
    store_accepted_authority_checkpoint,
)
from .genesis_trust import initial_generation_trust_sha256


def _acceptance_file_sha256(run_dir: Path, manifest_sha256: str) -> str:
    path = Path(run_dir) / "bamf-acceptance" / f"{manifest_sha256}.json"
    if path.is_symlink() or not path.is_file():
        invalid("BAMF_GENERATION_ACCEPTANCE_REQUIRED")
    return sha(path.read_bytes())


def _parent_checkpoint(run_dir: Path, current: dict | None, parent):
    if parent is None:
        if current is not None:
            invalid("BAMF_ACCEPTED_AUTHORITY_PARENT_DRIFT")
        return None
    if (current is None
            or current.get("run_id") != parent.run_id
            or current.get("generation") != parent.generation):
        invalid("BAMF_ACCEPTED_AUTHORITY_PARENT_DRIFT")
    return require_accepted_authority_checkpoint(
        parent.run_id, current["manifest_sha256"])


def commit_accepted_authority(
        run_dir: Path, pointer: dict, student, *, current: dict | None, parent=None,
        genesis_features=None, candidate_identity_sha256: str,
        parent_candidate_identity_sha256: str | None = None):
    """Seal current feature bytes, checkpoint them, then CAS the protected tip.

    The filesystem pointer is intentionally *not* installed here.  Callers install
    it only after this transaction returns, so a crash can leave only the bounded
    tip-ahead state recovered by ``accepted_authority_recovery``.
    """
    run_dir = Path(run_dir)
    parent_checkpoint = _parent_checkpoint(run_dir, current, parent)
    feature = mint_accepted_feature_artifact_commitment(
        run_dir, student, pointer, parent=parent,
        parent_checkpoint=parent_checkpoint, genesis_features=genesis_features)
    identity = student.run_identity
    source = student.compiler_features.get("feature_source")
    registry_sha = student.correction_frontier.get("source_authority_registry_sha256")
    if registry_sha is None:
        registry_sha = sha(canonical(None))
    if (identity is None or not isinstance(source, dict)
            or not isinstance(registry_sha, str)):
        invalid("BAMF_ACCEPTED_AUTHORITY_CHECKPOINT_INVALID")
    checkpoint = issue_accepted_authority_checkpoint(
        run_id=student.run_id,
        run_identity_sha256=identity.digest,
        generation=student.generation,
        manifest_sha256=pointer["manifest_sha256"],
        acceptance_sha256=pointer["acceptance_sha256"],
        pointer_sha256=sha(canonical(pointer)),
        acceptance_file_sha256=_acceptance_file_sha256(
            run_dir, pointer["manifest_sha256"]),
        candidate_identity_sha256=candidate_identity_sha256,
        optimizer_step=student.retained_state.optimizer_step,
        topology_sha256=student.topology.digest,
        extents_sha256=student.extents.digest,
        implementation_sha256=student.implementation_sha256,
        feature_receipt_sha256=feature.receipt.digest,
        feature_artifact_sha256=feature.artifact_bundle_id,
        source_authority_registry_sha256=registry_sha,
        semantic_release_sha256=student.provenance.release_digest,
        atlas_bundle_sha256=source.get("atlas_bundle_id"),
        factory_release_sha256=identity.factory_release_sha256,
        genesis_trust_sha256=initial_generation_trust_sha256(student.run_id),
        parent_checkpoint_sha256=(
            None if parent_checkpoint is None else parent_checkpoint.digest),
        parent_manifest_sha256=(
            None if parent_checkpoint is None else parent_checkpoint.manifest_sha256),
        parent_acceptance_sha256=(
            None if parent_checkpoint is None else parent_checkpoint.acceptance_sha256),
        parent_candidate_identity_sha256=(
            None if parent_checkpoint is None else parent_candidate_identity_sha256),
        kind="GENESIS" if student.generation == 0 else "INCREMENTAL",
    )
    store_accepted_authority_checkpoint(checkpoint)
    compare_and_swap_protected_accepted_authority_tip(
        checkpoint,
        expected_checkpoint_sha256=(
            None if parent_checkpoint is None else parent_checkpoint.digest),
    )
    return checkpoint


__all__ = ("commit_accepted_authority",)
