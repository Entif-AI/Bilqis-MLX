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


class SemanticCoverageDiscoveryTests(CoverageFixture):
    def test_undeclared_cross_grade_boolean_families_are_discovered(self):
        plan = self._plan()
        self.assertEqual(len(plan["obligations"]), 66)
        self.assertEqual(len(plan["unresolved"]), 0)
        self.assertFalse(plan["training_authorized"])
        by_producer = {}
        for edge in plan["obligations"]:
            by_producer.setdefault(edge["producer"], []).append(edge)
        self.assertEqual(set(by_producer), {n.id for n in self.a_ast.nodes})
        self.assertEqual({e["producer"] for e in plan["obligations"]
                          if not e["declared_prerequisite"]},
                         {n.id for n in self.a_ast.nodes})
        self.assertEqual(sum(e["status"] == "CROSS_SOURCE_AST_BRIDGE_UNVERIFIED"
                             for e in plan["obligations"]), 66)
        self.assertEqual(sum(e["status"] == "AWAITING_SOURCE_WITNESS"
                             for e in plan["obligations"]), 0)
        self.assertTrue(all(e["coverage_debt"] and not e["training_authorized"]
                            for e in plan["obligations"]))


    def test_adding_a_typed_predecessor_updates_b_without_a_constructor_patch(self):
        self._plan()
        original = next(token for token in self.registry.tokens
                        if token.symbol == "micro.compare.EQ")
        new_token = replace(original, id=222, symbol="micro.compare.SYNTHETIC",
                            identity="fixture:micro.compare.SYNTHETIC",
                            contract_sha256="a"*64)
        registry = replace(self.registry, tokens=(*self.registry.tokens, new_token),
                           source_sha256="b"*64)
        original_cap = next(n for n in self.a_ast.nodes if n.id == "A.IDENTITY")
        new_cap = replace(original_cap, id="A.SYNTHETIC",
                          roots=(new_token.symbol,))
        expanded = replace(self.b_ast, nodes=(
            *self.a_ast.nodes, new_cap, *self.b_ast.nodes[len(self.a_ast.nodes):]))
        plan = discover_composition_obligations(expanded, registry)
        new_edges = [edge for edge in plan["obligations"]
                     if edge["producer"] == "A.SYNTHETIC"]
        self.assertEqual(len(new_edges), 11)
        self.assertTrue(all(not e["declared_prerequisite"] and
                            e["status"] == "CROSS_SOURCE_AST_BRIDGE_UNVERIFIED"
                            for e in new_edges))
        revised_token = replace(new_token, signature="Entity*Entity->Number",
                                contract_sha256="c"*64)
        revised_registry = replace(registry,
            tokens=(*self.registry.tokens, revised_token), source_sha256="d"*64)
        revised = discover_composition_obligations(expanded, revised_registry)
        self.assertFalse(any(e["producer"] == "A.SYNTHETIC"
                             for e in revised["obligations"]))
