"""Cold replay tests for persistent BAMF multi-fidelity shadow evidence."""
from pathlib import Path
from tempfile import TemporaryDirectory

from bilqis_mlx.factory.teaching import content_digest
from bilqis_mlx.runtime.bamf_operator.evidence_parts import prepare_candidate_evidence_root
from bilqis_mlx.runtime.bamf_operator.evidence_parts.validation import read_candidate_horizon_evidence
from bilqis_mlx.runtime.tests.operator.candidate_evidence_test_support import (
    CandidateEvidenceTestCase,
)


class CandidateMultifidelityEvidenceTests(CandidateEvidenceTestCase):
    def test_shadow_trace_cold_replays_rungs_and_final_truth(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepare_candidate_evidence_root(root)
            capture = self.capture(root)
            capture.configure_multifidelity(
                full_budget_steps=12, rungs=(2, 4, 8, 12),
                policy_version="teacher-multifidelity-shadow/v2",
                minimum_target_delta_to_continue=1, minimum_decision_step=8)
            row = {
                "id": "row:one", "capability": "capability:evidence",
                "tokens": [1, 2, 3],
            }
            deltas = {2: 0, 4: 0, 8: 0, 12: 2}
            for ordinal in range(1, 13):
                capture.delivery(
                    self.release(), "capability:evidence", 10 + ordinal,
                    (row, row), option_rows=(row,), priority=(row,), seed=ordinal,
                    controls={
                        "realized_cost": {
                            "candidate_step_wall_seconds": 1.0,
                            "optimizer_steps": 1,
                            "candidate_optimizer_steps": ordinal,
                        },
                        "delivered_content_sha256": content_digest((row, row)),
                    })
                if ordinal in deltas:
                    capture.record_multifidelity_rung(
                        step=ordinal,
                        target_probe={
                            "schema": "bilqis.bamf.multifidelity-target-sentinel/v1",
                            "parent_correct": 3,
                            "candidate_correct": 3 + deltas[ordinal],
                            "total": 6,
                            "target_correct_delta": deltas[ordinal],
                            "actual_authority_changed": False,
                        },
                        probe_wall_seconds=0.25)

            receipt = capture.finalize(
                accepted=True, decision={"decision": "ACCEPTED"})
            shadow = read_candidate_horizon_evidence(
                root, receipt)["multifidelity_shadow"]

            self.assertEqual(shadow["status"], "COMPLETE")
            self.assertEqual([rung["step"] for rung in shadow["rungs"]], [2, 4, 8, 12])
            self.assertEqual(
                [rung["controller_recommendation"] for rung in shadow["rungs"]],
                ["OBSERVE", "OBSERVE", "WOULD_STOP", "WOULD_CONTINUE"])
            self.assertTrue(all(
                rung["predicted_retention"]["status"] == "NOT_MEASURED"
                and rung["uncertainty"]["status"] == "NOT_MEASURED"
                and rung["bounded_preservation_sentinel"]["status"] == "NOT_MEASURED"
                for rung in shadow["rungs"]))
            self.assertEqual(shadow["review"]["first_would_stop_step"], 8)
            self.assertTrue(shadow["review"]["false_kill"])
            self.assertTrue(shadow["review"]["retained_would_kill"])
            self.assertEqual(
                shadow["review"]["projected_candidate_wall_saved_seconds"], 4.0)
            self.assertEqual(
                shadow["review"]["projected_probe_wall_saved_seconds"], 0.25)
            self.assertEqual(shadow["activation"]["status"], "NOT_QUALIFIED")
            self.assertFalse(shadow["activation"]["authority_changed"])
            self.assertEqual(
                shadow["review"]["retentions_per_hour_effect"]["status"],
                "NOT_MEASURED")
