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


def _coverage_debt(code: str, *parts: str) -> ValueError:
    return ValueError("CURRICULUM_GENERIC_COVERAGE_DEBT:" + code + ":" + ":".join(parts))


def _seeded_rng(seed: int, node_id: str, split: str, ordinal: int) -> random.Random:
    material = f"{seed}:{node_id}:{split}:{ordinal}".encode()
    return random.Random(int(hashlib.sha256(material).hexdigest()[:16], 16))


def _operations(expression: Expression) -> tuple[Operation, ...]:
    if not isinstance(expression, Apply):
        return ()
    return (expression.operator, *(
        operation for argument in expression.arguments for operation in _operations(argument)))


def _validate_answer_type(node: CapabilityNode, expression: Expression) -> None:
    supported = {"binary": "Boolean"}
    if not node.answers or any(answer not in supported for answer in node.answers):
        raise _coverage_debt("UNSUPPORTED_ANSWER_TYPE", node.id)
    if expression.type_name not in {supported[answer] for answer in node.answers}:
        raise _coverage_debt("SOURCE_OUTPUT_ANSWER_TYPE_MISMATCH", node.id)


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


def compile_probe_plan(ast: CurriculumAST, *, variants_per_axis: int = 4):
    """Reusable factorized probe design, separate from admission and golds.

    Cross product over truth, universe cardinality and seeded world/query
    identities. Future AST node families must attach their own typed,
    independently verified construction operators rather than fake answers.
    """
    if variants_per_axis < 2:
        raise ValueError("CURRICULUM_PROBE_TOO_NARROW_VARIATION")
    rows = []
    for node in ast.nodes:
        if node.grade != "A" or node.id not in {
                "A.IDENTITY", "A.PARENT", "A.LINK", "A.MEMBER", "A.EDGE", "A.MAPS"}:
            raise ValueError("CURRICULUM_NO_SOURCE_ATTESTED_PROBE_BUILDER:" + node.id)
        if node.requires or node.composed_of or node.answers != ("binary",):
            raise ValueError("CURRICULUM_UNSUPPORTED_NODE_STRUCTURE:" + node.id)
        for size in (3, 4):
            for truth in (False, True):
                for variant in range(variants_per_axis):
                    identity = (node.id, size, truth, variant)
                    rows.append({"capability": node.id, "world_size": size,
                                 "positive": truth, "variant": variant,
                                 "probe_id": hashlib.sha256(json.dumps(identity).encode()).hexdigest(),
                                 "builder": "bilqis_mlx.grade_a_probe.make_record",
                                 "oracle": node.oracle})
    return tuple(rows)


def diagnose_coverage(ast: CurriculumAST, plans):
    """Check factor coverage, independent of model performance or exam gold."""
    findings = []
    for node in ast.nodes:
        rows = [r for r in plans if r["capability"] == node.id]
        groups = {(r["world_size"], r["positive"]) for r in rows}
        expected = {(size, truth) for size in (3, 4) for truth in (False, True)}
        if groups != expected:
            findings.append({"capability": node.id, "failure": "MISSING_FACTOR_CONTRAST"})
        if any(len({r["variant"] for r in rows if (r["world_size"], r["positive"]) == group}) < 2
               for group in expected):
            findings.append({"capability": node.id, "failure": "SINGLE_WORLD_IDENTITY"})
    return tuple(findings)


def materialize_probes(plans, *, micro, development, graph, excluded_record_ids=()):
    """Actually compile legal source records with three agreeing gold oracles.

    This is a candidate-only generator. No sealed exam, optimizer, or
    user-accepted lesson inventory is modified.
    """
    from .grade_a_probe import make_record
    from .grade_a_oracle import evaluate as independent_oracle
    output = []
    identities = set(excluded_record_ids)
    for plan in plans:
        seed = int(plan["probe_id"][:16], 16)
        rng = random.Random(seed)
        for _ in range(300):
            record, library = make_record(
                plan["capability"], rng, plan["positive"], split="train",
                micro=micro, development=development, universe_size=plan["world_size"])
            identity = hashlib.sha256(json.dumps(record, sort_keys=True,
                                separators=(",", ":")).encode()).hexdigest()
            if identity not in identities:
                break
        else:
            raise ValueError("CURRICULUM_PROBE_DISTINCT_WORLD_EXHAUSTED")
        gold = library.evaluate(record)
        if (gold != library.independent_evaluate(record) or
                gold != independent_oracle(record, plan["capability"]) or
                (gold == "TRUE") != plan["positive"]):
            raise ValueError("CURRICULUM_PROBE_ORACLES_DISAGREE")
        tokens = list(library.encode(record))
        if not tokens or len(tokens) > 96 or min(tokens) < 0 or max(tokens) >= len(graph["tokens"]):
            raise ValueError("CURRICULUM_PROBE_OUTSIDE_APPROVED_VOCABULARY")
        identities.add(identity)
        output.append({**plan, "record_id": identity, "record": record,
                       "tokens": tokens, "gold": gold, "admitted": False})
    return tuple(output)
