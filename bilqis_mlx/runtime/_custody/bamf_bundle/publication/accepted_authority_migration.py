"""Explicit one-time migration of legacy accepted BAMF state into durable authority."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile

from ..codec import load_bamf_bundle
from ..feature.checkpoint_artifact import persist_audited_feature_commitment
from ..feature_authority import _read_accepted_generation_feature_materialization
from ..records import canonical, invalid, sha
from .acceptance import require_published_acceptance
from .accepted_authority_checkpoint import (
    compare_and_swap_protected_accepted_authority_tip,
    issue_accepted_authority_checkpoint,
    read_protected_accepted_authority_tip,
    store_accepted_authority_checkpoint,
)
from .genesis_trust import initial_generation_trust_sha256
from .storage import _live_bundle_manifest, _pointer_lock, _pointer_read_lock, _read_pointer


MIGRATION_DIR = "bamf-authority-migrations"


def _persist_audit_receipt(run_dir: Path, record: dict) -> str:
    raw = canonical(record)
    digest = sha(raw)
    root = Path(run_dir) / MIGRATION_DIR
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{digest}.json"
    if path.is_symlink():
        invalid("BAMF_ACCEPTED_AUTHORITY_MIGRATION_INVALID")
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            invalid("BAMF_ACCEPTED_AUTHORITY_MIGRATION_INVALID")
        return digest
    descriptor, temporary = tempfile.mkstemp(prefix=".authority-audit-", dir=root)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return digest


def _backfill_current_accepted_authority_exclusive(run_dir: Path):
    run_dir = Path(run_dir)
    with _pointer_read_lock(run_dir):
        pointer = _read_pointer(run_dir / "bamf-state.json")
        if pointer is None:
            invalid("BAMF_ACCEPTED_AUTHORITY_MIGRATION_REQUIRED")
        existing = read_protected_accepted_authority_tip(pointer["run_id"])
        if existing is not None:
            if existing.manifest_sha256 != pointer["manifest_sha256"]:
                invalid("BAMF_ACCEPTED_AUTHORITY_TIP_DRIFT")
            return existing
        student = load_bamf_bundle(
            run_dir / "bamf-bundles" / pointer["manifest_sha256"],
            expected_manifest_sha256=pointer["manifest_sha256"])
        acceptance = require_published_acceptance(
            run_dir, pointer, student, load_bundle=load_bamf_bundle,
            live_manifest=_live_bundle_manifest)
        (feature_receipt, features, _predecessor, construction_predecessor,
         _materialization, materialization_count) = (
            _read_accepted_generation_feature_materialization(
                run_dir / "bamf-state.json"))
        feature = persist_audited_feature_commitment(
            run_dir, feature_receipt, features, construction_predecessor)
        manifest = _live_bundle_manifest(run_dir, pointer)
        audit_receipt_sha256 = _persist_audit_receipt(run_dir, {
            "schema": "bilqis.mlx.bamf-accepted-authority-backfill/v1",
            "run_id": student.run_id,
            "generation": student.generation,
            "manifest_sha256": pointer["manifest_sha256"],
            "acceptance_sha256": pointer["acceptance_sha256"],
            "feature_receipt_sha256": feature.receipt.digest,
            "historical_feature_materializations": materialization_count,
        })
        identity = student.run_identity
        source = student.compiler_features.get("feature_source")
        registry_sha = student.correction_frontier.get("source_authority_registry_sha256")
        if registry_sha is None:
            registry_sha = sha(canonical(None))
        if identity is None or not isinstance(source, dict):
            invalid("BAMF_ACCEPTED_AUTHORITY_MIGRATION_INVALID")
        checkpoint = issue_accepted_authority_checkpoint(
            run_id=student.run_id, run_identity_sha256=identity.digest,
            generation=student.generation,
            manifest_sha256=pointer["manifest_sha256"],
            acceptance_sha256=pointer["acceptance_sha256"],
            pointer_sha256=sha(canonical(pointer)),
            acceptance_file_sha256=sha((
                run_dir / "bamf-acceptance" /
                f"{pointer['manifest_sha256']}.json").read_bytes()),
            candidate_identity_sha256=acceptance.candidate_identity_sha256,
            optimizer_step=student.retained_state.optimizer_step,
            topology_sha256=student.topology.digest,
            extents_sha256=student.extents.digest,
            implementation_sha256=student.implementation_sha256,
            feature_receipt_sha256=feature.receipt.digest,
            feature_artifact_sha256=feature.artifact_bundle_id,
            source_authority_registry_sha256=registry_sha,
            semantic_release_sha256=student.provenance.release_digest,
            atlas_bundle_sha256=source["atlas_bundle_id"],
            factory_release_sha256=identity.factory_release_sha256,
            genesis_trust_sha256=initial_generation_trust_sha256(student.run_id),
            parent_manifest_sha256=(
                None if student.generation == 0 else student.parent_manifest_sha256),
            parent_acceptance_sha256=(
                None if student.generation == 0 else manifest.get("parent_acceptance_sha256")),
            parent_candidate_identity_sha256=(
                None if student.generation == 0
                else acceptance.parent_candidate_identity_sha256),
            audit_receipt_sha256=audit_receipt_sha256,
            kind="AUDIT_BACKFILL",
        )
    with _pointer_lock(run_dir, create=True):
        current = _read_pointer(run_dir / "bamf-state.json")
        if current != pointer:
            invalid("BAMF_ACCEPTED_AUTHORITY_MIGRATION_RACED")
        existing = read_protected_accepted_authority_tip(pointer["run_id"])
        if existing is not None:
            if existing.manifest_sha256 != pointer["manifest_sha256"]:
                invalid("BAMF_ACCEPTED_AUTHORITY_TIP_DRIFT")
            return existing
        store_accepted_authority_checkpoint(checkpoint)
        compare_and_swap_protected_accepted_authority_tip(
            checkpoint, expected_checkpoint_sha256=None)
        return checkpoint


def backfill_current_accepted_authority(run_dir: Path, *, operator_custody=None):
    """Explicitly audit legacy history once under exclusive operator custody.

    Normal runtime never calls this function. Missing checkpoint authority remains
    a visible migration requirement until an operator invokes this entry point.
    """
    run_dir = Path(run_dir)
    from bilqis_mlx.runtime.bamf_operator.locking import (
        bamf_operator_lock, bamf_operator_lock_covers, bamf_operator_lock_held,
    )

    if operator_custody is not None:
        if not bamf_operator_lock_covers(operator_custody, run_dir):
            invalid("BAMF_ACCEPTED_AUTHORITY_MIGRATION_OPERATOR_CUSTODY_INVALID")
        return _backfill_current_accepted_authority_exclusive(run_dir)
    held = bamf_operator_lock_held(run_dir)
    if held is not False:
        invalid("BAMF_ACCEPTED_AUTHORITY_MIGRATION_OPERATOR_ACTIVE")
    with bamf_operator_lock(run_dir):
        return _backfill_current_accepted_authority_exclusive(run_dir)


__all__ = ("backfill_current_accepted_authority",)
