"""#1032: production C13 source/capability reservation at binding validation."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.curriculum_definition import (
    C13_RESERVED_CAPABILITY_ID,
    C13_RESERVED_GENERATOR_ID,
    C13_RESERVED_ORACLE_ID,
    C13_RESERVED_SOURCE_ANCHOR,
    CapabilitySourceBinding,
    SourceBindingSet,
    from_legacy_course,
)
from bilqis_mlx.factory.execution import CurriculumProfile, compile_execution_plan
from bilqis_mlx.factory.model import SourceAdapter
from bilqis_mlx.factory.tests.execution_plan.fixtures import (
    _fixture_check,
    _fixture_rows,
    _synthetic_course,
    _synthetic_registry,
)
from bilqis_mlx.factory.tests.test_executable_release import _answers


class C13SourceBindingReservationTests(unittest.TestCase):
    @staticmethod
    def _base():
        curriculum, bindings = from_legacy_course(_synthetic_course(6))
        return curriculum, bindings

    @staticmethod
    def _rename_first_capability(curriculum, capability_id):
        grade = curriculum.grades[0]
        renamed = replace(grade.capabilities[0], capability_id=capability_id)
        return replace(
            curriculum,
            grades=(replace(
                grade,
                capabilities=(renamed, *grade.capabilities[1:]),
                exam_item_counts=((capability_id, grade.exam_item_counts[0][1]),
                                  *grade.exam_item_counts[1:]),
            ), *curriculum.grades[1:]),
        )

    @staticmethod
    def _compile(curriculum, bindings, registry=None):
        return compile_execution_plan(
            curriculum,
            CurriculumProfile.full(),
            registry or _synthetic_registry(),
            source_bindings=bindings,
            answer_registry=_answers(),
        )

    def test_lawful_existing_source_bindings_remain_compatible(self):
        curriculum, bindings = self._base()

        plan = self._compile(curriculum, bindings)
        self.assertEqual(plan.source_binding_sha256, bindings.digest())

    def test_exact_reserved_c13_binding_is_lawful(self):
        curriculum, bindings = self._base()
        curriculum = self._rename_first_capability(
            curriculum, C13_RESERVED_CAPABILITY_ID)
        reserved = CapabilitySourceBinding(
            C13_RESERVED_CAPABILITY_ID,
            C13_RESERVED_SOURCE_ANCHOR,
            C13_RESERVED_GENERATOR_ID,
            C13_RESERVED_ORACLE_ID,
        )
        bindings = SourceBindingSet((reserved, *bindings.bindings[1:]))
        reserved_adapter = RegisteredSourceAdapter(
            SourceAdapter(
                "bilqis.c13.episode-binding-adapter/v1",
                C13_RESERVED_GENERATOR_ID,
                (C13_RESERVED_ORACLE_ID,),
                "e" * 64,
            ),
            _fixture_rows,
            _fixture_check,
            semantic_footprint=lambda row: ("z.op.0",),
        )
        fixture_adapter = RegisteredSourceAdapter(
            SourceAdapter(
                "fixture.z-adapter/v1",
                "fixture.z-generator/v1",
                ("fixture.z-oracle/v1",),
                "d" * 64,
            ),
            _fixture_rows,
            _fixture_check,
            semantic_footprint=lambda row: (
                "z.op." + row["capability"].partition(".C")[2],),
        )
        plan = self._compile(
            curriculum,
            bindings,
            SourceAdapterRegistry((reserved_adapter, fixture_adapter)),
        )
        self.assertEqual(plan.capabilities[0].capability_id, C13_RESERVED_CAPABILITY_ID)

    def test_reserved_capability_rejects_foreign_source_tuple(self):
        curriculum, bindings = self._base()
        foreign = replace(bindings.bindings[0], capability_id=C13_RESERVED_CAPABILITY_ID)
        bindings = SourceBindingSet((foreign, *bindings.bindings[1:]))
        curriculum = self._rename_first_capability(
            curriculum, C13_RESERVED_CAPABILITY_ID)

        with self.assertRaisesRegex(
                BilqisError, "FACTORY.SOURCE_BINDING.INVALID"):
            self._compile(curriculum, bindings)

    def test_reserved_source_coordinates_reject_foreign_capability(self):
        curriculum, bindings = self._base()
        for changes in (
            {"source_anchor": C13_RESERVED_SOURCE_ANCHOR},
            {"generator_id": C13_RESERVED_GENERATOR_ID},
            {"oracle_id": C13_RESERVED_ORACLE_ID},
        ):
            candidate = replace(bindings.bindings[0], **changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(
                    BilqisError, "FACTORY.SOURCE_BINDING.INVALID"):
                self._compile(
                    curriculum,
                    SourceBindingSet((candidate, *bindings.bindings[1:])))

    def test_c13_prefix_cannot_be_extended_by_foreign_capability(self):
        curriculum, bindings = self._base()
        prefix_collision = replace(
            bindings.bindings[0], capability_id=C13_RESERVED_CAPABILITY_ID + ".FUTURE")
        bindings = SourceBindingSet((prefix_collision, *bindings.bindings[1:]))
        curriculum = self._rename_first_capability(
            curriculum, prefix_collision.capability_id)

        with self.assertRaisesRegex(
                BilqisError, "FACTORY.SOURCE_BINDING.INVALID"):
            self._compile(curriculum, bindings)


if __name__ == "__main__":
    unittest.main()
