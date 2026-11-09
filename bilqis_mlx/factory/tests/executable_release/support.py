from dataclasses import replace
import json
import unittest

from bilqis_mlx.curriculum import BINARY, BOOLEAN_OPERATORS
from bilqis_mlx.factory.adapters import (
    RegisteredSourceAdapter, SourceAdapterRegistry,
)
from bilqis_mlx.factory.answers import (
    AnswerModality, AnswerModalityRegistry, RegisteredAnswerModality,
    fixed_domain,
)
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import (
    ExecutableFactoryRelease, compile_executable_factory_release,
)
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.execution import (
    CapabilityProfile, GradeProfile, PlanLineage,
)
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.tests.test_execution_plan import (
    _synthetic_boolean_course, _synthetic_course, _synthetic_registry,
)


def _answers():
    return AnswerModalityRegistry((
        RegisteredAnswerModality(
            AnswerModality("binary", "answer.binary/v1", "a" * 64),
            fixed_domain(BINARY),
            lambda value: {
                "FALSE": "cogal.value.false",
                "TRUE": "cogal.value.true",
            }[value]),
    ))


def _boolean_answers():
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
    ))


class ReleaseTestSupport(unittest.TestCase):
    def setUp(self):
        self.course = _synthetic_course(6)
        self.registry = _synthetic_registry()
        self.curriculum, self.bindings = from_legacy_course(self.course)
        self.answers = _answers()
        self.graph = {
            "tokens": [
                "fixture.padding",
                "cogal.value.false",
                "cogal.value.true",
            ],
        }

    def compile(self):
        return compile_executable_factory_release(
            self.curriculum,
            self.bindings,
            CurriculumProfile.full(),
            self.registry,
            self.answers,
            source_root=None,
            graph=self.graph,
            verification_seed=20261019,
        )

    def registry_with_revised_roots(self, roots):
        adapter = self.registry.require("fixture.z-generator/v1", "fixture.z-oracle/v1")
        return SourceAdapterRegistry((replace(
            adapter,
            semantic_footprint=lambda row: (roots[row["capability"]],) if row["capability"] in roots
            else adapter.semantic_footprint(row)),))

    def compile_twelve(self):
        names = tuple(f"Z.C{i}" for i in range(12))
        template = self.curriculum.grades[0].capabilities[0]
        capabilities = tuple(replace(
            template, capability_id=name,
            taught_roots=(f"z.op.{i}",), examined_roots=(f"z.op.{i}",),
        ) for i, name in enumerate(names))
        grade = replace(self.curriculum.grades[0], capabilities=capabilities,
                        exam_item_counts=tuple((name, 4) for name in names))
        curriculum = replace(self.curriculum, grades=(grade,))
        bindings = replace(self.bindings, bindings=tuple(
            replace(self.bindings.bindings[0], capability_id=name) for name in names))
        return compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(), self.registry, self.answers,
            source_root=None, graph=self.graph, verification_seed=17)
