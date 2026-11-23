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
        _learning_first_epoch_key=None, _learning_first_epoch=None,
        _learning_first_planning=None, _learning_first_lawful_frontier=None,
        planning_generation_hits=0, planning_generation_misses=0,
        learning_first_epoch_hits=0, learning_first_epoch_misses=0,
    )


def _source_context(accepted_cache):
    return SimpleNamespace(
        release=SimpleNamespace(release_sha256="c" * 64),
        _accepted_runtime_host=SimpleNamespace(_accepted_cache=accepted_cache),
        _accepted_feature_context=SimpleNamespace(
            receipt=SimpleNamespace(digest="d" * 64)),
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


def test_learning_first_source_intent_draws_only_after_selection():
    from bilqis_mlx.runtime import priority_source_offer as offer_module
    from bilqis_mlx.runtime import priority_planning_generation as planning_module
    from bilqis_mlx.runtime._learning_first import priority_source_intent as intent_module
    from bilqis_mlx.runtime.tests.batch import test_atlas_training_adapter as fixture_module

    fixture = fixture_module.AtlasTrainingAdapterTest()
    fixture.setUp()
    try:
        context = replace(
            fixture.context, run_dir=Path("/run"), source_root=Path("/source"))
        planning = object.__new__(planning_module.PriorityPlanningGeneration)
        object.__setattr__(planning, "_issuance", planning_module._PLANNING_ISSUER)
        object.__setattr__(
            planning, "_target_registrar",
            SimpleNamespace(register=lambda *_args, **_kwargs: None))
        cache = SimpleNamespace(
            accepted_manifest_sha256="a" * 64, generation_binding="b" * 64)
        authenticated = SimpleNamespace(
            receipt=SimpleNamespace(
                generation_manifest_sha256=cache.accepted_manifest_sha256),
            features=SimpleNamespace(semantic_release="0" * 64))
        with evidence_mode(strict=False), patch.object(
                intent_module, "_require_planning_generation_identity",
                return_value=(cache, authenticated)), patch.object(
                offer_module, "_require_planning_generation_identity",
                return_value=(cache, authenticated)):
            intent = offer_module.plan_priority_source_intent(
                context, object(), "unused", capability="Z.C0",
                source_seed=17, source_each=4, planning_generation=planning)
            assert context._source_preparation_metrics.provider_draws == 0
            selected = offer_module.materialize_priority_source_intent(
                intent, context, object(), source_each=32)

        assert selected.capability_id == intent.capability_id == "Z.C0"
        assert selected.source_seed == intent.source_seed == 17
        assert selected.source_each == 32
        assert len(selected.rows()) == 32
        assert context._source_preparation_metrics.provider_draws == 1
    finally:
        fixture.doCleanups()
