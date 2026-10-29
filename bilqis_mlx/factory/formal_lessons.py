"""Task-scoped formal lesson proposals with independent typed checking.

A01 supplies immutable formal identities, A07 supplies pure execution,
and A13 supplies live operand/operator/domain rights. A checked source
fact is not a Factory admission or learner-retention receipt.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.cognitive_operators import (
    OperatorBinding, OperatorRegistry, SourceOperand, TypedValue, ValueState,
    VALUE_SCHEMA, execute_pure,
    operator_grant_digest, source_operand_digest,
)
from bilqis_mlx.semantics.context_eligibility import (
    ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
)
from bilqis_mlx.semantics.domains import contract_digest

from .formal_constructive import (
    FormalSourceOperator, _strict_formal_bytes,
    resolve_formal_source_operators,
)


FORMAL_LESSON_SCHEMA = "bilqis.formal-constructive-lesson-proposal/v1"
FORMAL_LESSON_STATUS = "TASK_SCOPED_NOT_ADMITTED"
SOURCE_PROJECTION_ONLY = "SOURCE_PROJECTION_NOT_AUTHORITY"
LEARNING_UNVERIFIED = "LEARNING_UNVERIFIED"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_SUPPORTED = frozenset({"BOOL_NOT", "BOOL_AND", "COUNT", "SUCC"})


def _fail(reason: str) -> None:
    ErrorBus.raise_(SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID, reason=reason)


def _typed_exact(value: object) -> bool:
    """Accept only the released primitive input/output shapes for this leaf."""
    if (type(value) is not TypedValue
            or type(value.type_name) is not str
            or type(value.semantic_release) is not str
            or not _SHA.fullmatch(value.semantic_release)
            or type(value.state) is not ValueState
            or value.state is not ValueState.VALUE
            or (value.source_handle is not None
                and (type(value.source_handle) is not str
                     or not value.source_handle))
            or type(value.schema_version) is not str
            or value.schema_version != VALUE_SCHEMA):
        return False
    if value.type_name == "Boolean":
        return type(value.value) is bool
    if value.type_name == "Number":
        return type(value.value) is int
    if value.type_name == "EntitySet":
        return (type(value.value) is tuple
                and all(type(item) is str and bool(item)
                        for item in value.value)
                and value.value == tuple(sorted(set(value.value))))
    return False


@dataclass(frozen=True)
class FormalConstructiveLesson:
    semantic_release: str
    atlas_bundle_id: str
    semantic_id: str
    operator_id: str
    source_binding_sha256: str
    operator_grant_sha256: str
    typed_inputs: tuple[TypedValue, ...]
    operand_evidence_sha256: tuple[str, ...]
    positive: TypedValue
    contrast: TypedValue
    constituents: tuple[str, ...]
    prerequisite_closure: tuple[str, ...]
    variation_axes: tuple[str, ...]
    evidence_sha256: str
    status: str = FORMAL_LESSON_STATUS
    source_authority: str = SOURCE_PROJECTION_ONLY
    learning_state: str = LEARNING_UNVERIFIED
    schema: str = FORMAL_LESSON_SCHEMA

    def __post_init__(self) -> None:
        if (any(type(value) is not str or not _SHA.fullmatch(value)
                for value in (
                    self.semantic_release, self.atlas_bundle_id,
                    self.source_binding_sha256, self.operator_grant_sha256,
                    self.evidence_sha256))
                or type(self.semantic_id) is not str or not self.semantic_id
                or type(self.operator_id) is not str or self.operator_id not in _SUPPORTED
                or type(self.typed_inputs) is not tuple or not self.typed_inputs
                or any(not _typed_exact(item) for item in self.typed_inputs)
                or type(self.operand_evidence_sha256) is not tuple
                or len(self.operand_evidence_sha256) != len(self.typed_inputs)
                or any(type(item) is not str or not _SHA.fullmatch(item)
                       for item in self.operand_evidence_sha256)
                or not _typed_exact(self.positive)
                or not _typed_exact(self.contrast)
                or self.positive.type_name != self.contrast.type_name
                or self.positive.semantic_release != self.semantic_release
                or self.contrast.semantic_release != self.semantic_release
                or self.positive.source_handle is not None
                or self.contrast.source_handle is not None
                or type(self.constituents) is not tuple
                or type(self.prerequisite_closure) is not tuple
                or type(self.variation_axes) is not tuple
                or any(type(item) is not str or not item
                       for group in (
                           self.constituents, self.prerequisite_closure,
                           self.variation_axes) for item in group)
                or self.positive.value == self.contrast.value
                or type(self.status) is not str
                or self.status != FORMAL_LESSON_STATUS
                or type(self.source_authority) is not str
                or self.source_authority != SOURCE_PROJECTION_ONLY
                or type(self.learning_state) is not str
                or self.learning_state != LEARNING_UNVERIFIED
                or type(self.schema) is not str
                or self.schema != FORMAL_LESSON_SCHEMA):
            _fail("BAMF_FORMAL_LESSON_INVALID")


def _source_case(
    atlas: AtlasArtifactSelection, semantic_id: str,
    inputs: tuple[TypedValue, ...], binding: OperatorBinding,
) -> tuple[FormalSourceOperator, TypedValue, tuple[str, ...]]:
    """Replay A01/A07 and require current A13 grants before using a fact."""
    if (type(semantic_id) is not str or type(inputs) is not tuple
            or type(binding) is not OperatorBinding
            or type(binding.registry) is not OperatorRegistry
            or type(binding.task) is not TaskScope
            or type(binding.frontier) is not SourceFrontier
            or type(binding.policy) is not ContextPolicy
            or any(type(grant) is not SourceGrant
                   for grant in binding.frontier.grants)
            or any(not _typed_exact(item) for item in inputs)
            or any(type(item) is not SourceOperand
                   or not _typed_exact(item.typed)
                   for item in binding.operands)):
        _fail("BAMF_FORMAL_LESSON_INPUT_INVALID")
    resolved = resolve_formal_source_operators(atlas, binding.registry)
    witnesses = tuple(
        item for item in resolved.witnesses if item.semantic_id == semantic_id)
    if len(witnesses) != 1 or witnesses[0].operator.operator_id not in _SUPPORTED:
        _fail("BAMF_FORMAL_LESSON_SOURCE_UNCOVERED")
    witness = witnesses[0]
    spec = binding.registry.resolve(witness.operator.operator_id)
    if (_strict_formal_bytes(witness.operator) != _strict_formal_bytes(spec)
            or witness.operator_grant_sha256 != operator_grant_digest(spec)
            or binding.task.semantic_release != resolved.semantic_release):
        _fail("BAMF_FORMAL_LESSON_OPERATOR_DRIFT")
    result = execute_pure(spec.operator_id, inputs, binding)
    if result.state is not ValueState.VALUE:
        _fail("BAMF_FORMAL_LESSON_SOURCE_INAPPLICABLE")
    evidence = []
    for item in inputs:
        matching = tuple(
            operand for operand in binding.operands
            if operand.typed.source_handle == item.source_handle
            and contract_digest(operand.typed) == contract_digest(item))
        if len(matching) != 1:
            _fail("BAMF_FORMAL_LESSON_OPERAND_DRIFT")
        evidence.append(source_operand_digest(matching[0]))
    return witness, result, tuple(evidence)


def _independent_truth(operator_id: str, inputs: tuple[TypedValue, ...]) -> object:
    """Four literal source-released laws, independent of A07's executor."""
    values = tuple(item.value for item in inputs)
    if operator_id == "BOOL_NOT":
        return not values[0]
    if operator_id == "BOOL_AND":
        return values[0] and values[1]
    if operator_id == "COUNT":
        return len(values[0])
    if operator_id == "SUCC":
        return values[0] + 1
    _fail("BAMF_FORMAL_LESSON_LAW_UNSUPPORTED")


