"""Atomic projection batches preserve durable outbox state on conflict."""
from dataclasses import replace
from importlib import import_module
from pathlib import Path
from pkgutil import iter_modules
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.akasha_outbox import AkashaEventKind
from bilqis_mlx.runtime.bamf_projection import project_generation_outbox
from bilqis_mlx.runtime.tests.projection.test_bamf_projection import _contract, _event, _projected


class BamfProjectionBatchTests(unittest.TestCase):
    def test_existing_projection_import_paths_remain_usable(self):
        import bilqis_mlx.runtime as runtime
        available = {item.name for item in iter_modules(runtime.__path__)}
        for module, name in (
            ('bilqis_mlx.runtime.akasha_outbox', 'AkashaEvent'),
            ('bilqis_mlx.runtime.akasha_staging', 'build_staging_projection'),
            ('bilqis_mlx.runtime.bamf_projection', 'BamfProjectionEvent'),
            ('bilqis_mlx.runtime.generation_projection', 'project_accepted_generation'),
            ('bilqis_mlx.runtime.owner_receipt_fixture', 'OwnerReceiptFixture'),
            ('bilqis_mlx.runtime.rosetta_observation', 'project_rosetta_observation'),
        ):
            with self.subTest(module=module):
                self.assertIn(module.rsplit('.', 1)[-1], available)
                loaded = import_module(module)
                self.assertEqual(loaded.__name__, module)
                self.assertTrue(hasattr(loaded, name))

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
        from bilqis_mlx.runtime.tests.projection.test_owner_receipt_fixture import OwnerReceiptFixtureTests, REGISTRY, signed
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
        from bilqis_mlx.runtime.tests.projection.test_owner_receipt_fixture import OwnerReceiptFixtureTests, REGISTRY, signed
        receipt = OwnerReceiptFixtureTests().receipt(AkashaEventKind.PACKAGE_EXPORT)
        first = project_owner_receipt_fixture(receipt, b'PRIVATE_OPAQUE_ARTIFACT', REGISTRY)
        second = project_owner_receipt_fixture(
            signed(replace(receipt, recorded_at=586)), b'PRIVATE_OPAQUE_ARTIFACT', REGISTRY)
        with tempfile.TemporaryDirectory() as folder:
            domain = _contract(Path(folder) / 'outbox.sqlite3')
            with self.assertRaises(BilqisError):
                project_generation_outbox((_projected(first, domain), _projected(second, domain)), domain)
            self.assertEqual(read_projection_outbox(domain.outbox_path), ())
