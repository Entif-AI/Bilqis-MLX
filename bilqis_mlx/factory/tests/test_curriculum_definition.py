from dataclasses import replace
import unittest

from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.execution import CurriculumProfile, compile_execution_plan
from bilqis_mlx.factory.tests.test_execution_plan import (
    _synthetic_course, _synthetic_registry,
)


class CurriculumDefinitionTests(unittest.TestCase):
    def test_source_implementation_change_does_not_change_semantic_curriculum_digest(self):
        course = _synthetic_course(6)
        curriculum, bindings = from_legacy_course(course)
        grade = course.grades[0]
        changed_capability = replace(
            grade.capabilities[-1],
            lesson_generator="fixture.z-generator-v2/v1",
            independent_oracle="fixture.z-oracle-v2/v1",
            source_anchor="repo:fixture/z/v2")
        changed_course = replace(
            course,
            grades=(replace(
                grade,
                capabilities=(*grade.capabilities[:-1], changed_capability)),),
        )
        changed_curriculum, changed_bindings = from_legacy_course(changed_course)
        self.assertEqual(curriculum.digest(), changed_curriculum.digest())
        self.assertNotEqual(bindings.digest(), changed_bindings.digest())

    def test_release_version_and_assessment_seal_do_not_change_semantic_curriculum(self):
        course = _synthetic_course(6)
        curriculum, bindings = from_legacy_course(course)
        grade = course.grades[0]
        changed = replace(
            course,
            version="fixture.z/repackaged-v2",
            source_attestation_sha256="c" * 64,
            assessment_manifest_sha256="e" * 64,
            grades=(replace(grade, assessment_sha256="f" * 64),),
        )
        changed_curriculum, changed_bindings = from_legacy_course(changed)
        self.assertEqual(curriculum.digest(), changed_curriculum.digest())
        self.assertNotEqual(bindings.digest(), changed_bindings.digest())

    def test_semantic_prerequisite_change_changes_curriculum_not_source_bindings(self):
        course = _synthetic_course(6)
        curriculum, bindings = from_legacy_course(course)
        grade = course.grades[0]
        # Same-grade prerequisite is intentionally invalid for the one-stage
        # fixture, so mutate a root instead to prove semantic identity changes
        # independently of provider/source identity.
        changed_capability = replace(
            grade.capabilities[-1],
            taught_roots=("z.op.changed",),
            examined_roots=("z.op.changed",))
        changed_course = replace(
            course,
            grades=(replace(
                grade,
                capabilities=(*grade.capabilities[:-1], changed_capability)),),
        )
        changed_curriculum, changed_bindings = from_legacy_course(changed_course)
        self.assertNotEqual(curriculum.digest(), changed_curriculum.digest())
        self.assertEqual(bindings.digest(), changed_bindings.digest())

    def test_new_semantic_definition_path_requires_explicit_source_and_answer_authority(self):
        course = _synthetic_course(6)
        curriculum, bindings = from_legacy_course(course)
        with self.assertRaisesRegex(ValueError, "SOURCE_BINDINGS_REQUIRED"):
            compile_execution_plan(
                curriculum, CurriculumProfile.full(), _synthetic_registry())
        with self.assertRaisesRegex(ValueError, "ANSWER_REGISTRY_REQUIRED"):
            compile_execution_plan(
                curriculum, CurriculumProfile.full(), _synthetic_registry(),
                source_bindings=bindings)


if __name__ == "__main__":
    unittest.main()
