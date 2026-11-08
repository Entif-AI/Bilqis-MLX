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
import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.tests.test_executable_release import _answers
from bilqis_mlx.factory.tests.test_execution_plan import (
    _synthetic_course, _synthetic_registry,
)
from bilqis_mlx.learning.atlas_candidate import begin_candidate, candidate_step, resolve_candidate
from bilqis_mlx.learning._retention.tests.execution_fixtures import execution_provenance
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.bamf_bundle import publication
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.bamf_bundle.admission import (
    bind_accepted_correction_authority,
)
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.records import canonical
from bilqis_mlx.runtime.cognitive_package import (
    DeltaSlice, PackageArtifact, PackageBinding, PackageKind, ReceiverTensor, SourceRights,
    apply_plastic_delta, encode_plastic_delta, export_capability,
    publish_screened_delta_import, receiver_parameter_schema_digest,
    receiver_weight_digest,
)
from bilqis_mlx.runtime.cognitive_package.delta import _issue_screened, _package_transaction
from bilqis_mlx.runtime.cognitive_package.tests.fixtures import snapshot
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    HP, NAME, accepted_state, candidate, parent_state, publish_candidate,
    retention_decision, shape_patch,
)
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_release_audit import ExportClearanceReceipt
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.semantics.context_eligibility import SourceFrontier
from bilqis_mlx.semantics.domains import contract_digest


PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("29" * 32))
PUBLIC = PRIVATE.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
WRONG_PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("31" * 32))
WRONG_PUBLIC = WRONG_PRIVATE.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
OWNER = "fixture:a12-source-owner"
KEY_OWNER = "fixture:key-owner"
SCOPE_OWNER = "fixture:scope-owner"
REGISTRY = SourceAuthorityRegistry((
    SourceAuthorityKey(
        OWNER, PUBLIC, (SourceAuthorityScope(DependencyKind.ARTIFACT, "a12-export:"),)),
    SourceAuthorityKey(
        KEY_OWNER, WRONG_PUBLIC,
        (SourceAuthorityScope(DependencyKind.ARTIFACT, "a12-export:"),)),
    SourceAuthorityKey(
        SCOPE_OWNER, PUBLIC,
        (SourceAuthorityScope(DependencyKind.ARTIFACT, "other-export:"),)),
))


def _selection():
    path = Path(__file__).resolve().parents[3] / "semantics" / "atlas_source_pins_v1.json"
    entry = json.loads(path.read_text())["entries"][0]
    return AtlasArtifactSelection(
        "fixture-atlas", entry["bundle_id"], entry["release_sha256"],
        entry["source_bundle_id"])


def _receipt(selection, frontier, artifacts, *, owner=OWNER, signer=PRIVATE):
    value = ExportClearanceReceipt(
        owner, selection.bundle_id, selection.release_sha256, selection.source_bundle_id,
        contract_digest(frontier), frontier.rights_epoch, frontier.correction_generation,
        artifacts, (), (), (), "0" * 128)
    return replace(value, signature_hex=signer.sign(value.signing_bytes()).hex())


