from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
import csv
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.mapping_admission import (
    ABSENT,
    COMMENTARY_FIELDS,
    KEY_FIELDS,
    AdmissionRule,
    PolicyTable,
    coverage_report,
    decide_normalized,
    decide_row,
    load_policy,
    mapping_key,
    validate_policy,
)


CORPUS_ROOT = ITHKUIL_ROOT
FIXTURE_ROOT = FIXTURES
TABLE_PATH = CORPUS_ROOT / "src/skos/mapping_admission_table.json"
REPORT_PATH = FIXTURE_ROOT / "skos_mapping_admission_coverage.json"


class MappingAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.table = load_policy(TABLE_PATH)
        data = CORPUS_ROOT / "_data/csv"
        with (data / "bilqis_ithkuil_crosswalk.csv").open(newline="", encoding="utf-8") as handle:
            cls.crosswalk = list(csv.DictReader(handle))
        with (data / "bilqis_semantic_bridges.csv").open(newline="", encoding="utf-8") as handle:
            cls.bridges = list(csv.DictReader(handle))

    def assert_code(self, code, callable_, *args, **kwargs):
        with self.assertRaises(ProfileError) as caught:
            callable_(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)

    def test_literal_schema_has_no_wildcards_or_commentary_keys(self):
        raw = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(tuple(raw["key_fields"]), KEY_FIELDS)
        self.assertEqual(raw["normalized_caution_dimensions"], [])
        self.assertEqual(set(raw["commentary_excluded"]), COMMENTARY_FIELDS)
        self.assertEqual(len(raw["rules"]), 39)
        for rule in raw["rules"]:
            self.assertEqual(tuple(rule["key"]), KEY_FIELDS)
            self.assertFalse(any(value in {"*", "ANY", "__ANY__"} for value in rule["key"].values()))
            self.assertTrue(COMMENTARY_FIELDS.isdisjoint(rule["key"]))

    def test_current_552_rows_have_exact_literal_coverage(self):
        report = coverage_report(self.crosswalk, self.bridges, self.table)
        expected = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        self.assertEqual(report, expected)
        self.assertEqual(report["rows"], {"crosswalk": 222, "bridge": 330, "total": 552})
        self.assertEqual(report["unique_policy_keys"], {"crosswalk": 13, "bridge": 26, "total": 39})
        self.assertEqual(report["outcomes"], {"HOLD": 551, "REJECT": 1})

    def test_current_rows_never_emit_and_approved_strategy_is_not_mapping_admission(self):
        decisions = [decide_row("crosswalk", row, self.table) for row in self.crosswalk]
        decisions += [decide_row("bridge", row, self.table) for row in self.bridges]
        self.assertFalse(any(decision.emitting for decision in decisions))
        for row in self.crosswalk:
            if row["mapping_disposition"].startswith("APPROVED_"):
                decision = decide_row("crosswalk", row, self.table)
                self.assertEqual(
                    (decision.outcome, decision.reason_code),
                    ("HOLD", "MAPPING_STRATEGY_NOT_SEMANTIC_ADMISSION_HELD"),
                )

    def test_rejected_historical_proposal_blocked_and_deferred_are_nonemitting(self):
        rejected = next(row for row in self.crosswalk if row["equivalence_state"] == "rejected_exact_equivalence")
        self.assertEqual(
            (decide_row("crosswalk", rejected, self.table).outcome,
             decide_row("crosswalk", rejected, self.table).reason_code),
            ("REJECT", "MAPPING_REJECTED_EXACT_EQUIVALENCE"),
        )
        expected = {
            "historical_only": "MAPPING_HISTORICAL_ONLY_HELD",
            "proposal": "MAPPING_PROPOSAL_HELD",
            "blocked": "MAPPING_BLOCKED_HELD",
            "deferred": "MAPPING_DEFERRED_HELD",
        }
        for state, reason in expected.items():
            row = next(row for row in self.bridges if row["bridge_epistemic_state"] == state)
            decision = decide_row("bridge", row, self.table)
            self.assertEqual((decision.outcome, decision.reason_code), ("HOLD", reason))

    def test_unknown_future_state_and_zero_match_fail_closed(self):
        row = dict(self.crosswalk[0])
        row["crosswalk_state"] = "FUTURE_UNREVIEWED_STATE"
        decision = decide_row("crosswalk", row, self.table)
        self.assertEqual((decision.outcome, decision.reason_code),
                         ("UNSUPPORTED", "MAPPING_POLICY_NO_MATCH"))

    def test_duplicate_table_rule_and_multiple_runtime_matches_fail_closed(self):
        duplicate = self.table.rules[0]
        bad = replace(self.table, rules=self.table.rules + (duplicate,))
        self.assert_code("MAPPING_POLICY_DUPLICATE_RULE", validate_policy, bad)
        record_kind = duplicate.key[0]
        rows = self.crosswalk if record_kind == "crosswalk" else self.bridges
        row = next(row for row in rows if mapping_key(record_kind, row) == duplicate.key)
        self.assert_code("MAPPING_POLICY_MULTIPLE_MATCHES", decide_row, record_kind, row, bad)

    def test_shuffled_rows_and_commentary_edits_do_not_change_report(self):
        baseline = coverage_report(self.crosswalk, self.bridges, self.table)
        crosswalk = [dict(row) for row in reversed(self.crosswalk)]
        bridges = [dict(row) for row in reversed(self.bridges)]
        for row in crosswalk:
            row["semantic_differential"] = "COMMENTARY EDIT MUST NOT CHANGE POLICY"
            row["bilqis_source_definition"] = "another prose edit"
        for row in bridges:
            row["semantic_caution_or_dependencies"] = "COMMENTARY EDIT MUST NOT CHANGE POLICY"
            row["source_grounded_semantic_meaning"] = "another prose edit"
        self.assertEqual(coverage_report(crosswalk, bridges, self.table), baseline)

    def test_all_five_emit_outcomes_exist_only_as_synthetic_normalized_admissions(self):
        expected = {
            ("exactMatch", "admitted_exact_equivalence"): "EMIT_EXACT",
            ("closeMatch", "admitted_close_match"): "EMIT_CLOSE",
            ("broadMatch", "admitted_broad_match"): "EMIT_BROAD",
            ("narrowMatch", "admitted_narrow_match"): "EMIT_NARROW",
            ("relatedMatch", "admitted_related_match"): "EMIT_RELATED",
        }
        self.assertEqual(
            {(item.predicate, item.review_state): item.outcome for item in self.table.normalized_admissions},
            expected,
        )
        for key, outcome in expected.items():
            decision = decide_normalized(*key, self.table)
            self.assertEqual((decision.outcome, decision.reason_code), (outcome, None))
        unsupported = decide_normalized("exactMatch", "APPROVED_TYPED_FORMAL_ADAPTER", self.table)
        self.assertEqual(
            (unsupported.outcome, unsupported.reason_code),
            ("UNSUPPORTED", "MAPPING_NORMALIZED_STATE_UNSUPPORTED"),
        )

    def test_table_has_no_raw_emitting_rules_and_no_concept_targets_currently(self):
        self.assertFalse(any(rule.outcome.startswith("EMIT_") for rule in self.table.rules))
        self.assertEqual({row["target_kind"] for row in self.crosswalk}, {"source_document", "source_section"})
        self.assertEqual(
            {row["target_kind"] for row in self.bridges},
            {"source_document", "source_section", "historical_source"},
        )

    def test_missing_required_key_field_fails_closed(self):
        row = dict(self.crosswalk[0])
        del row["source_match_state"]
        self.assert_code("MAPPING_POLICY_INPUT_FIELD_MISSING", decide_row, "crosswalk", row, self.table)

    def test_absent_dimensions_are_explicit_not_wildcards(self):
        bridge_key = mapping_key("bridge", self.bridges[0])
        values = dict(zip(KEY_FIELDS, bridge_key))
        self.assertEqual(values["equivalence_state"], ABSENT)
        self.assertEqual(values["mapping_disposition"], ABSENT)

    def test_policy_object_key_order_is_not_semantic(self):
        raw = json.loads(TABLE_PATH.read_text())
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "sorted.json"
            path.write_text(json.dumps(raw, sort_keys=True))
            self.assertEqual(load_policy(path), self.table)

    def test_policy_cannot_admit_source_document_or_historical_target(self):
        raw = json.loads(TABLE_PATH.read_text())
        raw["rules"][0]["outcome"] = "EMIT_EXACT"
        raw["rules"][0]["reason_code"] = None
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "invalid.json"
            path.write_text(json.dumps(raw))
            self.assert_code("MAPPING_POLICY_UNSAFE_EMIT_RULE", load_policy, path)

    def test_normalized_policy_cannot_relabel_close_as_exact(self):
        raw = json.loads(TABLE_PATH.read_text())
        row = next(row for row in raw["synthetic_normalized_admissions"] if row["predicate"] == "closeMatch")
        row["outcome"] = "EMIT_EXACT"
        with tempfile.TemporaryDirectory() as tempdir:
            path = Path(tempdir) / "invalid.json"
            path.write_text(json.dumps(raw))
            self.assert_code("MAPPING_NORMALIZED_STRENGTH_MISMATCH", load_policy, path)


if __name__ == "__main__":
    unittest.main()
