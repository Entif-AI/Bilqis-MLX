"""Predecessor-derived curriculum tests, with no model or optimizer writes."""

from copy import deepcopy
from pathlib import Path
import unittest

from bilqis_mlx.pedagogical_parity import (
    audit_summary, build_plan, eligible_stage, head_bindings,
    predecessor_instruction_choice, predecessor_teaching_batch, validate_plan,
)


from bilqis_mlx.paths import LEGACY_SOURCE as LEGACY


class PredecessorFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = build_plan(LEGACY)
