"""Factory execution projections owner."""
from __future__ import annotations

from ..curriculum_definition import SourceBindingSet
from .records import (CapabilityExecution, GradeExecution, ProjectionDigests, CapabilityProjectionDigests)
from .. import execution as _api


def _projection_digests(
        grades: tuple[GradeExecution, ...],
        capabilities: tuple[CapabilityExecution, ...],
        source_bindings: SourceBindingSet,
) -> ProjectionDigests:
    roster = tuple((grade.grade_id, grade.capabilities) for grade in grades)
    schedule = tuple((
        grade.grade_id, grade.teaching_stages,
        tuple((cap.capability_id, cap.stage, cap.prerequisites, cap.composed_of)
              for cap in capabilities if cap.grade_id == grade.grade_id),
    ) for grade in grades)
    assessment = tuple((
        grade.grade_id, grade.cumulative_scope, grade.assessment_blueprint_sha256,
        tuple((cap.capability_id, cap.exam_item_count)
              for cap in capabilities if cap.grade_id == grade.grade_id),
    ) for grade in grades)
    source = (
        ("source_attestation", source_bindings.source_attestation_sha256),
        *tuple((
            cap.capability_id, cap.source_anchor, cap.provider_id,
            cap.provider_implementation_sha256, cap.oracle_id,
            cap.construction_program_id, cap.provider_parameters,
        ) for cap in capabilities),
    )
    answer_schema = tuple((
        cap.capability_id,
        tuple((family.kind, family.values) for family in cap.answer_families),
    ) for cap in capabilities)
    coverage = tuple((
        cap.capability_id, cap.exam_item_count, cap.variation_axes,
    ) for cap in capabilities)
    teaching = tuple((cap.capability_id, cap.teaching_option_ids)
                     for cap in capabilities)
    return _api.ProjectionDigests(
        roster=_api._digest(roster), schedule=_api._digest(schedule),
        assessment=_api._digest(assessment), source=_api._digest(source),
        answer_schema=_api._digest(answer_schema), coverage=_api._digest(coverage),
        teaching=_api._digest(teaching))


def _capability_projection_digests(
        capabilities: tuple[CapabilityExecution, ...],
        source_bindings: SourceBindingSet,
) -> tuple[CapabilityProjectionDigests, ...]:
    return tuple(_api.CapabilityProjectionDigests(
        capability_id=cap.capability_id,
        schedule=_api._digest((
            cap.capability_id, cap.grade_id, cap.stage,
            cap.prerequisites, cap.composed_of)),
        assessment=_api._digest((
            cap.capability_id, cap.exam_item_count,
            tuple((family.kind, family.values) for family in cap.answer_families))),
        source=_api._digest((
            cap.capability_id, cap.source_anchor, cap.provider_id,
            cap.provider_implementation_sha256, cap.oracle_id,
            cap.construction_program_id, cap.provider_parameters,
            source_bindings.source_attestation_sha256)),
        answer_schema=_api._digest((
            cap.capability_id,
            tuple((family.kind, family.values) for family in cap.answer_families))),
        coverage=_api._digest((cap.capability_id, cap.exam_item_count, cap.variation_axes)),
        teaching=_api._digest((cap.capability_id, cap.teaching_option_ids)),
    ) for cap in capabilities)
