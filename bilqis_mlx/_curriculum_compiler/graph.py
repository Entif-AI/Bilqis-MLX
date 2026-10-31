"""Curriculum graph projection and dependency closure."""
from __future__ import annotations
from bilqis_mlx.curriculum import Course, validate
from .types import CapabilityNode, CurriculumAST

def compile_ast(course: Course) -> CurriculumAST:
    """Build one canonical topological projection; never promote proposals."""
    validate(course)
    nodes = tuple(CapabilityNode(
        id=cap.id, grade=grade.id, roots=cap.taught_roots,
        requires=cap.prerequisites, composed_of=cap.composed_of,
        answers=tuple(a.kind for a in cap.answer_families),
        oracle=cap.independent_oracle, source=cap.source_anchor,
        stage=next((i for i, names in enumerate(grade.teaching_stages)
                    if cap.id in names), 0))
        for grade in course.grades for cap in grade.capabilities)
    return CurriculumAST(course.version, nodes)

def dependency_coverage_plan(ast: CurriculumAST, supported_edges=()):
    """Inventory declared predecessor obligations without asserting admission.

    Supported edges are constructor declarations only. Source witnesses and
    independently verified oracle agreement are still required to discharge
    coverage debt; this planner intentionally cannot claim their proof.
    """
    nodes = {node.id: node for node in ast.nodes}
    if len(nodes) != len(ast.nodes):
        raise ValueError("CURRICULUM_DUPLICATE_SEMANTIC_ID")
    declared = {(node.id, pre) for node in ast.nodes
                for pre in (*node.requires, *node.composed_of)}
    for dependent, predecessor in declared:
        if dependent == predecessor or predecessor not in nodes:
            raise ValueError("CURRICULUM_UNRESOLVED_DEPENDENCY")
        if nodes[predecessor].grade > nodes[dependent].grade:
            raise ValueError("CURRICULUM_DEPENDENCY_NOT_EARLIER_GRADE")
        if (nodes[predecessor].grade == nodes[dependent].grade and
                nodes[predecessor].stage >= nodes[dependent].stage):
            raise ValueError("CURRICULUM_DEPENDENCY_NOT_EARLIER_STAGE")
    supported = set(supported_edges)
    if supported - declared:
        raise ValueError("CURRICULUM_UNDECLARED_SUPPORTED_EDGE")
    return tuple({"capability": dependent, "predecessor": predecessor,
                  "capability_grade": nodes[dependent].grade,
                  "predecessor_grade": nodes[predecessor].grade,
                  "status": ("CONSTRUCTOR_DECLARED_UNVERIFIED"
                             if (dependent, predecessor) in supported
                             else "MISSING_CONSTRUCTOR"),
                  "coverage_debt": True,
                  "training_authorized": False}
                 for dependent, predecessor in sorted(declared))

def affected_dependency_closure(ast: CurriculumAST, changed: tuple[str, ...]):
    """Return all affected capabilities when an admitted semantic ID changes.

    Walk the reverse prerequisite graph, not grade-specific constructor code;
    outputs are stable and include the changed identities themselves.
    """
    obligations = dependency_coverage_plan(ast)
    nodes = {node.id for node in ast.nodes}
    if not set(changed) <= nodes:
        raise ValueError("CURRICULUM_UNKNOWN_CHANGED_SEMANTIC_ID")
    reverse = {identity: set() for identity in nodes}
    for edge in obligations:
        reverse[edge["predecessor"]].add(edge["capability"])
    impacted = set(changed)
    pending = list(changed)
    while pending:
        for dependent in reverse[pending.pop()]:
            if dependent not in impacted:
                impacted.add(dependent)
                pending.append(dependent)
    return tuple(sorted(impacted))
