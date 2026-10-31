"""Deterministic curriculum-AST projection and source-oracled probe planner.

The Registry is editorial authority; a compiled proposal is NOT training
admission. This module has no optimizer, checkpoint, or grade-release effects.
"""
from __future__ import annotations

import random
from typing import Mapping

from .semantics.catalog import Catalog
from .semantics.core import Expression, Operation, TypedError
from .verification.cases import verify_constituents
from .verification.expressions import Backend, Proof
from ._curriculum_compiler.types import (
    CapabilityNode, CurriculumAST, FiniteTypedInput, TypedExpressionTemplate,
    TypedCandidateSpecimen, FiniteConstructionCoverage, TypedCandidatePackage,
)
from ._curriculum_compiler.helpers import (
    _coverage_debt, _operations, _seeded_rng, _validate_answer_type,
)
from ._curriculum_compiler.graph import (
    compile_ast, dependency_coverage_plan, affected_dependency_closure,
)

def compile_typed_candidate_package(
    ast: CurriculumAST, *, operations: Mapping[str, Operation],
    templates: Mapping[str, TypedExpressionTemplate],
    source: Backend, independent: Backend, qualified_prerequisites=(),
    seed: int = 0, specimens_per_split: int = 2, construction_budget: int = 256,
    target_capabilities: tuple[str, ...] | None = None,
) -> TypedCandidatePackage:
    """Compile a bounded, source-only candidate package from existing typed ASTs.

    Templates are declarative compositions over ``semantics.functions`` and
    finite typed inputs, so seeded instantiation has no capability-specific
    constructor dispatch. Qualification inputs are labels only: compilation
    cannot prove source pinning, morphology, catalog admission, or mastery.
    """
    if type(seed) is not int or type(specimens_per_split) is not int or specimens_per_split < 1:
        raise ValueError("CURRICULUM_GENERIC_INVALID_SEED_OR_SPECIMEN_COUNT")
    if type(construction_budget) is not int or construction_budget < 1:
        raise ValueError("CURRICULUM_GENERIC_INVALID_CONSTRUCTION_BUDGET")
    if not isinstance(ast, CurriculumAST) or not isinstance(templates, Mapping):
        raise ValueError("CURRICULUM_GENERIC_INVALID_COMPILATION_INPUT")
    dependency_coverage_plan(ast)
    Catalog(tuple(operations.values()))
    if not getattr(source, "identity", None) or not getattr(independent, "identity", None):
        raise _coverage_debt("MISSING_INDEPENDENT_ORACLE_IDENTITY")
    known = {node.id for node in ast.nodes}
    targets = set(target_capabilities) if target_capabilities is not None else known
    if not targets or targets - known:
        raise _coverage_debt("INVALID_TARGET_CAPABILITIES")
    qualified = set(qualified_prerequisites)
    unknown = qualified - known
    if unknown:
        raise _coverage_debt("UNKNOWN_QUALIFIED_PREREQUISITE", *sorted(unknown))
    for node in ast.nodes:
        if node.id not in targets:
            continue
        if not node.source or not node.oracle:
            raise _coverage_debt("MISSING_SOURCE_OR_ORACLE", node.id)
        if not node.roots:
            raise _coverage_debt("MISSING_TYPED_SOURCE_ROOT", node.id)
        if node.id not in templates:
            raise _coverage_debt("MISSING_DECLARATIVE_TEMPLATE", node.id)
        if not isinstance(templates[node.id], TypedExpressionTemplate):
            raise _coverage_debt("INVALID_DECLARATIVE_TEMPLATE", node.id)
        for root in node.roots:
            operation = operations.get(root)
            if not isinstance(operation, Operation) or operation.symbol != root:
                raise _coverage_debt("MISSING_TYPED_SOURCE_OPERATION", node.id, root)
        for prerequisite in (*node.requires, *node.composed_of):
            if prerequisite not in known:
                raise _coverage_debt("MISSING_PREREQUISITE", node.id, prerequisite)
            if prerequisite not in qualified:
                raise _coverage_debt("MISSING_PREREQUISITE", node.id, prerequisite)

    extra_templates = set(templates) - targets
    if extra_templates:
        raise _coverage_debt("UNDECLARED_TEMPLATE", *sorted(extra_templates))

    nodes = {node.id: node for node in ast.nodes}
    ordered = sorted((node for node in ast.nodes if node.id in targets),
                     key=lambda node: (len(node.grade), node.grade, node.stage, node.id))
    finite, coverage, debt = {}, [], []
    for node in ordered:
        if not templates[node.id].complete_boolean_inputs:
            debt.append("INCOMPLETE_BOOLEAN_DOMAIN:" + node.id)
        try:
            cases = templates[node.id].finite_cases(construction_budget)
            witnesses = []
            for expression in cases:
                nested = _operations(expression)
                if expression.operator.symbol not in node.roots:
                    raise _coverage_debt("UNDECLARED_ROOT_OPERATOR", node.id, expression.operator.symbol)
                if not set(node.roots) <= {operation.symbol for operation in nested}:
                    raise _coverage_debt("TEMPLATE_MISSING_DECLARED_ROOT", node.id)
                for operation in nested:
                    if operations.get(operation.symbol) != operation:
                        raise _coverage_debt("UNBOUND_NESTED_OPERATION", node.id, operation.symbol)
                prerequisites = (*node.requires, *node.composed_of)
                nested_roots = {operation.symbol for operation in nested[1:]}
                for constituent in node.composed_of:
                    if not nested_roots.intersection(nodes[constituent].roots):
                        raise _coverage_debt("MISSING_COMPOSED_CONSTITUENT", node.id, constituent)
                for operation in nested[1:]:
                    if not any(operation.symbol in nodes[pre].roots for pre in prerequisites):
                        raise _coverage_debt("UNQUALIFIED_CONSTITUENT", node.id, operation.symbol)
                _validate_answer_type(node, expression)
                proofs = verify_constituents(expression, source=source, independent=independent)
                witnesses.append((expression, proofs[-1], proofs[:-1]))
            finite[node.id] = witnesses
        except TypedError as exc:
            code = ("ORACLE_DISAGREEMENT" if str(exc) == "COMPOSITION_ORACLE_DISAGREEMENT"
                    else "INVALID_TYPED_SOURCE_WITNESS")
            raise _coverage_debt(code, node.id) from exc
        covered = min(specimens_per_split, len(cases))
        coverage.append(FiniteConstructionCoverage(node.id, len(cases), covered, covered))
        if covered < len(cases):
            debt.extend(f"INCOMPLETE_FINITE_COVERAGE:{node.id}:{split}:{covered}/{len(cases)}"
                        for split in ("lesson", "test"))

    compiled = {"lesson": [], "test": []}
    for split in ("lesson", "test"):
        for node in ordered:
            witnesses = list(finite[node.id])
            _seeded_rng(seed, node.id, split, 0).shuffle(witnesses)
            for ordinal in range(specimens_per_split):
                expression, proof, constituents = witnesses[ordinal % len(witnesses)]
                compiled[split].append(TypedCandidateSpecimen(
                    node.id, split, ordinal, seed, expression, proof,
                    expression.type_name, expression.world_contract,
                    constituent_proofs=constituents))
    bindings = {operation.symbol: operation
                for template in templates.values()
                for operation in _operations(template.instantiate(random.Random(0)))}
    return TypedCandidatePackage(ast.digest(), ast.version, ast.nodes,
                                 tuple(sorted(bindings.values(), key=lambda item: item.symbol)),
                                 tuple(compiled["lesson"]), tuple(compiled["test"]),
                                 coverage_debt=tuple(debt), construction_coverage=tuple(coverage),
                                 construction_templates=tuple((node.id, templates[node.id]) for node in ordered),
                                 construction_budget=construction_budget,
                                 target_capabilities=tuple(node.id for node in ordered))

from ._curriculum_compiler.packages import invalidated_typed_packages
from ._curriculum_compiler.probes import (
    compile_probe_plan, diagnose_coverage, materialize_probes,
)

_PUBLIC_MODULE = "bilqis_mlx.curriculum_compiler"
for _public_object in (
    CapabilityNode, CurriculumAST, FiniteTypedInput, TypedExpressionTemplate,
    TypedCandidateSpecimen, FiniteConstructionCoverage, TypedCandidatePackage,
    invalidated_typed_packages, compile_ast, dependency_coverage_plan,
    affected_dependency_closure, compile_probe_plan, diagnose_coverage,
    materialize_probes,
):
    _public_object.__module__ = _PUBLIC_MODULE
del _public_object
