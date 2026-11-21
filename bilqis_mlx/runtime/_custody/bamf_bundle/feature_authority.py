"""B13 accepted-generation feature authority.

Publication is not source authority. This owner mints one immutable receipt per
accepted generation and rederives the accepted feature identity from the
admitted source release, so a caller-created candidate can never ratify its own
factor-map digest.
"""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.semantics.atlas_features import build_feature_manifest
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactSelection, load_pinned_atlas_snapshot,
    resolve_atlas_artifact_selection,
)

from .codec import load_bamf_bundle
from .records import BamfBundleCandidate, CompleteStudent, invalid
from .feature.acceptance import (
    accepted_binding_for_manifest, parent_acceptance_anchor_from_manifest,
)
from .feature.context import (
    AcceptedGenerationFeatureContext, AuthenticatedCandidateFeatureContext,
    AuthenticatedGenerationFeatureContext, _issue_candidate_feature_context,
    _issue_generation_feature_context,
)
from .feature.current_authority import (
    AuthenticatedCheckpointFeatureContext,
    authenticate_checkpointed_bamf_generation_feature_context,
)
from .feature.history_replay import (
    read_accepted_generation_feature_materialization as _historical_materialization,
    replay_accepted_feature_context as _historical_feature_context,
)
from .feature.receipt import AcceptedGenerationFeatureReceipt
from .feature.replay_support import (
    artifact_identity as _artifact_identity,
    authenticate_feature_materialization as _authenticate_feature_materialization_with,
    authenticate_features as _authenticate_features_with,
    feature_schema as _feature_schema,
    feature_schema_from_compiler_features,
    feature_source as _feature_source,
)


def _authenticate_features(
        student, artifact_path: str | None = None, *, predecessor=None,
        require_active_set_match: bool = True):
    return _authenticate_features_with(
        student, artifact_path, predecessor=predecessor,
        resolve_selection=resolve_atlas_artifact_selection,
        load_snapshot=load_pinned_atlas_snapshot,
        build_manifest=build_feature_manifest,
        require_active_set_match=require_active_set_match)


def _authenticate_feature_materialization(
        student, artifact_path: str | None = None, *, predecessor=None,
        require_active_set_match: bool = True):
    return _authenticate_feature_materialization_with(
        student, artifact_path, predecessor=predecessor,
        resolve_selection=resolve_atlas_artifact_selection,
        load_snapshot=load_pinned_atlas_snapshot,
        build_manifest=build_feature_manifest,
        require_active_set_match=require_active_set_match)




def _accepted_feature_context(run_dir: Path, manifest_sha256: str, student, *,
                              expected_acceptance_sha256: str):
    """Historical audit/migration oracle for accepted feature ancestry."""
    return _historical_feature_context(
        run_dir, manifest_sha256, student,
        expected_acceptance_sha256=expected_acceptance_sha256,
        authenticate_materialization=_authenticate_feature_materialization,
        load_bundle=load_bamf_bundle,
        accepted_binding=accepted_binding_for_manifest,
        parent_acceptance_anchor=parent_acceptance_anchor_from_manifest)


def _accepted_feature_chain(run_dir: Path, manifest_sha256: str, student, *,
                            expected_acceptance_sha256: str):
    """Return current features plus the immediate parent generation's feature map."""
    features, binding, predecessor, _, _materialization, _count = _accepted_feature_context(
        run_dir, manifest_sha256, student,
        expected_acceptance_sha256=expected_acceptance_sha256)
    return features, binding, predecessor


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
    if type(candidate) is not BamfBundleCandidate:
        invalid("BAMF_FEATURE_CANDIDATE_REQUIRED")
    source = _feature_source(candidate.compiler_features)
    schema = _feature_schema(candidate.compiler_features)
    identity = _artifact_identity(source)
    selection = AtlasArtifactSelection(
        str(artifact_path), identity.bundle_id,
        identity.release_sha256, identity.source_bundle_id)
    snapshot = load_pinned_atlas_snapshot(selection)
    # A02 may stage an append-only identity row into the candidate generation
    # before C07 admits it.  The immutable source snapshot therefore still
    # carries the parent active set while the candidate extents carry the staged
    # generation set.  Candidate feature authentication proves source identity
    # and factor construction only; accepted-generation replay below remains
    # strict about active-set drift and C07 still owns admission.
    features = _authenticate_features(
        candidate, artifact_path, require_active_set_match=False)
    return _issue_candidate_feature_context(selection, snapshot, schema, features)


