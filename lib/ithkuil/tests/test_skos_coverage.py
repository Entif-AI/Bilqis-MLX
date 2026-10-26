from __future__ import annotations

import csv
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import unittest

from rdflib import Graph, Literal, URIRef

from lib.ithkuil.src.skos.atomic import compile_atomic
from lib.ithkuil.src.skos.atomic_reconcile import reconcile_atomic
from lib.ithkuil.src.skos.composition import load_composition_profile
from lib.ithkuil.src.skos.coverage import (
    ZERO_SEMANTICS,
    build_coverage,
    compose_coverage,
    coverage_json_bytes,
)
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.extension_vocabulary import load_extension_vocabulary
from lib.ithkuil.src.skos.lexicon_reconcile import reconcile_lexicon_frontier
from lib.ithkuil.src.skos.mapping_corpus import compile_mapping_corpus
from lib.ithkuil.src.skos.preflight import preflight
from lib.ithkuil.src.skos.residue_reconcile import reconcile_residue


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = Path(
    os.environ.get("BILQIS_SKOS_SOURCE_ROOT", str(PACKAGE_ROOT / "_data/csv"))
)
FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXPECTED = json.loads((FIXTURES / "coverage_current_expected.json").read_text(encoding="utf-8"))
CLEAN = json.loads((FIXTURES / "coverage_clean_fixture.json").read_text(encoding="utf-8"))


