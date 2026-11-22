"""BAMF C16.3 candidate-horizon projection from authenticated rejections."""
from unittest.mock import patch

from bilqis_mlx.runtime.priority_rejection_replay import candidate_step_horizon


def test_candidate_horizon_reuses_interference_shortening_policy():
    with patch(
            "bilqis_mlx.runtime.priority_rejection_replay.rejection_pressure",
            return_value=({
                "PROTECTED_CAPABILITY_REGRESSION": 1,
                "ACTIVE_SCHOOL_GRADE_REGRESSION": 1,
            }, 2)):
        assert candidate_step_horizon("/run", object(), object(), "cap", 16) == 8

    with patch(
            "bilqis_mlx.runtime.priority_rejection_replay.rejection_pressure",
            return_value=({
                "PROTECTED_CAPABILITY_REGRESSION": 2,
                "ACTIVE_SCHOOL_GRADE_REGRESSION": 1,
                "SAME_GRADE_NET_REGRESSION": 1,
            }, 4)):
        assert candidate_step_horizon("/run", object(), object(), "cap", 16) == 4


def test_no_gain_resets_interference_horizon_pressure():
    with patch(
            "bilqis_mlx.runtime.priority_rejection_replay.rejection_pressure",
            return_value=({
                "PROTECTED_CAPABILITY_REGRESSION": 1,
                "ACTIVE_SCHOOL_GRADE_REGRESSION": 1,
                "NO_MEASURABLE_TARGET_GAIN": 1,
            }, 0)):
        assert candidate_step_horizon("/run", object(), object(), "cap", 16) == 16



def test_twenty_four_step_horizon_uses_existing_generic_shortening_policy():
    with patch(
            "bilqis_mlx.runtime.priority_rejection_replay.rejection_pressure",
            return_value=({}, 0)):
        assert candidate_step_horizon("/run", object(), object(), "cap", 24) == 24

    with patch(
            "bilqis_mlx.runtime.priority_rejection_replay.rejection_pressure",
            return_value=({
                "PROTECTED_CAPABILITY_REGRESSION": 2,
            }, 2)):
        assert candidate_step_horizon("/run", object(), object(), "cap", 24) == 12

    with patch(
            "bilqis_mlx.runtime.priority_rejection_replay.rejection_pressure",
            return_value=({
                "PROTECTED_CAPABILITY_REGRESSION": 4,
            }, 4)):
        assert candidate_step_horizon("/run", object(), object(), "cap", 24) == 6
