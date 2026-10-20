from dataclasses import replace
import unittest

from bilqis_mlx.boolean_identification import answer_heads as legacy_boolean_heads
from bilqis_mlx.curriculum import AnswerFamily, INT_0_3
from bilqis_mlx.factory.answers import compile_answer_heads
from bilqis_mlx.factory.execution import (
    CapabilityProfile, CurriculumProfile, GradeProfile, compile_execution_plan,
)
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.factory.tests.test_execution_plan import (
    _synthetic_boolean_course,
    _synthetic_course,
    _synthetic_registry,
)


class LiveAnswerRegistryTests(unittest.TestCase):
    def test_full_boolean_head_matches_legacy_binding(self):
        course, providers = _synthetic_boolean_course()
        registry = live_answer_registry()
        plan = compile_execution_plan(
            course, CurriculumProfile.full(), providers,
            answer_registry=registry)
        graph = {
            "tokens": [
                "fixture.padding",
                "cogal.value.false",
                "cogal.value.true",
                "cogal.operator.NOT",
                "cogal.operator.AND",
                "cogal.operator.OR",
                "cogal.operator.XOR",
                "cogal.operator.IMPLIES",
                "cogal.operator.IFF",
            ],
        }
        compiled = compile_answer_heads(plan, graph, registry)
        legacy = legacy_boolean_heads(graph)
        self.assertEqual(compiled["binary"], {
            **legacy["binary"],
            "modality_id": "answer.binary/v1",
            "implementation_sha256":
                registry.require("binary").descriptor.implementation_sha256,
        })
        self.assertEqual(
            compiled["boolean_operator"]["values"],
            legacy["boolean_operator"]["values"])
        self.assertEqual(
            compiled["boolean_operator"]["token_ids"],
            legacy["boolean_operator"]["token_ids"])

    def test_numeric_modalities_bind_existing_number_identities(self):
        course = _synthetic_course(6)
        grade = course.grades[0]
        capability = replace(
            grade.capabilities[0],
            answer_families=(
                AnswerFamily("integer_0_3", INT_0_3),
                AnswerFamily(
                    "numeric_active",
                    tuple(str(index) for index in range(6))),
            ))
        course = replace(
            course,
            grades=(replace(
                grade,
                capabilities=(capability, *grade.capabilities[1:])),))
        providers = _synthetic_registry()
        registry = live_answer_registry()
        plan = compile_execution_plan(
            course, CurriculumProfile.full(), providers,
            answer_registry=registry)
        graph = {
            "tokens": [
                "fixture.padding",
                "cogal.value.false",
                "cogal.value.true",
                *(f"school.number.{index}" for index in range(6)),
            ],
        }
        heads = compile_answer_heads(plan, graph, registry)
        self.assertEqual(
            heads["integer_0_3"]["values"], ["0", "1", "2", "3"])
        self.assertEqual(
            heads["numeric_active"]["values"],
            ["0", "1", "2", "3", "4", "5"])
        for kind in ("integer_0_3", "numeric_active"):
            self.assertEqual(
                [graph["tokens"][index] for index in heads[kind]["token_ids"]],
                ["school.number." + value for value in heads[kind]["values"]])

    def test_same_live_registry_obeys_reduced_boolean_profile(self):
        course, providers = _synthetic_boolean_course()
        registry = live_answer_registry()
        graph = {
            "tokens": [
                "fixture.padding",
                "cogal.value.false",
                "cogal.value.true",
                "cogal.operator.NOT",
                "cogal.operator.AND",
                "cogal.operator.OR",
                "cogal.operator.XOR",
                "cogal.operator.IMPLIES",
                "cogal.operator.IFF",
            ],
        }
        full = compile_answer_heads(
            compile_execution_plan(
                course, CurriculumProfile.full(), providers,
                answer_registry=registry),
            graph, registry)
        reduced = compile_answer_heads(
            compile_execution_plan(
                course,
                CurriculumProfile(
                    "boolean-kernel/and-iff",
                    grades=(GradeProfile(
                        "B",
                        enabled_capabilities=(
                            "B.AND", "B.IFF",
                            "B.COMPOSITE", "B.IDBOOLOPS"),
                        capabilities=(CapabilityProfile(
                            "B.IDBOOLOPS",
                            answer_family_values=(
                                ("boolean_operator", ("AND", "IFF")),)),),
                    ),),
                ),
                providers,
                answer_registry=registry),
            graph, registry)

        self.assertEqual(
            full["boolean_operator"]["values"],
            ["NOT", "AND", "OR", "XOR", "IMPLIES", "IFF"])
        self.assertEqual(
            reduced["boolean_operator"]["values"],
            ["AND", "IFF"])
        self.assertEqual(
            reduced["boolean_operator"]["modality_id"],
            "answer.boolean-operator/v1")

    def test_unknown_modality_remains_fail_closed(self):
        registry = live_answer_registry()
        with self.assertRaisesRegex(
                ValueError, "FACTORY_ANSWER_MODALITY_MISSING:color"):
            registry.require("color")


if __name__ == "__main__":
    unittest.main()
