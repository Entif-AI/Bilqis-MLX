"""Source-oracled, dynamically sampled Grade B truth-functional constructors.

Only already mastered Grade A operand semantics are used: entity identity,
direct PARENT and undirected LINK. All six connective operators have stable
legacy token identities and formal typed semantics; no unattested NI wordform
or permanently embargoed examination question is introduced.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib
import json
from pathlib import Path
import random

from .curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from .grade_a_probe import PINNED_SOURCES, read_sources
from .grade_b_oracle import CONNECTIVES, VERSION as ORACLE_VERSION
from .grade_b_oracle import evaluate as independent_oracle

GENERATOR = "bilqis.mlx.grade-b-connectives-constructor/v1"
RELEASE = "bilqis.mlx.grade-a-b-live/20261015-v1"
ASSESSMENT_ITEMS_PER_CAPABILITY = 12
PREREQUISITES = ()
PINNED_BOOLEAN_SOURCE = PINNED_SOURCES["bilqis_logic/kernel.py"]
OUTER_LANDMARK_CONNECTIVES = ("AND", "IMPLIES")
OUTER_LANDMARK_PRESENTATION = "named-outer-operands/v1"
OUTER_LANDMARK_VARIATION = "and-implies-named-outer-operands"
MAX_BOOLEAN_CONTEXT_TOKENS = 96


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def source_record_identity(record: dict) -> str:
    return _digest(record)


def capability_row_identity(capability: str, record: dict) -> str:
    return _digest([capability, record])


def constructor_digest():
    home = Path(__file__).resolve().parent
    return _digest({p: hashlib.sha256((home / p).read_bytes()).hexdigest()
                    for p in ("live_grade_b.py", "grade_b_oracle.py")})


def source_attestation(legacy_root: Path) -> dict:
    """Fail closed unless the exact old source and graph are still available."""
    root = Path(legacy_root).resolve(strict=True)
    _, _, graph, sha, graph_sha = read_sources(root)
    source = root / "bilqis_logic/kernel.py"
    if hashlib.sha256(source.read_bytes()).hexdigest() != PINNED_BOOLEAN_SOURCE:
        raise ValueError("GRADE_B_BOOLEAN_TRUTH_TABLE_SOURCE_DRIFT")
    required = (
        "task.evaluate", "syntax.bind", "syntax.separator", "syntax.end",
        "micro.proof.premise", "cogal.value.false", "cogal.value.true",
        "cogal.variable.P", "cogal.variable.Q",
    )
    identities = tuple("cogal.operator." + op for op in CONNECTIVES)
    if not set(required + identities) <= set(graph["tokens"]):
        raise ValueError("GRADE_B_SOURCE_TOKEN_IDENTITIES_UNAVAILABLE")
    return {"source_sha256": sha, "graph_sha256": graph_sha,
            "boolean_sha256": PINNED_BOOLEAN_SOURCE,
            "operators": list(CONNECTIVES),
            "prerequisites": list(PREREQUISITES),
            "semantic_mode": "DIRECT_TYPED_BOOLEAN_AST"}


def live_course(grade_a: Course, legacy_root: Path) -> Course:
    """Append one versioned grade while preserving A's actual accepted seal."""
    if (grade_a.program_complete or len(grade_a.grades) != 1 or
            grade_a.grades[0].id != "A" or
            {c.id for c in grade_a.grades[0].capabilities} != {
                "A.IDENTITY", "A.PARENT", "A.LINK", "A.MEMBER", "A.EDGE", "A.MAPS"} or
            not grade_a.executable):
        raise ValueError("GRADE_B_PREDECESSOR_NOT_ADMITTED_GRADE_A")
    provenance = source_attestation(legacy_root)
    _, _, source_graph, _, _ = read_sources(legacy_root)
    # No B source is admitted from identifiers alone. Construct and verify an
    # entire complete source-oracled candidate cohort before a run may switch.
    witness = draw_connectives(legacy_root, source_graph, seed=2026101501)
    if (len(witness) != len(CONNECTIVES) * ASSESSMENT_ITEMS_PER_CAPABILITY or
            {op: sum(row["capability"] == "B." + op for row in witness)
             for op in CONNECTIVES} != {
                 op: ASSESSMENT_ITEMS_PER_CAPABILITY for op in CONNECTIVES}):
        raise ValueError("GRADE_B_SOURCE_ADMISSION_COHORT_NOT_COMPREHENSIVE")
    caps = tuple(Capability(
        id="B." + op, difficulty="first-boolean-composition",
        source_anchor="repo:bilqis_logic/kernel.py::TABLES+encode",
        taught_roots=("cogal.operator." + op,),
        examined_roots=("cogal.operator." + op,),
        prerequisites=PREREQUISITES,
        composed_of=(),
        answer_families=(AnswerFamily("binary", BINARY),),
        lesson_generator="bilqis_mlx.live_grade_b.draw_connectives",
        independent_oracle=ORACLE_VERSION,
    ) for op in CONNECTIVES)
    seal = _digest({"generator": GENERATOR,
                    "generator_code_sha256": constructor_digest(),
                    "source_attestation": provenance,
                    "source_witness_sha256": _digest(witness),
                    "prior_a_rubric": grade_a.grades[0].assessment_sha256,
                    "items_per_capability": ASSESSMENT_ITEMS_PER_CAPABILITY})
    grade_b = Grade("B", caps, assessment_sha256=seal,
                    exam_item_counts=tuple((c.id, ASSESSMENT_ITEMS_PER_CAPABILITY)
                                            for c in caps))
    course = replace(grade_a, grades=(*grade_a.grades, grade_b),
                     version=RELEASE, program_complete=False,
                     source_attestation_sha256=_digest({
                         "grade_a": grade_a.source_attestation_sha256,
                         "grade_b": provenance}),
                     assessment_manifest_sha256=seal)
    if not course.executable:
        raise ValueError("GRADE_B_SOURCE_RELEASE_NOT_EXECUTABLE")
    return course


