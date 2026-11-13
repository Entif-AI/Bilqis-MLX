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

from bilqis_mlx.errors import ErrorBus, SOURCE

from ..grade_a_oracle import evaluate as independent_oracle
from ..grade_a_probe import read_sources
from ..live_grade_a import draw_predicates, generator_source_digest


VERSION = "bilqis.mlx.grade-a-development-presentation/v3"
CONTEXT_VERSION = "bilqis.mlx.grade-a-contextual-presentation/v2"
MEMBER_CONTEXT_VARIATION = "member-decoy-set-context-v1"
IRRELEVANT_CONTEXT_VARIATION = "irrelevant-source-context-v2"
MIN_CONTEXT_ENTITY_COUNT = 2


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


def _library_for(record: dict, source_root):
    micro, development, *_ = read_sources(source_root)
    return micro if record["task"] == "micro" else development


def _verify_contextual_row(row: dict, record: dict, *, source_root) -> dict:
    library = _library_for(record, source_root)
    gold = library.evaluate(record)
    if (gold != library.independent_evaluate(record) or
            gold != independent_oracle(record, row["capability"]) or
            gold != row["gold"]):
        raise ErrorBus.legacy_error(SOURCE.GRADE_A.CONTEXT_ORACLE_DRIFT)
    identity = _digest(record)
    return {
        **row,
        "id": identity,
        "source_id": identity,
        "tokens": list(library.encode(record)),
        "record": record,
    }


def _micro_context_row(row: dict, *, seed: int, source_root) -> dict:
    """Add an irrelevant already-admitted relation fact to a Micro predicate."""
    record = copy.deepcopy(row["record"])
    world = record.get("world")
    entities = world.get("entities") if isinstance(world, dict) else None
    facts = world.get("facts") if isinstance(world, dict) else None
    if (not isinstance(entities, list) or len(entities) < MIN_CONTEXT_ENTITY_COUNT or
            not isinstance(facts, list)):
        raise ErrorBus.legacy_error(SOURCE.GRADE_A.MICRO_CONTEXT_SOURCE_SHAPE_INVALID)
    capability = row["capability"]
    relation = "LINK" if capability == "A.PARENT" else "PARENT"
    rng = random.Random(_digest([CONTEXT_VERSION, "micro-context", seed, row["id"]]))
    candidates = [
        [relation, left, right]
        for left in entities for right in entities if left != right
        if [relation, left, right] not in facts
    ]
    if not candidates:
        raise ErrorBus.legacy_error(SOURCE.GRADE_A.MICRO_CONTEXT_EXHAUSTED)
    facts.append(candidates[rng.randrange(len(candidates))])
    facts.sort()
    return _verify_contextual_row(row, record, source_root=source_root)


def _development_context_row(row: dict, *, seed: int, source_root) -> dict:
    """Populate the unused K1 set without changing the queried K0/edge/function."""
    record = copy.deepcopy(row["record"])
    world = record.get("world")
    sets = world.get("sets") if isinstance(world, dict) else None
    base = world.get("base") if isinstance(world, dict) else None
    universe = base.get("entities") if isinstance(base, dict) else None
    if (not isinstance(sets, dict) or "K1" not in sets or
            not isinstance(universe, list) or not universe):
        raise ErrorBus.legacy_error(SOURCE.GRADE_A.DEVELOPMENT_CONTEXT_SOURCE_SHAPE_INVALID)
    rng = random.Random(_digest([CONTEXT_VERSION, "development-context", seed, row["id"]]))
    mask = 1 + rng.randrange((1 << len(universe)) - 1)
    sets["K1"] = [entity for index, entity in enumerate(universe)
                  if mask & (1 << index)]
    return _verify_contextual_row(row, record, source_root=source_root)


def draw_a(*, source_root, graph, course, capability, seed, each):
    """Draw ordinary developmental Grade-A without contextual invariance noise."""
    del course
    return tuple(draw_predicates(
        source_root, graph, seed=seed, capability=capability, each=each))


def draw_a_contextual(*, source_root, graph, course, capability, seed, each):
    """Preserve contextual presentation for dormant research/generalization use."""
    del course
    rows = draw_predicates(
        source_root, graph, seed=seed, capability=capability, each=each)
    result = tuple(
        (_micro_context_row(row, seed=seed, source_root=source_root)
         if row["record"]["task"] == "micro" else
         _development_context_row(row, seed=seed, source_root=source_root))
        for row in rows)
    if len({row["id"] for row in result}) != len(result):
        raise ErrorBus.legacy_error(SOURCE.GRADE_A.CONTEXT_IDENTITY_COLLISION)
    return result
