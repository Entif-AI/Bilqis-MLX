"""Issue #1577 host-preparation pipeline scheduling and lifecycle proof."""
from functools import partial
from threading import Event
import time
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_operator.session_parts.pipeline import (
    CandidateHostPreparationPipeline,
    learning_first_prepare_step,
)
from bilqis_mlx.runtime.bamf_operator.source_prefetch import (
    CandidateLessonRows,
    SourcePrefetchMetrics,
)


class _Lane:
    def lesson(self, ordinal):
        return CandidateLessonRows(
            ({"id": f"row:{ordinal}", "capability": "A.TEST"},),
            prefetch_identity=f"{ordinal:064x}")


def test_host_preparation_pipeline_overlaps_future_cpu_work_with_current_step():
    class SlowLane(_Lane):
        def lesson(self, ordinal):
            time.sleep(0.02)
            return super().lesson(ordinal)

    def prepare(_ordinal, lesson):
        time.sleep(0.02)
        return ("prepared", lesson.direct[0]["id"])

    metrics = SourcePrefetchMetrics()
    pipeline = CandidateHostPreparationPipeline(SlowLane(), 2, prepare, metrics)
    try:
        pipeline.submit(1)
        first = pipeline.take(1)
        pipeline.submit(2)
        time.sleep(0.06)
        second = pipeline.take(2)
    finally:
        pipeline.close()

    assert first.prepared_source_inputs == ("prepared", "row:1")
    assert second.prepared_source_inputs == ("prepared", "row:2")
    assert metrics.pipeline_submitted_steps == 2
    assert metrics.pipeline_prepared_steps == 2
    assert metrics.pipeline_discarded_steps == 0
    assert second.overlap_wall_seconds >= 0.03
    assert second.host_wait_wall_seconds < first.host_wait_wall_seconds
    assert metrics.pipeline_accelerator_wait_for_host_seconds == (
        metrics.pipeline_host_wait_seconds)


def test_host_preparation_pipeline_accounts_for_discarded_running_work():
    metrics = SourcePrefetchMetrics()
    second_started = Event()

    def prepare(ordinal, _lesson):
        if ordinal == 2:
            second_started.set()
            time.sleep(0.02)
        return ("prepared", ordinal)

    pipeline = CandidateHostPreparationPipeline(_Lane(), 2, prepare, metrics)
    pipeline.submit(1)
    first = pipeline.take(1)
    pipeline.submit(2)
    assert second_started.wait(timeout=1.0)
    pipeline.close()

    assert first.prepared_source_inputs == ("prepared", 1)
    assert metrics.pipeline_submitted_steps == 2
    assert metrics.pipeline_prepared_steps == 1
    assert metrics.pipeline_discarded_steps == 1
    assert metrics.pipeline_discarded_preparation_seconds > 0.0
    assert metrics.pipeline_host_preparation_seconds >= (
        metrics.pipeline_discarded_preparation_seconds)


def test_host_preparation_pipeline_rejects_cross_ordinal_take():
    metrics = SourcePrefetchMetrics()
    pipeline = CandidateHostPreparationPipeline(
        _Lane(), 2, lambda ordinal, _lesson: ("prepared", ordinal), metrics)
    try:
        pipeline.submit(1)
        with pytest.raises(BilqisError) as caught:
            pipeline.take(2)
        assert caught.value.context["reason"] == "BAMF_HOST_PREPARATION_STEP_MISSING"
    finally:
        pipeline.close()


def test_learning_first_callback_is_selected_without_touching_strict_execution():
    def execute_candidate(*_args, **_kwargs):
        return None

    context = object()
    authenticated = object()
    selection = SimpleNamespace(offer=SimpleNamespace(
        source_seed=17,
        _planning_generation=SimpleNamespace(_authenticated_features=authenticated)))
    strict_executor = partial(execute_candidate, candidate_visit=object())
    learning_executor = partial(
        execute_candidate, candidate_visit=None, learning_first_cache=object())
    assert learning_first_prepare_step(strict_executor, selection, context) is None

    row = {"id": "row:1", "capability": "A.TEST"}
    lesson = SimpleNamespace(delivered=(row,), direct=(row,), enrichment=())
    with patch(
            "bilqis_mlx.runtime.factory_training_preparation."
            "prepare_learning_first_source_inputs_ahead",
            return_value="prepared") as prepare:
        callback = learning_first_prepare_step(learning_executor, selection, context)
        assert callback(1, lesson) == "prepared"
    prepare.assert_called_once_with(
        context, authenticated, (row,), source_seed=17, source_each=1)


def test_candidate_horizon_discovers_learning_first_pipeline_automatically():
    from bilqis_mlx.runtime.bamf_operator.session_parts import candidate_execution

    lane = SimpleNamespace(metrics=SourcePrefetchMetrics())
    capture = object()
    candidate = SimpleNamespace(motif_transition=object())
    step = SimpleNamespace(transaction=candidate)
    execute_candidate = partial(lambda *_args, **_kwargs: None,
                                learning_first_cache=object())
    with patch.object(
            candidate_execution, "_candidate_capture",
            return_value=(lane, capture)), patch.object(
            candidate_execution, "_configure_shadow", return_value=()), patch.object(
            candidate_execution, "_execute_horizon_step",
            return_value=(step, candidate, None)), patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.pipeline."
            "learning_first_prepare_step",
            return_value=lambda _ordinal, _lesson: object()) as discover, patch(
            "bilqis_mlx.runtime.bamf_operator.session_parts.pipeline."
            "CandidateHostPreparationPipeline") as pipeline_cls:
        pipeline = pipeline_cls.return_value
        pipeline.take.return_value = object()
        steps, result_capture = candidate_execution.execute_horizon(
            "run", object(), object(), object(), "atlas", "features", (), 1,
            object(), 1, None, 1, object(), SourcePrefetchMetrics(), object(),
            source_lane_cls=object, source_metrics_cls=SourcePrefetchMetrics,
            prepare_evidence_root=lambda *_args: None, capture_cls=object,
            delivery_observation_cls=object, execute_candidate=execute_candidate,
            step_seed=lambda *_args: 1, emit_progress=lambda *_args: None,
            invalid=lambda reason: (_ for _ in ()).throw(AssertionError(reason)),
            observe_completed_step_fn=lambda *_args: None)

    assert steps == [step]
    assert result_capture is capture
    discover.assert_called_once()
    pipeline.submit.assert_any_call(1)
    pipeline.take.assert_called_once_with(1)
    pipeline.close.assert_called_once_with()
