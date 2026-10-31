from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from lib.ithkuil.src.skos.build import compile_corpus
from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.determinism import (
    compare_bundles,
    compare_graphs,
    determinism_json_bytes,
    repeat_build_check,
    require_equivalent,
)
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.publication import make_bundle


PACKAGE_ROOT = ITHKUIL_ROOT
SOURCE_ROOT = Path(
    os.environ.get("BILQIS_SKOS_SOURCE_ROOT", str(PACKAGE_ROOT / "_data/csv"))
)
FIXTURES = FIXTURES
EXPECTED = json.loads((FIXTURES / "determinism_expected.json").read_text(encoding="utf-8"))
VERIFY_ROOT = REPO_ROOT


def _reverse_csv_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target)
    for path in target.rglob("*.csv"):
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fields, rows = reader.fieldnames, list(reader)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(reversed(fields)))
            writer.writeheader()
            writer.writerows(reversed(rows))


class DeterminismTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.reference = compile_corpus(SOURCE_ROOT)

    def test_repeat_build_same_process_matches_literal_digest(self):
        second = compile_corpus(SOURCE_ROOT)
        case = compare_bundles(self.reference, second, scenario="same-process-repeat")
        self.assertTrue(case.equal)
        self.assertEqual(case.before_sha256, EXPECTED["current_core"]["canonical_sha256"])
        self.assertEqual(case.before_triples, EXPECTED["current_core"]["triple_count"])
        self.assertEqual(require_equivalent(case), case)
        report = repeat_build_check(SOURCE_ROOT)
        self.assertTrue(report.deterministic)
        self.assertEqual(determinism_json_bytes(report), determinism_json_bytes(report))

    def test_reordered_csv_rows_and_columns_preserve_canonical_graph(self):
        with tempfile.TemporaryDirectory() as temporary:
            shuffled = Path(temporary) / "csv"
            _reverse_csv_tree(SOURCE_ROOT, shuffled)
            candidate = compile_corpus(shuffled)
        case = compare_bundles(self.reference, candidate, scenario="reordered-csv")
        self.assertTrue(case.equal)
        self.assertEqual(case.before_sha256, case.after_sha256)

    def test_fresh_processes_temp_dirs_and_hash_seeds_match(self):
        script = (
            "from lib.ithkuil.src.skos.build import compile_corpus;"
            "import json,sys;"
            "b=compile_corpus(sys.argv[1]);"
            "print(json.dumps({'sha256':b.metadata()['canonical_sha256'],"
            "'triples':b.metadata()['triple_count']},sort_keys=True))"
        )
        observed = []
        for seed in ("17", "83"):
            with tempfile.TemporaryDirectory() as directory:
                result = subprocess.run(
                    [sys.executable, "-B", "-c", script, str(SOURCE_ROOT)],
                    cwd=directory,
                    env={**os.environ, "PYTHONPATH": str(VERIFY_ROOT), "PYTHONHASHSEED": seed},
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=90,
                    check=True,
                )
                observed.append(json.loads(result.stdout))
        self.assertEqual(
            observed,
            [
                {
                    "sha256": EXPECTED["current_core"]["canonical_sha256"],
                    "triples": EXPECTED["current_core"]["triple_count"],
                }
            ]
            * 2,
        )

    def test_unicode_heavy_graph_is_insertion_order_invariant(self):
        lexical = EXPECTED["unicode_fixture"]["lexical"]
        triples = [
            (URIRef("urn:unicode:s"), SKOS.notation, Literal(lexical, datatype=URIRef("urn:unicode:d"), normalize=False)),
            (URIRef("urn:unicode:s"), URIRef("urn:unicode:p"), Literal("ž / ẓ / ţ / ç", lang="en")),
        ]
        first, second = Graph(), Graph()
        for triple in triples:
            first.add(triple)
        for triple in reversed(triples):
            second.add(triple)
        case = compare_graphs(first, second, scenario="unicode-insertion-order")
        self.assertTrue(case.equal)
        self.assertIsNone(case.first_removed)
        self.assertIsNone(case.first_added)

    def test_semantic_mutation_changes_digest_and_reports_first_delta(self):
        before = Graph().add((URIRef("urn:determinism:s"), URIRef("urn:determinism:p"), Literal("old")))
        after = Graph().add((URIRef("urn:determinism:s"), URIRef("urn:determinism:p"), Literal("new")))
        case = compare_graphs(before, after, scenario="intentional-semantic-mutation")
        self.assertFalse(case.equal)
        self.assertNotEqual(case.before_sha256, case.after_sha256)
        self.assertEqual(case.first_removed, EXPECTED["mutation_delta"]["removed"])
        self.assertEqual(case.first_added, EXPECTED["mutation_delta"]["added"])
        with self.assertRaises(ProfileError) as caught:
            require_equivalent(case)
        self.assertEqual(caught.exception.code, "CANONICAL_DETERMINISM_MISMATCH")
        self.assertIn(f"first_removed={EXPECTED['mutation_delta']['removed']}", caught.exception.details)

    def test_bundle_receipt_digest_mismatch_is_not_accepted(self):
        from dataclasses import replace

        forged_manifest = json.loads(self.reference.manifest)
        forged_manifest["canonical_sha256"] = "0" * 64
        forged = replace(
            self.reference,
            manifest=(json.dumps(forged_manifest, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        )
        with self.assertRaises(ProfileError) as caught:
            compare_bundles(forged, self.reference, scenario="forged-reference-receipt")
        self.assertEqual(caught.exception.code, "DETERMINISM_REFERENCE_RECEIPT_MISMATCH")


class TypedLexicalBundleTests(unittest.TestCase):
    def test_exact_typed_lexical_forms_survive_bundle_readback(self):
        bundles = []
        for lexical in ("01", "1"):
            graph = Graph().add((URIRef("urn:literal:s"), RDF.value,
                                 Literal(lexical, datatype=XSD.integer, normalize=False)))
            canonical = canonicalize(graph)
            bundles.append(make_bundle(
                {"canonical.nt": canonical.payload, "held.json": b"{}\n",
                 "digest.json": b"{}\n", "input.json": b"{}\n"},
                {"canonical_sha256": canonical.sha256, "triple_count": 1},
            ))
        unchanged = compare_bundles(bundles[0], bundles[0], scenario="typed-lexical-repeat")
        self.assertTrue(unchanged.equal)
        self.assertEqual(unchanged.before_sha256, bundles[0].metadata()["canonical_sha256"])
        changed = compare_bundles(bundles[0], bundles[1], scenario="typed-lexical-change")
        self.assertFalse(changed.equal)
        self.assertIn('"01"', changed.first_removed)
        self.assertIn('"1"', changed.first_added)


if __name__ == "__main__":
    unittest.main()
