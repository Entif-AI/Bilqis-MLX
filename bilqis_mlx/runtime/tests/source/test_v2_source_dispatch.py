"""Active v2 teaching uses the executable provider, not a legacy Course name."""
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from bilqis_mlx.runtime.assessment import _draw_live_rows


class V2SourceDispatchTests(unittest.TestCase):
    def test_active_v2_source_never_recompiles_legacy_course(self):
        release = SimpleNamespace()
        legacy = SimpleNamespace()
        expected = [{"id": "v2", "capability": "B.AND", "gold": "TRUE"}]
        with (patch("bilqis_mlx.runtime.assessment.draw_course_rows",
                    side_effect=AssertionError("Legacy v1 generation forbidden")),
              patch("bilqis_mlx.runtime.assessment.draw_executable_release_rows",
                    return_value=expected) as executable):
            actual = _draw_live_rows(
                "/source", {"tokens": []}, seed=3, capability="B.AND",
                each=1, course=legacy, executable_release=release)
        self.assertEqual(actual, expected)
        self.assertIs(executable.call_args.args[2], release)
        self.assertEqual(executable.call_args.kwargs["legacy_course"], legacy)


if __name__ == "__main__":
    unittest.main()
