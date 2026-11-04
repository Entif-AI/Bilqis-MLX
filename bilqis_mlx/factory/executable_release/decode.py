"""Manifest decoding without provider implementation imports."""
from __future__ import annotations
from ...curriculum import AnswerFamily
from ..curriculum_definition import (CapabilitySourceBinding, CapabilitySpec,
                                      CurriculumDefinition, GradeSpec, SourceBindingSet)
from ..execution import (CapabilityExecution, CapabilityProfile,
                         CapabilityProjectionDigests, CurriculumProfile, ExecutionPlan,
                         GradeExecution, GradeProfile, ProjectionDigests)
from .common import _tuples
from .records import (CapabilityVerificationReceipt, ExecutableVerificationReceipt,
                      VerifiedAssessmentSeal)

def _decode_curriculum(value: dict) -> CurriculumDefinition:
    grades = []
    for grade in value["grades"]:
        capabilities = tuple(CapabilitySpec(
            **{
                **_tuples(capability),
                "answer_families": tuple(
                    AnswerFamily(**_tuples(family))
                    for family in capability["answer_families"]),
            })
            for capability in grade["capabilities"])
        grades.append(GradeSpec(
            **{
                **_tuples(grade),
                "capabilities": capabilities,
            }))
    return CurriculumDefinition(
        value["curriculum_id"], tuple(grades), value["program_complete"])


def _decode_source_bindings(value: dict) -> SourceBindingSet:
    return SourceBindingSet(
        tuple(CapabilitySourceBinding(**item) for item in value["bindings"]),
        value.get("source_attestation_sha256"))


def _decode_profile(value: dict) -> CurriculumProfile:
    return CurriculumProfile(
        value["profile_id"],
        tuple(GradeProfile(
            grade["grade_id"],
            None if grade["enabled_capabilities"] is None
            else tuple(grade["enabled_capabilities"]),
            tuple(CapabilityProfile(
                capability["capability_id"],
                _tuples(capability["provider_parameters"]),
                _tuples(capability["answer_family_values"]),
            ) for capability in grade["capabilities"]),
        ) for grade in value["grades"]))


def _decode_plan(value: dict) -> ExecutionPlan:
    capabilities = tuple(CapabilityExecution(
        **{
            **_tuples(item),
            "answer_families": tuple(
                AnswerFamily(**_tuples(family))
                for family in item["answer_families"]),
        })
        for item in value["capabilities"])
    return ExecutionPlan(
        profile_id=value["profile_id"],
        curriculum_sha256=value["curriculum_sha256"],
        source_binding_sha256=value["source_binding_sha256"],
        grades=tuple(GradeExecution(**_tuples(item)) for item in value["grades"]),
        capabilities=capabilities,
        projection_digests=ProjectionDigests(**value["projection_digests"]),
        capability_projection_digests=tuple(
            CapabilityProjectionDigests(**item)
            for item in value["capability_projection_digests"]),
    )


def _decode_verification(value: dict) -> ExecutableVerificationReceipt:
    return ExecutableVerificationReceipt(
        verification_seed=value["verification_seed"],
        execution_plan_sha256=value["execution_plan_sha256"],
        source_binding_sha256=value["source_binding_sha256"],
        provider_descriptors_sha256=value["provider_descriptors_sha256"],
        answer_modalities_sha256=value["answer_modalities_sha256"],
        semantic_catalog_sha256=value["semantic_catalog_sha256"],
        answer_heads_sha256=value["answer_heads_sha256"],
        capabilities=tuple(
            CapabilityVerificationReceipt(**item)
            for item in value["capabilities"]),
        assessments=tuple(
            VerifiedAssessmentSeal(**_tuples(item))
            for item in value["assessments"]),
    )


