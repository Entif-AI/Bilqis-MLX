"""CT-056 qualification receipt refuses partial or proxy evidence."""
from dataclasses import replace
import json
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.akasha_qualification import (
    AkashaQualificationReceipt,
    QualificationDataset,
    QualificationEnvironment,
    QualificationMeasurements,
    QualificationOutcomes,
)


ENVIRONMENT = QualificationEnvironment(
    platform="macOS-qualifier", machine="arm64", python="3.14",
    falkordb_client="1.8.0", redis_client="8.1.0",
    server_version="fixture-server", endpoint="127.0.0.1:16379")
DATASET = QualificationDataset(
    release_ref="release:fixture", canonical_rdf_sha256="1" * 64,
    canonical_triples=130173, bundle_manifest_sha256="2" * 64,
    suite_sha256="3" * 64, prior_live_proof_sha256="4" * 64)
MEASUREMENTS = QualificationMeasurements(
    rebuild_seconds=10.0, restore_seconds=8.0, idempotent_seconds=1.0,
    read_latency_ms=(1.0, 1.1, 1.2, 1.3, 1.4),
    nodes=67410, edges=130173, indexes=3,
    canonical_rdf_bytes=123456, backup_bytes=234567)
OUTCOMES = QualificationOutcomes(
    backup_restore_identity_match=True,
    backup_restore_census_match=True,
    backup_restore_query_match=True,
    clean_rebuild_match=True,
    stale_detected=True,
    corruption_detected=True,
    partial_recovery=True,
    foreign_isolation=True,
    restart_reconnect=True,
    logical_domain_isolation=True)


def _receipt(**changes):
    values = {
        "candidate_revision": "a" * 40,
        "environment": ENVIRONMENT,
        "dataset": DATASET,
        "measurements": MEASUREMENTS,
        "outcomes": OUTCOMES,
        "prerequisite_heads": (("#301", "b" * 40), ("#302", "c" * 40)),
        "commands": ("python -m qualifier --fixture",),
        "residual_debt": ("server-process restart remains a separate provider drill",),
    }
    values.update(changes)
    return AkashaQualificationReceipt.create(**values)


class AkashaQualificationReceiptTests(unittest.TestCase):
    def test_complete_receipt_is_deterministic_and_content_addressed(self):
        first = _receipt()
        second = _receipt()
        self.assertEqual(first, second)
        self.assertEqual(first.status, "PASSED")
        self.assertEqual(first.receipt_sha256, second.receipt_sha256)
        stored = json.loads(first.canonical_json)
        self.assertEqual(stored["receipt_sha256"], first.receipt_sha256)
        self.assertEqual(stored["measurements"]["read_latency_p50_ms"], 1.2)
        self.assertEqual(stored["measurements"]["read_latency_p95_ms"], 1.4)

    def test_any_missing_required_fault_or_recovery_outcome_refuses_pass(self):
        for field in OUTCOMES.to_record():
            with self.subTest(field=field), self.assertRaises(BilqisError):
                _receipt(outcomes=replace(OUTCOMES, **{field: False}))

    def test_noncomparable_or_growth_measurements_refuse_pass(self):
        cases = (
            {"read_latency_ms": (1.0, 2.0)},
            {"rebuild_seconds": 0.0},
            {"idempotent_node_growth": 1},
            {"backup_bytes": 0},
        )
        for changes in cases:
            with self.subTest(changes=changes), self.assertRaises(BilqisError):
                _receipt(measurements=replace(MEASUREMENTS, **changes))

    def test_prerequisite_and_candidate_identity_are_exact_not_labels_only(self):
        for changed in (
            {"candidate_revision": "latest"},
            {"prerequisite_heads": (("#301", "not-a-sha"),)},
            {"prerequisite_heads": (("#301", "b" * 40), ("#301", "c" * 40))},
        ):
            with self.subTest(changed=changed), self.assertRaises(BilqisError):
                _receipt(**changed)


if __name__ == "__main__":
    unittest.main()
