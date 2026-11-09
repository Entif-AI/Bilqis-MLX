"""C16.1b owner adapter for one fresh B13 generation-zero foundation."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.factory.executable_release import (
    SCHEMA as FACTORY_RELEASE_SCHEMA,
    ExecutableFactoryRelease,
)
from bilqis_mlx.learning.atlas_engram import INITIAL_MOTIF_CAPACITY, MotifManifest
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, STATE_SCHEMA
from bilqis_mlx.runtime.bamf_bundle import (
    issue_initial_factory_foundation_authority,
    issue_initial_foundation_feature_authority,
    load_bamf_generation_authority,
    prepare_initial_generation,
    publish_initial_generation,
)
from bilqis_mlx.runtime.bamf_bundle.genesis.foundation import initial_foundation_sidecars
from bilqis_mlx.runtime.bamf_bundle.genesis.records import (
    RUN_IDENTITY_SCHEMA,
    BamfRunIdentity,
)
from bilqis_mlx.runtime.bamf_bundle.records import (
    ACCEPTANCE_BOUND_BAMF_BUNDLE_SCHEMA,
    BAMF_POINTER_SCHEMA,
)
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationProvenance,
    b01_generation_authority,
    b01_generation_extents,
)
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactIdentity,
    resolve_atlas_artifact_selection,
)


BAMF_FOUNDATION_CONFIG_SCHEMA = "bilqis.mlx.bamf-foundation-config/v1"
BAMF_LAUNCH_RECEIPT_SCHEMA = "bilqis.mlx.bamf-launch-receipt/v1"


def _invalid(reason: str) -> None:
    ErrorBus.Raise(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


@dataclass(frozen=True)
class BamfFoundationConfig:
    """Human/operator inputs that B13 rebinds to existing owner authority."""

    source_run_dir: str
    run_id: str
    run_seed: int
    semantic_graph: Mapping
    atlas_artifact: AtlasArtifactIdentity
    optimizer_hyperparameters: AdamWHyperparameters
    schema_version: str = BAMF_FOUNDATION_CONFIG_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != BAMF_FOUNDATION_CONFIG_SCHEMA
                or not isinstance(self.source_run_dir, str) or not self.source_run_dir
                or not isinstance(self.run_id, str) or not self.run_id
                or type(self.run_seed) is not int or self.run_seed < 0
                or not isinstance(self.semantic_graph, Mapping)
                or type(self.atlas_artifact) is not AtlasArtifactIdentity
                or type(self.optimizer_hyperparameters) is not AdamWHyperparameters):
            _invalid("BAMF_FIRST_STUDENT_CONFIG_INVALID")
        self.optimizer_hyperparameters.__post_init__()
        object.__setattr__(
            self, "semantic_graph",
            MappingProxyType(deepcopy(dict(self.semantic_graph))))


@dataclass(frozen=True)
class DashboardMetrics:
    optimizer_step: int
    grade_visits: int
    stage: str
    active_grades: tuple[str, ...]
    current_grade: str
    last_run_status: str


@dataclass(frozen=True)
class LaunchReceipt:
    """Non-authorizing report of the exact generation-zero launch binding."""

    run_identity: BamfRunIdentity
    manifest_sha256: str
    factory_release_sha256: str
    atlas_artifact: AtlasArtifactIdentity
    optimizer_hyperparameters: AdamWHyperparameters
    dashboard_metrics: DashboardMetrics
    input_schema_versions: tuple[tuple[str, str], ...]
    output_schema_versions: tuple[tuple[str, str], ...]
    optional_services_required: tuple[str, ...] = ()
    config_schema_version: str = BAMF_FOUNDATION_CONFIG_SCHEMA
    schema_version: str = BAMF_LAUNCH_RECEIPT_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != BAMF_LAUNCH_RECEIPT_SCHEMA
                or self.config_schema_version != BAMF_FOUNDATION_CONFIG_SCHEMA
                or type(self.run_identity) is not BamfRunIdentity
                or not isinstance(self.manifest_sha256, str)
                or len(self.manifest_sha256) != 64
                or not isinstance(self.factory_release_sha256, str)
                or len(self.factory_release_sha256) != 64
                or type(self.atlas_artifact) is not AtlasArtifactIdentity
                or type(self.optimizer_hyperparameters) is not AdamWHyperparameters
                or type(self.dashboard_metrics) is not DashboardMetrics
                or self.optional_services_required != ()):
            _invalid("BAMF_FIRST_STUDENT_LAUNCH_RECEIPT_INVALID")


def _fresh_run_dir(new_run_dir) -> Path:
    path = Path(new_run_dir).expanduser()
    if (path.is_symlink() or (path.exists() and not path.is_dir())
            or (path.is_dir() and next(path.iterdir(), None) is not None)):
        _invalid("BAMF_FIRST_STUDENT_RUN_DIRECTORY_OCCUPIED")
    return path.resolve()


def _dashboard_metrics(source_run_dir: str) -> DashboardMetrics:
    from bilqis_mlx.presentation.dashboard import _dashboard_state

    _, state, school, active, current_grade = _dashboard_state(Path(source_run_dir))
    if not isinstance(state, dict) or not isinstance(school, dict):
        _invalid("BAMF_FIRST_STUDENT_DASHBOARD_STATE_INVALID")
    current = school.get("current_student")
    if not isinstance(current, dict) or type(current.get("optimizer_step")) is not int:
        _invalid("BAMF_FIRST_STUDENT_DASHBOARD_STATE_INVALID")
    return DashboardMetrics(
        optimizer_step=current["optimizer_step"],
        grade_visits=school.get("visits", 0),
        stage=school.get("stage", "READY_FOR_HUMAN_START"),
        active_grades=tuple(active),
        current_grade=current_grade,
        last_run_status=state.get("result", "NOT_STARTED"),
    )


def _model_authority(release, admission, graph, run_seed, foundation_features,
                     provenance):
    semantic_abi, compiler_features, *_ = initial_foundation_sidecars(
        release, admission, graph, run_seed=run_seed,
        feature_authority=foundation_features)
    allocations = MotifAllocationSnapshot(MotifManifest(provenance.release_digest))
    extents = b01_generation_extents(
        semantic_abi=semantic_abi,
        compiler_features=compiler_features,
        motif_page_count=allocations.manifest.capacity // INITIAL_MOTIF_CAPACITY,
        motif_key_map_digest=allocations.manifest.digest,
    )
    return b01_generation_authority(extents)


def preflight_bamf_foundation(
        config: BamfFoundationConfig,
        admitted_release: ExecutableFactoryRelease,
        new_run_dir) -> LaunchReceipt:
    """Publish one owner-derived generation zero without performing a neural update."""
    if type(config) is not BamfFoundationConfig:
        _invalid("BAMF_FIRST_STUDENT_CONFIG_INVALID")
    config.__post_init__()
    target = _fresh_run_dir(new_run_dir)
    graph = deepcopy(dict(config.semantic_graph))
    factory = issue_initial_factory_foundation_authority(config.source_run_dir, graph)
    if type(admitted_release) is not ExecutableFactoryRelease or admitted_release != factory.release:
        _invalid("BAMF_FIRST_STUDENT_FACTORY_RELEASE_DRIFT")

    selection = resolve_atlas_artifact_selection(config.atlas_artifact)
    features = issue_initial_foundation_feature_authority(selection)
    source_identity = (admitted_release.source_bindings.source_attestation_sha256
                       or admitted_release.source_bindings.digest())
    provenance = GenerationProvenance(
        source_identity, features.features.semantic_release,
        admitted_release.execution_plan.projection_digests.teaching, 0)
    model_authority = _model_authority(
        admitted_release, factory.admission, graph, config.run_seed,
        features, provenance)
    prepared = prepare_initial_generation(
        run_id=config.run_id,
        run_seed=config.run_seed,
        graph=graph,
        factory_authority=factory,
        model_authority=model_authority,
        optimizer_hyperparameters=config.optimizer_hyperparameters,
        provenance=provenance,
        foundation_features=features,
        delivery_events=({
            "event": "BAMF_GENERATION_ACCEPTED",
            "optimizer_step": 0,
        },),
    )
    metrics = _dashboard_metrics(factory.source_run_dir)
    _fresh_run_dir(target)
    pointer = publish_initial_generation(target, prepared)
    student, manifest_sha256 = load_bamf_generation_authority(target / "bamf-state.json")
    if (student.run_identity != prepared.candidate.run_identity
            or student.retained_state.optimizer_step != 0
            or manifest_sha256 != pointer["manifest_sha256"]):
        _invalid("BAMF_FIRST_STUDENT_PERSISTED_FOUNDATION_DRIFT")

    return LaunchReceipt(
        run_identity=student.run_identity,
        manifest_sha256=manifest_sha256,
        factory_release_sha256=admitted_release.release_sha256,
        atlas_artifact=config.atlas_artifact,
        optimizer_hyperparameters=student.optimizer_hyperparameters,
        dashboard_metrics=metrics,
        input_schema_versions=(
            ("config", BAMF_FOUNDATION_CONFIG_SCHEMA),
            ("factory_release", admitted_release.schema),
        ),
        output_schema_versions=(
            ("launch_receipt", BAMF_LAUNCH_RECEIPT_SCHEMA),
            ("run_identity", RUN_IDENTITY_SCHEMA),
            ("optimizer_state", STATE_SCHEMA),
            ("generation_bundle", ACCEPTANCE_BOUND_BAMF_BUNDLE_SCHEMA),
            ("generation_pointer", BAMF_POINTER_SCHEMA),
        ),
    )


__all__ = (
    "BAMF_FOUNDATION_CONFIG_SCHEMA", "BAMF_LAUNCH_RECEIPT_SCHEMA",
    "BamfFoundationConfig", "DashboardMetrics", "LaunchReceipt",
    "preflight_bamf_foundation",
)
