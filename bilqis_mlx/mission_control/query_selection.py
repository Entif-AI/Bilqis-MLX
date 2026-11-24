"""CP03 record identity, reference, and current-row selection mechanics."""
from __future__ import annotations

from .contracts.model import WireRecord
from .contracts.dossier import CapabilityDossier
from .contracts.events import LearningHistorySummary
from .contracts.observability import (
    GenerationManifest, GenerationManifestV2, MemorySnapshot, MemorySnapshotV2, NeuralRuntimeSample, ResourceSample,
    SemanticAtlasSnapshot, SemanticProjectionSnapshot, SemanticReleaseSnapshot,
    TeacherSnapshot,
)
from .contracts.snapshots import (
    CapabilitySnapshot, CurriculumFrontier, OperatorView, RunContext, SchoolSnapshot,
)
from .contracts.trainer import TrainerObservation
from .contracts.notifications import Notification
from .query_contracts import QueryFamily, QueryMode, QueryRequest
from .semantic import (
    SemanticBankSnapshot, SemanticConceptSnapshot, SemanticGenerationState,
    SemanticHeldMappingSnapshot, SemanticSimilaritySnapshot,
)


def _forensic_refs(record: WireRecord) -> set[str]:
    refs = {
        record.meta.record_id,
        *record.meta.source_refs,
        *record.meta.evidence_refs,
        *record.meta.receipt_refs,
    }
    for name in (
        "capability_id", "episode_id", "candidate_id", "visit_id", "semantic_id",
        "frame_id", "correction_id", "target_ref", "salience_id", "teacher_identity",
        "strategy_id", "operation_id", "request_id", "request_sha256",
    ):
        value = getattr(record, name, None)
        if isinstance(value, str):
            refs.add(value)
    for name in ("capability_ids", "frame_schema_refs", "source_loci"):
        value = getattr(record, name, ())
        if isinstance(value, tuple):
            refs.update(item for item in value if isinstance(item, str))
    checkpoint = getattr(record, "checkpoint_sha256", None)
    if isinstance(checkpoint, str):
        refs.add(f"checkpoint:{checkpoint}")
        refs.add(checkpoint)
    for name in (
        "student_sha256", "optimizer_state_sha256", "source_frame_sha256",
        "compiled_frame_sha256", "old_digest", "new_digest", "subject_sha256",
        "factory_release_sha256", "candidate_sha256", "semantic_release_sha256",
        "qualification_receipt_sha256", "admission_receipt_sha256",
    ):
        value = getattr(record, name, None)
        if isinstance(value, str):
            refs.add(value)
    for receipt in getattr(record, "receipt_refs", ()):
        if isinstance(receipt, str):
            refs.add(receipt)
    for lineage in getattr(record, "lineage", ()):
        for value in (
            getattr(lineage, "checkpoint_lineage_id", None),
            getattr(lineage, "generation_manifest_sha256", None),
            getattr(lineage, "checkpoint_sha256", None),
            getattr(lineage, "checkpoint_receipt_sha256", None),
        ):
            if isinstance(value, str):
                refs.add(value)
        topology = getattr(lineage, "topology", None)
        for value in (
            getattr(topology, "topology_sha256", None),
            getattr(topology, "compatibility_ref", None),
        ):
            if isinstance(value, str):
                refs.add(value)
    return refs


def record_sort_key(record: WireRecord):
    run = record.meta.run
    return (
        "" if run is None else run.run_id,
        -1 if run is None else run.generation,
        -1 if record.meta.as_of is None else record.meta.as_of,
        record.schema_version,
        record.meta.record_id,
    )


def _freshness_key(record: WireRecord):
    meta = record.meta
    run = meta.run
    return (
        -1 if run is None else run.generation,
        -1 if meta.as_of is None else meta.as_of,
        -1 if meta.observed_at is None else meta.observed_at,
        meta.materialized_at,
        meta.record_id,
    )


def _current_identity(record: WireRecord):
    run = record.meta.run
    if run is None:
        return None
    record_type = TrainerObservation if isinstance(record, TrainerObservation) else type(record)
    base = (run.run_id, record_type)
    if isinstance(record, TrainerObservation):
        return (*base, record.observation_id)
    if type(record) is CapabilitySnapshot:
        return (*base, record.capability_id)
    if type(record) is CapabilityDossier:
        return (*base, record.capability_id)
    if type(record) is SemanticGenerationState:
        return (*base, record.semantic_id)
    if type(record) is SemanticBankSnapshot:
        return (*base, record.bank)
    if type(record) is SemanticSimilaritySnapshot:
        return (*base, record.source_semantic_id, record.target_semantic_id, record.basis_ref)
    if type(record) in {
        RunContext, OperatorView, SchoolSnapshot, CurriculumFrontier,
        GenerationManifest, GenerationManifestV2, SemanticAtlasSnapshot, NeuralRuntimeSample,
        MemorySnapshot, MemorySnapshotV2, TeacherSnapshot, ResourceSample, SemanticReleaseSnapshot,
        SemanticProjectionSnapshot,
    }:
        return base
    if type(record) is SemanticConceptSnapshot:
        return (type(record), record.atlas_release_sha256, record.semantic_id)
    if type(record) is SemanticHeldMappingSnapshot:
        return (type(record), record.atlas_release_sha256, record.domain, record.table, record.key)
    return None


def matches_identity(
        item: WireRecord, request: QueryRequest, *, match_record_id: bool = True) -> bool:
    if isinstance(item, (TrainerObservation, LearningHistorySummary)) and (
            request.mode is not QueryMode.CURRENT or request.generation is not None
            or request.as_of is not None or request.frontier_id is not None):
        return False
    if request.schema_version is not None and item.schema_version != request.schema_version:
        return False
    if request.run_id is not None:
        global_notification = (
            request.family is QueryFamily.NOTIFICATION
            and type(item) is Notification
            and item.meta.run is None
        )
        if (not global_notification
                and (item.meta.run is None or item.meta.run.run_id != request.run_id)):
            return False
    if match_record_id and request.record_id is not None and item.meta.record_id != request.record_id:
        return False
    if request.generation is not None:
        if item.meta.run is None or item.meta.run.generation != request.generation:
            return False
    if request.as_of is not None and item.meta.as_of != request.as_of:
        return False
    if request.frontier_id is not None:
        if type(item) is not CurriculumFrontier or item.frontier_id != request.frontier_id:
            return False
    if (request.family is QueryFamily.RECORD and request.reference is not None
            and request.reference not in _forensic_refs(item)):
        return False
    return True


def select_current(
        rows: list[WireRecord], family: QueryFamily | None = None) -> list[WireRecord]:
    cumulative = family in {QueryFamily.CAPABILITY, QueryFamily.EPISODE}
    generations = {}
    if not cumulative:
        for item in rows:
            run = item.meta.run
            if run is not None and not isinstance(item, TrainerObservation):
                generations[run.run_id] = max(
                    run.generation, generations.get(run.run_id, -1))
        if generations:
            rows = [
                item for item in rows
                if isinstance(item, (TrainerObservation, Notification)) or item.meta.run is None
                or item.meta.run.generation == generations[item.meta.run.run_id]
            ]
    newest = {}
    passthrough = []
    for item in rows:
        identity = _current_identity(item)
        if identity is None:
            passthrough.append(item)
            continue
        incumbent = newest.get(identity)
        if incumbent is None or _freshness_key(item) > _freshness_key(incumbent):
            newest[identity] = item
    return [*passthrough, *newest.values()]


__all__ = ("matches_identity", "record_sort_key", "select_current")
