"""Source replay and independent checking helpers for formal lessons."""
from __future__ import annotations

from bilqis_mlx.semantics.atlas_snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.cognitive_operators import (
    OperatorBinding, OperatorRegistry, SourceOperand, TypedValue, ValueState,
    execute_pure, operator_grant_digest, source_operand_digest,
)
from bilqis_mlx.semantics.context_eligibility import (
    ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
)
from bilqis_mlx.semantics.domains import contract_digest

from .formal_constructive import FormalSourceOperator, _strict_formal_bytes
from .formal_lesson_types import _SUPPORTED, _fail, _typed_exact

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
    from . import formal_lessons as _formal_lessons
    resolved = _formal_lessons.resolve_formal_source_operators(atlas, binding.registry)
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
    """Literal law truth, used only after exact source/executable authority joins."""
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
