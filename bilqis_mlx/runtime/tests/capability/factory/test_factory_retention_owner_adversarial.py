"""Caller-substitution regressions for the Factory-owned C05 admission seam."""
from pathlib import Path
from types import SimpleNamespace
import unittest

from bilqis_mlx.learning.atlas_retention_decision import (
    decide_candidate_retention, issue_factory_retention_decision,
)
from bilqis_mlx.runtime.factory_retention_owner import (
    FactoryRetentionEvaluation, _cohort, evaluate_factory_retention_candidate,
)
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import _screen_inputs


class FactoryRetentionOwnerAdversarialTests(unittest.TestCase):
    def test_caller_cannot_construct_evaluation_authority(self):
        with self.assertRaises(Exception):
            FactoryRetentionEvaluation(
                decision=object(),
                parent_candidate_sha256="a" * 64,
                candidate_candidate_sha256="b" * 64,
            )

    def test_issuer_rejects_foreign_evidence(self):
        with self.assertRaises(Exception):
            issue_factory_retention_decision(object())

    def test_caller_selected_solver_and_policy_remain_fail_closed(self):
        with self.assertRaises(Exception):
            decide_candidate_retention(
                parent_solver=object(), candidate_solver=object(),
                target_capability="B.IDBOOLOPS", policy=object(),
                cohorts=(), parent_state=object(), candidate_state=object(),
            )

    def test_factory_entry_rejects_caller_cohorts_and_policy(self):
        with self.assertRaises(TypeError):
            evaluate_factory_retention_candidate(
                object(), object(), "artifact", "B.IDBOOLOPS",
                run_dir=Path("unused"), cohorts=(), policy=object(),
            )

    def test_owner_cohorts_share_one_factory_evaluation_scope(self):
        _, _, _, policy, cohorts = _screen_inputs()
        release = SimpleNamespace(execution_plan=SimpleNamespace(
            curriculum_sha256="1" * 64,
            profile_id="factory-c05-test",
            grades=(SimpleNamespace(
                grade_id="A", assessment_blueprint_sha256="2" * 64),),
            projection_digests=SimpleNamespace(source="3" * 64),
        ))
        training = (("trained-family",), ("trained-episode",))
        rebuilt = tuple(_cohort(
            cohort.kind,
            tuple(SimpleNamespace(case=case) for case in cohort.cases),
            cohort.capability_groups,
            release,
            policy,
            training,
        ) for cohort in cohorts)
        self.assertEqual(len({cohort.scope_sha256 for cohort in rebuilt}), 1)


if __name__ == "__main__":
    unittest.main()
