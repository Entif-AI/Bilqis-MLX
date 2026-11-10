"""Immutable first-student launch contracts."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH
from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.bamf_bundle.genesis.records import BamfRunIdentity
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactIdentity

BAMF_FOUNDATION_CONFIG_SCHEMA = "bilqis.mlx.bamf-foundation-config/v1"
BAMF_DASHBOARD_METRICS_SCHEMA = "bilqis.mlx.bamf-launch-dashboard-metrics/v1"
BAMF_LAUNCH_RECEIPT_SCHEMA = "bilqis.mlx.bamf-launch-receipt/v1"


def _invalid(reason: str) -> None:
    ErrorBus.Raise(SCHOOL.BAMF_FIRST_STUDENT.INVALID, reason=reason)


def _sha256(value: object) -> bool:
    return (isinstance(value, str) and len(value) == SHA256_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


def _schema_inventory(value: object) -> bool:
    return (type(value) is tuple and bool(value)
            and all(type(item) is tuple and len(item) == 2
                    and all(type(part) is str and part for part in item)
                    for item in value))


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
    _semantic_graph_sha256: str = field(init=False, repr=False)

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
        graph = deepcopy(dict(self.semantic_graph))
        object.__setattr__(
            self, "semantic_graph", MappingProxyType(graph))
        object.__setattr__(self, "_semantic_graph_sha256", _fingerprint(graph))

    def validate(self) -> None:
        if (not _sha256(self._semantic_graph_sha256)
                or _fingerprint(dict(self.semantic_graph)) != self._semantic_graph_sha256):
            _invalid("BAMF_FIRST_STUDENT_SEMANTIC_GRAPH_DRIFT")
        self.optimizer_hyperparameters.__post_init__()


@dataclass(frozen=True)
class DashboardMetrics:
    optimizer_step: int
    grade_visits: int
    stage: str
    active_grades: tuple[str, ...]
    current_grade: str
    last_run_status: str
    schema_version: str = BAMF_DASHBOARD_METRICS_SCHEMA

    def __post_init__(self) -> None:
        if (self.schema_version != BAMF_DASHBOARD_METRICS_SCHEMA
                or self.optimizer_step != 0 or self.grade_visits != 0
                or self.stage != "READY_FOR_HUMAN_START"
                or type(self.active_grades) is not tuple or not self.active_grades
                or any(type(grade) is not str or not grade for grade in self.active_grades)
                or self.current_grade != self.active_grades[0]
                or self.last_run_status != "NOT_STARTED"):
            _invalid("BAMF_FIRST_STUDENT_DASHBOARD_METRICS_INVALID")


@dataclass(frozen=True)
class BamfFoundationDashboardProjection:
    """Read-only generation-zero facts projected from accepted B13 custody."""

    factory_release_sha256: str
    optimizer_step: int
    grade_visits: int
    teacher_events: int
    stage: str
    active_grades: tuple[str, ...]
    current_grade: str
    last_run_status: str

    def __post_init__(self) -> None:
        if (not _sha256(self.factory_release_sha256)
                or self.optimizer_step != 0
                or self.grade_visits != 0
                or self.teacher_events != 0
                or self.stage != "READY_FOR_HUMAN_START"
                or type(self.active_grades) is not tuple or not self.active_grades
                or len(set(self.active_grades)) != len(self.active_grades)
                or any(type(grade) is not str or not grade for grade in self.active_grades)
                or self.current_grade != self.active_grades[0]
                or self.last_run_status != "NOT_STARTED"):
            _invalid("BAMF_FIRST_STUDENT_DASHBOARD_PROJECTION_INVALID")


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
                or not _sha256(self.manifest_sha256)
                or not _sha256(self.factory_release_sha256)
                or type(self.atlas_artifact) is not AtlasArtifactIdentity
                or type(self.optimizer_hyperparameters) is not AdamWHyperparameters
                or type(self.dashboard_metrics) is not DashboardMetrics
                or not _schema_inventory(self.input_schema_versions)
                or not _schema_inventory(self.output_schema_versions)
                or self.optional_services_required != ()):
            _invalid("BAMF_FIRST_STUDENT_LAUNCH_RECEIPT_INVALID")


