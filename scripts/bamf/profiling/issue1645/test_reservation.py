"""Positive and negative controls for a research-only reserved source scope."""
import copy
import unittest

from scripts.bamf.profiling.issue1645.reservation import (
    BINDINGS, CAPABILITIES, GOLD, ROWS_PER_GOLD, audit, digest, prepare,
    require_allowed, semantic_key, witness_key,
)


def fixture():
    rows = []
    for cap in CAPABILITIES:
        for gold in GOLD:
            for i in range(ROWS_PER_GOLD):
                row = {"capability": cap, "gold": gold,
                       "tokens": [gold, i], "answer_kind": "PREDICATE"}
                rows.append({"row": row, "semantic_key": semantic_key(row),
                             "row_key": witness_key(row, gold)})
    return {**{field: "fixture" for field in BINDINGS},
            "prospective": {
                "status": "PREPARED_NOT_ISSUED_NOT_INDEPENDENT_UNTIL_EXCLUSION_ENFORCED",
                "count": len(rows), "rows": rows, "sha256": digest(rows)}}


class ReservationTests(unittest.TestCase):
    def test_frozen_input_includes_both_labels(self):
        source = fixture()
        reservation = prepare(source)
        row = source["prospective"]["rows"][0]["row"]
        self.assertEqual(len(reservation["semantic_keys"]), 72)
        self.assertEqual(len(reservation["excluded_witness_keys"]), 144)
        alternative = {**row, "gold": "FALSE", "id": "different"}
        with self.assertRaisesRegex(ValueError, "reserved assessment input"):
            require_allowed(reservation, [alternative], reservation["bindings"])
        require_allowed(reservation, [{**row, "tokens": ["new"]}],
                        reservation["bindings"])
        result = audit(reservation, [{"row_keys": [witness_key(row, "FALSE")]}],
                       reservation["bindings"])
        self.assertEqual(result["status"], "OVERLAP")
        self.assertEqual(result["overlap_witness_keys"], 1)
        self.assertFalse(result["independence_certified"])

    def test_no_overlap_is_not_certification(self):
        reservation = prepare(fixture())
        result = audit(reservation, [{"row_keys": ["unrelated"]}],
                       reservation["bindings"])
        self.assertEqual(result["status"], "NO_OVERLAP_IN_SUPPLIED_RECEIPTS")
        self.assertFalse(result["independence_certified"])
        self.assertEqual(reservation["status"], "PREPARED_NOT_APPROVED_NOT_ISSUED")

    def test_digest_and_source_binding_fail_closed(self):
        source = fixture()
        reservation = prepare(source)
        source["prospective"]["rows"][0]["row"]["gold"] = "FALSE"
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            prepare(source)
        with self.assertRaisesRegex(ValueError, "binding mismatch"):
            require_allowed(reservation, [], {**reservation["bindings"],
                                              "generator_version": "new"})
        changed = copy.deepcopy(reservation)
        changed["semantic_keys"].pop()
        with self.assertRaisesRegex(ValueError, "reservation digest mismatch"):
            audit(changed, [], changed["bindings"])

    def test_incomplete_and_duplicate_inputs_fail_closed(self):
        source = fixture()
        cohort = source["prospective"]
        cohort["rows"].pop()
        cohort["count"] -= 1
        cohort["sha256"] = digest(cohort["rows"])
        with self.assertRaisesRegex(ValueError, "incomplete"):
            prepare(source)
        source = fixture()
        cohort = source["prospective"]
        cohort["rows"][-1] = copy.deepcopy(cohort["rows"][0])
        cohort["sha256"] = digest(cohort["rows"])
        with self.assertRaisesRegex(ValueError, "duplicate"):
            prepare(source)


if __name__ == "__main__":
    unittest.main()
