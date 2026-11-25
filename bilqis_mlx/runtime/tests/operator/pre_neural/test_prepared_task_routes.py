"""Provider-neutral precompilation of the actual learning decision surface."""

import pytest

from bilqis_mlx.data_plane import DataPlane
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.learning.atlas_readout import DecisionKind
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.bamf_operator.session_parts.prepared_task_catalog import (
    PreparedTaskCatalog, _compiler_identity,
)
from bilqis_mlx.runtime.factory_candidate_microbatch import prepare_learning_first_task_route
from bilqis_mlx.runtime.factory_task_template import _source_view
from bilqis_mlx.runtime.factory_training_bridge import LearningFirstPreparationCache
from bilqis_mlx.runtime.refinement_request import refinement_request_disposition
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.runtime.task_goal_readout import (
    task_goal_route_decisions, task_goal_training_targets,
)
from bilqis_mlx.source_adapters.c13_episode import CAPABILITY as EPISODE
from bilqis_mlx.source_adapters.c13_episode_release import compile_episode_release
from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.source_adapters.task_goal_registry import require_task_goal_lowerer
from .pre_neural_journey_support import LEGACY, historical_school_release


SEMANTIC = "b" * 64


@pytest.fixture(scope="module")
def contexts():
    release, graph = historical_school_release()
    sources, answers = live_source_registry(), live_answer_registry()
    episode = compile_episode_release(None, graph, sources, answers)
    return (
        SourceExecutionContext(release, graph, LEGACY, sources, answers),
        SourceExecutionContext(episode, graph, None, sources, answers),
    )


@pytest.mark.parametrize("capability,kind", [
    ("A.PARENT", DecisionKind.OPERAND),
    ("B.AND", DecisionKind.OPERAND),
    ("C.ADD", DecisionKind.OPERATOR),
    (EPISODE, DecisionKind.OPERAND),
])
def test_precompiled_routes_match_full_provider_lowering(contexts, capability, kind, tmp_path):
    context = contexts[capability == EPISODE]
    execution = context.execution_for(capability)
    adapter = context.source_registry.resolve_owner(
        context.release.source_bindings.by_capability[capability].generator_id)
    lowerer = require_task_goal_lowerer(execution.provider_id, adapter.descriptor.implementation_sha256)
    rows = context.draw_rows(seed=52813, capability=capability, each=4)
    cache = LearningFirstPreparationCache()
    witnessed = set()
    for row in rows:
        kwargs = dict(semantic_release=SEMANTIC, capability=execution,
                      release=context.release, graph=context.graph, source_root=context.source_root)
        goal, _ = lowerer.lower(_source_view(row), **kwargs)
        resolved = lowerer.resolve(row, **kwargs)
        expected_targets, expected_mask = task_goal_training_targets(goal, resolved)
        with evidence_mode(strict=False):
            compiled = prepare_learning_first_task_route(context, row, SEMANTIC, cache=cache)
            redrawn = {**row, "source_family_id": "another-delivery", "source_family_seed": 52}
            restored = prepare_learning_first_task_route(context, redrawn, SEMANTIC, cache=cache)
        assert restored is compiled
        assert compiled.decisions == task_goal_route_decisions(goal)
        assert compiled.targets == expected_targets
        assert dict(compiled.mask) == expected_mask
        assert compiled.refinement == refinement_request_disposition(goal)
        witnessed.update(item.kind for item in compiled.decisions)
    assert kind in witnessed
    assert cache.task_hits == len(rows)
    assert cache.task_misses == len(rows)
    # Restore the same real provider outputs from a newly opened data plane.
    path = tmp_path / "plane.sqlite3"
    binding = (str(tmp_path), context.release.release_sha256,
               "snapshot", "bundle", "source", SEMANTIC, "features")
    compiler = _compiler_identity()
    plane = DataPlane(path)
    catalog = PreparedTaskCatalog(plane, tmp_path, binding, compiler)
    catalog.routes.update(cache._task_inputs)
    catalog.persist()
    assert plane.get_object_reference(catalog.reference) is not None
    plane.close()
    plane = DataPlane(path)
    try:
        restored = PreparedTaskCatalog(plane, tmp_path, binding, compiler)
        assert dict(restored.routes) == dict(cache._task_inputs)
        assert not PreparedTaskCatalog(plane, tmp_path, binding, "c" * 64).routes
        changed = (*binding[:5], "d" * 64, binding[6])
        assert not PreparedTaskCatalog(plane, tmp_path, changed, compiler).routes
        # A valid CAS object with an invalid catalog payload is not authority.
        plane.put_object_reference(catalog.reference, b'{"schema":"invalid"}')
        assert not PreparedTaskCatalog(plane, tmp_path, binding, compiler).routes
    finally:
        plane.close()


def test_task_cache_distinguishes_semantics_and_releases(contexts):
    context = contexts[0]
    row = context.draw_rows(seed=7, capability="A.PARENT", each=2)[0]
    cache = LearningFirstPreparationCache()
    with evidence_mode(strict=False):
        first = prepare_learning_first_task_route(context, row, SEMANTIC, cache=cache)
        changed = {**row, "gold": "FALSE" if row["gold"] == "TRUE" else "TRUE"}
        different = prepare_learning_first_task_route(context, changed, SEMANTIC, cache=cache)
    assert first.decisions == different.decisions
    assert first.targets != different.targets
    key = cache.task_key(row, SEMANTIC, context.release.release_sha256)
    assert cache.get_task_inputs(key) is first
    assert cache.get_task_inputs(cache.task_key(row, "c" * 64, context.release.release_sha256)) is None
    assert cache.get_task_inputs(cache.task_key(row, SEMANTIC, "d" * 64)) is None
    assert cache.get_task_inputs(cache.task_key({**row, "tokens": [0]}, SEMANTIC,
                                               context.release.release_sha256)) is None


def test_corrupt_compiled_catalog_does_not_pin_unreadable_object(contexts, tmp_path):
    context = contexts[0]
    binding = (str(tmp_path), context.release.release_sha256,
               "snapshot", "bundle", "source", SEMANTIC, "features")
    compiler = _compiler_identity()
    plane = DataPlane(tmp_path / "plane.sqlite3")
    try:
        catalog = PreparedTaskCatalog(plane, tmp_path, binding, compiler)
        cache = LearningFirstPreparationCache()
        rows = context.draw_rows(seed=7, capability="B.AND", each=4)
        with evidence_mode(strict=False):
            for row in rows:
                prepare_learning_first_task_route(context, row, SEMANTIC, cache=cache)
        catalog.routes.update(cache._task_inputs)
        catalog.persist()
        digest, _ = plane.get_object_reference(catalog.reference)
        # Simulate an unreadable archived object in the disposable data plane.
        plane._db.execute(
            "UPDATE archived_objects SET raw_bytes=raw_bytes+1 WHERE sha256=?", (digest,))
        with pytest.raises(ValueError, match="ARCHIVE_HEADER_DRIFT"):
            plane.get_object_reference(catalog.reference)
        restored = PreparedTaskCatalog(plane, tmp_path, binding, compiler)
        assert not restored.routes
        assert plane.get_object_reference(catalog.reference) is None
        # The same recompiled content has the same digest. Deduplication must not
        # accidentally republish a pointer to the still-unreadable old object.
        restored.routes.update(cache._task_inputs)
        restored.persist()
        assert plane.get_object_reference(catalog.reference) is None
        with pytest.raises(ValueError, match="ARCHIVE_HEADER_DRIFT"):
            plane.get_object(digest)
    finally:
        plane.close()
