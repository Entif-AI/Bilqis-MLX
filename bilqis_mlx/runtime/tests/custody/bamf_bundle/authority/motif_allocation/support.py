"""C05 fixture support for B07 motif publication witnesses."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
import bilqis_mlx.runtime.factory_retention_owner as retention_owner
from bilqis_mlx.runtime.factory_retention_owner import evaluate_factory_retention_candidate
from bilqis_mlx.runtime.capability_retention import Decision, DecisionStatus

TARGET = "B07.MOTIF"


def accepted_c05_decision(run_dir, transaction, parent, successor, retained):
    release_sha = "1" * 64
    capability = SimpleNamespace(capability_id=TARGET, grade_id="B")
    release = SimpleNamespace(
        release_sha256=release_sha,
        execution_plan=SimpleNamespace(
            capabilities=(capability,), capability_map={TARGET: capability}))
    source_context = SimpleNamespace(
        __post_init__=lambda: None, release=release,
        require_accepted_runtime=Mock())
    fixed = SimpleNamespace(rows=({"id": "fixed"},), seed=7)
    eligible = Decision(
        DecisionStatus.ELIGIBLE, "PAIRED_SCREEN_WITHIN_BUDGET",
        "a" * 64, "b" * 64, "c" * 64, "d" * 64)
    original = transaction.training_authorities
    object.__setattr__(transaction, "training_authorities", (
        SimpleNamespace(delivery_capability=TARGET, release_sha256=release_sha),))
    try:
        with patch.multiple(
                retention_owner, create=True,
                _training_exclusions=Mock(return_value=((), ())),
                _candidate_from_live_parent=Mock(
                    return_value=(parent, successor, retained, object())),
                read_current=Mock(return_value={"factory_release_sha256": release_sha}),
                frontier_exam=Mock(return_value={"factory_release_sha256": release_sha}),
                load_frontier_cohort=Mock(return_value=fixed),
                _instruments=Mock(return_value=(SimpleNamespace(case=SimpleNamespace()),)),
                case_census_digest=Mock(return_value="e" * 64),
                _cohort=Mock(return_value=object()),
                FoundationRetentionPolicy=Mock(return_value=object()),
                factory_complete_solver=Mock(side_effect=((object(), "b" * 64),
                                                          (object(), "c" * 64))),
                evaluate_foundation_fixed_school_candidate=Mock(return_value=eligible)):
            evaluation = evaluate_factory_retention_candidate(
                source_context, transaction, "artifact", TARGET, run_dir=run_dir)
    finally:
        object.__setattr__(transaction, "training_authorities", original)
    return issue_factory_retention_decision(evaluation)
