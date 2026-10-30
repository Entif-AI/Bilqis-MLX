"""Task-scoped formal lesson proposals with independent typed checking."""
from __future__ import annotations

from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.cognitive_operators import OperatorBinding, TypedValue
from bilqis_mlx.semantics.domains import contract_digest

from .formal_constructive import resolve_formal_source_operators
from .formal_lesson_checks import (
    _contrast, _evidence, _independent_truth, _source_case,
)
from .formal_lesson_types import (
    FORMAL_LESSON_SCHEMA, FORMAL_LESSON_STATUS, LEARNING_UNVERIFIED,
    SOURCE_PROJECTION_ONLY, FormalConstructiveLesson, _fail, _typed_exact,
)

def construct_formal_lesson(
    atlas: AtlasArtifactSelection, semantic_id: str,
    inputs: tuple[TypedValue, ...], binding: OperatorBinding,
) -> FormalConstructiveLesson:
    """Produce a source-checked task proposal, never global ADAPTER_READY."""
    witness, result, operand_evidence = _source_case(
        atlas, semantic_id, inputs, binding)
    expected = TypedValue(result.type_name, _independent_truth(
        witness.operator.operator_id, inputs), result.semantic_release)
    if contract_digest(result) != contract_digest(expected):
        _fail("BAMF_FORMAL_LESSON_OPERATOR_TRUTH_DRIFT")
    contrast = _contrast(expected, binding)
    constituents = tuple(item.source_handle for item in inputs)
    return FormalConstructiveLesson(
        result.semantic_release, atlas.bundle_id, witness.semantic_id,
        witness.operator.operator_id, witness.source_binding_sha256,
        witness.operator_grant_sha256, inputs, operand_evidence,
        expected, contrast, constituents, constituents,
        ("typed-answer-contrast",),
        _evidence(witness, inputs, operand_evidence, expected, contrast))


def check_formal_lesson(
    lesson: FormalConstructiveLesson, answer: TypedValue,
    atlas: AtlasArtifactSelection, binding: OperatorBinding,
) -> bool:
    """Independently replay A01/A07/A13; never trust generator-provided gold."""
    if type(lesson) is not FormalConstructiveLesson:
        _fail("BAMF_FORMAL_LESSON_CHECKER_INPUT_INVALID")
    FormalConstructiveLesson.__post_init__(lesson)
    witness, result, operand_evidence = _source_case(
        atlas, lesson.semantic_id, lesson.typed_inputs, binding)
    expected = TypedValue(result.type_name, _independent_truth(
        witness.operator.operator_id, lesson.typed_inputs), result.semantic_release)
    contrast = _contrast(expected, binding)
    constituents = tuple(item.source_handle for item in lesson.typed_inputs)
    if (contract_digest(result) != contract_digest(expected)
            or lesson.semantic_release != result.semantic_release
            or lesson.atlas_bundle_id != atlas.bundle_id
            or lesson.operator_id != witness.operator.operator_id
            or lesson.source_binding_sha256 != witness.source_binding_sha256
            or lesson.operator_grant_sha256 != witness.operator_grant_sha256
            or lesson.operand_evidence_sha256 != operand_evidence
            or contract_digest(lesson.positive) != contract_digest(expected)
            or contract_digest(lesson.contrast) != contract_digest(contrast)
            or lesson.constituents != constituents
            or lesson.prerequisite_closure != constituents
            or lesson.variation_axes != ("typed-answer-contrast",)
            or lesson.evidence_sha256 != _evidence(
                witness, lesson.typed_inputs, operand_evidence,
                expected, contrast)):
        _fail("BAMF_FORMAL_LESSON_SOURCE_EVIDENCE_MISMATCH")
    return (_typed_exact(answer)
            and contract_digest(answer) == contract_digest(expected))
