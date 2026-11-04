"""Gold-blind C04 lowering for admitted finite-number arithmetic rows."""
from __future__ import annotations

from bilqis_mlx.semantics.cognitive_dag import (
    DAGNode, DAGOperand, DAGProgram, RefKind, task_goal_from_program,
)
from bilqis_mlx.semantics.cognitive_operators import (
    OperatorBinding, SourceKind, SourceOperand, TypedValue,
    default_registry, numeric_domain_digest, operator_grant_digest,
    source_operand_digest,
)
from bilqis_mlx.semantics.context_eligibility import (
    PUBLIC_FORMAL, ContextPolicy, SourceFrontier, SourceGrant, TaskScope,
)
from bilqis_mlx.semantics.domains import FiniteDomain, SourceBinding, ValueCodec, contract_digest
from bilqis_mlx.semantics.foundation.core import Apply, Literal, literal
from bilqis_mlx.semantics.foundation.laws import SourceLocator
from bilqis_mlx.semantics.foundation import numeric as released_numeric

from .numeric import decode


_PURPOSE = "C04_SOLVER"
_PRINCIPAL = "bamf-c04-numeric"
_TENANT = "bamf-c05"
_JURISDICTION = "LOCAL"


def _grant(handle, evidence, semantic_release, scope):
    return SourceGrant(
        handle, _PRINCIPAL, _TENANT, PUBLIC_FORMAL, semantic_release, evidence,
        (_PURPOSE,), (_JURISDICTION,), (scope,), 1, 1, 0, 0,
    )


def _maximum(capability) -> int:
    parameters = dict(capability.provider_parameters)
    numbers = parameters.get("numbers")
    if numbers:
        expected = tuple(str(index) for index in range(len(numbers)))
        if tuple(numbers) != expected:
            raise ValueError("BAMF_C04_NUMERIC_DOMAIN_INVALID")
        return len(numbers) - 1
    return released_numeric.NUMBER_MAX


