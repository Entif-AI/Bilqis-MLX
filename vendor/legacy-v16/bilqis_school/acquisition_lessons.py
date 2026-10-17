"""Grade-local, source-partitioned acquisition lessons for the School50 student.

Unlike the B01 v4 experiment, this compiler does not ask an untrained student
to acquire every mathematical, Boolean and set relation on its first visit.
It retains the requested 16 concept triplets (48 evidence-only rows), with
real historical rehearsal and limited adjacent-grade preview.
"""
from __future__ import annotations

import copy
import random

from . import arithmetic
from . import bridge_foundation_lessons as foundation
from . import lessons
from . import spiral_numeric_lessons as numeric
from . import spiral_primitive_lessons as primitive
from . import spiral_semantic_bridge as bridge

VERSION = "bilqis.school50.acquisition-lessons/v1"
GRADES = ("B01", "B02", "B03", "B04", "B05", "B06", "B07")
TOPICS = {
    "B01": ("identity", "equality"),
    "B02": ("successor", "equality"),
    "B03": ("order", "ordering"),
    "B04": ("identity", "iff_math"),
    "B05": ("successor", "implies_math"),
    "B06": ("identity", "membership"),
    "B07": ("successor", "subset"),
}
HISTORICAL_REHEARSAL = (1, 5, 9, 10, 11, 12, 17, 19, 20, 22)


def _row(expression, operator, candidate, grade, stage, source_number,
         source_expression, difficulty, tranche, projection):
    proposition = arithmetic.operation(operator, copy.deepcopy(expression),
                                       arithmetic.atom(candidate))
    row = arithmetic.row(proposition, 20)
    meta = foundation._meta(stage, source_number, source_expression, difficulty,
                            tranche, projection, grade.lower())
    meta["grade"] = grade
    return dict(row, answer_kind="evidence", course_meta=meta)


def _basic_triplet(grade, stage, source_number, expression, tranche, opposite=False):
    """Minimal intervention pairs, without advanced logical families."""
    value = numeric._numeric(expression)
    if value >= arithmetic.MAX_NUMBER:
        raise ValueError("ACQUISITION_VALUE_OUTSIDE_PROPOSITION_ABI")
    if grade == "B03":
        operations = ((("LT", value, "order_false"),
                       ("LT", value+1, "order_true"),
                       ("LE", value-1, "order_equal_false"))
                      if opposite else
                      (("LT", value+1, "order_true"),
                       ("LT", value, "order_false"),
                       ("LE", value, "order_equal_true")))
        rows = [_row(expression, op, n, grade, stage, source_number,
                     expression, difficulty, tranche, projection)
                for difficulty, (op,n,projection) in
                zip(("low","medium","hard"),operations)]
    else:
        first = value+1 if opposite else value
        second = value if opposite else value+1
        rows = [
            _row(expression, "EQ", first, grade, stage, source_number,
                 expression, "low", tranche,
                 "equality_false" if opposite else "equality_true"),
            _row(expression, "EQ", second, grade, stage, source_number,
                 expression, "medium", tranche,
                 "equality_true" if opposite else "equality_false"),
        ]
        # Equality is symmetric. Changing operand direction remains inside
        # the verified numeric-source partition; an arbitrary ADD wrapper
        # would not (its new AST could map into the sealed partition).
        mirrored = arithmetic.operation("EQ", arithmetic.atom(first),
                                        copy.deepcopy(expression))
        peer = arithmetic.row(mirrored, 20)
        meta = foundation._meta(stage, source_number, expression, "hard",
                                tranche, ("mirrored_equality_false" if opposite
                                          else "mirrored_equality_true"), grade.lower())
        meta["grade"] = grade
        rows.append(dict(peer, answer_kind="evidence", course_meta=meta))
    expected=["FALSE","TRUE","FALSE"] if opposite else ["TRUE","FALSE","TRUE"]
    if [r["gold"] for r in rows] != expected:
        raise ValueError("ACQUISITION_MINIMAL_PAIR_ORACLE_DRIFT")
    if len({r["id"] for r in rows}) != 3:
        raise ValueError("ACQUISITION_DUPLICATE_PROJECTION")
    return rows


def triplet(grade, stage, source_number, expression, graph, rng, tranche,
            *, opposite=False):
    if grade not in TOPICS:
        raise ValueError("ACQUISITION_UNKNOWN_GRADE")
    family = TOPICS[grade][1]
    if family in ("equality", "ordering"):
        return _basic_triplet(grade, stage, source_number, expression, tranche,
                              opposite=opposite)
    rows = foundation.nonlocal_triplet(
        stage, source_number, expression, family, graph, rng, tranche=tranche,
        split="development" if tranche == "exam" else "train")
    for row in rows:
        row["course_meta"]["grade"] = grade
    return rows


