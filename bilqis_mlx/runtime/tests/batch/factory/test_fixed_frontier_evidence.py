"""Fixed frontier evidence."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, patch, rows,
)


class FixedFrontierEvidenceTests(CausalTeacherExperimentTests):
    def test_fragile_replay_uses_configured_policy_capabilities(self):
        from pathlib import Path
        from bilqis_mlx.runtime.candidate_evidence import _fragile_replay_evidence

        rows = (
            {"id": "configured-1", "capability": "C.ADD", "gold": "2"},
            {"id": "configured-2", "capability": "C.ADD", "gold": "3"},
        )
        expected = {
            "status": "MEASURED", "cohort_sha256": "a" * 64,
            "rows": 2, "regressions": [], "repaired": 1,
        }
        from bilqis_mlx.profiles.retention import FragilePreservationPolicy
        policy = FragilePreservationPolicy(("C.ADD",), 4, "fixture-source/v1")
        predictions = {
            "configured-1": "2", "configured-2": "3",
        }
        with (
            patch("bilqis_mlx.runtime.candidate_evidence._profiles_retention"
                  ".fragile_preservation_policy", return_value=policy),
            patch("bilqis_mlx.runtime.candidate_evidence._profiles_retention"
                  ".fragile_preservation_capabilities",
                  side_effect=AssertionError("compatibility accessor forbidden")),
            patch("bilqis_mlx.learning.fragile_replay.load_replay_rows",
                  return_value=rows) as load_rows,
            patch("bilqis_mlx.learning.fragile_replay.screen_replay",
                  return_value=expected) as screen,
            patch("bilqis_mlx.fixed_frontier.frontier_exam",
                  return_value={"cohort_sha256": "a" * 64}),
        ):
            result = _fragile_replay_evidence(
                None, Path("/not-used"), {}, "parent", "candidate", {}, [],
                predictions, predictions)

        load_rows.assert_called_once_with(
            Path("/not-used"), {}, capabilities=("C.ADD",))
        screen.assert_called_once_with(rows, predictions, predictions, "a" * 64)
        self.assertEqual(result, expected)
