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
    CorrectionEvent, RevalidatedArtifact, RevalidationFrontier,
    advance_revalidation, apply_correction, next_revalidation_task,
    read_artifact, revalidate_node,
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
