"""C16.3 persistent BAMF operator routing contracts."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.bamf_operator.session import (
    BamfOperatorResult, _next_target, operate_bamf,
)


def _capability(identity, grade, prerequisites=()):
    return SimpleNamespace(
        capability_id=identity, grade_id=grade,
        prerequisites=tuple(prerequisites))


class _Assessment:
    def __init__(self, scores):
        self.scores = scores

    def score(self, capability):
        return self.scores[capability]


class BamfOperatorRoutingTests(unittest.TestCase):
    def test_next_target_uses_factory_order_and_prerequisites_not_grade_label(self):
        first = _capability("alpha", "violet")
        held = _capability("dependent", "amber", ("missing",))
        ready = _capability("ready", "amber", ("alpha",))
        release = SimpleNamespace(
            execution_plan=SimpleNamespace(capabilities=(first, held, ready)))
        context = SimpleNamespace(release=release)
        assessment = _Assessment({
            "alpha": (4, 4), "dependent": (0, 4), "ready": (1, 4)})
        with patch(
            "bilqis_mlx.runtime.bamf_operator.session.measure_factory_foundation_progress",
            return_value=assessment,
        ):
            selected, measured = _next_target(
                context, object(), "atlas.json", Path("/run"))
        self.assertIs(selected, ready)
        self.assertIs(measured, assessment)

    def test_next_target_reports_complete_only_when_every_capability_is_mastered(self):
        one = _capability("one", "left")
        two = _capability("two", "right", ("one",))
        context = SimpleNamespace(release=SimpleNamespace(
            execution_plan=SimpleNamespace(capabilities=(one, two))))
        assessment = _Assessment({"one": (3, 3), "two": (2, 2)})
        with patch(
            "bilqis_mlx.runtime.bamf_operator.session.measure_factory_foundation_progress",
            return_value=assessment,
        ):
            selected, _measured = _next_target(
                context, object(), "atlas.json", Path("/run"))
        self.assertIsNone(selected)

    def test_rejected_visit_holds_without_hidden_retry(self):
        with TemporaryDirectory() as temporary:
            run = Path(temporary)
            student = SimpleNamespace(
                generation=7,
                retained_state=SimpleNamespace(optimizer_step=19))
            with patch(
                "bilqis_mlx.runtime.bamf_operator.session._visit",
                return_value="REJECTED",
            ) as visit, patch(
                "bilqis_mlx.runtime.bamf_operator.session.load_accepted_generation",
                return_value=student,
            ):
                result = operate_bamf(
                    run, {}, minutes=1, max_visits=9, reserve_gib=0.0)
        self.assertEqual(
            result, BamfOperatorResult("REJECTED_HOLD", 1, 0, 1, 7, 19))
        visit.assert_called_once()


if __name__ == "__main__":
    unittest.main()
