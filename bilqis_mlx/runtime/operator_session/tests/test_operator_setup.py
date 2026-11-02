"""Invalid initial staircase requests fail before initialization."""
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.runtime.operator_session import operator_setup as subject


class SetupTest(TestCase):
    def test_initial_numeric_staircase_rejected_before_initialization(self):
        with patch.object(subject._runtime_session, "_init", side_effect=AssertionError("initialized")):
            with self.assertRaisesRegex(ValueError, "^NUMERIC_STAIRCASE_REQUIRES_RESUME$"):
                subject.prepare_operator_session(resume=False, run_dir="run", manifest=None,
                    historical_course=None, course_a=None, source_root=None, teacher_sha=None,
                    historical_teacher=None, provenance=None, source_checkpoint=None, course=None,
                    numeric_staircase=True, reserve_gib=1, model_topology=None, qualification=None,
                    experiment_budget=None, mx=None, full_grade_b=True, autonomous_curriculum=False,
                    admit_next_grade_with_debt=False,

                     _resume_boolean_profile=None, _numeric_entry_transition=None)
