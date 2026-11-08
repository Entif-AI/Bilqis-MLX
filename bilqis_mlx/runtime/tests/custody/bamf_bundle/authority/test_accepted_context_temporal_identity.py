"""Accepted C09 context invalidations retain source-owned four-time identity."""
from dataclasses import replace
from bilqis_mlx.runtime.accepted_correction_ledger import (
    CONTEXT_INVALIDATION_EVENT,
    context_invalidation_from_record,
    context_invalidation_record,
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
from bilqis_mlx.semantics.context_eligibility import (
    C09ContextInvalidation,
    C09_INVALIDATION_SCHEMA_V1,
)
from bilqis_mlx.semantics.domains import contract_digest


class AcceptedContextTemporalIdentityTests(AcceptedContextFixture):
    def test_historical_v1_event_identity_excludes_v2_temporal_fields(self):
        event = C09ContextInvalidation(
            old_context_digest="1" * 64,
            new_context_digest="2" * 64,
            reason_codes=("BAMF_CONTEXT_APPROVED_VIEW_CHANGED",),
            principal_id="principal:legacy",
            tenant_id="tenant:legacy",
            scope="SOURCE_CONTEXT",
            semantic_release="3" * 64,
            policy_epoch=1,
            rights_epoch=1,
            correction_generation=1,
            causal_prefix_end=1,
            invalidated_handles=("frame:legacy",),
        )
        self.assertEqual(event.schema_version, C09_INVALIDATION_SCHEMA_V1)
        self.assertEqual(event.event_id, contract_digest({
            "old_context_digest": event.old_context_digest,
            "new_context_digest": event.new_context_digest,
            "reason_codes": event.reason_codes,
            "principal_id": event.principal_id,
            "tenant_id": event.tenant_id,
            "scope": event.scope,
            "semantic_release": event.semantic_release,
            "policy_epoch": event.policy_epoch,
            "rights_epoch": event.rights_epoch,
            "correction_generation": event.correction_generation,
            "causal_prefix_end": event.causal_prefix_end,
            "invalidated_handles": event.invalidated_handles,
            "schema_version": event.schema_version,
        }))

    def test_source_owned_four_time_identity_survives_cold_ledger_read(self):
        case = source_owned_temporal_case()
        authority = case.contexts.transition_authority
        cache = self.publish()
        with shape_patch():
            host = AcceptedRuntimeHost(self.run, AUTHORITY)
            transition = host.record_context_transition(
                case.previous, case.contexts)
        self.assertEqual(len(transition.invalidations), 1)
        live_event = transition.invalidations[0]
        self.assertEqual(
            (
                live_event.source_time,
                live_event.effective_time,
                live_event.observed_at,
                live_event.recorded_at,
            ),
            (
                authority.source_time,
                authority.effective_time,
                authority.observed_at,
                authority.recorded_at,
            ),
        )
        self.assertEqual(
            live_event.temporal_authority_sha256,
            authority.authority_registry_sha256,
        )

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
        cold_event = context_invalidation_from_record(cold_record)
        self.assertEqual(cold_event, live_event)
        self.assertEqual(context_temporal_identity_from_record(cold_record), expected)

        forged_event = replace(
            live_event,
            source_time=live_event.source_time + 1,
        )
        with self.assertRaises(BilqisError):
            context_invalidation_record(
                cache.accepted_manifest_sha256,
                forged_event,
            )

        forged_record = dict(cold_record)
        forged_payload = dict(cold_record["context_invalidation"])
        forged_payload["source_time"] = forged_event.source_time
        forged_payload["context_event_id"] = forged_event.event_id
        forged_record["context_invalidation"] = forged_payload
        with self.assertRaises(BilqisError):
            context_invalidation_from_record(forged_record)

        for field in ("source_time", "effective_time", "observed_at", "recorded_at"):
            with self.subTest(field=field):
                forged_record = dict(cold_record)
                forged_payload = dict(cold_record["context_invalidation"])
                forged_payload[field] += 1
                forged_record["context_invalidation"] = forged_payload
                with self.assertRaises(BilqisError):
                    context_invalidation_from_record(forged_record)


if __name__ == "__main__":
    import unittest

    unittest.main()
