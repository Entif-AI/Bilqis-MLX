"""Strict B13.1 generation records over the integrated B12 retained state."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from bilqis_mlx.data_plane import DataPlaneError
from bilqis_mlx.errors import ErrorBus, SCHOOL

from .motif_codec import snapshot_from_record, snapshot_to_record

BAMF_BUNDLE_SCHEMA = "bilqis.mlx.bamf-generation-bundle/v2"
BAMF_POINTER_SCHEMA = "bilqis.mlx.bamf-generation-pointer/v1"
TRANSITION_SCHEMA = "bilqis.mlx.bamf-generation-transition/v1"
SIDECARS = MappingProxyType({
    "semantic_abi": "semantic-abi.json",
    "motif_allocation": "motif-allocation.json",
    "plasticity_policy": "plasticity-policy.json",
    "compiler_features": "compiler-features.json",
    "correction_frontier": "correction-frontier.json",
    "teacher_state": "teacher-state.json",
    "evaluation_contract": "evaluation-contract.json",
    "outbox": "outbox.json",
})
_TRANSITIONS = frozenset({"INITIAL", "RETAINED_CANDIDATE", "PARAMETER_EXTENSION", "MODEL_SWAP"})


@dataclass(frozen=True)
class BamfBundleCandidate:
    run_id: str
    generation: int
    parent_manifest_sha256: str | None
    implementation_sha256: str
    topology: object
    extents: object
    retained_state: object
    optimizer_hyperparameters: object
    provenance: object
    semantic_abi: Mapping
    compiler_features: Mapping
    correction_frontier: Mapping
    teacher_state: Mapping
    evaluation_contract: Mapping
    transition: Mapping
    outbox: tuple


@dataclass(frozen=True)
class CompleteStudent(BamfBundleCandidate):
    """Cold-loaded immutable v2 generation with exact B12 retained custody."""


@dataclass(frozen=True)
class BamfGenerationManifest:
    run_id: str
    generation: int
    parent_manifest_sha256: str | None
    implementation_sha256: str
    topology: Mapping
    extents: Mapping
    provenance: Mapping
    tensors: Mapping
    optimizer: Mapping
    transition: Mapping
    sidecars: Mapping
    schema: str = BAMF_BUNDLE_SCHEMA

    def __post_init__(self) -> None:
        valid_parent = (self.parent_manifest_sha256 is None if self.generation == 0
                        else _hex(self.parent_manifest_sha256))
        if (not isinstance(self.run_id, str) or not self.run_id
                or type(self.generation) is not int or self.generation < 0
                or not valid_parent or not _hex(self.implementation_sha256)
                or self.schema != BAMF_BUNDLE_SCHEMA
                or any(not isinstance(value, Mapping) for value in (
                    self.topology, self.extents, self.provenance, self.tensors,
                    self.optimizer, self.transition, self.sidecars))):
            invalid()
        validate_transition(self.generation, self.transition)

    def to_record(self) -> dict:
        return {
            "schema": self.schema, "run_id": self.run_id,
            "generation": self.generation,
            "parent_manifest_sha256": self.parent_manifest_sha256,
            "implementation_sha256": self.implementation_sha256,
            "topology": dict(self.topology), "extents": dict(self.extents),
            "provenance": dict(self.provenance), "tensors": dict(self.tensors),
            "optimizer": dict(self.optimizer), "transition": dict(self.transition),
            "sidecars": dict(self.sidecars),
        }

    @classmethod
    def from_record(cls, record: Mapping) -> "BamfGenerationManifest":
        expected = {"schema", "run_id", "generation", "parent_manifest_sha256",
                    "implementation_sha256", "topology", "extents", "provenance",
                    "tensors", "optimizer", "transition", "sidecars"}
        if not isinstance(record, Mapping) or set(record) != expected:
            invalid()
        return cls(*(record[name] for name in (
            "run_id", "generation", "parent_manifest_sha256", "implementation_sha256",
            "topology", "extents", "provenance", "tensors", "optimizer", "transition",
            "sidecars", "schema")))


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hex(value: object) -> bool:
    return (isinstance(value, str) and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


def invalid(code=DataPlaneError.BUNDLE_MANIFEST_INVALID):
    reason = code.value if isinstance(code, DataPlaneError) else str(code)
    ErrorBus.Raise(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def validate_transition(generation: int, transition: Mapping) -> None:
    if (set(transition) != {"schema", "kind", "invalidate_derived_caches"}
            or transition.get("schema") != TRANSITION_SCHEMA
            or transition.get("kind") not in _TRANSITIONS
            or type(transition.get("invalidate_derived_caches")) is not bool
            or (generation == 0) != (transition["kind"] == "INITIAL")
            or (transition["kind"] in {"PARAMETER_EXTENSION", "MODEL_SWAP"}
                and not transition["invalidate_derived_caches"])):
        invalid("BAMF_GENERATION_TRANSITION_INVALID")


def validate_sidecars(extents, provenance, records: Mapping):
    from bilqis_mlx.learning.atlas_engram import INITIAL_MOTIF_CAPACITY
    from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
    if not isinstance(records, Mapping) or set(records) != set(SIDECARS):
        invalid()
    semantic, compiler, correction, teacher = (
        records["semantic_abi"], records["compiler_features"],
        records["correction_frontier"], records["teacher_state"])
    if (any(not isinstance(records[name], Mapping) for name in SIDECARS
            if name not in ("outbox",)) or type(records["outbox"]) not in (list, tuple)):
        invalid()
    try:
        motif = snapshot_from_record(records["motif_allocation"])
        policy = PlasticityPolicy.from_record(records["plasticity_policy"])
    except (TypeError, ValueError, KeyError) as exc:
        invalid("BAMF_SIDECAR_RECORD_INVALID")
    if (semantic.get("active_set_sha256") != extents.active_semantic_digest
            or semantic.get("semantic_bank_count") != extents.semantic_bank_count
            or motif.manifest.digest != extents.motif_key_map_digest
            or motif.manifest.capacity // INITIAL_MOTIF_CAPACITY != extents.motif_page_count
            or compiler.get("factor_map_sha256") != extents.factor_map_digest
            or type(compiler.get("rights_epoch")) is not int
            or type(compiler.get("correction_generation")) is not int
            or correction.get("rights_epoch") != compiler["rights_epoch"]
            or correction.get("correction_generation") != compiler["correction_generation"]
            or correction.get("source_identity") != provenance.source_identity
            or correction.get("release_digest") != provenance.release_digest
            or teacher.get("teacher_identity") != provenance.teacher_identity
            or teacher.get("teacher_epoch") != provenance.teacher_epoch
            or type(teacher.get("next_seed")) is not int or teacher["next_seed"] < 0
            or not _hex(records["evaluation_contract"].get("contract_sha256"))
            or any(row.bank_index >= extents.semantic_bank_count for row in policy.row_ages)):
        invalid()
    return motif, policy


def sidecar_records(candidate: BamfBundleCandidate) -> dict:
    from bilqis_mlx.learning.atlas_candidate import CandidateState
    from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
    from bilqis_mlx.runtime.checkpoint_outbox import ordinary_outbox_lineage, with_delivery_outbox
    from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, GenerationProvenance, ModelTopologySpecV2
    if (type(candidate) not in (BamfBundleCandidate, CompleteStudent)
            or type(candidate.retained_state) is not CandidateState
            or type(candidate.topology) is not ModelTopologySpecV2
            or type(candidate.extents) is not GenerationExtents
            or type(candidate.optimizer_hyperparameters) is not AdamWHyperparameters
            or type(candidate.provenance) is not GenerationProvenance
            or not _hex(candidate.implementation_sha256)):
        invalid()
    candidate.retained_state.__post_init__()
    validate_transition(candidate.generation, candidate.transition)
    lineage = {"run_id": candidate.run_id, "generation": candidate.generation}
    if type(candidate) is CompleteStudent:
        outbox = list(candidate.outbox)
        if not ordinary_outbox_lineage(lineage, outbox):
            invalid("BAMF_OUTBOX_LINEAGE_INVALID")
    else:
        outbox = with_delivery_outbox(lineage, candidate.outbox)["delivery_outbox"]
    records = {
        "semantic_abi": dict(candidate.semantic_abi),
        "motif_allocation": snapshot_to_record(candidate.retained_state.allocations),
        "plasticity_policy": candidate.retained_state.policy.to_record(),
        "compiler_features": dict(candidate.compiler_features),
        "correction_frontier": dict(candidate.correction_frontier),
        "teacher_state": dict(candidate.teacher_state),
        "evaluation_contract": dict(candidate.evaluation_contract),
        "outbox": outbox,
    }
    validate_sidecars(candidate.extents, candidate.provenance, records)
    return records
