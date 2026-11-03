"""C12 accepted imports cross B12 custody and B13 publication exactly once."""
from dataclasses import replace
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import publication
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation, publish_bamf_generation
from bilqis_mlx.runtime.cognitive_package import (
    DeltaSlice, PackageArtifact, PackageBinding, PackageKind, ReceiverTensor, SourceRights,
    apply_plastic_delta, encode_plastic_delta, export_capability,
    publish_screened_delta_import, receiver_parameter_schema_digest,
    receiver_weight_digest, screen_delta_candidate,
)
from bilqis_mlx.runtime.cognitive_package.tests.fixtures import snapshot
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import _screen_inputs
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    NAME, accepted_state, candidate, parent_state, shape_patch,
)
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_release_audit import ExportClearanceReceipt
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.semantics.context_eligibility import SourceFrontier
from bilqis_mlx.semantics.domains import contract_digest


PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("29" * 32))
PUBLIC = PRIVATE.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
OWNER = "fixture:a12-source-owner"
REGISTRY = SourceAuthorityRegistry((SourceAuthorityKey(
    OWNER, PUBLIC, (SourceAuthorityScope(DependencyKind.ARTIFACT, "a12-export:"),)),))


def _selection():
    path = Path(__file__).resolve().parents[3] / "semantics" / "atlas_source_pins_v1.json"
    entry = json.loads(path.read_text())["entries"][0]
    return AtlasArtifactSelection(
        "fixture-atlas", entry["bundle_id"], entry["release_sha256"],
        entry["source_bundle_id"])


def _receipt(selection, frontier, artifacts):
    value = ExportClearanceReceipt(
        OWNER, selection.bundle_id, selection.release_sha256, selection.source_bundle_id,
        contract_digest(frontier), frontier.rights_epoch, frontier.correction_generation,
        artifacts, (), (), (), "0" * 128)
    return replace(value, signature_hex=PRIVATE.sign(value.signing_bytes()).hex())


class PackageImportAdoptionTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.run = self.root / "run"
        self.selection = _selection()
        self.frontier = SourceFrontier(2, 4, ())
        self.state = parent_state()
        base = candidate(self.state)
        self.initial = replace(
            base,
            provenance=replace(base.provenance, release_digest=self.selection.release_sha256),
            correction_frontier={**base.correction_frontier,
                                 "release_digest": self.selection.release_sha256})
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            self.pointer = publish_bamf_generation(self.run, self.initial)
        array = np.asarray(self.state.optimizer.parameters[NAME], dtype="<f4")
        self.tensor = ReceiverTensor(NAME, array.shape, array.tobytes())
        self.binding = PackageBinding(
            receiver_weight_digest((self.tensor,)), receiver_parameter_schema_digest((self.tensor,)),
            self.initial.topology.digest, self.selection.release_sha256,
            self.initial.extents.active_semantic_digest, self.initial.extents.factor_map_digest,
            self.initial.extents.motif_key_map_digest)

    def package_and_clearance(self):
        source, _ = snapshot(PackageKind.WEIGHT_DELTA)
        parent = np.frombuffer(self.tensor.values_fp32, dtype="<f4")
        payload = encode_plastic_delta((DeltaSlice(
            NAME, 0, 1, sha256(parent[:1].tobytes()).hexdigest(),
            np.asarray([.5], dtype="<f4").tobytes()),))
        artifact = PackageArtifact("weights", PackageKind.WEIGHT_DELTA, payload)
        source = replace(source, binding=self.binding, artifacts=(artifact,) + source.artifacts[1:])
        artifacts = tuple(sorted(item.digest for item in source.artifacts))
        receipt = _receipt(self.selection, self.frontier, artifacts)
        rights = SourceRights(OWNER, receipt.clearance_sha256, artifacts, (), ())
        return export_capability(source, source.signature, rights), receipt

    def screened(self, *, protected_loss=2):
        package, receipt = self.package_and_clearance()
        with shape_patch():
            disposable = apply_plastic_delta(package, self.run)
        inputs = _screen_inputs(protected_loss)
        screened = screen_delta_candidate(
            disposable, parent_solver=inputs[0], candidate_solver=inputs[1],
            target_capability=inputs[2], policy=inputs[3], cohorts=inputs[4])
        return screened, receipt

    def adopt(self, screened, receipt):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_screened_delta_import(
                screened, self.run, export_clearance=receipt,
                atlas_selection=self.selection, source_frontier=self.frontier,
                authority_registry=REGISTRY)

    def test_eligible_import_resets_receiver_state_and_publishes_lineage(self):
        screened, receipt = self.screened()
        published = self.adopt(screened, receipt)
        with shape_patch():
            loaded = load_bamf_generation(self.run / "bamf-state.json")

        self.assertEqual(loaded.generation, 1)
        self.assertEqual(loaded.retained_state.optimizer_step, 11)
        self.assertEqual(loaded.retained_state.policy.mode, "ADAPTIVE")
        self.assertEqual(loaded.retained_state.policy.accepted_fast_since_full, 0)
        self.assertEqual(tuple(row.accepted_age for row in loaded.retained_state.policy.row_ages), (0, 2))
        self.assertEqual(np.asarray(loaded.retained_state.optimizer.parameters[NAME])[0, 0], 1.)
        self.assertEqual(np.asarray(loaded.retained_state.optimizer.m[NAME])[0, 0], 0.)
        self.assertEqual(np.asarray(loaded.retained_state.optimizer.v[NAME])[0, 0], 0.)
        np.testing.assert_array_equal(
            np.asarray(loaded.retained_state.optimizer.update_counts[NAME]), [0, 3])
        self.assertEqual(loaded.transition["kind"], "PACKAGE_IMPORT")
        self.assertEqual(loaded.transition["package_sha256"], screened.candidate.package.digest)
        self.assertEqual(loaded.transition["source_clearance_sha256"], receipt.clearance_sha256)
        self.assertEqual(loaded.outbox[0]["origin"], "PACKAGE_IMPORT")
        self.assertEqual(loaded.outbox[0]["receiver_manifest_sha256"], self.pointer["manifest_sha256"])
        self.assertEqual(published["parent_manifest_sha256"], self.pointer["manifest_sha256"])

    def test_reject_or_eligible_label_alone_cannot_publish(self):
        rejected, receipt = self.screened(protected_loss=3)
        self.assertEqual(rejected.decision.status, "REJECT")
        with self.assertRaises(BilqisError):
            self.adopt(rejected, receipt)
        eligible, receipt = self.screened()
        for forged in (True, eligible.decision):
            with self.subTest(forged=type(forged).__name__), self.assertRaises(BilqisError):
                self.adopt(forged, receipt)
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["manifest_sha256"], self.pointer["manifest_sha256"])

    def test_current_a12_clearance_is_required(self):
        screened, receipt = self.screened()
        forged = replace(receipt, signature_hex="0" * 128)
        with self.assertRaises(BilqisError):
            self.adopt(screened, forged)
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["manifest_sha256"], self.pointer["manifest_sha256"])

    def test_stale_screened_parent_fails_after_intervening_generation(self):
        screened, receipt = self.screened()
        advanced = accepted_state(self.state)
        successor = candidate(advanced, 1, self.pointer["manifest_sha256"])
        successor = replace(
            successor, provenance=self.initial.provenance,
            correction_frontier=self.initial.correction_frontier)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            newer = publish_bamf_generation(self.run, successor)
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
                    authority_registry=REGISTRY)
        pointer = json.loads((self.run / "bamf-state.json").read_text())
        self.assertEqual(pointer["manifest_sha256"], self.pointer["manifest_sha256"])

        published = self.adopt(screened, receipt)
        self.assertEqual(published["parent_manifest_sha256"], self.pointer["manifest_sha256"])
        with shape_patch():
            loaded = load_bamf_generation(self.run / "bamf-state.json")
        self.assertEqual(loaded.generation, 1)
        self.assertEqual(loaded.transition["package_sha256"], screened.candidate.package.digest)


if __name__ == "__main__":
    import unittest
    unittest.main()
