"""Public pure operator entrypoint and result-state propagation."""
from __future__ import annotations
from .authorization import _authorize_inputs, _check_grant, _number_domain
from .common import _invalid
from .compute import _compute, _NONE, _UNKNOWN, _UNSUPPORTED
from .registry import CognitiveOperatorSpec, OperatorBinding, operator_grant_digest
from .types import TypedValue, ValueState

def execute_pure(
    operator_id: str,
    typed_inputs: tuple[TypedValue, ...],
    binding: OperatorBinding,
) -> TypedValue:
    """Public source-qualified PURE entrypoint, never an evaluation oracle."""
    if not isinstance(binding, OperatorBinding) or not isinstance(typed_inputs, tuple):
        _invalid("BAMF_OPERATOR_CALL_INVALID")
    if any(not isinstance(item, TypedValue) for item in typed_inputs):
        _invalid("BAMF_OPERATOR_INPUT_NOT_TYPED")
    spec = binding.registry.resolve(operator_id)
    _check_grant(
        "source:operator:" + operator_id,
        operator_grant_digest(spec),
        binding,
    )
    if tuple(item.type_name for item in typed_inputs) != spec.signature.inputs:
        _invalid("BAMF_OPERATOR_SIGNATURE_MISMATCH")
    _authorize_inputs(typed_inputs, binding)
    return _compute_after_authorization(spec, typed_inputs, binding)


def _compute_after_authorization(
    spec: CognitiveOperatorSpec,
    typed_inputs: tuple[TypedValue, ...],
    binding: OperatorBinding,
) -> TypedValue:
    """Pure computation after a caller has proved source and operator grants."""
    release = binding.task.semantic_release
    def unresolved(state: ValueState) -> TypedValue:
        return TypedValue(spec.signature.output, None, release, state=state)

    if any(item.state is ValueState.UNKNOWN for item in typed_inputs):
        return unresolved(ValueState.UNKNOWN)
    if any(item.state is not ValueState.VALUE for item in typed_inputs):
        return unresolved(ValueState.UNSUPPORTED)
    domain = None
    if spec.applicability == "FINITE_NUMBER":
        domain = _number_domain(binding)
        if domain is None:
            return unresolved(ValueState.UNSUPPORTED)
        for item in typed_inputs:
            if item.type_name == "Number":
                try:
                    domain.encode(item.value)
                except ValueError:
                    return unresolved(ValueState.UNSUPPORTED)
    result = _compute(
        spec.operator_id, tuple(item.value for item in typed_inputs), binding)
    if result is _UNKNOWN:
        return unresolved(ValueState.UNKNOWN)
    if result is _NONE:
        return unresolved(ValueState.NONE)
    if result is _UNSUPPORTED:
        return unresolved(ValueState.UNSUPPORTED)
    if domain is not None and spec.signature.output == "Number":
        try:
            domain.encode(result)
        except ValueError:
            return unresolved(ValueState.UNSUPPORTED)
    return TypedValue(spec.signature.output, result, release)
