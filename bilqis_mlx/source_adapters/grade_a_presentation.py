"""Current Grade-A source presentation without rewriting historical constructors.

The original Grade-A source generator remains immutable compatibility evidence.
This adapter adds source-valid irrelevant set context to MEMBER records so fresh
assessment can keep drawing independent specimen identities after long teaching
runs have exposed most of the tiny historical finite world.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import random

from ..grade_a_oracle import evaluate as independent_oracle
from ..grade_a_probe import read_sources
from ..live_grade_a import draw_predicates, generator_source_digest


VERSION = "bilqis.mlx.grade-a-member-context/v1"
MEMBER_CONTEXT_VARIATION = "member-decoy-set-context-v1"


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def constructor_digest() -> str:
    """Bind the current presentation layer plus the immutable base generator."""
    return _digest({
        "base_generator_sha256": generator_source_digest(),
        "presentation_file_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "version": VERSION,
    })


def _member_context_row(row: dict, *, seed: int, development) -> dict:
    record = copy.deepcopy(row["record"])
    world = record.get("world")
    sets = world.get("sets") if isinstance(world, dict) else None
    base = world.get("base") if isinstance(world, dict) else None
    universe = base.get("entities") if isinstance(base, dict) else None
    if (not isinstance(sets, dict) or "K0" not in sets or
            not isinstance(universe, list) or not universe):
        raise ValueError("FACTORY_GRADE_A_MEMBER_CONTEXT_SOURCE_SHAPE_INVALID")

    rng = random.Random(_digest([VERSION, seed, row["id"]]))
    mask = 1 + rng.randrange((1 << len(universe)) - 1)
    sets["K1"] = [entity for index, entity in enumerate(universe)
                  if mask & (1 << index)]

    gold = development.evaluate(record)
    if (gold != development.independent_evaluate(record) or
            gold != independent_oracle(record, "A.MEMBER") or
            gold != row["gold"]):
        raise ValueError("FACTORY_GRADE_A_MEMBER_CONTEXT_ORACLE_DRIFT")
    tokens = list(development.encode(record))
    identity = _digest(record)
    return {
        **row,
        "id": identity,
        "source_id": identity,
        "tokens": tokens,
        "record": record,
    }


def draw_a(*, source_root, graph, course, capability, seed, each):
    """Draw the admitted Grade-A source, widening only MEMBER presentation."""
    del course
    rows = draw_predicates(
        source_root, graph, seed=seed, capability=capability, each=each)
    if capability != "A.MEMBER":
        return rows
    _, development, *_ = read_sources(source_root)
    result = tuple(
        _member_context_row(row, seed=seed, development=development)
        for row in rows)
    if len({row["id"] for row in result}) != len(result):
        raise ValueError("FACTORY_GRADE_A_MEMBER_CONTEXT_IDENTITY_COLLISION")
    return result
