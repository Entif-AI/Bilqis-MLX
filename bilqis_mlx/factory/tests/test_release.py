from dataclasses import replace
import unittest

from bilqis_mlx.curriculum import AnswerFamily, BINARY, Capability, Course, Grade
from bilqis_mlx.factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from bilqis_mlx.factory.model import AssessmentClass, SourceAdapter
from bilqis_mlx.factory.release import compile_factory_release


class FactoryReleaseTests(unittest.TestCase):
    def setUp(self):
        caps = tuple(Capability(
            id=f"A.C{i}", difficulty="fixture", source_anchor="repo:fixture/source",
            taught_roots=(f"fixture.op.{i}",), examined_roots=(f"fixture.op.{i}",),
            prerequisites=(), composed_of=(),
            answer_families=(AnswerFamily("binary", BINARY),),
            lesson_generator="fixture.generator/v1", independent_oracle="fixture.oracle/v1",
        ) for i in range(6))
        grade = Grade("A", caps, assessment_sha256="a" * 64,
                      exam_item_counts=tuple((cap.id, 4) for cap in caps))
        self.course = Course((grade,), "fixture.course/v1", "b" * 64, "c" * 64)
        descriptor = SourceAdapter("fixture.adapter/v1", "fixture.generator/v1",
                                   ("fixture.oracle/v1",), "d" * 64)
        self.registry = SourceAdapterRegistry((RegisteredSourceAdapter(
            descriptor, lambda **_: ()),))

    def test_release_binds_semantics_adapters_and_three_assessment_classes(self):
        release = compile_factory_release(self.course, self.registry)
        release.verify()
        self.assertEqual(tuple(item.capability_id for item in release.capabilities),
                         tuple(cap.id for cap in self.course.grades[0].capabilities))
        self.assertEqual({plan.assessment_class for plan in release.assessments},
                         set(AssessmentClass))
        self.assertEqual(
            tuple(item.capability_id for item in release.construction_programs),
            tuple(cap.id for cap in self.course.grades[0].capabilities))
        self.assertTrue(all(plan.require_fresh_seed for plan in release.coverage_plans))
        self.assertTrue(all(item.source_grounded for item in release.teaching_options))
        generalization = [plan for plan in release.assessments
                          if plan.assessment_class is AssessmentClass.GENERALIZATION][0]
        self.assertTrue(generalization.fresh_on_decision)
        self.assertTrue(generalization.burn_after_failure)
        promotion = [plan for plan in release.assessments
                     if plan.assessment_class is AssessmentClass.PROMOTION][0]
        self.assertTrue(promotion.reusable_after_failure)
        self.assertFalse(promotion.fresh_on_decision)

    def test_missing_source_adapter_blocks_release(self):
        with self.assertRaisesRegex(ValueError, "FACTORY_SOURCE_ADAPTER_MISSING"):
            compile_factory_release(self.course, SourceAdapterRegistry())

    def test_oracle_mismatch_blocks_release(self):
        wrong = SourceAdapter("fixture.adapter/v2", "fixture.generator/v1",
                              ("other.oracle/v1",), "e" * 64)
        registry = SourceAdapterRegistry((RegisteredSourceAdapter(wrong, lambda **_: ()),))
        with self.assertRaisesRegex(ValueError, "FACTORY_SOURCE_ORACLE_NOT_ADAPTER_OWNED"):
            compile_factory_release(self.course, registry)

    def test_release_digest_detects_tampering(self):
        release = compile_factory_release(self.course, self.registry)
        tampered = replace(release, release_sha256="f" * 64)
        with self.assertRaisesRegex(ValueError, "FACTORY_RELEASE_CONTENT_DRIFT"):
            tampered.verify()


if __name__ == "__main__":
    unittest.main()
