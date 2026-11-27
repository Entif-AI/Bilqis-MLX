"""Shared helpers for the target-first FOUNDATION retention screen."""
import time

from bilqis_mlx.runtime._factory_retention_support import (
    C05_PROBE_EACH,
    C05_PROTECTED_REFERENCE_LOSS,
    _instruments,
)
from bilqis_mlx.runtime.baseline.currentness import (
    BaselineComparisonEpoch,
    BaselineCoverage,
)
from bilqis_mlx.runtime.capability_evaluation import _invalid
from bilqis_mlx.runtime.capability_retention import case_census_digest
from bilqis_mlx.runtime.capability_retention_foundation import (
    FoundationRetentionPolicy,
    mastery_debt_utility_margin_units,
)
from bilqis_mlx.semantics.domains import contract_digest


def observe(observer, **fields):
    if observer is None:
        return
    try:
        observer(fields)
    except Exception:
        # Retention profiling is observational and cannot gate C05 authority.
        pass


def elapsed(observer, field, started):
    if observer is None or started is None:
        return
    observe(observer, **{field: max(0.0, time.perf_counter() - started)})


def solver_profile(observer, prefix, *solvers):
    shared = scalar = rows = padded = attention = 0
    largest_rows = largest_positions = 0
    for solver in solvers:
        telemetry_for = getattr(solver, "telemetry_for", None)
        if not callable(telemetry_for):
            continue
        try:
            telemetry = telemetry_for()
        except Exception:
            continue
        if not isinstance(telemetry, dict):
            continue
        shared += int(telemetry.get("shared_backbone_launches", 0) or 0)
        scalar += int(telemetry.get("scalar_neural_launches", 0) or 0)
        rows += int(telemetry.get("shared_backbone_rows", 0) or 0)
        padded += int(telemetry.get("shared_backbone_padded_positions", 0) or 0)
        attention += int(telemetry.get("shared_backbone_attention_cells", 0) or 0)
        largest_rows = max(
            largest_rows, int(telemetry.get("largest_shared_rows", 0) or 0))
        largest_positions = max(
            largest_positions, int(telemetry.get("largest_shared_positions", 0) or 0))
    observe(
        observer,
        **{f"{prefix}_shared_backbone_launches": shared,
           f"{prefix}_shared_backbone_rows": rows,
           f"{prefix}_shared_backbone_padded_positions": padded,
           f"{prefix}_shared_backbone_attention_cells": attention,
           f"{prefix}_largest_shared_rows": largest_rows,
           f"{prefix}_largest_shared_positions": largest_positions,
           f"{prefix}_scalar_neural_launches": scalar},
    )


def comparison_epoch(release, plan, target_plan, cases, parent, cache):
    target_cases = tuple(
        case for case in cases
        if case.capability_id == target_plan.target_capability_id)
    if not target_cases:
        _invalid("BAMF_C05_RETENTION_PROTECTION_SCOPE_INVALID")
    return BaselineComparisonEpoch(
        release.release_sha256,
        release.semantic_catalog_sha256,
        plan.rubric_sha256,
        target_plan.comparison_scope_sha256,
        plan.policy_epoch_sha256,
        plan.source_sha256,
        cache.source_authority_registry_sha256,
        contract_digest(parent.correction_frontier),
        contract_digest(parent.evaluation_contract),
        case_census_digest(target_cases),
        plan.evidence_stage,
    )


def split_cached_rows(cached_rows, target_plan):
    by_capability = {capability: (seed, rows)
                     for capability, seed, rows in cached_rows}
    if (set(by_capability) != set(target_plan.evaluated_capability_ids)
            or len(by_capability) != len(cached_rows)):
        _invalid("BAMF_C05_RETENTION_SOURCE_CACHE_INVALID")
    target = target_plan.target_capability_id
    return by_capability[target], tuple(
        (capability, *by_capability[capability])
        for capability in target_plan.protected_capability_ids)


def cached_instruments(
        source_context, candidate_bundle, artifact_path, cached_rows, *,
        authenticated=None):
    result = []
    for _capability, seed, rows in cached_rows:
        result.extend(_instruments(
            source_context, candidate_bundle, artifact_path, rows,
            seed=seed, release_prevalidated=True, authenticated=authenticated))
    return tuple(result)


def foundation_policy(
        groups, protected, cases, coverage, mastery_debt_min_utility):
    return FoundationRetentionPolicy(
        groups,
        tuple(dict.fromkeys(group for _capability, group in groups)),
        tuple((capability, C05_PROTECTED_REFERENCE_LOSS) for capability in protected),
        C05_PROBE_EACH, case_census_digest(cases), coverage,
        mastery_debt_min_utility_units=mastery_debt_utility_margin_units(
            mastery_debt_min_utility))


def local_coverage(target_coverage, target_plan, plan_sha256):
    measured = set(target_plan.protected_capability_ids)
    if target_plan.target_capability_id in set(target_coverage.measured_capabilities):
        measured.add(target_plan.target_capability_id)
    groups = target_plan.evaluated_capability_groups
    capabilities = tuple(capability for capability, _group in groups)
    measured_ordered = tuple(capability for capability in capabilities
                             if capability in measured)
    measured_set = set(measured_ordered)
    unmeasured = tuple(capability for capability in capabilities
                       if capability not in measured_set)
    group_names = tuple(dict.fromkeys(group for _capability, group in groups))
    return BaselineCoverage(
        measured_ordered, unmeasured,
        tuple((
            group,
            sum(capability in measured_set for capability, member in groups
                if member == group),
            sum(member == group for _capability, member in groups),
        ) for group in group_names),
        len(measured_ordered), len(capabilities),
        contract_digest({
            "schema": "bilqis.mlx.c05-local-baseline-coverage/v1",
            "target_epoch_sha256": target_coverage.epoch_sha256,
            "retention_protection_plan_sha256": plan_sha256,
            "evaluated_capability_ids": capabilities,
        }))
