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


def test_learning_first_phase_reuse_requires_unattempted_ready_member():
    from bilqis_mlx.runtime._learning_first.priority_frontier import (
        can_reuse_learning_first_phase_authority,
    )

    state = _phase_state(phase=("capability:alpha", "capability:beta"))
    frontier = _phase_frontier(
        ready=("capability:alpha",), complete=("capability:alpha",))
    with patch(
            "bilqis_mlx.runtime.active_grade_cadence_custody.read_current_cadence",
            return_value=state):
        assert not can_reuse_learning_first_phase_authority("/run", frontier)


def test_learning_first_publication_reuse_rebuilds_on_release_authority_change():
    from bilqis_mlx.runtime import priority_authority as authority

    first_cache = SimpleNamespace(
        accepted_manifest_sha256="a" * 64, generation_binding="b" * 64)
    second_cache = SimpleNamespace(
        accepted_manifest_sha256="e" * 64, generation_binding="f" * 64)
    first_context = _source_context(first_cache)
    second_context = _source_context(second_cache)
    second_context.release.release_sha256 = "9" * 64
    planning_cache = _planning_cache()
    generations = (object(), object())
    with evidence_mode(strict=False), patch.object(
            authority, "bind_priority_planning_generation",
            side_effect=generations), patch.object(
            authority, "_require_planning_generation_identity",
            side_effect=((first_cache, object()), (second_cache, object()))), patch.object(
            authority, "_build_priority_planning_epoch",
            side_effect=("epoch-1", "epoch-2")) as build_epoch, patch.object(
            authority, "_priority_planning_from_epoch",
            side_effect=("planning-1", "planning-2")), patch(
            "bilqis_mlx.runtime.lawful_teaching_frontier."
            "_issue_lawful_teaching_frontier_from_epoch",
            side_effect=("frontier-1", "frontier-2")), patch(
            "bilqis_mlx.runtime._learning_first.priority_frontier."
            "can_reuse_learning_first_phase_authority",
            return_value=True):
        authority._bind_lawful_priority_epoch(
            "/run", first_context, SimpleNamespace(correction_frontier={}),
            "/atlas", None, planning_cache=planning_cache)
        authority._bind_lawful_priority_epoch(
            "/run", second_context, SimpleNamespace(correction_frontier={}),
            "/atlas", None, planning_cache=planning_cache)

    assert build_epoch.call_count == 2
    assert planning_cache.learning_first_publication_reuses == 0


def test_learning_first_publication_reuse_rebuilds_on_correction_change():
    from bilqis_mlx.runtime import priority_authority as authority

    first_cache = SimpleNamespace(
        accepted_manifest_sha256="a" * 64, generation_binding="b" * 64)
    second_cache = SimpleNamespace(
        accepted_manifest_sha256="e" * 64, generation_binding="f" * 64)
    planning_cache = _planning_cache()
    generations = (object(), object())
    with evidence_mode(strict=False), patch.object(
            authority, "bind_priority_planning_generation",
            side_effect=generations), patch.object(
            authority, "_require_planning_generation_identity",
            side_effect=((first_cache, object()), (second_cache, object()))), patch.object(
            authority, "_build_priority_planning_epoch",
            side_effect=("epoch-1", "epoch-2")) as build_epoch, patch.object(
            authority, "_priority_planning_from_epoch",
            side_effect=("planning-1", "planning-2")), patch(
            "bilqis_mlx.runtime.lawful_teaching_frontier."
            "_issue_lawful_teaching_frontier_from_epoch",
            side_effect=("frontier-1", "frontier-2")), patch(
            "bilqis_mlx.runtime._learning_first.priority_frontier."
            "can_reuse_learning_first_phase_authority",
            return_value=True):
        authority._bind_lawful_priority_epoch(
            "/run", _source_context(first_cache),
            SimpleNamespace(correction_frontier={}), "/atlas", None,
            planning_cache=planning_cache)
        authority._bind_lawful_priority_epoch(
            "/run", _source_context(second_cache),
            SimpleNamespace(correction_frontier={"epoch": 2}), "/atlas", None,
            planning_cache=planning_cache)

    assert build_epoch.call_count == 2
    assert planning_cache.learning_first_publication_reuses == 0


