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


VERSION = "bilqis.mlx.boolean-association-bridge/20261018-v2"


def constructor_digest() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _truth(gold: str) -> bool:
    if gold == "TRUE":
        return True
    if gold == "FALSE":
        return False
    raise ValueError("BOOLEAN_ASSOCIATION_CHILD_NOT_BOOLEAN")


def compose_assertions(assertions: tuple[dict, ...] | list[dict], graph: dict, *,
                       seed: int, count: int = 4, association_grade: str,
                       operator: str | None = None) -> tuple[dict, ...]:
    """Compose opaque source assertions with Grade-B connectives.

    When ``operator`` is supplied, every bridge example rehearses that active
    connective. Otherwise connectives are sampled for broad bridge coverage.
    Child assertions are sampled without regard to truth values and the
    independent truth function computes the result.
    """
    if (type(seed) is not int or type(count) is not int or count < 2 or count % 2 or
            association_grade not in ("A", "C")):
        raise ValueError("BOOLEAN_ASSOCIATION_INVALID_DRAW")
    tokens = graph.get("tokens") or []
    mapping = {symbol: index for index, symbol in enumerate(tokens)}
    if operator is not None and operator not in CONNECTIVES:
        raise ValueError("BOOLEAN_ASSOCIATION_UNKNOWN_OPERATOR")
    broad_choices = tuple(op for op in CONNECTIVES if op != "NOT")
    choices = (operator,) if operator is not None else broad_choices
    required = {"task.evaluate", "syntax.end",
                *("cogal.operator." + op for op in choices)}
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
        selected_operator = operator if operator is not None else rng.choice(broad_choices)
        for _ in range(5000):
            if selected_operator == "NOT":
                children_rows = (rng.choice(pool),)
            else:
                children_rows = tuple(rng.sample(pool, 2))
            values = tuple(_truth(child["gold"]) for child in children_rows)
            expected = independent_truth(selected_operator, values)
            # Each complete child question is an opaque proposition with its
            # own source/world envelope. Grade B owns only the outer connective.
            ids = [mapping["task.evaluate"], mapping["cogal.operator." + selected_operator]]
            for child in children_rows:
                ids.extend(child["tokens"])
            ids.append(end)
            if len(ids) > 96:
                continue
            identity = digest((VERSION, association_grade, selected_operator, expected,
                               *(child["id"] for child in children_rows), ids))
            if identity in seen:
                continue
            seen.add(identity)
            children = tuple({
                "id": child["id"], "source_id": child.get("source_id", child["id"]),
                "capability": child["capability"], "gold": child["gold"],
                "oracle": child.get("oracle"), "generator": child.get("generator"),
            } for child in children_rows)
            result.append({
                "id": identity, "source_id": identity,
                "capability": "B." + selected_operator, "answer_kind": "binary",
                "gold": "TRUE" if expected else "FALSE", "tokens": ids,
                "record": {"task": VERSION, "operator": selected_operator,
                           "children": children},
                "operand_truths": list(values),
                "root": "cogal.operator." + selected_operator,
                "oracle": "bilqis_mlx.live_grade_b.independent_truth",
                "generator": VERSION, "association_grade": association_grade,
            })
            break
        else:
            raise ValueError("BOOLEAN_ASSOCIATION_VARIATION_EXHAUSTED")
    return tuple(result)


def draw_grade_associations(legacy_root: Path, graph: dict, *, grade: str, seed: int,
                            maximum: int | None = None, count: int = 4,
                            operator: str | None = None) -> tuple[dict, ...]:
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
                              association_grade=grade, operator=operator)


def draw_b_grade_bridges(legacy_root: Path, graph: dict, *, seed: int,
                         maximum: int, per_source: int = 4,
                         capability: str | None = None) -> tuple[dict, ...]:
    """Borrow A/C propositions while assigning every new question to Grade B."""
    if type(per_source) is not int or per_source < 2 or per_source % 2:
        raise ValueError("BOOLEAN_ASSOCIATION_PER_SOURCE_MUST_BE_POSITIVE_EVEN")
    operator = capability.removeprefix("B.") if capability is not None else None
    if capability is not None and (not capability.startswith("B.") or operator not in CONNECTIVES):
        raise ValueError("BOOLEAN_ASSOCIATION_UNKNOWN_CAPABILITY")
    a_seed = int(digest((VERSION, "A", seed))[:16], 16)
    c_seed = int(digest((VERSION, "C", seed))[:16], 16)
    rows = (*draw_grade_associations(
                legacy_root, graph, grade="A", seed=a_seed,
                maximum=maximum, count=per_source, operator=operator),
            *draw_grade_associations(
                legacy_root, graph, grade="C", seed=c_seed,
                maximum=maximum, count=per_source, operator=operator))
    if (len(rows) != per_source * 2 or
            any(not row["capability"].startswith("B.") for row in rows) or
            {row["association_grade"] for row in rows} != {"A", "C"}):
        raise ValueError("BOOLEAN_ASSOCIATION_B_GRADE_OWNERSHIP_DRIFT")
    return tuple(rows)
