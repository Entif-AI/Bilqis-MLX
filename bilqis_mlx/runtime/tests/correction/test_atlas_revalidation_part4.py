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
        def test_unsigned_supersession_cannot_retire_authenticated_alternatives(self):
            source = DependencyRef(DependencyKind.SOURCE, 'source:synthetic')
            original = _event(source)
            branches = add_correction(CorrectionBranches(source, ()), original)
            other = _sign_event(replace(original, event_id='correction:other'))
            with self.assertRaises(BilqisError):
                add_correction(branches, other, supersedes_event_ids=(original.event_id,))
            tampered = replace(other, supersedes_event_ids=(original.event_id,))
            with self.assertRaises(BilqisError) as caught:
                add_correction(branches, tampered, supersedes_event_ids=(original.event_id,))
            self.assertEqual(caught.exception.context['reason'], 'BAMF_C09_SOURCE_SIGNATURE_INVALID')

        def test_expiring_intermediate_correction_does_not_resurrect_ancestor(self):
            a = TemporalEvent('a', 'actor:x', TemporalEventKind.OBSERVED,
                'a' * 64, '1' * 64, 10, 10, None, 10, 10)
            b = replace(a, event_id='b', kind=TemporalEventKind.CORRECTION,
                fact_digest='b' * 64, effective_from=20, effective_until=30,
                source_time=20, observed_at=20, recorded_at=20, supersedes_event_id='a')
            c = replace(b, event_id='c', fact_digest='c' * 64, effective_from=25,
                effective_until=None, source_time=25, observed_at=25, recorded_at=25,
                supersedes_event_id='b')
            for time in (26, 31):
                result = project_as_of((a, b, c), actor_id='actor:x', as_of=time)
                self.assertEqual(result.status, TemporalStatus.CORRECTED)
                self.assertEqual(result.fact_digest, 'c' * 64)

        def test_invalidated_learned_support_queues_targeted_source_tasks_without_weight_edits(self):
            index, _, _ = _chain()
            motif = index.node("motif:alpha")
            rights = _ref(DependencyKind.RIGHTS, "rights:motif")
            index = index.replace_node(replace(
                motif, immediate_dependencies=tuple(sorted((
                    *motif.immediate_dependencies, rights,
                )))))
            queue = apply_correction(_event(rights), index)
            original_alpha = CapabilitySupport(
                capability_id="capability:alpha",
                support_artifact_ids=("capability:alpha",),
                source_anchor_ids=("source:alpha",),
                retained_generation_sha256="1" * 64,
                observation_ids=("observation:alpha:1",),
                status=RequalificationStatus.QUALIFIED,
            )
            original_beta = CapabilitySupport(
                capability_id="capability:beta",
                support_artifact_ids=("feature:beta",),
                source_anchor_ids=("source:beta",),
                retained_generation_sha256="2" * 64,
                observation_ids=("observation:beta:1",),
                status=RequalificationStatus.QUALIFIED,
            )
            ledger = RequalificationLedger((original_alpha, original_beta))
            update = mark_affected_capabilities(ledger, index, queue)
            self.assertEqual(update.affected_capability_ids,
                             ("capability:alpha",))
            self.assertEqual(update.ledger.capability(
                "capability:alpha").status,
                RequalificationStatus.REQUALIFICATION_REQUIRED)
            self.assertEqual(update.ledger.capability("capability:beta"),
                             original_beta)
            self.assertEqual(update.ledger.historical, (original_alpha,))
            self.assertEqual(update.ledger.capability(
                "capability:alpha").retained_generation_sha256, "1" * 64)
            self.assertEqual(update.ledger.capability(
                "capability:alpha").observation_ids,
                ("observation:alpha:1",))
            self.assertEqual(len(update.new_source_tasks), 1)
            self.assertEqual(update.new_source_tasks[0].source_anchor_ids,
                             ("source:alpha",))
            self.assertEqual(update.new_source_tasks[0].capability_id,
                             "capability:alpha")
            self.assertEqual(len(update.new_c10_intents), 1)
            self.assertEqual(update.new_c10_intents[0].namespace,
                             "bamf.c09.requalification")
            self.assertEqual(update.new_c10_intents[0].delivery_state,
                             "PENDING_C10")
            with self.assertRaises(BilqisError) as caught:
                replace(update.new_source_tasks[0], task_id="0" * 64)
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C09_SOURCE_TASK_INVALID")
            with self.assertRaises(BilqisError) as caught:
                replace(update.new_c10_intents[0], payload_digest="0" * 64)
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C09_C10_INTENT_INVALID")
            again = mark_affected_capabilities(update.ledger, index, queue)
            self.assertEqual(again.new_source_tasks, ())
            self.assertEqual(again.new_c10_intents, ())
            self.assertEqual(again.ledger, update.ledger)
            self.assertEqual(ledger.capability("capability:alpha"), original_alpha)

        def test_prior_unrelated_ineligibility_does_not_contaminate_new_correction(self):
            index, _, source_b = _chain()
            index = index.replace_node(replace(
                index.node("motif:alpha"), eligible=False))
            ledger = RequalificationLedger((
                CapabilitySupport(
                    capability_id="capability:alpha",
                    support_artifact_ids=("capability:alpha",),
                    source_anchor_ids=("source:alpha",),
                    retained_generation_sha256="1" * 64,
                    observation_ids=("observation:alpha:1",),
                    status=RequalificationStatus.QUALIFIED,
                ),
            ))
            unrelated = mark_affected_capabilities(
                ledger, index, apply_correction(_event(source_b), index))
            self.assertEqual(unrelated.affected_capability_ids, ())
            self.assertEqual(unrelated.new_source_tasks, ())
            self.assertEqual(unrelated.new_c10_intents, ())
            self.assertEqual(unrelated.ledger, ledger)
