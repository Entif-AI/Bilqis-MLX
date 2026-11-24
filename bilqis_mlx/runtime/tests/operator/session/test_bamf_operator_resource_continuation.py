"""Native visit coordination after a provisional candidate resource failure."""
from contextlib import nullcontext
from functools import partial
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from bilqis_mlx.errors import BilqisError, SCHOOL
from bilqis_mlx.runtime.atlas_memory_retry import RESOURCE_REJECTION_SCHEMA
from bilqis_mlx.runtime.bamf_operator.session_parts.session_execution import _run_visits
from bilqis_mlx.runtime.bamf_operator.session_parts.session_visit import visit
from bilqis_mlx.runtime.bamf_operator.session_parts.retention import _instruction_event
from bilqis_mlx.runtime.bamf_operator.session_parts.stop_receipt import _resume_state
from bilqis_mlx.runtime.bamf_operator.session_parts.session_support import BamfPreparedVisit


@pytest.mark.parametrize("has_peer", (True, False))
def test_resource_rejection_returns_to_scheduler_without_learner_feedback(tmp_path, has_peer):
    parent = object()
    cadence_record = {
        "schema": "bilqis.bamf.active-grade-cadence-authorization/v2",
        "disposition": "TEACHING",
    }
    identity = SimpleNamespace(
        visit_id="visit:failed", policy_key="policy",
        to_record=lambda: {"visit_id": "visit:failed"})
    failed = BamfPreparedVisit(
        "RESOURCE_REJECTED", parent,
        selection=SimpleNamespace(
            visit=SimpleNamespace(identity=identity),
            metadata={"cadence": cadence_record}),
        capability="failed",
        resource={"schema": RESOURCE_REJECTION_SCHEMA, "status": "EXHAUSTED"})
    peer = BamfPreparedVisit(
        "READY", parent, selection=SimpleNamespace(metadata={}),
        decision=SimpleNamespace(accepted=True), successor=SimpleNamespace(
            extents=SimpleNamespace(factor_map_digest="feature")),
        step=SimpleNamespace(transaction=SimpleNamespace(training_authorities=())))
    prepare = Mock(side_effect=(
        failed, peer if has_peer else BamfPreparedVisit("RESOURCE_HOLD", parent)))
    journal, publish, cadence = Mock(), Mock(), Mock()
    authority = SimpleNamespace(assert_current=Mock())
    disk = Mock(return_value={"sufficient": True})
    observer = SimpleNamespace(finish=Mock(), update=Mock())
    outcome = _run_visits(
        tmp_path, deadline=100, max_visits=1, steps_per_visit=1, batch_size=1,
        reserve_gib=100,
        source_prefetch_workers=0, progress=None, source_prefetch_executor=None,
        metrics=None, run_authority_binding=authority, resource_snapshot=disk,
        monotonic=lambda: 0, observer_type=lambda *_: nullcontext(observer),
        emit_progress=lambda *_: None,
        visit_fn=partial(
            visit, prepare_visit=prepare, record_rejection=journal, accept_publish=publish,
            load_generation=None, measure_phase=lambda *_: nullcontext(),
            emit_progress=lambda *_: None, record_cadence_attempt=cadence))

    assert prepare.call_count == 2
    assert prepare.call_args.kwargs["resource_holds"] == frozenset({"failed"})
    assert disk.call_count == 2
    journal.assert_called_once_with(tmp_path, parent, {
        "schema": RESOURCE_REJECTION_SCHEMA,
        "status": "EXHAUSTED",
        "capability": "failed",
        "visit_id": "visit:failed",
        "teacher_visit": {"visit_id": "visit:failed"},
        "selected_policy_key": "policy",
        "cadence": cadence_record,
    })
    cadence.assert_not_called()
    if has_peer:
        assert outcome[:4] == ("VISIT_LIMIT", 1, 1, 0)
        publish.assert_called_once()
    else:
        assert outcome[:4] == ("RESOURCE_HOLD", 0, 0, 0)
        publish.assert_not_called()
        assert _resume_state("RESOURCE_HOLD") == (True, "RESUME_AFTER_RESOURCE_RECOVERY")


