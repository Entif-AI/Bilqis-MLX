from pathlib import Path
import json
import tempfile
import unittest

from bilqis_mlx.factory.autonomy import (
    EvidenceReceipt, initial_evidence_ledger, next_work, record_evidence,
)
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.factory.tests.support import synthetic_release_inputs
from bilqis_mlx.runtime.autonomy_state import (
    persist_autonomy_state, read_autonomy_state,
)


class DurableAutonomyStateTests(unittest.TestCase):
    def setUp(self):
        course, registry = synthetic_release_inputs()
        self.release = compile_factory_release(course, registry)

    def receipt(self, obligation, index=1):
        return EvidenceReceipt(
            obligation_id=obligation.obligation_id,
            evidence_id=f"evidence-{index}", checkpoint_sha256="e" * 64,
            optimizer_step=index, cohort_sha256=(hex(index)[2:] * 64)[:64],
            specimen_count=obligation.minimum_specimens, passed=True,
        )

    def test_persist_readback_and_restart_preserve_exact_plan_and_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ledger = initial_evidence_ledger(self.release)
            first = persist_autonomy_state(root, self.release, ledger=ledger)
            plan, restored = read_autonomy_state(root, self.release)
            self.assertEqual(restored, ledger)
            self.assertEqual(first["receipt_count"], 0)
            self.assertEqual(first["autonomy_plan_sha256"], plan.digest())

            work = next_work(self.release, restored, plan=plan)
            updated = record_evidence(
                self.release, restored, self.receipt(work.obligation), plan=plan)
            second = persist_autonomy_state(root, self.release, plan=plan, ledger=updated)
            _, restarted = read_autonomy_state(root, self.release)
            self.assertEqual(restarted, updated)
            self.assertEqual(second["receipt_count"], 1)
            self.assertNotEqual(first["state_file"], second["state_file"])
            self.assertTrue((root / first["state_file"]).is_file())
            self.assertTrue((root / second["state_file"]).is_file())

    def test_snapshot_tamper_is_detected_before_state_is_used(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            persist_autonomy_state(root, self.release,
                                   ledger=initial_evidence_ledger(self.release))
            pointer = json.loads((root / "autonomy/current.json").read_text())
            state = root / pointer["state_file"]
            payload = json.loads(state.read_text())
            payload["ledger"]["factory_release_sha256"] = "f" * 64
            state.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "AUTONOMY_STATE_DIGEST_DRIFT"):
                read_autonomy_state(root, self.release)

    def test_unsafe_autonomy_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as elsewhere:
            root = Path(temp)
            (root / "autonomy").symlink_to(Path(elsewhere), target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "AUTONOMY_UNSAFE_ARTIFACT_DIRECTORY"):
                persist_autonomy_state(root, self.release,
                                       ledger=initial_evidence_ledger(self.release))


if __name__ == "__main__":
    unittest.main()
