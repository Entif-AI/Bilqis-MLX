"""Cross-grade Boolean association questions over opaque source assertions.

Each child row owns its source semantics and oracle. This module does not
inspect a child record or reconstruct its world. It reads only the child's
already source-verified TRUE/FALSE result, chooses a Grade-B connective first,
and computes the composite result with the existing independent truth function.

This is an explicitly opted-in lesson adjunct. It is deliberately not part of
an admitted grade exam rubric.
"""
from __future__ import annotations

import hashlib
import random
from pathlib import Path

from .generated_assessment import digest
from .grade_b_oracle import CONNECTIVES
from .live_grade_b import independent_truth


VERSION = "bilqis.mlx.boolean-association-bridge/20261018-v1"


def constructor_digest() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _truth(gold: str) -> bool:
    if gold == "TRUE":
        return True
    if gold == "FALSE":
        return False
    raise ValueError("BOOLEAN_ASSOCIATION_CHILD_NOT_BOOLEAN")


def compose_assertions(assertions: tuple[dict, ...] | list[dict], graph: dict, *,
                       seed: int, count: int = 4, association_grade: str) -> tuple[dict, ...]:
    """Randomly compose opaque binary assertions with Grade-B connectives.

    The connective is selected first.  Two child assertions are then sampled
    without regard to their truth values, and ``independent_truth`` computes
    the result.  No inverse lookup and no label-balancing rejection step can
    bias which semantic associations the student sees.
    """
    if (type(seed) is not int or type(count) is not int or count < 2 or count % 2 or
            association_grade not in ("A", "C")):
        raise ValueError("BOOLEAN_ASSOCIATION_INVALID_DRAW")
    tokens = graph.get("tokens") or []
    mapping = {symbol: index for index, symbol in enumerate(tokens)}
    binary = tuple(op for op in CONNECTIVES if op != "NOT")
    required = {"task.evaluate", "syntax.end",
                *("cogal.operator." + op for op in binary)}
    if not required <= set(mapping):
        raise ValueError("BOOLEAN_ASSOCIATION_REQUIRED_TOKENS_MISSING")
    end = mapping["syntax.end"]
    pool = []
    for row in assertions:
        item = row.get("tokens")
        if (row.get("answer_kind") == "binary" and row.get("gold") in ("TRUE", "FALSE") and
                isinstance(item, list) and len(item) >= 2 and item[-1] == end and
                all(type(value) is int and 0 <= value < len(tokens) for value in item)):
            pool.append(row)
    if len(pool) < 2 or {row["gold"] for row in pool} != {"TRUE", "FALSE"}:
        raise ValueError("BOOLEAN_ASSOCIATION_NEEDS_MIXED_OPAQUE_ASSERTIONS")

    rng = random.Random(digest((VERSION, association_grade, seed)))
    result, seen = [], set()
    for index in range(count):
        operator = rng.choice(binary)
        for _ in range(5000):
            left, right = rng.sample(pool, 2)
            values = (_truth(left["gold"]), _truth(right["gold"]))
            expected = independent_truth(operator, values)
            # Each complete child question is an opaque proposition with its
            # own source/world envelope. Grade B owns only the outer connective.
            ids = [mapping["task.evaluate"], mapping["cogal.operator." + operator],
                   *left["tokens"], *right["tokens"], end]
            if len(ids) > 96:
                continue
            identity = digest((VERSION, association_grade, operator, expected,
                               left["id"], right["id"], ids))
            if identity in seen:
                continue
            seen.add(identity)
            children = tuple({
                "id": child["id"], "source_id": child.get("source_id", child["id"]),
                "capability": child["capability"], "gold": child["gold"],
                "oracle": child.get("oracle"), "generator": child.get("generator"),
            } for child in (left, right))
            result.append({
                "id": identity, "source_id": identity,
                "capability": "B." + operator, "answer_kind": "binary",
                "gold": "TRUE" if expected else "FALSE", "tokens": ids,
                "record": {"task": VERSION, "operator": operator,
                           "children": children},
                "operand_truths": list(values), "root": "cogal.operator." + operator,
                "oracle": "bilqis_mlx.live_grade_b.independent_truth",
                "generator": VERSION, "association_grade": association_grade,
            })
            break
        else:
            raise ValueError("BOOLEAN_ASSOCIATION_VARIATION_EXHAUSTED")
    return tuple(result)


def draw_grade_associations(legacy_root: Path, graph: dict, *, grade: str, seed: int,
                            maximum: int | None = None, count: int = 4) -> tuple[dict, ...]:
    """Draw four association questions from fresh A or C source assertions."""
    if grade == "A":
        from .live_grade_a import draw_predicates
        source_rows = draw_predicates(legacy_root, graph, seed=seed, each=max(4, count))
    elif grade == "C":
        if type(maximum) is not int:
            raise ValueError("BOOLEAN_ASSOCIATION_C_REQUIRES_NUMERIC_SCOPE")
        from .live_grade_c import draw
        # Two source triplets per capability provide TRUE/FALSE equality views
        # while leaving direct numeric outputs encapsulated and unused here.
        source_rows = draw(graph, seed=seed, maximum=maximum, each=max(6, count))
    else:
        raise ValueError("BOOLEAN_ASSOCIATION_GRADE_MUST_BE_A_OR_C")
    return compose_assertions(source_rows, graph, seed=seed, count=count,
                              association_grade=grade)


def draw_b_grade_bridges(legacy_root: Path, graph: dict, *, seed: int,
                         maximum: int, per_source: int = 4) -> tuple[dict, ...]:
    """Borrow A/C propositions while assigning every new question to Grade B."""
    if type(per_source) is not int or per_source < 2 or per_source % 2:
        raise ValueError("BOOLEAN_ASSOCIATION_PER_SOURCE_MUST_BE_POSITIVE_EVEN")
    a_seed = int(digest((VERSION, "A", seed))[:16], 16)
    c_seed = int(digest((VERSION, "C", seed))[:16], 16)
    rows = (*draw_grade_associations(
                legacy_root, graph, grade="A", seed=a_seed,
                maximum=maximum, count=per_source),
            *draw_grade_associations(
                legacy_root, graph, grade="C", seed=c_seed,
                maximum=maximum, count=per_source))
    if (len(rows) != per_source * 2 or
            any(not row["capability"].startswith("B.") for row in rows) or
            {row["association_grade"] for row in rows} != {"A", "C"}):
        raise ValueError("BOOLEAN_ASSOCIATION_B_GRADE_OWNERSHIP_DRIFT")
    return tuple(rows)
