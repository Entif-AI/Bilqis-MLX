"""Accepted-run C09 context revalidation stops at material equality."""
from dataclasses import replace

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.accepted_corrections import (
    ContextRevalidationFrontier, _RUNTIME_OWNER, register_accepted_target,
)
from bilqis_mlx.runtime.accepted_correction_runtime import require_pending_corrections
from bilqis_mlx.runtime.atlas_owner_ingress import _route
from bilqis_mlx.runtime.bamf_bundle import admission
from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch
from bilqis_mlx.runtime.tests.custody.bamf_bundle.authority.accepted_context_revalidation_support import (
    AUTHORITY, AcceptedContextFixture, ContextOwner, DependencyKind, DependencyRef,
    signed_context_result,
)

# Compatibility names retained for the ordering companion while the shared
# fixture moved out of this test module.
_ContextOwner = ContextOwner
_signed_context_result = signed_context_result


class AcceptedContextRevalidationTests(AcceptedContextFixture):
    def test_equal_direct_context_revalidation_releases_and_stops(self):
        _case, owner, host, invalidation, accepted_event_id = self.registered_owner()
        direct = owner.index.node("frame:context-direct")
        descendant = owner.index.node("motif:context-descendant")
        with self.assertRaises(BilqisError):
            require_pending_corrections(owner, direct.artifact_id)
        self.assertIsNone(require_pending_corrections(owner, descendant.artifact_id))

        new_time = DependencyRef(
            DependencyKind.TIME,
            "time:asof:context:" + invalidation.new_context_digest)
        result = signed_context_result(
            direct, invalidation=invalidation,
            accepted_event_id=accepted_event_id, dependencies=(new_time,))
        with shape_patch():
            host.record_context_revalidation(ContextRevalidationFrontier((result,)))

        self.assertIsNone(require_pending_corrections(owner, direct.artifact_id))
        self.assertIsNone(require_pending_corrections(owner, descendant.artifact_id))
        self.assertEqual(
            owner.index.node(direct.artifact_id).immediate_dependencies, (new_time,))

        admission._EXECUTION_CACHE_OWNER.entries.clear()
        _RUNTIME_OWNER.clear()
        cold_owner = ContextOwner((replace(direct), replace(descendant)))
        with shape_patch():
            cold_cache = bind_accepted_execution_cache(self.run)
            register_accepted_target(
                self.run, cold_cache.accepted_manifest_sha256,
                "TEST_CONTEXT", cold_owner,
                lambda current, event, source_authority: _route(
                    current, event, source_authority), AUTHORITY)
        self.assertIsNone(require_pending_corrections(cold_owner, direct.artifact_id))
        self.assertEqual(
            cold_owner.index.node(direct.artifact_id).immediate_dependencies,
            (new_time,))

    def test_context_revalidation_rejects_wrong_invalidation_receipt(self):
        _case, owner, host, invalidation, _accepted_event_id = self.registered_owner()
        direct = owner.index.node("frame:context-direct")
        result = signed_context_result(
            direct, invalidation=invalidation, accepted_event_id="9" * 64,
            dependencies=(DependencyRef(
                DependencyKind.TIME,
                "time:asof:context:" + invalidation.new_context_digest),))
        with shape_patch(), self.assertRaises(BilqisError) as rejected:
            host.record_context_revalidation(ContextRevalidationFrontier((result,)))
        self.assertEqual(
            rejected.exception.context["reason"],
            "BAMF_C09_CONTEXT_REVALIDATION_INVALIDATION_MISSING")
