"""Learning-first C05 target short-circuit and protected-cache contracts."""
from dataclasses import replace
from types import SimpleNamespace as N
from unittest.mock import ANY, Mock, patch

import bilqis_mlx.runtime.retention.local_screen as local_screen
import bilqis_mlx.runtime.retention.local_screen_stages as local_stages
import bilqis_mlx.runtime.retention.local_screen_support as local_support
from bilqis_mlx.runtime.capability_retention import (
    AssessmentPair,
    EvidenceStage,
    case_census_digest,
    evaluate_capabilities,
)
from bilqis_mlx.runtime.capability_retention_foundation import FoundationRetentionPolicy
from bilqis_mlx.runtime.baseline.currentness import BaselineCoverage
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.retention.local_evaluation import (
    evaluate_target_gate,
    finalize_target_first_local_candidate,
)
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import (
    CANDIDATE,
    PARENT,
    _screen_inputs,
)


def _live_short_circuit_fixture():
    target, protected = "future.target", "future.protected"
    target_plan = N(
        target_capability_id=target, target_grade_id="opaque-grade",
        protected_capability_ids=(protected,),
        evaluated_capability_ids=(target, protected),
        evaluated_capability_groups=(
            (target, "opaque-grade"), (protected, "prior-grade")),
        evaluation_scope_sha256="1" * 64, comparison_scope_sha256="2" * 64,
    )
    return N(
        target=target, protected=protected, target_plan=target_plan,
        plan=N(digest="3" * 64, rubric_sha256="4" * 64, source_sha256="5" * 64),
        release=N(release_sha256="6" * 64), parent=N(baseline_evidence=None),
        cache=N(), target_instrument=N(case=N(capability_id=target)),
        rejection=object(),
        protected_compile=Mock(side_effect=AssertionError(
            "protected compilation ran before target rejection")),
        fresh_rows=Mock(return_value=N(
            seed=13, rows=({"id": "fresh", "capability": target},))),
        target_cohort=object(),
        assessments=Mock(side_effect=(object(), object())),
        solvers=Mock(side_effect=((object(), "a" * 64), (object(), "b" * 64))),
        observed=[],
    )


def _assert_short_circuit_profile(observed, target):
    profile = {}
    for event in observed:
        profile.update(event)
    assert profile["retention_target_case_count"] == 1
    assert profile["retention_target_shared_backbone_launches"] == 0
    assert profile["retention_target_scalar_neural_launches"] == 0
    progress = [event for event in observed if "retention_completed" in event]
    assert [(event["retention_completed"], event["retention_total"],
             event["retention_subject"], event["retention_role"])
            for event in progress] == [
                (0, 4, target, "parent"),
                (1, 4, target, "parent"),
                (1, 4, target, "candidate"),
                (2, 4, target, "candidate"),
            ]
    for field in (
            "retention_target_prepare_wall_seconds",
            "retention_target_solver_wall_seconds",
            "retention_target_parent_wall_seconds",
            "retention_target_candidate_wall_seconds"):
        assert isinstance(profile[field], float)
        assert profile[field] >= 0.0
    assert "retention_protected_prepare_wall_seconds" not in profile


def test_learning_first_target_seed_uses_lightweight_candidate_coordinates():
    state = N(optimizer=N(parameters=object()), optimizer_step=11)
    bundle = N(
        run_id="run", generation=7,
        topology=N(digest="1" * 64), extents=N(digest="2" * 64))
    with evidence_mode(strict=False):
        identity = local_stages._candidate_seed_identity(state, bundle)
        repeated = local_stages._candidate_seed_identity(state, bundle)
    assert isinstance(identity, str) and len(identity) == 64
    assert identity == repeated


def test_learning_first_screen_reuses_session_feature_context_without_candidate_auth():
    fixture = _live_short_circuit_fixture()
    feature_context = object()
    source_context = N(run_dir=None, _accepted_feature_context=feature_context)
    decision = object()
    with (
        evidence_mode(strict=False),
        patch.object(
            local_screen, "authenticate_bamf_execution_feature_context",
            side_effect=AssertionError("learning-first C05 reauthenticated features")),
        patch.object(
            local_screen, "target_stage",
            return_value=(
                fixture.target, (), (), object(), object(), object(), decision)) as stage,
    ):
        result = local_screen.foundation_local_retention_screen(
            source_context, fixture.parent, object(), object(), "artifact",
            fixture.release, fixture.plan, fixture.target_plan,
            (("trained-family",), ("trained-episode",)), (), fixture.cache)

    assert result[0] is decision
    assert result[3] is fixture.cache
    assert stage.call_args.kwargs["authenticated"] is feature_context


