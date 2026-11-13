"""C13.1 harness accessors for the repository-owned live episode source authority.

This module deliberately owns no provider, registry, TaskGoal lowerer, semantic
root, or checker implementation.  #1020 admitted those owners into production;
the C13.1 witness consumes them exactly as the runtime does.
"""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.source_adapters.c13_episode import (
    CAPABILITY,
    GENERATOR_ID,
    ORACLE_ID,
    PROVIDER_ID,
    check_episode_row,
    draw_episode,
    encode_case,
    provider_implementation_digest,
)
from bilqis_mlx.source_adapters.c13_episode_cases import (
    EpisodeBindingCase,
    EpisodeEvent,
    SOURCE_FAMILY,
    check_episode_binding,
    episode_binding_case,
)
from bilqis_mlx.source_adapters.c13_episode_release import compile_episode_release
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.source_adapters.task_goal_registry import require_task_goal_lowerer


LOWERER_ID = "bilqis.c13.episode-binding-task-goal/v1"
_SOURCE_ROOT = (Path(__file__).resolve().parents[2] / "vendor/legacy-v16").resolve()


def implementation_digest() -> str:
    """Return the live provider implementation digest, never a harness digest."""
    return provider_implementation_digest()


def episode_graph() -> dict:
    """Return the production semantic graph used by the admitted C13 provider."""
    return registry_graph()


def registered_episode_adapter():
    """Resolve the exact live source owner admitted by #1020."""
    return live_source_registry().require(GENERATOR_ID, ORACLE_ID)


def registered_episode_lowerer():
    """Resolve the exact live TaskGoal lowerer bound to the provider digest."""
    return require_task_goal_lowerer(PROVIDER_ID, provider_implementation_digest())


def lower_episode_task_goal(*args, **kwargs):
    return registered_episode_lowerer().lower(*args, **kwargs)


def resolve_episode_task_goal(*args, **kwargs):
    return registered_episode_lowerer().resolve(*args, **kwargs)


def episode_factory_release(*, depths: tuple[int, ...] = (1,)):
    """Compile the C13-only disposable release from live registries and source."""
    graph = registry_graph()
    sources = live_source_registry()
    answers = live_answer_registry()
    release = compile_episode_release(
        _SOURCE_ROOT,
        graph,
        sources,
        answers,
        depths=depths,
    )
    return release, graph, sources, answers


__all__ = (
    "CAPABILITY",
    "EpisodeBindingCase",
    "EpisodeEvent",
    "GENERATOR_ID",
    "LOWERER_ID",
    "ORACLE_ID",
    "PROVIDER_ID",
    "SOURCE_FAMILY",
    "check_episode_binding",
    "check_episode_row",
    "draw_episode",
    "encode_case",
    "episode_binding_case",
    "episode_factory_release",
    "episode_graph",
    "implementation_digest",
    "lower_episode_task_goal",
    "registered_episode_adapter",
    "registered_episode_lowerer",
    "resolve_episode_task_goal",
)
