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


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT.parent / "bilqis-triplets-v16"


class SemanticCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry(ROOT / "docs/CURRICULUM_REGISTRY_SNAPSHOT_20261015.json")
        grade_a = accepted_grade_a(json.loads(
            (ROOT / "docs/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text()))
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
                         {"A.MEMBER", "A.EDGE", "A.MAPS"})
        self.assertEqual(sum(e["status"] == "CROSS_SOURCE_AST_BRIDGE_UNVERIFIED"
                             for e in plan["obligations"]), 33)
        self.assertEqual(sum(e["status"] == "AWAITING_SOURCE_WITNESS"
                             for e in plan["obligations"]), 33)
        self.assertTrue(all(e["coverage_debt"] and not e["training_authorized"]
                            for e in plan["obligations"]))

    def test_actual_source_generated_compositions_require_independent_gold(self):
        plan = self._plan()
        rows = draw_connectives(LEGACY, self.graph, seed=2026101601, each=12)
        verified = verify_micro_composition_witnesses(
            plan, rows, micro=self.micro, graph=self.graph)
        confirmed = [edge for edge in verified["obligations"]
                     if edge["status"] == "SOURCE_CONTRAST_COVERED"]
        self.assertTrue(confirmed)
        self.assertTrue(all(len(edge["witness_ids"]) >= 2 for edge in confirmed))
        self.assertTrue(all(set(edge["expected_truth_pairs"]) ==
                            set(edge["observed_truth_pairs"]) for edge in confirmed))
        self.assertEqual(len(verified["source_witness_cohort_sha256"]), 64)
        self.assertTrue(all(edge["coverage_debt"] for edge in verified["obligations"]
                            if edge["producer"] in ("A.MEMBER", "A.EDGE", "A.MAPS")))
        self.assertEqual(verified, verify_micro_composition_witnesses(
            plan, rows, micro=self.micro, graph=self.graph))
        self.assertFalse(verified["training_authorized"])

        poisoned = list(copy.deepcopy(rows))
        poisoned[0]["gold"] = ("FALSE" if poisoned[0]["gold"] == "TRUE"
                               else "TRUE")
        with self.assertRaisesRegex(ValueError, "COMPOSED_ORACLE_DRIFT"):
            verify_micro_composition_witnesses(
                plan, tuple(poisoned), micro=self.micro, graph=self.graph)
        poisoned = list(copy.deepcopy(rows))
        poisoned[0]["tokens"][0] = -1
        with self.assertRaisesRegex(ValueError, "WITNESS_TOKEN_DRIFT"):
            verify_micro_composition_witnesses(
                plan, tuple(poisoned), micro=self.micro, graph=self.graph)
        poisoned = list(copy.deepcopy(rows))
        poisoned[0]["root"] = "cogal.operator.AND" if poisoned[0]["root"] != "cogal.operator.AND" else "cogal.operator.XOR"
        with self.assertRaisesRegex(ValueError, "WITNESS_SOURCE_CONTRACT_DRIFT"):
            verify_micro_composition_witnesses(
                plan, tuple(poisoned), micro=self.micro, graph=self.graph)
        poisoned = list(copy.deepcopy(rows))
        poisoned[0]["operand_truths"][0] = not poisoned[0]["operand_truths"][0]
        with self.assertRaisesRegex(ValueError, "OPERAND_ORACLE_DRIFT"):
            verify_micro_composition_witnesses(
                plan, tuple(poisoned), micro=self.micro, graph=self.graph)

    def test_source_audit_reports_remaining_debt_and_reproducible_proof(self):
        plan = self._plan()
        first = audit_pinned_micro_generator(plan, LEGACY, max_rounds=1)
        self.assertEqual(first["rounds_used"], 1)
        self.assertEqual(first["constructed_record_count"], 72)
        self.assertTrue(any(e["status"] in ("AWAITING_SOURCE_WITNESS",
                                               "SOURCE_CONTRAST_PARTIAL")
                            for e in first["obligations"]))
        improved = audit_pinned_micro_generator(plan, LEGACY, max_rounds=8)
        self.assertEqual(sum(e["status"] == "SOURCE_CONTRAST_COVERED"
                             for e in improved["obligations"]), 33)
        self.assertEqual(sum(e["status"] == "CROSS_SOURCE_AST_BRIDGE_UNVERIFIED"
                             for e in improved["obligations"]), 33)
        self.assertFalse(improved["student_exposure_measured"])
        self.assertFalse(improved["training_authorized"])
        self.assertEqual(improved, audit_pinned_micro_generator(
            plan, LEGACY, max_rounds=8))
        with self.assertRaisesRegex(ValueError, "INVALID_AUDIT_BUDGET"):
            audit_pinned_micro_generator(plan, LEGACY, max_rounds=0)

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
                            e["status"] == "AWAITING_SOURCE_WITNESS"
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
