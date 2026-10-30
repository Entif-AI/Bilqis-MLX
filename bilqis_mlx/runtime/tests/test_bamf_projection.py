"""C10.2 source/release/model/evaluator/rights-bound outbox projections."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.akasha_outbox import (
    AkashaEvent, AkashaEventKind, pending_events,
)
from bilqis_mlx.runtime.bamf_projection import (
    BamfProjectionEvent, ProjectionDomainContract,
    project_generation_outbox,
)
from bilqis_mlx.runtime.akasha_staging import (
    build_staging_projection, promote_staging_projection,
    query_public_projection, read_active_projection,
    read_staging_projection, verify_staging_projection,
)


def _event(subject):
    return AkashaEvent.from_payload(
        kind=AkashaEventKind.REQUALIFICATION,
        subject_id=subject, source_receipt_sha256="9" * 64,
        payload={
            "capability_id": subject,
            "retained_generation_sha256": "a" * 64,
            "status": "REQUALIFICATION_REQUIRED",
        },
        source_time=570, effective_time=575,
        observed_at=580, recorded_at=585,
    )


def _contract(path):
    return ProjectionDomainContract(
        outbox_path=path,
        source_id="source:fixture",
        release_digest="1" * 64,
        model_digest="2" * 64,
        evaluator_digest="3" * 64,
        rights_digest="4" * 64,
        as_of=600,
    )


def _projected(event, contract):
    return BamfProjectionEvent(
        event=event,
        source_id=contract.source_id,
        release_digest=contract.release_digest,
        model_digest=contract.model_digest,
        evaluator_digest=contract.evaluator_digest,
        rights_digest=contract.rights_digest,
        as_of=contract.as_of,
    )


class BamfProjectionTests(unittest.TestCase):
    def test_late_durable_conflict_rolls_back_entire_batch(self):
        from bilqis_mlx.runtime.bamf_projection import read_projection_outbox
        with tempfile.TemporaryDirectory() as folder:
            original = _contract(Path(folder) / 'outbox.sqlite3')
            existing = _projected(_event('capability:existing'), original)
            project_generation_outbox((existing,), original)
            changed = replace(original, rights_digest='5' * 64)
            new = _projected(_event('capability:new'), changed)
            conflict = _projected(existing.event, changed)
            with self.assertRaises(BilqisError) as caught:
                project_generation_outbox((new, conflict), changed)
            self.assertEqual(caught.exception.context['reason'], 'BAMF_C10_EVENT_ID_CONFLICT')
            self.assertEqual(read_projection_outbox(original.outbox_path), (existing,))

    def test_late_source_identity_conflict_rolls_back_entire_batch(self):
        from bilqis_mlx.runtime.bamf_projection import read_projection_outbox
        from bilqis_mlx.runtime.owner_receipt_fixture import project_owner_receipt_fixture
        from bilqis_mlx.runtime.tests.test_owner_receipt_fixture import OwnerReceiptFixtureTests, REGISTRY, signed
        receipt = OwnerReceiptFixtureTests().receipt(AkashaEventKind.PACKAGE_EXPORT)
        original_event = project_owner_receipt_fixture(receipt, b'PRIVATE_OPAQUE_ARTIFACT', REGISTRY)
        conflicting_event = project_owner_receipt_fixture(
            signed(replace(receipt, recorded_at=586)), b'PRIVATE_OPAQUE_ARTIFACT', REGISTRY)
        with tempfile.TemporaryDirectory() as folder:
            domain = _contract(Path(folder) / 'outbox.sqlite3')
            existing = _projected(original_event, domain)
            project_generation_outbox((existing,), domain)
            new = _projected(_event('capability:new'), domain)
            with self.assertRaises(BilqisError) as caught:
                project_generation_outbox((new, _projected(conflicting_event, domain)), domain)
            self.assertEqual(caught.exception.context['reason'], 'BAMF_C10_OWNER_SOURCE_EVENT_CONFLICT')
            self.assertEqual(read_projection_outbox(domain.outbox_path), (existing,))

    def test_conflicting_source_identities_in_new_batch_leave_no_events(self):
        from bilqis_mlx.runtime.bamf_projection import read_projection_outbox
        from bilqis_mlx.runtime.owner_receipt_fixture import project_owner_receipt_fixture
        from bilqis_mlx.runtime.tests.test_owner_receipt_fixture import OwnerReceiptFixtureTests, REGISTRY, signed
        receipt = OwnerReceiptFixtureTests().receipt(AkashaEventKind.PACKAGE_EXPORT)
        first = project_owner_receipt_fixture(receipt, b'PRIVATE_OPAQUE_ARTIFACT', REGISTRY)
        second = project_owner_receipt_fixture(
            signed(replace(receipt, recorded_at=586)), b'PRIVATE_OPAQUE_ARTIFACT', REGISTRY)
        with tempfile.TemporaryDirectory() as folder:
            domain = _contract(Path(folder) / 'outbox.sqlite3')
            with self.assertRaises(BilqisError):
                project_generation_outbox((_projected(first, domain), _projected(second, domain)), domain)
            self.assertEqual(read_projection_outbox(domain.outbox_path), ())

    def test_durable_domain_binding_cannot_be_relabelled_after_restart(self):
        from bilqis_mlx.runtime.bamf_projection import read_projection_outbox
        with tempfile.TemporaryDirectory() as folder:
            domain = _contract(Path(folder) / 'outbox.sqlite3')
            event = _projected(_event('capability:bound'), domain)
            project_generation_outbox((event,), domain)
            self.assertEqual(read_projection_outbox(domain.outbox_path), (event,))
            for key, value in (('source_id', 'other'), ('release_digest', '5' * 64),
                               ('model_digest', '6' * 64), ('evaluator_digest', '7' * 64),
                               ('rights_digest', '8' * 64), ('as_of', 601)):
                changed = replace(domain, **{key: value})
                with self.subTest(key=key), self.assertRaises(BilqisError):
                    project_generation_outbox((_projected(event.event, changed),), changed)
                self.assertEqual(read_projection_outbox(domain.outbox_path), (event,))
                with self.assertRaises(BilqisError):
                    build_staging_projection((_projected(event.event, changed),), changed)


    def test_staging_census_bounded_queries_and_private_payload_exclusion(self):
        with tempfile.TemporaryDirectory() as folder:
            contract = _contract(Path(folder) / "outbox.sqlite3")
            private = AkashaEvent.from_payload(
                kind=AkashaEventKind.REQUALIFICATION,
                subject_id="/private/users/alpha",
                source_receipt_sha256="9" * 64,
                payload={
                    "capability_id": "capability:private",
                    "retained_generation_sha256": "a" * 64,
                    "status": "REQUALIFICATION_REQUIRED",
                    "raw_private_input": "SECRET_SOURCE_TEXT",
                    "private_path": "/private/users/alpha/source.txt",
                },
                source_time=570, effective_time=575,
                observed_at=580, recorded_at=585,
            )
            events = (
                _projected(private, contract),
                _projected(_event("capability:public"), contract),
            )
            stage = build_staging_projection(events, contract)
            verified = verify_staging_projection(stage)
            self.assertEqual(len(stage.public_events), 2)
            self.assertEqual(stage.census, (("REQUALIFICATION", 2),))
            self.assertNotIn("SECRET_SOURCE_TEXT", stage.canonical_json)
            self.assertNotIn("/private/users/alpha", stage.canonical_json)
            self.assertNotIn("private_path", stage.canonical_json)
            self.assertEqual(len(query_public_projection(stage, limit=1)), 1)
            self.assertEqual(len(query_public_projection(stage, limit=2)), 2)
            self.assertEqual(
                query_public_projection(stage, limit=2, as_of=580), ())
            with self.assertRaises(BilqisError):
                query_public_projection(stage, limit=101)
            self.assertEqual(verified.stage.stage_digest, stage.stage_digest)
            future_effective = AkashaEvent.from_payload(
                kind=AkashaEventKind.REQUALIFICATION,
                subject_id="capability:future",
                source_receipt_sha256="9" * 64,
                payload={
                    "capability_id": "capability:future",
                    "retained_generation_sha256": "a" * 64,
                    "status": "REQUALIFICATION_REQUIRED",
                },
                source_time=570, effective_time=620,
                observed_at=580, recorded_at=585,
            )
            future_stage = build_staging_projection(
                (_projected(future_effective, contract),), contract)
            self.assertEqual(
                query_public_projection(future_stage, limit=1, as_of=600), ())
            self.assertEqual(len(query_public_projection(
                future_stage, limit=1, as_of=630)), 1)

    def test_atomic_staging_promotion_preserves_old_generation_and_pointer(self):
        with tempfile.TemporaryDirectory() as folder:
            contract = _contract(Path(folder) / "outbox.sqlite3")
            stage_db = Path(folder) / "staging.sqlite3"
            first = verify_staging_projection(build_staging_projection(
                (_projected(_event("capability:1"), contract),), contract))
            receipt = promote_staging_projection(
                stage_db, first, expected_active_digest=None)
            self.assertEqual(receipt.active_digest, first.stage.stage_digest)
            self.assertEqual(read_active_projection(stage_db), first.stage)
            second = verify_staging_projection(build_staging_projection(
                tuple(_projected(
                    _event("capability:" + str(index)), contract)
                    for index in range(2)), contract))
            with self.assertRaises(BilqisError) as caught:
                promote_staging_projection(
                    stage_db, second, expected_active_digest=None)
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C10_STAGING_POINTER_CONFLICT")
            self.assertEqual(read_active_projection(stage_db), first.stage)
            promoted = promote_staging_projection(
                stage_db, second,
                expected_active_digest=first.stage.stage_digest)
            self.assertEqual(promoted.previous_digest,
                             first.stage.stage_digest)
            self.assertEqual(read_active_projection(stage_db), second.stage)
            self.assertEqual(read_staging_projection(
                stage_db, first.stage.stage_digest), first.stage)
            self.assertEqual(read_staging_projection(
                stage_db, second.stage.stage_digest), second.stage)

    def test_identity_bound_outbox_is_deduplicated_without_graph_io(self):
        with tempfile.TemporaryDirectory() as folder:
            contract = _contract(Path(folder) / "outbox.sqlite3")
            events = tuple(
                _projected(_event("capability:" + str(index)), contract)
                for index in range(2))
            receipt = project_generation_outbox(events, contract)
            self.assertEqual(receipt.appended_count, 2)
            self.assertEqual(receipt.duplicate_count, 0)
            self.assertEqual(receipt.pending_count, 2)
            self.assertEqual(receipt.domain_digest, contract.digest)
            self.assertEqual(receipt.event_ids,
                             tuple(item.event.event_id for item in events))
            repeated = project_generation_outbox(events, contract)
            self.assertEqual(repeated.appended_count, 0)
            self.assertEqual(repeated.duplicate_count, 2)
            self.assertEqual(len(pending_events(contract.outbox_path)), 2)

    def test_rights_release_model_evaluator_or_asof_drift_rejects_before_write(self):
        with tempfile.TemporaryDirectory() as folder:
            contract = _contract(Path(folder) / "outbox.sqlite3")
            event = _projected(_event("capability:1"), contract)
            for changed in (
                replace(event, rights_digest="0" * 64),
                replace(event, release_digest="0" * 64),
                replace(event, model_digest="0" * 64),
                replace(event, evaluator_digest="0" * 64),
                replace(event, as_of=590),
            ):
                with self.subTest(changed=changed):
                    with self.assertRaises(BilqisError):
                        project_generation_outbox((changed,), contract)
            self.assertEqual(pending_events(contract.outbox_path), ())
            with self.assertRaises(BilqisError):
                replace(event, as_of=580)

    def test_graph_outage_never_blocks_local_training_or_event_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            contract = _contract(Path(folder) / "outbox.sqlite3")
            event = _projected(_event("capability:1"), contract)
            class GraphUnavailable:
                def __getattr__(self, name):
                    raise RuntimeError("GRAPH_UNAVAILABLE")

            graph = GraphUnavailable()
            # The outbox projection has no graph/client parameter and never
            # touches the graph. The training caller can continue locally.
            receipt = project_generation_outbox((event,), contract)
            training_steps = 1
            self.assertEqual(training_steps, 1)
            self.assertEqual(receipt.pending_count, 1)
            self.assertEqual(pending_events(contract.outbox_path),
                             (event.event,))
            self.assertIsNotNone(graph)


if __name__ == "__main__":
    unittest.main()