def test_live_screen_short_circuits_before_protected_compilation():
    fixture = _live_short_circuit_fixture()
    candidate_bundle = N(
        run_id="run", generation=1,
        topology=N(digest="7" * 64), extents=N(digest="8" * 64))

    def fresh_only_instruments(_context, _candidate, _artifact, rows, **_kwargs):
        if rows and rows[0].get("id") == "reference":
            raise AssertionError("learning-first compiled reference-only baseline row")
        return (fixture.target_instrument,)

    with evidence_mode(strict=False), patch.multiple(
            local_stages,
            split_cached_rows=Mock(return_value=(
                (7, ({"id": "reference", "capability": fixture.target},)),
                ((fixture.protected, 8, ({
                    "id": "protected", "capability": fixture.protected},)),))),
            comparison_epoch=Mock(return_value=N(identity=lambda capability: capability)),
            BaselineLedger=N(from_optional_record=Mock(return_value=object())),
            baseline_coverage=Mock(return_value=N()),
            _owner_seed=Mock(return_value=11),
            _fresh_rows=fixture.fresh_rows,
            _instruments=Mock(side_effect=fresh_only_instruments),
            foundation_policy=Mock(return_value=object()),
            _cohort=Mock(return_value=fixture.target_cohort),
            factory_complete_solver=fixture.solvers,
            evaluate_capabilities=fixture.assessments,
            AssessmentPair=Mock(return_value=object()),
            evaluate_target_gate=Mock(return_value=fixture.rejection),
            cached_instruments=fixture.protected_compile), patch.object(
                local_stages, "factory_evaluation_case_from_source",
                create=True, return_value=fixture.target_instrument.case) as reference_case, patch.object(
                local_screen, "authenticate_bamf_execution_feature_context",
                return_value=N(features=N(semantic_release="9" * 64))):
        result = local_screen.foundation_local_retention_screen(
            N(
                run_dir=None,
                _accepted_feature_context=N(features=N(semantic_release="9" * 64))),
            fixture.parent, candidate_bundle, N(optimizer_step=13), "artifact",
            fixture.release, fixture.plan, fixture.target_plan,
            (("trained-family",), ("trained-episode",)),
            ((fixture.target, 7, ({"id": "reference", "capability": fixture.target},)),
             (fixture.protected, 8, ({
                 "id": "protected", "capability": fixture.protected},))),
            fixture.cache, observer=fixture.observed.append)

    assert result[0] is fixture.rejection
    assert fixture.solvers.call_args_list[0].kwargs.get(
        "execution_cache") is fixture.cache
    assert fixture.solvers.call_args_list[1].kwargs.get("execution_cache") is None
    fixture.protected_compile.assert_not_called()
    reference_case.assert_called_once()
    fixture.fresh_rows.assert_called_once_with(
        ANY,
        (fixture.target,), seed=11 + local_stages.C05_FRESH_TARGET_SEED_OFFSET,
        training=(("trained-family",), ("trained-episode",)),
        require_independent=False)
    assert fixture.assessments.call_args_list[0].args[1] is fixture.target_cohort
    assert fixture.assessments.call_args_list[1].args[1] is fixture.target_cohort
    _assert_short_circuit_profile(fixture.observed, fixture.target)


def test_protected_parent_cache_hit_skips_parent_solver_construction():
    protected = "prior.protected"
    instrument = N(case=N(capability_id=protected))
    target_plan = N(
        evaluated_capability_groups=((protected, "prior-grade"),),
        protected_capability_ids=(protected,),
        evaluation_scope_sha256="1" * 64,
    )
    plan = N(digest="2" * 64, rubric_sha256="3" * 64, source_sha256="4" * 64)
    cache = N(generation_binding="5" * 64)
    cached_assessment = object()
    cache_receipt = N(reused=True)
    parent = object()
    candidate = object()
    candidate_solver = object()
    solver = Mock(return_value=(candidate_solver, "6" * 64))

    with patch.multiple(
            local_stages,
            cached_instruments=Mock(return_value=(instrument,)),
            local_coverage=Mock(return_value=N()),
            foundation_policy=Mock(return_value=object()),
            _cohort=Mock(return_value=object()),
            factory_parent_assessment_identity=Mock(return_value=object()),
            lookup_parent_assessment=Mock(return_value=(
                cached_assessment, cache_receipt)),
            use_parent_assessment=Mock(return_value=(cached_assessment, cache_receipt)),
            factory_complete_solver=solver,
            observed_assessment=Mock(return_value=object()),
            AssessmentPair=Mock(side_effect=lambda parent, candidate: N(
                parent=parent, candidate=candidate)),
            solver_profile=Mock()):
        pair, receipt, _ = local_stages.reference_stage(
            object(), parent, candidate, "artifact", object(), plan,
            target_plan, (), ((protected, 7, ({"id": "p"},)),), cache, N())

    assert receipt is cache_receipt
    assert pair.parent is cached_assessment
    assert solver.call_count == 1
    assert solver.call_args.args[1] is candidate
