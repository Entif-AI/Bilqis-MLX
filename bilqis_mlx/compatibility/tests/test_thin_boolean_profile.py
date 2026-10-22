"""Compatibility views must preserve a factory-selected Boolean learning slice."""
from dataclasses import replace
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.compatibility.executable_projection import (
    legacy_course_for_profile, profile_has_legacy_inventory,
)
from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_boolean_course


class ThinBooleanProfileTests(unittest.TestCase):
    def setUp(self):
        self.canonical, _ = _synthetic_boolean_course()
        self.grade_a = replace(self.canonical, grades=self.canonical.grades[:1])
        self.profile = CurriculumProfile('test/not-and', (
            GradeProfile('B', enabled_capabilities=('B.NOT', 'B.AND')),))

    def test_thin_view_preserves_constituents_and_filters_assessment_and_stages(self):
        with patch('bilqis_mlx.compatibility.executable_projection._canonical_boolean_course',
                   return_value=self.canonical):
            view = legacy_course_for_profile(self.grade_a, None, self.profile)
        self.assertEqual(view.grades[0], self.grade_a.grades[0])
        self.assertEqual(view.grades[1].capabilities, self.canonical.grades[1].capabilities[:2])
        self.assertEqual(view.grades[1].exam_item_counts, (('B.NOT', 12), ('B.AND', 12)))
        self.assertEqual(view.grades[1].teaching_stages, (('B.NOT', 'B.AND'),))
        self.assertTrue(view.executable)

    def test_unknown_capability_is_not_silently_dropped(self):
        profile = CurriculumProfile('test/unknown', (
            GradeProfile('B', enabled_capabilities=('B.UNKNOWN',)),))
        with patch('bilqis_mlx.compatibility.executable_projection._canonical_boolean_course',
                   return_value=self.canonical):
            with self.assertRaises(ValueError):
                legacy_course_for_profile(self.grade_a, None, profile)

    def test_legacy_resume_does_not_replace_a_custom_slice_with_and_iff(self):
        release = SimpleNamespace(execution_plan=SimpleNamespace(
            capability_map={key: None for key in (*self.grade_a.capability_map, 'B.NOT', 'B.AND')}))
        self.assertFalse(profile_has_legacy_inventory(release, self.canonical))
