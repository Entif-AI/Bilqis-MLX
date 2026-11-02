"""Versioned derived Grade-B Boolean composition capability."""
from __future__ import annotations

from .paths import source_path

from collections import Counter
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random

from .boolean_composite_oracle import VERSION as ORACLE, evaluate as independent_evaluate
from .curriculum import AnswerFamily, BINARY, Capability, Course
from .grade_a_probe import read_sources
from .grade_b_oracle import CONNECTIVES
from .live_grade_b import (
    PREREQUISITES, RELEASE as PARENT_RELEASE,
    _encode_logic_record, _logic_source, capability_row_identity,
    source_record_identity,
    constructor_digest as parent_boolean_constructor_digest,
)

CAPABILITY = "B.COMPOSITE"
GENERATOR = "bilqis.mlx.grade-b-composite-constructor/v1"
RELEASE = "bilqis.mlx.grade-a-b-composite/20261019-v1"
ASSESSMENT_ITEMS = 12


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()


def constructor_digest() -> str:
    return _digest({
        "files": {name: hashlib.sha256(source_path(name).read_bytes()).hexdigest()
                  for name in ("boolean_composite.py", "boolean_composite_oracle.py")},
        "parent_boolean_constructor_sha256": parent_boolean_constructor_digest(),
    })


def _leaf_count(operators: tuple[str, ...]) -> int:
    return len(operators) + 1 - (1 if "NOT" in operators else 0)


def _expression(logic, operators: tuple[str, ...], leaves: tuple[dict, ...]):
    if len(operators) == 2:
        outer, inner = operators
        if outer == "NOT":
            return logic.apply("NOT", logic.apply(inner, leaves[0], leaves[1]))
        if inner == "NOT":
            return logic.apply(outer, logic.apply("NOT", leaves[0]), leaves[1])
        return logic.apply(outer, logic.apply(inner, leaves[0], leaves[1]), leaves[2])
    if len(operators) != 3:
        raise ValueError("GRADE_B_COMPOSITE_OPERATOR_WIDTH")
    outer, left, right = operators
    if outer == "NOT":
        return logic.apply("NOT", logic.apply(
            left, logic.apply(right, leaves[0], leaves[1]), leaves[2]))
    if left == "NOT":
        return logic.apply(outer, logic.apply("NOT", leaves[0]),
                           logic.apply(right, leaves[1], leaves[2]))
    if right == "NOT":
        return logic.apply(outer, logic.apply(left, leaves[0], leaves[1]),
                           logic.apply("NOT", leaves[2]))
    return logic.apply(outer, logic.apply(left, leaves[0], leaves[1]),
                       logic.apply(right, leaves[2], leaves[3]))


def _operator_domain(operators) -> tuple[str, ...]:
    operators = tuple(operators)
    if (len(operators) < 2 or len(set(operators)) != len(operators) or
            not set(operators) <= set(CONNECTIVES) or
            operators != tuple(op for op in CONNECTIVES if op in operators)):
        raise ValueError("GRADE_B_COMPOSITE_OPERATOR_DOMAIN_INVALID")
    return operators


def _schedule(rng: random.Random, operators=CONNECTIVES
              ) -> tuple[tuple[int, int, tuple[str, ...]], ...]:
    operators = _operator_domain(operators)
    if operators != tuple(CONNECTIVES):
        pairs = [(left, right) for left in operators for right in operators]
        rows = []
        pass_index = 0
        while len(rows) < ASSESSMENT_ITEMS:
            current = list(pairs)
            rng.shuffle(current)
            for pair in current:
                rows.append((2, pass_index, tuple(pair)))
                if len(rows) == ASSESSMENT_ITEMS:
                    break
            pass_index += 1
        return tuple(rows)
    rows = []
    for pass_index in range(2):
        operators = list(CONNECTIVES)
        rng.shuffle(operators)
        rows.extend((2, pass_index, tuple(operators[index:index + 2]))
                    for index in (0, 2, 4))
    for pass_index in range(3):
        operators = list(CONNECTIVES)
        rng.shuffle(operators)
        rows.extend((3, pass_index, tuple(operators[index:index + 3]))
                    for index in (0, 3))
    return tuple(rows)


