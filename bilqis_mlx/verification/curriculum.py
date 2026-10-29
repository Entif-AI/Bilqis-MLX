"""Consumer-side checks of candidate packages against their declared domain.

These checks re-evaluate gold with the supplied source and independent backend.
Authority for semantic meaning, adapter independence and release approval stays
with independently pinned source receipts.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..curriculum_contracts import ConstructionContractPlan, plan_construction_contracts
from ..semantics.foundation.domains import contract_digest, require_sha256
from .construction_contracts import DomainWitness, verify_domain_witness

from ..semantics.foundation.core import Apply, expression_digest
from .cases import verify_constituents
from .expressions import Backend


@dataclass(frozen=True)
class ContractWitnessReport:
    package_sha256: str
    plan: ConstructionContractPlan | None
    witnesses: tuple[DomainWitness, ...]
    mechanical_problems: tuple[str, ...]
    qualification_gaps: tuple[str, ...] = (
        "SOURCE_COMPLETENESS_ATTESTATION_REQUIRED", "FAMILY_SOURCE_QUALIFICATION_REQUIRED",
        "STUDENT_PREREQUISITE_MASTERY_REQUIRED")
    source_qualified: bool = field(default=False, init=False)
    training_authorized: bool = field(default=False, init=False)


def inspect_construction_contracts(package, *, contracts, expected_contracts_sha256,
                                   catalog, source, independent, semantic_catalog=None) -> ContractWitnessReport:
    """Opt-in mechanical inspection through the existing Boolean package gate.

    Wider domain witnesses remain research-only. No existing answer-family,
    canonical binding, independent-gold or prerequisite guard is relaxed.
    """
    from collections.abc import Mapping
    from ..curriculum_compiler import CurriculumAST, TypedCandidatePackage
    if not isinstance(package, TypedCandidatePackage) or not isinstance(contracts, Mapping):
        raise ValueError("CONSTRUCTION_INVALID_PACKAGE_OR_CONTRACTS")
    require_sha256(expected_contracts_sha256)
    problems = list(candidate_package_problems(package, source=source, independent=independent))
    plan, witnesses = None, []
    if contract_digest(contracts) != expected_contracts_sha256:
        problems.append("CONSTRUCTION_CONTRACT_PIN_MISMATCH")
    else:
        try:
            plan = plan_construction_contracts(CurriculumAST(package.ast_version, package.ast_nodes),
                templates=dict(package.construction_templates), contracts=contracts,
                construction_budget=package.construction_budget)
            for item in (() if source is None or independent is None else (*package.lessons, *package.tests)):
                contract = contracts[item.capability]
                witnesses.append(verify_domain_witness(item.expression, contract=contract,
                    expected_contract_sha256=contract_digest(contract), catalog=catalog,
                    source=source, independent=independent, semantic_catalog=semantic_catalog))
        except (KeyError, TypeError, ValueError) as exc:
            problems.append("CONSTRUCTION_CONTRACT_WITNESS_BLOCKED:" + str(exc))
    return ContractWitnessReport(contract_digest(package), plan, tuple(witnesses),
                                  tuple(dict.fromkeys(problems)))


def candidate_package_problems(package, *, source: Backend | None,
                               independent: Backend | None) -> tuple[str, ...]:
    from ..curriculum_compiler import CurriculumAST, dependency_coverage_plan

    problems = []
    ast = CurriculumAST(package.ast_version, package.ast_nodes)
    if ast.digest() != package.ast_sha256:
        problems.append("GRADE_ADMISSION_CANDIDATE_AST_DRIFT")
    try:
        dependency_coverage_plan(ast)
    except ValueError:
        problems.append("GRADE_ADMISSION_CANDIDATE_DEPENDENCY_INVALID")
    nodes = {node.id: node for node in ast.nodes}
    targets = set(package.target_capabilities)
    templates = dict(package.construction_templates)
    if (not targets or not targets <= nodes.keys() or set(templates) != targets or
            len(templates) != len(package.construction_templates)):
        return (*problems, "GRADE_ADMISSION_CANDIDATE_COVERAGE_INVALID")
    if (package.training_authorized or type(package.construction_budget) is not int or
            package.construction_budget < 1):
        return (*problems, "GRADE_ADMISSION_CANDIDATE_STATUS_INVALID")
    if source is None or independent is None:
        problems.append("GRADE_ADMISSION_INDEPENDENT_BACKENDS_MISSING")

    bindings = {operation.symbol: operation for operation in package.operation_bindings}
    seen = set()
    for split, specimens in (("lesson", package.lessons), ("test", package.tests)):
        for node_id in targets:
            if not templates[node_id].complete_boolean_inputs:
                problems.append("GRADE_ADMISSION_CANDIDATE_COVERAGE_INVALID")
            try:
                expected = {expression_digest(expr) for expr in
                            templates[node_id].finite_cases(package.construction_budget)}
            except (TypeError, ValueError):
                problems.append("GRADE_ADMISSION_CANDIDATE_COVERAGE_INVALID")
                continue
            actual = {expression_digest(item.expression) for item in specimens
                      if item.capability == node_id}
            if actual != expected:
                problems.append("GRADE_ADMISSION_CANDIDATE_COVERAGE_INVALID")
        for item in specimens:
            identity = item.capability, item.split, item.ordinal
            if (identity in seen or item.capability not in targets or item.split != split or
                    item.admitted or item.type_name != item.expression.type_name or
                    item.world_contract != item.expression.world_contract or
                    item.proof.expression_sha256 != expression_digest(item.expression)):
                problems.append("GRADE_ADMISSION_CANDIDATE_PROOF_INVALID")
            seen.add(identity)

            def bound(expression):
                return not isinstance(expression, Apply) or (
                    bindings.get(expression.operator.symbol) == expression.operator and
                    all(bound(child) for child in expression.arguments))

            if not bound(item.expression):
                problems.append("GRADE_ADMISSION_SOURCE_BINDINGS_MISMATCH")
            if item.capability in nodes:
                node = nodes[item.capability]

                def operations(expression):
                    return (() if not isinstance(expression, Apply) else
                            (expression.operator.symbol, *(symbol for child in expression.arguments
                                                         for symbol in operations(child))))

                symbols = operations(item.expression)
                predecessors = (*node.requires, *node.composed_of)
                prior_roots = {root for pre in predecessors if pre in nodes for root in nodes[pre].roots}
                if (not symbols or symbols[0] not in node.roots or
                        not set(node.roots) <= set(symbols) or
                        any(symbol not in prior_roots for symbol in symbols[1:]) or
                        any(pre not in nodes or not set(nodes[pre].roots).intersection(symbols[1:])
                            for pre in node.composed_of) or
                        item.type_name != "Boolean" or node.answers != ("binary",)):
                    problems.append("GRADE_ADMISSION_CANDIDATE_PROOF_INVALID")
            if source is not None and independent is not None:
                try:
                    proofs = verify_constituents(item.expression, source=source, independent=independent)
                    if item.proof != proofs[-1] or item.constituent_proofs != proofs[:-1]:
                        problems.append("GRADE_ADMISSION_CANDIDATE_PROOF_INVALID")
                except (TypeError, ValueError):
                    problems.append("GRADE_ADMISSION_CANDIDATE_PROOF_INVALID")
    return tuple(dict.fromkeys(problems))
