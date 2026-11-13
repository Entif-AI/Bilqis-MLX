"""Repository-owned source authority for the bounded C13 episode-binding family."""
from __future__ import annotations

import hashlib
from pathlib import Path

from bilqis_mlx.errors import BilqisError, ErrorBus, SOURCE
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.generated_assessment import digest
from .c13_episode_cases import (
    ACTORS, CASE_SCHEMA, DEPTHS, EpisodeBindingCase, EpisodeEvent, SOURCE_FAMILY,
    case_from_record, check_episode_binding, episode_binding_case,
)


CAPABILITY = "Z.C13_EPISODE"
PROVIDER_ID = "source.bamf.c13.episode-binding/v1"
GENERATOR_ID = "bilqis.c13.episode-binding-generator/v1"
ORACLE_ID = "bilqis.c13.episode-binding-checker/v1"
ACTOR_ROOT = "ithkuil:ATOM-5d7116db8e1508"
TIME_ROOT = "ithkuil:ATOM-ef7cf17b427af9"
ADD_ROOT = "school.op.ADD"
MAX_DRAW_EACH = 128


def _fail(reason: str) -> None:
    ErrorBus.raise_(SOURCE.BAMF_C13_EPISODE.INVALID, reason=reason)


def _symbols(case: EpisodeBindingCase) -> tuple[str, ...]:
    result = [
        "micro.syntax.world",
        "micro.syntax.entities",
        *("micro.entity." + actor for actor in ACTORS),
        "micro.syntax.section_end",
        "development.syntax.events",
    ]
    for event in case.events:
        result.extend((
            "micro.entity." + event.actor,
            "development.Event.E" + str(event.ordinal),
            "school.number." + str(event.start_minute),
            "school.number." + str(event.duration_minutes),
        ))
    result.extend((
        "micro.syntax.section_end",
        "micro.role.source",
        "micro.entity." + case.cue_actor,
        "micro.role.target",
        "school.number." + str(case.depth),
        "micro.syntax.query",
    ))
    if case.query_kind == "LATER_DURATION":
        result.append("development.Event.E1")
    else:
        result.extend(("school.op.ADD", "development.Event.E0", "development.Event.E1"))
    result.append("syntax.end")
    return tuple(result)


def encode_case(case: EpisodeBindingCase, graph: dict) -> list[int]:
    if not isinstance(graph, dict) or not isinstance(graph.get("tokens"), list):
        _fail("BAMF_C13_EPISODE_GRAPH_INVALID")
    ids = {token: index for index, token in enumerate(graph["tokens"])}
    try:
        return [ids[symbol] for symbol in _symbols(case)]
    except KeyError:
        _fail("BAMF_C13_EPISODE_GRAPH_SYMBOL_MISSING")


def _depths(profile_parameters) -> tuple[int, ...]:
    if profile_parameters is None:
        return (1,)
    values = tuple(profile_parameters.get("depths", ("1",)))
    try:
        depths = tuple(int(value) for value in values)
    except (TypeError, ValueError):
        _fail("BAMF_C13_EPISODE_PROFILE_VALUE_INVALID")
    if not depths or any(depth not in DEPTHS for depth in depths):
        _fail("BAMF_C13_EPISODE_PROFILE_INVALID")
    return depths


def draw_episode(
    source_root, graph, *, seed: int, each: int = 12, capability: str = CAPABILITY,
    profile_parameters=None, **_,
) -> tuple[dict, ...]:
    del source_root
    if (capability != CAPABILITY or type(seed) is not int or seed < 0
            or type(each) is not int or not 1 <= each <= MAX_DRAW_EACH):
        _fail("BAMF_C13_EPISODE_DRAW_INVALID")
    depths = _depths(profile_parameters)
    rows = []
    for index in range(each):
        case = episode_binding_case(seed * 1000 + index, depths[index % len(depths)])
        record = case.source_view()
        row_id = digest((GENERATOR_ID, record))
        gold = str(check_episode_binding(case))
        number_identity = "school.number." + gold
        try:
            native_token_id = graph["tokens"].index(number_identity)
        except (KeyError, ValueError):
            _fail("BAMF_C13_EPISODE_NATIVE_TARGET_MISSING")
        rows.append({
            "id": row_id,
            "source_id": row_id,
            "capability": CAPABILITY,
            "answer_kind": "numeric_active",
            "gold": gold,
            "native_output": {
                "identity": number_identity,
                "token_id": native_token_id,
            },
            "record": record,
            "tokens": encode_case(case, graph),
            "generator": GENERATOR_ID,
            "oracle": ORACLE_ID,
            "source_family_id": SOURCE_FAMILY,
            "episode_id": row_id,
        })
    return tuple(rows)


def check_episode_row(row: dict, *, graph: dict, **_) -> bool:
    try:
        case = case_from_record(row["record"])
        expected_id = digest((GENERATOR_ID, row["record"]))
        gold = str(check_episode_binding(case))
        number_identity = "school.number." + gold
        native_output = {
            "identity": number_identity,
            "token_id": graph["tokens"].index(number_identity),
        }
        return (
            row.get("generator") == GENERATOR_ID
            and row.get("oracle") == ORACLE_ID
            and row.get("capability") == CAPABILITY
            and row.get("answer_kind") == "numeric_active"
            and row.get("source_family_id") == SOURCE_FAMILY
            and row.get("episode_id") == expected_id
            and row.get("id") == row.get("source_id") == expected_id
            and row.get("gold") == gold
            and row.get("native_output") == native_output
            and row.get("tokens") == encode_case(case, graph)
        )
    except (BilqisError, KeyError, TypeError, ValueError):
        return False


def semantic_footprint(row: dict) -> tuple[str, ...]:
    case = case_from_record(row.get("record"))
    roots = (ACTOR_ROOT, TIME_ROOT)
    return (*roots, ADD_ROOT) if case.query_kind == "SUM_DURATIONS" else roots


def provider_implementation_digest() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def registered_adapter() -> RegisteredSourceAdapter:
    return RegisteredSourceAdapter(
        SourceAdapter(
            PROVIDER_ID,
            GENERATOR_ID,
            (ORACLE_ID,),
            provider_implementation_digest(),
            variation_axes=(
                "source-valid", "fresh-seed", "actor-binding", "event-order",
                "duration", "query-form", "relation-depth",
            ),
            profile_dimensions=(("depths", tuple(str(depth) for depth in DEPTHS)),),
        ),
        draw_episode,
        check_episode_row,
        semantic_footprint=semantic_footprint,
    )


__all__ = (
    "ACTOR_ROOT", "ACTORS", "ADD_ROOT", "CAPABILITY", "CASE_SCHEMA", "DEPTHS",
    "EpisodeBindingCase", "EpisodeEvent", "GENERATOR_ID", "ORACLE_ID", "PROVIDER_ID",
    "SOURCE_FAMILY", "TIME_ROOT", "case_from_record", "check_episode_binding",
    "check_episode_row", "draw_episode", "encode_case", "episode_binding_case",
    "provider_implementation_digest", "registered_adapter", "semantic_footprint",
)
