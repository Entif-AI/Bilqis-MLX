"""C09.1 correction propagation against synthetic source-owned receipts."""
from __future__ import annotations

from dataclasses import replace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.cognitive_dependencies import (
    ArtifactKind, ArtifactNode, DependencyIndex, DependencyKind,
    DependencyRef,
)
from bilqis_mlx.runtime.atlas_revalidation import (
    CapabilitySupport, CorrectionBranches, CorrectionEvent,
    RequalificationLedger, RequalificationStatus,
    RevalidatedArtifact, RevalidationFrontier, add_correction,
    advance_revalidation, apply_correction, mark_affected_capabilities,
    next_revalidation_task, read_artifact, revalidate_node,
)
from bilqis_mlx.runtime.atlas_temporal_revalidation import (
    DerivedClaim, RemediationReceipt, RemediationStatus, TemporalEvent,
    TemporalEventKind, TemporalStatus, bind_as_of_dependency,
    escalate_stale_replay, project_as_of,
)


def _ref(kind: DependencyKind, key: str) -> DependencyRef:
    return DependencyRef(kind, key)


def _node(
    key: str, kind: ArtifactKind, deps: tuple[DependencyRef, ...],
    *, impact: int = 1, exigency: int = 1,
) -> ArtifactNode:
    return ArtifactNode(
        artifact_id=key, kind=kind, content_digest="a" * 64,
        eligible=True, immediate_dependencies=deps,
        impact=impact, exigency=exigency,
    )


def _event(dependency: DependencyRef) -> CorrectionEvent:
    return CorrectionEvent(
        event_id="correction:synthetic:1",
        dependency=dependency,
        source_owner="synthetic:source-authority",
        source_receipt_sha256="f" * 64,
        old_evidence_sha256="a" * 64,
        new_evidence_sha256="b" * 64,
        source_time=570, effective_time=620, observed_at=625,
        recorded_at=630, reason_code="SOURCE_CORRECTION",
    )


def _result(node: ArtifactNode, *, digest: str = "a" * 64,
            eligible: bool = True) -> RevalidationFrontier:
    return RevalidationFrontier((
        RevalidatedArtifact(
            artifact_id=node.artifact_id,
            immediate_dependencies=node.immediate_dependencies,
            content_digest=digest, eligible=eligible,
            source_receipt_sha256="c" * 64,
        ),
    ))


def _chain() -> tuple[DependencyIndex, DependencyRef, DependencyRef]:
    source_a = _ref(DependencyKind.SOURCE, "source:alpha")
    source_b = _ref(DependencyKind.SOURCE, "source:beta")
    feature = _node("feature:alpha", ArtifactKind.ATLAS_FEATURE, (source_a,))
    frame = _node("frame:alpha", ArtifactKind.PACKED_FRAME, (
        _ref(DependencyKind.ARTIFACT, feature.artifact_id),))
    motif = _node("motif:alpha", ArtifactKind.MOTIF, (
        _ref(DependencyKind.ARTIFACT, frame.artifact_id),))
    cache = _node("cache:alpha", ArtifactKind.EXACT_CACHE, (
        _ref(DependencyKind.ARTIFACT, motif.artifact_id),))
    composition = _node("composition:alpha", ArtifactKind.OPERATOR_COMPOSITION, (
        _ref(DependencyKind.ARTIFACT, cache.artifact_id),))
    capability = _node("capability:alpha", ArtifactKind.CAPABILITY_SUPPORT, (
        _ref(DependencyKind.ARTIFACT, composition.artifact_id),))
    unrelated = _node("feature:beta", ArtifactKind.ATLAS_FEATURE, (source_b,))
    return DependencyIndex.build((
        feature, frame, motif, cache, composition, capability, unrelated,
    )), source_a, source_b


