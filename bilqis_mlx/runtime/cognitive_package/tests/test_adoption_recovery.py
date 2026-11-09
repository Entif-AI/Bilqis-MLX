"""C12 adoption failure, retry, and parent-authority regressions."""
from dataclasses import replace
from hashlib import sha256
import json
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation, publication
from bilqis_mlx.runtime.bamf_bundle.records import canonical
from bilqis_mlx.runtime.cognitive_package import publish_screened_delta_import
from bilqis_mlx.runtime.cognitive_package.tests.adoption_harness import AdoptionHarness
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state, candidate, publish_candidate, shape_patch,
)


class PackageImportAdoptionRecoveryTests(AdoptionHarness):
    def test_stale_screened_parent_fails_after_intervening_generation(self):
        screened, receipt = self.screened()
        advanced = accepted_state(
            self.state, self.initial.extents, spec=self.initial.topology)
        successor = candidate(advanced, 1, self.pointer["manifest_sha256"])
        successor = replace(
            successor, provenance=self.initial.provenance,
            correction_frontier=self.initial.correction_frontier)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            newer = publish_candidate(self.run, successor)
        with self.assertRaises(BilqisError):
            self.adopt(screened, receipt)
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["manifest_sha256"], newer["manifest_sha256"])

    def test_crash_before_pointer_preserves_parent_and_retry_converges(self):
        screened, receipt = self.screened()
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                patch.object(publication, "_atomic_pointer", side_effect=RuntimeError("crash")):
            with self.assertRaisesRegex(RuntimeError, "crash"):
                publish_screened_delta_import(
                    screened, self.run, export_clearance=receipt,
                    atlas_selection=self.selection, source_frontier=self.frontier,
                    source_context=self.source_context())
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["manifest_sha256"], self.pointer["manifest_sha256"])

        published = self.adopt(screened, receipt)
        self.assertEqual(published["parent_manifest_sha256"], self.pointer["manifest_sha256"])
        with shape_patch():
            loaded = load_bamf_generation(self.run / "bamf-state.json")
        self.assertEqual(loaded.generation, self.initial.generation + 1)
        self.assertEqual(loaded.transition["package_sha256"], screened.candidate.package.digest)

    def test_missing_parent_acceptance_cannot_authorize_package_import(self):
        screened, receipt = self.screened()
        self.parent_acceptance_path().unlink()
        with self.assertRaises(BilqisError):
            self.adopt(screened, receipt)
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["manifest_sha256"], self.pointer["manifest_sha256"])

    def test_resigned_parent_acceptance_drift_cannot_authorize_package_import(self):
        screened, receipt = self.screened()
        path = self.parent_acceptance_path()
        record = json.loads(path.read_text())
        record["optimizer_step"] += 1
        record["binding_sha256"] = sha256(canonical({
            key: value for key, value in record.items()
            if key != "binding_sha256"
        })).hexdigest()
        path.write_text(json.dumps(record))
        with self.assertRaises(BilqisError):
            self.adopt(screened, receipt)
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["manifest_sha256"], self.pointer["manifest_sha256"])
