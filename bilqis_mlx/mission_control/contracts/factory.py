"""Read-only FactoryRelease/curriculum cockpit records for Mission Control."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .model import (
    RecordMeta, WireRecord, is_name, is_names, is_sha256, is_wire_integer, require,
)


class FactorySubjectKind(StrEnum):
    CURRICULUM_CANDIDATE = "CURRICULUM_CANDIDATE"
    FACTORY_RELEASE = "FACTORY_RELEASE"


class FactoryDeliveryStatus(StrEnum):
    NOT_EVIDENCED = "NOT_EVIDENCED"
    IMPLEMENTED = "IMPLEMENTED"
    TURNED_IN = "TURNED_IN"
    INDIVIDUALLY_QUALIFIED = "INDIVIDUALLY_QUALIFIED"
    INTEGRATED = "INTEGRATED"
    LAUNCH_QUALIFIED = "LAUNCH_QUALIFIED"
    BLOCKED = "BLOCKED"
    SUPERSEDED = "SUPERSEDED"


class FactoryLifecycleStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    CURRICULUM_CANDIDATE = "CURRICULUM_CANDIDATE"
    FACTORY_VALIDATED = "FACTORY_VALIDATED"
    QUALIFIED = "QUALIFIED"
    STAGED = "STAGED"
    ADMITTED = "ADMITTED"
    PROMOTED = "PROMOTED"
    DEBT = "DEBT"
    SUPERSEDED = "SUPERSEDED"


class FactoryCurrencyState(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    HISTORICAL = "HISTORICAL"
    UNKNOWN = "UNKNOWN"


class FactoryAdmissionAuthority(StrEnum):
    HUMAN_ONLY = "HUMAN_ONLY"


class FactoryTopologyKnowledge(StrEnum):
    EXACT = "EXACT"
    HISTORICAL_COMPATIBILITY_REQUIRED = "HISTORICAL_COMPATIBILITY_REQUIRED"


@dataclass(frozen=True)
class FactoryBlocker:
    owner_ref: str
    evidence_ref: str
    reason: str

    def __post_init__(self) -> None:
        require(all(is_name(value) for value in (
            self.owner_ref, self.evidence_ref, self.reason)), "FACTORY_BLOCKER")


@dataclass(frozen=True)
class FactoryGradeFrontier:
    grade_id: str
    capability_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        require(is_name(self.grade_id), "FACTORY_GRADE_ID")
        require(is_names(self.capability_ids, allow_empty=False), "FACTORY_GRADE_CAPABILITIES")


@dataclass(frozen=True)
class FactoryTopologyEvidence:
    knowledge: FactoryTopologyKnowledge
    view_schema_version: str
    topology_schema: str | None
    topology_sha256: str | None
    architecture_id: str | None
    layers: int | None
    query_heads: int | None
    kv_heads: int | None
    model_dimension: int | None
    feed_forward_dimension: int | None
    context_length: int | None
    compatibility_ref: str | None

    def __post_init__(self) -> None:
        require(type(self.knowledge) is FactoryTopologyKnowledge, "FACTORY_TOPOLOGY_KNOWLEDGE")
        require(is_name(self.view_schema_version), "FACTORY_TOPOLOGY_VIEW_SCHEMA")
        exact = self.knowledge is FactoryTopologyKnowledge.EXACT
        exact_names = (self.topology_schema, self.architecture_id)
        exact_ints = (
            self.layers, self.query_heads, self.kv_heads, self.model_dimension,
            self.feed_forward_dimension, self.context_length,
        )
        if exact:
            require(all(is_name(item) for item in exact_names), "FACTORY_TOPOLOGY_NAMES")
            require(is_sha256(self.topology_sha256), "FACTORY_TOPOLOGY_DIGEST")
            require(all(is_wire_integer(item) and item > 0 for item in exact_ints),
                    "FACTORY_TOPOLOGY_DIMENSIONS")
            require(self.compatibility_ref is None, "FACTORY_TOPOLOGY_COMPATIBILITY")
        else:
            require(all(item is None for item in (
                *exact_names, self.topology_sha256, *exact_ints,
            )), "FACTORY_TOPOLOGY_HISTORICAL_VALUES")
            require(is_name(self.compatibility_ref), "FACTORY_TOPOLOGY_COMPATIBILITY")


@dataclass(frozen=True)
class FactoryRunLineage:
    run_id: str
    checkpoint_lineage_id: str
    generation: int | None
    generation_manifest_sha256: str
    checkpoint_sha256: str | None
    checkpoint_receipt_sha256: str | None
    topology: FactoryTopologyEvidence

    def __post_init__(self) -> None:
        require(is_name(self.run_id), "FACTORY_LINEAGE_RUN")
        require(is_name(self.checkpoint_lineage_id), "FACTORY_LINEAGE_ID")
        require(self.generation is None or (
            is_wire_integer(self.generation) and self.generation >= 0), "FACTORY_LINEAGE_GENERATION")
        require(is_sha256(self.generation_manifest_sha256), "FACTORY_LINEAGE_MANIFEST")
        require(self.checkpoint_sha256 is None or is_sha256(self.checkpoint_sha256),
                "FACTORY_LINEAGE_CHECKPOINT")
        require(self.checkpoint_receipt_sha256 is None
                or is_sha256(self.checkpoint_receipt_sha256),
                "FACTORY_LINEAGE_CHECKPOINT_RECEIPT")
        require(type(self.topology) is FactoryTopologyEvidence, "FACTORY_LINEAGE_TOPOLOGY")


@dataclass(frozen=True)
class FactoryCockpitSnapshot(WireRecord):
    """One immutable factory/curriculum subject projected for operator inspection."""

    SCHEMA = "bilqis.bamf.mission-control.factory-cockpit-snapshot/v1"
    RUN_BOUND = False

    meta: RecordMeta
    subject_kind: FactorySubjectKind
    subject_sha256: str
    factory_release_sha256: str | None
    candidate_sha256: str | None
    semantic_release_sha256: str
    lifecycle_state: FactoryLifecycleStatus
    delivery_status: FactoryDeliveryStatus
    currency_state: FactoryCurrencyState
    admission_authority: FactoryAdmissionAuthority
    grade_frontier: tuple[FactoryGradeFrontier, ...]
    capability_ids: tuple[str, ...]
    dependency_edges: tuple[tuple[str, str], ...]
    blockers: tuple[FactoryBlocker, ...]
    promoted_capability_ids: tuple[str, ...]
    debt_capability_ids: tuple[str, ...]
    receipt_refs: tuple[str, ...]
    qualification_receipt_sha256: str | None
    admission_receipt_sha256: str | None
    lineage: tuple[FactoryRunLineage, ...]

    def __post_init__(self) -> None:
        super().__post_init__()
        require(type(self.subject_kind) is FactorySubjectKind, "FACTORY_SUBJECT_KIND")
        require(is_sha256(self.subject_sha256), "FACTORY_SUBJECT_DIGEST")
        require(is_sha256(self.semantic_release_sha256), "FACTORY_SEMANTIC_RELEASE")
        require(type(self.lifecycle_state) is FactoryLifecycleStatus, "FACTORY_LIFECYCLE")
        require(type(self.delivery_status) is FactoryDeliveryStatus, "FACTORY_DELIVERY_STATUS")
        require(type(self.currency_state) is FactoryCurrencyState, "FACTORY_CURRENCY")
        require(self.admission_authority is FactoryAdmissionAuthority.HUMAN_ONLY,
                "FACTORY_ADMISSION_AUTHORITY")
        require(self.factory_release_sha256 is None or is_sha256(self.factory_release_sha256),
                "FACTORY_RELEASE_DIGEST")
        require(self.candidate_sha256 is None or is_sha256(self.candidate_sha256),
                "FACTORY_CANDIDATE_DIGEST")
        if self.subject_kind is FactorySubjectKind.FACTORY_RELEASE:
            require(self.factory_release_sha256 == self.subject_sha256
                    and self.candidate_sha256 is None, "FACTORY_RELEASE_IDENTITY")
        else:
            require(self.candidate_sha256 == self.subject_sha256, "FACTORY_CANDIDATE_IDENTITY")
        require(type(self.grade_frontier) is tuple
                and all(type(item) is FactoryGradeFrontier for item in self.grade_frontier),
                "FACTORY_GRADE_FRONTIER")
        grade_ids = tuple(item.grade_id for item in self.grade_frontier)
        require(len(grade_ids) == len(set(grade_ids)), "FACTORY_GRADE_FRONTIER_DUPLICATE")
        require(is_names(self.capability_ids), "FACTORY_CAPABILITIES")
        capability_set = set(self.capability_ids)
        frontier_capabilities = tuple(
            capability for grade in self.grade_frontier for capability in grade.capability_ids)
        require(len(frontier_capabilities) == len(set(frontier_capabilities)),
                "FACTORY_GRADE_CAPABILITY_DUPLICATE")
        require(set(frontier_capabilities) <= capability_set, "FACTORY_GRADE_CAPABILITY_SCOPE")
        require(type(self.dependency_edges) is tuple
                and all(type(edge) is tuple and len(edge) == 2
                        and all(is_name(item) for item in edge)
                        for edge in self.dependency_edges), "FACTORY_DEPENDENCIES")
        require(type(self.blockers) is tuple
                and all(type(item) is FactoryBlocker for item in self.blockers),
                "FACTORY_BLOCKERS")
        require((self.delivery_status is FactoryDeliveryStatus.BLOCKED) == bool(self.blockers),
                "FACTORY_BLOCKER_STATUS")
        require(is_names(self.promoted_capability_ids), "FACTORY_PROMOTED_CAPABILITIES")
        require(is_names(self.debt_capability_ids), "FACTORY_DEBT_CAPABILITIES")
        if capability_set:
            require(set(self.promoted_capability_ids) <= capability_set,
                    "FACTORY_PROMOTION_SCOPE")
            require(set(self.debt_capability_ids) <= capability_set, "FACTORY_DEBT_SCOPE")
        require(is_names(self.receipt_refs), "FACTORY_RECEIPT_REFS")
        require(self.qualification_receipt_sha256 is None
                or is_sha256(self.qualification_receipt_sha256),
                "FACTORY_QUALIFICATION_RECEIPT")
        require(self.admission_receipt_sha256 is None
                or is_sha256(self.admission_receipt_sha256),
                "FACTORY_ADMISSION_RECEIPT")
        require(type(self.lineage) is tuple
                and all(type(item) is FactoryRunLineage for item in self.lineage),
                "FACTORY_LINEAGE")


__all__ = (
    "FactoryAdmissionAuthority", "FactoryBlocker", "FactoryCockpitSnapshot",
    "FactoryCurrencyState", "FactoryDeliveryStatus", "FactoryGradeFrontier",
    "FactoryLifecycleStatus",
    "FactoryRunLineage", "FactorySubjectKind", "FactoryTopologyEvidence",
    "FactoryTopologyKnowledge",
)
