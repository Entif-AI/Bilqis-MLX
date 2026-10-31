"""Deterministic curriculum-AST projection and source-oracled probe planner.

The Registry is editorial authority; a compiled proposal is NOT training
admission. This module has no optimizer, checkpoint, or grade-release effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import hashlib
import json
import random
from typing import Mapping

from .curriculum import Course, validate
from .semantics.core import Apply, Expression, Operation, TypedError, literal
from .semantics.functions import curry
from .semantics.catalog import Catalog
from .verification.cases import verify_constituents
from .verification.expressions import Backend, Proof

@dataclass(frozen=True)
class CapabilityNode:
    id: str
    grade: str
    roots: tuple[str, ...]
    requires: tuple[str, ...]
    composed_of: tuple[str, ...]
    answers: tuple[str, ...]
    oracle: str | None
    source: str
    stage: int = 0

@dataclass(frozen=True)
class CurriculumAST:
    version: str
    nodes: tuple[CapabilityNode, ...]
    authorized_for_training: bool = False

    def digest(self):
        from dataclasses import asdict
        value = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(value.encode()).hexdigest()

@dataclass(frozen=True)
class FiniteTypedInput:
    """A bounded typed leaf domain for declarative candidate construction."""

    type_name: str
    values: tuple[str | bool, ...]
    world_contract: str | None = None

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError("CURRICULUM_GENERIC_EMPTY_TYPED_DOMAIN")
        if len({(type(value), value) for value in self.values}) != len(self.values):
            raise ValueError("CURRICULUM_GENERIC_DUPLICATE_TYPED_DOMAIN_VALUE")
        for value in self.values:
            literal(value, self.type_name, world_contract=self.world_contract)

    def instantiate(self, rng: random.Random) -> Expression:
        return literal(rng.choice(self.values), self.type_name,
                       world_contract=self.world_contract)

@dataclass(frozen=True)
class TypedExpressionTemplate:
    """Declarative composition over the existing immutable semantic AST."""

    operation: Operation
    arguments: tuple["TypedExpressionTemplate | FiniteTypedInput", ...]

    def __post_init__(self) -> None:
        if len(self.arguments) != len(self.operation.signature.inputs):
            raise ValueError("CURRICULUM_GENERIC_TEMPLATE_ARITY_MISMATCH")
        for argument, expected in zip(self.arguments, self.operation.signature.inputs):
            actual = (argument.operation.signature.output
                      if isinstance(argument, TypedExpressionTemplate)
                      else argument.type_name if isinstance(argument, FiniteTypedInput)
                      else None)
            if actual != expected:
                raise ValueError("CURRICULUM_GENERIC_TEMPLATE_TYPE_MISMATCH")

    def instantiate(self, rng: random.Random) -> Apply:
        arguments = tuple(argument.instantiate(rng) for argument in self.arguments)
        expression = curry(self.operation)(*arguments)
        if not isinstance(expression, Apply):
            raise ValueError("CURRICULUM_GENERIC_TEMPLATE_NOT_FULLY_APPLIED")
        return expression

    @property
    def construction_count(self) -> int:
        count = 1
        for argument in self.arguments:
            count *= (argument.construction_count if isinstance(argument, TypedExpressionTemplate)
                      else len(argument.values))
        return count

    @property
    def complete_boolean_inputs(self) -> bool:
        return all(argument.complete_boolean_inputs if isinstance(argument, TypedExpressionTemplate)
                   else argument.type_name != "Boolean" or set(argument.values) == {False, True}
                   for argument in self.arguments)

    def finite_cases(self, budget: int) -> tuple[Apply, ...]:
        """Enumerate the declared finite domain before any seeded draw."""
        if self.construction_count > budget:
            raise _coverage_debt("FINITE_CONSTRUCTION_BUDGET", self.operation.symbol)
        domains = tuple(
            argument.finite_cases(budget) if isinstance(argument, TypedExpressionTemplate)
            else tuple(literal(value, argument.type_name, world_contract=argument.world_contract)
                       for value in argument.values)
            for argument in self.arguments)
        return tuple(curry(self.operation)(*arguments) for arguments in product(*domains))

@dataclass(frozen=True)
class TypedCandidateSpecimen:
    capability: str
    split: str
    ordinal: int
    seed: int
    expression: Expression
    proof: Proof
    type_name: str
    world_contract: str | None
    admitted: bool = False
    constituent_proofs: tuple[Proof, ...] = ()

@dataclass(frozen=True)
class FiniteConstructionCoverage:
    capability: str
    expected_constructions: int
    lesson_constructions: int
    test_constructions: int

@dataclass(frozen=True)
class TypedCandidatePackage:
    """Seeded, source-verified candidate lessons and tests for a typed AST.

    This is deliberately a read-only proposal artifact.  Its receipts make a
    semantic-contract edit observable, while leaving old candidate packages
    inspectable and leaving every admission and neural action outside this
    module.
    """

    ast_sha256: str
    ast_version: str
    ast_nodes: tuple[CapabilityNode, ...]
    operation_bindings: tuple[Operation, ...]
    lessons: tuple[TypedCandidateSpecimen, ...]
    tests: tuple[TypedCandidateSpecimen, ...]
    coverage_debt: tuple[str, ...] = ()
    source_status: str = "SOURCE_ONLY_CANDIDATE"
    training_authorized: bool = False
    construction_coverage: tuple[FiniteConstructionCoverage, ...] = ()
    construction_templates: tuple[tuple[str, TypedExpressionTemplate], ...] = ()
    construction_budget: int = 256
    target_capabilities: tuple[str, ...] = ()

from ._curriculum_compiler.helpers import (
    _coverage_debt, _seeded_rng, _operations, _validate_answer_type,
)
from ._curriculum_compiler.graph import (
    compile_ast, dependency_coverage_plan, affected_dependency_closure,
)
from ._curriculum_compiler.packages import (
    compile_typed_candidate_package, invalidated_typed_packages,
)
from ._curriculum_compiler.probes import (
    compile_probe_plan, diagnose_coverage, materialize_probes,
)

_PUBLIC_MODULE = "bilqis_mlx.curriculum_compiler"
for _public_object in (
    compile_typed_candidate_package, invalidated_typed_packages, compile_ast,
    dependency_coverage_plan, affected_dependency_closure, compile_probe_plan,
    diagnose_coverage, materialize_probes,
):
    _public_object.__module__ = _PUBLIC_MODULE
del _public_object
