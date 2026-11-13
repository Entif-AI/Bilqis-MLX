"""Debt rehearsal."""
import unittest

from bilqis_mlx.learning.tests.test_learning_experiment import (
    CausalTeacherExperimentTests, schedule_program,
)


class DebtRehearsalTests(CausalTeacherExperimentTests):
    def test_only_recorded_earlier_debt_joins_graduated_rehearsal(self):
        from bilqis_mlx.learning.learning_experiment import earlier_grade_capabilities

        program = schedule_program(
            ("A", ("A.IDENTITY", "A.MAPS")),
            ("B", ("B.XOR",)),
            ("D", ("D.EVENT_OCCURRENCE",)),
        )
        debt = ("A.MAPS", "B.XOR", "D.EVENT_OCCURRENCE", "E.UNKNOWN")
        self.assertEqual(
            earlier_grade_capabilities(
                program, {}, "B.XOR", carried_mastery_debt=debt),
            ("A.MAPS",),
        )
        self.assertEqual(
            earlier_grade_capabilities(
                program, {"A": object()}, "D.EVENT_OCCURRENCE",
                carried_mastery_debt=debt),
            ("A.IDENTITY", "A.MAPS", "B.XOR"),
        )
        self.assertEqual(earlier_grade_capabilities(program, {}, "B.XOR"), ())