def lower_numeric_task_goal(
    row: dict, *, semantic_release: str, capability, release, **_,
):
    """Lower source-visible arithmetic while keeping the root operator neural."""
    if (not isinstance(row, dict) or "gold" in row
            or not isinstance(row.get("record"), dict)
            or not isinstance(row["record"].get("symbols"), list)
            or row.get("capability") != capability.capability_id):
        raise ValueError("BAMF_C04_NUMERIC_SOURCE_VIEW_INVALID")
    expression = decode(row["record"]["symbols"])
    declared = capability.capability_id.removeprefix("C.")
    if (isinstance(expression, Apply)
            and expression.operator.symbol == "school.op.EQ"
            and declared != "EQ"):
        expression = expression.arguments[0]
    if not isinstance(expression, Apply):
        raise ValueError("BAMF_C04_NUMERIC_OPERATION_REQUIRED")
    actual = expression.operator.symbol.removeprefix("school.op.")
    if actual not in released_numeric.OPERATIONS or actual == "COUNT":
        raise ValueError("BAMF_C04_NUMERIC_OPERATION_UNSUPPORTED")

    maximum = _maximum(capability)
    domain = FiniteDomain(
        "bilqis.finite-number-domain", "v1", "Number",
        tuple(literal(str(index), "Number") for index in range(maximum + 1)),
        SourceBinding(
            SourceLocator("bilqis_mlx.semantics.numeric", "v1", "finite-number-domain"),
            contract_digest(released_numeric.CONTRACT)),
        ValueCodec.DECIMAL_INTEGER_TEXT, True,
    )
    domain_handle = "source:numeric-domain:" + contract_digest(domain)
    task = TaskScope(
        _PRINCIPAL, _TENANT, _PURPOSE, semantic_release, _JURISDICTION,
        capability.capability_id, 0, 0, len(row.get("tokens", ())),
    )
    policy = ContextPolicy(
        "bamf-c04-numeric/v1", 1, 1,
        (_PURPOSE,), (PUBLIC_FORMAL,), (_JURISDICTION,),
        (capability.capability_id,), (PUBLIC_FORMAL,), (), (),
    )
    registry = default_registry(semantic_release)
    grants = [_grant(
        domain_handle, numeric_domain_digest(domain, semantic_release),
        semantic_release, capability.capability_id)]
    operands = []
    nodes = []
    row_id = str(row.get("id") or row.get("source_id") or "numeric-row")

    def visit(item, path: tuple[int, ...], *, root=False):
        if isinstance(item, Literal):
            if item.type_name != "Number":
                raise ValueError("BAMF_C04_NUMERIC_LITERAL_TYPE_UNSUPPORTED")
            value = int(item.value)
            if not 0 <= value <= maximum:
                raise ValueError("BAMF_C04_NUMERIC_LITERAL_OUTSIDE_DOMAIN")
            handle = "source:numeric-literal:" + contract_digest((row_id, path, value))
            typed = TypedValue("Number", value, semantic_release, handle)
            source = SourceOperand(
                typed, SourceKind.TASK_VISIBLE, "source:numeric-row:" + row_id,
                len(row.get("tokens", ())))
            operands.append(source)
            grants.append(_grant(
                handle, source_operand_digest(source), semantic_release,
                capability.capability_id))
            return DAGOperand(RefKind.LITERAL, "Number", source_handle=handle)
        if not isinstance(item, Apply):
            raise ValueError("BAMF_C04_NUMERIC_EXPRESSION_INVALID")
        refs = tuple(visit(child, (*path, index))
                     for index, child in enumerate(item.arguments))
        operator = item.operator.symbol.removeprefix("school.op.")
        spec = registry.resolve(operator)
        if tuple(ref.type_name for ref in refs) != spec.signature.inputs:
            raise ValueError("BAMF_C04_NUMERIC_SIGNATURE_DRIFT")
        node_id = "numeric:" + ("root" if root else ".".join(map(str, path)))
        if root:
            admitted = tuple(
                item.source_anchor.removeprefix("school.op.")
                for item in release.execution_plan.capabilities
                if item.source_anchor.startswith("school.op."))
            candidates = tuple(sorted(
                operator for operator in admitted
                if operator in {candidate.operator_id for candidate in registry.specs}
                and registry.resolve(operator).signature == spec.signature
                and registry.resolve(operator).applicability == spec.applicability))
            if actual not in candidates:
                raise ValueError("BAMF_C04_NUMERIC_OPERATOR_NOT_ADMITTED")
            node = DAGNode(
                node_id, None, refs, spec.signature.output,
                capability.capability_id, candidates, (),
                ("APPLICABLE", "SOURCE_VISIBLE", "TYPE_COMPATIBLE"),
            )
        else:
            node = DAGNode(
                node_id, operator, refs, spec.signature.output,
                capability.capability_id)
        nodes.append(node)
        return DAGOperand(RefKind.RESULT, spec.signature.output, result_node_id=node_id)

    visit(expression, (), root=True)
    used_operators = {
        operator for node in nodes
        for operator in ((node.operator_id,) if node.operator_id else node.candidate_operator_ids)
    }
    grants.extend(
        _grant(
            "source:operator:" + operator,
            operator_grant_digest(registry.resolve(operator)), semantic_release,
            capability.capability_id)
        for operator in sorted(used_operators)
    )
    frontier = SourceFrontier(
        1, 1, tuple(sorted(grants, key=lambda grant: grant.source_handle)))
    binding = OperatorBinding(
        task, frontier, policy, registry, tuple(operands),
        numeric_domain=domain, numeric_source_handle=domain_handle)
    program = DAGProgram(tuple(nodes), nodes[-1].node_id, capability.capability_id)
    return task_goal_from_program(program, binding, goal_id=row_id), binding


__all__ = ("lower_numeric_task_goal",)
