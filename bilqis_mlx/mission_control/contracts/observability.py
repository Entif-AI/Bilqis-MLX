"""Semantic, runtime, memory, teacher, generation, and resource read models."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .model import (
    DataValue, RecordMeta, WireRecord, is_name, is_sha256, is_wire_integer, require,
)


class SemanticProjectionState(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    MISSING = "MISSING"
    PARTIAL = "PARTIAL"
    ERROR = "ERROR"


@dataclass(frozen=True)
class SemanticReleaseSnapshot(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.semantic-release-snapshot/v1"
    meta: RecordMeta
    atlas_bundle_id: str
    semantic_release_sha256: str
    source_bundle_id: str
    canonical_rdf_sha256: str
    coverage_sha256: str
    conformance_sha256: str
    source_rows_sha256: str
    active_set_sha256: str
    conformance_status: str
    coverage_status: DataValue
    frontier_debt: DataValue
    source_rows: int
    semantic_concepts: int
    active_abi_indices: int
    source_held: int
    source_ir_only: int
    implementation_uncovered: int

    def __post_init__(self) -> None:
        super().__post_init__()
        require(all(is_sha256(item) for item in (
            self.atlas_bundle_id, self.semantic_release_sha256, self.source_bundle_id,
            self.canonical_rdf_sha256, self.coverage_sha256,
            self.conformance_sha256, self.source_rows_sha256, self.active_set_sha256,
        )), "SEMANTIC_RELEASE_DIGEST")
        require(self.conformance_status == "COMPLETE", "SEMANTIC_RELEASE_CONFORMANCE")
        require(type(self.coverage_status) is DataValue
                and type(self.frontier_debt) is DataValue, "SEMANTIC_RELEASE_COVERAGE")
        require(all(is_wire_integer(item) and item >= 0 for item in (
            self.source_rows, self.semantic_concepts, self.active_abi_indices,
            self.source_held, self.source_ir_only,
            self.implementation_uncovered,
        )), "SEMANTIC_RELEASE_COUNTS")


@dataclass(frozen=True)
class SemanticProjectionSnapshot(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.semantic-projection-snapshot/v1"
    meta: RecordMeta
    state: SemanticProjectionState
    graph: DataValue
    owner: DataValue
    materialization_receipt_sha256: DataValue
    projection_version: DataValue
    coverage_status: DataValue
    canonical_rdf_sha256: DataValue
    semantic_coverage_sha256: DataValue
    importer_implementation_sha256: DataValue
    smoke_suite_sha256: DataValue

    def __post_init__(self) -> None:
        super().__post_init__()
        require(type(self.state) is SemanticProjectionState, "SEMANTIC_PROJECTION_STATE")
        require(all(type(item) is DataValue for item in (
            self.graph, self.owner, self.materialization_receipt_sha256,
            self.projection_version, self.coverage_status, self.canonical_rdf_sha256,
            self.semantic_coverage_sha256, self.importer_implementation_sha256,
            self.smoke_suite_sha256,
        )), "SEMANTIC_PROJECTION_VALUES")


@dataclass(frozen=True)
class SemanticAtlasSnapshot(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.semantic-atlas-snapshot/v1"
    meta: RecordMeta
    atlas_bundle_id: str
    atlas_release_sha256: str
    source_bundle_id: str
    active_concepts: DataValue
    source_eligible: DataValue
    source_held: DataValue

    def __post_init__(self) -> None:
        super().__post_init__()
        require(is_sha256(self.atlas_bundle_id)
                and is_sha256(self.source_bundle_id), "ATLAS_ID")
        require(is_sha256(self.atlas_release_sha256), "ATLAS_RELEASE")
        require(all(type(item) is DataValue for item in (
            self.active_concepts, self.source_eligible, self.source_held)), "ATLAS_VALUES")


@dataclass(frozen=True)
class NeuralRuntimeSample(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.neural-runtime-sample/v1"
    meta: RecordMeta
    optimizer_step: int
    step_duration_ms: DataValue
    active_parameters: DataValue
    refinement_fraction: DataValue

    def __post_init__(self) -> None:
        super().__post_init__()
        require(is_wire_integer(self.optimizer_step) and self.optimizer_step >= 0,
                "RUNTIME_STEP")
        require(all(type(item) is DataValue for item in (
            self.step_duration_ms, self.active_parameters,
            self.refinement_fraction)), "RUNTIME_VALUES")


@dataclass(frozen=True)
class MemorySnapshot(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.memory-snapshot/v1"
    meta: RecordMeta
    used_bytes: DataValue
    budget_bytes: DataValue
    hits: DataValue
    misses: DataValue
    requalifications: DataValue

    def __post_init__(self) -> None:
        super().__post_init__()
        require(all(type(item) is DataValue for item in (
            self.used_bytes, self.budget_bytes, self.hits,
            self.misses, self.requalifications)), "MEMORY_VALUES")


@dataclass(frozen=True)
class TeacherSnapshot(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.teacher-snapshot/v1"
    meta: RecordMeta
    teacher_identity: str
    teacher_epoch: int
    strategy_id: str
    attempts: DataValue
    accepted: DataValue
    rejected: DataValue

    def __post_init__(self) -> None:
        super().__post_init__()
        require(is_name(self.teacher_identity) and is_name(self.strategy_id), "TEACHER_ID")
        require(is_wire_integer(self.teacher_epoch) and self.teacher_epoch >= 0,
                "TEACHER_EPOCH")
        require(all(type(item) is DataValue for item in (
            self.attempts, self.accepted, self.rejected)), "TEACHER_VALUES")


@dataclass(frozen=True)
class GenerationManifest(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.generation-manifest/v1"
    meta: RecordMeta
    checkpoint_sha256: str
    student_sha256: str
    optimizer_state_sha256: str
    parent_manifest_sha256: str | None
    status: str

    def __post_init__(self) -> None:
        super().__post_init__()
        require(all(is_sha256(item) for item in (
            self.checkpoint_sha256, self.student_sha256,
            self.optimizer_state_sha256)), "GENERATION_DIGEST")
        require(self.parent_manifest_sha256 is None
                or is_sha256(self.parent_manifest_sha256), "PARENT_MANIFEST")
        require(is_name(self.status), "GENERATION_STATUS")


@dataclass(frozen=True)
class ResourceSample(WireRecord):
    SCHEMA = "bilqis.bamf.mission-control.resource-sample/v1"
    meta: RecordMeta
    memory_used_bytes: DataValue
    memory_budget_bytes: DataValue
    disk_used_bytes: DataValue
    step_rate_per_minute: DataValue

    def __post_init__(self) -> None:
        super().__post_init__()
        require(all(type(item) is DataValue for item in (
            self.memory_used_bytes, self.memory_budget_bytes,
            self.disk_used_bytes, self.step_rate_per_minute)), "RESOURCE_VALUES")
