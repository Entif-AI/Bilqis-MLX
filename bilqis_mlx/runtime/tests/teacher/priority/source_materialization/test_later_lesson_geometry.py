"""Complete source-owned constructions survive native HOW selection."""
from collections import Counter

import pytest

from bilqis_mlx.learning.native_lesson_selection import select_group_lesson
from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.source_adapters import copular, event_frames, event_intro, event_pairs
from bilqis_mlx.source_adapters.lesson_geometry import (
    complete_groups, distinct_groups, geometry_for_adapter,
)
from bilqis_mlx.source_adapters.tests.test_copular import proposed_graph


def _selected(adapter, graph, *, seed, each, capability=None):
    kwargs = {} if capability is None else {"capability": capability}
    geometry = geometry_for_adapter(adapter)
    baseline = distinct_groups(complete_groups(
        adapter.draw(None, graph, seed=seed, each=each, **kwargs), geometry))
    pool = distinct_groups(complete_groups(
        adapter.draw(None, graph, seed=seed, each=2 * each, **kwargs), geometry))
    available = Counter((len(g.rows), g.stratum) for g in pool)
    needed = Counter((len(g.rows), g.stratum) for g in baseline)
    if any(available[key] < count for key, count in needed.items()):
        pool = baseline
    result = select_group_lesson(baseline, pool, seed=seed, deep=True, contrast=True)
    return baseline, result


def test_copular_contrast_pairs_and_singletons_remain_complete():
    graph = proposed_graph()
    adapter = copular.registered_adapter()
    baseline, result = _selected(adapter, graph, seed=349, each=12)
    assert [len(group.rows) for group in result.groups] == [2, 2, 2, 2, 1, 1, 1, 1]
    assert Counter(g.stratum for g in result.groups) == Counter(g.stratum for g in baseline)
    assert all(adapter.check(row, graph=graph) for row in result.rows)
    for group in result.groups[:4]:
        left, right = group.rows
        assert left["record"]["query"] == right["record"]["query"]
        assert {left["gold"], right["gold"]} == {"TRUE", "FALSE"}
    assert result.depth_control == "SOURCE_TOKEN_LENGTH_PROXY"


def _event_pattern(row):
    record = row["record"]
    return tuple(next(event[1:] for event in record["events"] if event[0] == record["query"]))


@pytest.mark.parametrize("provider,paired", [
    (event_frames, False), (event_intro, False), (event_pairs, True),
])
def test_event_source_preserves_query_transition_census(provider, paired):
    graph = event_frames.expanded_graph(registry_graph())
    adapter = provider.registered_adapter()
    baseline, result = _selected(
        adapter, graph, seed=349, each=12, capability="D.EVENT_OCCURRENCE")
    assert len(result.rows) == 12
    assert Counter(_event_pattern(row) for row in result.rows) == Counter(
        _event_pattern(row) for group in baseline for row in group.rows)
    if paired:
        left, right = result.groups[0].rows
        assert left["record"]["events"] == right["record"]["events"]
        assert left["record"]["query"] != right["record"]["query"]
        assert {left["gold"], right["gold"]} == {"TRUE", "FALSE"}
        assert all(len(group.rows) == 1 for group in result.groups[1:])
    else:
        assert all(len(group.rows) == 1 for group in result.groups)


def test_c13_admitted_episode_profile_preserves_depth_and_query():
    from bilqis_mlx.factory.live_answers import live_answer_registry
    from bilqis_mlx.runtime.source_execution import SourceExecutionContext
    from bilqis_mlx.source_adapters.c13_episode import CAPABILITY
    from bilqis_mlx.source_adapters.c13_episode_release import compile_episode_release
    from bilqis_mlx.source_adapters.school import live_source_registry

    graph, sources, answers = registry_graph(), live_source_registry(), live_answer_registry()
    release = compile_episode_release(None, graph, sources, answers)
    context = SourceExecutionContext(release, graph, None, sources, answers)
    adapter = sources.resolve_owner(release.source_bindings.by_capability[CAPABILITY].generator_id)
    geometry = geometry_for_adapter(adapter)
    rows, _ = context.draw_bound_rows(seed=349, capability=CAPABILITY, each=12)
    expanded, authority = context.draw_bound_rows(seed=349, capability=CAPABILITY, each=24)
    baseline = distinct_groups(complete_groups(rows, geometry))
    pool = distinct_groups(complete_groups(expanded, geometry))
    result = select_group_lesson(baseline, pool, seed=349, deep=True, contrast=True)
    def census(rows):
        return Counter((row["record"]["depth"], row["record"]["query"]) for row in rows)
    assert census(result.rows) == census(rows)
    assert len(result.rows) == 12
    selected = context.bind_authorized_subset_rows(expanded, result.rows, authority)
    assert context.require_bound_rows(result.rows, selected) is selected
