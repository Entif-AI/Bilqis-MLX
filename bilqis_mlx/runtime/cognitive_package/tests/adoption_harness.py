"""Shared C12 adoption harness for B13-backed package import tests."""
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

from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import CurriculumProfile
from bilqis_mlx.factory.tests.test_executable_release import _answers
from bilqis_mlx.factory.tests.test_execution_plan import _synthetic_course, _synthetic_registry
from bilqis_mlx.runtime import mlx_checkpoint
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation
from bilqis_mlx.runtime.cognitive_package import (
    DeltaSlice, PackageArtifact, PackageBinding, PackageKind, ReceiverTensor, SourceRights,
    apply_plastic_delta, encode_plastic_delta, export_capability,
    publish_screened_delta_import, receiver_parameter_schema_digest, receiver_weight_digest,
)
from bilqis_mlx.runtime.cognitive_package.delta import _issue_screened, _package_transaction
from bilqis_mlx.runtime.cognitive_package.tests.fixtures import snapshot
from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import (
    genesis_feature_source_patch, issue_feature_authority, source_features,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    NAME, candidate, parent_state, provision_source_authority_registry,
    publish_candidate, retention_decision, shape_patch,
    with_source_authority_registry,
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


class AdoptionHarness(TestCase):
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
        self.state = parent_state()
        base = candidate(self.state)
        self.initial = replace(
            base,
            provenance=replace(base.provenance, release_digest=self.selection.release_sha256),
            correction_frontier={**base.correction_frontier,
                                 "release_digest": self.selection.release_sha256,
                                 "source_authority_registry_sha256": self.registry.digest})
        self.initial = with_source_authority_registry(self.initial, self.registry)
        foundation_features = issue_feature_authority(
            source_features(release=self.selection.release_sha256))
        provision_source_authority_registry(self.run, self.registry)
        with shape_patch(), genesis_feature_source_patch(
                source_features(release=self.selection.release_sha256)), \
                patch.object(mlx_checkpoint, "assert_headroom"):
            self.pointer = publish_candidate(
                self.run, self.initial, foundation_features=foundation_features)
            self.initial = load_bamf_generation(self.run / "bamf-state.json")
        self.frontier = SourceFrontier(
            self.initial.correction_frontier["rights_epoch"],
            self.initial.correction_frontier["correction_generation"],
            (),
        )
        self.state = self.initial.retained_state
        array = np.asarray(self.state.optimizer.parameters[NAME], dtype="<f4")
        self.tensor = ReceiverTensor(NAME, array.shape, array.tobytes())
        self.binding = PackageBinding(
            receiver_weight_digest((self.tensor,)), receiver_parameter_schema_digest((self.tensor,)),
            self.initial.topology.digest, self.initial.provenance.release_digest,
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

