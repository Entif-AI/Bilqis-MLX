"""Decode persisted executable release components."""
from __future__ import annotations

from ..curriculum_definition import CurriculumDefinition, SourceBindingSet
from ..execution import CurriculumProfile, ExecutionPlan
from .primitives import ExecutableVerificationReceipt

from .. import executable_release as _api


def _decode_curriculum(value: dict) -> CurriculumDefinition:
    grades = []
    for grade in value["grades"]:
        capabilities = tuple(_api.CapabilitySpec(
            **{
                **_api._tuples(capability),
                "answer_families": tuple(
                    _api.AnswerFamily(**_api._tuples(family))
                    for family in capability["answer_families"]),
            })
            for capability in grade["capabilities"])
        grades.append(_api.GradeSpec(
            **{
                **_api._tuples(grade),
                "capabilities": capabilities,
            }))
    return _api.CurriculumDefinition(
        value["curriculum_id"], tuple(grades), value["program_complete"])


def _decode_source_bindings(value: dict) -> SourceBindingSet:
    return _api.SourceBindingSet(
        tuple(_api.CapabilitySourceBinding(**item) for item in value["bindings"]),
        value.get("source_attestation_sha256"))


def _decode_profile(value: dict) -> CurriculumProfile:
    return _api.CurriculumProfile(
        value["profile_id"],
        tuple(_api.GradeProfile(
            grade["grade_id"],
            None if grade["enabled_capabilities"] is None
            else tuple(grade["enabled_capabilities"]),
            tuple(_api.CapabilityProfile(
                capability["capability_id"],
                _api._tuples(capability["provider_parameters"]),
                _api._tuples(capability["answer_family_values"]),
            ) for capability in grade["capabilities"]),
        ) for grade in value["grades"]))


def _decode_plan(value: dict) -> ExecutionPlan:
    capabilities = tuple(_api.CapabilityExecution(
        **{
            **_api._tuples(item),
            "answer_families": tuple(
                _api.AnswerFamily(**_api._tuples(family))
                for family in item["answer_families"]),
        })
        for item in value["capabilities"])
    return _api.ExecutionPlan(
        profile_id=value["profile_id"],
        curriculum_sha256=value["curriculum_sha256"],
        source_binding_sha256=value["source_binding_sha256"],
        grades=tuple(_api.GradeExecution(**_api._tuples(item)) for item in value["grades"]),
        capabilities=capabilities,
        projection_digests=_api.ProjectionDigests(**value["projection_digests"]),
        capability_projection_digests=tuple(
            _api.CapabilityProjectionDigests(**item)
            for item in value["capability_projection_digests"]),
    )


def _decode_verification(value: dict) -> ExecutableVerificationReceipt:
    return _api.ExecutableVerificationReceipt(
        verification_seed=value["verification_seed"],
        execution_plan_sha256=value["execution_plan_sha256"],
        source_binding_sha256=value["source_binding_sha256"],
        provider_descriptors_sha256=value["provider_descriptors_sha256"],
        answer_modalities_sha256=value["answer_modalities_sha256"],
        semantic_catalog_sha256=value["semantic_catalog_sha256"],
        answer_heads_sha256=value["answer_heads_sha256"],
        capabilities=tuple(
            _api.CapabilityVerificationReceipt(**item)
            for item in value["capabilities"]),
        assessments=tuple(
            _api.VerifiedAssessmentSeal(**_api._tuples(item))
            for item in value["assessments"]),
    )
