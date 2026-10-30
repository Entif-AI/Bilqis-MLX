from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

from lib.ithkuil.tests.source_expectations import LEXICON

import json
from pathlib import Path
import unittest

from rdflib import URIRef
from rdflib.namespace import SKOS


import lib.ithkuil.src.skos as _skos
BASE_SKOS = Path(next(iter(_skos.__path__))).resolve()
STAGED = ITHKUIL_ROOT / "src" / "skos"
VERIFY = REPO_ROOT / "_verify" / "lib" / "ithkuil" / "src" / "skos"
_skos.__path__.insert(0, str(STAGED))
if VERIFY.exists():
    _skos.__path__.insert(1, str(VERIFY))

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.lexicon_reconcile import (
    reconcile_lexicon_closure, reconcile_lexicon_frontier,
    reconciliation_json_bytes, validate_dispositions,
)
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable


LIB = BASE_SKOS.parents[1]
DATA = LIB / "_data" / "csv"
VERIFY_ITHKUIL = VERIFY.parents[1] if VERIFY.exists() else LIB
RELATION_PROFILE = (VERIFY if VERIFY.exists() else BASE_SKOS) / "root_sense_extension.json"
NEGATIVE = VERIFY_ITHKUIL / "tests" / "fixtures" / "skos_root_sense_negative.ttl"
FIXTURES = FIXTURES


def replace_table(closure: CompilerClosure, name: str, rows) -> CompilerClosure:
    tables = []
    for table in closure.tables:
        if table.name == name:
            frozen = tuple(FrozenRow(tuple(row.items())) if isinstance(row, dict) else row for row in rows)
            tables.append(LoadedTable(table.name, table.columns, frozen))
        else:
            tables.append(table)
    return CompilerClosure(closure.manifest_version, tuple(tables))


class LexiconReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closure = preflight(DATA).require_valid()
        cls.result = reconcile_lexicon_frontier(
            DATA, relation_profile_path=RELATION_PROFILE, negative_fixture_path=NEGATIVE
        )

    def test_current_frontier_receipt_matches_literal_source_counts(self):
        counts = self.result.receipt["counts"]
        self.assertEqual(counts, LEXICON["counts"])
        self.assertEqual(self.result.receipt["coverage"], LEXICON["coverage"])

    def test_zero_sense_debt_is_explicit_and_not_mislabeled_held(self):
        debt = self.result.receipt["debt"]
        self.assertEqual(len(debt["roots_with_zero_parsed_sense_ids"]), LEXICON["roots_with_zero_parsed_senses"])
        self.assertEqual(debt["held_roots"], [])
        self.assertEqual(debt["held_senses"], [])
        self.assertEqual(debt["held_by_reason"], {})
        self.assertIn("LEXROOT-0169626ce9d3bd", debt["roots_with_zero_parsed_sense_ids"])

    def test_frontier_receipt_never_claims_unparsed_chapters(self):
        frontier = self.result.receipt["frontier"]
        self.assertEqual(frontier, LEXICON["frontier_contract"])
        self.assertIn("not complete official lexicon coverage", frontier["claim"])

    def test_source_and_canonical_digests_are_bound_and_receipt_bytes_repeat(self):
        source = self.result.receipt["source"]
        self.assertEqual(set(source["lexicon_tables"]), {
            "lexicon_root_evidence", "lexicon_root_senses", "lexicon_roots"
        })
        self.assertEqual(len(source["lexicon_source_sha256"]), 64)
        canonical = self.result.receipt["canonical_rdf"]
        self.assertEqual(canonical["sha256"], self.result.canonical.sha256)
        self.assertEqual(canonical["triple_count"], len(self.result.graph))
        self.assertEqual(json.loads(reconciliation_json_bytes(self.result)), self.result.receipt)

    def test_current_snapshot_has_literal_source_and_rdf_digests(self):
        expected = json.loads(
            (FIXTURES / "skos_lexicon_reconciliation_expected.json").read_text(encoding="utf-8")
        )
        counts = self.result.receipt["counts"]
        self.assertEqual(expected["frontier"], self.result.receipt["frontier"]["scope"])
        self.assertEqual(expected["root_rows"], counts["root_rows_consumed"])
        self.assertEqual(expected["sense_rows"], counts["sense_rows_consumed"])
        self.assertEqual(expected["roots_with_zero_parsed_senses"], counts["roots_with_zero_parsed_senses"])
        self.assertEqual(expected["roots_with_multiple_parsed_senses"], counts["roots_with_multiple_parsed_senses"])
        self.assertEqual(expected["notation_count"], counts["notation_count"])
        self.assertEqual(expected["canonical_triple_count"], self.result.canonical.triple_count)
        self.assertEqual(expected["canonical_byte_count"], len(self.result.canonical.payload))
        self.assertEqual(expected["canonical_sha256"], self.result.canonical.sha256)
        self.assertEqual(expected["lexicon_source_sha256"], self.result.receipt["source"]["lexicon_source_sha256"])
        self.assertEqual(expected["compiler_input_closure_sha256"],
                         self.result.receipt["source"]["compiler_input_closure_sha256"])
        self.assertEqual(expected["receipt_sha256"], self.result.receipt["receipt_sha256"])

    def test_every_source_record_has_exactly_one_disposition(self):
        validate_dispositions({"a", "b"}, {"a"}, {"b"}, domain="fixture")
        with self.assertRaises(ProfileError) as duplicate:
            validate_dispositions({"a"}, {"a"}, {"a"}, domain="fixture")
        self.assertEqual(duplicate.exception.code, "LEXICON_DUPLICATE_ACCOUNTING")
        with self.assertRaises(ProfileError) as missing:
            validate_dispositions({"a", "b"}, {"a"}, set(), domain="fixture")
        self.assertEqual(missing.exception.code, "LEXICON_MISSING_ACCOUNTING")

    def test_unreviewed_source_mode_becomes_explicit_held_sense_and_leaves_no_concept(self):
        rows = [dict(row.values) for row in self.closure.table("lexicon_root_senses").rows]
        target = next(row for row in rows if row["lexicon_sense_id"] == "LEXSENSE-e3f64d03c6f6ec")
        target["source_locus_kind"] = "future-unreviewed-mode"
        closure = replace_table(self.closure, "lexicon_root_senses", rows)
        result = reconcile_lexicon_closure(
            closure,
            source_csv_root=DATA,
            relation_profile_path=RELATION_PROFILE,
            negative_fixture_path=NEGATIVE,
        )
        self.assertEqual(result.receipt["counts"]["sense_concepts_emitted"], LEXICON["sense_rows"] - 1)
        self.assertEqual(result.receipt["counts"]["sense_rows_held"], 1)
        self.assertEqual(result.receipt["debt"]["held_senses"], [{
            "source_sense_id": target["lexicon_sense_id"],
            "reasons": ["ROOT_SENSE_DIMENSIONS_NOT_EMITTED", "UNKNOWN_LEXICON_SOURCE_LOCUS_KIND"],
        }])
        identity = Identity("sense", (
            target["source_id"], target["lexicon_root_id"], "STEM 1", target["specification"]
        ))
        self.assertFalse(any(result.graph.triples((URIRef(identity.iri), None, None))))

    def test_reversing_primary_rows_preserves_canonical_and_receipt_digests(self):
        closure = replace_table(self.closure, "lexicon_roots", reversed(self.closure.table("lexicon_roots").rows))
        closure = replace_table(closure, "lexicon_root_senses", reversed(closure.table("lexicon_root_senses").rows))
        closure = replace_table(closure, "lexicon_root_evidence", reversed(closure.table("lexicon_root_evidence").rows))
        other = reconcile_lexicon_closure(
            closure,
            source_csv_root=DATA,
            relation_profile_path=RELATION_PROFILE,
            negative_fixture_path=NEGATIVE,
        )
        self.assertEqual(other.canonical.sha256, self.result.canonical.sha256)
        self.assertEqual(other.canonical.payload, self.result.canonical.payload)
        self.assertEqual(other.receipt["source"]["lexicon_source_sha256"],
                         self.result.receipt["source"]["lexicon_source_sha256"])
        self.assertEqual(other.receipt["receipt_sha256"], self.result.receipt["receipt_sha256"])


if __name__ == "__main__":
    unittest.main()
