"""Accepted C09 context invalidations retain source-owned four-time identity."""
from bilqis_mlx.runtime.accepted_correction_ledger import (
    CONTEXT_INVALIDATION_EVENT,
    context_temporal_identity_from_record,
    read_records,
)
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.tests.custody.bamf_bundle.authority.accepted_context_revalidation_support import (
    AUTHORITY,
    AcceptedContextFixture,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.authority.accepted_correction_runtime_temporal_support import (
    source_owned_temporal_case,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch


class AcceptedContextTemporalIdentityTests(AcceptedContextFixture):
    def test_source_owned_four_time_identity_survives_cold_ledger_read(self):
        case = source_owned_temporal_case()
        authority = case.contexts.transition_authority
        cache = self.publish()
        with shape_patch():
            host = AcceptedRuntimeHost(self.run, AUTHORITY)
            transition = host.record_context_transition(
                case.previous, case.contexts)
        self.assertEqual(len(transition.invalidations), 1)

        records = read_records(self.run, cache.accepted_manifest_sha256)
        record = next(
            item for item in records
            if item["event"] == CONTEXT_INVALIDATION_EVENT)
        expected = {
            "source_time": authority.source_time,
            "effective_time": authority.effective_time,
            "observed_at": authority.observed_at,
            "recorded_at": authority.recorded_at,
            "authority_registry_sha256": authority.authority_registry_sha256,
            "schema_version": "bilqis.source-context-temporal-identity/v1",
        }
        self.assertEqual(context_temporal_identity_from_record(record), expected)

        # Read the append-only ledger again rather than reusing the in-memory record.
        cold_records = read_records(self.run, cache.accepted_manifest_sha256)
        cold_record = next(
            item for item in cold_records
            if item["event"] == CONTEXT_INVALIDATION_EVENT)
        self.assertEqual(context_temporal_identity_from_record(cold_record), expected)

        for field in ("source_time", "effective_time", "observed_at", "recorded_at"):
            with self.subTest(field=field):
                forged_record = dict(cold_record)
                forged_identity = dict(cold_record["source_temporal_identity"])
                forged_identity[field] += 1
                forged_record["source_temporal_identity"] = forged_identity
                with self.assertRaises(BilqisError):
                    context_temporal_identity_from_record(forged_record)


if __name__ == "__main__":
    import unittest

    unittest.main()