def _append_concepts(result, seen, numbers, grade, count, graph, rng, method,
                     tranche, split):
    stage = TOPICS[grade][0]
    previous = None
    for index in range(count):
        options = foundation._choose_pairs(
            rng, stage, split, numbers, mode=method, previous_number=previous)
        for n, expression in options:
            try:
                rows = triplet(grade, stage, n, expression, graph, rng, tranche,
                               opposite=bool(index%2))
            except ValueError as error:
                if str(error) in ("BRIDGE_SET_PARTITION_EXHAUSTED",
                                  "BRIDGE_96_TOKEN_CONTEXT_OVERFLOW",
                                  "BRIDGE_FOUNDATION_NONLOCAL_CONTRAST_INVALID"):
                    continue
                raise
            if foundation._unique_add(result, seen, rows):
                numbers.add((stage,n))
                previous = n
                break
        else:
            raise ValueError("ACQUISITION_TRAIN_SOURCE_EXHAUSTED")


def compile_batch(grade, library, graph, rng, *, method="standard"):
    """One grade's concept, real G-grade rehearsal, and next-two previews."""
    if grade not in GRADES:
        raise ValueError("ACQUISITION_UNKNOWN_GRADE")
    if method not in ("standard","structural_equivalence","minimal_counterfactual"):
        raise ValueError("ACQUISITION_UNKNOWN_INSTRUCTION")
    index = GRADES.index(grade)
    future = GRADES[index+1:index+3]
    previews = min(4, 2*len(future))
    allocation = {"current":14-previews, "random_old":2, "preview":previews}
    result=[];seen=set();numbers=set()
    _append_concepts(result,seen,numbers,grade,allocation["current"],
                     graph,rng,method,"current","train")
    for i in range(allocation["random_old"]):
        # Spread genuine School50 rehearsal across its compiled 22-grade
        # history, rather than drilling only G09/G10 forever.
        origin=HISTORICAL_REHEARSAL[(index*3+i+rng.randrange(len(HISTORICAL_REHEARSAL))) %
                                    len(HISTORICAL_REHEARSAL)]
        for _ in range(300):
            rows = numeric.earlier_triplet(
                library,graph,rng,(f"G{origin:02d}",),depth=2)
            if not all(row["answer_kind"]=="evidence" and
                       primitive.admissible_rehearsal(row) for row in rows):
                continue
            if foundation._unique_add(result,seen,rows):
                for row in rows:
                    row["course_meta"]["retention"]=True
                    row["course_meta"]["tranche"]="random_old"
                break
        else:
            raise ValueError("ACQUISITION_HISTORIC_REHEARSAL_EXHAUSTED")
    for i in range(previews):
        next_grade=future[i%len(future)]
        _append_concepts(result,seen,numbers,next_grade,1,graph,rng,method,
                         "preview","train")
    foundation.validate_rows(result,graph,split="train")
    observed={tranche:sum(row["course_meta"]["tranche"]==tranche for row in result)
              for tranche in allocation}
    expected={key:count*3 for key,count in allocation.items()}
    if observed!=expected or len(result)!=48:
        raise ValueError("ACQUISITION_BATCH_ALLOCATION_DRIFT")
    if len({row["id"] for row in result})!=48:
        raise ValueError("ACQUISITION_DUPLICATE_TEACHING_ROW")
    return result,observed


def panel(grade, graph, *, fold, seed=20261013):
    """Four distinct developmental sources per panel; no sealed access."""
    if grade not in GRADES or fold not in ("primary","confirm"):
        raise ValueError("ACQUISITION_INVALID_PANEL")
    stage=TOPICS[grade][0]
    rng=random.Random(seed+GRADES.index(grade)*57111+
                      (791903 if fold=="confirm" else 0))
    options=list(primitive._bridge_options(stage,"development"))
    numbers=sorted({n for n,_ in options})
    selected_numbers=set(numbers[::2] if fold=="primary" else numbers[1::2])
    options=[(n,expression) for n,expression in options if n in selected_numbers]
    rng.shuffle(options)
    rows=[];seen=set();used=set()
    # A finite-world set projection can coincidentally have the same record
    # ID for DIFFERENT numerical sources. Number splits alone therefore do
    # not guarantee independent examination questions.
    forbidden=set()
    if fold=="confirm":
        forbidden={row["id"] for row in panel(grade,graph,fold="primary",seed=seed)}
    for index in range(4):
        for n,expression in options:
            if n in used:
                continue
            try:
                candidate=triplet(grade,stage,n,expression,graph,rng,"exam",
                                  opposite=bool(index%2))
            except ValueError as error:
                if str(error) in ("BRIDGE_SET_PARTITION_EXHAUSTED",
                                  "BRIDGE_96_TOKEN_CONTEXT_OVERFLOW",
                                  "BRIDGE_FOUNDATION_NONLOCAL_CONTRAST_INVALID"):
                    continue
                raise
            if any(row["id"] in forbidden for row in candidate):
                continue
            if foundation._unique_add(rows,seen,candidate):
                used.add(n)
                break
        else:
            raise ValueError("ACQUISITION_INDEPENDENT_PANEL_EXHAUSTED")
    foundation.validate_rows(rows,graph,split="development")
    if len(rows)!=12 or {r["gold"] for r in rows}!={"TRUE","FALSE"}:
        raise ValueError("ACQUISITION_PANEL_INVALID")
    return rows