def _csv_rows(name: str):
    with (SOURCE_ROOT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _current_coverage():
    closure = preflight(SOURCE_ROOT).require_valid()
    atomic = compile_atomic(closure)
    atomic_reconciliation = reconcile_atomic(closure, atomic)
    relation_profile = PACKAGE_ROOT / "src/skos/root_sense_extension.json"
    lexicon = reconcile_lexicon_frontier(
        SOURCE_ROOT,
        relation_profile_path=relation_profile,
        negative_fixture_path=FIXTURES / "skos_root_sense_negative.ttl",
    )
    profile = load_composition_profile(
        PACKAGE_ROOT / "src/skos/composition_profile.json",
        closure,
        FIXTURES / "skos_composition_negative.ttl",
    )
    vocabulary = load_extension_vocabulary(
        PACKAGE_ROOT / "src/skos/extension_vocabulary.json",
        SOURCE_ROOT,
    )
    residue = reconcile_residue(
        closure,
        degree_rows=_csv_rows("affix_degrees.csv"),
        component_rows=_csv_rows("composition_components.csv"),
        allomorph_rows=_csv_rows("allomorph_rules.csv"),
        composition_profile=profile,
        vocabulary=vocabulary,
    )
    mapping = compile_mapping_corpus(SOURCE_ROOT)
    profile_sha = hashlib.sha256((SOURCE_ROOT.parents[1] / "SKOS_PROFILE.md").read_bytes()).hexdigest()
    coverage = build_coverage(
        closure,
        atomic_compiled=atomic,
        atomic_reconciliation=atomic_reconciliation,
        lexicon=lexicon,
        residue=residue,
        mapping=mapping,
        profile_version="bilqis-skos-profile/1",
        profile_sha256=profile_sha,
    )
    return closure, atomic, lexicon, residue, mapping, coverage


def _clean_domain(name: str, row: dict) -> dict:
    semantics = dict(ZERO_SEMANTICS)
    field = {
        "atomic": "concepts",
        "lexicon": "roots",
        "mapping": "mappings",
        "residue": "compositions",
    }[name]
    semantics[field] = 1
    return {
        "source_rows": 1,
        "dispositions": {
            "EMITTED": 1,
            "HELD": 0,
            "REJECTED": 0,
            "UNSUPPORTED": 0,
            "IR_ONLY": 0,
        },
        "rows": [
            {
                **row,
                "status": "EMITTED",
                "reason_code": f"EMITTED_{name.upper()}_FIXTURE",
                "owner": "#68-fixture",
            }
        ],
        "semantic_counts": semantics,
        "notation_counts": {},
        "frontier_debt": [],
    }


class CoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.closure, cls.atomic, cls.lexicon, cls.residue, cls.mapping, cls.coverage = _current_coverage()

    def test_current_corpus_matches_literal_whole_source_summary(self):
        receipt = self.coverage.receipt
        self.assertEqual(receipt["build_status"], EXPECTED["build_status"])
        self.assertEqual(receipt["canonical_rdf"], EXPECTED["canonical_rdf"])
        self.assertEqual(receipt["compiler"]["profile_sha256"], EXPECTED["profile_sha256"])
        self.assertEqual(receipt["totals"], EXPECTED["totals"])
        self.assertEqual(
            {entry["domain"]: entry["sha256"] for entry in receipt["inputs"]},
            EXPECTED["inputs"],
        )
        for name, expected in EXPECTED["domains"].items():
            domain = receipt["domains"][name]
            for field in (
                "source_rows",
                "dispositions",
                "semantic_counts",
                "notation_counts",
                "frontier_debt",
            ):
                self.assertEqual(domain[field], expected[field], (name, field))
        self.assertEqual(sum(len(domain["rows"]) for domain in receipt["domains"].values()), EXPECTED["totals"]["source_rows"])
        self.assertEqual(coverage_json_bytes(self.coverage), coverage_json_bytes(self.coverage))

    def test_corrected_lexicon_graph_is_consumed_without_downstream_filtering(self):
        expected = EXPECTED["domains"]["lexicon"]
        self.assertEqual(self.lexicon.canonical.sha256, expected["corrected_graph_sha256"])
        self.assertEqual(self.lexicon.canonical.triple_count, expected["corrected_graph_triples"])
        self.assertEqual(self.lexicon.receipt["receipt_sha256"], expected["corrected_receipt_sha256"])
        predicates = {str(predicate) for _, predicate, _ in self.lexicon.graph}
        self.assertFalse(any("sourceLocusKind" in predicate for predicate in predicates))

    def test_current_corpus_is_explicitly_partial_not_release_clean(self):
        receipt = self.coverage.receipt
        self.assertEqual(receipt["build_status"], "partial")
        self.assertEqual(receipt["totals"]["dispositions"]["HELD"], 1051)
        self.assertEqual(receipt["totals"]["dispositions"]["REJECTED"], 1)
        self.assertEqual(receipt["domains"]["lexicon"]["frontier_debt"], EXPECTED["domains"]["lexicon"]["frontier_debt"])
        self.assertEqual(receipt["domains"]["mapping"]["frontier_debt"][0]["count"], 552)

    def test_every_domain_row_id_is_unique_and_status_totals_reconcile(self):
        for name, domain in self.coverage.receipt["domains"].items():
            ids = [(row["table"], row["key"]) for row in domain["rows"]]
            self.assertEqual(len(ids), len(set(ids)), name)
            observed = {status: 0 for status in domain["dispositions"]}
            for row in domain["rows"]:
                observed[row["status"]] += 1
            self.assertEqual(observed, domain["dispositions"], name)

    def test_expected_canonical_binding_rejects_mismatched_41_result(self):
        forged = replace(self.coverage.canonical, sha256="0" * 64)
        with self.assertRaises(ProfileError) as caught:
            build_coverage(
                self.closure,
                atomic_compiled=self.atomic,
                atomic_reconciliation=reconcile_atomic(self.closure, self.atomic),
                lexicon=self.lexicon,
                residue=self.residue,
                mapping=self.mapping,
                profile_version="bilqis-skos-profile/1",
                profile_sha256=EXPECTED["profile_sha256"],
                expected_canonical=forged,
            )
        self.assertEqual(caught.exception.code, "COVERAGE_CANONICAL_RDF_MISMATCH")

    def test_clean_bounded_fixture_is_complete_and_release_ready(self):
        domains = {
            name: _clean_domain(name, row)
            for name, row in CLEAN["rows"].items()
        }
        graphs = []
        for subject, predicate, value in CLEAN["triples"]:
            graph = Graph()
            graph.add((URIRef(subject), URIRef(predicate), Literal(value)))
            graphs.append(graph)
        build = compose_coverage(
            domains,
            CLEAN["inputs"],
            graphs,
            profile_version=CLEAN["profile_version"],
            profile_sha256=CLEAN["profile_sha256"],
        )
        self.assertEqual(build.receipt["build_status"], "complete")
        self.assertEqual(build.receipt["totals"]["source_rows"], 4)
        self.assertEqual(build.receipt["totals"]["dispositions"]["EMITTED"], 4)
        self.assertEqual(build.receipt["conflicts"], {"blocking": 0, "by_reason": {}})
        self.assertEqual(build.canonical.sha256, CLEAN["expected_canonical_sha256"])
        self.assertEqual(build.canonical.triple_count, CLEAN["expected_triple_count"])


if __name__ == "__main__":
    unittest.main()
