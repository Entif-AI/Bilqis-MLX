"""Nontraining regression checks for the 94 source-verified semantic decisions."""
import copy
from pathlib import Path
import unittest

from bilqis_mlx.ni_adjudication import (
    load_adjudication, inspect_adjudication, materialize_review_view,
    verify_delegation_receipt, SUCCESSOR)
from bilqis_mlx.registry_versions import REVIEW_COLUMNS
from bilqis_mlx.token_atlas import read_historic_graph, rows_for_graph


def _graph():
    root = Path(__file__).resolve().parents[4] / "vendor" / "legacy-v16"
    checkpoint = root / "runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt"
    if not checkpoint.is_file():
        raise unittest.SkipTest("Audited source checkpoint is not mounted")
    return read_historic_graph(checkpoint)


class NiAdjudicationTests(unittest.TestCase):
    def test_94_source_meanings_and_ni_limitations_are_individually_traceable(self):
        d = load_adjudication()
        receipt = inspect_adjudication(d, _graph())
        self.assertEqual(receipt["reviewed_token_count"], 94)
        self.assertEqual(sum(receipt["disposition_counts"].values()), 94)
        self.assertFalse(receipt["ni_wordform_certified"])
        self.assertEqual(receipt["neural_updates"], 0)
        sample = {x["token_id"]: x for x in d["outcomes"]}
        self.assertIn("Horn-rule closure", sample[45]["source_semantics"])
        self.assertIn("finite-world Horn-rule closure", sample[105]["source_semantics"])
        self.assertIn("(true,true)", sample[60]["source_semantics"])
        self.assertIn("Two active interpretations", sample[61]["source_semantics"])
        self.assertIn("injective", sample[94]["source_semantics"])
        self.assertIn("positive-length", sample[99]["scope_difference"])
        self.assertIn("-ŇŢT-", sample[1]["reviewed_bridge"])

    def test_materialization_keeps_all_original_ids_and_is_nonmutating(self):
        graph = _graph()
        d = load_adjudication()
        expected = rows_for_graph(graph)
        old = []
        for row in expected:
            old.append(["DRAFT-" + row[0], "legacy-source/v1", row[0], row[1], row[2],
                        row[3], "old", "old", "old", "source", "locus", "note",
                        "APPROVED_QUALIFIED_RELATION", "authority", "ref", "mapping-review/20261015-c"])
        for decision in d["outcomes"]:
            r = old[decision["token_id"]]
            r[7] = decision["previous_proposal"]
            r[8] = decision["previous_relation"]
            r[12] = "HOLD_SOURCE_OR_GRAMMAR_REVIEW"
            r[15] = ""
        parent = [list(REVIEW_COLUMNS)] + old
        frozen = copy.deepcopy(parent)
        successor, evidence = materialize_review_view(d, graph, parent)
        self.assertEqual(parent, frozen)
        self.assertEqual(len(successor), 223)
        self.assertEqual(sum(r[15] == SUCCESSOR for r in successor[1:]), 94)
        for before, after in zip(parent[1:], successor[1:]):
            self.assertEqual(before[:6], after[:6])
        self.assertTrue(evidence["source_graph_unchanged"])
        corrupted = copy.deepcopy(parent)
        corrupted[46][12] = "APPROVED_EXACT_EQUIVALENCE"
        with self.assertRaisesRegex(ValueError, "HOLD_DRIFT"):
            materialize_review_view(d, graph, corrupted)
        bad = copy.deepcopy(d)
        bad["outcomes"][0]["ni_form_conformance"] = "CERTIFIED"
        with self.assertRaisesRegex(ValueError, "INVALID_ROW"):
            inspect_adjudication(bad, graph)

    def test_authority_digest_is_not_a_self_authenticating_url(self):
        with self.assertRaisesRegex(ValueError, "CONTENT_MISMATCH"):
            verify_delegation_receipt(load_adjudication(), readback_body="unverified example")


if __name__ == "__main__":
    unittest.main()
