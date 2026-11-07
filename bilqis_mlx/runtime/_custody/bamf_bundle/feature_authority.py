"""B13 accepted-generation feature authority.

Publication is not source authority. This owner mints one immutable receipt per
accepted generation and rederives the accepted feature identity from the
admitted source release, so a caller-created candidate can never ratify its own
factor-map digest.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot

from .codec import load_bamf_bundle
from .publication import _require_published_acceptance
from .records import BamfBundleCandidate, invalid
from ._feature_acceptance import (
    accepted_binding_for_manifest, accepted_generation,
    parent_acceptance_from_manifest,
)
from ._feature_receipt import AcceptedGenerationFeatureReceipt, is_digest

FEATURE_SOURCE_KEYS = frozenset({
    "atlas_bundle_id", "release_sha256", "source_bundle_id"})
FEATURE_SCHEMA_KEYS = frozenset({"role_ids", "schema_ids", "source_bindings"})
SOURCE_BINDING_WIDTH = 2


@dataclass(frozen=True)
class AuthenticatedCandidateFeatureContext:
    """Source-replayed feature inputs for pre-acceptance evaluation only."""

    selection: AtlasArtifactSelection
    snapshot: FrozenAtlasSnapshot
    schema: FeatureSchema
    features: object

    def __post_init__(self) -> None:
        if (type(self.selection) is not AtlasArtifactSelection
                or type(self.snapshot) is not FrozenAtlasSnapshot
                or type(self.schema) is not FeatureSchema
                or self.features.semantic_release != self.selection.release_sha256
                or self.features.atlas_bundle_id != self.selection.bundle_id
                or self.features.source_bundle_id != self.selection.source_bundle_id
                or self.snapshot.release_sha256 != self.selection.release_sha256
                or self.snapshot.bundle_id != self.selection.bundle_id
                or self.snapshot.source_bundle_id != self.selection.source_bundle_id):
            invalid("BAMF_FEATURE_CONTEXT_INVALID")


def _feature_source(compiler_features: dict) -> dict:
    """Read the admitted source release identity recorded with the generation."""
    source = compiler_features.get("feature_source")
    if (not isinstance(source, dict) or set(source) != set(FEATURE_SOURCE_KEYS)
            or any(not is_digest(source[name]) for name in FEATURE_SOURCE_KEYS)):
        invalid("BAMF_FEATURE_SOURCE_BINDING_MISSING")
    return dict(source)


def _feature_schema(compiler_features: dict) -> FeatureSchema:
    """Rebuild the recorded feature schema shape without any predecessor payload."""
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


def _authenticate_features(student, artifact_path: str, *, predecessor=None):
    """Replay the admitted source release and rederive the accepted feature map."""
    compiler = student.compiler_features
    if compiler.get("factor_map_sha256") != student.extents.factor_map_digest:
        invalid("BAMF_FEATURE_BINDING_DRIFT")
    source = _feature_source(compiler)
    schema = _feature_schema(compiler)
    if predecessor is not None:
        schema = FeatureSchema(
            schema.role_ids, schema.schema_ids, predecessor,
            schema.source_bindings)
    selection = AtlasArtifactSelection(
        str(artifact_path), source["atlas_bundle_id"],
        source["release_sha256"], source["source_bundle_id"])
    snapshot = load_pinned_atlas_snapshot(selection)
    try:
        features = build_feature_manifest(snapshot, schema)
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


def _accepted_feature_chain(run_dir: Path, manifest_sha256: str, student,
                            artifact_path: str, *, expected_acceptance_sha256: str):
    """Rebuild feature ancestry only from accepted B13 generation custody."""
    binding = accepted_binding_for_manifest(
        run_dir, manifest_sha256, student,
        expected_acceptance_sha256=expected_acceptance_sha256)
    if student.generation == 0:
        return _authenticate_features(student, artifact_path), binding, None
    parent_sha = student.parent_manifest_sha256
    if parent_sha is None:
        invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
    parent = load_bamf_bundle(
        run_dir / "bamf-bundles" / parent_sha,
        expected_manifest_sha256=parent_sha)
    if parent.run_id != student.run_id or parent.generation + 1 != student.generation:
        invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
    parent_acceptance = parent_acceptance_from_manifest(run_dir, manifest_sha256)
    prior, _, prior_predecessor = _accepted_feature_chain(
        run_dir, parent_sha, parent, artifact_path,
        expected_acceptance_sha256=parent_acceptance)
    if (student.extents.factor_map_digest == parent.extents.factor_map_digest
            and student.compiler_features == parent.compiler_features
            and student.provenance.release_digest == parent.provenance.release_digest):
        return prior, binding, prior
    features = _authenticate_features(student, artifact_path, predecessor=prior)
    if features.predecessor_digest != prior.digest:
        invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
    return features, binding, prior


def authenticate_bamf_candidate_features(
        candidate: BamfBundleCandidate, artifact_path: str):
    """Re-derive a proposed generation's feature map from its recorded source.

    This is deliberately pre-acceptance authority.  It proves only that the
    candidate's recorded feature identity is reproducible from the admitted
    Atlas source; it does not mint acceptance, publication, or live-generation
    authority.
    """
    return authenticate_bamf_candidate_feature_context(
        candidate, artifact_path).features


def authenticate_bamf_candidate_feature_context(
        candidate: BamfBundleCandidate,
        artifact_path: str) -> AuthenticatedCandidateFeatureContext:
    """Return the exact source selection, schema and replayed feature map."""
    if not isinstance(candidate, BamfBundleCandidate):
        invalid("BAMF_FEATURE_CANDIDATE_REQUIRED")
    source = _feature_source(candidate.compiler_features)
    schema = _feature_schema(candidate.compiler_features)
    selection = AtlasArtifactSelection(
        str(artifact_path), source["atlas_bundle_id"],
        source["release_sha256"], source["source_bundle_id"])
    snapshot = load_pinned_atlas_snapshot(selection)
    features = _authenticate_features(candidate, artifact_path)
    context = AuthenticatedCandidateFeatureContext(
        selection, snapshot, schema, features)
    context.__post_init__()
    return context


def read_accepted_generation_feature_lineage(pointer_path: Path, artifact_path: str):
    """Return the accepted receipt plus source-replayed current/predecessor maps."""
    pointer, student = accepted_generation(pointer_path)
    current_binding = _require_published_acceptance(
        pointer_path.parent, pointer, student)
    features, binding, predecessor_features = _accepted_feature_chain(
        pointer_path.parent, pointer["manifest_sha256"], student, artifact_path,
        expected_acceptance_sha256=pointer["acceptance_sha256"])
    if binding != current_binding:
        invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    predecessor = None if predecessor_features is None else predecessor_features.digest
    if student.generation == 0:
        if predecessor is not None or features.predecessor_digest is not None:
            invalid("BAMF_FEATURE_LINEAGE_DRIFT")
    elif predecessor is None:
        invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
    receipt = AcceptedGenerationFeatureReceipt(
        run_id=student.run_id,
        generation=student.generation,
        generation_manifest_sha256=pointer["manifest_sha256"],
        parent_generation_manifest_sha256=student.parent_manifest_sha256,
        semantic_release=features.semantic_release,
        active_set_sha256=student.extents.active_semantic_digest,
        feature_sha256=features.digest,
        predecessor_feature_sha256=predecessor,
        compiler_sha256=student.compiler_features["compiler_sha256"],
        implementation_sha256=student.implementation_sha256,
        acceptance_sha256=binding.digest,
        source_atlas_bundle_id=features.atlas_bundle_id,
        source_release_sha256=features.semantic_release,
        source_source_bundle_id=features.source_bundle_id,
    )
    return receipt, features, predecessor_features


def read_accepted_generation_feature_receipt(
        pointer_path: Path, artifact_path: str) -> AcceptedGenerationFeatureReceipt:
    """Mint the accepted generation's source-replayed immutable feature receipt."""
    return read_accepted_generation_feature_lineage(pointer_path, artifact_path)[0]


def verify_accepted_generation_feature_receipt(
        pointer_path: Path, artifact_path: str,
        receipt: AcceptedGenerationFeatureReceipt) -> AcceptedGenerationFeatureReceipt:
    """Re-derive the live accepted receipt; a caller record alone is not authority."""
    if type(receipt) is not AcceptedGenerationFeatureReceipt:
        invalid("BAMF_FEATURE_RECEIPT_INVALID")
    expected = read_accepted_generation_feature_receipt(pointer_path, artifact_path)
    if receipt != expected:
        invalid("BAMF_FEATURE_RECEIPT_MISMATCH")
    return expected
