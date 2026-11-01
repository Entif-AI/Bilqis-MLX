"""Typed candidate package compilation and invalidation."""
from __future__ import annotations
import random
from typing import Mapping
from .types import (
    CurriculumAST, FiniteConstructionCoverage, TypedCandidatePackage,
    TypedCandidateSpecimen, TypedExpressionTemplate,
)
from bilqis_mlx.semantics.catalog import Catalog
from bilqis_mlx.semantics.core import Operation, TypedError
from bilqis_mlx.verification.cases import verify_constituents
from bilqis_mlx.verification.expressions import Backend
from .helpers import _coverage_debt, _operations, _seeded_rng, _validate_answer_type
from .graph import affected_dependency_closure, dependency_coverage_plan


def invalidated_typed_packages(
    package: TypedCandidatePackage, ast: CurriculumAST,
    operations: Mapping[str, Operation],
) -> tuple[str, ...]:
    """Return affected nodes after a bound operation contract changes.

    Package bytes are intentionally not rewritten: callers retain old receipts
    and compile a fresh candidate package for the reported closure.
    """
    if not isinstance(package, TypedCandidatePackage):
        raise ValueError("CURRICULUM_GENERIC_INVALID_CANDIDATE_PACKAGE")
    dependency_coverage_plan(ast)
    previous = {node.id: node for node in package.ast_nodes}
    current = {node.id: node for node in ast.nodes}
    changed = {identity for identity in set(previous) | set(current)
               if previous.get(identity) != current.get(identity)}
    for prior in package.operation_bindings:
        if operations.get(prior.symbol) != prior:
            changed.update(node.id for node in ast.nodes if prior.symbol in node.roots)
            changed.update(item.capability for item in (*package.lessons, *package.tests)
                           if prior in _operations(item.expression))
    existing = tuple(sorted(changed & set(current)))
    return tuple(sorted((changed - set(current)) |
                        set(affected_dependency_closure(ast, existing))))
