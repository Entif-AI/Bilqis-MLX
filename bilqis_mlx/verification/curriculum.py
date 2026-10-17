"""Consumer-side checks of candidate packages against their declared domain.

These checks re-evaluate gold with the supplied source and independent backend.
Authority for semantic meaning, adapter independence and release approval stays
with independently pinned source receipts.
"""
from __future__ import annotations

from ..semantics.core import Apply, expression_digest
from .cases import verify_constituents
from .expressions import Backend


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
            if source is not None and independent is not None:
                try:
                    proofs = verify_constituents(item.expression, source=source, independent=independent)
                    if item.proof != proofs[-1] or item.constituent_proofs != proofs[:-1]:
                        problems.append("GRADE_ADMISSION_CANDIDATE_PROOF_INVALID")
                except (TypeError, ValueError):
                    problems.append("GRADE_ADMISSION_CANDIDATE_PROOF_INVALID")
    return tuple(dict.fromkeys(problems))
