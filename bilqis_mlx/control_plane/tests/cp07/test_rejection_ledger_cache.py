"""Content-verified rejection prefix reuse across independent writer appends."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.control_plane.native_cache.rejections import RejectionLedgerCache
from bilqis_mlx.control_plane.native_contracts import canonical
from bilqis_mlx.control_plane import native_rejections
from bilqis_mlx.errors import BilqisError


class RejectionLedgerCacheTests(unittest.TestCase):
    def test_reuse_requires_exact_prefix_and_accepted_history(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root / "events.jsonl"
            portable = {
                "event": "BAMF_CANDIDATE_REJECTED",
                "student_manifest_sha256": "parent",
                "event_id": "portable",
                "rejection_authority": {},
            }
            legacy = {**portable, "event_id": "legacy", "rejection_authority": None}
            ledger.write_bytes(canonical(portable) + canonical(legacy))
            history = (SimpleNamespace(manifest_sha256="parent"),)
            cache = RejectionLedgerCache()
            verified = []

            def verify(row, generation, plane):
                verified.append(row["event_id"])
                if row["event_id"] not in {"portable", "legacy"}:
                    native_rejections.invalid("CONTROL_PLANE_NATIVE_REJECTION_EVENT_ID_DRIFT")
                event_id = row["event_id"]
                return event_id, "authority", event_id, {}, event_id == "portable"

            def project(result, generation):
                return (result[0],), ()

            with (
                    patch.object(native_rejections, "_verified_rejection", side_effect=verify),
                    patch.object(native_rejections, "_project_verified_rejection", side_effect=project),
                    patch("bilqis_mlx.data_plane.data_plane", return_value=object())):
                expected = (("portable", "legacy"), ())
                self.assertEqual(cache(root, history), expected)
                with ledger.open("ab") as stream:
                    stream.write(canonical({"event": "heartbeat"}))
                self.assertEqual(cache(root, history), expected)
                self.assertEqual(verified, ["portable", "legacy", "legacy"])
                new_history = (SimpleNamespace(manifest_sha256="parent"),)
                self.assertEqual(cache(root, new_history), expected)
                self.assertEqual(verified[-2:], ["portable", "legacy"])

                # Growth alone cannot hide a modified previously verified row.
                ledger.write_bytes(
                    canonical({**portable, "event_id": "forged"})
                    + canonical(legacy) + canonical({"event": "heartbeat" * 100}))
                with self.assertRaises(BilqisError):
                    cache(root, new_history)
                self.assertEqual(verified[-1], "forged")
                ledger.write_bytes(canonical(legacy))
                self.assertEqual(cache(root, new_history), (("legacy",), ()))
                with ledger.open("ab") as stream:
                    stream.write(b"invalid")
                with self.assertRaises(BilqisError):
                    cache(root, new_history)

    def test_empty_or_missing_ledger_resets_material(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            ledger = root / "events.jsonl"
            cache = RejectionLedgerCache()
            ledger.write_bytes(canonical({"event": "heartbeat"}))
            self.assertEqual(cache(root, ()), ((), ()))
            ledger.unlink()
            self.assertEqual(cache(root, ()), ((), ()))
            ledger.write_bytes(b"not-json\n")
            with self.assertRaises(BilqisError):
                cache(root, ())