def test_visit_progress_is_mirrored_into_observation_activity(tmp_path):
    observer = SimpleNamespace(finish=Mock(), update=Mock(), stage=Mock())
    messages = []
    def visit_fn(*_args, **kwargs):
        kwargs['progress']('planner: compiling semantic curriculum')
        return 'REJECTED'
    outcome = _run_visits(
        tmp_path, deadline=100, max_visits=1, steps_per_visit=1, batch_size=1,
        reserve_gib=100,
        source_prefetch_workers=0, progress=messages.append, source_prefetch_executor=None,
        metrics=None, run_authority_binding=None, resource_snapshot=None,
        monotonic=lambda: 0, observer_type=lambda *_: nullcontext(observer),
        emit_progress=lambda callback, message: callback(message) if callback else None,
        visit_fn=visit_fn)
    observer.stage.assert_any_call(activity='planner: compiling semantic curriculum')
    assert not any(
        call.kwargs == {'activity': 'planner: compiling semantic curriculum'}
        for call in observer.update.call_args_list)
    assert 'planner: compiling semantic curriculum' in messages
    assert outcome[:4] == ('VISIT_LIMIT', 1, 0, 1)


def test_acquisition_rearmed_continues_without_candidate_decision(tmp_path):
    parent = object()
    rearmed = BamfPreparedVisit("ACQUISITION_REARMED", parent)
    peer = BamfPreparedVisit(
        "READY", parent, selection=SimpleNamespace(metadata={}),
        decision=SimpleNamespace(accepted=True), successor=SimpleNamespace(
            extents=SimpleNamespace(factor_map_digest="feature")),
        step=SimpleNamespace(transaction=SimpleNamespace(training_authorities=())))
    prepare = Mock(side_effect=(rearmed, peer))
    publish = Mock()
    observer = SimpleNamespace(finish=Mock(), update=Mock())

    outcome = _run_visits(
        tmp_path, deadline=100, max_visits=1, steps_per_visit=1, batch_size=1,
        reserve_gib=100,
        source_prefetch_workers=0, progress=None, source_prefetch_executor=None,
        metrics=None, run_authority_binding=None, resource_snapshot=None,
        monotonic=lambda: 0, observer_type=lambda *_: nullcontext(observer),
        emit_progress=lambda *_: None,
        visit_fn=partial(
            visit, prepare_visit=prepare, record_rejection=Mock(),
            accept_publish=publish, load_generation=None,
            measure_phase=lambda *_: nullcontext(), emit_progress=lambda *_: None))

    assert prepare.call_count == 2
    assert outcome[:4] == ("VISIT_LIMIT", 1, 1, 0)
    publish.assert_called_once()


def test_stale_execution_cache_restarts_visit_from_current_custody(tmp_path):
    stale = BilqisError(
        SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID,
        {"reason": "B13_EXECUTION_CACHE_STALE"},
    )
    visit_fn = Mock(side_effect=(stale, "REJECTED"))
    observer = SimpleNamespace(finish=Mock(), update=Mock())
    messages = []

    outcome = _run_visits(
        tmp_path, deadline=100, max_visits=1, steps_per_visit=1, batch_size=1,
        reserve_gib=100,
        source_prefetch_workers=0, progress=messages.append,
        source_prefetch_executor=None, metrics=None, run_authority_binding=None,
        resource_snapshot=None, monotonic=lambda: 0,
        observer_type=lambda *_: nullcontext(observer),
        emit_progress=lambda callback, message: callback(message) if callback else None,
        visit_fn=visit_fn,
    )

    assert visit_fn.call_count == 2
    assert outcome[:4] == ("VISIT_LIMIT", 1, 0, 1)
    assert any("refreshing accepted custody" in message for message in messages)
    observer.update.assert_any_call(
        error_code="SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID",
        error_detail="B13_EXECUTION_CACHE_STALE",
    )
    observer.finish.assert_any_call("INTERRUPTED")


