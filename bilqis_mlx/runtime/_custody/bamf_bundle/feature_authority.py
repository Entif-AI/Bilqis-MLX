"""B13 accepted-generation feature authority.

Publication is not source authority. This owner mints one immutable receipt per
accepted generation and rederives the accepted feature identity from the
admitted source release, so a caller-created candidate can never ratify its own
factor-map digest.
"""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.atlas_features import FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
)

from .codec import load_bamf_bundle
from ._feature_authority_custody import (
    _accepted_binding, _accepted_generation, _binding_for_manifest,
)
from ._feature_authority_records import (
    AcceptedGenerationFeatureReceipt, AuthenticatedCandidateFeatureContext,
    _feature_schema, _feature_source,
)
from .records import invalid
from .records import BamfBundleCandidate


def _authenticate_features(student, artifact_path: str, *, predecessor=None):
    """Replay the admitted source release and rederive the accepted feature map."""
    compiler = student.compiler_features
    if compiler.get("factor_map_sha256") != student.extents.factor_map_digest:
        invalid("BAMF_FEATURE_BINDING_DRIFT")
    source = _feature_source(compiler)
    schema = _feature_schema(compiler)
    if predecessor is not None:
        schema = FeatureSchema(
            role_ids=schema.role_ids,
            schema_ids=schema.schema_ids,
            predecessor=predecessor,
            source_bindings=schema.source_bindings,
        )
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


def _accepted_feature_chain(
        run_dir: Path, manifest_sha256: str, student,
        artifact_path: str):
    """Rebuild an accepted feature map through accepted generation ancestry.

    The predecessor map is never supplied by the caller. It is recursively
    rederived from immutable B13 custody and each generation's persisted
    retention acceptance before the source feature compiler receives it.
    """
    binding = _binding_for_manifest(run_dir, manifest_sha256, student)
    if student.generation == 0:
        return _authenticate_features(student, artifact_path), binding, None
    parent_sha = student.parent_manifest_sha256
    if parent_sha is None:
        invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
    parent = load_bamf_bundle(
        run_dir / "bamf-bundles" / parent_sha,
        expected_manifest_sha256=parent_sha)
    if (parent.run_id != student.run_id
            or parent.generation + 1 != student.generation):
        invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
    predecessor, _, predecessor_parent = _accepted_feature_chain(
        run_dir, parent_sha, parent, artifact_path)
    if (student.extents.factor_map_digest == parent.extents.factor_map_digest
            and student.compiler_features == parent.compiler_features
            and student.provenance.release_digest == parent.provenance.release_digest):
        return predecessor, binding, predecessor_parent
    features = _authenticate_features(
        student, artifact_path, predecessor=predecessor)
    if features.predecessor_digest != predecessor.digest:
        invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
    return features, binding, predecessor


def read_accepted_generation_feature_lineage(
        pointer_path: Path, artifact_path: str):
    """Return the accepted receipt plus source-replayed current/parent features."""
    pointer, student = _accepted_generation(pointer_path)
    binding = _accepted_binding(pointer_path.parent, pointer, student)
    if student.generation == 0:
        features = _authenticate_features(student, artifact_path)
        predecessor = None
    else:
        features, chained_binding, predecessor = _accepted_feature_chain(
            pointer_path.parent, pointer["manifest_sha256"], student,
            artifact_path)
        if chained_binding != binding:
            invalid("BAMF_GENERATION_ACCEPTANCE_DRIFT")
    receipt = _feature_receipt(pointer, student, binding, features)
    return receipt, features, predecessor


def _feature_receipt(pointer, student, binding, features):
    predecessor = features.predecessor_digest
    if student.generation == 0:
        if predecessor is not None:
            invalid("BAMF_FEATURE_LINEAGE_DRIFT")
    elif predecessor is None:
        invalid("BAMF_FEATURE_PREDECESSOR_UNAUTHENTICATED")
    return AcceptedGenerationFeatureReceipt(
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


def read_accepted_generation_feature_receipt(
        pointer_path: Path, artifact_path: str) -> AcceptedGenerationFeatureReceipt:
    """Mint the receipt of the accepted generation from custody and source replay.

    The feature identity is rederived from the admitted source release, never
    taken from a caller candidate. A generation whose recorded feature map is
    not the replayed source map cannot mint a receipt.
    """
    return read_accepted_generation_feature_lineage(
        pointer_path, artifact_path)[0]


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
