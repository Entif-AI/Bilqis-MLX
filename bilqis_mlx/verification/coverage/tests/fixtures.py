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


from bilqis_mlx.paths import REPO_ROOT as ROOT

LEGACY = ROOT / "vendor" / "legacy-v16"


class CoverageFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry(ROOT / "docs/provenance/CURRICULUM_REGISTRY_SNAPSHOT_20261015.json")
        grade_a = accepted_grade_a(json.loads(
            (ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text()))
        cls.a_ast = compile_ast(grade_a)
        if LEGACY.is_dir():
            cls.b_ast = compile_ast(live_course(grade_a, LEGACY))
            cls.micro, _, cls.graph, _, _ = read_sources(LEGACY)


    def _plan(self):
        if not hasattr(self, "b_ast"):
            self.skipTest("Pinned historical source unavailable")
        return discover_composition_obligations(self.b_ast, self.registry)
