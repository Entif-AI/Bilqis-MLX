from dataclasses import replace
import unittest

from bilqis_mlx.curriculum import BOOLEAN_OPERATORS
from bilqis_mlx.factory.adapters import (
    RegisteredSourceAdapter, SourceAdapterRegistry,
)
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import (
    answer_heads_from_executable_release,
    compile_executable_factory_release,
)
from bilqis_mlx.factory.execution import (
    CapabilityProfile, CurriculumProfile, GradeProfile,
)
from bilqis_mlx.factory.generation import draw_executable_release_rows
from bilqis_mlx.factory.tests.test_executable_release import _boolean_answers
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_boolean_course


def _profile():
    return CurriculumProfile(
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
    )


class ExecutableConsumerTests(unittest.TestCase):
    def setUp(self):
        self.course, self.registry = _synthetic_boolean_course()
        self.curriculum, self.bindings = from_legacy_course(self.course)
        self.answers = _boolean_answers()
        self.graph = {
            "tokens": [
                "fixture.padding",
                "cogal.value.false",
                "cogal.value.true",
                *(f"cogal.operator.{value}" for value in BOOLEAN_OPERATORS),
            ],
        }
        self.full = compile_executable_factory_release(
            self.curriculum, self.bindings, CurriculumProfile.full(),
            self.registry, self.answers, source_root=None, graph=self.graph,
            verification_seed=31, legacy_course=self.course)
        self.reduced = compile_executable_factory_release(
            self.curriculum, self.bindings, _profile(),
            self.registry, self.answers, source_root=None, graph=self.graph,
            verification_seed=31, legacy_course=self.course,
            predecessor=self.full)

    def test_same_generation_consumer_obeys_release_profile(self):
        full = draw_executable_release_rows(
            None, self.graph, self.full, self.registry,
            seed=37, legacy_course=self.course,
            capability="B.IDBOOLOPS")
        reduced = draw_executable_release_rows(
            None, self.graph, self.reduced, self.registry,
            seed=37, legacy_course=self.course,
            capability="B.IDBOOLOPS")

        self.assertEqual(
            {row["gold"] for row in full},
            set(BOOLEAN_OPERATORS))
        self.assertEqual(
            {row["gold"] for row in reduced},
            {"AND", "IFF"})

    def test_same_answer_consumer_obeys_release_profile(self):
        full = answer_heads_from_executable_release(
            self.full, self.graph)
        reduced = answer_heads_from_executable_release(
            self.reduced, self.graph)

        self.assertEqual(
            full["boolean_operator"]["values"],
            list(BOOLEAN_OPERATORS))
        self.assertEqual(
            reduced["boolean_operator"]["values"],
            ["AND", "IFF"])
        self.assertEqual(
            reduced["semantic_token"]["values"],
            self.graph["tokens"])

    def _registry_with_reimplemented_provider(self, draw=None):
        registered = self.registry.require(
            self.bindings.by_capability["B.IDBOOLOPS"].generator_id,
            self.bindings.by_capability["B.IDBOOLOPS"].oracle_id)
        changed = replace(
            registered.descriptor,
            implementation_sha256="f" * 64)
        return SourceAdapterRegistry((
            *(item for item in self.registry._by_generator.values()
              if item.descriptor.adapter_id != changed.adapter_id),
            RegisteredSourceAdapter(
                changed, draw or registered.draw, registered.check),
        ))

    def test_generation_accepts_reimplementation_when_sealed_specimens_match(self):
        expected = draw_executable_release_rows(
            None, self.graph, self.reduced, self.registry,
            seed=41, legacy_course=self.course,
            capability="B.IDBOOLOPS")
        registry = self._registry_with_reimplemented_provider()

        actual = draw_executable_release_rows(
            None, self.graph, self.reduced, registry,
            seed=41, legacy_course=self.course,
            capability="B.IDBOOLOPS")

        self.assertEqual(actual, expected)

    def test_generation_refuses_provider_behavior_drift(self):
        registered = self.registry.require(
            self.bindings.by_capability["B.IDBOOLOPS"].generator_id,
            self.bindings.by_capability["B.IDBOOLOPS"].oracle_id)

        def drifted_draw(**kwargs):
            rows = list(registered.draw(**kwargs))
            rows[0] = {**rows[0], "id": "drifted-" + rows[0]["id"]}
            return tuple(rows)

        registry = self._registry_with_reimplemented_provider(drifted_draw)
        with self.assertRaisesRegex(
                ValueError, "FACTORY_EXECUTABLE_GENERATION_ADAPTER_DRIFT"):
            draw_executable_release_rows(
                None, self.graph, self.reduced, registry,
                seed=41, legacy_course=self.course,
                capability="B.IDBOOLOPS")


if __name__ == "__main__":
    unittest.main()
