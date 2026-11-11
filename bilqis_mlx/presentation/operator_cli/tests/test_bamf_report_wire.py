"""Exact C16.1a lifecycle report wire for every non-neural result."""
import unittest

from bilqis_mlx.presentation.operator_cli.bamf_lifecycle import SCHEMA, _report
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation
from bilqis_mlx.runtime.tests._bamf_first_student_support import BamfFirstStudentCase
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch


class BamfReportWireTests(BamfFirstStudentCase):
    def test_every_lifecycle_result_uses_the_exact_non_authorizing_wire(self):
        receipt = self.preflight(self.root / "report-source")
        identity = receipt.run_identity
        with shape_patch():
            student = load_bamf_generation(self.root / "report-source" / "bamf-state.json")
        topology = student.topology
        hp = AdamWHyperparameters(.0007, (.88, .97), 1e-7, .03)
        expected_keys = {
            "schema", "result", "run_id", "run_seed", "run_identity",
            "model_topology", "atlas_release_manifest", "admission_policy",
            "optimizer_hyperparameters", "source_prefetch_workers",
            "generation_manifest_sha256", "ready_for_training", "neural_updates",
        }
        for workers, result in enumerate((
                "READY_TO_CREATE", "CREATED", "READY_TO_RESUME", "ENROLLED")):
            workers = workers % 3
            report = _report(
                result=result, run_identity=identity, topology=topology,
                atlas=self.identity, policy="staged", hp=hp,
                source_prefetch_workers=workers, manifest_sha256="9" * 64)
            with self.subTest(result=result):
                self.assertEqual(set(report), expected_keys)
                self.assertEqual(report["schema"], SCHEMA)
                self.assertEqual(report["result"], result)
                self.assertEqual(report["run_identity"], identity.to_record())
                self.assertEqual(report["model_topology"], topology.to_record())
                self.assertEqual(report["atlas_release_manifest"], {
                    "sha256": self.identity.bundle_id,
                    "release_sha256": self.identity.release_sha256,
                    "source_bundle_id": self.identity.source_bundle_id,
                    "qualification": "A01_SOURCE_PINNED",
                })
                self.assertEqual(report["optimizer_hyperparameters"], {
                    "learning_rate": .0007, "betas": [.88, .97],
                    "eps": 1e-7, "weight_decay": .03,
                })
                self.assertEqual(report["source_prefetch_workers"], workers)
                self.assertFalse(report["ready_for_training"])
                self.assertEqual(report["neural_updates"], 0)


if __name__ == "__main__":
    unittest.main()
