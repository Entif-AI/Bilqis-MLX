"""Source-backed, neural-inert coverage evidence for cross-grade composition."""
from dataclasses import replace
from pathlib import Path
import copy
import json
import unittest

from bilqis_mlx.curriculum_compiler import compile_ast
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.live_grade_b import draw_connectives, live_course
from bilqis_mlx.registry_ast import load_registry
from bilqis_mlx.semantic_coverage import (
    affected_typed_dependency_closure, discover_composition_obligations,
    verify_micro_composition_witnesses, audit_pinned_micro_generator)
from bilqis_mlx.errors import BilqisError, SEMANTIC_COVERAGE


from bilqis_mlx.verification.coverage.tests.fixtures import CoverageFixture, LEGACY


class SemanticCoverageAuditTests(CoverageFixture):
    def test_direct_boolean_plan_does_not_request_historical_micro_audit(self):
        plan = self._plan()
        self.assertFalse(any(edge["status"] == "AWAITING_SOURCE_WITNESS"
                             for edge in plan["obligations"]))
        with self.assertRaises(BilqisError) as caught:
            audit_pinned_micro_generator(plan, LEGACY, max_rounds=0)
        self.assertIs(
            caught.exception.spec, SEMANTIC_COVERAGE.AUDIT.INVALID_BUDGET)
