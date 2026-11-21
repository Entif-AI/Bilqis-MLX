"""Checkpoint-authorized current accepted feature authority."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from bilqis_mlx.semantics.atlas.feature_io_storage import (
    load_checkpoint_feature_manifest,
)
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
    resolve_atlas_artifact_selection,
)
from bilqis_mlx.semantics.atlas_features import FeatureSchema
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot

from ..records import CompleteStudent, invalid
from .context_validation import validate_materialized_feature_context
from .receipt import AcceptedFeatureArtifactCommitment
from .replay_support import artifact_identity, feature_schema, feature_source


_CURRENT_FEATURE_CONTEXT_ISSUER = object()


@dataclass(frozen=True, init=False)
class AuthenticatedCheckpointFeatureContext:
    """Current accepted feature bytes authenticated from a durable checkpoint."""

    selection: AtlasArtifactSelection
    snapshot: FrozenAtlasSnapshot
    schema: FeatureSchema
    features: object
    commitment: AcceptedFeatureArtifactCommitment
    feature_artifact_path: str
    atlas_reload_count: int
    feature_manifest_rebuild_count: int
    _issuance: object = field(repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        invalid("BAMF_CHECKPOINT_FEATURE_CONTEXT_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self) -> None:
        if self._issuance is not _CURRENT_FEATURE_CONTEXT_ISSUER:
            invalid("BAMF_CHECKPOINT_FEATURE_CONTEXT_INVALID")
        validate_materialized_feature_context(
            self.selection, self.snapshot, self.schema, self.features)
        if type(self.commitment) is not AcceptedFeatureArtifactCommitment:
            invalid("BAMF_CHECKPOINT_FEATURE_CONTEXT_INVALID")
        receipt = self.commitment.receipt
        if (receipt.feature_sha256 != self.features.digest
                or receipt.semantic_release != self.features.semantic_release
                or not isinstance(self.feature_artifact_path, str)
                or not self.feature_artifact_path
                or type(self.atlas_reload_count) is not int
                or self.atlas_reload_count != 1
                or type(self.feature_manifest_rebuild_count) is not int
                or self.feature_manifest_rebuild_count != 0):
            invalid("BAMF_CHECKPOINT_FEATURE_CONTEXT_INVALID")


def _issue_checkpoint_feature_context(
        selection, snapshot, schema, features, commitment, feature_artifact_path
) -> AuthenticatedCheckpointFeatureContext:
    context = object.__new__(AuthenticatedCheckpointFeatureContext)
    for name, value in (
            ("selection", selection), ("snapshot", snapshot), ("schema", schema),
            ("features", features), ("commitment", commitment),
            ("feature_artifact_path", str(feature_artifact_path)),
            ("atlas_reload_count", 1), ("feature_manifest_rebuild_count", 0),
            ("_issuance", _CURRENT_FEATURE_CONTEXT_ISSUER)):
        object.__setattr__(context, name, value)
    context.__post_init__()
    return context


def authenticate_checkpointed_bamf_generation_feature_context(
        student: CompleteStudent, artifact_path: str | None,
        feature_artifact_path: str | Path,
        commitment: AcceptedFeatureArtifactCommitment,
) -> AuthenticatedCheckpointFeatureContext:
    """Authenticate current immutable feature bytes from accepted checkpoint state."""
    if (type(student) is not CompleteStudent
            or type(commitment) is not AcceptedFeatureArtifactCommitment
            or not isinstance(feature_artifact_path, (str, Path))):
        invalid("BAMF_CHECKPOINT_FEATURE_AUTHORITY_REQUIRED")
    receipt = commitment.receipt
    compiler = student.compiler_features
    source = feature_source(compiler)
    if (receipt.run_id != student.run_id
            or receipt.generation != student.generation
            or receipt.parent_generation_manifest_sha256
            != student.parent_manifest_sha256
            or receipt.semantic_release != student.provenance.release_digest
            or receipt.source_release_sha256 != receipt.semantic_release
            or receipt.active_set_sha256 != student.extents.active_semantic_digest
            or receipt.feature_sha256 != student.extents.factor_map_digest
            or compiler.get("factor_map_sha256") != receipt.feature_sha256
            or receipt.compiler_sha256 != compiler.get("compiler_sha256")
            or receipt.implementation_sha256 != student.implementation_sha256
            or receipt.source_atlas_bundle_id != source["atlas_bundle_id"]
            or receipt.source_release_sha256 != source["release_sha256"]
            or receipt.source_source_bundle_id != source["source_bundle_id"]):
        invalid("BAMF_CHECKPOINT_FEATURE_BINDING_DRIFT")

    schema = feature_schema(compiler)
    identity = artifact_identity(source)
    selection = (resolve_atlas_artifact_selection(identity)
                 if artifact_path is None else AtlasArtifactSelection(
                     str(artifact_path), identity.bundle_id,
                     identity.release_sha256, identity.source_bundle_id))
    snapshot = load_pinned_atlas_snapshot(selection)
    if snapshot.active_set_sha256 != receipt.active_set_sha256:
        invalid("BAMF_CHECKPOINT_FEATURE_ACTIVE_SET_DRIFT")
    features = load_checkpoint_feature_manifest(
        feature_artifact_path,
        expected_bundle_id=commitment.artifact_bundle_id,
        expected_feature_digest=receipt.feature_sha256,
        expected_semantic_release=receipt.semantic_release,
        expected_source_bundle_id=receipt.source_source_bundle_id,
        expected_atlas_bundle_id=receipt.source_atlas_bundle_id,
        expected_predecessor_digest=commitment.artifact_predecessor_digest,
    )
    return _issue_checkpoint_feature_context(
        selection, snapshot, schema, features, commitment,
        str(feature_artifact_path))
