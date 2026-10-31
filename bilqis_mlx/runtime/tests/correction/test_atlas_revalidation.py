"""Structural test shard from test_atlas_revalidation.py; assertions preserved."""
from __future__ import annotations
from dataclasses import replace
import unittest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind,
    DependencyRef,
)
from bilqis_mlx.runtime.atlas_revalidation import (
    CorrectionEvent, RevalidatedArtifact, RevalidationFrontier,
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
    advance_revalidation as _advance_revalidation,
    apply_correction as _apply_correction,
    next_revalidation_task, read_artifact,
    revalidate_node as _revalidate_node,
)
from bilqis_mlx.runtime.atlas_requalification import (
    CapabilitySupport, CorrectionBranches, RequalificationLedger,
    RequalificationStatus, add_correction as _add_correction,
    mark_affected_capabilities,
)
from bilqis_mlx.runtime.atlas_temporal_revalidation import (
    DerivedClaim, RemediationReceipt, RemediationStatus, TemporalEvent,
    TemporalEventKind, TemporalStatus, bind_as_of_dependency,
    escalate_stale_replay as _escalate_stale_replay, project_as_of,
)
from bilqis_mlx.runtime.tests.correction.test_atlas_revalidation_helpers import (_SOURCE_OWNER, _TEST_PUBLIC, _chain, _event, _node, _ref, _result, _sign_event, add_correction, advance_revalidation, apply_correction, escalate_stale_replay, revalidate_node)

class AtlasRevalidationTests(unittest.TestCase):
        def test_authentic_old_revalidation_receipt_cannot_clear_new_correction_hold(self):
            index, source, _ = _chain()
            current = _event(source)
            queue = apply_correction(current, index)
            node = index.node("feature:alpha")
            older = _sign_event(replace(
                current, event_id="correction:older",
                source_receipt_sha256="f" * 64))
            stale = revalidate_node(
                node, _result(node, correction=older))
            self.assertFalse(stale.changed)
            with self.assertRaises(BilqisError) as caught:
                advance_revalidation(index, queue, stale)
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C09_REVALIDATION_CORRECTION_MISMATCH")
            self.assertEqual(queue.held_artifact_ids, ("feature:alpha",))
            fresh = revalidate_node(
                node, _result(node, correction=current))
            progressed = advance_revalidation(index, queue, fresh)
            self.assertEqual(progressed.queue.pending, ())
            self.assertEqual(progressed.index.node("feature:alpha"), node)

        def test_forged_source_owner_and_revalidation_receipts_cannot_mutate_state(self):
            index, source, _ = _chain()
            event = _event(source)
            with self.assertRaises(BilqisError) as caught:
                _apply_correction(event, index)
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C09_SOURCE_AUTHORITY_MISSING")
            with self.assertRaises(BilqisError) as caught:
                apply_correction(replace(
                    event, source_owner="unrelated:caller"), index)
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C09_SOURCE_AUTHORITY_UNREGISTERED")
            with self.assertRaises(BilqisError) as caught:
                apply_correction(_sign_event(replace(
                    event, dependency=_ref(
                        DependencyKind.SOURCE, "foreign:unowned"))), index)
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C09_SOURCE_AUTHORITY_SCOPE_MISMATCH")
            narrow = SourceAuthorityRegistry((
                SourceAuthorityKey(
                    _SOURCE_OWNER, _TEST_PUBLIC, (
                        SourceAuthorityScope(
                            DependencyKind.ARTIFACT, "feature:"),
                        SourceAuthorityScope(
                            DependencyKind.SOURCE, "source:"),
                    )),
            ))
            cross_pair = _sign_event(replace(
                event, dependency=DependencyRef(
                    DependencyKind.ARTIFACT, "source:alpha")))
            with self.assertRaises(BilqisError) as caught:
                _apply_correction(cross_pair, index, narrow)
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C09_SOURCE_AUTHORITY_SCOPE_MISMATCH")
            node = index.node("feature:alpha")
            forged = replace(
                _result(node).results[0],
                content_digest="b" * 64, eligible=False,
                source_receipt_sha256="3" * 64)
            with self.assertRaises(BilqisError) as caught:
                revalidate_node(node, RevalidationFrontier((forged,)))
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C09_SOURCE_SIGNATURE_INVALID")
            valid = revalidate_node(node, _result(node, digest="b" * 64))
            with self.assertRaises(BilqisError) as caught:
                advance_revalidation(
                    index, apply_correction(event, index),
                    replace(valid, new_content_digest="c" * 64))
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C09_SOURCE_SIGNATURE_INVALID")
