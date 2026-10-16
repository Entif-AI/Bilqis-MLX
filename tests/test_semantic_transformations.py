"""Behavior-level metamorphic checks; no neural optimizer or model mutation."""
import json
from pathlib import Path
import unittest

from bilqis_mlx.grade_a_oracle import evaluate
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.curriculum_compiler import compile_ast
from bilqis_mlx.semantic_transformations import (
    apply_law, canonical_orbit, compile_transformations,
    audit_structural_coverage, diagnose_growth)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = json.loads((ROOT / "docs/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
AST = compile_ast(accepted_grade_a(MANIFEST))


def example(capability, gold="TRUE"):
    return next(x for x in MANIFEST["training_rows"]
                if x["capability"] == capability and x["gold"] == gold)


class SemanticTransformationsTests(unittest.TestCase):
    def test_alpha_rename_preserves_every_grade_a_predicate(self):
        for capability in ("A.IDENTITY", "A.PARENT", "A.LINK",
                           "A.MEMBER", "A.EDGE", "A.MAPS"):
            for gold in ("TRUE", "FALSE"):
                with self.subTest(capability=capability, gold=gold):
                    source = example(capability, gold)
                    renamed = apply_law(source["record"], capability, "alpha_rename")
                    self.assertEqual(evaluate(renamed, capability), gold)
                    self.assertEqual(canonical_orbit(renamed),
                                     canonical_orbit(source["record"]))
                    self.assertEqual(evaluate(source["record"], capability), gold)

    def test_directed_counterexamples_flip_but_symmetric_queries_do_not(self):
        for capability in ("A.PARENT", "A.EDGE"):
            for gold in ("TRUE", "FALSE"):
                source = example(capability, gold)
                reversed_query = apply_law(source["record"], capability,
                                           "reverse_query")
                self.assertEqual(evaluate(reversed_query, capability),
                                 "FALSE" if gold == "TRUE" else "TRUE")
        for capability in ("A.IDENTITY", "A.LINK"):
            for gold in ("TRUE", "FALSE"):
                source = example(capability, gold)
                self.assertEqual(evaluate(apply_law(source["record"], capability,
                                                    "reverse_query"), capability), gold)

    def test_membership_and_mapping_counterfactuals_flip_without_new_roots(self):
        for capability, law in (("A.MEMBER", "toggle_membership"),
                                ("A.MAPS", "toggle_mapping")):
            for gold in ("TRUE", "FALSE"):
                source = example(capability, gold)
                changed = apply_law(source["record"], capability, law)
                self.assertEqual(evaluate(changed, capability),
                                 "FALSE" if gold == "TRUE" else "TRUE")
                if capability == "A.MEMBER":
                    self.assertEqual(len(changed["world"]["sets"]["K0"]),
                                     len(source["record"]["world"]["sets"]["K0"]))

    def test_inapplicable_law_rejected_not_guessed(self):
        with self.assertRaisesRegex(ValueError, "UNSUPPORTED_SEMANTIC_LAW"):
            apply_law(example("A.MEMBER")["record"], "A.MEMBER", "reverse_query")

    def test_source_oracles_materialize_transformations_as_candidates(self):
        from bilqis_mlx.grade_a_probe import read_sources
        root = ROOT.parent / "bilqis-triplets-v16"
        if not root.exists():
            self.skipTest("Pinned original interpreters not mounted")
        micro, development, graph, _, _ = read_sources(root)
        candidates = compile_transformations(
            MANIFEST["training_rows"], ast=AST, micro=micro, development=development,
            graph=graph, exam_ids={x["id"] for x in MANIFEST["examination_rows"]})
        self.assertTrue(candidates)
        self.assertTrue(all(x["admitted"] is False for x in candidates))
        self.assertEqual(len({x["id"] for x in candidates}), len(candidates))
        self.assertFalse({x["id"] for x in candidates} &
                         {x["id"] for x in MANIFEST["examination_rows"]})
        self.assertEqual(candidates, compile_transformations(
            MANIFEST["training_rows"], ast=AST, micro=micro, development=development,
            graph=graph, exam_ids={x["id"] for x in MANIFEST["examination_rows"]}))

    def test_sealed_exam_is_never_a_transformation_source(self):
        from bilqis_mlx.grade_a_probe import read_sources
        root = ROOT.parent / "bilqis-triplets-v16"
        if not root.exists():
            self.skipTest("Pinned original interpreters not mounted")
        micro, development, graph, _, _ = read_sources(root)
        with self.assertRaisesRegex(ValueError, "TRAINING_SOURCES_ONLY"):
            compile_transformations([MANIFEST["examination_rows"][0]],
                ast=AST, micro=micro, development=development, graph=graph, exam_ids=())

    def test_in_sample_growth_without_transfer_is_a_classified_failure(self):
        result = diagnose_growth(train_before=.5, train_after=1.,
                                 validation_before=.5, validation_after=.49,
                                 validation_family_count=4)
        self.assertEqual(result["failure_mode"], "GENERALIZATION_GAP")
        self.assertEqual(result["action"], "RECOMPILE_VARIATION_FAMILIES")
        self.assertFalse(result["training_authorized"])
        empty = diagnose_growth(train_before=.5, train_after=1.,
                                validation_before=.5, validation_after=.5,
                                validation_family_count=0)
        self.assertEqual(empty["failure_mode"], "NO_INDEPENDENT_VALIDATION")


    def test_identity_worlds_collapse_to_four_semantic_families(self):
        rows = [r for r in MANIFEST["training_rows"] if r["capability"] == "A.IDENTITY"]
        result = audit_structural_coverage(rows)["A.IDENTITY"]
        self.assertEqual(result["example_count"], 24)
        self.assertEqual(result["isomorphic_family_count"], 4)
        self.assertEqual(result["repeated_isomorphic_examples"], 20)
        self.assertEqual(result["diagnosis"], "SEMANTIC_VARIATION_EXHAUSTED")


if __name__ == "__main__":
    unittest.main()
