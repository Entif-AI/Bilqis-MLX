"""Deterministic case semantics for the C13 episode-binding source family."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import random


CASE_SCHEMA = "bilqis.c13.episode-binding-case/v1"
SOURCE_FAMILY = "bamf.c13.episode-binding/v1"
ACTORS = ("A", "B", "C")
DEPTHS = (1, 2, 3, 4)


@dataclass(frozen=True)
class EpisodeEvent:
    actor: str
    ordinal: int
    start_minute: int
    duration_minutes: int

    def __post_init__(self) -> None:
        if (self.actor not in ACTORS or self.ordinal not in (0, 1)
                or type(self.start_minute) is not int or self.start_minute < 0
                or type(self.duration_minutes) is not int
                or not 1 <= self.duration_minutes <= 10):
            raise ValueError("BAMF_C13_EPISODE_EVENT_INVALID")


@dataclass(frozen=True)
class EpisodeBindingCase:
    seed: int
    depth: int
    events: tuple[EpisodeEvent, ...]
    cue_actor: str
    query_kind: str
    schema_version: str = CASE_SCHEMA

    def __post_init__(self) -> None:
        keys = tuple((event.actor, event.ordinal) for event in self.events)
        if (self.schema_version != CASE_SCHEMA or type(self.seed) is not int
                or self.seed < 0 or self.depth not in DEPTHS
                or self.cue_actor not in ACTORS
                or self.query_kind not in ("LATER_DURATION", "SUM_DURATIONS")
                or len(self.events) != 6 or len(set(keys)) != 6
                or set(actor for actor, _ in keys) != set(ACTORS)):
            raise ValueError("BAMF_C13_EPISODE_CASE_INVALID")

    def source_view(self) -> dict:
        return {
            "schema": CASE_SCHEMA,
            "source_family_id": SOURCE_FAMILY,
            "seed": self.seed,
            "depth": self.depth,
            "actors": list(ACTORS),
            "events": [asdict(event) for event in self.events],
            "relation_cue": {
                "kind": "FIRST_EVENT_SUCCESSOR",
                "from_actor": self.cue_actor,
                "hops": self.depth,
            },
            "query": self.query_kind,
        }


def episode_binding_case(seed: int, depth: int = 1) -> EpisodeBindingCase:
    if type(seed) is not int or seed < 0 or depth not in DEPTHS:
        raise ValueError("BAMF_C13_EPISODE_SEED_INVALID")
    rng = random.Random(seed)
    order = list(ACTORS)
    rng.shuffle(order)
    starts = {
        actor: position * 10 + rng.randrange(0, 3)
        for position, actor in enumerate(order)
    }
    events = tuple(
        EpisodeEvent(
            actor,
            ordinal,
            starts[actor] + ordinal * 5,
            1 + rng.randrange(1, 10),
        )
        for actor in ACTORS for ordinal in (0, 1)
    )
    return EpisodeBindingCase(
        seed,
        depth,
        events,
        order[0],
        "LATER_DURATION" if seed % 2 == 0 else "SUM_DURATIONS",
    )


def case_from_record(record: dict) -> EpisodeBindingCase:
    required = {
        "schema", "source_family_id", "seed", "depth", "actors", "events",
        "relation_cue", "query",
    }
    if (not isinstance(record, dict) or set(record) != required
            or record.get("schema") != CASE_SCHEMA
            or record.get("source_family_id") != SOURCE_FAMILY
            or record.get("actors") != list(ACTORS)
            or not isinstance(record.get("relation_cue"), dict)
            or set(record["relation_cue"]) != {"kind", "from_actor", "hops"}
            or record["relation_cue"].get("kind") != "FIRST_EVENT_SUCCESSOR"
            or record["relation_cue"].get("hops") != record.get("depth")):
        raise ValueError("BAMF_C13_EPISODE_RECORD_INVALID")
    return EpisodeBindingCase(
        record["seed"],
        record["depth"],
        tuple(EpisodeEvent(**event) for event in record["events"]),
        record["relation_cue"]["from_actor"],
        record["query"],
    )


def check_episode_binding(case: EpisodeBindingCase) -> int:
    if type(case) is not EpisodeBindingCase:
        raise ValueError("BAMF_C13_EPISODE_CHECK_INPUT_INVALID")
    first = {
        event.actor: event.start_minute
        for event in case.events if event.ordinal == 0
    }
    ordered = tuple(sorted(ACTORS, key=lambda actor: (first[actor], actor)))
    target = ordered[(ordered.index(case.cue_actor) + case.depth) % len(ordered)]
    durations = tuple(
        event.duration_minutes for event in case.events if event.actor == target
    )
    return durations[1] if case.query_kind == "LATER_DURATION" else sum(durations)


__all__ = (
    "ACTORS", "CASE_SCHEMA", "DEPTHS", "EpisodeBindingCase", "EpisodeEvent",
    "SOURCE_FAMILY", "case_from_record", "check_episode_binding",
    "episode_binding_case",
)
