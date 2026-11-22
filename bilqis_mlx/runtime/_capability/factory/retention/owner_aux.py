"""Less-frequent C05 owner routes kept behind the public retention facade."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.learning.atlas_package_import import PackageImportTransaction
from bilqis_mlx.runtime.capability_retention import EvidenceKind, EvidenceStage
from bilqis_mlx.runtime.retention.protection_plan import BroadCertificationTrigger


def _owner():
    import bilqis_mlx.runtime.factory_retention_owner as owner
    return owner


def measure_factory_foundation_progress(
    source_context, artifact_path: str, *, run_dir: Path,
):
    """Measure the accepted parent on C05's immutable whole-school fixture."""
    owner = _owner()
    if not isinstance(run_dir, Path):
        owner._invalid("BAMF_C05_FACTORY_OWNER_INPUT_INVALID")
    from bilqis_mlx.runtime.source_execution import SourceExecutionContext
    if type(source_context) is not SourceExecutionContext:
        owner._invalid("BAMF_C05_FACTORY_OWNER_INPUT_INVALID")
    source_context.require_accepted_runtime(run_dir)
    parent = owner.load_accepted_generation(run_dir)
    cache = owner.bind_accepted_execution_cache(run_dir)
    release = source_context.release
    fixed = owner._fixed_school_instruments(
        source_context, parent, artifact_path, run_dir, release,
        parent=parent, cache=cache)
    cases = tuple(item.case for item in fixed)
    measured = {case.capability_id for case in cases}
    groups = tuple(
        (item.capability_id, item.grade_id)
        for item in release.execution_plan.capabilities
        if item.capability_id in measured)
    policy = owner.FoundationRetentionPolicy(
        groups, tuple(dict.fromkeys(group for _, group in groups)), (),
        owner.C05_PROBE_EACH, owner.case_census_digest(cases))
    cohort = owner._cohort(
        EvidenceKind.FIXED_SCHOOL, fixed, groups, release, policy, ((), ()),
        evidence_stage=owner.CURRENT_EVIDENCE_STAGE)
    solver, generation = owner.factory_complete_solver(
        source_context, parent, artifact_path, fixed)
    return owner.evaluate_capabilities(solver, cohort, generation)


def derive_current_plasticity_escape_state(parent, selection, release):
    """Derive exceptional state from accepted/replayed evidence only in strict C05."""
    owner = _owner()
    if owner.CURRENT_EVIDENCE_STAGE is not EvidenceStage.STRICT_GENERALIZATION:
        return None
    from bilqis_mlx.runtime.plasticity_escape import derive_plasticity_escape_state
    context = getattr(selection, "metadata", {}).get("how_context")
    visit = getattr(selection, "visit", None)
    projection = getattr(visit, "projection", None)
    teacher_state = getattr(projection, "teacher_state", None)
    if not isinstance(context, dict):
        owner._invalid("BAMF_PLASTICITY_HOW_CONTEXT_REQUIRED")
    grades = tuple(release.execution_plan.grades)
    if not grades:
        owner._invalid("BAMF_PLASTICITY_ACTIVE_GRADE_REQUIRED")
    return derive_plasticity_escape_state(
        teacher_state,
        getattr(parent, "learning_health_state", None),
        target_capability_id=selection.offer.capability_id,
        target_group_id=context["grade"],
        frontier_group_id=grades[-1].grade_id,
        phase=context["phase"],
        curriculum_scope=context["curriculum_scope"],
        policy_epoch_sha256=owner.policy_epoch_sha256(
            owner.CURRENT_EVIDENCE_STAGE),
    )


def evaluate_factory_package_import(
    source_context,
    transaction: PackageImportTransaction,
    artifact_path: str,
    target_capability: str,
    *,
    run_dir: Path,
):
    """Run the same C05 owner over a B12 package-import state proposal."""
    owner = _owner()
    if (type(transaction) is not PackageImportTransaction
            or not isinstance(target_capability, str) or not target_capability
            or not isinstance(run_dir, Path)):
        owner._invalid("BAMF_C05_PACKAGE_IMPORT_INPUT_INVALID")
    source_context.__post_init__()
    source_context.require_accepted_runtime(run_dir)
    release = source_context.release
    capability_map = release.execution_plan.capability_map
    if target_capability not in capability_map:
        owner._invalid("BAMF_C05_TARGET_CAPABILITY_NOT_ADMITTED")
    groups = tuple((item.capability_id, item.grade_id)
                   for item in release.execution_plan.capabilities)
    target_group = capability_map[target_capability].grade_id
    lesson_capabilities = tuple(capability for capability, group in groups
                                if group == target_group)
    training = ((), ())
    parent, candidate_bundle, candidate_state, cache = (
        owner._package_import_from_live_parent(run_dir, transaction))
    fixed_instruments = owner._fixed_school_instruments(
        source_context, candidate_bundle, artifact_path, run_dir, release,
        parent=parent, cache=cache)
    if {(item.case.capability_id, item.case.group_id)
            for item in fixed_instruments} != set(groups):
        owner._invalid("BAMF_C05_FIXED_SCHOOL_COVERAGE_INCOMPLETE")
    if owner.CURRENT_EVIDENCE_STAGE is EvidenceStage.FOUNDATION_ACQUISITION:
        return owner._broad_foundation_retention_evaluation(
            source_context, parent, candidate_bundle, artifact_path,
            target_capability, release, groups, training, fixed_instruments,
            cache,
            broad_certification_trigger=(
                BroadCertificationTrigger.DECLARED_BROAD_BLAST_RADIUS))
    return owner._adaptive_retention_evaluation(
        source_context, parent, candidate_bundle, candidate_state, artifact_path,
        target_capability, target_group, lesson_capabilities, release, groups,
        training, fixed_instruments, cache,
        protected_capabilities=tuple(
            capability for capability, _group in groups
            if capability != target_capability))


__all__ = (
    "derive_current_plasticity_escape_state",
    "evaluate_factory_package_import",
    "measure_factory_foundation_progress",
)
