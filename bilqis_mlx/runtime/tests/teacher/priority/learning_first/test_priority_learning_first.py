"""Ordinary BAMF priority must remain learning-first rather than evidence-first."""
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.runtime import priority_rejection_replay as rejection_replay
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.tests.teacher.priority.authority.test_priority_signer import (
    _cadence,
    _foundation_case,
)


def _planning_cache():
    return SimpleNamespace(
        _planning_generation_key=None, _planning_generation=None,
        _learning_first_epoch_key=None, _learning_first_authority_key=None,
        _learning_first_epoch=None, _learning_first_planning=None,
        _learning_first_lawful_frontier=None,
        planning_generation_hits=0, planning_generation_misses=0,
        learning_first_epoch_hits=0, learning_first_epoch_misses=0,
        learning_first_publication_reuses=0,
    )


def _source_context(accepted_cache):
    return SimpleNamespace(
        release=SimpleNamespace(release_sha256="c" * 64),
        _accepted_runtime_host=SimpleNamespace(_accepted_cache=accepted_cache),
        _accepted_feature_context=SimpleNamespace(
            receipt=SimpleNamespace(digest="d" * 64)),
    )


def _phase_frontier(*, activation="1" * 64, definition="2" * 64,
                    ready=("capability:alpha",), complete=()):
    complete = set(complete)
    return SimpleNamespace(
        active_grade_activation_sha256=activation,
        active_grade_definition_sha256=definition,
        ready_capability_ids=tuple(ready),
        capabilities=tuple(
            SimpleNamespace(
                capability_id=capability,
                disposition=("EVIDENCE_COMPLETE" if capability in complete else "READY"),
            )
            for capability in set(ready) | complete
        ),
    )


def _phase_state(*, activation="1" * 64, definition="2" * 64,
                 phase=("capability:alpha",), attempted=()):
    return SimpleNamespace(
        active_grade_activation_sha256=activation,
        active_grade_definition_sha256=definition,
        phase_capability_ids=tuple(phase),
        attempted_capability_ids=tuple(attempted),
    )


def test_learning_first_reuses_planning_generation_within_accepted_generation():
    from bilqis_mlx.runtime import priority_authority as authority

    accepted_cache = SimpleNamespace(
        accepted_manifest_sha256="a" * 64, generation_binding="b" * 64)
    source_context = _source_context(accepted_cache)
    parent = SimpleNamespace(correction_frontier={})
    planning_cache = _planning_cache()
    generation = object()
    with evidence_mode(strict=False), patch.object(
            authority, "bind_priority_planning_generation",
            return_value=generation) as bind, patch.object(
            authority, "_require_planning_generation_identity",
            return_value=(accepted_cache, object())), patch.object(
            authority, "_build_priority_planning_epoch",
            return_value="epoch") as build_epoch, patch.object(
            authority, "_priority_planning_from_epoch",
            return_value="planning") as project_planning, patch(
            "bilqis_mlx.runtime.lawful_teaching_frontier."
            "_issue_lawful_teaching_frontier_from_epoch",
            return_value="frontier") as issue_frontier:
        first = authority._bind_lawful_priority_epoch(
            "/run", source_context, parent, "/atlas", None,
            planning_cache=planning_cache)
        second = authority._bind_lawful_priority_epoch(
            "/run", source_context, parent, "/atlas", None,
            planning_cache=planning_cache)

    assert first[0] is second[0] is generation
    assert bind.call_count == 1
    assert first[2:] == second[2:] == ("epoch", "planning", "frontier")
    assert build_epoch.call_count == project_planning.call_count == 1
    # One unchanged accepted parent owns one process-live frontier. Publication
    # to a new parent is covered separately and must reissue learner-relative
    # readiness against that successor.
    assert issue_frontier.call_count == 1
    assert planning_cache.planning_generation_misses == 1
    assert planning_cache.planning_generation_hits == 1
    assert planning_cache.learning_first_epoch_misses == 1
    assert planning_cache.learning_first_epoch_hits == 1