def authenticate_bamf_generation_feature_context(
        student: CompleteStudent, artifact_path: str | None,
        pointer_path: Path) -> AuthenticatedGenerationFeatureContext:
    """Replay feature inputs for one exact accepted generation through B13 custody."""
    if type(student) is not CompleteStudent or not isinstance(pointer_path, Path):
        invalid("BAMF_ACCEPTED_FEATURE_GENERATION_REQUIRED")
    # Keep B13 feature authority importable on portable/non-MLX hosts. The
    # accepted-runtime owner is needed only when replaying an accepted neural
    # generation, not while importing custody/release contracts.
    from .accepted_runtime import _published_in_memory_identity
    _published_in_memory_identity(pointer_path.parent, student)
    (receipt, features, _predecessor, _construction,
     materialization, materialization_count) = (
        _read_accepted_generation_feature_materialization(pointer_path))
    if (receipt.run_id != student.run_id
            or receipt.generation != student.generation
            or receipt.active_set_sha256 != student.extents.active_semantic_digest
            or receipt.feature_sha256 != student.extents.factor_map_digest):
        invalid("BAMF_ACCEPTED_FEATURE_GENERATION_DRIFT")
    selection = materialization.selection
    if artifact_path is not None:
        source = _feature_source(student.compiler_features)
        identity = _artifact_identity(source)
        selection = AtlasArtifactSelection(
            str(artifact_path), identity.bundle_id,
            identity.release_sha256, identity.source_bundle_id)
    schema = _feature_schema(student.compiler_features)
    snapshot = materialization.snapshot
    if (materialization.schema != schema
            or (snapshot.release_sha256, snapshot.bundle_id, snapshot.source_bundle_id)
            != (selection.release_sha256, selection.bundle_id,
                selection.source_bundle_id)):
        invalid("BAMF_ACCEPTED_FEATURE_GENERATION_DRIFT")
    return _issue_generation_feature_context(
        selection, snapshot, schema, features, receipt,
        construction_predecessor=_construction,
        atlas_reload_count=materialization_count,
        feature_manifest_rebuild_count=materialization_count)


def authenticate_bamf_execution_feature_context(
        candidate: BamfBundleCandidate, artifact_path: str,
        run_dir: Path | None = None):
    """Dispatch feature replay by lifecycle class without collapsing authority."""
    if type(candidate) is CompleteStudent:
        if not isinstance(run_dir, Path):
            invalid("BAMF_ACCEPTED_FEATURE_POINTER_REQUIRED")
        return authenticate_bamf_generation_feature_context(
            candidate, artifact_path, run_dir / "bamf-state.json")
    if type(candidate) is BamfBundleCandidate:
        return authenticate_bamf_candidate_feature_context(candidate, artifact_path)
    invalid("BAMF_FEATURE_CANDIDATE_REQUIRED")


def _read_accepted_generation_feature_materialization(pointer_path: Path):
    """Historical replay used by audit/migration and legacy callers."""
    return _historical_materialization(
        pointer_path,
        authenticate_materialization=_authenticate_feature_materialization,
        load_bundle=load_bamf_bundle,
        accepted_binding=accepted_binding_for_manifest,
        parent_acceptance_anchor=parent_acceptance_anchor_from_manifest)


def _read_accepted_generation_feature_context(pointer_path: Path):
    """Compatibility seam for callers that do not need materialized A01 state."""
    receipt, features, predecessor, construction, _materialization, _count = (
        _read_accepted_generation_feature_materialization(pointer_path))
    return receipt, features, predecessor, construction


def read_accepted_generation_feature_context(
        pointer_path: Path) -> AcceptedGenerationFeatureContext:
    """Replay historical accepted feature construction ancestry."""
    receipt, features, predecessor, construction = (
        _read_accepted_generation_feature_context(pointer_path))
    return AcceptedGenerationFeatureContext(
        receipt, features, predecessor, construction)


def read_accepted_generation_semantic_snapshot(pointer_path: Path):
    """Return the fully authenticated immutable Atlas snapshot for the accepted generation."""
    _receipt, _features, _predecessor, _construction, materialization, _count = (
        _read_accepted_generation_feature_materialization(pointer_path))
    return materialization.snapshot


def read_accepted_generation_feature_lineage(pointer_path: Path):
    """Return the accepted receipt plus current/immediate-parent generation maps."""
    receipt, features, predecessor, _ = _read_accepted_generation_feature_context(
        pointer_path)
    return receipt, features, predecessor


def read_accepted_generation_feature_receipt(
        pointer_path: Path) -> AcceptedGenerationFeatureReceipt:
    """Mint the accepted generation's source-replayed immutable feature receipt."""
    return read_accepted_generation_feature_lineage(pointer_path)[0]


def verify_accepted_generation_feature_receipt(
        pointer_path: Path, receipt: AcceptedGenerationFeatureReceipt
) -> AcceptedGenerationFeatureReceipt:
    """Re-derive the live accepted receipt; a caller record alone is not authority."""
    if type(receipt) is not AcceptedGenerationFeatureReceipt:
        invalid("BAMF_FEATURE_RECEIPT_INVALID")
    expected = read_accepted_generation_feature_receipt(pointer_path)
    if receipt != expected:
        invalid("BAMF_FEATURE_RECEIPT_MISMATCH")
    return expected