class AtlasRevalidationTests(unittest.TestCase):
    def test_temporal_projection_distinguishes_plan_silence_negative_and_correction(self):
        planned = TemporalEvent(
            event_id="event:planned", actor_id="actor:alpha",
            kind=TemporalEventKind.PLANNED, fact_digest="a" * 64,
            source_receipt_sha256="1" * 64,
            source_time=570, effective_from=570, effective_until=None,
            observed_at=565, recorded_at=565, expected_report_by=585,
        )
        nonoccurrence = TemporalEvent(
            event_id="event:nonoccurrence", actor_id="actor:alpha",
            kind=TemporalEventKind.EXPLICIT_NONOCCURRENCE,
            fact_digest="b" * 64, source_receipt_sha256="2" * 64,
            source_time=600, effective_from=600, effective_until=None,
            observed_at=601, recorded_at=601,
            supersedes_event_id="event:planned",
        )
        corrected = TemporalEvent(
            event_id="event:corrected", actor_id="actor:alpha",
            kind=TemporalEventKind.CORRECTION, fact_digest="c" * 64,
            source_receipt_sha256="3" * 64,
            source_time=620, effective_from=620, effective_until=None,
            observed_at=621, recorded_at=621,
            supersedes_event_id="event:nonoccurrence",
        )
        events = (planned, nonoccurrence, corrected)
        before = project_as_of(events, actor_id="actor:alpha", as_of=575)
        missing = project_as_of(events, actor_id="actor:alpha", as_of=590)
        explicit = project_as_of(events, actor_id="actor:alpha", as_of=605)
        correction = project_as_of(events, actor_id="actor:alpha", as_of=625)
        self.assertEqual(
            (before.status, missing.status, explicit.status, correction.status),
            (TemporalStatus.PLANNED, TemporalStatus.MISSING_EXPECTED_REPORT,
             TemporalStatus.EXPLICIT_NONOCCURRENCE, TemporalStatus.CORRECTED))
        self.assertEqual(correction.fact_digest, "c" * 64)
        self.assertEqual(missing.fact_digest, "a" * 64)
        self.assertNotEqual(before.time_dependency, missing.time_dependency)
        self.assertEqual(
            project_as_of((planned,), actor_id="actor:alpha", as_of=590),
            missing)
        self.assertEqual(missing.time_dependency.kind, DependencyKind.TIME)
        self.assertEqual(
            project_as_of(events, actor_id="actor:alpha", as_of=567).status,
            TemporalStatus.PLANNED)
        changed_deadline = replace(planned, expected_report_by=600)
        self.assertNotEqual(
            project_as_of((changed_deadline,), actor_id="actor:alpha",
                          as_of=575).time_dependency,
            before.time_dependency)
        expiring = replace(planned, effective_until=580)
        self.assertEqual(
            project_as_of((expiring,), actor_id="actor:alpha",
                          as_of=580).status, TemporalStatus.UNKNOWN)
        self.assertNotEqual(
            project_as_of((expiring,), actor_id="actor:alpha",
                          as_of=575).time_dependency,
            project_as_of((expiring,), actor_id="actor:alpha",
                          as_of=580).time_dependency)
        concurrent = replace(
            corrected, event_id="event:concurrent",
            supersedes_event_id=None, fact_digest="d" * 64)
        self.assertEqual(project_as_of(
            (planned, nonoccurrence, corrected, concurrent),
            actor_id="actor:alpha", as_of=625).status,
            TemporalStatus.CONFLICTING_ALTERNATIVES)
        retroactive = replace(corrected, effective_from=600)
        self.assertEqual(project_as_of(
            (planned, nonoccurrence, retroactive),
            actor_id="actor:alpha", as_of=610).status,
            TemporalStatus.EXPLICIT_NONOCCURRENCE)
        cache = _node("cache:asof", ArtifactKind.EXACT_CACHE, (
            _ref(DependencyKind.SOURCE, "source:plan"),))
        bound = bind_as_of_dependency(cache, before)
        self.assertEqual(apply_correction(
            _event(before.time_dependency),
            DependencyIndex.build((bound,))).held_artifact_ids,
            ("cache:asof",))
        refreshed = bind_as_of_dependency(bound, missing)
        self.assertNotIn(before.time_dependency,
                         refreshed.immediate_dependencies)
        self.assertIn(missing.time_dependency,
                      refreshed.immediate_dependencies)

    def test_post_remediation_stale_replay_escalates_but_new_evidence_does_not(self):
        index, source_a, _ = _chain()
        correction = _event(source_a)
        remediation = RemediationReceipt(
            remediation_id="remediation:alpha",
            correction_event_id=correction.event_id,
            correction_receipt_sha256=correction.source_receipt_sha256,
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
        alternative = replace(
            original, event_id="correction:synthetic:2",
            new_evidence_sha256="d" * 64,
            source_receipt_sha256="e" * 64)
        branches = add_correction(CorrectionBranches(source, ()), original)
        concurrent = add_correction(branches, alternative)
        self.assertEqual(
            tuple(item.event.event_id for item in concurrent.active),
            ("correction:synthetic:1", "correction:synthetic:2"))
        self.assertEqual(add_correction(concurrent, alternative), concurrent)
        with self.assertRaises(BilqisError) as caught:
            add_correction(concurrent, replace(
                original, new_evidence_sha256="0" * 64))
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_CORRECTION_EVENT_ID_CONFLICT")
        superseding = replace(
            original, event_id="correction:synthetic:3",
            new_evidence_sha256="9" * 64)
        resolved = add_correction(
            concurrent, superseding,
            supersedes_event_ids=("correction:synthetic:1",
                                  "correction:synthetic:2"))
        self.assertEqual(tuple(item.event.event_id for item in resolved.active),
                         ("correction:synthetic:3",))
        self.assertEqual(len(resolved.branches), 3)
        self.assertEqual(len(concurrent.branches), 2)

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

    def test_correction_holds_only_direct_dependents_then_stops_at_equal_output(self):
        index, source_a, source_b = _chain()
        original = index
        queue = apply_correction(_event(source_a), index)
        self.assertEqual(queue.held_artifact_ids, ("feature:alpha",))
        self.assertEqual(tuple(item.artifact_id for item in queue.pending),
                         ("feature:alpha",))
        self.assertEqual(read_artifact(index, queue, "feature:beta").artifact_id,
                         "feature:beta")
        with self.assertRaises(BilqisError) as caught:
            read_artifact(index, queue, "feature:alpha")
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_ARTIFACT_HELD")
        with self.assertRaises(BilqisError) as caught:
            read_artifact(index, queue, "frame:alpha")
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_ARTIFACT_DEPENDENCY_HELD")

        feature = index.node("feature:alpha")
        changed = revalidate_node(feature, _result(feature, digest="b" * 64))
        self.assertTrue(changed.changed)
        progress = advance_revalidation(index, queue, changed)
        self.assertEqual(progress.queue.held_artifact_ids, ("frame:alpha",))
        self.assertEqual(progress.index.node("feature:alpha").content_digest,
                         "b" * 64)
        self.assertEqual(original.node("feature:alpha").content_digest,
                         "a" * 64)

        frame = progress.index.node("frame:alpha")
        same = revalidate_node(frame, _result(frame))
        self.assertFalse(same.changed)
        stopped = advance_revalidation(progress.index, progress.queue, same)
        self.assertEqual(stopped.queue.pending, ())
        self.assertEqual(stopped.queue.held_artifact_ids, ())
        self.assertEqual(stopped.index.node("motif:alpha").content_digest,
                         "a" * 64)
        self.assertEqual(apply_correction(_event(source_b), index).held_artifact_ids,
                         ("feature:beta",))

    def test_revoked_motif_is_held_before_read_and_remains_ineligible(self):
        index, _, _ = _chain()
        motif = index.node("motif:alpha")
        rights = _ref(DependencyKind.RIGHTS, "rights:motif")
        index = index.replace_node(replace(
            motif, immediate_dependencies=tuple(sorted((
                *motif.immediate_dependencies, rights,
            )))))
        queue = apply_correction(_event(rights), index)
        with self.assertRaises(BilqisError) as caught:
            read_artifact(index, queue, motif.artifact_id)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_ARTIFACT_HELD")
        result = revalidate_node(index.node(motif.artifact_id), _result(
            index.node(motif.artifact_id), eligible=False))
        progress = advance_revalidation(index, queue, result)
        self.assertEqual(progress.queue.held_artifact_ids, ("cache:alpha",))
        with self.assertRaises(BilqisError) as caught:
            read_artifact(progress.index, progress.queue, motif.artifact_id)
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_ARTIFACT_INELIGIBLE")
        with self.assertRaises(BilqisError) as caught:
            read_artifact(progress.index, progress.queue, "capability:alpha")
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_ARTIFACT_DEPENDENCY_HELD")
        cache = progress.index.node("cache:alpha")
        after_cache = advance_revalidation(
            progress.index, progress.queue, revalidate_node(cache, _result(cache)))
        self.assertEqual(after_cache.queue.pending, ())
        with self.assertRaises(BilqisError) as caught:
            read_artifact(after_cache.index, after_cache.queue,
                          "capability:alpha")
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_ARTIFACT_DEPENDENCY_INELIGIBLE")

    def test_topology_overrides_priority_until_upstream_hold_clears(self):
        source = _ref(DependencyKind.SOURCE, "source:shared")
        feature = _node("feature", ArtifactKind.ATLAS_FEATURE, (source,),
                        impact=0, exigency=0)
        frame = _node("frame", ArtifactKind.PACKED_FRAME, tuple(sorted((
            source, feature.reference))), impact=4, exigency=4)
        index = DependencyIndex.build((feature, frame))
        queue = apply_correction(_event(source), index)
        self.assertEqual(tuple(item.artifact_id for item in queue.pending),
                         ("frame", "feature"))
        self.assertEqual(next_revalidation_task(index, queue).artifact_id,
                         "feature")
        with self.assertRaises(BilqisError) as caught:
            advance_revalidation(index, queue, revalidate_node(
                frame, _result(frame)))
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_REVALIDATION_OUT_OF_ORDER")
        progress = advance_revalidation(index, queue, revalidate_node(
            feature, _result(feature)))
        self.assertEqual(next_revalidation_task(
            progress.index, progress.queue).artifact_id, "frame")
        finished = advance_revalidation(
            progress.index, progress.queue, revalidate_node(frame, _result(frame)))
        self.assertEqual(finished.queue.pending, ())
        self.assertEqual(read_artifact(finished.index, finished.queue, "frame"),
                         frame)

    def test_priority_uses_exigency_then_impact_then_stable_id(self):
        source = _ref(DependencyKind.SOURCE, "source:one")
        index = DependencyIndex.build((
            _node("a", ArtifactKind.ATLAS_FEATURE, (source,), impact=4, exigency=1),
            _node("b", ArtifactKind.PACKED_FRAME, (source,), impact=1, exigency=4),
            _node("c", ArtifactKind.MOTIF, (source,), impact=3, exigency=4),
            _node("d", ArtifactKind.EXACT_CACHE, (source,), impact=3, exigency=4),
        ))
        queue = apply_correction(_event(source), index)
        self.assertEqual(tuple(task.artifact_id for task in queue.pending),
                         ("c", "d", "b", "a"))
        self.assertEqual(queue.held_artifact_ids, ("a", "b", "c", "d"))

    def test_unknown_dependency_causes_no_rebuild(self):
        index, _, _ = _chain()
        queue = apply_correction(
            _event(_ref(DependencyKind.SOURCE, "source:unrelated")), index)
        self.assertEqual(queue.pending, ())
        self.assertEqual(queue.held_artifact_ids, ())
        self.assertEqual(index.node("capability:alpha").eligible, True)

    def test_source_operator_release_policy_time_rights_edges_are_independent(self):
        refs = tuple(
            _ref(kind, "fixture:" + kind.value.lower())
            for kind in (
                DependencyKind.SOURCE, DependencyKind.OPERATOR,
                DependencyKind.RELEASE, DependencyKind.POLICY,
                DependencyKind.TIME, DependencyKind.RIGHTS,
            )
        )
        nodes = tuple(_node(
            "artifact:" + ref.kind.value.lower(),
            ArtifactKind.EXACT_CACHE, (ref,),
        ) for ref in refs)
        index = DependencyIndex.build(nodes)
        for ref in refs:
            with self.subTest(kind=ref.kind):
                queue = apply_correction(_event(ref), index)
                self.assertEqual(
                    queue.held_artifact_ids,
                    ("artifact:" + ref.kind.value.lower(),))
                self.assertEqual(
                    len(index.direct_dependents(ref)), 1)

    def test_reverse_index_contains_only_immediate_edges_for_all_six_artifact_kinds(self):
        index, source_a, _ = _chain()
        self.assertEqual(tuple(node.artifact_id for node in
                               index.direct_dependents(source_a)),
                         ("feature:alpha",))
        self.assertEqual(tuple(node.artifact_id for node in
                               index.direct_dependents(
                                   _ref(DependencyKind.ARTIFACT, "feature:alpha"))),
                         ("frame:alpha",))
        self.assertEqual(tuple(node.artifact_id for node in
                               index.direct_dependents(
                                   _ref(DependencyKind.ARTIFACT, "frame:alpha"))),
                         ("motif:alpha",))
        self.assertEqual(tuple(node.artifact_id for node in
                               index.direct_dependents(
                                   _ref(DependencyKind.ARTIFACT, "motif:alpha"))),
                         ("cache:alpha",))
        self.assertEqual(tuple(node.artifact_id for node in
                               index.direct_dependents(
                                   _ref(DependencyKind.ARTIFACT, "cache:alpha"))),
                         ("composition:alpha",))
        self.assertEqual(tuple(node.artifact_id for node in
                               index.direct_dependents(
                                   _ref(DependencyKind.ARTIFACT, "composition:alpha"))),
                         ("capability:alpha",))
        self.assertEqual(len(index.reverse_edges), 7)

    def test_invalid_graph_and_unqualified_frontier_fail_closed(self):
        one = _node("one", ArtifactKind.EXACT_CACHE, (
            _ref(DependencyKind.ARTIFACT, "two"),))
        two = _node("two", ArtifactKind.MOTIF, (
            _ref(DependencyKind.ARTIFACT, "one"),))
        with self.assertRaises(BilqisError) as caught:
            DependencyIndex.build((one, two))
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_DEPENDENCY_CYCLE")
        index, source_a, _ = _chain()
        node = index.node("feature:alpha")
        with self.assertRaises(BilqisError) as caught:
            revalidate_node(node, RevalidationFrontier(()))
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_REVALIDATION_EVIDENCE_MISSING")
        bad = replace(_result(node).results[0],
                      immediate_dependencies=(
                          _ref(DependencyKind.SOURCE, "source:foreign"),))
        with self.assertRaises(BilqisError) as caught:
            revalidate_node(node, RevalidationFrontier((bad,)))
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_REVALIDATION_DEPENDENCY_DRIFT")
        queue = apply_correction(_event(source_a), index)
        with self.assertRaises(BilqisError) as caught:
            advance_revalidation(index, queue, revalidate_node(
                index.node("frame:alpha"), _result(index.node("frame:alpha"))))
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_REVALIDATION_OUT_OF_ORDER")


if __name__ == "__main__":
    unittest.main()
