"""Shared fixtures for adversarial Factory-owned C05 admission tests."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bilqis_mlx.learning.atlas_candidate import CandidateTransaction
import bilqis_mlx.runtime.factory_retention_owner as owner
import bilqis_mlx.runtime.retention.screen as owner_screen
import bilqis_mlx.runtime.retention.local_screen as local_screen
import bilqis_mlx.runtime.retention.local_screen_stages as local_stages
import bilqis_mlx.runtime.retention.local_screen_support as local_support
from bilqis_mlx.runtime.factory_retention_owner import evaluate_factory_retention_candidate
from bilqis_mlx.runtime.capability_retention import Decision, DecisionStatus


def _foundation_owner_fixture():
    release_sha = "a" * 64
    target = "B.IDBOOLOPS"
    capabilities = (
        SimpleNamespace(capability_id="B.AND", grade_id="B"),
        SimpleNamespace(capability_id=target, grade_id="B"),
    )
    release = SimpleNamespace(
        release_sha256=release_sha,
        semantic_catalog_sha256="b" * 64,
        execution_plan=SimpleNamespace(
            capabilities=capabilities,
            capability_map={item.capability_id: item for item in capabilities},
            grades=(SimpleNamespace(
                grade_id="B", assessment_blueprint_sha256="c" * 64),),
            curriculum_sha256="d" * 64,
            profile_id="factory-c05-adversarial",
            projection_digests=SimpleNamespace(
                roster="e" * 64, assessment="f" * 64,
                coverage="0" * 64, source="1" * 64),
        ),
    )
    source = SimpleNamespace(
        __post_init__=lambda: None,
        release=release,
        run_dir=Path("unused"),
        require_accepted_runtime=Mock(),
    )
    candidate = object.__new__(CandidateTransaction)
    object.__setattr__(candidate, "training_authorities", (
        SimpleNamespace(delivery_capability=target, release_sha256=release_sha),
    ))
    object.__setattr__(candidate, "_parent_identity_sha256", "d" * 64)
    fixed = SimpleNamespace(rows=({"id": "fixed"},), seed=7)
    fresh = Mock(return_value=SimpleNamespace(
        seed=13, rows=({"id": "fresh", "capability": target},)))
    policy_factory = Mock(return_value=object())
    decision = Decision(
        DecisionStatus.ELIGIBLE, "PAIRED_SCREEN_WITHIN_BUDGET",
        "a" * 64, "b" * 64, "c" * 64, "d" * 64,
        evaluated_capability_ids=(target,),
        retention_protection_plan_sha256="3" * 64)
    return source, candidate, target, fixed, fresh, policy_factory, decision


def _foundation_retention_plan(target):
    target_plan = SimpleNamespace(
        target_capability_id=target,
        target_grade_id="B",
        protected_capability_ids=(),
        evaluated_capability_ids=(target,),
        evaluated_capability_groups=((target, "B"),),
        evaluation_scope_sha256="1" * 64,
        comparison_scope_sha256="2" * 64,
    )
    plan = SimpleNamespace(
        digest="3" * 64, rubric_sha256="4" * 64,
        policy_epoch_sha256="5" * 64, source_sha256="6" * 64,
        established_capability_ids=(),
        evidence_stage=owner.CURRENT_EVIDENCE_STAGE.value,
        for_target=lambda capability: target_plan if capability == target else None,
    )
    instrument = SimpleNamespace(
        case=SimpleNamespace(capability_id=target, case_id="fixture-case"))
    return plan, target_plan, instrument


def _evaluate_foundation_owner(source, candidate, target, fixed, fresh,
                               policy_factory, decision, *,
                               championship_cohort=None,
                               championship_assessment=None,
                               target_gate_decision=None):
    release_sha = source.release.release_sha256
    plan, target_plan, instrument = _foundation_retention_plan(target)
    with patch(
            "bilqis_mlx.runtime.bamf_bundle.genesis.records."
            "successor_candidate_identity_digest", return_value="f" * 64), \
            patch.multiple(
                owner,
                create=True,
                _training_exclusions=Mock(
                    return_value=(("trained-family",), ("trained-episode",))),
                _candidate_from_live_parent=Mock(return_value=(
                    SimpleNamespace(
                        retained_state=object(), run_identity=None,
                        run_id="fixture-run", generation=0, baseline_evidence=None,
                        correction_frontier={}, evaluation_contract={}),
                    SimpleNamespace(
                        retained_state=object(),
                        parent_manifest_sha256="0" * 64,
                        transition={
                            "schema": "bilqis.mlx.bamf-generation-transition/v3",
                            "kind": "MOTIF_ALLOCATION",
                        }),
                    object(), SimpleNamespace(
                        run_id="fixture-run",
                        accepted_manifest_sha256="0" * 64,
                        source_authority_registry_sha256=None))),
                require_current_retention_source_rows=Mock(
                    return_value=(plan, target_plan, ((target, 7, ({"id": "row"},)),))),
                candidate_identity_digest=Mock(return_value="d" * 64),
                _owner_seed=Mock(return_value=11),
                read_current=Mock(return_value={"factory_release_sha256": release_sha}),
                frontier_exam=Mock(return_value={"factory_release_sha256": release_sha}),
                load_frontier_cohort=Mock(return_value=fixed),
            ), patch.object(
                local_screen, "capability_championship_evidence", create=True,
                side_effect=AssertionError(
                    "ordinary C05 must not execute championship evidence")), \
            patch.multiple(
                local_support,
                case_census_digest=Mock(return_value="e" * 64),
                FoundationRetentionPolicy=policy_factory,
            ), patch.multiple(
                local_stages,
                candidate_identity_for_canonical_consumer=Mock(return_value="d" * 64),
                _owner_seed=Mock(return_value=11),
                _fresh_rows=fresh,
                _instruments=Mock(return_value=(instrument,)),
                _cohort=Mock(return_value=SimpleNamespace(
                    rubric_sha256="1" * 64, scope_sha256="2" * 64,
                    policy_sha256="3" * 64, source_sha256="4" * 64,
                    evidence_stage=owner.CURRENT_EVIDENCE_STAGE)),
                factory_complete_solver=Mock(side_effect=(
                    (object(), "b" * 64), (object(), "c" * 64))),
                evaluate_capabilities=Mock(return_value=object()),
                AssessmentPair=Mock(return_value=object()),
                evaluate_target_gate=Mock(return_value=target_gate_decision),
            ), patch.multiple(
                local_screen,
                authenticate_bamf_execution_feature_context=Mock(
                    return_value=object()),
                reference_stage=Mock(return_value=(
                    SimpleNamespace(parent=SimpleNamespace(cohort=object())),
                    None, object())),
                finalize_target_first_local_candidate=Mock(return_value=decision),
            ), patch.multiple(
                owner_screen,
                candidate_identity_for_canonical_consumer=Mock(return_value="d" * 64),
                candidate_identity_binding_for_state=Mock(return_value=None),
                current_learning_first_step_authority_for_parameters=Mock(
                    return_value="d" * 64)):
        return evaluate_factory_retention_candidate(
            source, candidate, "artifact", target, run_dir=Path("unused"))


__all__ = (
    "_evaluate_foundation_owner", "_foundation_owner_fixture",
    "_foundation_retention_plan",
)
