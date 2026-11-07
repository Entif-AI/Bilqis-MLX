"""Accepted-run C09 context revalidation stops at material equality."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.accepted_corrections import (
    AcceptedRuntimeHost,
    ContextRevalidatedArtifact,
    ContextRevalidationFrontier,
    _RUNTIME_OWNER,
    register_accepted_target,
)
from bilqis_mlx.runtime.accepted_correction_ledger import read_records
from bilqis_mlx.runtime.accepted_correction_ledger import (
    append_record, context_invalidation_record,
)
from bilqis_mlx.runtime.accepted_correction_runtime import (
    require_pending_corrections, runtime,
)
from bilqis_mlx.runtime.atlas_owner_ingress import _route
from bilqis_mlx.runtime.bamf_bundle import admission, publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, candidate, parent_state, shape_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.authority.accepted_correction_runtime_temporal_support import (
    source_owned_temporal_case,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _SOURCE_OWNER, _TEST_PRIVATE,
)
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind, DependencyRef,
)
from bilqis_mlx.semantics.context_eligibility import C09ContextInvalidation


def _signed_context_result(
    node: ArtifactNode, *, invalidation, accepted_event_id: str,
    dependencies: tuple[DependencyRef, ...] | None = None,
    digest: str | None = None, eligible: bool | None = None,
) -> ContextRevalidatedArtifact:
    result = ContextRevalidatedArtifact(
        artifact_id=node.artifact_id,
        immediate_dependencies=(
            node.immediate_dependencies if dependencies is None else dependencies),
        content_digest=node.content_digest if digest is None else digest,
        eligible=node.eligible if eligible is None else eligible,
        source_receipt_sha256="c" * 64,
        context_event_id=invalidation.event_id,
        context_invalidation_receipt_sha256=accepted_event_id,
        source_owner=_SOURCE_OWNER,
        source_signature_hex="0" * 128,
    )
    return replace(
        result,
        source_signature_hex=_TEST_PRIVATE.sign(result.signing_bytes()).hex(),
    )


class _ContextOwner:
    def __init__(self, nodes: tuple[ArtifactNode, ...]):
        self._index = DependencyIndex.build(nodes)

    @property
    def index(self) -> DependencyIndex:
        return self._index

    def _install_context_revalidation(self, index: DependencyIndex, transition) -> None:
        self._index = index


class AcceptedContextRevalidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def _publish(self):
        source = candidate(parent_state())
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            publish_bamf_generation(
                self.run, source, acceptance=acceptance(source))
            return bind_accepted_execution_cache(self.run)

    def _registered_owner(self):
        case = source_owned_temporal_case()
        direct = ArtifactNode(
            "frame:context-direct", ArtifactKind.PACKED_FRAME, "a" * 64, True,
            (DependencyRef(
                DependencyKind.TIME,
                "time:asof:context:" + case.previous.digest),),
            impact=3, exigency=3,
        )
        descendant = ArtifactNode(
            "motif:context-descendant", ArtifactKind.MOTIF, "b" * 64, True,
            (direct.reference,), impact=2, exigency=2,
        )
        owner = _ContextOwner((direct, descendant))
        cache = self._publish()
        with shape_patch():
            register_accepted_target(
                self.run, cache.accepted_manifest_sha256, "TEST_CONTEXT", owner,
                lambda current, event, source_authority: _route(
                    current, event, source_authority),
                AUTHORITY,
            )
            host = AcceptedRuntimeHost(self.run, AUTHORITY)
        invalidation = C09ContextInvalidation(
            old_context_digest=case.previous.digest,
            new_context_digest="e" * 64,
            reason_codes=("BAMF_CONTEXT_APPROVED_VIEW_CHANGED",),
            principal_id=case.task.principal_id,
            tenant_id=case.task.tenant_id,
            scope=case.task.scope,
            semantic_release=case.task.semantic_release,
            policy_epoch=case.policy.policy_epoch,
            rights_epoch=case.frontier.rights_epoch,
            correction_generation=case.frontier.correction_generation,
            causal_prefix_end=case.task.causal_prefix_end,
            invalidated_handles=tuple(sorted({
                handle
                for frame in case.previous.eligible.frames
                for handle in (frame.frame_handle, *frame.member_handles)
            })),
        )
        record = context_invalidation_record(
            cache.accepted_manifest_sha256, invalidation)
        append_record(self.run, cache.accepted_manifest_sha256, record)
        runtime(
            self.run, cache.accepted_manifest_sha256,
        ).deliver_context_invalidation(record["event_id"], invalidation)
        accepted_event_id = record["event_id"]
        return case, owner, host, invalidation, accepted_event_id

    def test_equal_direct_context_revalidation_releases_and_stops(self):
        _case, owner, host, invalidation, accepted_event_id = self._registered_owner()
        direct = owner.index.node("frame:context-direct")
        descendant = owner.index.node("motif:context-descendant")
        with self.assertRaises(BilqisError):
            require_pending_corrections(owner, direct.artifact_id)
        self.assertIsNone(require_pending_corrections(owner, descendant.artifact_id))

        new_time = DependencyRef(
            DependencyKind.TIME,
            "time:asof:context:" + invalidation.new_context_digest)
        result = _signed_context_result(
            direct,
            invalidation=invalidation,
            accepted_event_id=accepted_event_id,
            dependencies=(new_time,),
        )
        with shape_patch():
            host.record_context_revalidation(
                ContextRevalidationFrontier((result,)))

        self.assertIsNone(require_pending_corrections(owner, direct.artifact_id))
        self.assertIsNone(require_pending_corrections(owner, descendant.artifact_id))
        self.assertEqual(
            owner.index.node(direct.artifact_id).immediate_dependencies,
            (new_time,),
        )

        admission._EXECUTION_CACHE_OWNER.entries.clear()
        _RUNTIME_OWNER.clear()
        cold_owner = _ContextOwner((
            replace(direct),
            replace(descendant),
        ))
        with shape_patch():
            cold_cache = bind_accepted_execution_cache(self.run)
            register_accepted_target(
                self.run, cold_cache.accepted_manifest_sha256,
                "TEST_CONTEXT", cold_owner,
                lambda current, event, source_authority: _route(
                    current, event, source_authority),
                AUTHORITY,
            )
        self.assertIsNone(
            require_pending_corrections(cold_owner, direct.artifact_id))
        self.assertIsNone(
            require_pending_corrections(cold_owner, descendant.artifact_id))
        self.assertEqual(
            cold_owner.index.node(direct.artifact_id).immediate_dependencies,
            (new_time,),
        )

    def test_changed_direct_context_revalidation_holds_child_until_equal_rebuild(self):
        _case, owner, host, invalidation, accepted_event_id = self._registered_owner()
        direct = owner.index.node("frame:context-direct")
        new_time = DependencyRef(
            DependencyKind.TIME,
            "time:asof:context:" + invalidation.new_context_digest)
        changed = _signed_context_result(
            direct,
            invalidation=invalidation,
            accepted_event_id=accepted_event_id,
            dependencies=(new_time,),
            digest="d" * 64,
        )
        with shape_patch():
            host.record_context_revalidation(
                ContextRevalidationFrontier((changed,)))

        self.assertIsNone(require_pending_corrections(owner, direct.artifact_id))
        with self.assertRaises(BilqisError) as held:
            require_pending_corrections(owner, "motif:context-descendant")
        self.assertEqual(held.exception.context["reason"], "BAMF_C09_ARTIFACT_HELD")

        descendant = owner.index.node("motif:context-descendant")
        child = _signed_context_result(
            descendant,
            invalidation=invalidation,
            accepted_event_id=accepted_event_id,
        )
        with shape_patch():
            host.record_context_revalidation(
                ContextRevalidationFrontier((child,)))
        self.assertIsNone(
            require_pending_corrections(owner, descendant.artifact_id))

        admission._EXECUTION_CACHE_OWNER.entries.clear()
        _RUNTIME_OWNER.clear()

    def test_expired_context_revalidation_marks_direct_ineligible_then_propagates(self):
        case = source_owned_temporal_case()
        source_ref = DependencyRef(
            DependencyKind.SOURCE, "source:expiry-direct")
        direct = ArtifactNode(
            "frame:expiry-direct", ArtifactKind.PACKED_FRAME, "a" * 64, True,
            tuple(sorted((
                source_ref,
                DependencyRef(
                    DependencyKind.TIME,
                    "time:asof:context:" + case.previous.digest),
            ))),
            impact=3, exigency=3,
        )
        child = ArtifactNode(
            "motif:expiry-child", ArtifactKind.MOTIF, "b" * 64, True,
            (direct.reference,), impact=2, exigency=2,
        )
        owner = _ContextOwner((direct, child))
        cache = self._publish()
        with shape_patch():
            register_accepted_target(
                self.run, cache.accepted_manifest_sha256,
                "TEST_EXPIRY", owner,
                lambda current, event, source_authority: _route(
                    current, event, source_authority),
                AUTHORITY,
            )
            host = AcceptedRuntimeHost(self.run, AUTHORITY)
            transition = host.record_context_transition(
                case.previous, case.contexts)
        invalidation = transition.invalidations[0]
        self.assertIsNone(invalidation.new_context_digest)
        accepted_event_id = read_records(
            self.run, cache.accepted_manifest_sha256)[-1]["event_id"]
        expired = _signed_context_result(
            direct,
            invalidation=invalidation,
            accepted_event_id=accepted_event_id,
            dependencies=(source_ref,),
            eligible=False,
        )
        with shape_patch():
            host.record_context_revalidation(
                ContextRevalidationFrontier((expired,)))
        self.assertFalse(owner.index.node(direct.artifact_id).eligible)
        self.assertEqual(
            owner.index.node(direct.artifact_id).immediate_dependencies,
            (source_ref,))
        with self.assertRaises(BilqisError) as held:
            require_pending_corrections(owner, child.artifact_id)
        self.assertEqual(held.exception.context["reason"], "BAMF_C09_ARTIFACT_HELD")

    def test_context_revalidation_rejects_wrong_invalidation_receipt(self):
        _case, owner, host, invalidation, _accepted_event_id = self._registered_owner()
        direct = owner.index.node("frame:context-direct")
        new_time = DependencyRef(
            DependencyKind.TIME,
            "time:asof:context:" + invalidation.new_context_digest)
        result = _signed_context_result(
            direct,
            invalidation=invalidation,
            accepted_event_id="9" * 64,
            dependencies=(new_time,),
        )
        with shape_patch(), self.assertRaises(BilqisError) as rejected:
            host.record_context_revalidation(
                ContextRevalidationFrontier((result,)))
        self.assertEqual(
            rejected.exception.context["reason"],
            "BAMF_C09_CONTEXT_REVALIDATION_INVALIDATION_MISSING",
        )

if __name__ == "__main__":
    unittest.main()
