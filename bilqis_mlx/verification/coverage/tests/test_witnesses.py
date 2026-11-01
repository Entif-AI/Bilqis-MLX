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


class SemanticCoverageWitnessesTests(CoverageFixture):
    def test_direct_boolean_rows_do_not_claim_micro_world_transfer_evidence(self):
        plan = self._plan()
        rows = draw_connectives(LEGACY, self.graph, seed=2026101601, each=12)
        self.assertTrue(rows)
        self.assertTrue(all(row["record"]["task"] == "evaluate" for row in rows))
        self.assertTrue(all("world" not in row["record"] for row in rows))
        self.assertTrue(all(edge["status"] == "CROSS_SOURCE_AST_BRIDGE_UNVERIFIED"
                            for edge in plan["obligations"]))
        self.assertFalse(plan["training_authorized"])


    def test_missing_signatures_and_oracles_are_visible(self):
        plan = self._plan()
        node = replace(self.b_ast.nodes[-1], id="C.UNKNOWN", grade="C",
                       roots=("not.in.the.registry",))
        proposed = replace(self.b_ast, nodes=(*self.b_ast.nodes, node))
        result = discover_composition_obligations(proposed, self.registry)
        self.assertIn({"capability": "C.UNKNOWN",
                       "failure": "MISSING_UNIQUE_TYPED_SOURCE_ROOT"}, result["unresolved"])
        unsupported = replace(self.b_ast.nodes[-1], id="C.UNSOURCED", grade="C",
                              oracle=None)
        proposed = replace(self.b_ast, nodes=(*self.b_ast.nodes, unsupported))
        result = discover_composition_obligations(proposed, self.registry)
        self.assertIn({"capability": "C.UNSOURCED",
                       "failure": "MISSING_ORACLE_OR_SOURCE_ANCHOR"}, result["unresolved"])
        self.assertTrue(all(e["status"] == "CAPABILITY_CONTRACT_UNVERIFIED"
                            for e in result["obligations"]
                            if e["consumer"] == "C.UNSOURCED"))
        with self.assertRaisesRegex(ValueError, "UNRESOLVED_CONTRACT_PROOF_BLOCKED"):
            verify_micro_composition_witnesses(
                result, (), micro=self.micro, graph=self.graph)
        self.assertFalse(result["training_authorized"])
