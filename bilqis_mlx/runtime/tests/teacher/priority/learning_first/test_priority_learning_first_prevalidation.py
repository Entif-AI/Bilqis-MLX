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


def test_learning_first_epoch_validation_trusts_owner_objects_without_full_reproof():
    from bilqis_mlx.runtime.lawful_teaching_frontier import (
        _validate_learning_first_epoch,
    )
    from bilqis_mlx.runtime.priority_planning_owner import PriorityPlanningEpoch

    release = SimpleNamespace(
        release_sha256="a" * 64,
        verify=lambda: (_ for _ in ()).throw(
            AssertionError("learning-first must not reverify release")),
    )
    source = SimpleNamespace(
        frontier=SimpleNamespace(rights_epoch=3, correction_generation=4),
        policy=SimpleNamespace(policy_epoch=5),
        authority_registry_sha256="b" * 64,
    )
    snapshot = SimpleNamespace(
        admitted_factory_release_sha256=release.release_sha256,
        snapshot_sha256="c" * 64,
        rights_epoch=3,
        correction_generation=4,
        policy_epoch=5,
        verify=lambda: (_ for _ in ()).throw(
            AssertionError("learning-first must not reverify snapshot")),
    )
    closure = SimpleNamespace(
        snapshot_sha256=snapshot.snapshot_sha256,
        verify=lambda: (_ for _ in ()).throw(
            AssertionError("learning-first must not reverify closure")),
    )
    checkpoint = SimpleNamespace(sha256="d" * 64, optimizer_step=17)
    epoch = PriorityPlanningEpoch(
        release, object(), snapshot, closure, (), None, object(), object(),
        checkpoint, source)
    parent = SimpleNamespace(retained_state=SimpleNamespace(optimizer_step=18))
    source_context = SimpleNamespace(release=release)
    generation = SimpleNamespace(
        _source_context=source_context,
        _parent=parent,
        release_sha256=release.release_sha256,
        parent_candidate_identity_sha256="e" * 64,
    )

    assert _validate_learning_first_epoch(
        epoch, generation, source_context, parent) is source


def test_learning_first_owner_planning_verification_uses_identity_witness_only():
    from bilqis_mlx.runtime import priority_qualification

    snapshot = SimpleNamespace(snapshot_sha256="1" * 64)
    progress = SimpleNamespace(
        input_snapshot=snapshot,
        input_snapshot_sha256=snapshot.snapshot_sha256,
    )
    closure = SimpleNamespace(closure_sha256="2" * 64)
    selection = SimpleNamespace(selection_sha256="3" * 64)
    projection = SimpleNamespace(projection_sha256="4" * 64)
    release = SimpleNamespace(release_sha256="5" * 64)
    planning = priority_qualification._issue_internal_priority_planning(
        progress, closure, selection, projection, release=release)

    with evidence_mode(strict=False), patch.object(
            priority_qualification, "_planning",
            side_effect=AssertionError("ordinary planning replayed full proof")):
        priority_qualification._verify_planning(planning, release, None)


def test_strict_owner_planning_verification_still_runs_full_proof():
    from bilqis_mlx.runtime import priority_qualification

    snapshot = SimpleNamespace(snapshot_sha256="1" * 64)
    progress = SimpleNamespace(
        input_snapshot=snapshot,
        input_snapshot_sha256=snapshot.snapshot_sha256,
    )
    closure = SimpleNamespace(closure_sha256="2" * 64)
    selection = SimpleNamespace(selection_sha256="3" * 64)
    projection = SimpleNamespace(projection_sha256="4" * 64)
    release = SimpleNamespace(release_sha256="5" * 64)
    planning = priority_qualification._issue_internal_priority_planning(
        progress, closure, selection, projection, release=release)

    with evidence_mode(strict=True), patch.object(
            priority_qualification, "_planning") as full_proof, patch.object(
                priority_qualification, "_mint_planning_verification"):
        priority_qualification._verify_planning(planning, release, None)

    full_proof.assert_called_once_with(planning, release)