class PackageImportAdoptionTests(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.run = self.root / "run"
        self.registry = REGISTRY
        self.selection = _selection()
        self.frontier = SourceFrontier(2, 4, ())
        self.state = parent_state()
        base = candidate(self.state)
        self.initial = replace(
            base,
            provenance=replace(base.provenance, release_digest=self.selection.release_sha256),
            correction_frontier={**base.correction_frontier,
                                 "release_digest": self.selection.release_sha256,
                                 "source_authority_registry_sha256": self.registry.digest})
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            self.pointer = publish_candidate(self.run, self.initial)
            self.initial = load_bamf_generation(self.run / "bamf-state.json")
        self.state = self.initial.retained_state
        array = np.asarray(self.state.optimizer.parameters[NAME], dtype="<f4")
        self.tensor = ReceiverTensor(NAME, array.shape, array.tobytes())
        self.binding = PackageBinding(
            receiver_weight_digest((self.tensor,)), receiver_parameter_schema_digest((self.tensor,)),
            self.initial.topology.digest, self.selection.release_sha256,
            self.initial.extents.active_semantic_digest, self.initial.extents.factor_map_digest,
            self.initial.extents.motif_key_map_digest)
        course = _synthetic_course(6)
        curriculum, bindings = from_legacy_course(course)
        self.source_graph = {
            "tokens": ["fixture.padding", "cogal.value.false", "cogal.value.true"]}
        self.source_registry = _synthetic_registry()
        self.answer_registry = _answers()
        self.factory_release = compile_executable_factory_release(
            curriculum, bindings, CurriculumProfile.full(), self.source_registry,
            self.answer_registry, source_root=None, graph=self.source_graph,
            verification_seed=17)

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

    def screened(self, *, accepted=True):
        package, receipt = self.package_and_clearance()
        with shape_patch():
            disposable = apply_plastic_delta(package, self.run)
            transaction = _package_transaction(disposable, self.run)
        decision = retention_decision(
            accepted=accepted, parent=transaction.parent,
            retained=transaction.candidate)
        screened = _issue_screened(disposable, transaction, decision)
        return screened, receipt

    def adopt(self, screened, receipt):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_screened_delta_import(
                screened, self.run, export_clearance=receipt,
                atlas_selection=self.selection, source_frontier=self.frontier,
                source_context=self.source_context())

    def source_context(self):
        with shape_patch():
            bind_accepted_correction_authority(self.run, self.registry)
        host = AcceptedRuntimeHost(self.run)
        receipt = {"factory_release_sha256": self.factory_release.release_sha256}
        with patch(
            "bilqis_mlx.runtime.admission._read_executable_factory_release_artifact",
            return_value=self.factory_release,
        ), patch(
            "bilqis_mlx.source_adapters.school.live_source_registry",
            return_value=self.source_registry,
        ), patch(
            "bilqis_mlx.factory.live_answers.live_answer_registry",
            return_value=self.answer_registry,
        ):
            return host.source_context(
                receipt, graph=self.source_graph, source_root=None)

    def parent_acceptance_path(self):
        return (self.run / "bamf-acceptance"
                / f"{self.pointer['manifest_sha256']}.json")

    def test_eligible_import_resets_receiver_state_and_publishes_lineage(self):
        screened, receipt = self.screened()
        published = self.adopt(screened, receipt)
        with shape_patch():
            loaded = load_bamf_generation(self.run / "bamf-state.json")

        self.assertEqual(loaded.generation, 1)
        self.assertEqual(
            loaded.retained_state.optimizer_step,
            self.state.optimizer_step,
        )
        self.assertEqual(loaded.retained_state.policy.mode, self.state.policy.mode)
        self.assertEqual(loaded.retained_state.policy.accepted_fast_since_full, 0)
        self.assertEqual(tuple(row.accepted_age for row in loaded.retained_state.policy.row_ages), (0, 2))
        self.assertAlmostEqual(
            float(np.asarray(loaded.retained_state.optimizer.parameters[NAME])[0, 0]),
            float(np.asarray(self.state.optimizer.parameters[NAME])[0, 0]) + .5,
        )
        self.assertEqual(np.asarray(loaded.retained_state.optimizer.m[NAME])[0, 0], 0.)
        self.assertEqual(np.asarray(loaded.retained_state.optimizer.v[NAME])[0, 0], 0.)
        np.testing.assert_array_equal(
            np.asarray(loaded.retained_state.optimizer.update_counts[NAME]), [0, 0])
        self.assertEqual(loaded.transition["kind"], "PACKAGE_IMPORT")
        self.assertEqual(loaded.transition["package_sha256"], screened.candidate.package.digest)
        self.assertEqual(loaded.transition["source_clearance_sha256"], receipt.clearance_sha256)
        self.assertEqual(loaded.outbox[0]["origin"], "PACKAGE_IMPORT")
        self.assertEqual(loaded.outbox[0]["receiver_manifest_sha256"], self.pointer["manifest_sha256"])
        self.assertEqual(published["parent_manifest_sha256"], self.pointer["manifest_sha256"])

    def test_next_native_step_binds_to_imported_generation_and_reset_lineage(self):
        screened, receipt = self.screened()
        published = self.adopt(screened, receipt)
        with shape_patch():
            loaded = load_bamf_generation(self.run / "bamf-state.json")

        self.assertEqual(loaded.generation, 1)
        self.assertEqual(loaded.transition["kind"], "PACKAGE_IMPORT")
        self.assertEqual(loaded.transition["package_sha256"], screened.candidate.package.digest)
        self.assertEqual(
            loaded.transition["reset_policy_sha256"], screened.transaction.reset_policy_sha256)
        self.assertEqual(
            loaded.retained_state.custody.manifest_sha256, published["manifest_sha256"])

        transaction = begin_candidate(loaded.retained_state)
        execution = execution_provenance(
            transaction.parent, rows=(0,), candidate_step=1)
        with shape_patch():
            transaction = candidate_step(
                transaction,
                {NAME: mx.array([[1., 1.], [0., 0.]], dtype=mx.float32)},
                execution, HP, spec=loaded.topology, extents=loaded.extents,
                loss_bearing=True, max_norm=1.)
        retained = resolve_candidate(transaction, accepted=True)

        np.testing.assert_array_equal(
            np.asarray(retained.optimizer.update_counts[NAME]), [1, 0])
        self.assertEqual(retained.optimizer_step, loaded.retained_state.optimizer_step + 1)
        self.assertEqual(execution.parent_manifest_sha256, published["manifest_sha256"])

    def test_reject_or_eligible_label_alone_cannot_publish(self):
        rejected, receipt = self.screened(accepted=False)
        self.assertFalse(rejected.decision.accepted)
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

    def test_host_bound_authority_rejects_scope_key_and_stale_frontier_before_publish(self):
        screened, receipt = self.screened()
        artifacts = receipt.export_artifact_digests
        cases = (
            ("scope", _receipt(
                self.selection, self.frontier, artifacts, owner=SCOPE_OWNER), self.frontier),
            ("key", _receipt(
                self.selection, self.frontier, artifacts, owner=KEY_OWNER), self.frontier),
            ("frontier", receipt, SourceFrontier(3, 4, ())),
        )
        for name, candidate_receipt, frontier in cases:
            with self.subTest(name=name), patch(
                "bilqis_mlx.runtime.cognitive_package.adoption.accept_and_publish",
                side_effect=AssertionError("downstream mutation reached"),
            ):
                with self.assertRaises(BilqisError):
                    publish_screened_delta_import(
                        screened, self.run, export_clearance=candidate_receipt,
                        atlas_selection=self.selection, source_frontier=frontier,
                        source_context=self.source_context())
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
        self.assertEqual(loaded.generation, 1)
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


if __name__ == "__main__":
    import unittest
    unittest.main()
