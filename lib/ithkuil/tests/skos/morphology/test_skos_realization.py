"""Source-backed realization normalization proofs for issue #45."""
from __future__ import annotations
from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import unittest

from lib.ithkuil.src.skos.identity import Identity
from lib.ithkuil.src.skos.notation import NEW_ITHKUIL_DATATYPE_IRI
from lib.ithkuil.src.skos.preflight import CompilerClosure, preflight
from lib.ithkuil.src.skos.preflight_io import FrozenRow, LoadedTable
from lib.ithkuil.src.skos.realization import normalize_atomic_realizations
from lib.ithkuil.src.skos.resolver import GRAMMAR_ATOM_CLASSES, RecordRef, resolve_identities


ROOT = ITHKUIL_ROOT
SOURCE_ROOT = ROOT / "_data" / "csv"
FIXTURES = FIXTURES
SOURCE = json.loads((FIXTURES / "realization_source_expected.json").read_text(encoding="utf-8"))
NORMALIZED = json.loads((FIXTURES / "realization_normalized_expected.json").read_text(encoding="utf-8"))


class RealizationNormalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.closure = preflight(SOURCE_ROOT).require_valid()
        cls.resolution = resolve_identities(cls.closure)
        cls.normalized = normalize_atomic_realizations(cls.closure, cls.resolution)
        cls.groups = {group.identity.iri: group for group in cls.normalized.groups}

    def test_literal_before_after_counts_match_current_source_snapshot(self) -> None:
        counts = SOURCE["counts"]
        atomic = self.closure.table("morphemes_atomic").rows
        grammar = tuple(row for row in atomic if row["morpheme_class"] in GRAMMAR_ATOM_CLASSES)
        roots = tuple(row for row in atomic if row["morpheme_class"] not in GRAMMAR_ATOM_CLASSES)
        semantic = defaultdict(list)
        for row in grammar:
            semantic[(row["category_code"], row["value_code"])].append(row)
        realization_counts = Counter(row["realization_type"] for row in atomic)
        combos = Counter(
            " + ".join(sorted({row["realization_type"] for row in rows}))
            for rows in semantic.values()
            if len(rows) > 1
        )
        self.assertEqual(len(atomic), counts["atomic_source_rows"])
        self.assertEqual(len(grammar), counts["grammar_source_rows"])
        self.assertEqual(len(semantic), counts["grammar_semantic_groups"])
        self.assertEqual(len(roots), counts["atomic_root_source_rows"])
        self.assertEqual(sum(len(rows) > 1 for rows in semantic.values()), counts["multi_grammar_keys"])
        self.assertEqual(sum(len(rows) - 1 for rows in semantic.values()), counts["collapsed_extra_grammar_rows"])
        self.assertEqual(dict(sorted(realization_counts.items())), counts["realization_type_counts"])
        self.assertEqual(dict(sorted(combos.items())), counts["multi_group_type_combinations"])
        self.assertEqual(self.normalized.source_row_count, 772)
        self.assertEqual(len(self.normalized.groups), 650)
        self.assertEqual(self.normalized.grammar_group_count, 485)
        self.assertEqual(self.normalized.atomic_root_group_count, 165)
        self.assertEqual(sum(len(group.realizations) for group in self.normalized.groups), 772)
        self.assertEqual(self.normalized.issues, ())

    def test_source_fixture_pins_exact_tracked_rows_and_assertions(self) -> None:
        self.assertEqual(
            hashlib.sha256((SOURCE_ROOT / "morphemes_atomic.csv").read_bytes()).hexdigest(),
            SOURCE["tracked_input_digests"]["morphemes_atomic.csv"],
        )
        self.assertEqual(
            hashlib.sha256((SOURCE_ROOT / "source_assertions.csv").read_bytes()).hexdigest(),
            SOURCE["tracked_input_digests"]["source_assertions.csv"],
        )
        rows = {row["atomic_id"]: row for row in self.closure.table("morphemes_atomic").rows}
        assertions = {
            row["entity_id"]: row["assertion_id"]
            for row in self.closure.table("source_assertions").rows
            if row["entity_kind"] == "atomic_morpheme"
        }
        for fixture_rows in SOURCE["representative_cases"].values():
            for expected in fixture_rows:
                actual = rows[expected["atomic_id"]]
                for field in (
                    "surface_form_raw", "surface_form_normalized", "morpheme_family",
                    "morpheme_class", "slot", "category_code", "category_name",
                    "value_code", "value_name", "semantic_summary", "realization_type",
                    "allomorph_group_id", "allomorph_condition", "primary_source_id",
                    "primary_section_id", "primary_table_id", "primary_source_line",
                    "primary_source_url", "primary_source_anchor", "evidence_status",
                ):
                    self.assertEqual(actual[field], expected[field], (expected["atomic_id"], field))
                self.assertEqual(assertions[expected["atomic_id"]], expected["source_assertion_id"])

    def test_representative_groups_match_literal_normalized_fixture(self) -> None:
        for expected in NORMALIZED["groups"].values():
            group = self.groups[expected["identity_iri"]]
            self.assertEqual(group.role, expected["role"])
            self.assertEqual([scheme.iri for scheme in group.schemes], expected["scheme_iris"])
            self.assertEqual(
                [[ref.table, ref.key] for ref in group.source_records],
                expected["source_records"],
            )
            actual = []
            for realization in group.realizations:
                actual.append({
                    "atomic_id": realization.record_ref.key,
                    "surface_form_raw": realization.raw_form,
                    "surface_form_normalized": realization.normalized_form,
                    "realization_type": realization.realization_type,
                    "allomorph_group_id": realization.allomorph_group_id,
                    "allomorph_condition": realization.condition,
                    "morpheme_family": realization.family,
                    "morpheme_class": realization.morpheme_class,
                    "slot": realization.slot,
                    "primary_source_id": realization.source_id,
                    "primary_section_id": realization.section_id,
                    "primary_table_id": realization.table_id,
                    "primary_source_line": realization.source_line,
                    "primary_source_url": realization.source_url,
                    "primary_source_anchor": realization.source_anchor,
                })
                self.assertEqual(realization.notation_datatype_iri, NEW_ITHKUIL_DATATYPE_IRI)
            self.assertEqual(actual, expected["realizations"])

    def test_named_realization_classes_all_preserve_one_identity(self) -> None:
        expected = {
            "PERSPECTIVE_ESSENCE::M.NRM": {"zero", "standalone_allomorph"},
            "AFFILIATION::ASO": {"overt", "standalone_allomorph"},
            "EFFECT::1:BEN": {"overt", "conditioned_allomorph"},
            "CASE::ACT": {"underlying_glottal", "realized_allomorph"},
            "REGISTER::DSV": {"overt", "overt_optional"},
            "REGISTER::NRR": {"zero"},
            "CONFIGURATION::DDS": {"overt"},
            "CONFIGURATION::UPX": {"zero"},
        }
        for label, types in expected.items():
            iri = NORMALIZED["groups"][label]["identity_iri"]
            group = self.groups[iri]
            self.assertEqual({item.realization_type for item in group.realizations}, types)
            self.assertEqual(len({item.record_ref for item in group.realizations}), len(group.realizations))

        dsv = self.groups[NORMALIZED["groups"]["REGISTER::DSV"]["identity_iri"]]
        self.assertEqual(
            {item.family for item in dsv.realizations},
            {"register_adjunct_initial", "register_adjunct_final"},
        )
        self.assertEqual(
            {item.slot for item in dsv.realizations},
            {"register initial", "register final"},
        )

    def test_raw_unicode_and_conditions_remain_separate_from_notation_identity(self) -> None:
        case = self.groups[NORMALIZED["groups"]["CASE::ACT"]["identity_iri"]]
        self.assertEqual(
            {(item.raw_form, item.normalized_form) for item in case.realizations},
            {("ai’", "ai'"), ("a’i", "a'i")},
        )
        self.assertEqual(
            {item.condition for item in case.realizations},
            {"formative Slot IX underlying case form", "surface realization of glottal case form"},
        )
        zero = self.groups[NORMALIZED["groups"]["CONFIGURATION::UPX"]["identity_iri"]]
        self.assertEqual([(item.raw_form, item.normalized_form) for item in zero.realizations], [("∅", "∅")])
        self.assertTrue(all(item.raw_form != item.condition for item in case.realizations))

    def test_same_surface_string_never_collapses_distinct_semantic_values(self) -> None:
        atv = self.groups[NORMALIZED["groups"]["EXTENSION::ATV"]["identity_iri"]]
        dpl = self.groups[NORMALIZED["groups"]["EXTENSION::DPL"]["identity_iri"]]
        self.assertNotEqual(atv.identity, dpl.identity)
        self.assertIn("b", {item.raw_form for item in atv.realizations})
        self.assertIn("b", {item.raw_form for item in dpl.realizations})
        self.assertEqual(atv.identity, Identity("grammar", ("EXTENSION", "ATV")))
        self.assertEqual(dpl.identity, Identity("grammar", ("EXTENSION", "DPL")))

    def test_atomic_roots_remain_source_qualified_and_senses_are_not_realization_groups(self) -> None:
        expected = NORMALIZED["atomic_root_control"]
        group = self.groups[expected["identity_iri"]]
        self.assertEqual(group.role, "root")
        self.assertEqual(group.schemes, ())
        self.assertEqual(group.identity, Identity("root", ("NI-WEB-CH07", "ATOM-00e59b6388deca")))
        self.assertEqual([[ref.table, ref.key] for ref in group.source_records], expected["source_records"])
        self.assertTrue(all(item.identity.kind in {"grammar", "root"} for item in self.normalized.groups))

    def test_row_reordering_is_exactly_normalization_invariant(self) -> None:
        shuffled = CompilerClosure(
            self.closure.manifest_version,
            tuple(
                LoadedTable(table.name, table.columns, tuple(reversed(table.rows)))
                for table in reversed(self.closure.tables)
            ),
        )
        result = normalize_atomic_realizations(shuffled, resolve_identities(shuffled))
        self.assertEqual(result, self.normalized)


if __name__ == "__main__":
    unittest.main()
