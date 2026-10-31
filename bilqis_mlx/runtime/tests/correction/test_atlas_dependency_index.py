"""Source-authenticated dependency index behavior."""
import unittest

from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    ArtifactKind, BilqisError, DependencyIndex, DependencyKind,
    RevalidationFrontier, _chain, _event, _node,
    _ref, _result, advance_revalidation, apply_correction,
    replace, revalidate_node,
)


class DependencyIndexTests(unittest.TestCase):
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
