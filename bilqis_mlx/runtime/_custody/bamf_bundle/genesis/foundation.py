"""Owner-derived sidecars for a fresh BAMF generation-zero foundation."""
from __future__ import annotations
from dataclasses import dataclass, field

from bilqis_mlx.factory.executable_release import (
    ExecutableAdmissionReceipt, ExecutableFactoryRelease,
)
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas.feature_io_pins import _source_owned_feature_schema
from bilqis_mlx.semantics.atlas_features import AtlasFeatures, FeatureSchema, build_feature_manifest
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot

from ..records import canonical, invalid, sha

_FEATURE_AUTHORITY_ISSUER = object()


@dataclass(frozen=True)
class InitialFoundationFeatureAuthority:
    """Source-replayed A01/A03/A06 feature authority for generation zero."""

    selection: AtlasArtifactSelection
    snapshot: FrozenAtlasSnapshot
    schema: FeatureSchema
    features: AtlasFeatures
    _issuance: object = field(init=False, default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if (getattr(self, "_issuance", None) is not _FEATURE_AUTHORITY_ISSUER
                or type(self.selection) is not AtlasArtifactSelection
                or type(self.snapshot) is not FrozenAtlasSnapshot
                or type(self.schema) is not FeatureSchema
                or type(self.features) is not AtlasFeatures):
            invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")


def issue_initial_foundation_feature_authority(
        selection: AtlasArtifactSelection) -> InitialFoundationFeatureAuthority:
    """Replay source-owned semantic inputs and issue the bounded B13 input."""
    if type(selection) is not AtlasArtifactSelection:
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")
    try:
        snapshot, schema = _source_owned_feature_schema(selection)
        features = build_feature_manifest(snapshot, schema)
    except Exception:
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")
    authority = object.__new__(InitialFoundationFeatureAuthority)
    for name, value in (
            ("selection", selection), ("snapshot", snapshot),
            ("schema", schema), ("features", features),
            ("_issuance", _FEATURE_AUTHORITY_ISSUER)):
        object.__setattr__(authority, name, value)
    authority.__post_init__()
    return authority


def _replay_features(authority) -> InitialFoundationFeatureAuthority:
    if type(authority) is not InitialFoundationFeatureAuthority:
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")
    authority.__post_init__()
    expected = issue_initial_foundation_feature_authority(authority.selection)
    if authority != expected:
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT")
    return expected


def _verified_factory(release, admission, graph) -> None:
    if (type(release) is not ExecutableFactoryRelease
            or type(admission) is not ExecutableAdmissionReceipt
            or not isinstance(graph, dict)):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")
    try:
        release.verify()
        release.verify_semantic_catalog(graph)
        admission.verify(release)
    except (TypeError, ValueError):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")
    if admission.semantic_graph_sha256 != _fingerprint(graph):
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_DRIFT")


def initial_foundation_sidecars(
        release: ExecutableFactoryRelease,
        admission: ExecutableAdmissionReceipt,
        graph: dict, *, run_seed: int,
        feature_authority: InitialFoundationFeatureAuthority,
        ) -> tuple[dict, dict, dict, dict, dict]:
    """Project genesis sidecars only from independently admitted Factory state.

    Generation zero has no accepted correction or C03 visit history yet.  B13
    therefore records the canonical fresh-run baseline instead of accepting a
    caller's JSON description of that baseline.  Later owners may advance these
    records only through accepted successor generations.
    """
    _verified_factory(release, admission, graph)
    if type(run_seed) is not int or run_seed < 0:
        invalid("BAMF_INITIAL_GENERATION_SOURCE_AUTHORITY_INVALID")

    plan = release.execution_plan
    projections = plan.projection_digests
    feature = _replay_features(feature_authority)
    active_banks = tuple(
        entry.bank for entry in feature.snapshot.abi_entries if entry.active)
    bank_count = max(1, max(active_banks, default=0) + 1)
    semantic = {
        "schema": "bilqis.mlx.bamf-semantic-abi/v1",
        "active_set_sha256": feature.snapshot.active_set_sha256,
        "semantic_bank_count": bank_count,
        "bank_identities": [f"bank:{index}" for index in range(bank_count)],
    }
    factor_map_sha256 = feature.features.digest
    compiler = {
        "schema": "bilqis.mlx.bamf-compiler-features/v1",
        "factor_map_sha256": factor_map_sha256,
        "compiler_sha256": sha(canonical({
            "schema": "bilqis.mlx.bamf-initial-compiler/v1",
            "execution_plan_sha256": plan.digest(),
            "factor_map_sha256": factor_map_sha256,
        })),
        "rights_epoch": 0,
        "correction_generation": 0,
        "factory_release_sha256": release.release_sha256,
        "factory_semantic_catalog_sha256": release.semantic_catalog_sha256,
        "factory_grade_ids": [grade.grade_id for grade in plan.grades],
        "feature_source": {
            "atlas_bundle_id": feature.features.atlas_bundle_id,
            "release_sha256": feature.features.semantic_release,
            "source_bundle_id": feature.features.source_bundle_id,
        },
        "feature_schema": {
            "role_ids": list(feature.schema.role_ids),
            "schema_ids": list(feature.schema.schema_ids),
            "source_bindings": [list(item) for item in feature.schema.source_bindings],
        },
    }
    source_identity = (release.source_bindings.source_attestation_sha256
                       or release.source_bindings.digest())
    correction = {
        "schema": "bilqis.mlx.bamf-correction-frontier/v1",
        "source_identity": source_identity,
        "release_digest": feature.features.semantic_release,
        "rights_epoch": 0,
        "correction_generation": 0,
        "frontier": [],
    }
    teacher = {
        "schema": "bilqis.mlx.bamf-teacher-state/v1",
        "teacher_identity": projections.teaching,
        "teacher_epoch": 0,
        "next_seed": run_seed,
        "cursor": "GENESIS",
    }
    evaluation = {
        "schema": "bilqis.mlx.bamf-evaluation-contract/v1",
        "contract_sha256": projections.assessment,
    }
    return semantic, compiler, correction, teacher, evaluation


def initial_foundation_row_ages(
        feature_authority: InitialFoundationFeatureAuthority) -> tuple:
    """Derive fresh FOUNDATION membership from active A01 ABI rows at age zero."""
    from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge

    feature = _replay_features(feature_authority)
    return tuple(
        IdentityRowAge(entry.bank, entry.row, 0)
        for entry in feature.snapshot.abi_entries if entry.active)


__all__ = (
    "InitialFoundationFeatureAuthority", "initial_foundation_sidecars",
    "initial_foundation_row_ages", "issue_initial_foundation_feature_authority",
)
