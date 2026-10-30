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


ROOT = Path(__file__).resolve().parents[4]
LEGACY = ROOT / "vendor" / "legacy-v16"


class SemanticCoverageTests(unittest.TestCase):
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

    def test_direct_boolean_rows_do_not_claim_micro_world_transfer_evidence(self):
        plan = self._plan()
        rows = draw_connectives(LEGACY, self.graph, seed=2026101601, each=12)
        self.assertTrue(rows)
        self.assertTrue(all(row["record"]["task"] == "evaluate" for row in rows))
        self.assertTrue(all("world" not in row["record"] for row in rows))
        self.assertTrue(all(edge["status"] == "CROSS_SOURCE_AST_BRIDGE_UNVERIFIED"
                            for edge in plan["obligations"]))
        self.assertFalse(plan["training_authorized"])

    def test_direct_boolean_plan_does_not_request_historical_micro_audit(self):
        plan = self._plan()
        self.assertFalse(any(edge["status"] == "AWAITING_SOURCE_WITNESS"
                             for edge in plan["obligations"]))
        with self.assertRaises(BilqisError) as caught:
            audit_pinned_micro_generator(plan, LEGACY, max_rounds=0)
        self.assertIs(
            caught.exception.spec, SEMANTIC_COVERAGE.AUDIT.INVALID_BUDGET)

    def test_new_source_typed_primitive_and_grade_regenerate_dependents(self):
        plan = self._plan()
        self.assertEqual(affected_typed_dependency_closure(plan, ("A.MAPS",)),
                         ("A.MAPS", "B.AND", "B.IFF", "B.IMPLIES", "B.NOT",
                          "B.OR", "B.XOR"))
        new_token = replace(self.registry.tokens[0], id=222,
                            identity="fixture:cogal.operator.SYNTHETIC",
                            symbol="cogal.operator.SYNTHETIC",
                            signature="Boolean->Boolean", arity="1",
                            contract_sha256="a"*64)
        registry = replace(self.registry, tokens=(*self.registry.tokens, new_token),
                           source_sha256="b"*64)
        prototype = next(x for x in self.b_ast.nodes if x.id == "B.NOT")
        new_cap = replace(prototype, id="C.SYNTHETIC", grade="C",
                          roots=(new_token.symbol,), requires=("A.IDENTITY",))
        expanded = replace(self.b_ast, nodes=(*self.b_ast.nodes, new_cap))
        extended = discover_composition_obligations(expanded, registry)
        c_edges = [e for e in extended["obligations"] if e["consumer"] == "C.SYNTHETIC"]
        self.assertEqual(len(c_edges), 12)
        self.assertEqual({e["producer"] for e in c_edges},
                         {x.id for x in self.b_ast.nodes})
        self.assertIn("C.SYNTHETIC", affected_typed_dependency_closure(
            extended, ("A.MAPS",)))
        self.assertNotIn("C.SYNTHETIC", affected_typed_dependency_closure(
            plan, ("A.MAPS",)))

        # Meaning/signature revision automatically changes the typed edges.
        changed_token = replace(new_token, signature="Entity->Boolean",
                                contract_sha256="c"*64)
        changed_registry = replace(registry, tokens=(*self.registry.tokens, changed_token),
                                   source_sha256="d"*64)
        revised = discover_composition_obligations(expanded, changed_registry)
        self.assertFalse(any(e["consumer"] == "C.SYNTHETIC"
                             for e in revised["obligations"]))
        self.assertIn("DECLARED_PREREQUISITE_HAS_NO_TYPED_COMPOSITION",
                      {e["failure"] for e in revised["unresolved"]})

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


if __name__ == "__main__":
    unittest.main()