def test_strict_mode_never_reuses_learning_first_planning_snapshot():
    from bilqis_mlx.runtime import priority_authority as authority

    source_context = SimpleNamespace(release=SimpleNamespace(release_sha256="c" * 64))
    parent = SimpleNamespace(correction_frontier={})
    planning_cache = _planning_cache()
    planning_cache._learning_first_epoch_key = ("cached",)
    planning_cache._learning_first_epoch = "cached-epoch"
    planning_cache._learning_first_planning = "cached-planning"
    planning_cache._learning_first_lawful_frontier = "cached-frontier"
    generations = (object(), object())
    with evidence_mode(strict=True), patch.object(
            authority, "bind_priority_planning_generation",
            side_effect=generations) as bind, patch.object(
            authority, "_require_planning_generation",
            return_value=(object(), object())), patch.object(
            authority, "_build_priority_planning_epoch",
            side_effect=("epoch-1", "epoch-2")) as build_epoch, patch.object(
            authority, "_priority_planning_from_epoch",
            side_effect=("planning-1", "planning-2")), patch(
            "bilqis_mlx.runtime.lawful_teaching_frontier."
            "_issue_lawful_teaching_frontier_from_epoch",
            side_effect=("frontier-1", "frontier-2")):
        authority._bind_lawful_priority_epoch(
            "/run", source_context, parent, "/atlas", None,
            planning_cache=planning_cache)
        authority._bind_lawful_priority_epoch(
            "/run", source_context, parent, "/atlas", None,
            planning_cache=planning_cache)

    assert bind.call_count == build_epoch.call_count == 2
    assert planning_cache.learning_first_epoch_hits == 0
    assert planning_cache.learning_first_epoch_misses == 0


def test_learning_first_priority_never_enters_signed_salience_evidence_plane():
    from bilqis_mlx.runtime import priority_authority as authority

    (registry, _signer, source_context, planning, parent,
     planning_generation, _offer, cache, lawful) = _foundation_case()
    intents = tuple(
        (capability, SimpleNamespace(
            capability_id=capability, source_seed=index + 1, source_each=2,
            source_binding_digest="e" * 64,
            release_sha256=source_context.release.release_sha256,
            accepted_manifest_sha256=cache.accepted_manifest_sha256,
            generation_binding="d" * 64))
        for index, capability in enumerate(("capability:alpha", "capability:beta")))
    plane = SimpleNamespace(sync_event_ledger=lambda *_args: None)
    with TemporaryDirectory() as run_dir, evidence_mode(strict=False), patch.object(
        rejection_replay, "data_plane", return_value=plane), patch(
        "bilqis_mlx.runtime.bamf_bundle.accepted_runtime._accepted_correction_registry",
        return_value=(cache, registry)), patch(
        "bilqis_mlx.runtime.bamf_bundle._darwin_salience_signer."
        "read_host_system_source_authority_signer",
        side_effect=AssertionError("learning-first planning must not load the signer")), patch.object(
        authority, "bind_priority_planning_generation",
        return_value=planning_generation), patch.object(
        authority, "_require_planning_generation_identity",
        return_value=(cache, None)), patch.object(
        authority, "_priority_offers",
        return_value=((SimpleNamespace(capability_id="capability:alpha"),
                       SimpleNamespace(capability_id="capability:beta")), intents)), patch.object(
        authority, "priority_rotation_state",
        return_value=(1, {"capability:alpha": 1})), patch.object(
        authority, "_build_priority_planning_epoch", return_value="epoch"), patch.object(
        authority, "_priority_planning_from_epoch", return_value=planning), patch(
        "bilqis_mlx.runtime.lawful_teaching_frontier."
        "_issue_lawful_teaching_frontier_from_epoch", return_value=lawful), patch(
        "bilqis_mlx.runtime.active_grade_cadence.issue_active_grade_cadence",
        return_value=_cadence("capability:alpha", "capability:beta")), patch.object(
        authority, "_ordered_rejections", return_value=()), patch.object(
        authority, "_rejection_recency", return_value=(0, {})), patch.object(
        authority, "_priority_options",
        side_effect=AssertionError("learning-first planning must not mint C06 facts")), patch.object(
        authority, "_priority_history",
        side_effect=AssertionError("learning-first planning must not mint C06 history")):
        issued = authority.issue_foundation_priority_authority(
            run_dir, source_context, parent, {"epoch": 1}, "/atlas",
            teacher_state=parent.teacher_state, logical_batch_size=32)

    assert issued.history is None
    assert tuple(option.stable_id for option in issued.frontier.options) == (
        "capability:beta", "capability:alpha")
