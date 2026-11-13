"""Deterministic C13.1 fixture manifests projected from live source authority."""
from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

from bilqis_mlx.generated_assessment import digest
from bilqis_mlx.runtime.factory_task_authority import _source_view
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.source_adapters.c13_episode import (
    CAPABILITY,
    GENERATOR_ID,
    encode_case,
)
from bilqis_mlx.source_adapters.c13_episode_cases import (
    ACTORS,
    CASE_SCHEMA,
    EpisodeBindingCase,
    EpisodeEvent,
    case_from_record,
    check_episode_binding,
    episode_binding_case,
)

from scripts.bamf.c13.contracts import fail
from scripts.bamf.c13.episode_source import (
    episode_factory_release,
    registered_episode_lowerer,
)


@lru_cache(maxsize=4)
def _lowering_context(depth: int):
    release, graph, sources, answers = episode_factory_release(depths=(depth,))
    capability = release.execution_plan.capability_map[CAPABILITY]
    source_root = (Path(__file__).resolve().parents[2] / "vendor/legacy-v16").resolve()
    context = SourceExecutionContext(release, graph, source_root, sources, answers)
    return release, graph, capability, context, registered_episode_lowerer()


def episode_task_goal(case: EpisodeBindingCase, semantic_release: str):
    """Project one gold-blind fixture through the live C13 TaskGoal lowerer."""
    if (type(case) is not EpisodeBindingCase or not isinstance(semantic_release, str)
            or len(semantic_release) != 64):
        fail("BAMF_C13_TASK_GOAL_INPUT_INVALID")
    release, graph, capability, _context, lowerer = _lowering_context(case.depth)
    record = case.source_view()
    row_id = digest((GENERATOR_ID, record))
    row = {
        "id": row_id,
        "source_id": row_id,
        "capability": CAPABILITY,
        "record": record,
        "tokens": encode_case(case, graph),
    }
    goal, _binding = lowerer.lower(
        row,
        semantic_release=semantic_release,
        capability=capability,
        release=release,
    )
    return goal


def fixture_manifest(config, source) -> dict:
    release, _graph, capability, context, lowerer = _lowering_context(1)
    rows = tuple(context.draw_rows(seed=0, capability=CAPABILITY, each=128))
    expected = tuple(range(128))
    observed = tuple(row["record"]["seed"] for row in rows)
    if observed != expected or any(row["record"]["depth"] != 1 for row in rows):
        fail("BAMF_C13_FIXTURE_SEED_SPLIT_DRIFT")

    def project(row):
        goal, _binding = lowerer.lower(
            _source_view(row),
            semantic_release=source.semantic_release,
            capability=capability,
            release=release,
        )
        case = case_from_record(row["record"])
        return {
            "input": row["record"],
            "task_goal": asdict(goal),
            "checker_answer": check_episode_binding(case),
        }

    baseline = tuple(project(row) for row in rows[:64])
    fresh = tuple(project(row) for row in rows[64:])

    return {
        "schema": "bilqis.c13.disposable-fixture-manifest/v1",
        "source_release_sha256": source.release_sha256,
        "semantic_release": source.semantic_release,
        "baseline": baseline,
        "fresh": fresh,
    }


__all__ = (
    "ACTORS",
    "CASE_SCHEMA",
    "EpisodeBindingCase",
    "EpisodeEvent",
    "check_episode_binding",
    "episode_binding_case",
    "episode_task_goal",
    "fixture_manifest",
)