def _logic_source(legacy_root: Path):
    source_attestation(legacy_root)
    logic = importlib.import_module("bilqis_logic.kernel")
    expected = Path(legacy_root).resolve() / "bilqis_logic/kernel.py"
    if Path(logic.__file__).resolve() != expected:
        raise ValueError(BOOLEAN_SOURCE_ROOT_MISMATCH)
    return logic


def _encode_logic_record(logic, record: dict, graph: dict) -> list[int]:
    names = graph["tokens"]
    try:
        tokens = [names.index(logic.TOKENS[index]) for index in logic.encode(record)]
    except (IndexError, ValueError) as exc:
        raise ValueError(BOOLEAN_TOKEN_ABI_DRIFT) from exc
    if not 1 <= len(tokens) <= MAX_BOOLEAN_CONTEXT_TOKENS:
        raise ValueError(BOOLEAN_CONTEXT_LENGTH)
    return tokens


def _expression_prefix(
        logic, expression: dict, assignments: dict, graph: dict) -> list[int]:
    """Reuse the pinned codec to obtain one operand's typed prefix."""
    free_names = logic.free_variables(expression)
    operand_assignments = {
        name: assignments[name] for name in free_names}
    encoded = logic.encode(
        logic.evaluation_record(expression, operand_assignments))
    bind = logic.TOKEN_ID["syntax.bind"]
    try:
        boundary = encoded.index(bind)
        names = graph["tokens"]
        return [names.index(logic.TOKENS[index])
                for index in encoded[1:boundary]]
    except (IndexError, ValueError) as exc:
        raise ValueError(BOOLEAN_TOKEN_ABI_DRIFT) from exc


