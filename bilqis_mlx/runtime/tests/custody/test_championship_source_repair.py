"""Metadata source repair preserves valid roles and permanent pair history."""
from copy import deepcopy
import unittest

from bilqis_mlx.runtime.championship_source_repair import _invalidate_championship_source_context


class ChampionshipSourceRepairTests(unittest.TestCase):
    def test_source_repair_archives_only_affected_role_and_its_soup(self):
        original = {
            'active_roles': {'A.ONE': {'sha': 'first'}, 'B.TWO': {'sha': 'second'}},
            'active_grade_soups': {'A': {'sha': 'soup-a'}, 'B': {'sha': 'soup-b'}},
            'settled_matchups': {'pair': {'winner': 'first'}},
        }
        before = deepcopy(original)
        repaired = _invalidate_championship_source_context(original, {'A.ONE'})
        self.assertEqual(original, before)
        self.assertEqual(repaired, {
            'active_roles': {'B.TWO': {'sha': 'second'}},
            'active_grade_soups': {'B': {'sha': 'soup-b'}},
            'settled_matchups': {'pair': {'winner': 'first'}},
            'invalidated_active_roles': [{
                'capability': 'A.ONE', 'reason': 'COHORT_SOURCE_RUBRIC_CONTRADICTION',
                'role': {'sha': 'first'},
            }],
            'invalidated_active_soups': [{
                'grade': 'A', 'reason': 'ROLE_SOURCE_CONTRADICTION',
                'active_grade_soup': {'sha': 'soup-a'},
            }],
        })
