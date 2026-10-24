from dataclasses import replace
import unittest

from bilqis_mlx.factory.curriculum_definition import (
    from_legacy_course, validate_curriculum_definition, GradeSpec,
    instructional_constituent_roots,
)
from bilqis_mlx.factory.execution import CurriculumProfile, compile_execution_plan
from bilqis_mlx.factory.tests.test_execution_plan import (
    _synthetic_course, _synthetic_registry,
)


class CurriculumDefinitionTests(unittest.TestCase):
    def test_instructional_roots_follow_grade_and_strict_stage_order(self):
        curriculum, _ = from_legacy_course(_synthetic_course(6))
        template = curriculum.grades[0].capabilities[0]
        def capability(name):
            return replace(template, capability_id=name,
                           taught_roots=("root." + name,),
                           examined_roots=("root." + name,))
        def grade(name, names, stages=()):
            return GradeSpec(name, tuple(capability(n) for n in names),
                             tuple((n, 4) for n in names), stages)
        curriculum = replace(curriculum, grades=(
            grade("Z", ("first.one", "first.two")),
            grade("A", ("later.intro", "later.peer", "later.compose", "later.final"),
                  (("later.intro", "later.peer"), ("later.compose",), ("later.final",))),
            grade("B", ("future.one",)),))
        expected = {
            "first.one": {"root.first.one"},
            "first.two": {"root.first.two"},
            "later.intro": {"root.first.one", "root.first.two", "root.later.intro"},
            "later.peer": {"root.first.one", "root.first.two", "root.later.peer"},
            "later.compose": {"root.first.one", "root.first.two", "root.later.intro",
                              "root.later.peer", "root.later.compose"},
            "later.final": {"root.first.one", "root.first.two", "root.later.intro",
                            "root.later.peer", "root.later.compose", "root.later.final"},
        }
        for name, roots in expected.items():
            with self.subTest(capability=name):
                actual = instructional_constituent_roots(curriculum, name)
                self.assertEqual(set(actual), roots)
                self.assertEqual(len(actual), len(roots))
                self.assertEqual(actual, instructional_constituent_roots(curriculum, name))
        unstaged = replace(curriculum, grades=(curriculum.grades[0],
            replace(curriculum.grades[1], teaching_stages=()), curriculum.grades[2]))
        self.assertEqual(set(instructional_constituent_roots(unstaged, "later.compose")),
                         {"root.first.one", "root.first.two", "root.later.compose"})
        with self.assertRaisesRegex(ValueError, "UNKNOWN_CAPABILITY"):
            instructional_constituent_roots(curriculum, "missing.capability")
        duplicate = replace(curriculum.grades[1].capabilities[2],
                            taught_roots=("root.first.one",), examined_roots=("root.first.one",))
        overlap = replace(curriculum, grades=(curriculum.grades[0], replace(
            curriculum.grades[1], capabilities=(*curriculum.grades[1].capabilities[:2],
                                               duplicate, curriculum.grades[1].capabilities[3]))))
        roots = instructional_constituent_roots(overlap, "later.compose")
        self.assertEqual(len(roots), len(set(roots)))
        self.assertEqual(curriculum.grades[0].grade_id, "Z")

    def test_jit_canonical_slice_can_start_with_one_real_capability(self):
        curriculum, _ = from_legacy_course(_synthetic_course(6))
        first = curriculum.grades[0].capabilities[0]
        thin = replace(curriculum, grades=(GradeSpec(
            "Z", (first,), ((first.capability_id, 4),), ((first.capability_id,),)),))
        validate_curriculum_definition(thin, answer_kinds=("binary",))
        with self.assertRaisesRegex(ValueError, "GRADE_INVALID"):
            validate_curriculum_definition(replace(thin, grades=(GradeSpec("Z", (), ()),)),
                                           answer_kinds=("binary",))

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
