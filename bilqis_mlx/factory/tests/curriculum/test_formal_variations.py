"""A08.1b.2 exercised formal variation axes and literal source-valid cases."""
from __future__ import annotations

from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.curriculum.formal_lesson_types import formal_variation_axes
from bilqis_mlx.factory.formal_lessons import (
    check_formal_lesson, construct_formal_lesson,
)
from bilqis_mlx.factory.tests.formal_lesson_fixtures import (
    FORMAL, _case, _selection, _source,
)


_CASES = (
    ("BOOL_NOT", (("Boolean", True),), False),
    ("BOOL_NOT", (("Boolean", False),), True),
    ("BOOL_AND", (("Boolean", True), ("Boolean", True)), True),
    ("BOOL_AND", (("Boolean", True), ("Boolean", False)), False),
    ("BOOL_AND", (("Boolean", False), ("Boolean", True)), False),
    ("BOOL_AND", (("Boolean", False), ("Boolean", False)), False),
    ("COUNT", (("EntitySet", ()),), 0),
    ("COUNT", (("EntitySet", ("alpha",)),), 1),
    ("COUNT", (("EntitySet", ("alpha", "beta")),), 2),
    ("SUCC", (("Number", 0),), 1),
    ("SUCC", (("Number", 1),), 2),
    ("SUCC", (("Number", 4),), 5),
    ("SUCC", (("Number", 9),), 10),
)
_SEMANTIC = {operator_id: semantic_id for semantic_id, _, operator_id in FORMAL}


class FormalVariationTests(TestCase):
    def test_thirteen_cases_exercise_each_declared_axis(self):
        seen = {operator_id: set() for operator_id in _SEMANTIC}
        with patch(
                "bilqis_mlx.factory.formal_lessons.resolve_formal_source_operators",
                return_value=_source()):
            for operator_id, operands, expected in _CASES:
                with self.subTest(operator_id=operator_id, operands=operands):
                    binding, typed_inputs = _case(operator_id, *operands)
                    lesson = construct_formal_lesson(
                        _selection(), _SEMANTIC[operator_id],
                        typed_inputs, binding)
                    self.assertEqual(lesson.positive.value, expected)
                    self.assertEqual(
                        lesson.variation_axes, formal_variation_axes(operator_id))
                    self.assertTrue(check_formal_lesson(
                        lesson, lesson.positive, _selection(), binding))
                    seen[operator_id].add(
                        tuple(item.value for item in typed_inputs))

        self.assertEqual(len(seen["BOOL_NOT"]), 2)
        self.assertEqual(len(seen["BOOL_AND"]), 4)
        self.assertEqual(len(seen["COUNT"]), 3)
        self.assertEqual(len(seen["SUCC"]), 4)

    def test_variation_metadata_is_checked_not_advisory(self):
        binding, inputs = _case("BOOL_NOT", ("Boolean", True))
        with patch(
                "bilqis_mlx.factory.formal_lessons.resolve_formal_source_operators",
                return_value=_source()):
            lesson = construct_formal_lesson(
                _selection(), _SEMANTIC["BOOL_NOT"], inputs, binding)
            object.__setattr__(
                lesson, "variation_axes", ("typed-answer-contrast",))
            with self.assertRaises(BilqisError):
                check_formal_lesson(
                    lesson, lesson.positive, _selection(), binding)
