"""Accepted A02 Registry-mirror readback for navigation/evidence export."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Mapping

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.semantics.atlas.vocabulary_contracts import UINT32_MAX
from bilqis_mlx.semantics.atlas.vocabulary_resources import (
    REGISTRY_DELTA_SCHEMA, RESOURCE_SCHEMA, RegistryMirrorDelta,
    RegistryMirrorRow,
)
from bilqis_mlx.semantics.atlas_projection import BANK_SIZE

from ._vocabulary_admission_records import (
    A02VocabularyStagingReceipt, STAGED_EVENT,
)
from .atlas_admission import ParsedAtlasAdmissionBinding
from .feature.acceptance import accepted_binding_for_manifest, accepted_generation
from .records import canonical, invalid, sha


REGISTRY_EXPORT_SCHEMA = "bilqis.mlx.a02-accepted-registry-mirror-export/v1"
REGISTRY_EXPORT_STATUS = "ACCEPTED_DERIVED_NAVIGATION_EVIDENCE"
_RESOURCE_FIELDS = (
    "previous_bank_count", "next_bank_count", "added_bank_bytes",
    "complete_checkpoint_bytes_lower_bound", "disk_reserve_bytes",
    "extra_planning_bytes", "required_available_bytes_lower_bound",
)


def _hex(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


@dataclass(frozen=True)
class AcceptedVocabularyRegistryExport:
    """Derived accepted Registry view; never semantic or training authority."""

    run_id: str
    generation: int
    manifest_sha256: str
    acceptance_sha256: str
    staging_receipt_sha256: str
    plan_sha256: str
    registry_mirror_sha256: str
    resource_estimate_sha256: str
    semantic_release: str
    source_bundle_id: str
    predecessor_generation_id: str
    allocation_source_digest: str
    active_indices: tuple[int, ...]
    rows: tuple[RegistryMirrorRow, ...]
    previous_bank_count: int
    next_bank_count: int
    added_bank_bytes: int
    complete_checkpoint_bytes_lower_bound: int
    disk_reserve_bytes: int
    extra_planning_bytes: int
    required_available_bytes_lower_bound: int
    semantic_authority: bool = False
    training_authorized: bool = False
    status: str = REGISTRY_EXPORT_STATUS
    schema_version: str = REGISTRY_EXPORT_SCHEMA

    def __post_init__(self) -> None:
        digests = (
            self.manifest_sha256, self.acceptance_sha256,
            self.staging_receipt_sha256, self.plan_sha256,
            self.registry_mirror_sha256, self.resource_estimate_sha256,
            self.semantic_release, self.source_bundle_id,
            self.predecessor_generation_id, self.allocation_source_digest,
        )
        if (not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 1
                or any(not _hex(value) for value in digests)
                or type(self.active_indices) is not tuple
                or self.active_indices != tuple(sorted(set(self.active_indices)))
                or any(type(index) is not int or index < 0 or index > UINT32_MAX
                       for index in self.active_indices)
                or type(self.rows) is not tuple or not self.rows
                or any(type(row) is not RegistryMirrorRow for row in self.rows)
                or any(row.abi_index not in self.active_indices
                       or row.abi_index != BANK_SIZE * row.bank + row.row
                       for row in self.rows)
                or any(type(value) is not int or value < 0 for value in (
                    self.previous_bank_count, self.next_bank_count,
                    self.added_bank_bytes,
                    self.complete_checkpoint_bytes_lower_bound,
                    self.disk_reserve_bytes, self.extra_planning_bytes,
                    self.required_available_bytes_lower_bound))
                or self.previous_bank_count > self.next_bank_count
                or self.required_available_bytes_lower_bound
                != self.complete_checkpoint_bytes_lower_bound
                + self.disk_reserve_bytes + self.extra_planning_bytes
                or self.semantic_authority is not False
                or self.training_authorized is not False
                or self.status != REGISTRY_EXPORT_STATUS
                or self.schema_version != REGISTRY_EXPORT_SCHEMA):
            invalid("BAMF_A02_REGISTRY_EXPORT_INVALID")

    @property
    def digest(self) -> str:
        return sha(canonical(asdict(self)))

    def to_record(self) -> dict:
        return {**asdict(self), "export_sha256": self.digest}


def _mirror_from_record(record: Mapping) -> RegistryMirrorDelta:
    names = {item.name for item in fields(RegistryMirrorDelta)}
    if (not isinstance(record, Mapping) or set(record) != names
            or record.get("schema_version") != REGISTRY_DELTA_SCHEMA
            or not isinstance(record.get("rows"), (list, tuple))
            or not isinstance(record.get("active_indices"), (list, tuple))):
        invalid("BAMF_A02_REGISTRY_EXPORT_INVALID")
    try:
        rows = tuple(RegistryMirrorRow(**dict(row)) for row in record["rows"])
        mirror = RegistryMirrorDelta(
            semantic_release=record["semantic_release"],
            source_bundle_id=record["source_bundle_id"],
            predecessor_generation_id=record["predecessor_generation_id"],
            allocation_source_digest=record["allocation_source_digest"],
            active_indices=tuple(record["active_indices"]),
            rows=rows,
            status=record["status"],
            schema_version=record["schema_version"],
        )
    except (TypeError, KeyError, ValueError):
        invalid("BAMF_A02_REGISTRY_EXPORT_INVALID")
    if (not _hex(mirror.semantic_release)
            or not _hex(mirror.source_bundle_id)
            or not _hex(mirror.predecessor_generation_id)
            or not _hex(mirror.allocation_source_digest)
            or mirror.status != "STAGED_NOT_ADMITTED"
            or not mirror.rows
            or any(not isinstance(row.semantic_id, str) or not row.semantic_id
                   or type(row.abi_index) is not int or row.abi_index < 0
                   or row.abi_index > UINT32_MAX
                   or type(row.bank) is not int or row.bank < 0
                   or type(row.row) is not int or row.row < 0 or row.row >= BANK_SIZE
                   or not isinstance(row.source_status, str) or not row.source_status
                   or not isinstance(row.description, str) or not row.description
                   or not _hex(row.source_record_digest)
                   for row in mirror.rows)):
        invalid("BAMF_A02_REGISTRY_EXPORT_INVALID")
    return mirror


def _resource_requirement(record: Mapping, *, expected_digest: str,
                          expected_bank_count: int) -> dict:
    if (not isinstance(record, Mapping)
            or set(record) != set(_RESOURCE_FIELDS) | {"schema_version"}
            or record.get("schema_version") != RESOURCE_SCHEMA
            or any(type(record.get(name)) is not int or record[name] < 0
                   for name in _RESOURCE_FIELDS)
            or record["previous_bank_count"] > record["next_bank_count"]
            or record["next_bank_count"] != expected_bank_count
            or record["required_available_bytes_lower_bound"]
            != record["complete_checkpoint_bytes_lower_bound"]
            + record["disk_reserve_bytes"] + record["extra_planning_bytes"]
            or sha(canonical(dict(record))) != expected_digest):
        invalid("BAMF_A02_REGISTRY_EXPORT_INVALID")
    return {name: record[name] for name in _RESOURCE_FIELDS}


def read_accepted_vocabulary_registry_export(
        run_dir: Path) -> AcceptedVocabularyRegistryExport:
    """Read one accepted A02 mirror/resource export from immutable B13 custody."""
    run_dir = Path(run_dir)
    pointer, student = accepted_generation(run_dir / "bamf-state.json")
    if student.generation < 1:
        invalid("BAMF_A02_REGISTRY_EXPORT_MISSING")
    binding = accepted_binding_for_manifest(
        run_dir, pointer["manifest_sha256"], student,
        expected_acceptance_sha256=pointer["acceptance_sha256"])
    if not isinstance(binding, ParsedAtlasAdmissionBinding):
        invalid("BAMF_A02_REGISTRY_EXPORT_UNACCEPTED")
    events = tuple(
        event for event in student.outbox
        if isinstance(event, dict) and event.get("event") == STAGED_EVENT)
    if len(events) != 1:
        invalid("BAMF_A02_REGISTRY_EXPORT_MISSING")
    event = events[0]
    receipt = A02VocabularyStagingReceipt.from_record(
        event.get("staging_receipt"))
    plan = event.get("plan")
    if not isinstance(plan, Mapping):
        invalid("BAMF_A02_REGISTRY_EXPORT_INVALID")
    mirror = _mirror_from_record(event.get("registry_mirror"))
    resource = event.get("resource_estimate")
    if (binding.staging_receipt_sha256 != receipt.digest
            or binding.parent_feature_receipt_sha256
            != receipt.parent_feature_receipt_sha256
            or receipt.run_id != student.run_id
            or receipt.generation != student.generation
            or receipt.parent_manifest_sha256 != student.parent_manifest_sha256
            or receipt.candidate_identity_sha256
            != candidate_identity_digest(student.retained_state)
            or receipt.prepared_extents_sha256 != student.extents.digest
            or receipt.active_set_sha256 != student.extents.active_semantic_digest
            or receipt.feature_sha256 != student.extents.factor_map_digest
            or receipt.semantic_bank_count != student.extents.semantic_bank_count
            or sha(canonical(dict(plan))) != receipt.plan_sha256
            or mirror.digest != receipt.registry_mirror_sha256
            or plan.get("parent_generation_id") != receipt.parent_manifest_sha256
            or plan.get("source_allocation_digest")
            != receipt.source_allocation_sha256
            or plan.get("semantic_release") != mirror.semantic_release
            or plan.get("source_bundle_id") != mirror.source_bundle_id
            or plan.get("parent_generation_id") != mirror.predecessor_generation_id
            or plan.get("source_allocation_digest") != mirror.allocation_source_digest
            or tuple(plan.get("active_indices", ())) != mirror.active_indices
            or plan.get("active_semantic_digest") != receipt.active_set_sha256
            or plan.get("bank_count") != receipt.semantic_bank_count):
        invalid("BAMF_A02_REGISTRY_EXPORT_INVALID")
    allocations = tuple(plan.get("allocations", ()))
    if (len(allocations) != len(mirror.rows)
            or any(not isinstance(allocation, Mapping)
                   or (row.semantic_id, row.abi_index, row.bank, row.row,
                       row.source_status)
                   != (allocation.get("semantic_id"), allocation.get("abi_index"),
                       allocation.get("bank"), allocation.get("row"),
                       allocation.get("source_status"))
                   for row, allocation in zip(mirror.rows, allocations))):
        invalid("BAMF_A02_REGISTRY_EXPORT_INVALID")
    resource = _resource_requirement(
        resource, expected_digest=receipt.resource_estimate_sha256,
        expected_bank_count=receipt.semantic_bank_count)
    export = AcceptedVocabularyRegistryExport(
        student.run_id, student.generation, pointer["manifest_sha256"],
        pointer["acceptance_sha256"], receipt.digest, receipt.plan_sha256,
        receipt.registry_mirror_sha256, receipt.resource_estimate_sha256,
        mirror.semantic_release, mirror.source_bundle_id,
        mirror.predecessor_generation_id, mirror.allocation_source_digest,
        mirror.active_indices, mirror.rows,
        resource["previous_bank_count"], resource["next_bank_count"],
        resource["added_bank_bytes"],
        resource["complete_checkpoint_bytes_lower_bound"],
        resource["disk_reserve_bytes"], resource["extra_planning_bytes"],
        resource["required_available_bytes_lower_bound"])
    export.__post_init__()
    return export
