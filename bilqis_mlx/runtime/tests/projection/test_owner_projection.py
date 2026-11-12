"""Production C10 owner projections consume accepted authority, never lookalikes."""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.akasha_outbox import AkashaEvent, AkashaEventKind, read_outbox
from bilqis_mlx.runtime.akasha_staging import build_staging_projection
from bilqis_mlx.runtime.tests.projection.test_bamf_projection import _contract, _projected
from bilqis_mlx.runtime.owner_projection import (
    _motif_event,
    append_accepted_bamf_generation,
    append_public_package_export,
    event_from_public_package_export,
    events_from_accepted_bamf_generation,
)
from bilqis_mlx.runtime.bamf_bundle.atlas_admission import _issue_atlas_admission_binding
from bilqis_mlx.runtime.bamf_bundle.factory_release.admission import (
    _issue_factory_release_admission_binding,
)
from bilqis_mlx.runtime.bamf_bundle.factory_release_adoption import (
    _issue_factory_release_adoption_transition,
    derive_factory_release_adoption_candidate,
)
from bilqis_mlx.runtime.bamf_bundle.publication import (
    publish_atlas_admission_generation,
    publish_factory_release_adoption_generation,
)
from bilqis_mlx.runtime.cognitive_package import export_capability
from bilqis_mlx.runtime.cognitive_package.exchange import publish_package
from bilqis_mlx.runtime.cognitive_package.staging import authorize_public_export
from bilqis_mlx.runtime.cognitive_package.tests.export_authority_fixtures import (
    REGISTRY as EXPORT_REGISTRY,
    frontier as export_frontier,
    receipt as export_receipt,
    selection as export_selection,
)
from bilqis_mlx.runtime.cognitive_package.tests.fixtures import snapshot
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.acceptance._generation_acceptance_support import (
    GenerationAcceptanceFixture,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.acceptance.test_atlas_admission_publication import (
    AtlasAdmissionPublicationTests,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch


class AcceptedOwnerProjectionTests(GenerationAcceptanceFixture, unittest.TestCase):
    def test_factory_release_projection_consumes_b13_acceptance_and_keeps_time_unknown(self):
        parent = self.parent()
        transition = _issue_factory_release_adoption_transition(
            predecessor_factory_release_sha256=parent.run_identity.factory_release_sha256,
            factory_release_sha256="2" * 64,
            handoff_sha256="3" * 64,
            proposal_sha256="4" * 64,
            staged_candidate_sha256="5" * 64,
            selection_receipt_sha256="6" * 64,
            lease_sha256="7" * 64,
            source_approval_sha256="8" * 64,
        )
        candidate = derive_factory_release_adoption_candidate(
            parent,
            parent_manifest_sha256=self._parent_pointer["manifest_sha256"],
            transition=transition,
        )
        binding = _issue_factory_release_admission_binding(
            candidate, parent, transition=transition)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            publish_factory_release_adoption_generation(
                self.run, candidate, admission=binding, reserve_gib=0.0)

        with shape_patch():
            events = events_from_accepted_bamf_generation(self.run)
        self.assertEqual(tuple(event.kind for event in events),
                         (AkashaEventKind.FACTORY_RELEASE,))
        event = events[0]
        self.assertEqual(
            (event.source_time, event.effective_time,
             event.observed_at, event.recorded_at),
            (None, None, None, None))
        self.assertIn(binding.digest, event.payload_json)
        path = self.root / "factory-outbox.sqlite3"
        with shape_patch():
            self.assertEqual(append_accepted_bamf_generation(path, self.run), 1)
            self.assertEqual(append_accepted_bamf_generation(path, self.run), 0)
        self.assertEqual(read_outbox(path), events)

    def test_parameter_extension_projects_bank_allocation_from_c07_binding(self):
        parent, source = AtlasAdmissionPublicationTests.extension(self)
        with AtlasAdmissionPublicationTests.atlas_context(self):
            binding = _issue_atlas_admission_binding(
                source, parent,
                lease_sha256="9" * 64,
                source_approval_sha256="8" * 64,
                proposal_sha256="7" * 64,
                factory_release_sha256="6" * 64,
                staging_receipt_sha256="5" * 64,
                parent_feature_receipt_sha256="4" * 64,
            )
            publish_atlas_admission_generation(
                self.run, source, admission=binding, reserve_gib=0.0)

        with AtlasAdmissionPublicationTests.atlas_context(self):
            events = events_from_accepted_bamf_generation(self.run)
        self.assertEqual(tuple(event.kind for event in events),
                         (AkashaEventKind.BANK_ALLOCATION,))
        self.assertIn(binding.feature_sha256, events[0].payload_json)
        self.assertIn(binding.digest, events[0].payload_json)

    def test_retained_policy_change_projects_plasticity_epoch_from_accepted_generation(self):
        source = self.source(alternate=True)
        self.publish(source, acceptance=self.binding(source))
        with shape_patch():
            events = events_from_accepted_bamf_generation(self.run)
        self.assertEqual(tuple(event.kind for event in events),
                         (AkashaEventKind.PLASTICITY_EPOCH,))
        self.assertIn('"optimizer_step":', events[0].payload_json)
        self.assertIn('"parent_policy_sha256":', events[0].payload_json)


class PackageOwnerProjectionTests(unittest.TestCase):
    def test_public_package_projection_revalidates_clearance_and_exact_published_bytes(self):
        selection = export_selection()
        source, _unused_grant = snapshot()
        source = replace(
            source,
            binding=replace(source.binding, semantic_release=selection.release_sha256),
        )
        receipt = export_receipt(source)
        frontier = export_frontier()
        grant = authorize_public_export(
            source, receipt, selection, frontier, EXPORT_REGISTRY)
        package = export_capability(source, source.signature, grant)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            published = publish_package(package, root / "published")
            event = event_from_public_package_export(
                package, published, receipt, selection, frontier, EXPORT_REGISTRY)
            self.assertEqual(event.kind, AkashaEventKind.PACKAGE_EXPORT)
            self.assertEqual(event.source_receipt_sha256, receipt.clearance_sha256)
            self.assertEqual(
                (event.source_time, event.effective_time,
                 event.observed_at, event.recorded_at),
                (None, None, None, None))
            outbox = root / "outbox.sqlite3"
            self.assertEqual(append_public_package_export(
                outbox, package, published, receipt, selection, frontier,
                EXPORT_REGISTRY), 1)
            self.assertEqual(append_public_package_export(
                outbox, package, published, receipt, selection, frontier,
                EXPORT_REGISTRY), 0)
            published.write_text("tampered")
            with self.assertRaises(Exception):
                event_from_public_package_export(
                    package, published, receipt, selection, frontier, EXPORT_REGISTRY)


class OwnerProjectionContractTests(unittest.TestCase):
    def test_unknown_time_requires_complete_null_quartet_and_stays_internal(self):
        payload = {
            "run_id": "fixture-run",
            "generation": 1,
            "transition_kind": "PARAMETER_EXTENSION",
            "feature_sha256": "1" * 64,
            "factory_release_sha256": "2" * 64,
            "admission_receipt_sha256": "3" * 64,
        }
        event = AkashaEvent.from_payload(
            kind=AkashaEventKind.BANK_ALLOCATION,
            subject_id="feature-allocation:" + "1" * 64,
            source_receipt_sha256="3" * 64,
            payload=payload,
            source_time=None,
            effective_time=None,
            observed_at=None,
            recorded_at=None,
        )
        with self.assertRaises(BilqisError):
            AkashaEvent.from_payload(
                kind=AkashaEventKind.BANK_ALLOCATION,
                subject_id="feature-allocation:" + "1" * 64,
                source_receipt_sha256="3" * 64,
                payload=payload,
                source_time=None,
                effective_time=1,
                observed_at=None,
                recorded_at=None,
            )
        with tempfile.TemporaryDirectory() as folder:
            domain = _contract(Path(folder) / "outbox.sqlite3")
            with self.assertRaises(BilqisError):
                build_staging_projection((_projected(event, domain),), domain)

    def test_motif_projection_uses_validated_b13_transition_identity(self):
        transition = {
            "schema": "bilqis.mlx.bamf-generation-transition/v3",
            "kind": "MOTIF_ALLOCATION",
            "invalidate_derived_caches": True,
            "added_pages": 1,
            "b12_transition_sha256": "1" * 64,
            "parent_extents_sha256": "2" * 64,
            "candidate_extents_sha256": "3" * 64,
            "parent_allocation_sha256": "4" * 64,
            "candidate_allocation_sha256": "5" * 64,
            "motif_candidate_sha256": "6" * 64,
            "approved_context_sha256": "7" * 64,
            "candidate_identity_sha256": "8" * 64,
        }
        student = type("Student", (), {
            "run_id": "fixture-run",
            "generation": 2,
            "transition": transition,
        })()
        binding = type("Binding", (), {"digest": "9" * 64})()
        event = _motif_event(student, binding)
        self.assertEqual(event.kind, AkashaEventKind.MOTIF_CANDIDATE)
        self.assertIn('"motif_candidate_sha256":"' + "6" * 64 + '"', event.payload_json)
        altered = dict(transition, added_pages=2)
        student.transition = altered
        with self.assertRaises(BilqisError):
            _motif_event(student, binding)


if __name__ == "__main__":
    unittest.main()