def _contrast(positive: TypedValue, binding: OperatorBinding) -> TypedValue:
    if positive.type_name == "Boolean":
        alternate = not positive.value
    elif positive.type_name == "Number" and binding.numeric_domain is not None:
        candidates = sorted(
            value for literal in binding.numeric_domain.values
            if type(value := binding.numeric_domain.decode(literal)) is int
            and value != positive.value)
        if not candidates:
            _fail("BAMF_FORMAL_LESSON_CONTRAST_UNAVAILABLE")
        alternate = candidates[0]
    else:
        _fail("BAMF_FORMAL_LESSON_CONTRAST_UNAVAILABLE")
    return TypedValue(positive.type_name, alternate, positive.semantic_release)


def _evidence(
    witness: FormalSourceOperator, inputs: tuple[TypedValue, ...],
    operand_evidence: tuple[str, ...], positive: TypedValue,
    contrast: TypedValue,
) -> str:
    return contract_digest({
        "schema": "bilqis.formal-lesson-evidence/v1",
        "semantic_id": witness.semantic_id,
        "source_binding": witness.source_binding_sha256,
        "operator_grant": witness.operator_grant_sha256,
        "inputs": inputs,
        "operand_evidence": operand_evidence,
        "positive": positive,
        "contrast": contrast,
    })


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
