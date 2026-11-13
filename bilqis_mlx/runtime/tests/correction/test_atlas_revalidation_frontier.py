"""Source-authenticated revalidation frontier behavior."""
import unittest

from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    ArtifactKind, BilqisError, DependencyIndex, DependencyKind,
    _chain, _event, _node, _ref,
    _result, advance_revalidation, apply_correction, next_revalidation_task,
    read_artifact, replace, revalidate_node,
)


class RevalidationFrontierTests(unittest.TestCase):
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

    def test_transitive_held_ancestor_blocks_high_priority_descendant(self):
        source = _ref(DependencyKind.SOURCE, "source:x")
        a = _node("a", ArtifactKind.ATLAS_FEATURE, (source,),
                  exigency=0, impact=0)
        b = _node("b", ArtifactKind.PACKED_FRAME, (a.reference,),
                  exigency=1, impact=1)
        c = _node("c", ArtifactKind.MOTIF, tuple(sorted((
            source, b.reference))), exigency=4, impact=4)
        index = DependencyIndex.build((a, b, c))
        queue = apply_correction(_event(source), index)
        self.assertEqual(tuple(task.artifact_id for task in queue.pending),
                         ("c", "a"))
        self.assertEqual(next_revalidation_task(index, queue).artifact_id, "a")
        with self.assertRaises(BilqisError) as caught:
            advance_revalidation(index, queue, revalidate_node(c, _result(c)))
        self.assertEqual(caught.exception.context["reason"],
                         "BAMF_C09_REVALIDATION_OUT_OF_ORDER")

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
