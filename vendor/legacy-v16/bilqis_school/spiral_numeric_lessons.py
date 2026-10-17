"""Direct-number mathematics for a cumulative School50 spiral.

Eight *new, namespaced* mathematics episodes follow historical G01..G22.
Each numerical update contains 10 novelty, 2 earlier-grade rehearsal, and
4 nonadjacent compositional low/medium/hard triplets (48 items). No G23 ID
is reused: G23..G33 remain reserved for the proposed New Ithkuil sequence.

Semantic labels are computed by TWO existing School50 interpreters. Numeric
rows deliberately contain no EQ candidate on the input: the student must
produce the value of the expression. No new vocabulary/parameters are needed.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import random

from bilqis_logic.kernel import digest
from bilqis_micro.graph import STATES
from . import arithmetic, lessons, spiral_semantic_bridge as bridge

VERSION = "bilqis.school50.numeric-spiral-lessons/v2"
DIFFICULTIES = ("low", "medium", "hard")
ALLOC = {"novelty": 10, "random_old": 2, "nonlocal": 4}


@dataclass(frozen=True)
class MathGrade:
    id: str
    concept: str
    focus_ops: tuple[str, ...]
    prerequisite_domains: tuple[str, ...]


GRADES = (
    MathGrade("M01", "addition", ("ADD",), ("legacy:G20",)),
    MathGrade("M02", "subtraction", ("SUB",), ("legacy:G20", "M01")),
    MathGrade("M03", "multiplication", ("MUL",), ("legacy:G20", "M01")),
    MathGrade("M04", "modulo-remainder", ("MOD",), ("legacy:G20", "M02")),
    MathGrade("M05", "mixed-addition-subtraction", ("ADD", "SUB"), ("M01", "M02")),
    MathGrade("M06", "distributive-numerical-evaluation", ("MUL", "ADD"), ("M01", "M03")),
    MathGrade("M07", "remainder-multiplication-composition", ("MOD", "MUL"), ("M03", "M04")),
    MathGrade("M08", "nested-multioperation-evaluation", ("ADD", "MUL", "MOD"),
              ("M01", "M03", "M04")),
)
MAP = {g.id: g for g in GRADES}
CYCLE = tuple(g.id for g in GRADES) + tuple(f"G{i:02d}" for i in range(1, 23))


def _n(rng, lo=1, hi=9):
    return arithmetic.atom(rng.randint(lo, hi))


def _op(name, a, b):
    return arithmetic.operation(name, a, b)


def _make(grade, rng, difficulty):
    """Different problem families, not eight aliases for one old G20 generator."""
    d = DIFFICULTIES.index(difficulty)
    if grade == "M01":
        if d == 0: return _op("ADD", _n(rng, 1, 10), _n(rng, 1, 10))
        if d == 1: return _op("ADD", _n(rng, 5, 19), _n(rng, 3, 16))
        return _op("ADD", _op("ADD", _n(rng, 8, 24), _n(rng, 4, 14)), _n(rng, 3, 21))
    if grade == "M02":
        if d == 0: return _op("SUB", _n(rng, 7, 18), _n(rng, 1, 8))
        if d == 1: return _op("SUB", _n(rng, 18, 49), _n(rng, 4, 17))
        return _op("SUB", _op("ADD", _n(rng, 20, 40), _n(rng, 10, 28)),
                   _op("ADD", _n(rng, 4, 12), _n(rng, 3, 9)))
    if grade == "M03":
        if d == 0: return _op("MUL", _n(rng, 2, 10), _n(rng, 2, 10))
        if d == 1: return _op("MUL", _n(rng, 4, 9), _n(rng, 3, 8))
        return _op("MUL", _op("ADD", _n(rng, 3, 8), _n(rng, 2, 5)), _n(rng, 3, 7))
    if grade == "M04":
        if d == 0: return _op("MOD", _n(rng, 7, 18), _n(rng, 2, 9))
        if d == 1: return _op("MOD", _n(rng, 24, 70), _n(rng, 4, 10))
        return _op("MOD", _op("ADD", _n(rng, 31, 59), _n(rng, 11, 24)), _n(rng, 6, 13))
    if grade == "M05":
        if d == 0: return _op("ADD", _op("SUB", _n(rng, 7, 12), _n(rng, 1, 3)), _n(rng, 1, 6))
        if d == 1: return _op("SUB", _op("ADD", _n(rng, 14, 28), _n(rng, 8, 17)), _n(rng, 9, 19))
        return _op("SUB", _op("ADD", _op("SUB", _n(rng, 18, 32), _n(rng, 2, 9)),
                                      _n(rng, 9, 21)), _n(rng, 4, 13))
    if grade == "M06":
        if d == 0: return _op("MUL", _n(rng, 2, 4), _op("ADD", _n(rng, 2, 4), _n(rng, 1, 3)))
        if d == 1:
            x, y, z = _n(rng, 3, 6), _n(rng, 2, 5), _n(rng, 1, 4)
            return _op("ADD", _op("MUL", copy.deepcopy(x), y), _op("MUL", x, z))
        return _op("MUL", _op("ADD", _n(rng, 2, 6), _n(rng, 1, 4)),
                   _op("ADD", _n(rng, 1, 4), _n(rng, 2, 5)))
    if grade == "M07":
        base = _op("MOD", _n(rng, 7, 24), _n(rng, 3, 7))
        if d == 0: return _op("ADD", base, _n(rng, 1, 6))
        if d == 1: return _op("MUL", base, _n(rng, 2, 6))
        return _op("SUB", _op("MUL", base, _n(rng, 4, 8)), _n(rng, 1, 3))
    if grade == "M08":
        mul = _op("MUL", _n(rng, 2, 6), _n(rng, 2, 5))
        rem = _op("MOD", _n(rng, 13, 27), _n(rng, 3, 9))
        if d == 0: return _op("ADD", mul, rem)
        if d == 1: return _op("SUB", _op("ADD", mul, _n(rng, 9, 16)), rem)
        return _op("ADD", _op("SUB", _op("ADD", mul, _n(rng, 12, 22)), rem),
                   _op("MOD", _n(rng, 30, 61), _n(rng, 5, 12)))
    raise ValueError("UNKNOWN_NUMERIC_GRADE")


def _nonlocal_expression(grade, rng, difficulty):
    """Two genuinely necessary arithmetic concepts, separated in grade space.

    These are math-math nonlocal bridges; they do NOT claim logic/math or
    Ithkuil transfer. Every subtree must affect the numeric gold.
    """
    d = DIFFICULTIES.index(difficulty)
    a = _n(rng, 2, 7 + d)
    b = _n(rng, 2, 5 + d)
    c = _n(rng, 15, 23 + d * 6)
    divisor = _n(rng, 3 + d, 6 + d)
    times = _op("MUL", a, b)
    residue = _op("MOD", c, divisor)
    if grade in ("M01", "M03", "M06", "M08"):
        return _op("ADD", times, residue)
    if grade in ("M02", "M05"):
        return _op("SUB", _op("ADD", times, _n(rng, 7, 12)), residue)
    if grade in ("M04", "M07"):
        return _op("MUL", _op("ADD", a, b), _op("ADD", residue, arithmetic.atom(1)))
    raise ValueError("NUMERIC_NONLOCAL_GRADE_MISSING")


def _numeric(expression):
    """Accept a numeric gold only when independent AST interpreters agree."""
    arithmetic.verify(expression)
    val = arithmetic.evaluate(expression)
    independent = _independent_value(expression)
    if val != independent or type(val) is not int:
        raise ValueError("NUMERIC_ORACLE_INDEPENDENCE_FAILURE")
    if not 0 <= val <= arithmetic.MAX_NUMBER:
        raise ValueError("NUMERIC_GOLD_OUTSIDE_ORIGINAL_0_100_ABI")
    return val


def _independent_value(expr):
    if expr["kind"] == "number":
        return int(expr["value"])
    if expr["kind"] != "op" or len(expr["args"]) != 2:
        raise ValueError("NUMERIC_UNSUPPORTED_FORMAL_AST")
    a, b = (_independent_value(child) for child in expr["args"])
    name = expr["name"]
    if name == "ADD":
        return a + b
    if name == "SUB":
        return a - b
    if name == "MUL":
        return a * b
    if name == "MOD":
        if b == 0:
            raise ValueError("NUMERIC_MODULO_BY_ZERO_UNDEFINED")
        return a % b
    raise ValueError("NUMERIC_UNKNOWN_OPERATOR")


def split_of(expression):
    return bridge.split_of(expression)


def admissible_legacy_math(row):
    """Keep old arithmetic training off new numeric development/sealed sources.

    Legacy School50 questions may expose a computed operand inside a proposed
    equality. Train uses the unchanged legacy generator, but it may resample
    a question whose source calculation is held out for numeric transfer.
    Standalone number literals cannot collide with direct-expression exams.
    """
    record=row["input"]
    if record.get("task") != arithmetic.VERSION:
        return True
    expression=record["expression"]
    operands=(expression["args"] if expression.get("name") in ("EQ","LT","LE")
              else (expression,))
    return all(node["kind"]=="number" or split_of(node)=="train"
               for node in operands)


def _path_numbers(expr, prefix=()):
    if expr["kind"] == "number":
        yield prefix
    else:
        for index, child in enumerate(expr["args"]):
            yield from _path_numbers(child, prefix + (index,))


def _child_at(expr, path):
    node = expr
    for index in path:
        node = node["args"][index]
    return node


def twin(expression, rng, *, restrict=None, required_split=None):
    """One leaf changes; the correct numeric answer MUST also change."""
    truth = _numeric(expression)
    paths = list(_path_numbers(expression))
    if restrict is not None:
        paths = [p for p in paths if p[:len(restrict)] == tuple(restrict)]
    rng.shuffle(paths)
    # A source expression has only finitely many one-leaf interventions.
    # Enumerate a broader, randomized bounded neighborhood and filter on
    # split *inside* the search. Repeatedly picking the same four invalid
    # interventions cannot make a train-partition example appear.
    deltas=list(range(-12,0))+list(range(1,13))
    for path in paths:
        rng.shuffle(deltas)
        for delta in deltas:
            altered = copy.deepcopy(expression)
            leaf = _child_at(altered, path)
            value = leaf["value"] + delta
            if not 0 <= value <= 100:
                continue
            leaf["value"] = value
            try:
                newer = _numeric(altered)
            except (ValueError, ZeroDivisionError):
                continue
            if newer != truth and (required_split is None or
                                   split_of(altered)==required_split):
                return altered
    raise ValueError("NUMERIC_COUNTERFACTUAL_NO_RELEVANT_LEAF")


def equivalent(expression, rng, *, preserve_root=False):
    """Change the expression's structure while preserving its numeric value.

    This is an invariance lesson, distinct from `twin`'s counterfactual
    answer-changing lesson. Both are independently checked against the source
    oracle, and neither contains the expected answer as an `EQ` candidate.
    """
    truth=_numeric(expression)
    altered=copy.deepcopy(expression)
    # For nonlocal questions keep the original two-factor root intact; only
    # rewrite *inside* one of its factors, so both remain independently testable.
    path=(rng.randrange(2),) if preserve_root else ()
    node=altered
    for index in path[:-1]:node=node["args"][index]
    key=path[-1] if path else None
    target=copy.deepcopy(node["args"][key] if path else node)
    n=arithmetic.atom(rng.randint(1,100))
    variants=(
        lambda: _op("ADD",target,arithmetic.atom(0)),
        lambda: _op("ADD",arithmetic.atom(0),target),
        lambda: _op("SUB",target,arithmetic.atom(0)),
        lambda: _op("MUL",target,arithmetic.atom(1)),
        lambda: _op("MUL",arithmetic.atom(1),target),
        lambda: _op("ADD",target,_op("SUB",n,copy.deepcopy(n))),
        lambda: _op("SUB",_op("ADD",target,n),copy.deepcopy(n)),
    )
    transformed=rng.choice(variants)()
    if path:node["args"][key]=transformed
    else:altered=transformed
    if _numeric(altered)!=truth or altered==expression:
        raise ValueError("NUMERIC_STRUCTURAL_EQUIVALENCE_NOT_VERIFIED")
    return altered


def _row(grade, expression, *, difficulty, tranche, triplet, mode):
    gold = _numeric(expression)
    record = {"task": arithmetic.VERSION, "expression": expression}
    return {"id": digest(record), "input": record, "gold": gold,
            "answer_kind": "numeric", "family": f"spiral-numeric:{grade}",
            "course_meta": {"grade": grade, "concept": MAP[grade].concept,
                            "difficulty": difficulty, "tranche": tranche,
                            "triplet_id": triplet, "mutation_mode": mode}}


def equality_bridge_triplet(grade, graph, rng, *, source=None, tranche="nonlocal"):
    """Three linked views of one source: value, true equality, false equality.

    This uses the original School50 math EQ grammar and evidence readout,
    rather than pretending Boolean-kernel or finite-set ASTs are interchangeable.
    The *source* owns the partition for all projections, not the EQ surface.
    """
    for _ in range(300 if source is None else 1):
        expression = source if source is not None else _nonlocal_expression(grade, rng, "low")
        try:
            value = _numeric(expression)
            if split_of(expression) != "train":
                continue
            if value >= arithmetic.MAX_NUMBER:
                continue
            arithmetic.verify(arithmetic.operation("EQ", expression, arithmetic.atom(value)))
            break
        except ValueError:
            continue
    else:
        raise ValueError("BRIDGE_TRAIN_SOURCE_EXHAUSTED")
    identity = digest(["shared-math-source/v1", expression])
    numeric = _row(grade, expression, difficulty="low", tranche=tranche,
                   triplet=identity, mode="cross_domain_equality")
    true_row = arithmetic.row(arithmetic.operation("EQ", copy.deepcopy(expression),
                                                  arithmetic.atom(value)), 20)
    false_row = arithmetic.row(arithmetic.operation("EQ", copy.deepcopy(expression),
                                                   arithmetic.atom(value + 1)), 20)
    rows = [numeric]
    for row, difficulty, projection in ((true_row, "medium", "equality_true"),
                                        (false_row, "hard", "equality_false")):
        rows.append(dict(row, answer_kind="evidence", course_meta={
            "grade":grade, "concept":MAP[grade].concept,
            "difficulty":difficulty, "tranche":tranche, "triplet_id":identity,
            "mutation_mode":"cross_domain_equality", "projection":projection,
            "semantic_source_id":identity, "split":split_of(expression)}))
    numeric["course_meta"].update({"projection":"numeric_value",
                                   "semantic_source_id":identity,
                                   "split":split_of(expression)})
    validate_rows([numeric],graph)
    lessons.valid_rows(rows[1:],graph)
    return rows


def cross_domain_triplet(grade, graph, rng, *, family, tranche="nonlocal",
                         split="train", source=None):
    """Train math, Boolean equivalence/implication and genuine finite sets.

    Difficulty progresses from the same mathematical value to its relational
    interpretation and finally to a composite proposition. The source math
    expression owns the split across all variants, including the set world.
    """
    if grade not in MAP or family not in bridge.FAMILIES:
        raise ValueError("BRIDGE_UNKNOWN_GRADE_OR_FAMILY")
    if source is not None:
        return bridge.linked_triplet(grade, MAP[grade].concept, source, family,
                                     graph, rng, tranche=tranche, split=split)
    for _ in range(400):
        expression = _make(grade, rng, "low" if int(grade[1:]) <= 4 else
                           rng.choice(("low", "medium")))
        try:
            _numeric(expression)
            if split_of(expression) != split:
                continue
            return bridge.linked_triplet(grade, MAP[grade].concept, expression,
                                         family, graph, rng, tranche=tranche,
                                         split=split)
        except ValueError as error:
            if str(error) in ("NUMERIC_GOLD_OUTSIDE_ORIGINAL_0_100_ABI",
                              "BRIDGE_SOURCE_NOT_ABI_INTEGER",
                              "BRIDGE_CANNOT_MAKE_MINIMAL_FALSE_NUMBER",
                              "BRIDGE_96_TOKEN_CONTEXT_OVERFLOW"):
                continue
            raise
    raise ValueError("BRIDGE_SOURCE_FAMILY_EXHAUSTED")


def triplet(grade, graph, rng, *, tranche, mode="standard", source=None):
    if grade not in MAP or tranche not in ("novelty", "nonlocal"):
        raise ValueError("NUMERIC_TRIPLET_INVALID_GRADE_OR_TRANCHE")
    if mode not in ("standard", "minimal_counterfactual", "structural_equivalence"):
        raise ValueError("NUMERIC_TRIPLET_INVALID_MUTATION_MODE")
    results = []
    for difficulty in DIFFICULTIES:
        for _ in range(300 if source is None else 32):
            expression = (source[difficulty] if source is not None else
                          _nonlocal_expression(grade, rng, difficulty)
                          if tranche == "nonlocal" else _make(grade, rng, difficulty))
            try:
                _numeric(expression)
                if source is not None:
                    expression = (equivalent(source[difficulty],rng,
                                             preserve_root=tranche=="nonlocal")
                                  if mode=="structural_equivalence" else
                                  twin(source[difficulty], rng,required_split="train"))
                if split_of(expression)!="train":
                    continue
                if tranche == "nonlocal":
                    # Both math factors are necessary, independently checked.
                    twin(expression, rng, restrict=(0,))
                    twin(expression, rng, restrict=(1,))
                break
            except ValueError:
                continue
        else:
            raise ValueError("NUMERIC_SEMANTIC_TRIPLET_EXHAUSTED")
        results.append(expression)
    marker = digest([grade, tranche, results])
    rows = [_row(grade, expression, difficulty=difficulty,
                 tranche=tranche, triplet=marker, mode=mode)
            for difficulty, expression in zip(DIFFICULTIES, results)]
    validate_rows(rows, graph)
    return rows


def validate_rows(rows, graph):
    mapping = {token: i for i, token in enumerate(graph["tokens"])}
    if not rows:
        raise ValueError("NUMERIC_EMPTY_QUESTION_SET")
    for row in rows:
        if row.get("answer_kind") != "numeric" or row["gold"] != _numeric(
                row["input"]["expression"]):
            raise ValueError("NUMERIC_QUESTION_ORACLE_OR_TYPE_DRIFT")
        if row["input"]["task"] != arithmetic.VERSION:
            raise ValueError("NUMERIC_QUESTION_TASK_NOT_PRESERVED")
        ids = arithmetic.encode(row["input"], mapping)
        if len(ids) > 96 or max(ids) >= len(graph["tokens"]):
            raise ValueError("NUMERIC_QUESTION_CONTEXT_INVALID")


def earlier_triplet(lib, graph, rng, previous, *, depth):
    origin = rng.choice(previous)
    if origin in MAP:
        rows = triplet(origin, graph, rng, tranche="novelty")
        return [dict(row, course_meta=dict(row["course_meta"], tranche="random_old",
                                               source_grade=origin)) for row in rows]
    old_grade = int(origin[1:])
    rows = []
    for i in range(3):
        for _ in range(100):
            try:
                packet = lib.one(old_grade, rng, depth=depth,
                                 prefer_composition=bool(i % 2),
                                 truth=bool(i % 2) if old_grade >= 19 else None)
                row = packet[i % len(packet)] if isinstance(packet, list) else packet
                lessons.valid_rows([row], graph)
                if not admissible_legacy_math(row):
                    continue
                break
            except ValueError as exc:
                if ("world exceeds preserved context" not in str(exc) and
                        "context" not in str(exc).lower()):
                    raise
        else:
            raise ValueError("NUMERIC_OLD_REHEARSAL_SOURCE_INVALID")
        rows.append(dict(row, answer_kind="evidence",
                         course_meta={"tranche": "random_old", "source_grade": origin,
                                      "difficulty": DIFFICULTIES[i],
                                      "difficulty_certification": "legacy_unverified"}))
    return rows


def compile_batch(grade, lib, graph, rng, *, mode="standard", previous=()):
    if grade not in MAP:
        raise ValueError("NUMERIC_COURSE_GRADE_NOT_FOUND")
    if not previous:
        raise ValueError("NUMERIC_NO_PREVIOUS_GRADE_REHEARSAL")
    result = []
    used = set()
    def add_distinct(rows):
        identifiers = [r["id"] for r in rows]
        if len(set(identifiers)) < len(identifiers) or used.intersection(identifiers):
            return False
        used.update(identifiers)
        result.extend(rows)
        return True
    for tranche in ("novelty", "nonlocal"):
        count = ALLOC[tranche]
        index = 0
        while index < count:
            for _attempt in range(300):
                original = (cross_domain_triplet(grade,graph,rng,
                             family=bridge.FAMILIES[index % len(bridge.FAMILIES)])
                            if tranche == "nonlocal" else
                            triplet(grade, graph, rng, tranche=tranche, mode=mode))
                ids = {r["id"] for r in original}
                if len(ids) != 3 or ids.intersection(used):
                    continue
                if tranche == "novelty" and mode in ("minimal_counterfactual","structural_equivalence") and index + 1 < count:
                    base = {r["course_meta"]["difficulty"]: r["input"]["expression"]
                            for r in original}
                    try:
                        revised = triplet(grade, graph, rng, tranche=tranche,
                                          mode=mode, source=base)
                    except ValueError as exc:
                        # Some seed expressions have no valid *minimal*
                        # intervention in the train partition. Choose a new
                        # source triplet, never corrupt the label or leak dev.
                        if str(exc) in ("NUMERIC_SEMANTIC_TRIPLET_EXHAUSTED",
                                        "NUMERIC_COUNTERFACTUAL_NO_RELEVANT_LEAF"):
                            continue
                        raise
                    combined_ids = [r["id"] for r in original + revised]
                    if len(set(combined_ids)) != 6 or used.intersection(combined_ids):
                        continue
                    add_distinct(original)
                    add_distinct(revised)
                    index += 2
                else:
                    add_distinct(original)
                    index += 1
                break
            else:
                raise ValueError("NUMERIC_TRIPLET_VARIETY_EXHAUSTED")
    for _ in range(ALLOC["random_old"]):
        for _attempt in range(300):
            if add_distinct(earlier_triplet(lib, graph, rng, previous, depth=2)):
                break
        else:
            raise ValueError("NUMERIC_OLD_TRIPLET_VARIETY_EXHAUSTED")
    actual = {t:sum(row["course_meta"]["tranche"] == t for row in result)
              for t in ALLOC}
    if actual != {"novelty":30,"random_old":6,"nonlocal":12} or len(result)!=48:
        raise ValueError("NUMERIC_TRANCHE_ALLOCATIONS_CHANGED")
    numeric_rows=[r for r in result if r["answer_kind"]=="numeric"]
    validate_rows(numeric_rows, graph)
    old_evidence = [r for r in result if r["answer_kind"]=="evidence"
                    and r["input"].get("task") != bridge.VERSION]
    if old_evidence:
        lessons.valid_rows(old_evidence, graph)
    composed = [r for r in result if r["input"].get("task") == bridge.VERSION]
    if composed:
        bridge.validate_rows(composed, graph, partition="train")
    if len({r["id"] for r in result}) != len(result):
        raise ValueError("NUMERIC_BATCH_DUPLICATE_QUESTIONS")
    return result, actual
