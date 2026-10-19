import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.factory.generation import draw_release_rows
from bilqis_mlx.factory.live_releases import (
    BOOLEAN_COMPOSITE_RELEASE, BOOLEAN_IDENTIFICATION_RELEASE,
    GRAPH_GROWTH_TRANSITION, SAME_GRADE_TRANSITION,
    boolean_composite_successor, boolean_identification_successor,
    next_successor_plan,
)
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.live_grade_a import draw_predicates, live_course as grade_a_course
from bilqis_mlx.live_grade_b import draw_connectives, live_course as grade_b_course
from bilqis_mlx.live_grade_c import draw as draw_numbers, live_course as grade_c_course, registry_graph


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "vendor" / "legacy-v16"


class LiveFactoryReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.a = grade_a_course(accepted_grade_a(manifest))
        cls.b = grade_b_course(cls.a, SOURCE)
        cls.graph = registry_graph()
        cls.c = grade_c_course(cls.b, cls.graph, maximum=10)
        _, _, cls.a_graph, _, _ = read_sources(SOURCE)
        cls.registry = live_source_registry()

    def test_a_b_c_each_compile_through_same_factory_release_api(self):
        for course in (self.a, self.b, self.c):
            with self.subTest(course=course.version):
                release = compile_factory_release(course, self.registry)
                release.verify()
                self.assertEqual(release.course, course)

    def test_generic_generation_preserves_a_and_runtime_samples_b_source_contracts(self):
        release = compile_factory_release(self.b, self.registry)
        expected_a = list(draw_predicates(SOURCE, self.a_graph, seed=31,
                                          capability="A.IDENTITY", each=12))
        actual_a = draw_release_rows(SOURCE, self.a_graph, release, self.registry,
                                     seed=31, capability="A.IDENTITY", each=12)
        self.assertEqual(actual_a, expected_a)

        source_pool = list(draw_connectives(SOURCE, self.a_graph, seed=31,
                                            capability="B.IMPLIES", each=24))
        actual_b = draw_release_rows(SOURCE, self.a_graph, release, self.registry,
                                     seed=31, capability="B.IMPLIES", each=12)
        pool_ids = {row["id"] for row in source_pool}
        self.assertEqual(len(actual_b), 12)
        self.assertTrue({row["id"] for row in actual_b} <= pool_ids)
        self.assertNotEqual(sum(row["gold"] == "TRUE" for row in actual_b), 6)
        self.assertEqual({tuple(row["operand_truths"]) for row in actual_b},
                         {(False,False), (False,True), (True,False), (True,True)})
        self.assertEqual({row["runtime_sampler"] for row in actual_b},
                         {"bilqis.mlx.grade-b-runtime-sampler/v2"})

    def test_generic_generation_matches_existing_numeric_source_contract(self):
        release = compile_factory_release(self.c, self.registry)
        expected = list(draw_numbers(self.graph, seed=47, maximum=10,
                                     capability="C.ADD", each=12))
        actual = draw_release_rows(SOURCE, self.graph, release, self.registry,
                                   seed=47, capability="C.ADD", each=12)
        self.assertEqual(actual, expected)

    def test_same_grade_b_releases_preserve_history_and_precede_c(self):
        self.assertEqual(self.b.digest(),
                         "fde5e7e3be6d3903fc46dedcc7c1d23907c713d64ce75b3fefd4d8c9a36aa5e2")
        old_release = compile_factory_release(self.b, self.registry)
        self.assertEqual(old_release.release_sha256,
                         "fa02b5de588a47692da54ab542f33df56fd9a5e9e00c0c64a2f447ba8730f8d4")
        plan = next_successor_plan(self.b, SOURCE)
        self.assertEqual(plan.transition, SAME_GRADE_TRANSITION)
        composite = plan.successor
        self.assertEqual(composite.version, BOOLEAN_COMPOSITE_RELEASE)
        self.assertEqual(composite, boolean_composite_successor(self.b, SOURCE))
        id_plan = next_successor_plan(composite, SOURCE)
        self.assertEqual(id_plan.transition, SAME_GRADE_TRANSITION)
        identified = id_plan.successor
        self.assertEqual(identified.version, BOOLEAN_IDENTIFICATION_RELEASE)
        self.assertEqual(identified, boolean_identification_successor(composite, SOURCE))
        self.assertEqual(len(identified.grades[-1].capabilities), 8)
        with patch.dict(os.environ, {"BILQIS_INTEGER_MAX": "10"}):
            c_plan = next_successor_plan(identified, SOURCE)
        self.assertEqual(c_plan.transition, GRAPH_GROWTH_TRANSITION)
        self.assertEqual(tuple(grade.id for grade in c_plan.successor.grades),
                         ("A", "B", "C"))


if __name__ == "__main__":
    unittest.main()
