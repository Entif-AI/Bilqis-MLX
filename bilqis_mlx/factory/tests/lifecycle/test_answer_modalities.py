from dataclasses import replace
import unittest

from bilqis_mlx.curriculum import AnswerFamily, BINARY, BOOLEAN_OPERATORS
from bilqis_mlx.factory.answers import (
    AnswerModality, AnswerModalityRegistry, RegisteredAnswerModality,
    compile_answer_heads, fixed_domain,
)
from bilqis_mlx.factory.execution import (
    CapabilityProfile, CurriculumProfile, GradeProfile, compile_execution_plan,
)
from bilqis_mlx.factory.tests.test_execution_plan import (
    _synthetic_boolean_course, _synthetic_course, _synthetic_registry,
)


def modalities(*extra):
    return AnswerModalityRegistry((
        RegisteredAnswerModality(
            AnswerModality("binary", "answer.binary/v1", "a" * 64),
            fixed_domain(BINARY),
            lambda value: {
                "FALSE": "cogal.value.false",
                "TRUE": "cogal.value.true",
            }[value]),
        RegisteredAnswerModality(
            AnswerModality(
                "boolean_operator", "answer.boolean-operator/v1", "b" * 64),
            fixed_domain(BOOLEAN_OPERATORS),
            lambda value: "cogal.operator." + value),
        *extra,
    ))


class AnswerModalityTests(unittest.TestCase):
    def test_boolean_kernel_head_is_derived_from_profile_values(self):
        course, source_registry = _synthetic_boolean_course()
        plan = compile_execution_plan(
            course,
            CurriculumProfile(
                "boolean-kernel/and-iff",
                grades=(GradeProfile(
                    "B",
                    enabled_capabilities=(
                        "B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"),
                    capabilities=(
                        CapabilityProfile(
                            "B.COMPOSITE",
                            provider_parameters=(("operators", ("AND", "IFF")),)),
                        CapabilityProfile(
                            "B.IDBOOLOPS",
                            provider_parameters=(("operators", ("AND", "IFF")),),
                            answer_family_values=(
                                ("boolean_operator", ("AND", "IFF")),)),
                    ),
                ),),
            ),
            source_registry,
            answer_registry=modalities(),
        )
        graph = {"tokens": [
            "padding", "cogal.value.false", "cogal.value.true",
            *("cogal.operator." + operator for operator in BOOLEAN_OPERATORS),
        ]}
        heads = compile_answer_heads(plan, graph, modalities())
        self.assertEqual(heads["binary"]["values"], ["FALSE", "TRUE"])
        self.assertEqual(heads["boolean_operator"]["values"], ["AND", "IFF"])
        self.assertEqual(
            [graph["tokens"][index]
             for index in heads["boolean_operator"]["token_ids"]],
            ["cogal.operator.AND", "cogal.operator.IFF"])

    def test_new_answer_modality_requires_registry_extension_not_grade_branch(self):
        course = _synthetic_course(6)
        grade = course.grades[0]
        capability = replace(
            grade.capabilities[-1],
            answer_families=(AnswerFamily("color", ("RED", "BLUE")),))
        grade = replace(grade, capabilities=(*grade.capabilities[:-1], capability))
        course = replace(course, grades=(grade,))
        color = RegisteredAnswerModality(
            AnswerModality("color", "answer.color/v1", "c" * 64),
            fixed_domain(("RED", "BLUE")),
            lambda value: "fixture.color." + value.lower())
        plan = compile_execution_plan(
            course, CurriculumProfile.full(), _synthetic_registry(),
            answer_registry=modalities(color))
        graph = {"tokens": [
            "padding", "cogal.value.false", "cogal.value.true",
            "fixture.color.red", "fixture.color.blue",
        ]}
        heads = compile_answer_heads(plan, graph, modalities(color))
        self.assertEqual(heads["color"]["values"], ["RED", "BLUE"])
        self.assertEqual(heads["color"]["token_ids"], [3, 4])

    def test_unknown_answer_modality_fails_closed(self):
        course = _synthetic_course(6)
        grade = course.grades[0]
        capability = replace(
            grade.capabilities[-1],
            answer_families=(AnswerFamily("color", ("RED", "BLUE")),))
        course = replace(
            course,
            grades=(replace(
                grade, capabilities=(*grade.capabilities[:-1], capability)),))
        with self.assertRaisesRegex(ValueError, "UNKNOWN_CAPABILITY_ANSWER_FAMILY"):
            compile_execution_plan(
                course, CurriculumProfile.full(), _synthetic_registry(),
                answer_registry=modalities())


if __name__ == "__main__":
    unittest.main()
