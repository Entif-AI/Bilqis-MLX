"""Finite reference identity; source qualification is separate from admission."""
import copy
import itertools
import unittest
from pathlib import Path

from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.semantics.copular import (
    SYMBOL, SEMANTIC_ID, ReferentWorld, bind_operation, identify, evaluate,
)
from bilqis_mlx.source_adapters.copular import (
    draw, encode, decode, check, verify_source, registered_adapter,
)
from bilqis_mlx.verification.copular import independent_answer
from bilqis_mlx.vocabulary_growth import digest


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "vendor/legacy-v16"


def proposed_graph():
    """A test-only append, without Registry approval or neural allocation."""
    graph = copy.deepcopy(read_sources(SOURCE_ROOT)[2])
    node = dict(id=SYMBOL, semantic_id=SEMANTIC_ID,
                signature="Entity*Entity->Boolean", arity=2)
    graph["tokens"].append(SYMBOL)
    graph["nodes"].append(node)
    graph["row_contract_sha256"][SYMBOL] = digest(node)
    return graph


class CopularTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = proposed_graph()
        cls.operation = bind_operation(cls.graph)

    def test_copular_provider_owns_check_without_using_generator(self):
        from unittest.mock import patch
        from bilqis_mlx.factory.verification import check_copular
        self.assertEqual(check.__module__, "bilqis_mlx.source_adapters.copular")
        self.assertIs(check_copular, check)
        rows = draw(None, self.graph, seed=17, each=12)
        with patch("bilqis_mlx.source_adapters.copular.draw",
                   side_effect=AssertionError("checker invoked generator")):
            self.assertTrue(all(check(row, graph=self.graph) for row in rows))

    def test_positive_identity_is_about_denotation(self):
        world = ReferentWorld(("A", "B", "C"),
                              (("A", "C"), ("B", "C"), ("C", "A")))
        self.assertTrue(evaluate(world, identify(self.operation, "A", "B")))
        self.assertFalse(evaluate(world, identify(self.operation, "A", "C")))
        self.assertTrue(evaluate(world, identify(self.operation, "C", "C")))

    def test_independent_oracle_agrees_over_all_small_total_worlds(self):
        for targets in itertools.product("ABC", repeat=3):
            world = ReferentWorld(tuple("ABC"), tuple(zip("ABC", targets)))
            for left, right in itertools.product("ABC", repeat=2):
                expression = identify(self.operation, left, right)
                record = dict(task="bilqis.ithkuil-reference-identity/v1",
                    entities=list(world.entities), denotations=[list(p) for p in world.denotations],
                    query=dict(operator=SYMBOL, arguments=[left, right]))
                self.assertEqual(independent_answer(record),
                                 "TRUE" if evaluate(world, expression) else "FALSE")
                self.assertEqual(decode(encode(world, expression), self.graph),
                                 (world, expression))

    def test_total_single_valued_world_and_declared_references_required(self):
        for pairs in [(("A", "A"),), (("A", "A"), ("A", "B")),
                      (("A", "A"), ("B", "C"))]:
            with self.assertRaises(ValueError):
                ReferentWorld(("A", "B"), pairs)
        world = ReferentWorld(("A", "B"), (("A", "B"), ("B", "A")))
        with self.assertRaises(ValueError):
            evaluate(world, identify(self.operation, "A", "C"))

    def test_proposal_cannot_reuse_an_existing_token_or_drift_its_signature(self):
        original = read_sources(SOURCE_ROOT)[2]
        with self.assertRaisesRegex(ValueError, "COPULAR_TOKEN_NOT_ADMITTED"):
            bind_operation(original)
        graph = copy.deepcopy(self.graph)
        graph["nodes"][-1]["signature"] = "Boolean*Boolean->Boolean"
        graph["row_contract_sha256"][SYMBOL] = digest(graph["nodes"][-1])
        with self.assertRaisesRegex(ValueError, "COPULAR_TOKEN_CONTRACT_DRIFT"):
            bind_operation(graph)

    def test_draw_is_fresh_balanced_and_counterfactual_in_the_same_world(self):
        first = draw(None, self.graph, seed=17, each=12)
        self.assertEqual(first, draw(None, self.graph, seed=17, each=12))
        self.assertFalse({r["id"] for r in first} &
                         {r["id"] for r in draw(None, self.graph, seed=18, each=12)})
        self.assertEqual(sum(r["gold"] == "TRUE" for r in first), 6)
        self.assertTrue(all(check(row, graph=self.graph) for row in first))
        self.assertEqual({r["reference_pattern"] for r in first},
                         {"same-reference", "distinct-coreferent", "distinct-referent"})
        for i in range(0, 8, 2):
            a, b = first[i:i+2]
            self.assertEqual(a["record"]["query"], b["record"]["query"])
            self.assertEqual(a["tokens"][-5:], b["tokens"][-5:])
            self.assertNotEqual(a["gold"], b["gold"])
        self.assertTrue(all(len(row["tokens"]) <= 96 for row in first))

    def test_checker_rejects_tampered_gold_tokens_identity_and_unsupported_meanings(self):
        row = draw(None, self.graph, seed=33, each=12)[0]
        for changed in [dict(row, gold="FALSE" if row["gold"] == "TRUE" else "TRUE"),
                        dict(row, tokens=row["tokens"][:-1]), dict(row, id="0" * 64)]:
            self.assertFalse(check(changed, graph=self.graph))
        for adjacent in ("naming", "property", "spatiotemporal", "occurrence",
                         "existence", "membership", "material-composition"):
            record = copy.deepcopy(row["record"])
            record["query"]["operator"] = adjacent
            with self.assertRaises(ValueError):
                independent_answer(record)

    def test_source_witness_is_exact_and_registered_as_a_new_domain(self):
        witness = verify_source(ROOT)
        self.assertEqual(witness["sense_id"], "LEXSENSE-5286ade9db42c7")
        self.assertEqual(witness["scope"], "finite-reference-identity")
        self.assertEqual(registered_adapter().descriptor.variation_axes,
            ("reference-identity", "denotation", "universe-size", "fact-order", "fresh-seed"))

    def test_unselected_source_integrity_is_checked_at_its_draw_boundary(self):
        from unittest.mock import patch
        from bilqis_mlx.source_adapters.school import live_source_registry
        with patch("bilqis_mlx.source_adapters.copular.verify_source",
                   side_effect=ValueError("COPULAR_SOURCE_PDF_DRIFT")):
            registry = live_source_registry()
            self.assertIsNotNone(registry.require("bilqis_mlx.grade_a_probe.make_record",
                                                  "bilqis.mlx.grade-a-record-oracle/v2"))
            with self.assertRaisesRegex(ValueError, "SOURCE_PDF_DRIFT"):
                draw(None, self.graph, seed=1)


if __name__ == "__main__":
    unittest.main()
