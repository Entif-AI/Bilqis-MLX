"""Same-run accepted correction/requalification witness for #1300."""
from __future__ import annotations

from dataclasses import replace

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.tests.test_atlas_salience import _KEY, _OWNER
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.atlas_capability_support_owner import (
    load_capability_support_owner,
)
from bilqis_mlx.runtime.atlas_revalidation import (
    CorrectionEvent,
    RevalidatedArtifact,
    RevalidationFrontier,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind


def _salience_source_fact(owner):
    return next((
        ref
        for node in owner.index.nodes
        for ref in node.immediate_dependencies
        if ref.kind is DependencyKind.SOURCE
        and ref.key.startswith("salience-fact:")
    ), None)


def hold_successor_only(test, run_dir, *, target: str, successor: str):
    """Hold learned successor support through accepted C09 without neural mutation."""
    target_owner = load_capability_support_owner(run_dir, target)
    successor_owner = load_capability_support_owner(run_dir, successor)
    target_owner.require(target)
    successor_owner.require(successor)
    target_before = (
        target_owner.support,
        target_owner.ledger,
        target_owner.index,
    )
    dependency = _salience_source_fact(successor_owner)
    test.assertIsNotNone(dependency)
    target_dependencies = {
        ref
        for node in target_owner.index.nodes
        for ref in node.immediate_dependencies
    }
    test.assertNotIn(dependency, target_dependencies)

    unsigned = CorrectionEvent(
        event_id="fixture:1300-successor-source-correction",
        dependency=dependency,
        source_owner=_OWNER,
        source_receipt_sha256="f" * 64,
        old_evidence_sha256="a" * 64,
        new_evidence_sha256="b" * 64,
        source_time=1,
        effective_time=2,
        observed_at=3,
        recorded_at=4,
        reason_code="SOURCE_CORRECTION",
        source_signature_hex="0" * 128,
    )
    event = replace(
        unsigned,
        source_signature_hex=_KEY.sign(unsigned.signing_bytes()).hex(),
    )
    event_id = AcceptedRuntimeHost(run_dir).record_correction(event)
    target_after_correction = load_capability_support_owner(run_dir, target)
    target_after_correction.require(target)
    test.assertEqual(
        (target_after_correction.support,
         target_after_correction.ledger,
         target_after_correction.index),
        target_before,
    )
    with test.assertRaises(BilqisError):
        successor_owner.require(successor)
    node = successor_owner.current_node
    unsigned_result = RevalidatedArtifact(
        artifact_id=node.artifact_id,
        immediate_dependencies=node.immediate_dependencies,
        content_digest="e" * 64,
        eligible=True,
        source_receipt_sha256="c" * 64,
        correction_event_id=event.event_id,
        correction_receipt_sha256=event.source_receipt_sha256,
        source_owner=_OWNER,
        source_signature_hex="0" * 128,
    )
    result = replace(
        unsigned_result,
        source_signature_hex=_KEY.sign(unsigned_result.signing_bytes()).hex(),
    )
    AcceptedRuntimeHost(run_dir).record_revalidation(
        RevalidationFrontier((result,)))
    recovered = load_capability_support_owner(run_dir, successor)
    target_after_revalidation = load_capability_support_owner(run_dir, target)
    target_after_revalidation.require(target)
    test.assertEqual(
        (target_after_revalidation.support,
         target_after_revalidation.ledger,
         target_after_revalidation.index),
        target_before,
    )
    test.assertEqual(recovered.support.status, "REQUALIFICATION_REQUIRED")
    test.assertIsNotNone(recovered.queue)
    test.assertEqual(len(recovered.ledger.pending_source_tasks), 1)
    test.assertEqual(
        recovered.ledger.pending_source_tasks[0].capability_id,
        successor,
    )
    return event_id, dependency, recovered
