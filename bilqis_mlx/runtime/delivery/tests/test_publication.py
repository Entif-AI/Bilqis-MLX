import json
from pathlib import Path
import unittest

from bilqis_mlx.runtime.delivery import load_manifest_record
from bilqis_mlx.runtime.delivery.publication import (
    published_boundary_record, published_conformance_record, published_manifest_record,
)


class DeliveryPublicationTests(unittest.TestCase):
    def test_manifest_pins_required_delivery_components_without_claiming_mastery(self):
        record = published_manifest_record()
        manifest = load_manifest_record(record)
        components = {item.component_id: item for item in manifest.components}
        for name in ("semantic-release", "factory-head", "teacher-head", "topology",
                     "compiler", "plasticity", "codec", "delivery-tests", "architecture",
                     "workstack"):
            self.assertIn(name, components)
        self.assertEqual(manifest.software_delivery_status, "IN_PROGRESS")
        self.assertEqual(manifest.student_mastery_status, "NOT_CLAIMED")

    def test_conformance_projection_is_complete_and_keeps_known_gaps_visible(self):
        record = published_conformance_record()
        rows = {row["claim_id"]: row for row in record["rows"]}
        self.assertEqual(len(rows), 44)
        self.assertEqual(rows["BAMF-REQ-024"]["state"], "BLOCKED")
        self.assertEqual(rows["F15"]["state"], "REQUALIFICATION_REQUIRED")
        self.assertEqual(rows["F20"]["state"], "BLOCKED")
        gates = {gate["gate_id"]: gate for gate in record["failure_gates"]}
        self.assertEqual(set(gates), {
            "GRADE_NEUTRAL_INVARIANCE", "NO_LEGACY_BAV_RUNTIME_NAMESPACE"})
        self.assertEqual(gates["GRADE_NEUTRAL_INVARIANCE"]["state"], "CODE_PRESENT")
        self.assertEqual(record["software_delivery_status"], "IN_PROGRESS")
        self.assertEqual(record["student_mastery_status"], "NOT_CLAIMED")

    def test_checked_in_publication_exactly_matches_deterministic_projection(self):
        root = Path(__file__).resolve().parents[4]
        evidence = root / "docs" / "evidence" / "bamf" / "delivery"
        self.assertEqual(json.loads((evidence / "manifest.json").read_text()),
                         published_manifest_record())
        self.assertEqual(json.loads((evidence / "conformance.json").read_text()),
                         published_conformance_record())
        self.assertEqual(json.loads((evidence / "c15-2-evidence-boundary.json").read_text()),
                         published_boundary_record())

    def test_boundary_is_public_safe_and_dependency_graph_is_explicit(self):
        boundary = published_boundary_record()
        self.assertEqual(boundary["dependency_graph"]["held_keys"], [])
        self.assertEqual(boundary["dependency_graph"]["executable_order_length"], 215)
        self.assertIn("PRIVATE_REAL", boundary["source_privacy_boundary"]["protected_excluded"])
        self.assertEqual(boundary["cross_document_diff"]["normative_conflicts"], [])


if __name__ == "__main__":
    unittest.main()
