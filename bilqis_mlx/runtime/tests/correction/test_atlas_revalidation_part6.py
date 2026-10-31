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
