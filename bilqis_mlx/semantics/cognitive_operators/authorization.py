"""Source grants, visible frames and independent applicability."""
from __future__ import annotations
from ..context_eligibility import ContextEligibility, ContextHold, check_context_eligibility
from ..domains import FiniteDomain, ValueCodec
from ..frame_schema import FrameInstance
from .common import _invalid
from .registry import CognitiveOperatorSpec, OperatorBinding
from .types import SourceKind, TypedValue, ValueState, numeric_domain_digest, source_operand_digest

def _check_grant(
    handle: str, evidence: str, binding: OperatorBinding,
) -> None:
    task, frontier, policy = binding.task, binding.frontier, binding.policy
    grant = next((item for item in frontier.grants
                  if item.source_handle == handle), None)
    if grant is None:
        _invalid("BAMF_OPERATOR_SOURCE_GRANT_MISSING")
    if (frontier.rights_epoch != policy.rights_epoch
            or grant.evidence_digest != evidence
            or grant.semantic_release != task.semantic_release
            or grant.principal_id != task.principal_id
            or grant.tenant_id != task.tenant_id
            or grant.rights_epoch != frontier.rights_epoch
            or grant.correction_generation != frontier.correction_generation
            or grant.revoked or task.purpose is None
            or task.purpose not in policy.allowed_purposes
            or task.purpose not in grant.permitted_purposes
            or task.jurisdiction not in policy.allowed_jurisdictions
            or task.jurisdiction not in grant.permitted_jurisdictions
            or task.scope not in policy.allowed_scopes
            or task.scope not in grant.permitted_scopes
            or grant.source_regime not in policy.allowed_regimes
            or grant.observed_at > task.observed_frontier
            or grant.effective_from > task.effective_time
            or (grant.effective_until is not None
                and task.effective_time >= grant.effective_until)):
        _invalid("BAMF_OPERATOR_SOURCE_GRANT_INELIGIBLE")


def _approved_frames(binding: OperatorBinding) -> dict[str, ContextEligibility]:
    if not binding.frames:
        return {}
    result = check_context_eligibility(
        binding.frames, binding.task, binding.frontier, binding.policy)
    if isinstance(result, ContextHold):
        _invalid("BAMF_OPERATOR_CONTEXT_HELD")
    return {item.frame_handle: item for item in binding.frames}


def _authorize_inputs(
    values: tuple[TypedValue, ...], binding: OperatorBinding,
) -> None:
    if binding.registry.semantic_release != binding.task.semantic_release:
        _invalid("BAMF_OPERATOR_RELEASE_MISMATCH")
    approved = _approved_frames(binding)
    visible = {operand.typed: operand for operand in binding.operands}
    for operand in binding.operands:
        if (operand.typed.semantic_release != binding.task.semantic_release
                or operand.visible_at_prefix > binding.task.causal_prefix_end):
            _invalid("BAMF_OPERATOR_INVISIBLE_OPERAND")
        _check_grant(
            operand.typed.source_handle, source_operand_digest(operand), binding)
    for value in values:
        if not isinstance(value, TypedValue):
            _invalid("BAMF_OPERATOR_INPUT_NOT_TYPED")
        if value.semantic_release != binding.task.semantic_release:
            _invalid("BAMF_OPERATOR_INPUT_RELEASE_MISMATCH")
        if value in visible:
            continue
        if value.type_name == "FrameHandle":
            envelope = approved.get(value.value)
            if (envelope is not None
                    and value.source_handle == envelope.source_handle):
                continue
        if value.type_name == "ConceptRef":
            if any(
                member.source_handle == value.source_handle
                and frame_binding.concept == value.value
                for envelope in approved.values()
                if isinstance(envelope.frame, FrameInstance)
                for member in envelope.members
                for frame_binding in envelope.frame.bindings
                if frame_binding.key == member.key
            ):
                continue
        _invalid("BAMF_OPERATOR_OPERAND_NOT_ADMITTED")


def _number_domain(binding: OperatorBinding) -> FiniteDomain | None:
    domain = binding.numeric_domain
    if domain is None:
        return None
    if (domain.type_name != "Number" or not domain.closed
            or domain.codec is not ValueCodec.DECIMAL_INTEGER_TEXT):
        _invalid("BAMF_OPERATOR_NUMERIC_DOMAIN_INVALID")
    _check_grant(
        binding.numeric_source_handle,
        numeric_domain_digest(domain, binding.task.semantic_release),
        binding,
    )
    return domain


def _frame(handle: str, binding: OperatorBinding) -> FrameInstance | None:
    for envelope in binding.frames:
        if envelope.frame_handle == handle:
            return envelope.frame if isinstance(envelope.frame, FrameInstance) else None
    return None


def _independent_applicability(
    spec: CognitiveOperatorSpec,
    inputs: tuple[TypedValue | None, ...],
    binding: OperatorBinding,
) -> bool | None:
    """Source-visible preconditions only; never evaluate a candidate answer.

    None means a predecessor value is not yet available. A False result
    disqualifies a hole candidate without consuming a pure compute unit.
    Exact operators still run and count failed applicability normally.
    """
    known = tuple(value for value in inputs if value is not None)
    if any(value.state is not ValueState.VALUE for value in known):
        return False
    if spec.applicability == "FINITE_NUMBER":
        domain = _number_domain(binding)
        if domain is None:
            return False
        allowed = {int(item.value) for item in domain.values}
        if any(value.type_name == "Number" and value.value not in allowed
               for value in known):
            return False
    if spec.operator_id in {"DIV", "MOD"}:
        if inputs[1] is not None and inputs[1].value == 0:
            return False
    if spec.operator_id in {"ROLE_LOOKUP", "PARENT_OF", "BEFORE"}:
        if any(_frame(value.value, binding) is None for value in known
               if value.type_name == "FrameHandle"):
            return False
    if any(value is None for value in inputs):
        return None
    values = tuple(value.value for value in inputs)
    if spec.operator_id in {"DIV", "MOD"}:
        left, right = values
        return right != 0 and (
            spec.operator_id != "DIV" or left % right == 0)
    if spec.operator_id == "UNIT_CONVERT":
        duration, target = values
        return any(
            item.kind is SourceKind.ADMITTED_KNOWLEDGE
            and item.typed.type_name == "UnitConversion"
            and item.typed.state is ValueState.VALUE
            and item.typed.value.from_unit == duration.unit
            and item.typed.value.to_unit == target
            for item in binding.operands)
    if spec.operator_id == "ROLE_LOOKUP":
        return _frame(values[0], binding) is not None
    if spec.operator_id in {"PARENT_OF", "BEFORE"}:
        return all(_frame(handle, binding) is not None for handle in values)
    return True


