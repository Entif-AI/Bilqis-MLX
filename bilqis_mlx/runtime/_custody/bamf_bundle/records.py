"""Strict B13.1 generation records and cross-owner identity bindings."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping

from bilqis_mlx.data_plane import DataPlaneError

BAMF_BUNDLE_SCHEMA = "bilqis.mlx.bamf-generation-bundle/v2"
BAMF_POINTER_SCHEMA = "bilqis.mlx.bamf-generation-pointer/v1"
SIDECARS = {
    "semantic_abi": "semantic-abi.json",
    "motif_allocation": "motif-allocation.json",
    "plasticity_policy": "plasticity-policy.json",
    "compiler_features": "compiler-features.json",
    "correction_frontier": "correction-frontier.json",
    "teacher_state": "teacher-state.json",
    "evaluation_contract": "evaluation-contract.json",
    "outbox": "outbox.json",
}


@dataclass(frozen=True)
class BamfBundleCandidate:
    generation: int
    topology: object
    extents: object
    optimizer: object
    optimizer_hyperparameters: object
    optimizer_step: int
    provenance: object
    semantic_abi: Mapping
    motif_allocation: Mapping
    plasticity_policy: object
    compiler_features: Mapping
    correction_frontier: Mapping
    teacher_state: Mapping
    evaluation_contract: Mapping
    outbox: tuple


@dataclass(frozen=True)
class CompleteStudent(BamfBundleCandidate):
    """Cold-loaded immutable v2 generation; publication authority lives elsewhere."""


def canonical(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def invalid(code=DataPlaneError.BUNDLE_MANIFEST_INVALID):
    raise ValueError(code.value)


def validate_sidecars(extents, provenance, records: Mapping):
    from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
    if not isinstance(records, Mapping) or set(records) != set(SIDECARS):
        invalid()
    semantic, motif, compiler, correction, teacher = (
        records["semantic_abi"], records["motif_allocation"],
        records["compiler_features"], records["correction_frontier"],
        records["teacher_state"])
    if (any(not isinstance(records[name], Mapping) for name in SIDECARS
            if name not in ("plasticity_policy", "outbox"))
            or not isinstance(records["plasticity_policy"], Mapping)
            or type(records["outbox"]) not in (list, tuple)):
        invalid()
    policy = PlasticityPolicy.from_record(records["plasticity_policy"])
    if (semantic.get("active_set_sha256") != extents.active_semantic_digest
            or semantic.get("semantic_bank_count") != extents.semantic_bank_count
            or motif.get("motif_key_map_sha256") != extents.motif_key_map_digest
            or motif.get("motif_page_count") != extents.motif_page_count
            or compiler.get("factor_map_sha256") != extents.factor_map_digest
            or type(compiler.get("rights_epoch")) is not int
            or type(compiler.get("correction_generation")) is not int
            or correction.get("rights_epoch") != compiler["rights_epoch"]
            or correction.get("correction_generation") != compiler["correction_generation"]
            or teacher.get("teacher_epoch") != provenance.teacher_epoch
            or type(teacher.get("next_seed")) is not int or teacher["next_seed"] < 0
            or any(row.bank_index >= extents.semantic_bank_count for row in policy.row_ages)):
        invalid()
    return policy


def sidecar_records(candidate: BamfBundleCandidate) -> dict:
    from bilqis_mlx.learning.atlas_plasticity import PlasticityPolicy
    from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, AdamWStateTree
    from bilqis_mlx.runtime.model_topology_v2 import (
        GenerationExtents, GenerationProvenance, ModelTopologySpecV2,
    )
    if (type(candidate) not in (BamfBundleCandidate, CompleteStudent)
            or type(candidate.generation) is not int or candidate.generation < 0
            or type(candidate.topology) is not ModelTopologySpecV2
            or type(candidate.extents) is not GenerationExtents
            or type(candidate.optimizer) is not AdamWStateTree
            or type(candidate.optimizer_hyperparameters) is not AdamWHyperparameters
            or type(candidate.optimizer_step) is not int or candidate.optimizer_step < 0
            or type(candidate.provenance) is not GenerationProvenance
            or type(candidate.plasticity_policy) is not PlasticityPolicy):
        invalid()
    candidate.optimizer.validate()
    records = {
        "semantic_abi": dict(candidate.semantic_abi),
        "motif_allocation": dict(candidate.motif_allocation),
        "plasticity_policy": candidate.plasticity_policy.to_record(),
        "compiler_features": dict(candidate.compiler_features),
        "correction_frontier": dict(candidate.correction_frontier),
        "teacher_state": dict(candidate.teacher_state),
        "evaluation_contract": dict(candidate.evaluation_contract),
        "outbox": list(candidate.outbox),
    }
    validate_sidecars(candidate.extents, candidate.provenance, records)
    return records