def _encode_connective_record(
        logic, record: dict, graph: dict, capability: str) -> list[int]:
    """Encode atomic Boolean rows, landmarking only the authorized outer slots."""
    operator = capability.removeprefix("B.")
    if (operator not in OUTER_LANDMARK_CONNECTIVES or
            record.get("presentation") != OUTER_LANDMARK_PRESENTATION):
        return _encode_logic_record(logic, record, graph)
    expression = record.get("expression")
    if (not isinstance(expression, dict) or
            expression.get("kind") != "apply" or
            expression.get("operator") != operator or
            len(expression.get("args", ())) != 2 or
            not isinstance(record.get("assignments"), dict)):
        raise ValueError(BOOLEAN_LANDMARK_RECORD_INVALID)
    assignments = record["assignments"]
    names = graph["tokens"]
    try:
        task = names.index("task.evaluate")
        root = names.index("cogal.operator." + operator)
        premise = names.index("micro.proof.premise")
        left = names.index("cogal.variable.P")
        right = names.index("cogal.variable.Q")
        bind = names.index("syntax.bind")
        separator = names.index("syntax.separator")
        end = names.index("syntax.end")
        false_id = names.index("cogal.value.false")
        true_id = names.index("cogal.value.true")
    except ValueError as exc:
        raise ValueError(BOOLEAN_TOKEN_ABI_DRIFT) from exc
    left_prefix = _expression_prefix(
        logic, expression["args"][0], assignments, graph)
    right_prefix = _expression_prefix(
        logic, expression["args"][1], assignments, graph)
    tokens = [
        task, root,
        premise, left, bind, *left_prefix,
        separator,
        premise, right, bind, *right_prefix,
        separator,
        bind,
    ]
    for name, value in sorted(assignments.items()):
        if name not in ("P", "Q") or type(value) is not bool:
            raise ValueError(BOOLEAN_LANDMARK_RECORD_INVALID)
        tokens.extend((
            names.index("cogal.variable." + name),
            true_id if value else false_id,
        ))
    tokens.append(end)
    if not 1 <= len(tokens) <= MAX_BOOLEAN_CONTEXT_TOKENS:
        raise ValueError(BOOLEAN_CONTEXT_LENGTH)
    return tokens


def _truth_expressions(logic, truth: bool, operator: str) -> tuple[tuple[dict, dict], ...]:
    result = []
    if operator == "NOT":
        for source in ("literal", "P", "Q"):
            for depth in range(7):
                base_truth = truth if depth % 2 == 0 else not truth
                if source == "literal":
                    expression, env = logic.literal(base_truth), {}
                else:
                    expression, env = logic.variable(source), {source: base_truth}
                for _ in range(depth):
                    expression = logic.apply("NOT", expression)
                result.append((expression, env))
        return tuple(result)
    wrappers = {
        "AND": lambda x: logic.apply("AND", x, logic.literal(True)),
        "OR": lambda x: logic.apply("OR", x, logic.literal(False)),
        "XOR": lambda x: logic.apply("XOR", x, logic.literal(False)),
        "IFF": lambda x: logic.apply("IFF", x, logic.literal(True)),
        "IMPLIES": lambda x: logic.apply("IMPLIES", logic.literal(True), x),
    }
    wrap = wrappers[operator]
    for source in ("literal", "P", "Q"):
        if source == "literal":
            base, env = logic.literal(truth), {}
        else:
            base, env = logic.variable(source), {source: truth}
        expression = base
        for _ in range(6):
            result.append((expression, dict(env)))
            expression = wrap(expression)
    return tuple(result)


def _split_three(total: int) -> tuple[int, int, int]:
    base, remainder = divmod(total, 3)
    return tuple(base + (1 if index < remainder else 0)
                 for index in range(3))


def _u7c_pattern_counts(op: str, each: int) -> dict[tuple[bool, ...], int]:
    half = each // 2
    low, high = half // 2, half - half // 2
    if op == "NOT":
        return {(False,): half, (True,): half}
    if op == "AND":
        tf, ft, ff = _split_three(half)
        return {
            pattern: count
            for pattern, count in (
                ((True, True), half),
                ((True, False), tf),
                ((False, True), ft),
                ((False, False), ff),
            )
            if count
        }
    if op == "OR":
        return {(False, False): half, (True, False): low, (False, True): high}
    if op == "IMPLIES":
        tt, ff, ft = _split_three(half)
        return {
            pattern: count
            for pattern, count in (
                ((True, False), half),
                ((True, True), tt),
                ((False, False), ff),
                ((False, True), ft),
            )
            if count
        }
    if op == "XOR":
        return {(False, True): low, (True, False): high,
                (False, False): low, (True, True): high}
    if op == "IFF":
        return {(False, False): low, (True, True): high,
                (False, True): low, (True, False): high}
    raise ValueError(UNKNOWN_OPERATOR)


