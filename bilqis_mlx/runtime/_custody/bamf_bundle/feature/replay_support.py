"""B13 feature replay primitives shared by accepted and candidate custody."""
from __future__ import annotations

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.semantics.atlas_features import FeatureSchema
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactIdentity, AtlasArtifactSelection,
)

from .._vocabulary_admission_records import (
    A02VocabularyStagingReceipt, STAGED_EVENT,
)
from ..records import invalid
from .receipt import is_digest

FEATURE_SOURCE_KEYS = frozenset({
    "atlas_bundle_id", "release_sha256", "source_bundle_id"})
FEATURE_SCHEMA_KEYS = frozenset({"role_ids", "schema_ids", "source_bindings"})
SOURCE_BINDING_WIDTH = 2


def accepted_a02_active_set_extension(child, binding, features) -> bool:
    """Recognize an accepted C07-bound A02 parameter extension during replay."""
    if dict(child.transition) != {
            "schema": "bilqis.mlx.bamf-generation-transition/v1",
            "kind": "PARAMETER_EXTENSION",
            "invalidate_derived_caches": True}:
        return False
    events = tuple(
        event for event in child.outbox
        if isinstance(event, dict) and event.get("event") == STAGED_EVENT)
    if len(events) != 1:
        return False
    record = events[0].get("staging_receipt")
    if not isinstance(record, dict):
        return False
    payload = dict(record)
    receipt_sha256 = payload.pop("receipt_sha256", None)
    try:
        receipt = A02VocabularyStagingReceipt(**payload)
    except (TypeError, BilqisError):
        return False
    return (
        receipt.digest == receipt_sha256
        and getattr(binding, "staging_receipt_sha256", None) == receipt.digest
        and receipt.run_id == child.run_id
        and receipt.generation == child.generation
        and receipt.parent_manifest_sha256 == child.parent_manifest_sha256
        and receipt.candidate_identity_sha256
        == candidate_identity_digest(child.retained_state)
        and receipt.prepared_extents_sha256 == child.extents.digest
        and receipt.active_set_sha256 == child.extents.active_semantic_digest
        and receipt.feature_sha256 == features.digest
        and receipt.semantic_bank_count == child.extents.semantic_bank_count)


def feature_source(compiler_features: dict) -> dict:
    """Read the admitted source release identity recorded with the generation."""
    source = compiler_features.get("feature_source")
    if (not isinstance(source, dict) or set(source) != set(FEATURE_SOURCE_KEYS)
            or any(not is_digest(source[name]) for name in FEATURE_SOURCE_KEYS)):
        invalid("BAMF_FEATURE_SOURCE_BINDING_MISSING")
    return dict(source)


def feature_schema(compiler_features: dict) -> FeatureSchema:
    """Rebuild the recorded feature schema shape without predecessor payload."""
    recorded = compiler_features.get("feature_schema")
    if (not isinstance(recorded, dict)
            or set(recorded) != set(FEATURE_SCHEMA_KEYS)):
        invalid("BAMF_FEATURE_SCHEMA_BINDING_MISSING")
    bindings = recorded["source_bindings"]
    if (not isinstance(recorded["role_ids"], list)
            or not isinstance(recorded["schema_ids"], list)
            or not isinstance(bindings, list)
            or any(not isinstance(row, list) or len(row) != SOURCE_BINDING_WIDTH
                   or not all(isinstance(value, str) and value for value in row)
                   for row in bindings)):
        invalid("BAMF_FEATURE_SCHEMA_BINDING_INVALID")
    try:
        return FeatureSchema(
            role_ids=tuple(recorded["role_ids"]),
            schema_ids=tuple(recorded["schema_ids"]),
            source_bindings=tuple((row[0], row[1]) for row in bindings))
    except BilqisError:
        invalid("BAMF_FEATURE_SCHEMA_BINDING_INVALID")


def feature_schema_from_compiler_features(compiler_features: dict) -> FeatureSchema:
    """Public B13 owner seam for a recorded compiler feature schema."""
    return feature_schema(compiler_features)


def artifact_identity(source: dict) -> AtlasArtifactIdentity:
    return AtlasArtifactIdentity(
        source["atlas_bundle_id"], source["release_sha256"],
        source["source_bundle_id"])


def authenticate_features(
        student, artifact_path: str | None = None, *, predecessor=None,
        resolve_selection, load_snapshot, build_manifest):
    """Replay the admitted source release and rederive the accepted feature map."""
    compiler = student.compiler_features
    if compiler.get("factor_map_sha256") != student.extents.factor_map_digest:
        invalid("BAMF_FEATURE_BINDING_DRIFT")
    source = feature_source(compiler)
    schema = feature_schema(compiler)
    if predecessor is not None:
        schema = FeatureSchema(
            schema.role_ids, schema.schema_ids, predecessor,
            schema.source_bindings)
    identity = artifact_identity(source)
    selection = (resolve_selection(identity)
                 if artifact_path is None else AtlasArtifactSelection(
                     str(artifact_path), identity.bundle_id,
                     identity.release_sha256, identity.source_bundle_id))
    snapshot = load_snapshot(selection)
    if student.extents.active_semantic_digest != snapshot.active_set_sha256:
        invalid("BAMF_FEATURE_ACTIVE_SET_DRIFT")
    try:
        features = build_manifest(snapshot, schema)
    except BilqisError:
        invalid("BAMF_FEATURE_SOURCE_REPLAY_FAILED")
    if features.digest != student.extents.factor_map_digest:
        invalid("BAMF_FEATURE_SOURCE_REPLAY_MISMATCH")
    if (features.semantic_release != source["release_sha256"]
            or features.atlas_bundle_id != source["atlas_bundle_id"]
            or features.source_bundle_id != source["source_bundle_id"]):
        invalid("BAMF_FEATURE_SOURCE_IDENTITY_DRIFT")
    if student.provenance.release_digest != features.semantic_release:
        invalid("BAMF_FEATURE_RELEASE_DRIFT")
    return features
