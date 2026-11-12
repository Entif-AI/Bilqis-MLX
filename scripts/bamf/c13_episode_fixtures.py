"""Deterministic gold-blind episode fixtures for C13.1."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import random

from bilqis_mlx.semantics.cognitive_dag import (
    DAGBudget, DAGNode, DAGOperand, DAGProgram, RefKind, TaskGoal,
)

from scripts.bamf.c13_delivery_contracts import ACTORS, CASE_SCHEMA, fail


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
                or self.duration_minutes <= 0):
            fail("BAMF_C13_EPISODE_EVENT_INVALID")


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
                or self.seed < 0 or self.depth not in (1, 2, 3, 4)
                or self.cue_actor not in ACTORS
                or self.query_kind not in ("LATER_DURATION", "SUM_DURATIONS")
                or len(self.events) != 6 or len(set(keys)) != 6
                or set(actor for actor, _ in keys) != set(ACTORS)):
            fail("BAMF_C13_EPISODE_CASE_INVALID")

    def source_view(self) -> dict:
        return {
            "schema": CASE_SCHEMA,
            "source_family_id": "bamf.c13.episode-binding/v1",
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
    if type(seed) is not int or seed < 0 or depth not in (1, 2, 3, 4):
        fail("BAMF_C13_EPISODE_SEED_INVALID")
    rng = random.Random(seed)
    order = list(ACTORS)
    rng.shuffle(order)
    starts = {actor: position * 10 + rng.randrange(0, 3)
              for position, actor in enumerate(order)}
    events = tuple(
        EpisodeEvent(actor, ordinal, starts[actor] + ordinal * 5,
                     1 + rng.randrange(1, 10))
        for actor in ACTORS for ordinal in (0, 1)
    )
    return EpisodeBindingCase(
        seed, depth, events, order[0],
        "LATER_DURATION" if seed % 2 == 0 else "SUM_DURATIONS")


def _duration_ref(case: EpisodeBindingCase, actor: str, ordinal: int) -> DAGOperand:
    return DAGOperand(
        RefKind.LITERAL, "Number",
        source_handle=f"source:c13:{case.seed}:duration:{actor}:{ordinal}")


def episode_task_goal(case: EpisodeBindingCase, semantic_release: str) -> TaskGoal:
    if (type(case) is not EpisodeBindingCase or not isinstance(semantic_release, str)
            or len(semantic_release) != 64):
        fail("BAMF_C13_TASK_GOAL_INPUT_INVALID")
    scope = "C13.EPISODE_BINDING"
    later = tuple(_duration_ref(case, actor, 1) for actor in ACTORS)
    select_later = DAGNode(
        "select-later-duration", "SELECT_NUMBER", (None,), "Number", scope,
        candidate_operand_refs=(later,),
        constraints=("SOURCE_VISIBLE", "TYPE_COMPATIBLE"))
    nodes = [select_later]
    if case.query_kind == "SUM_DURATIONS":
        earlier = tuple(_duration_ref(case, actor, 0) for actor in ACTORS)
        select_earlier = DAGNode(
            "select-earlier-duration", "SELECT_NUMBER", (None,), "Number", scope,
            candidate_operand_refs=(earlier,),
            constraints=("SOURCE_VISIBLE", "TYPE_COMPATIBLE"))
        nodes = [select_earlier, select_later, DAGNode(
            "sum-visible-durations", "ADD", (
                DAGOperand(RefKind.RESULT, "Number",
                           result_node_id="select-earlier-duration"),
                DAGOperand(RefKind.RESULT, "Number",
                           result_node_id="select-later-duration"),
            ), "Number", scope)]
    program = DAGProgram(tuple(nodes), nodes[-1].node_id, scope)
    visible = tuple(sorted({
        ref.identity for node in nodes for group in node.candidate_operand_refs
        for ref in group
    }))
    operators = tuple(sorted({node.operator_id for node in nodes if node.operator_id}))
    return TaskGoal(
        f"c13-episode-{case.seed}-d{case.depth}", "Number", visible, program,
        operators, DAGBudget(max_nodes=3, max_depth=3, max_operations=3, max_decisions=2),
        semantic_release, scope)


def check_episode_binding(case: EpisodeBindingCase) -> int:
    if type(case) is not EpisodeBindingCase:
        fail("BAMF_C13_EPISODE_CHECK_INPUT_INVALID")
    first = {event.actor: event.start_minute for event in case.events
             if event.ordinal == 0}
    ordered = tuple(sorted(ACTORS, key=lambda actor: (first[actor], actor)))
    target = ordered[(ordered.index(case.cue_actor) + case.depth) % len(ordered)]
    durations = tuple(event.duration_minutes for event in case.events
                      if event.actor == target)
    return durations[1] if case.query_kind == "LATER_DURATION" else sum(durations)


def fixture_manifest(config, source) -> dict:
    def rows(seeds):
        return [{
            "input": case.source_view(),
            "task_goal": asdict(episode_task_goal(case, source.semantic_release)),
            "checker_answer": check_episode_binding(case),
        } for case in (episode_binding_case(seed, 1) for seed in seeds)]

    return {
        "schema": "bilqis.c13.disposable-fixture-manifest/v1",
        "source_release_sha256": source.release_sha256,
        "semantic_release": source.semantic_release,
        "baseline": rows(config.baseline_seeds),
        "fresh": rows(config.fresh_seeds),
    }


__all__ = (
    "EpisodeBindingCase", "EpisodeEvent", "check_episode_binding",
    "episode_binding_case", "episode_task_goal", "fixture_manifest",
)
