import json
from pathlib import Path
import unittest

from bilqis_mlx.runtime.delivery import load_conformance_record, load_manifest_record
from bilqis_mlx.runtime.delivery.publication import (
    published_boundary_record, published_conformance_record, published_manifest_record,
    published_roadmap_record,
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
        self.assertEqual(load_conformance_record(record).digest(),
                         record["conformance_sha256"])

    def test_conformance_rows_bind_concrete_owner_fixtures_not_generic_runner(self):
        record = published_conformance_record()
        for row in record["rows"]:
            if row["state"] not in {"BLOCKED", "REQUALIFICATION_REQUIRED"}:
                self.assertNotEqual(row["test_ref"], "scripts/run_tests.py")

    def test_checked_in_publication_exactly_matches_deterministic_projection(self):
        root = Path(__file__).resolve().parents[4]
        evidence = root / "docs" / "evidence" / "bamf" / "delivery"
        self.assertEqual(json.loads((evidence / "manifest.json").read_text()),
                         published_manifest_record())
        self.assertEqual(json.loads((evidence / "conformance.json").read_text()),
                         published_conformance_record())
        self.assertEqual(json.loads((evidence / "c15-2-evidence-boundary.json").read_text()),
                         published_boundary_record())
        self.assertEqual(json.loads((evidence / "roadmap-projection.json").read_text()),
                         published_roadmap_record())

    def test_boundary_is_public_safe_and_dependency_graph_is_explicit(self):
        boundary = published_boundary_record()
        self.assertEqual(boundary["dependency_graph"]["held_keys"], [])
        self.assertEqual(boundary["dependency_graph"]["node_count"], 215)
        self.assertIn("PRIVATE_REAL", boundary["source_privacy_boundary"]["protected_excluded"])
        self.assertEqual(boundary["cross_document_diff"]["disposition"],
                         "PASS_0_BLOCKERS_0_MAJORS_0_NITS")
        self.assertEqual(
            boundary["live_issue_parity"],
            "PASS_43_OWNERS_172_CHILDREN_190_NATIVE_EDGES_215_DAG_NODES")

    def test_roadmap_projects_exact_checkpoint_heads_without_completion_claims(self):
        record = published_roadmap_record()
        leaves = {row["issue"]: row for row in record["leaves"]}
        self.assertEqual(leaves[538]["head_sha"],
                         "030aa51d5e3f1e669648831cee2b7b340dab1c67")
        self.assertEqual(leaves[539]["head_sha"],
                         "96ec126f0a9a02d9e1adaafcdd5dbf859d6d1111")
        self.assertEqual(leaves[539]["status"], "DEVELOPMENT_RECEIPT")
        self.assertEqual(leaves[540]["status"], "DEVELOPMENT_RECEIPT_FACTORY_PASS")
        upstream = {row["issue"]: row for row in record["upstream"]}
        self.assertEqual(upstream[385]["status"], "ACCEPTED_RELEASE_SCOPED_INTEGRATION")
        self.assertEqual(upstream[386]["status"], "REVIEW_CLEAN_PENDING_HUMAN_PR_CHAIN")
        self.assertEqual(record["student_mastery_status"], "NOT_CLAIMED")


if __name__ == "__main__":
    unittest.main()