def draw_connectives(legacy_root: Path, graph: dict, *, seed: int,
                     each: int = ASSESSMENT_ITEMS_PER_CAPABILITY,
                     capability: str | None = None) -> tuple[dict, ...]:
    if type(seed) is not int or type(each) is not int or each < 4 or each % 2:
        raise ValueError("GRADE_B_BALANCED_EVEN_SAMPLE_REQUIRED")
    logic = _logic_source(legacy_root)
    _, _, source_graph, _, _ = read_sources(legacy_root)
    if (graph["tokens"][:len(source_graph["tokens"])] != source_graph["tokens"] or
            len(graph["tokens"]) < len(source_graph["tokens"])):
        raise ValueError("GRADE_B_FROZEN_TOKEN_PREFIX_MISMATCH")
    selected = (CONNECTIVES if capability is None else
                (capability.removeprefix("B."),))
    if not selected or any(op not in CONNECTIVES for op in selected):
        raise ValueError(UNKNOWN_OPERATOR)
    result = []
    for op in selected:
        rng = random.Random(_digest([GENERATOR, seed, op]))
        pools = {truth: list(_truth_expressions(logic, truth, op))
                 for truth in (False, True)}
        op_rows = []
        seen = set()
        for pattern, count in _u7c_pattern_counts(op, each).items():
            candidates = ([(term,) for term in pools[pattern[0]]]
                          if len(pattern) == 1 else
                          [(left, right) for left in pools[pattern[0]]
                           for right in pools[pattern[1]]])
            rng.shuffle(candidates)
            for terms in candidates:
                operands = []
                env = {}
                conflict = False
                for operand, bindings in terms:
                    if any(name in env and env[name] != value
                           for name, value in bindings.items()):
                        conflict = True
                        break
                    env.update(bindings)
                    operands.append(operand)
                if conflict:
                    continue
                expression = logic.apply(op, *operands)
                record = logic.evaluation_record(expression, env)
                record["query"] = expression
                if op in OUTER_LANDMARK_CONNECTIVES:
                    record["presentation"] = OUTER_LANDMARK_PRESENTATION
                source_id = source_record_identity(record)
                identity = capability_row_identity("B." + op, record)
                if identity in seen:
                    continue
                gold_bool = logic.gold(record)
                gold = "TRUE" if gold_bool else "FALSE"
                if (gold_bool != logic.gold(record, independent=True) or
                        independent_oracle(record, "B." + op) != gold or
                        gold_bool != independent_truth(op, pattern)):
                    raise ValueError("GRADE_B_THREE_ORACLE_DISAGREEMENT")
                seen.add(identity)
                op_rows.append({
                    "id": identity, "source_id": source_id,
                    "capability": "B." + op, "answer_kind": "binary",
                    "gold": gold, "record": record,
                    "tokens": _encode_connective_record(
                        logic, record, graph, "B." + op),
                    "oracle": ORACLE_VERSION, "generator": GENERATOR,
                    "operand_truths": list(pattern),
                    "root": "cogal.operator." + op,
                })
                if sum(tuple(row["operand_truths"]) == pattern for row in op_rows) == count:
                    break
            else:
                raise ValueError("GRADE_B_OPERATOR_VARIATION_EXHAUSTED:" + op)
        rng.shuffle(op_rows)
        result.extend(op_rows)
    return tuple(result)


def independent_truth(op: str, values: tuple[bool, ...]) -> bool:
    """Pure generator-side classification used only to choose balanced cases."""
    if op == "NOT": return not values[0]
    a, b = values
    if op == "AND": return a and b
    if op == "OR": return a or b
    if op == "XOR": return a != b
    if op == "IMPLIES": return not a or b
    if op == "IFF": return a == b
    raise ValueError(UNKNOWN_OPERATOR)
BOOLEAN_SOURCE_ROOT_MISMATCH = "GRADE_B_BOOLEAN_SOURCE_ROOT_MISMATCH"
BOOLEAN_TOKEN_ABI_DRIFT = "GRADE_B_BOOLEAN_TOKEN_ABI_DRIFT"
BOOLEAN_CONTEXT_LENGTH = "GRADE_B_BOOLEAN_CONTEXT_LENGTH"
BOOLEAN_LANDMARK_RECORD_INVALID = "GRADE_B_BOOLEAN_LANDMARK_RECORD_INVALID"
UNKNOWN_OPERATOR = "GRADE_B_UNKNOWN_OPERATOR"
