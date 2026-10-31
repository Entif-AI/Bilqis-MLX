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
        def test_post_remediation_stale_replay_escalates_but_new_evidence_does_not(self):
            index, source_a, _ = _chain()
            correction = _event(source_a)
            remediation = RemediationReceipt(
                remediation_id="remediation:alpha",
                correction_event_id=correction.event_id,
                correction_receipt_sha256=correction.source_receipt_sha256,
                original_actor_id="actor:alpha",
                original_source_event_id="event:planned",
                original_source_time=570,
                superseded_fact_digest="a" * 64,
                superseded_source_receipt_sha256="1" * 64,
                affected_artifact_ids=("motif:alpha",),
                retained_generation_sha256="9" * 64,
                completed_at=650, status=RemediationStatus.COMPLETED,
            )
            stale = DerivedClaim(
                claim_id="claim:stale", actor_id="actor:alpha",
                source_event_id="event:planned", source_time=570,
                source_receipt_sha256="1" * 64,
                fact_digest="a" * 64, observed_at=660,
                derived_path=(
                    "feature:alpha", "frame:alpha", "motif:alpha",
                    "cache:alpha", "composition:alpha", "capability:alpha",
                ),
            )
            ledger = RequalificationLedger((
                CapabilitySupport(
                    capability_id="capability:alpha",
                    support_artifact_ids=("capability:alpha",),
                    source_anchor_ids=("source:alpha",),
                    retained_generation_sha256="9" * 64,
                    observation_ids=("observation:historical:1",),
                    status=RequalificationStatus.QUALIFIED,
                ),
            ))
            result = escalate_stale_replay(remediation, stale, correction,
                                           index, ledger)
            self.assertIsNotNone(result)
            self.assertEqual(result.fault.reason_code,
                             "BAMF_C09_PROPAGATION_REPAIR_FAILED")
            self.assertEqual(result.fault.original_source_event_id,
                             "event:planned")
            self.assertEqual(result.fault.correction_event_id,
                             correction.event_id)
            self.assertEqual(result.fault.offending_derived_path,
                             stale.derived_path)
            self.assertEqual(result.queue.held_artifact_ids, (
                "cache:alpha", "capability:alpha", "composition:alpha",
                "motif:alpha"))
            self.assertEqual(result.requalification.ledger.capability(
                "capability:alpha").status,
                RequalificationStatus.REQUALIFICATION_REQUIRED)
            self.assertEqual(result.requalification.ledger.capability(
                "capability:alpha").retained_generation_sha256, "9" * 64)
            self.assertEqual(ledger.capability("capability:alpha").status,
                             RequalificationStatus.QUALIFIED)
            relabelled = replace(
                stale, claim_id="claim:relabelled",
                source_event_id="event:relabelled")
            self.assertIsNotNone(escalate_stale_replay(
                remediation, relabelled, correction, index, ledger))
            receipt_relabelled = replace(
                stale, claim_id="claim:receipt-relabelled",
                source_receipt_sha256="2" * 64)
            self.assertIsNotNone(escalate_stale_replay(
                remediation, receipt_relabelled, correction, index, ledger))
            self.assertEqual(escalate_stale_replay(
                remediation, replace(stale, observed_at=640),
                correction, index, ledger), None)
            self.assertIsNone(escalate_stale_replay(
                replace(remediation, status=RemediationStatus.PENDING),
                stale, correction, index, ledger))
            new_evidence = replace(
                stale, claim_id="claim:new", actor_id="actor:beta",
                source_event_id="event:new", source_time=700,
                source_receipt_sha256="2" * 64, observed_at=705)
            self.assertIsNone(escalate_stale_replay(
                remediation, new_evidence, correction, index, ledger))
            self.assertIsNone(escalate_stale_replay(
                remediation, replace(stale, derived_path=("feature:beta",)),
                correction, index, ledger))
            with self.assertRaises(BilqisError) as caught:
                escalate_stale_replay(
                    remediation, replace(stale, derived_path=(
                        "feature:beta", "motif:alpha")),
                    correction, index, ledger)
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C09_DERIVED_PATH_INVALID")
            with self.assertRaises(BilqisError) as caught:
                escalate_stale_replay(
                    replace(remediation, completed_at=620),
                    stale, correction, index, ledger)
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C09_REMEDIATION_BEFORE_CORRECTION")

        def test_concurrent_corrections_keep_branches_until_explicit_supersession(self):
            source = _ref(DependencyKind.SOURCE, "source:meeting")
            original = _event(source)
            alternative = _sign_event(replace(
                original, event_id="correction:synthetic:2",
                new_evidence_sha256="d" * 64,
                source_receipt_sha256="e" * 64))
            branches = add_correction(CorrectionBranches(source, ()), original)
            concurrent = add_correction(branches, alternative)
            self.assertEqual(
                tuple(item.event.event_id for item in concurrent.active),
                ("correction:synthetic:1", "correction:synthetic:2"))
            self.assertEqual(add_correction(concurrent, alternative), concurrent)
            with self.assertRaises(BilqisError) as caught:
                add_correction(concurrent, _sign_event(replace(
                    original, new_evidence_sha256="0" * 64)))
            self.assertEqual(caught.exception.context["reason"],
                             "BAMF_C09_CORRECTION_EVENT_ID_CONFLICT")
            superseding = _sign_event(replace(
                original, event_id="correction:synthetic:3",
                supersedes_event_ids=("correction:synthetic:1", "correction:synthetic:2"),
                new_evidence_sha256="9" * 64))
            resolved = add_correction(
                concurrent, superseding,
                supersedes_event_ids=("correction:synthetic:1",
                                      "correction:synthetic:2"))
            self.assertEqual(tuple(item.event.event_id for item in resolved.active),
                             ("correction:synthetic:3",))
            self.assertEqual(len(resolved.branches), 3)
            self.assertEqual(len(concurrent.branches), 2)
