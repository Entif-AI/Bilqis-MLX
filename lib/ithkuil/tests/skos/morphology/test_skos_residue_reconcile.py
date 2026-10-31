from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

import csv
import json
from pathlib import Path
import unittest

from rdflib import URIRef

import lib.ithkuil.src.skos as _skos
BASE_SKOS = Path(next(iter(_skos.__path__))).resolve()
STAGED = ITHKUIL_ROOT / "src" / "skos"
VERIFY = REPO_ROOT / "_verify" / "lib" / "ithkuil" / "src" / "skos"
_skos.__path__.insert(0, str(STAGED))
if VERIFY.exists():
    _skos.__path__.insert(1, str(VERIFY))

from lib.ithkuil.src.skos.composition import load_composition_profile
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.extension_vocabulary import load_extension_vocabulary
from lib.ithkuil.src.skos.preflight import preflight
from lib.ithkuil.src.skos.residue_reconcile import (
    reconcile_residue, reconciliation_json_bytes, validate_partition,
)


LIB = BASE_SKOS.parents[1]
DATA = LIB / "_data" / "csv"
VERIFY_ITHKUIL = VERIFY.parents[1] if VERIFY.exists() else LIB
COMPOSITION_PROFILE = (VERIFY if VERIFY.exists() else BASE_SKOS) / "composition_profile.json"
COMPOSITION_NEGATIVE = VERIFY_ITHKUIL / "tests" / "fixtures" / "skos_composition_negative.ttl"
VOCAB = (VERIFY if VERIFY.exists() else BASE_SKOS) / "extension_vocabulary.json"
FIXTURES = FIXTURES


