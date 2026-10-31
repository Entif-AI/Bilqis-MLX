"""Frozen upstream receipt fixtures carry identity without production authority."""
from dataclasses import replace
import hashlib
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.owner_receipt_fixture import OwnerReceiptFixture, project_owner_receipt_fixture
from bilqis_mlx.runtime.akasha_outbox import AkashaEventKind
from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityKey, SourceAuthorityScope, SourceAuthorityRegistry
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind

KEY = Ed25519PrivateKey.from_private_bytes(bytes.fromhex('33' * 32))
REGISTRY = SourceAuthorityRegistry((SourceAuthorityKey('fixture:owner',
    KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex(),
    (SourceAuthorityScope(DependencyKind.ARTIFACT, 'projection-fixture:'),)),))


def signed(record):
    return replace(record, signature_hex=KEY.sign(record.signing_bytes()).hex())


class OwnerReceiptFixtureTests(unittest.TestCase):
    def receipt(self, category):
        return signed(OwnerReceiptFixture(category, 'external:event:one', 'fixture:producer',
            'fixture:opaque-artifact/v1', hashlib.sha256(b'PRIVATE_OPAQUE_ARTIFACT').hexdigest(),
            'fixture:owner', 570, 575, 580, 585, '0' * 128))

    def test_three_categories_are_opaque_repeatable_and_explicit_fixtures(self):
        for category in (AkashaEventKind.BANK_ALLOCATION, AkashaEventKind.PLASTICITY_EPOCH,
                         AkashaEventKind.PACKAGE_EXPORT):
            receipt = self.receipt(category)
            event = project_owner_receipt_fixture(receipt, b'PRIVATE_OPAQUE_ARTIFACT', REGISTRY)
            self.assertEqual(event.kind, category)
            self.assertEqual(event, project_owner_receipt_fixture(receipt, b'PRIVATE_OPAQUE_ARTIFACT', REGISTRY))
            self.assertNotIn('PRIVATE_OPAQUE_ARTIFACT', event.payload_json)
            self.assertIn('DISPOSABLE_CONTRACT', event.payload_json)
            self.assertNotEqual(event.event_id, receipt.source_event_id)
            self.assertNotEqual(event.source_receipt_sha256, receipt.artifact_sha256)

    def test_artifact_signature_scope_mode_and_identity_tampering_reject(self):
        receipt = self.receipt(AkashaEventKind.BANK_ALLOCATION)
        with self.assertRaises(BilqisError):
            project_owner_receipt_fixture(receipt, b'altered', REGISTRY)
        for fields in ({'source_event_id': 'other'}, {'recorded_at': 586},
                       {'category': AkashaEventKind.PACKAGE_EXPORT}, {'verification_mode': 'PRODUCTION'},
                       {'schema_version': 'unknown/v1'}, {'source_owner': 'other'}, {'category': 'BANK_ALLOCATION'},
                       {'source_time': False}):
            with self.subTest(fields=fields), self.assertRaises(BilqisError):
                project_owner_receipt_fixture(replace(receipt, **fields), b'PRIVATE_OPAQUE_ARTIFACT', REGISTRY)
        limited = SourceAuthorityRegistry((replace(REGISTRY.keys[0], allowed_scopes=(
            SourceAuthorityScope(DependencyKind.ARTIFACT, 'unrelated:'),)),))
        with self.assertRaises(BilqisError):
            project_owner_receipt_fixture(receipt, b'PRIVATE_OPAQUE_ARTIFACT', limited)

    def test_divergent_attestations_cannot_reuse_one_source_event_identity(self):
        from pathlib import Path
        import tempfile
        from bilqis_mlx.runtime.akasha_outbox import append_outbox, read_outbox
        receipt = self.receipt(AkashaEventKind.PACKAGE_EXPORT)
        first = project_owner_receipt_fixture(receipt, b'PRIVATE_OPAQUE_ARTIFACT', REGISTRY)
        second = project_owner_receipt_fixture(signed(replace(receipt, recorded_at=586)), b'PRIVATE_OPAQUE_ARTIFACT', REGISTRY)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'outbox.sqlite3'
            self.assertTrue(append_outbox(path, first))
            self.assertFalse(append_outbox(path, first))
            with self.assertRaises(BilqisError):
                append_outbox(path, second)
            self.assertEqual(read_outbox(path), (first,))

    def test_fixture_categories_cannot_lose_maturity_in_public_staging(self):
        from pathlib import Path
        import tempfile
        from bilqis_mlx.runtime.akasha_staging import build_staging_projection
        from bilqis_mlx.runtime.tests.projection.test_bamf_projection import _contract, _projected
        for category in (AkashaEventKind.BANK_ALLOCATION, AkashaEventKind.PLASTICITY_EPOCH,
                         AkashaEventKind.PACKAGE_EXPORT):
            receipt = self.receipt(category)
            event = project_owner_receipt_fixture(receipt, b'PRIVATE_OPAQUE_ARTIFACT', REGISTRY)
            with tempfile.TemporaryDirectory() as folder:
                domain = _contract(Path(folder) / 'outbox.sqlite3')
                with self.subTest(category=category):
                    with self.assertRaises(BilqisError) as caught:
                        build_staging_projection((_projected(event, domain),), domain)
                    self.assertEqual(caught.exception.context['reason'], 'BAMF_C10_FIXTURE_PUBLIC_SCHEMA_REQUIRED')
                    self.assertEqual(tuple(Path(folder).iterdir()), ())

    def test_direct_and_canonical_public_records_reject_fixture_categories(self):
        import json
        from pathlib import Path
        import tempfile
        from bilqis_mlx.runtime.akasha_staging import build_staging_projection, StagingProjection, _digest
        from bilqis_mlx.runtime.tests.projection.test_bamf_projection import _contract, _projected, _event
        with tempfile.TemporaryDirectory() as folder:
            domain = _contract(Path(folder) / 'outbox.sqlite3')
            ordinary = build_staging_projection((_projected(_event('capability:public'), domain),), domain)
            for category in (AkashaEventKind.BANK_ALLOCATION, AkashaEventKind.PLASTICITY_EPOCH,
                             AkashaEventKind.PACKAGE_EXPORT):
                with self.subTest(category=category):
                    with self.assertRaises(BilqisError):
                        replace(ordinary.public_events[0], kind=category)
                    raw = json.loads(ordinary.canonical_json)
                    raw['public_events'][0]['kind'] = category.value
                    raw['census'] = [[category.value, 1]]
                    raw['stage_digest'] = _digest({key: value for key, value in raw.items() if key != 'stage_digest'})
                    with self.assertRaises(BilqisError):
                        StagingProjection.from_canonical_json(json.dumps(raw, sort_keys=True, separators=(',', ':')))
                    self.assertEqual(tuple(Path(folder).iterdir()), ())