def test_learning_first_semantic_candidate_does_not_publish_restart_memo():
    from bilqis_mlx.factory import skos_curriculum
    from bilqis_mlx.runtime.priority_planning_parts import candidate_memo
    from bilqis_mlx.runtime.priority_planning_parts import epoch as epoch_module

    selection = SimpleNamespace(release_sha256="a" * 64)
    candidate = object()
    with patch.object(
            candidate_memo, "load_candidate_memo", return_value=None), patch.object(
                candidate_memo, "persist_candidate_memo",
                side_effect=AssertionError("learning-first published restart memo")), patch.object(
                    skos_curriculum, "_compile_semantic_curriculum_snapshot",
                    return_value=candidate):
        result = epoch_module._semantic_candidate(
            "/run", selection, object(), (), None, persist_memo=False)

    assert result is candidate


def test_default_semantic_candidate_still_publishes_restart_memo():
    from bilqis_mlx.factory import skos_curriculum
    from bilqis_mlx.runtime.priority_planning_parts import candidate_memo
    from bilqis_mlx.runtime.priority_planning_parts import epoch as epoch_module

    selection = SimpleNamespace(release_sha256="a" * 64)
    candidate = object()
    with patch.object(
            candidate_memo, "load_candidate_memo", return_value=None), patch.object(
                candidate_memo, "persist_candidate_memo") as persist, patch.object(
                    skos_curriculum, "_compile_semantic_curriculum_snapshot",
                    return_value=candidate):
        result = epoch_module._semantic_candidate(
            "/run", selection, object(), (), None)

    assert result is candidate
    persist.assert_called_once_with("/run", selection, (), candidate)


def test_learning_first_planning_snapshot_uses_prevalidated_owner_builder():
    from bilqis_mlx.factory import atlas_runtime_snapshot
    from bilqis_mlx.runtime.priority_planning_parts import epoch as epoch_module

    snapshot = object()
    candidate = SimpleNamespace()
    source = SimpleNamespace(frontier=object(), policy=object())
    frontier = SimpleNamespace()
    current = SimpleNamespace(
        execution_plan=SimpleNamespace(grades=()))
    feature_receipt = SimpleNamespace(acceptance_sha256="a" * 64)
    with patch.object(
            atlas_runtime_snapshot, "build_accepted_executable_snapshot",
            side_effect=AssertionError(
                "learning-first replayed public snapshot proof")), patch.object(
                    atlas_runtime_snapshot,
                    "build_accepted_executable_snapshot_prevalidated",
                    return_value=snapshot) as prevalidated:
        result = epoch_module._planning_snapshot(
            candidate, source, frontier, current, (), feature_receipt, None,
            None, None, learning_first=True)

    assert result is snapshot
    assert prevalidated.call_count == 1


def test_strict_planning_snapshot_keeps_public_snapshot_proof():
    from bilqis_mlx.factory import atlas_runtime_snapshot
    from bilqis_mlx.runtime.priority_planning_parts import epoch as epoch_module

    snapshot = object()
    candidate = SimpleNamespace()
    source = SimpleNamespace(frontier=object(), policy=object())
    frontier = SimpleNamespace()
    current = SimpleNamespace(
        execution_plan=SimpleNamespace(grades=()))
    feature_receipt = SimpleNamespace(acceptance_sha256="a" * 64)
    with patch.object(
            atlas_runtime_snapshot, "build_accepted_executable_snapshot",
            return_value=snapshot) as public, patch.object(
                atlas_runtime_snapshot,
                "build_accepted_executable_snapshot_prevalidated",
                side_effect=AssertionError(
                    "strict planning used prevalidated snapshot path")):
        result = epoch_module._planning_snapshot(
            candidate, source, frontier, current, (), feature_receipt, None,
            None, None, learning_first=False)

    assert result is snapshot
    assert public.call_count == 1
