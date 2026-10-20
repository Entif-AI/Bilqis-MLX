"""Versioned derived Grade-B Boolean composition capability."""
from __future__ import annotations

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
    constructor_digest as parent_boolean_constructor_digest,
)
from .live_grade_b import _operand, _random_world

CAPABILITY = "B.COMPOSITE"
GENERATOR = "bilqis.mlx.grade-b-composite-constructor/v1"
RELEASE = "bilqis.mlx.grade-a-b-composite/20261019-v1"
ASSESSMENT_ITEMS = 12


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()


def constructor_digest() -> str:
    home = Path(__file__).resolve().parent
    return _digest({
        "files": {name: hashlib.sha256((home / name).read_bytes()).hexdigest()
                  for name in ("boolean_composite.py", "boolean_composite_oracle.py")},
        "parent_boolean_constructor_sha256": parent_boolean_constructor_digest(),
    })


def _leaf_count(operators: tuple[str, ...]) -> int:
    return len(operators) + 1 - (1 if "NOT" in operators else 0)


def _expression(micro, operators: tuple[str, ...], leaves: tuple[dict, ...]):
    if len(operators) == 2:
        outer, inner = operators
        if outer == "NOT":
            return micro.logic("NOT", micro.logic(inner, leaves[0], leaves[1]))
        if inner == "NOT":
            return micro.logic(outer, micro.logic("NOT", leaves[0]), leaves[1])
        return micro.logic(outer, micro.logic(inner, leaves[0], leaves[1]), leaves[2])
    if len(operators) != 3:
        raise ValueError("GRADE_B_COMPOSITE_OPERATOR_WIDTH")
    outer, left, right = operators
    if outer == "NOT":
        return micro.logic("NOT", micro.logic(
            left, micro.logic(right, leaves[0], leaves[1]), leaves[2]))
    if left == "NOT":
        return micro.logic(outer, micro.logic("NOT", leaves[0]),
                           micro.logic(right, leaves[1], leaves[2]))
    if right == "NOT":
        return micro.logic(outer, micro.logic(left, leaves[0], leaves[1]),
                           micro.logic("NOT", leaves[2]))
    return micro.logic(outer, micro.logic(left, leaves[0], leaves[1]),
                       micro.logic(right, leaves[2], leaves[3]))


def _schedule(rng: random.Random) -> tuple[tuple[int, int, tuple[str, ...]], ...]:
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


def _cycle(legacy_root: Path, graph: dict, *, seed: int, cycle: int) -> tuple[dict, ...]:
    micro, _, source_graph, _, _ = read_sources(legacy_root)
    if (graph["tokens"][:len(source_graph["tokens"])] != source_graph["tokens"] or
            len(graph["tokens"]) < len(source_graph["tokens"])):
        raise ValueError("GRADE_B_COMPOSITE_FROZEN_TOKEN_PREFIX_MISMATCH")
    rng = random.Random(_digest([GENERATOR, seed, cycle]))
    schedule = _schedule(rng)
    appearances = Counter(op for _, _, operators in schedule for op in operators)
    if appearances != Counter({op: 5 for op in CONNECTIVES}):
        raise ValueError("GRADE_B_COMPOSITE_OPERATOR_COVERAGE_DRIFT")
    true_count = rng.choice((4, 5, 7, 8))
    expected = [True] * true_count + [False] * (ASSESSMENT_ITEMS - true_count)
    rng.shuffle(expected)
    result, seen = [], set()
    for index, ((width, pass_index, operators), wanted) in enumerate(zip(schedule, expected)):
        n = 3 if index % 2 == 0 else 4
        for _ in range(5000):
            world = _random_world(micro, rng, n)
            leaves = tuple(_operand(micro, rng, world)
                           for _ in range(_leaf_count(operators)))
            query = _expression(micro, operators, leaves)
            record = micro.record(world, query)
            gold = micro.evaluate(record)
            if (gold != micro.independent_evaluate(record) or
                    gold != independent_evaluate(record) or
                    (gold == "TRUE") != wanted):
                continue
            tokens = list(micro.encode(record))
            identity = _digest(record)
            if (identity in seen or not 1 <= len(tokens) <= 96 or
                    min(tokens) < 0 or max(tokens) >= len(graph["tokens"])):
                continue
            break
        else:
            raise ValueError("GRADE_B_COMPOSITE_VARIATION_EXHAUSTED")
        seen.add(identity)
        result.append({
            "id": identity, "source_id": identity, "capability": CAPABILITY,
            "answer_kind": "binary", "gold": gold, "record": record,
            "tokens": tokens, "universe_size": n, "oracle": ORACLE,
            "generator": GENERATOR, "operators": list(operators),
            "operator_roots": ["cogal.operator." + op for op in operators],
            "composition_width": width, "composition_pass": pass_index,
            "root": "cogal.operator." + operators[0],
        })
    return tuple(result)


def draw_composite(legacy_root: Path, graph: dict, *, seed: int,
                   each: int = ASSESSMENT_ITEMS,
                   capability: str | None = CAPABILITY) -> tuple[dict, ...]:
    if type(seed) is not int or type(each) is not int or each < 1:
        raise ValueError("GRADE_B_COMPOSITE_INVALID_DRAW")
    if capability not in (None, CAPABILITY):
        raise ValueError("GRADE_B_COMPOSITE_UNKNOWN_CAPABILITY")
    rows = []
    cycle = 0
    while len(rows) < each:
        rows.extend(_cycle(legacy_root, graph, seed=seed, cycle=cycle))
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
        source_anchor="repo:bilqis_micro/kernel.py::_operation+_table",
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