def test_learning_first_planning_snapshot_invalidates_with_accepted_parent():
    from bilqis_mlx.runtime import priority_authority as authority

    accepted_cache = SimpleNamespace(
        accepted_manifest_sha256="a" * 64, generation_binding="b" * 64)
    source_context = _source_context(accepted_cache)
    first_parent = SimpleNamespace(correction_frontier={})
    second_parent = SimpleNamespace(correction_frontier={})
    planning_cache = _planning_cache()
    generations = (object(), object())
    with evidence_mode(strict=False), patch.object(
            authority, "bind_priority_planning_generation",
            side_effect=generations) as bind, patch.object(
            authority, "_require_planning_generation_identity",
            return_value=(accepted_cache, object())), patch.object(
            authority, "_build_priority_planning_epoch",
            side_effect=("epoch-1", "epoch-2")) as build_epoch, patch.object(
            authority, "_priority_planning_from_epoch",
            side_effect=("planning-1", "planning-2")), patch(
            "bilqis_mlx.runtime.lawful_teaching_frontier."
            "_issue_lawful_teaching_frontier_from_epoch",
            side_effect=("frontier-1", "frontier-2")):
        first = authority._bind_lawful_priority_epoch(
            "/run", source_context, first_parent, "/atlas", None,
            planning_cache=planning_cache)
        second = authority._bind_lawful_priority_epoch(
            "/run", source_context, second_parent, "/atlas", None,
            planning_cache=planning_cache)

    assert first[0] is generations[0]
    assert second[0] is generations[1]
    assert bind.call_count == build_epoch.call_count == 2
    assert planning_cache.learning_first_epoch_misses == 2
    assert planning_cache.learning_first_epoch_hits == 0


def test_learning_first_reuses_phase_authority_after_accepted_publication():
    from bilqis_mlx.runtime import priority_authority as authority

    first_cache = SimpleNamespace(
        accepted_manifest_sha256="a" * 64, generation_binding="b" * 64)
    second_cache = SimpleNamespace(
        accepted_manifest_sha256="e" * 64, generation_binding="f" * 64)
    first_context = _source_context(first_cache)
    second_context = _source_context(second_cache)
    first_parent = SimpleNamespace(correction_frontier={})
    second_parent = SimpleNamespace(correction_frontier={})
    planning_cache = _planning_cache()
    generations = (object(), object())
    with evidence_mode(strict=False), patch.object(
            authority, "bind_priority_planning_generation",
            side_effect=generations) as bind, patch.object(
            authority, "_require_planning_generation_identity",
            side_effect=((first_cache, object()), (second_cache, object()))), patch.object(
            authority, "_build_priority_planning_epoch",
            return_value="epoch") as build_epoch, patch.object(
            authority, "_priority_planning_from_epoch",
            return_value="planning") as project_planning, patch(
            "bilqis_mlx.runtime.lawful_teaching_frontier."
            "_issue_lawful_teaching_frontier_from_epoch",
            return_value="frontier") as issue_frontier, patch(
            "bilqis_mlx.runtime._learning_first.priority_frontier."
            "can_reuse_learning_first_phase_authority",
            return_value=True):
        first = authority._bind_lawful_priority_epoch(
            "/run", first_context, first_parent, "/atlas", None,
            planning_cache=planning_cache)
        second = authority._bind_lawful_priority_epoch(
            "/run", second_context, second_parent, "/atlas", None,
            planning_cache=planning_cache)

    assert first[0] is generations[0]
    assert second[0] is generations[1]
    assert first[2:] == second[2:] == ("epoch", "planning", "frontier")
    assert bind.call_count == 2
    assert build_epoch.call_count == project_planning.call_count == 1
    assert issue_frontier.call_count == 2
    assert planning_cache.learning_first_epoch_misses == 1
    assert planning_cache.learning_first_epoch_hits == 1
    assert planning_cache.learning_first_publication_reuses == 1


def test_learning_first_phase_reuse_fails_closed_without_current_cadence():
    from bilqis_mlx.runtime._learning_first.priority_frontier import (
        can_reuse_learning_first_phase_authority,
    )

    with patch(
            "bilqis_mlx.runtime.active_grade_cadence_custody.read_current_cadence",
            return_value=None):
        assert not can_reuse_learning_first_phase_authority(
            "/run", _phase_frontier())


def test_learning_first_phase_reuse_fails_closed_when_phase_is_exhausted():
    from bilqis_mlx.runtime._learning_first.priority_frontier import (
        can_reuse_learning_first_phase_authority,
    )

    state = _phase_state(attempted=("capability:alpha",))
    with patch(
            "bilqis_mlx.runtime.active_grade_cadence_custody.read_current_cadence",
            return_value=state):
        assert not can_reuse_learning_first_phase_authority(
            "/run", _phase_frontier())


def test_learning_first_phase_reuse_fails_closed_on_grade_identity_change():
    from bilqis_mlx.runtime._learning_first.priority_frontier import (
        can_reuse_learning_first_phase_authority,
    )

    cases = (
        _phase_state(activation="3" * 64),
        _phase_state(definition="4" * 64),
    )
    for state in cases:
        with patch(
                "bilqis_mlx.runtime.active_grade_cadence_custody.read_current_cadence",
                return_value=state):
            assert not can_reuse_learning_first_phase_authority(
                "/run", _phase_frontier())
