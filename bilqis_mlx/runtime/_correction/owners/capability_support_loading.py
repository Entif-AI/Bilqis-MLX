"""Authenticated accepted-generation loading for C09 capability support."""
from __future__ import annotations

import json
from pathlib import Path

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_acceptance import (
    ACCEPTANCE_SCHEMA, AcceptedCandidateBinding, candidate_identity_digest,
)

from .atlas_requalification_contracts import RequalificationLedger
from .atlas_revalidation_common import _invalid
from .capability_support_materialization import materialized_support


def _accepted_binding(run_dir: Path, manifest_sha256: str):
    from bilqis_mlx.runtime.bamf_bundle.publication import ACCEPTANCE_DIR, _pointer_lock

    run_dir = Path(run_dir)
    with _pointer_lock(run_dir):
        path = run_dir / ACCEPTANCE_DIR / f"{manifest_sha256}.json"
        if path.is_symlink() or not path.is_file():
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_ACCEPTANCE_MISSING")
        try:
            return AcceptedCandidateBinding.from_record(json.loads(path.read_bytes()))
        except (UnicodeDecodeError, json.JSONDecodeError, BilqisError):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_ACCEPTANCE_INVALID")


def _accepted_materialization(
    run_dir: Path, manifest_sha256: str, expected_acceptance_sha256: str | None = None,
):
    from bilqis_mlx.runtime.bamf_bundle.codec import load_bamf_bundle
    from bilqis_mlx.runtime.bamf_bundle.publication import _pointer_lock

    run_dir = Path(run_dir)
    binding = _accepted_binding(run_dir, manifest_sha256)
    with _pointer_lock(run_dir):
        student = load_bamf_bundle(
            run_dir / "bamf-bundles" / manifest_sha256,
            expected_manifest_sha256=manifest_sha256,
        )
        if (binding.schema_version != ACCEPTANCE_SCHEMA
                or (expected_acceptance_sha256 is not None
                    and binding.digest != expected_acceptance_sha256)
                or binding.run_id != student.run_id
                or binding.generation != student.generation
                or binding.feature_sha256 != student.extents.factor_map_digest
                or binding.optimizer_step != student.retained_state.optimizer_step
                or binding.candidate_identity_sha256
                != candidate_identity_digest(student.retained_state)
                or binding.step_proof_sha256 != tuple(
                    proof.digest for proof in student.retained_state.step_proofs)):
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_ACCEPTANCE_DRIFT")
    return binding, student


def _latest_source_qualified_materialization(
    run_dir: Path, current_manifest_sha256: str, capability_id: str,
):
    """Resolve the newest accepted ancestor that actually qualified this capability."""
    from bilqis_mlx.runtime.accepted_correction_ledger import _manifest_lineage

    for manifest_sha256 in reversed(_manifest_lineage(
            Path(run_dir), current_manifest_sha256)):
        binding = _accepted_binding(run_dir, manifest_sha256)
        if (binding.schema_version != ACCEPTANCE_SCHEMA
                or not any(anchor[0] == capability_id
                           for anchor in binding.source_anchors)):
            continue
        binding, student = _accepted_materialization(run_dir, manifest_sha256)
        return manifest_sha256, binding, student
    _invalid("BAMF_C09_CAPABILITY_SUPPORT_SOURCE_MISSING")


def load_current_support(run_dir: Path, capability_id: str):
    from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
    from bilqis_mlx.runtime.bamf_bundle.publication import (
        _live_bundle_manifest, _pointer_lock, _read_pointer,
    )

    run_dir = Path(run_dir)
    with _pointer_lock(run_dir):
        pointer = _read_pointer(run_dir / "bamf-state.json")
        if pointer is None:
            _invalid("BAMF_C09_CAPABILITY_SUPPORT_GENERATION_MISSING")
        manifest_sha256 = pointer["manifest_sha256"]
        _live_bundle_manifest(run_dir, pointer)
    _current_binding, current_student = _accepted_materialization(
        run_dir, manifest_sha256)
    source_manifest_sha256, binding, student = (
        _latest_source_qualified_materialization(
            run_dir, manifest_sha256, capability_id))
    support, node, _source_generation_bindings = materialized_support(
        binding, student, source_manifest_sha256, capability_id)
    current_generation_binding = execution_generation_digest(
        current_student.retained_state.optimizer.parameters,
        spec=current_student.topology,
        extents=current_student.extents,
    )
    return manifest_sha256, support, node, (current_generation_binding,)


def accepted_support_census(
    run_dir: Path, manifest_sha256: str,
) -> tuple[RequalificationLedger, tuple[object, ...]]:
    """Materialize all v3 learned support without registering physical owners."""
    from bilqis_mlx.runtime.accepted_correction_ledger import _manifest_lineage

    materializations = {}
    for lineage_manifest in reversed(_manifest_lineage(run_dir, manifest_sha256)):
        binding = _accepted_binding(run_dir, lineage_manifest)
        if binding.schema_version != ACCEPTANCE_SCHEMA or not binding.source_anchors:
            continue
        binding, student = _accepted_materialization(run_dir, lineage_manifest)
        for capability_id in sorted({anchor[0] for anchor in binding.source_anchors}):
            materializations.setdefault(
                capability_id, (lineage_manifest, binding, student))
    supports = []
    nodes = []
    for capability_id, (source_manifest, binding, student) in sorted(
            materializations.items()):
        support, node, _bindings = materialized_support(
            binding, student, source_manifest, capability_id)
        supports.append(support)
        nodes.append(node)
    return RequalificationLedger(tuple(supports)), tuple(nodes)


__all__ = ("accepted_support_census", "load_current_support")
