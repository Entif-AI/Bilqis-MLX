"""#1032: production C13 source/capability reservation at binding validation."""
from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.curriculum_definition import (
    C13_RESERVED_CAPABILITY_ID,
    C13_RESERVED_GENERATOR_ID,
    C13_RESERVED_ORACLE_ID,
    C13_RESERVED_SOURCE_ANCHOR,
    CapabilitySourceBinding,
    SourceBindingSet,
    from_legacy_course,
    validate_source_bindings,
)
from bilqis_mlx.factory.tests.execution_plan.fixtures import _synthetic_course


class C13SourceBindingReservationTests(unittest.TestCase):
    @staticmethod
    def _base():
        curriculum, bindings = from_legacy_course(_synthetic_course(6))
        return curriculum, bindings

    def test_lawful_existing_source_bindings_remain_compatible(self):
        curriculum, bindings = self._base()

        validate_source_bindings(curriculum, bindings)

    def test_exact_reserved_c13_binding_is_lawful(self):
        curriculum, bindings = self._base()
        first = bindings.bindings[0]
        capability = replace(
            curriculum.grades[0].capabilities[0],
            capability_id=C13_RESERVED_CAPABILITY_ID,
        )
        curriculum = replace(
            curriculum,
            grades=(replace(
                curriculum.grades[0],
                capabilities=(capability, *curriculum.grades[0].capabilities[1:]),
                exam_item_counts=((C13_RESERVED_CAPABILITY_ID,
                                   curriculum.grades[0].exam_item_counts[0][1]),
                                  *curriculum.grades[0].exam_item_counts[1:]),
                teaching_stages=((C13_RESERVED_CAPABILITY_ID,),
                                 *curriculum.grades[0].teaching_stages[1:]),
            ), *curriculum.grades[1:]),
        )
        reserved = CapabilitySourceBinding(
            C13_RESERVED_CAPABILITY_ID,
            C13_RESERVED_SOURCE_ANCHOR,
            C13_RESERVED_GENERATOR_ID,
            C13_RESERVED_ORACLE_ID,
        )
        bindings = SourceBindingSet((reserved, *bindings.bindings[1:]))

        validate_source_bindings(curriculum, bindings)
        self.assertNotEqual(first.capability_id, C13_RESERVED_CAPABILITY_ID)

    def test_reserved_capability_rejects_foreign_source_tuple(self):
        curriculum, bindings = self._base()
        foreign = replace(bindings.bindings[0], capability_id=C13_RESERVED_CAPABILITY_ID)
        bindings = SourceBindingSet((foreign, *bindings.bindings[1:]))
        curriculum = replace(
            curriculum,
            grades=(replace(
                curriculum.grades[0],
                capabilities=(replace(curriculum.grades[0].capabilities[0],
                                      capability_id=C13_RESERVED_CAPABILITY_ID),
                              *curriculum.grades[0].capabilities[1:]),
            ), *curriculum.grades[1:]),
        )

        with self.assertRaisesRegex(
                BilqisError, "FACTORY.SOURCE_BINDING.INVALID"):
            validate_source_bindings(curriculum, bindings)

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
                validate_source_bindings(
                    curriculum,
                    SourceBindingSet((candidate, *bindings.bindings[1:])),
                )

    def test_c13_prefix_cannot_be_extended_by_foreign_capability(self):
        curriculum, bindings = self._base()
        prefix_collision = replace(
            bindings.bindings[0], capability_id=C13_RESERVED_CAPABILITY_ID + ".FUTURE")
        bindings = SourceBindingSet((prefix_collision, *bindings.bindings[1:]))
        curriculum = replace(
            curriculum,
            grades=(replace(
                curriculum.grades[0],
                capabilities=(replace(curriculum.grades[0].capabilities[0],
                                      capability_id=prefix_collision.capability_id),
                              *curriculum.grades[0].capabilities[1:]),
            ), *curriculum.grades[1:]),
        )

        with self.assertRaisesRegex(
                BilqisError, "FACTORY.SOURCE_BINDING.INVALID"):
            validate_source_bindings(curriculum, bindings)


if __name__ == "__main__":
    unittest.main()
