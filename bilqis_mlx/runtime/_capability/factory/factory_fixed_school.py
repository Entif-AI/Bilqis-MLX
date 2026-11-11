"""C05-owned immutable fixed-school custody for accepted BAMF lineages."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.runtime.assessment import (
    _draw_executable_scope_cohort,
    _persist_executable_cohort,
)
from bilqis_mlx.runtime.bamf_bundle.admission import (
    bind_accepted_execution_cache,
    load_accepted_generation,
)
from bilqis_mlx.runtime.capability_evaluation import _invalid
from bilqis_mlx.runtime.state import _durable_json

from ._factory_fixed_school_contract import (
    SCHEMA, load_complete_school, load_receipt, pointer, require_receipt,
    require_receipt_root, school_seed, scope,
)
from ._factory_fixed_school_custody import fixed_school_lock, foundation_anchor


def _accepted_parent(source_context, run_dir: Path, expected_parent_manifest_sha256: str):
    source_context.require_accepted_runtime(run_dir)
    parent = load_accepted_generation(run_dir)
    cache = bind_accepted_execution_cache(run_dir)
    custody = parent.retained_state.custody
    if (custody is None or parent.run_id != cache.run_id
            or parent.generation != cache.generation
            or custody.manifest_sha256 != cache.accepted_manifest_sha256
            or cache.accepted_manifest_sha256 != expected_parent_manifest_sha256):
        _invalid("BAMF_C05_FIXED_SCHOOL_ACCEPTED_PARENT_DRIFT")
    return parent, cache


def _cold_school(
        run_dir, receipt_path, source_manifest, source_context, parent,
        capabilities, contract, source_identity, anchor):
    receipt = require_receipt(
        load_receipt(receipt_path), source_context=source_context, parent=parent,
        capabilities=capabilities, contract=contract, source_identity=source_identity)
    if receipt["foundation_parent_manifest_sha256"] != anchor:
        _invalid("BAMF_C05_FIXED_SCHOOL_FOUNDATION_PARENT_INVALID")
    return load_complete_school(
        run_dir, source_manifest, source_context.release, capabilities,
        pointer(receipt))


def _materialize_school(
        run_dir, receipt_path, source_manifest, source_context, parent,
        capabilities, contract, source_identity, anchor):
    identity = parent.run_identity
    seed = school_seed(
        identity, source_context.release, source_identity, capabilities, contract)
    cohort, actual_contract = _draw_executable_scope_cohort(
        source_context.source_root, source_context.graph, source_context.release,
        source_context.source_registry, capabilities=capabilities, seed=seed)
    if actual_contract != contract:
        _invalid("BAMF_C05_FIXED_SCHOOL_SCOPE_DRIFT")
    cohort_pointer = _persist_executable_cohort(
        run_dir, source_manifest, contract, cohort)
    receipt = {
        "schema": SCHEMA,
        "run_id": parent.run_id,
        "run_identity_sha256": identity.digest,
        "foundation_parent_manifest_sha256": anchor,
        "factory_release_sha256": source_context.release.release_sha256,
        "source_identity_sha256": source_identity,
        "semantic_catalog_sha256": source_context.release.semantic_catalog_sha256,
        "capabilities": list(capabilities),
        "rubric_sha256": contract.rubric_sha256,
        "source_sha256": contract.source_sha256,
        "generator_version": contract.generator_version,
        "seed": seed,
        "cohort_sha256": cohort_pointer["cohort_sha256"],
        "cohort_file": cohort_pointer["cohort_file"],
        "cohort_seed": cohort_pointer["cohort_seed"],
    }
    require_receipt(
        receipt, source_context=source_context, parent=parent,
        capabilities=capabilities, contract=contract, source_identity=source_identity)
    _durable_json(receipt_path, receipt)
    return _cold_school(
        run_dir, receipt_path, source_manifest, source_context, parent,
        capabilities, contract, source_identity, anchor)


def _bamf_fixed_school_cohort(
        source_context, run_dir: Path, *, expected_parent_manifest_sha256: str):
    """Create once, then cold-verify one whole-release fixed school per BAMF run."""
    run_dir = Path(run_dir)
    with fixed_school_lock(run_dir):
        parent, cache = _accepted_parent(
            source_context, run_dir, expected_parent_manifest_sha256)
        capabilities, contract, source_identity = scope(source_context, parent)
        root = run_dir / "c05-fixed-school"
        receipt_path = root / f"{parent.run_identity.digest}.json"
        source_manifest = {"manifest_sha256": source_identity}
        require_receipt_root(root, receipt_path)
        exists = receipt_path.exists() or receipt_path.is_symlink()
        anchor = foundation_anchor(
            run_dir, parent, cache, receipt_exists=exists)
        if exists:
            return _cold_school(
                run_dir, receipt_path, source_manifest, source_context, parent,
                capabilities, contract, source_identity, anchor)
        school = _materialize_school(
            run_dir, receipt_path, source_manifest, source_context, parent,
            capabilities, contract, source_identity, anchor)
        require_receipt_root(root, receipt_path)
        return school


__all__ = ()
