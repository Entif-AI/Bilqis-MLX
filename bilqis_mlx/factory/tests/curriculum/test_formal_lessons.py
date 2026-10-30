"""Core adversarial tests for task-scoped formal lessons."""
from dataclasses import replace
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.formal_lessons import check_formal_lesson, construct_formal_lesson
from bilqis_mlx.semantics.cognitive_operators import TypedValue, numeric_domain_digest, source_operand_digest
from bilqis_mlx.semantics.core import literal

from bilqis_mlx.factory.tests.formal_lesson_fixtures import (
    FORMAL, RELEASE, _case, _selection, _source,
)


class FormalLessonCoreTests(unittest.TestCase):
    def test_checker_rejects_mutated_admission_and_authority_metadata(self):
        binding, inputs = _case("SUCC", ("Number", 2))
        with patch(
                "bilqis_mlx.factory.formal_lessons.resolve_formal_source_operators",
                return_value=_source()):
            for field, forged in (
                    ("status", "ADAPTER_READY"),
                    ("learning_state", "LEARNING_VERIFIED"),
                    ("source_authority", "A13_TRANSFERABLE_AUTHORITY"),
                    ("schema", "forged/formal-lesson/v9")):
                with self.subTest(field=field):
                    lesson = construct_formal_lesson(
                        _selection(), FORMAL[3][0], inputs, binding)
                    object.__setattr__(lesson, field, forged)
                    with self.assertRaises(BilqisError) as caught:
                        check_formal_lesson(
                            lesson, lesson.positive, _selection(), binding)
                    self.assertEqual(
                        caught.exception.context["reason"],
                        "BAMF_FORMAL_LESSON_INVALID")

    def test_mutated_entity_set_cannot_be_reauthorized_by_new_grant(self):
        for malformed in (("alpha", "alpha"), ("beta", "alpha")):
            with self.subTest(malformed=malformed):
                binding, inputs = _case(
                    "COUNT", ("EntitySet", ("alpha", "beta")))
                object.__setattr__(inputs[0], "value", malformed)
                operand = binding.operands[0]
                grants = tuple(
                    replace(grant, evidence_digest=source_operand_digest(operand))
                    if grant.source_handle == inputs[0].source_handle else grant
                    for grant in binding.frontier.grants)
                binding = replace(
                    binding, frontier=replace(binding.frontier, grants=grants))
                with patch(
                        "bilqis_mlx.factory.formal_lessons."
                        "resolve_formal_source_operators",
                        return_value=_source()):
                    with self.assertRaises(BilqisError) as caught:
                        construct_formal_lesson(
                            _selection(), FORMAL[2][0], inputs, binding)
                self.assertEqual(
                    caught.exception.context["reason"],
                    "BAMF_FORMAL_LESSON_INPUT_INVALID")

    def test_mutated_typed_schema_cannot_be_reauthorized(self):
        binding, inputs = _case("SUCC", ("Number", 2))
        object.__setattr__(inputs[0], "schema_version", "forged/v9")
        grants = tuple(
            replace(grant, evidence_digest=source_operand_digest(
                binding.operands[0]))
            if grant.source_handle == inputs[0].source_handle else grant
            for grant in binding.frontier.grants)
        binding = replace(
            binding, frontier=replace(binding.frontier, grants=grants))
        with patch(
                "bilqis_mlx.factory.formal_lessons.resolve_formal_source_operators",
                return_value=_source()):
            with self.assertRaises(BilqisError) as caught:
                construct_formal_lesson(
                    _selection(), FORMAL[3][0], inputs, binding)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_FORMAL_LESSON_INPUT_INVALID")

    def test_numeric_result_must_stay_inside_source_domain(self):
        binding, inputs = _case("SUCC", ("Number", 2))
        single = replace(
            binding.numeric_domain, values=(literal("2", "Number"),))
        grants = tuple(
            replace(grant, evidence_digest=numeric_domain_digest(
                single, RELEASE))
            if grant.source_handle == binding.numeric_source_handle else grant
            for grant in binding.frontier.grants)
        restricted = replace(
            binding, numeric_domain=single,
            frontier=replace(binding.frontier, grants=grants))
        with patch(
                "bilqis_mlx.factory.formal_lessons.resolve_formal_source_operators",
                return_value=_source()):
            with self.assertRaises(BilqisError) as caught:
                construct_formal_lesson(
                    _selection(), FORMAL[3][0], inputs, restricted)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_FORMAL_LESSON_SOURCE_INAPPLICABLE")


if __name__ == '__main__':
    unittest.main()
