"""Explicit finite research fixtures, with no production source authority."""
from bilqis_mlx.curriculum_compiler import (CapabilityNode, CurriculumAST,
    FiniteTypedInput, TypedExpressionTemplate)
from bilqis_mlx.curriculum_contracts import (CapabilityConstructionContract,
    ConstructionFamily, FamilyDisposition, FamilyObligation, LeafDomainBinding)
from bilqis_mlx.semantics.core import Operation, Signature, literal
from bilqis_mlx.semantics.domains import (AnswerContract, AnswerMode, FiniteDomain,
    SourceBinding, ValueCodec)
from bilqis_mlx.semantics.laws import SourceLocator

SOURCE = SourceBinding(SourceLocator("synthetic:contract", "fixture/v1", "finite-domain"), "a" * 64)


def domain(*, kind="Boolean", values=(False, True), codec=ValueCodec.LITERAL, world=None):
    return FiniteDomain("fixture-domain", "v1", kind,
        tuple(literal(value, kind, world_contract=world) for value in values),
        SOURCE, codec, True, world)


def construction():
    operation = Operation(0, "fixture.negate", Signature(("Boolean",), "Boolean"), "b" * 64)
    template = TypedExpressionTemplate(operation, (FiniteTypedInput("Boolean", (False, True)),))
    node = CapabilityNode("X.ATOM", "D", (operation.symbol,), (), (),
                          ("binary",), "synthetic:oracle", "synthetic:source")
    families = tuple(FamilyObligation(f, FamilyDisposition.NOT_APPLICABLE,
                     "Scoped fixture only", SOURCE) for f in ConstructionFamily)
    contract = CapabilityConstructionContract(node.id, (LeafDomainBinding((0,), domain()),),
                                              AnswerContract(AnswerMode.BINARY, domain()), families)
    return CurriculumAST("synthetic:contracts/v1", (node,)), template, contract


class BooleanBackend:
    def __init__(self, identity):
        self.identity = identity

    def invoke(self, operation, values, world_contract):
        return not values[0]
