"""Current C07 debt and policy view over verified A09/B13 authority."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..factory.atlas_delta_scope import AtlasDeltaScopeHandoff
from .atlas_admission import _invalid


@dataclass(frozen=True)
class CurrentDomainPolicyView:
    """Existing policy identities projected from the current snapshot and release."""

    policy_epoch: int
    curriculum_sha256: str
    source_binding_sha256: str
    schedule_sha256: str
    source_sha256: str
    teaching_sha256: str


@dataclass(frozen=True)
class CurrentAtlasDebtView:
    accepted_factory_release_sha256: str
    snapshot_sha256: str
    retained_debt_source_sha256: str | None
    grade_debt: tuple[tuple[str, tuple[str, ...]], ...]
    numeric_scope: tuple[tuple[str, tuple[str, ...]], ...]
    current_domain_policy: CurrentDomainPolicyView
    historical_scope_policy_status: str = field(default="NOT_MEASURED", init=False)
    authorizes_learning: bool = field(default=False, init=False)
    schema_version: str = field(default="bilqis.c07.current-debt-policy-view/v1", init=False)


def _numeric_scope(release) -> tuple[tuple[str, tuple[str, ...]], ...]:
    result = []
    for capability in release.execution_plan.capabilities:
        parameters = dict(capability.provider_parameters)
        provider_numbers = parameters.get("numbers")
        numeric_families = tuple(
            family.values for family in capability.answer_families
            if family.kind == "numeric_active" or family.kind.startswith("integer_")
        )
        if provider_numbers is None and not numeric_families:
            continue
        if provider_numbers is not None:
            values = tuple(provider_numbers)
            if numeric_families and any(tuple(family) != values for family in numeric_families):
                _invalid("BAMF_ATLAS_CURRENT_NUMERIC_SCOPE_DRIFT")
        elif len(numeric_families) == 1:
            values = tuple(numeric_families[0])
        else:
            _invalid("BAMF_ATLAS_CURRENT_NUMERIC_SCOPE_AMBIGUOUS")
        result.append((capability.capability_id, values))
    return tuple(result)


def read_current_atlas_debt_policy(
        run_dir: Path, handoff: AtlasDeltaScopeHandoff) -> CurrentAtlasDebtView:
    """Project current debt/scope/policy without creating new admission authority."""
    if not isinstance(run_dir, Path) or not isinstance(handoff, AtlasDeltaScopeHandoff):
        _invalid("BAMF_ATLAS_CURRENT_DEBT_POLICY_INPUT_INVALID")
    handoff.verify()
    from .atlas_admission import read_accepted_atlas_factory_release

    accepted = read_accepted_atlas_factory_release(run_dir)
    predecessor = handoff.receipt.predecessor_release
    snapshot = handoff.receipt.selection_snapshot
    if (accepted != predecessor
            or snapshot.admitted_factory_release_sha256 != accepted.release_sha256):
        _invalid("BAMF_ATLAS_CURRENT_DEBT_POLICY_RELEASE_DRIFT")

    capability_grades = {
        capability.capability_id: capability.grade_id
        for capability in accepted.execution_plan.capabilities
    }
    unknown = tuple(
        capability for capability in snapshot.retained_mastery_debt
        if capability not in capability_grades)
    if unknown:
        _invalid("BAMF_ATLAS_CURRENT_DEBT_CAPABILITY_DRIFT")
    grades = tuple(grade.grade_id for grade in accepted.execution_plan.grades)
    grade_debt = tuple(
        (grade, tuple(
            capability for capability in snapshot.retained_mastery_debt
            if capability_grades[capability] == grade))
        for grade in grades
    )
    projections = accepted.execution_plan.projection_digests
    policy = CurrentDomainPolicyView(
        snapshot.policy_epoch,
        accepted.execution_plan.curriculum_sha256,
        accepted.execution_plan.source_binding_sha256,
        projections.schedule,
        projections.source,
        projections.teaching,
    )
    return CurrentAtlasDebtView(
        accepted.release_sha256,
        snapshot.snapshot_sha256,
        snapshot.retained_debt_source_sha256,
        grade_debt,
        _numeric_scope(accepted),
        policy,
    )
