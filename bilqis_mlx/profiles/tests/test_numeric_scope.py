"""Numeric scope filtering must honor the source codec's list input contract."""
import unittest

from bilqis_mlx.profiles.catalog import numeric_row_in_scope
from bilqis_mlx.semantics.numeric import number
from bilqis_mlx.source_adapters.numeric import encode


class NumericScopeTests(unittest.TestCase):
    def test_in_scope_number_decodes_from_the_source_list(self):
        row = {"record": {"symbols": encode(number(3))}}
        self.assertTrue(numeric_row_in_scope(row, 3))
        self.assertFalse(numeric_row_in_scope(row, 2))


class NumericEntryProfileTests(unittest.TestCase):
    def test_numeric_entry_preserves_introduced_boolean_slice_without_mastery_gate(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from bilqis_mlx.factory.executable_release import ExecutableFactoryRelease
        from bilqis_mlx.factory.execution import CurriculumProfile, GradeProfile
        from bilqis_mlx.profiles.catalog import numeric_entry_transition

        profile = CurriculumProfile('test/not-and', (
            GradeProfile('B', enabled_capabilities=('B.NOT', 'B.AND')),
            GradeProfile('C', enabled_capabilities=()),))
        release = Mock(spec=ExecutableFactoryRelease)
        release.profile = profile
        release.execution_plan = SimpleNamespace(grades=('A', 'B'))
        numeric_ids = ('C.COUNT', 'C.NUMBER', 'C.SUCCESSOR', 'C.ADD', 'C.SUB', 'C.MUL', 'C.DIV')
        release.curriculum = SimpleNamespace(grades=(None, None, SimpleNamespace(grade_id='C',
            capabilities=tuple(SimpleNamespace(capability_id=cap) for cap in numeric_ids))))
        with patch('bilqis_mlx.profiles.catalog.expanded_graph', return_value={'fixture': True}):
            transition = numeric_entry_transition(release, {}, full_boolean=False, maximum=3)
        grades = {grade.grade_id: grade for grade in transition.profile.grades}
        self.assertEqual(grades['B'], profile.grades[0])
        self.assertEqual(grades['C'].enabled_capabilities, numeric_ids[:5])
        self.assertEqual(dict(grades['C'].capabilities[0].provider_parameters)['numbers'],
                         ('0', '1', '2', '3'))


if __name__ == "__main__":
    unittest.main()
