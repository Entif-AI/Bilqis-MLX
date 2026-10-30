import unittest

from bilqis_mlx.factory.development import (
    DevelopmentalStaircase,
    DevelopmentalTarget,
    RepresentationLayer,
    UnderstandingProjection,
    post_boolean_staircase,
)


class DevelopmentalStaircaseTests(unittest.TestCase):
    def setUp(self):
        self.staircase = post_boolean_staircase()
        self.baseline = self.staircase.baseline_capabilities

    def test_post_boolean_route_is_candidate_only_and_stably_ordered(self):
        expected = (
            "DEV.LAW_SCHEMA",
            "DEV.TYPE_DISCIPLINE",
            "DEV.ORDERED_ROLES",
            "DEV.SCOPE",
            "DEV.FEATURE_DIMENSION",
            "DEV.FEATURE_BUNDLE",
            "DEV.RELATION_FRAME",
            "DEV.REALIZATION",
            "DEV.ALLOMORPHY",
            "DEV.ROLE_BINDING",
            "DEV.MULTIFEATURE_COMPOSITION",
            "DEV.COUNTERFACTUAL_EXPLANATION",
        )
        self.assertEqual(
            tuple(item.capability_id for item in self.staircase.targets),
            expected,
        )
        for target in self.staircase.targets:
            self.assertFalse(hasattr(target, "source_adapter_id"))
            self.assertFalse(hasattr(target, "oracle_id"))
            self.assertFalse(hasattr(target, "lesson_generator"))
            self.assertTrue(target.source_requirements)

    def test_frontier_starts_with_one_small_post_boolean_move(self):
        frontier = self.staircase.frontier(self.baseline)
        self.assertEqual(
            tuple(item.capability_id for item in frontier),
            ("DEV.LAW_SCHEMA",),
        )
        completed = (*self.baseline, "DEV.LAW_SCHEMA")
        self.assertEqual(
            tuple(item.capability_id for item in self.staircase.frontier(completed)),
            ("DEV.TYPE_DISCIPLINE",),
        )

    def test_route_branches_only_after_shared_prerequisites(self):
        completed = (
            *self.baseline,
            "DEV.LAW_SCHEMA",
            "DEV.TYPE_DISCIPLINE",
            "DEV.ORDERED_ROLES",
        )
        self.assertEqual(
            tuple(item.capability_id for item in self.staircase.frontier(completed)),
            ("DEV.SCOPE", "DEV.FEATURE_DIMENSION", "DEV.RELATION_FRAME"),
        )

    def test_surface_realization_cannot_arrive_before_semantic_feature_composition(self):
        with self.assertRaisesRegex(
                ValueError, "DEVELOPMENT_COMPLETION_PREREQUISITE_GAP"):
            self.staircase.frontier((
                *self.baseline,
                "DEV.LAW_SCHEMA",
                "DEV.TYPE_DISCIPLINE",
                "DEV.ORDERED_ROLES",
                "DEV.FEATURE_DIMENSION",
                "DEV.REALIZATION",
            ))

    def test_three_representation_layers_stay_explicit(self):
        target = self.staircase.target_map["DEV.ALLOMORPHY"]
        self.assertEqual(
            target.layers,
            (
                RepresentationLayer.SEMANTIC_IDENTITY,
                RepresentationLayer.STRUCTURAL_COMPOSITION,
                RepresentationLayer.SURFACE_REALIZATION,
            ),
        )
        self.assertIn(UnderstandingProjection.INVERT, target.projections)
        self.assertIn(UnderstandingProjection.COUNTERFACTUAL, target.projections)

    def test_final_target_requires_counterfactual_and_explanation(self):
        target = self.staircase.target_map["DEV.COUNTERFACTUAL_EXPLANATION"]
        self.assertEqual(
            target.projections,
            (
                UnderstandingProjection.TRANSFER,
                UnderstandingProjection.COUNTERFACTUAL,
                UnderstandingProjection.EXPLAIN,
            ),
        )
        self.assertEqual(
            target.prerequisites,
            (
                "DEV.MULTIFEATURE_COMPOSITION",
                "DEV.ROLE_BINDING",
                "DEV.LAW_SCHEMA",
            ),
        )

    def test_bad_stage_order_and_unknown_prerequisite_fail_closed(self):
        target = DevelopmentalTarget(
            "DEV.BAD", 1, "Bad",
            ("DEV.LATER",),
            (RepresentationLayer.SEMANTIC_IDENTITY,),
            (UnderstandingProjection.EXECUTE,),
            ("fixture source",),
            "fixture",
        )
        later = DevelopmentalTarget(
            "DEV.LATER", 2, "Later",
            ("B.IDBOOLOPS",),
            (RepresentationLayer.SEMANTIC_IDENTITY,),
            (UnderstandingProjection.EXECUTE,),
            ("fixture source",),
            "fixture",
        )
        with self.assertRaisesRegex(
                ValueError, "PREREQUISITE_NOT_EARLIER"):
            DevelopmentalStaircase(
                "fixture/v1", ("B.IDBOOLOPS",), (target, later))

        unknown = DevelopmentalTarget(
            "DEV.UNKNOWN", 1, "Unknown",
            ("NOT.ADMITTED",),
            (RepresentationLayer.SEMANTIC_IDENTITY,),
            (UnderstandingProjection.EXECUTE,),
            ("fixture source",),
            "fixture",
        )
        with self.assertRaisesRegex(ValueError, "UNKNOWN_PREREQUISITE"):
            DevelopmentalStaircase(
                "fixture/v1", ("B.IDBOOLOPS",), (unknown,))


if __name__ == "__main__":
    unittest.main()