def rows(name: str):
    with (DATA / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class ResidueReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(DATA).require_valid()
        cls.degree_rows = rows("affix_degrees.csv")
        cls.component_rows = rows("composition_components.csv")
        cls.rule_rows = rows("allomorph_rules.csv")
        cls.profile = load_composition_profile(COMPOSITION_PROFILE, cls.closure, COMPOSITION_NEGATIVE)
        cls.vocab = load_extension_vocabulary(VOCAB, DATA)
        cls.result = reconcile_residue(
            cls.closure, degree_rows=cls.degree_rows, component_rows=cls.component_rows,
            allomorph_rows=cls.rule_rows, composition_profile=cls.profile, vocabulary=cls.vocab,
        )

    def test_current_census_is_exactly_one_disposition_per_source_row(self):
        receipt = self.result.receipt
        self.assertEqual(receipt["counts"], {
            "source_rows": 6062, "emitted": 6062, "held": 0, "ir_only": 0,
        })
        expected = {
            "affix_degrees": 271,
            "morpheme_compositions": 1917,
            "composition_components": 3855,
            "allomorph_rules": 19,
        }
        for table, count in expected.items():
            self.assertEqual(receipt["tables"][table]["source_count"], count)
            self.assertEqual(len(receipt["tables"][table]["emitted_ids"]), count)
            self.assertEqual(receipt["tables"][table]["held"], [])
            self.assertEqual(receipt["tables"][table]["ir_only"], [])

    def test_every_custom_predicate_is_admitted_by_sixty(self):
        used = {iri.rsplit("/", 1)[-1] for iri in self.result.receipt["used_extension_terms"]}
        self.assertEqual(used, {
            "degreeOf", "surfacePattern", "condition", "componentCount",
            "componentRole", "slotLabel", "inputPattern", "intermediatePattern",
            "outputPattern", "allomorphDomain",
        })
        self.assertTrue(used <= self.vocab.admitted_keys)

    def test_missing_component_holds_remaining_parent_group_instead_of_shortening(self):
        changed = [row for row in self.component_rows if row["component_id"] != "CC-88d06c223b2f4a"]
        result = reconcile_residue(
            self.closure, degree_rows=self.degree_rows, component_rows=changed,
            allomorph_rows=self.rule_rows, composition_profile=self.profile, vocabulary=self.vocab,
        )
        component = result.receipt["tables"]["composition_components"]
        self.assertGreater(len(component["held"]), 0)
        reasons = {reason for item in component["held"] for reason in item["reasons"]}
        self.assertIn("COMPONENT_COUNT_MISMATCH", reasons)

    def test_duplicate_affix_degree_source_id_fails_before_projection(self):
        changed = [dict(row) for row in self.degree_rows]
        duplicate = dict(changed[1]); duplicate["degree_id"] = changed[0]["degree_id"]
        with self.assertRaises(ProfileError) as caught:
            reconcile_residue(
                self.closure, degree_rows=[*changed, duplicate], component_rows=self.component_rows,
                allomorph_rows=self.rule_rows, composition_profile=self.profile, vocabulary=self.vocab,
            )
        self.assertEqual(caught.exception.code, "RESIDUE_DUPLICATE_SOURCE_ID")

    def test_unsupported_allomorph_rule_is_explicitly_held_not_dropped(self):
        changed = [dict(row) for row in self.rule_rows]
        target = changed[0]; target["output_pattern"] = ""
        result = reconcile_residue(
            self.closure, degree_rows=self.degree_rows, component_rows=self.component_rows,
            allomorph_rows=changed, composition_profile=self.profile, vocabulary=self.vocab,
        )
        rules_receipt = result.receipt["tables"]["allomorph_rules"]
        held = {item["id"]: item["reasons"] for item in rules_receipt["held"]}
        self.assertIn(target["allomorph_rule_id"], held)
        self.assertIn("ALLOMORPH_RULE_REQUIRED_FIELD_MISSING", held[target["allomorph_rule_id"]])
        self.assertEqual(result.receipt["counts"]["held"], 1)

    def test_partition_validator_rejects_multiple_missing_and_out_of_scope(self):
        validate_partition({"a", "b"}, {"a"}, {"b"}, set(), table="fixture")
        for emitted, held, ir, code in (
            ({"a"}, {"a"}, set(), "RESIDUE_MULTIPLE_DISPOSITIONS"),
            ({"a"}, set(), set(), "RESIDUE_MISSING_DISPOSITION"),
            ({"a", "x"}, {"b"}, set(), "RESIDUE_OUT_OF_SCOPE_DISPOSITION"),
        ):
            with self.subTest(code=code):
                with self.assertRaises(ProfileError) as caught:
                    validate_partition({"a", "b"}, emitted, held, ir, table="fixture")
                self.assertEqual(caught.exception.code, code)

    def test_row_reorder_preserves_source_graph_and_receipt_digests(self):
        other = reconcile_residue(
            self.closure,
            degree_rows=reversed(self.degree_rows),
            component_rows=reversed(self.component_rows),
            allomorph_rows=reversed(self.rule_rows),
            composition_profile=self.profile, vocabulary=self.vocab,
        )
        self.assertEqual(other.canonical.payload, self.result.canonical.payload)
        self.assertEqual(other.receipt["residue_source_sha256"], self.result.receipt["residue_source_sha256"])
        self.assertEqual(other.receipt["receipt_sha256"], self.result.receipt["receipt_sha256"])

    def test_literal_snapshot_binds_current_source_and_canonical_digests(self):
        expected = json.loads(
            (FIXTURES / "skos_residue_reconciliation_expected.json").read_text(encoding="utf-8")
        )
        self.assertEqual(expected["counts"], self.result.receipt["counts"])
        self.assertEqual(expected["canonical_triple_count"], self.result.canonical.triple_count)
        self.assertEqual(expected["canonical_byte_count"], len(self.result.canonical.payload))
        self.assertEqual(expected["canonical_sha256"], self.result.canonical.sha256)
        self.assertEqual(expected["residue_source_sha256"], self.result.receipt["residue_source_sha256"])
        self.assertEqual(expected["receipt_sha256"], self.result.receipt["receipt_sha256"])
        self.assertEqual(json.loads(reconciliation_json_bytes(self.result)), self.result.receipt)


if __name__ == "__main__":
    unittest.main()
