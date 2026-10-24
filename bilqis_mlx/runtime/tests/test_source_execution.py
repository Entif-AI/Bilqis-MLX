from dataclasses import replace
import unittest

from bilqis_mlx.factory.adapters import SourceAdapterRegistry
from bilqis_mlx.factory.answers import AnswerModalityRegistry
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.tests.test_executable_release import _answers
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_course, _synthetic_registry
from bilqis_mlx.runtime.source_execution import SourceExecutionContext


class SourceExecutionContextTests(unittest.TestCase):
    def setUp(self):
        self.course = _synthetic_course(6)
        curriculum, bindings = from_legacy_course(self.course)
        self.graph = {"tokens": ["fixture.padding", "cogal.value.false", "cogal.value.true"]}
        self.sources = _synthetic_registry()
        self.answers = _answers()
        self.release = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(), self.sources, self.answers,
            source_root=None, graph=self.graph, verification_seed=17)
        self.arguments = dict(release=self.release, graph=self.graph, source_root=None,
                              source_registry=self.sources, answer_registry=self.answers)

    def test_context_holds_the_existing_release_and_runtime_inputs(self):
        context = SourceExecutionContext(**self.arguments)
        self.assertIs(context.release, self.release)
        self.assertIs(context.graph, self.graph)
        self.assertIs(context.source_registry, self.sources)
        self.assertIs(context.answer_registry, self.answers)
        self.assertIsNone(context.source_root)

    def test_context_rejects_legacy_course_and_untyped_registries(self):
        for field, value in (("release", self.course), ("source_registry", object()),
                             ("answer_registry", object())):
            with self.subTest(field=field), self.assertRaises(TypeError):
                SourceExecutionContext(**{**self.arguments, field: value})

    def test_context_rejects_unverified_release_or_mismatched_graph(self):
        mutations = (
            {"release": replace(self.release, release_sha256="f" * 64)},
            {"graph": {"tokens": list(reversed(self.graph["tokens"]))}},
            {"source_registry": SourceAdapterRegistry()},
            {"answer_registry": AnswerModalityRegistry()},
        )
        for mutation in mutations:
            with self.subTest(field=tuple(mutation)), self.assertRaises(ValueError):
                SourceExecutionContext(**{**self.arguments, **mutation})


if __name__ == "__main__":
    unittest.main()