def test_repeated_stale_execution_cache_still_fails_closed(tmp_path):
    stale = BilqisError(
        SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID,
        {"reason": "B13_EXECUTION_CACHE_STALE"},
    )
    visit_fn = Mock(side_effect=(stale, stale))
    observer = SimpleNamespace(finish=Mock(), update=Mock())

    with pytest.raises(BilqisError) as caught:
        _run_visits(
            tmp_path, deadline=100, max_visits=1, steps_per_visit=1, batch_size=1,
            reserve_gib=100, source_prefetch_workers=0, progress=None,
            source_prefetch_executor=None, metrics=None,
            run_authority_binding=None, resource_snapshot=None,
            monotonic=lambda: 0,
            observer_type=lambda *_: nullcontext(observer),
            emit_progress=lambda *_: None,
            visit_fn=visit_fn,
        )

    assert visit_fn.call_count == 2
    assert caught.value.context["reason"] == "B13_EXECUTION_CACHE_STALE"


def test_instruction_history_does_not_hide_stale_execution_cache(monkeypatch):
    stale = BilqisError(
        SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID,
        {"reason": "B13_EXECUTION_CACHE_STALE"},
    )
    monkeypatch.setattr(
        "bilqis_mlx.learning.teacher_lineage.instruction_history",
        lambda _teacher: ("COMPLETE", ("A.IDENTITY",)),
    )
    monkeypatch.setattr(
        "bilqis_mlx.runtime.priority_rejection_replay.rejection_recency",
        Mock(side_effect=stale),
    )

    with pytest.raises(BilqisError) as caught:
        _instruction_event(
            object(),
            SimpleNamespace(teacher_state={}),
            object(),
            "A.EDGE",
        )

    assert caught.value.context["reason"] == "B13_EXECUTION_CACHE_STALE"


def test_instruction_event_uses_selected_teacher_projection(monkeypatch):
    selected_teacher = {"schema": "selected-c03"}
    history = Mock(return_value=("COMPLETE", ("A.IDENTITY",)))
    monkeypatch.setattr(
        "bilqis_mlx.learning.teacher_lineage.instruction_history", history)
    monkeypatch.setattr(
        "bilqis_mlx.runtime.priority_rejection_replay.rejection_recency",
        lambda *_: (None, ()))

    event = _instruction_event(
        object(),
        SimpleNamespace(teacher_state={"schema": "raw-genesis"}),
        object(),
        "A.EDGE",
        teacher_state=selected_teacher,
    )

    history.assert_called_once_with(selected_teacher)
    assert event["capability_ids"] == ["A.EDGE", "A.IDENTITY"]


def test_neutral_skip_is_a_visit_but_not_candidate_credit(tmp_path, monkeypatch):
    from bilqis_mlx.runtime.bamf_bundle.publication import preflight
    parent = SimpleNamespace(retained_state=SimpleNamespace(optimizer_step=11))
    authorization = {'phase_sha256': 'phase'}
    prepared = BamfPreparedVisit(
        'PERFECT_TARGET_SKIPPED', parent,
        selection=SimpleNamespace(metadata={'cadence': authorization}),
        capability='target', preflight=SimpleNamespace(
            assessment=SimpleNamespace(score=lambda _: (6, 6))))
    journal, rejection, publish, cadence = Mock(), Mock(), Mock(), Mock()
    monkeypatch.setattr(preflight, 'record_perfect_target_skip', journal)
    observer = SimpleNamespace(finish=Mock(), update=Mock())
    outcome = _run_visits(
        tmp_path, deadline=100, max_visits=1, steps_per_visit=1, batch_size=1,
        reserve_gib=100, source_prefetch_workers=0, progress=None,
        source_prefetch_executor=None, metrics=None, run_authority_binding=None,
        resource_snapshot=None, monotonic=lambda: 0,
        observer_type=lambda *_: nullcontext(observer), emit_progress=lambda *_: None,
        visit_fn=partial(visit, prepare_visit=Mock(return_value=prepared),
                         record_rejection=rejection, accept_publish=publish,
                         load_generation=None, measure_phase=lambda *_: nullcontext(),
                         emit_progress=lambda *_: None, record_cadence_attempt=cadence))
    assert outcome[:4] == ('VISIT_LIMIT', 1, 0, 0)
    assert outcome[-1] == 1
    journal.assert_called_once_with(tmp_path, parent, prepared.preflight)
    cadence.assert_called_once_with(tmp_path, authorization, 'target', 'PERFECT_TARGET_SKIPPED')
    rejection.assert_not_called()
    publish.assert_not_called()
