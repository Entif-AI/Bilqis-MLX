"""Source-indexed, neural-inert NI construction evidence."""
from pathlib import Path
import unittest

from bilqis_mlx.ni_construction_audit import census, rows
from bilqis_mlx.token_atlas import read_historic_graph, rows_for_graph


class ConstructionCensusTests(unittest.TestCase):
    def test_all_101_historical_integer_ids_are_aligned_without_reassignment(self):
        d = census()
        self.assertEqual(d["version"], "ni-construction/20261015-a")
        self.assertEqual(d["matched_official_examples"], 5)
        self.assertEqual(d["grammar_derived_pending_independent_attestation"], 96)
        self.assertEqual(len(d["entries"]), 101)
        self.assertEqual([x["historical_token_id"] for x in d["entries"]],
                         list(range(121, 222)))
        self.assertEqual([x["historical_token"] for x in d["entries"]],
                         ["school.number." + str(n) for n in range(101)])
        self.assertTrue(d["model_abi_unchanged"])
        self.assertEqual(d["neural_updates"], 0)
        witnesses = {e["historical_token_id"]: e["ni_surface"]
                     for e in d["entries"]
                     if e["attestation"] == "LITERAL_OFFICIAL_EXAMPLE"}
        self.assertEqual(witnesses, {
            142: "wallärsa", 147: "cpalärsa", 163: "ksalirsa",
            193: "ksalorsa", 221: "gzalui",
        })
        self.assertTrue(all(not e["token_learned"] for e in d["entries"]))

    def test_real_legacy_graph_still_assigns_these_exact_numeric_ids(self):
        root = Path(__file__).resolve().parents[4] / "vendor" / "legacy-v16"
        path = root / "runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt"
        if not path.is_file():
            self.skipTest("Original full checkpoint not mounted")
        graph = read_historic_graph(path)
        original = rows_for_graph(graph)
        self.assertEqual(len(original), 222)
        for entry in rows():
            row = original[entry["historical_token_id"]]
            self.assertEqual(row[1], entry["historical_token"])
            self.assertIn("exact integer " + entry["historical_token"].split(".")[-1],
                          row[3])
            self.assertEqual(row[2], "legacy:" + entry["historical_token"])


if __name__ == "__main__":
    unittest.main()
