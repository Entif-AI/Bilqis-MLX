"""C16.1a fresh-start policy remains grade-neutral and rejects legacy B cadence."""
from dataclasses import asdict
import unittest

from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.curriculum.tests.test_school import cp
from bilqis_mlx.curriculum.tests.test_staged_school import staged_course
from bilqis_mlx.trainer import _state_from_json


class BamfFirstStartNeutralityTests(unittest.TestCase):
    def test_fresh_state_rejects_conflicting_legacy_b_only_cadence_fields(self):
        course = staged_course()
        state = start_new(course, cp("bamf-first-start"))
        payload = asdict(state)

        self.assertGreaterEqual(len({grade.id for grade in course.grades}), 2)
        self.assertIsNone(state.debt_cadence_policy)
        self.assertNotIn("nongating_b_visits", payload)
        self.assertNotIn("non_b_training_turns_since_b_run", payload)

        payload["nongating_b_visits"] = payload["bounded_debt_visits"] + 1
        payload["non_b_training_turns_since_b_run"] = (
            payload["priority_visits_since_bounded_debt"] + 1)

        with self.assertRaisesRegex(ValueError, "SCHOOL_DEBT_COUNTER_MIGRATION_CONFLICT"):
            _state_from_json(payload, course)


if __name__ == "__main__":
    unittest.main()
