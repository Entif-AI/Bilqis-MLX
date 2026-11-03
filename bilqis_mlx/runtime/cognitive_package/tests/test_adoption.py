"""Accepted C12 package imports commit only through A12/C05/B12/B13 owners."""
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
import mlx.core as mx
import numpy as np

from bilqis_mlx.data_plane import close_data_planes
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import begin_candidate, candidate_step, resolve_candidate
from bilqis_mlx.learning.atlas_package_import import ImportResetSlice, begin_package_import
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.bamf_bundle import (
    BamfBundleCandidate, load_bamf_generation, publication, publish_bamf_generation,
)
import bilqis_mlx.runtime.bamf_bundle.codec as codec
from bilqis_mlx.runtime.capability_retention import DecisionStatus
from bilqis_mlx.runtime.cognitive_package import (
    DeltaSlice, PackageArtifact, PackageBinding, PackageKind, ReceiverTensor,
    SourceRights, adopt_screened_delta, apply_plastic_delta, encode_plastic_delta,
    export_capability, receiver_parameter_schema_digest, receiver_weight_digest,
    screen_delta_candidate,
)
from bilqis_mlx.runtime.cognitive_package.tests.fixtures import snapshot
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import _screen_inputs
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    HP, NAME, accepted_state, candidate, parent_state, shape_patch,
)
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_release_audit import ExportClearanceReceipt
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.semantics.context_eligibility import SourceFrontier
from bilqis_mlx.semantics.domains import contract_digest


PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("31" * 32))
PUBLIC = PRIVATE.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
OWNER = "fixture:c12-export-owner"


def _selection():
    path = Path(__file__).resolve().parents[3] / "semantics" / "atlas_source_pins_v1.json"
    entry = json.loads(path.read_text())["entries"][0]
    return AtlasArtifactSelection(
        "fixture-atlas", entry["bundle_id"], entry["release_sha256"],
        entry["source_bundle_id"])


class PackageAdoptionTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(close_data_planes)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.run = self.root / "run"
        self.selection = _selection()
        base = candidate(parent_state())
        provenance = replace(base.provenance, release_digest=self.selection.release_sha256)
        correction = {**base.correction_frontier, "release_digest": self.selection.release_sha256}
        self.base = replace(base, provenance=provenance, correction_frontier=correction)
        with shape_patch(), self._headroom(), patch.object(codec, "assert_headroom"):
            self.pointer = publish_bamf_generation(self.run, self.base)
        array = np.asarray(self.base.retained_state.optimizer.parameters[NAME], dtype="<f4")
        self.tensor = ReceiverTensor(NAME, array.shape, array.tobytes())
        self.binding = PackageBinding(
            receiver_weight_digest((self.tensor,)), receiver_parameter_schema_digest((self.tensor,)),
            self.base.topology.digest, self.selection.release_sha256,
            self.base.extents.active_semantic_digest, self.base.extents.factor_map_digest,
            self.base.extents.motif_key_map_digest)
        self.frontier = SourceFrontier(2, 4, ())
        self.registry = SourceAuthorityRegistry((SourceAuthorityKey(
            OWNER, PUBLIC, (SourceAuthorityScope(DependencyKind.ARTIFACT, "a12-export:"),)),))

    def _headroom(self):
        return patch.object(mlx_checkpoint, "assert_headroom")

    def package_and_clearance(self, *, rights_clearance=None):
        source, unused = snapshot(PackageKind.WEIGHT_DELTA)
        values = np.frombuffer(self.tensor.values_fp32, dtype="<f4")
        delta = np.asarray((.5, -.5), dtype="<f4").tobytes()
        artifact = PackageArtifact(
            "weights", PackageKind.WEIGHT_DELTA,
            encode_plastic_delta((DeltaSlice(
                NAME, 0, 2, sha256(values[:2].tobytes()).hexdigest(), delta),)))
        source = replace(source, binding=self.binding, artifacts=(artifact,) + source.artifacts[1:])
        exported = tuple(sorted(value.digest for value in source.artifacts))
        receipt = ExportClearanceReceipt(
            OWNER, self.selection.bundle_id, self.selection.release_sha256,
            self.selection.source_bundle_id, contract_digest(self.frontier),
            self.frontier.rights_epoch, self.frontier.correction_generation,
            exported, (), (), (), "0" * 128)
        receipt = replace(receipt, signature_hex=PRIVATE.sign(receipt.signing_bytes()).hex())
        rights = SourceRights(
            OWNER, rights_clearance or receipt.clearance_sha256, exported, (), ())
        return export_capability(source, source.signature, rights), receipt

    def screened(self, *, reject=False, rights_clearance=None):
        package, receipt = self.package_and_clearance(rights_clearance=rights_clearance)
        with shape_patch():
            disposable = apply_plastic_delta(package, self.run)
        inputs = _screen_inputs(3 if reject else 0)
        return screen_delta_candidate(
            disposable, parent_solver=inputs[0], candidate_solver=inputs[1],
            target_capability=inputs[2], policy=inputs[3], cohorts=inputs[4]), receipt

    def adopt(self, screened, receipt):
        with shape_patch(), self._headroom(), patch.object(codec, "assert_headroom"):
            return adopt_screened_delta(
                screened, self.run, clearance_receipt=receipt,
                selection=self.selection, source_frontier=self.frontier,
                authority_registry=self.registry)

    def test_accepted_import_resets_only_changed_state_and_cold_loads_lineage(self):
        screened, receipt = self.screened()
        outcome = self.adopt(screened, receipt)
        self.assertEqual(outcome.status, "PUBLISHED")
        with shape_patch():
            student = load_bamf_generation(self.run / "bamf-state.json")
        self.assertEqual(student.transition["kind"], "PACKAGE_IMPORT")
        self.assertEqual(student.retained_state.optimizer_step, 11)
        parameter = np.asarray(student.retained_state.optimizer.parameters[NAME])
        self.assertEqual(parameter[0].tolist(), [1.0, -0.75])
        self.assertEqual(parameter[1].tolist(), [1.0, 2.0])
        self.assertEqual(np.asarray(student.retained_state.optimizer.m[NAME])[0].tolist(), [0., 0.])
        np.testing.assert_allclose(
            np.asarray(student.retained_state.optimizer.m[NAME])[1], [.1, .1])
        np.testing.assert_allclose(
            np.asarray(student.retained_state.optimizer.v[NAME])[0], [0., 0.])
        np.testing.assert_allclose(
            np.asarray(student.retained_state.optimizer.v[NAME])[1], [.01, .01])
        self.assertEqual(np.asarray(student.retained_state.optimizer.update_counts[NAME]).tolist(), [0, 3])
        self.assertEqual(tuple(age.accepted_age for age in student.retained_state.policy.row_ages), (0, 2))
        self.assertEqual(student.retained_state.policy.mode, "ADAPTIVE")
        self.assertEqual(student.retained_state.policy.accepted_fast_since_full, 0)
        self.assertEqual(student.teacher_state, self.base.teacher_state)
        lineage = student.evaluation_contract["package_import"]
        self.assertEqual(lineage["parent_manifest_sha256"], self.pointer["manifest_sha256"])
        self.assertEqual(lineage["package_sha256"], outcome.package_sha256)
        self.assertEqual(lineage["reset_policy_sha256"], outcome.reset_policy_sha256)

        transaction = begin_candidate(student.retained_state)
        transaction = candidate_step(
            transaction, {NAME: mx.array([[.25, -.5], [0., 0.]], dtype=mx.float32)},
            {NAME: mx.array([True, False])}, HP, decay={NAME: True},
            loss_bearing=True, max_norm=1.)
        stepped = resolve_candidate(transaction, accepted=True)
        self.assertEqual(np.asarray(stepped.optimizer.update_counts[NAME]).tolist(), [1, 3])
        self.assertEqual(student.evaluation_contract["package_import"]["package_sha256"],
                         outcome.package_sha256)

    def test_b12_import_custody_rejects_changes_outside_declared_slices(self):
        parent = parent_state()
        forged = mx.array([[1., -.75], [99., 2.]], dtype=mx.float32)
        with self.assertRaises(BilqisError):
            begin_package_import(
                parent, {NAME: forged}, (ImportResetSlice(NAME, 0, 2),),
                parent_manifest_sha256="a" * 64, package_sha256="b" * 64)

    def test_rejection_and_stale_parent_preserve_current_generation(self):
        rejected, receipt = self.screened(reject=True)
        original = (self.run / "bamf-state.json").read_bytes()
        outcome = self.adopt(rejected, receipt)
        self.assertEqual(outcome.status, "REJECTED")
        self.assertEqual((self.run / "bamf-state.json").read_bytes(), original)

        screened, receipt = self.screened()
        retained = replace(candidate(accepted_state(parent_state()), generation=1,
                                     parent=self.pointer["manifest_sha256"]),
                           provenance=self.base.provenance,
                           correction_frontier=self.base.correction_frontier)
        with shape_patch(), self._headroom(), patch.object(codec, "assert_headroom"):
            newer = publish_bamf_generation(self.run, retained)
        with self.assertRaises(BilqisError):
            self.adopt(screened, receipt)
        self.assertEqual(json.loads((self.run / "bamf-state.json").read_text())["manifest_sha256"],
                         newer["manifest_sha256"])

    def test_pointer_crash_preserves_parent_and_retry_converges(self):
        screened, receipt = self.screened()
        original = (self.run / "bamf-state.json").read_bytes()
        with shape_patch(), self._headroom(), patch.object(codec, "assert_headroom"), \
                patch.object(publication, "_atomic_pointer", side_effect=RuntimeError("crash")), \
                self.assertRaisesRegex(RuntimeError, "crash"):
            adopt_screened_delta(
                screened, self.run, clearance_receipt=receipt,
                selection=self.selection, source_frontier=self.frontier,
                authority_registry=self.registry)
        self.assertEqual((self.run / "bamf-state.json").read_bytes(), original)
        outcome = self.adopt(screened, receipt)
        self.assertEqual(outcome.status, "PUBLISHED")

    def test_unsigned_clearance_and_embedded_rights_cannot_authorize(self):
        screened, receipt = self.screened()
        with self.assertRaises(BilqisError):
            self.adopt(screened, replace(receipt, signature_hex="0" * 128))
        wrong, receipt = self.screened(rights_clearance="f" * 64)
        with self.assertRaises(BilqisError):
            self.adopt(wrong, receipt)

    def test_public_package_import_transition_cannot_self_authorize(self):
        forged = replace(
            self.base, generation=1, parent_manifest_sha256=self.pointer["manifest_sha256"],
            transition={"schema": "bilqis.mlx.bamf-generation-transition/v1",
                        "kind": "PACKAGE_IMPORT", "invalidate_derived_caches": True})
        self.assertIs(type(forged), BamfBundleCandidate)
        with shape_patch(), self._headroom(), patch.object(codec, "assert_headroom"), \
                self.assertRaises(BilqisError):
            publish_bamf_generation(self.run, forged)
        self.assertEqual(json.loads((self.run / "bamf-state.json").read_text())["generation"], 0)


if __name__ == "__main__":
    import unittest
    unittest.main()
