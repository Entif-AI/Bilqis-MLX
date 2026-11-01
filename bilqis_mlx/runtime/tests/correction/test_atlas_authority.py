"""Source-authenticated authority behavior."""
import unittest

from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    BilqisError, DependencyKind, DependencyRef, RevalidationFrontier,
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope, _SOURCE_OWNER,
    _TEST_PUBLIC, _apply_correction, _chain, _event,
    _ref, _result, _sign_event, advance_revalidation,
    apply_correction, replace, revalidate_node,
)


class AuthorityTests(unittest.TestCase):
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