def _cycle(legacy_root: Path, graph: dict, *, seed: int, cycle: int,
           operators=CONNECTIVES) -> tuple[dict, ...]:
    operators = _operator_domain(operators)
    logic = _logic_source(legacy_root)
    _, _, source_graph, _, _ = read_sources(legacy_root)
    if (graph["tokens"][:len(source_graph["tokens"])] != source_graph["tokens"] or
            len(graph["tokens"]) < len(source_graph["tokens"])):
        raise ValueError("GRADE_B_COMPOSITE_FROZEN_TOKEN_PREFIX_MISMATCH")
    material = ([GENERATOR, seed, cycle] if operators == tuple(CONNECTIVES)
                else [GENERATOR, "profile", list(operators), seed, cycle])
    rng = random.Random(_digest(material))
    schedule = _schedule(rng, operators)
    appearances = Counter(op for _, _, operators in schedule for op in operators)
    default_coverage_is_exact = (
        operators != tuple(CONNECTIVES) or
        appearances == Counter({op: 5 for op in CONNECTIVES}))
    if not default_coverage_is_exact or set(appearances) != set(operators):
        raise ValueError("GRADE_B_COMPOSITE_OPERATOR_COVERAGE_DRIFT")
    true_count = rng.choice((4, 5, 7, 8))
    expected = [True] * true_count + [False] * (ASSESSMENT_ITEMS - true_count)
    rng.shuffle(expected)
    result, seen = [], set()
    for index, ((width, pass_index, operators), wanted) in enumerate(zip(schedule, expected)):
        for _ in range(5000):
            leaf_truths = tuple(rng.choice((False, True))
                                for _ in range(_leaf_count(operators)))
            variants = []
            env = {}
            conflict = False
            for truth in leaf_truths:
                choice = rng.randrange(3)
                if choice == 0:
                    variants.append(logic.literal(truth))
                    continue
                name = "P" if choice == 1 else "Q"
                if name in env and env[name] != truth:
                    conflict = True
                    break
                env[name] = truth
                variants.append(logic.variable(name))
            if conflict:
                continue
            leaves = tuple(variants)
            query = _expression(logic, operators, leaves)
            record = logic.evaluation_record(query, env)
            record["query"] = query
            gold_bool = logic.gold(record)
            gold = "TRUE" if gold_bool else "FALSE"
            if (gold_bool != logic.gold(record, independent=True) or
                    gold != independent_evaluate(record) or
                    gold_bool != wanted):
                continue
            tokens = _encode_logic_record(logic, record, graph)
            source_id = source_record_identity(record)
            identity = capability_row_identity(CAPABILITY, record)
            if identity in seen:
                continue
            break
        else:
            raise ValueError("GRADE_B_COMPOSITE_VARIATION_EXHAUSTED")
        seen.add(identity)
        result.append({
            "id": identity, "source_id": source_id, "capability": CAPABILITY,
            "answer_kind": "binary", "gold": gold, "record": record,
            "tokens": tokens, "oracle": ORACLE,
            "generator": GENERATOR, "operators": list(operators),
            "operator_roots": ["cogal.operator." + op for op in operators],
            "composition_width": width, "composition_pass": pass_index,
            "root": "cogal.operator." + operators[0],
        })
    return tuple(result)


def draw_composite(legacy_root: Path, graph: dict, *, seed: int,
                   each: int = ASSESSMENT_ITEMS,
                   capability: str | None = CAPABILITY,
                   operators=CONNECTIVES) -> tuple[dict, ...]:
    if type(seed) is not int or type(each) is not int or each < 1:
        raise ValueError("GRADE_B_COMPOSITE_INVALID_DRAW")
    if capability not in (None, CAPABILITY):
        raise ValueError("GRADE_B_COMPOSITE_UNKNOWN_CAPABILITY")
    operators = _operator_domain(operators)
    rows = []
    cycle = 0
    while len(rows) < each:
        rows.extend(_cycle(
            legacy_root, graph, seed=seed, cycle=cycle,
            operators=operators))
        cycle += 1
    return tuple(rows[:each])


def build_course(previous: Course, legacy_root: Path) -> Course:
    if (not isinstance(previous, Course) or previous.version != PARENT_RELEASE or
            len(previous.grades) != 2 or previous.grades[-1].id != "B" or
            tuple(cap.id for cap in previous.grades[-1].capabilities) !=
            tuple("B." + op for op in CONNECTIVES)):
        raise ValueError("GRADE_B_COMPOSITE_REQUIRES_ADMITTED_BOOLEAN_PARENT")
    _, _, graph, _, _ = read_sources(legacy_root)
    witness = draw_composite(legacy_root, graph, seed=2026101901)
    roots = tuple("cogal.operator." + op for op in CONNECTIVES)
    cap = Capability(
        id=CAPABILITY, difficulty=previous.grades[-1].capabilities[0].difficulty,
        source_anchor="repo:bilqis_logic/kernel.py::TABLES+encode",
        taught_roots=roots, examined_roots=roots, prerequisites=PREREQUISITES,
        composed_of=(), answer_families=(AnswerFamily("binary", BINARY),),
        lesson_generator=GENERATOR, independent_oracle=ORACLE,
    )
    atomic = tuple(replace(item, lesson_generator=GENERATOR)
                   for item in previous.grades[-1].capabilities)
    counts = (*previous.grades[-1].exam_item_counts, (CAPABILITY, ASSESSMENT_ITEMS))
    seal = _digest({
        "parent_course_sha256": previous.digest(),
        "parent_b_rubric": previous.grades[-1].assessment_sha256,
        "generator": GENERATOR, "generator_code_sha256": constructor_digest(),
        "source_witness_sha256": _digest(witness),
        "items_per_capability": ASSESSMENT_ITEMS,
    })
    grade = replace(previous.grades[-1], capabilities=(*atomic, cap),
                    assessment_sha256=seal, exam_item_counts=counts,
                    teaching_stages=())
    course = replace(previous, grades=(*previous.grades[:-1], grade),
                     version=RELEASE, assessment_manifest_sha256=seal)
    if not course.executable:
        raise ValueError("GRADE_B_COMPOSITE_RELEASE_NOT_EXECUTABLE")
    return course
