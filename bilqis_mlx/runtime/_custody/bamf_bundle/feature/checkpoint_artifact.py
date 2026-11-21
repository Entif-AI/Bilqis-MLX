"""Durable current-feature commitment owned by accepted B13 authority."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from bilqis_mlx.semantics.atlas.feature_io import persist_feature_manifest
from bilqis_mlx.semantics.atlas.feature_io_storage import load_checkpoint_feature_manifest

from ..records import canonical, invalid
from .receipt import (
    AcceptedFeatureArtifactCommitment, AcceptedGenerationFeatureReceipt,
)


COMMITMENT_DIR = "bamf-feature-commitments"
ARTIFACT_DIR = "bamf-feature-artifacts"


def _commitment_path(run_dir: Path, manifest_sha256: str) -> Path:
    root = Path(run_dir) / COMMITMENT_DIR
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        invalid("BAMF_FEATURE_CHECKPOINT_COMMITMENT_INVALID")
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{manifest_sha256}.json"


def _write_commitment(run_dir: Path, manifest_sha256: str,
                      commitment: AcceptedFeatureArtifactCommitment) -> None:
    path = _commitment_path(run_dir, manifest_sha256)
    raw = canonical(commitment.to_record())
    if path.is_symlink():
        invalid("BAMF_FEATURE_CHECKPOINT_COMMITMENT_INVALID")
    if path.exists():
        if not path.is_file() or path.read_bytes() != raw:
            invalid("BAMF_FEATURE_CHECKPOINT_COMMITMENT_DRIFT")
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".feature-commitment-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_accepted_feature_artifact_commitment(
        run_dir: Path, manifest_sha256: str) -> AcceptedFeatureArtifactCommitment:
    path = _commitment_path(run_dir, manifest_sha256)
    if path.is_symlink() or not path.is_file():
        invalid("BAMF_FEATURE_CHECKPOINT_COMMITMENT_REQUIRED")
    try:
        record = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        invalid("BAMF_FEATURE_CHECKPOINT_COMMITMENT_INVALID")
    if canonical(record) != path.read_bytes():
        invalid("BAMF_FEATURE_CHECKPOINT_COMMITMENT_INVALID")
    return AcceptedFeatureArtifactCommitment.from_record(record)


def _checkpoint_artifact_path(run_dir: Path, bundle_id: str) -> Path:
    return Path(run_dir) / ARTIFACT_DIR / bundle_id


def _parent_features(run_dir: Path, parent_checkpoint):
    commitment = read_accepted_feature_artifact_commitment(
        run_dir, parent_checkpoint.manifest_sha256)
    if (commitment.receipt.digest != parent_checkpoint.feature_receipt_sha256
            or commitment.artifact_bundle_id != parent_checkpoint.feature_artifact_sha256
            or commitment.receipt.generation_manifest_sha256
            != parent_checkpoint.manifest_sha256
            or commitment.receipt.acceptance_sha256
            != parent_checkpoint.acceptance_sha256):
        invalid("BAMF_FEATURE_CHECKPOINT_COMMITMENT_DRIFT")
    features = load_checkpoint_feature_manifest(
        _checkpoint_artifact_path(run_dir, commitment.artifact_bundle_id),
        expected_bundle_id=commitment.artifact_bundle_id,
        expected_feature_digest=commitment.receipt.feature_sha256,
        expected_semantic_release=commitment.receipt.semantic_release,
        expected_source_bundle_id=commitment.receipt.source_source_bundle_id,
        expected_atlas_bundle_id=commitment.receipt.source_atlas_bundle_id,
        expected_predecessor_digest=commitment.artifact_predecessor_digest,
    )
    return commitment, features


def mint_accepted_feature_artifact_commitment(
        run_dir: Path, student, pointer: dict, *, parent=None,
        parent_checkpoint=None, genesis_features=None) -> AcceptedFeatureArtifactCommitment:
    """Validate the direct feature transition once and persist its current artifact."""
    from ..feature_authority import (
        _authenticate_feature_materialization, _feature_schema, _feature_source,
    )

    predecessor = None
    prior_commitment = None
    if student.generation == 0:
        if parent is not None or parent_checkpoint is not None:
            invalid("BAMF_FEATURE_CHECKPOINT_COMMITMENT_DRIFT")
        if genesis_features is None:
            materialization = _authenticate_feature_materialization(student)
            features = materialization.features
        else:
            features = genesis_features
            source = _feature_source(student.compiler_features)
            if (getattr(features, "digest", None) != student.extents.factor_map_digest
                    or features.semantic_release != student.provenance.release_digest
                    or features.atlas_bundle_id != source["atlas_bundle_id"]
                    or features.semantic_release != source["release_sha256"]
                    or features.source_bundle_id != source["source_bundle_id"]
                    or features.predecessor_digest is not None):
                invalid("BAMF_FEATURE_SOURCE_REPLAY_MISMATCH")
    else:
        if parent is None or parent_checkpoint is None:
            invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
        prior_commitment, predecessor = _parent_features(run_dir, parent_checkpoint)
        if (parent.run_id != student.run_id
                or parent.generation + 1 != student.generation
                or student.parent_manifest_sha256 != parent_checkpoint.manifest_sha256
                or predecessor.digest != parent.extents.factor_map_digest):
            invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
        if student.extents.factor_map_digest == predecessor.digest:
            source = _feature_source(student.compiler_features)
            if (student.compiler_features.get("factor_map_sha256") != predecessor.digest
                    or source != _feature_source(parent.compiler_features)
                    or _feature_schema(student.compiler_features)
                    != _feature_schema(parent.compiler_features)
                    or student.provenance.release_digest != predecessor.semantic_release
                    or source["release_sha256"] != predecessor.semantic_release
                    or source["atlas_bundle_id"] != predecessor.atlas_bundle_id
                    or source["source_bundle_id"] != predecessor.source_bundle_id):
                invalid("BAMF_FEATURE_SOURCE_REPLAY_MISMATCH")
            features = predecessor
        else:
            materialization = _authenticate_feature_materialization(
                student, predecessor=predecessor)
            features = materialization.features
            if features.predecessor_digest != predecessor.digest:
                invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")

    receipt = AcceptedGenerationFeatureReceipt(
        run_id=student.run_id,
        generation=student.generation,
        generation_manifest_sha256=pointer["manifest_sha256"],
        parent_generation_manifest_sha256=student.parent_manifest_sha256,
        semantic_release=features.semantic_release,
        active_set_sha256=student.extents.active_semantic_digest,
        feature_sha256=features.digest,
        predecessor_feature_sha256=(None if predecessor is None else predecessor.digest),
        compiler_sha256=student.compiler_features["compiler_sha256"],
        implementation_sha256=student.implementation_sha256,
        acceptance_sha256=pointer["acceptance_sha256"],
        source_atlas_bundle_id=features.atlas_bundle_id,
        source_release_sha256=features.semantic_release,
        source_source_bundle_id=features.source_bundle_id,
    )
    if prior_commitment is not None and features.digest == predecessor.digest:
        artifact_bundle_id = prior_commitment.artifact_bundle_id
    else:
        artifact = persist_feature_manifest(
            features, Path(run_dir) / ARTIFACT_DIR, predecessor=predecessor)
        artifact_bundle_id = artifact.bundle_id
    commitment = AcceptedFeatureArtifactCommitment(
        receipt, artifact_bundle_id, features.predecessor_digest)
    _write_commitment(run_dir, pointer["manifest_sha256"], commitment)
    return commitment


def require_checkpoint_feature_commitment(run_dir: Path, checkpoint):
    """Read the current commitment only after checkpoint authority is established."""
    commitment = read_accepted_feature_artifact_commitment(
        run_dir, checkpoint.manifest_sha256)
    if (commitment.receipt.digest != checkpoint.feature_receipt_sha256
            or commitment.artifact_bundle_id != checkpoint.feature_artifact_sha256
            or commitment.receipt.generation_manifest_sha256 != checkpoint.manifest_sha256
            or commitment.receipt.acceptance_sha256 != checkpoint.acceptance_sha256):
        invalid("BAMF_FEATURE_CHECKPOINT_COMMITMENT_DRIFT")
    return commitment, _checkpoint_artifact_path(run_dir, commitment.artifact_bundle_id)


def persist_audited_feature_commitment(
        run_dir: Path, receipt: AcceptedGenerationFeatureReceipt, features,
        construction_predecessor=None) -> AcceptedFeatureArtifactCommitment:
    """Persist one feature artifact after an explicit historical audit/backfill."""
    artifact = persist_feature_manifest(
        features, Path(run_dir) / ARTIFACT_DIR,
        predecessor=construction_predecessor)
    commitment = AcceptedFeatureArtifactCommitment(
        receipt, artifact.bundle_id, features.predecessor_digest)
    _write_commitment(run_dir, receipt.generation_manifest_sha256, commitment)
    return commitment


__all__ = (
    "mint_accepted_feature_artifact_commitment",
    "persist_audited_feature_commitment",
    "read_accepted_feature_artifact_commitment",
    "require_checkpoint_feature_commitment",
)
