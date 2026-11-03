import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.compatibility.source_adapters import historical_source_registry
from bilqis_mlx.factory.generation import draw_release_rows
from bilqis_mlx.factory.live_releases import (
    BOOLEAN_COMPOSITE_RELEASE, BOOLEAN_IDENTIFICATION_RELEASE, BOOLEAN_RELEASE,
    GRAPH_GROWTH_TRANSITION, SAME_GRADE_TRANSITION,
    MINIMAL_BOOLEAN_RELEASE,
    boolean_composite_successor, boolean_identification_successor,
    minimal_boolean_answer_heads, next_successor_plan, numeric_answer_heads,
    minimal_boolean_successor, default_resume_replacement,
)
from bilqis_mlx.factory.release import compile_factory_release
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.live_curriculum import assessment_rubric_for_scope
from bilqis_mlx.live_grade_a import draw_predicates, live_course as grade_a_course
from bilqis_mlx.live_grade_b import draw_connectives, live_course as grade_b_course
from bilqis_mlx.live_grade_c import draw as draw_numbers, live_course as grade_c_course, registry_graph


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "vendor" / "legacy-v16"


from bilqis_mlx.compatibility.live_release_parts.tests.fixtures import LiveReleaseFixture


class LiveFactoryReleaseTests(LiveReleaseFixture, unittest.TestCase):
    def test_a_b_c_each_compile_through_same_factory_release_api(self):
        for course in (self.a, self.b, self.c):
            with self.subTest(course=course.version):
                release = compile_factory_release(course, self.historical_registry)
                release.verify()
                self.assertEqual(release.course, course)


    @unittest.skipUnless(os.environ.get("BILQIS_FULL_GRADE_B_TESTS") == "1",
                         "legacy/full Grade B compatibility tests are opt-in")
    def test_generic_generation_preserves_a_and_runtime_samples_b_source_contracts(self):
        release = compile_factory_release(self.full_b, self.registry)
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
        self.assertEqual(sum(row["gold"] == "TRUE" for row in actual_b), 6)
        self.assertEqual({tuple(row["operand_truths"]) for row in actual_b},
                         {(False,False), (True,False), (True,True)})
        self.assertTrue(all("world" not in row["record"] for row in actual_b))
        self.assertEqual({row["runtime_sampler"] for row in actual_b},
                         {"bilqis.mlx.grade-b-u7c-runtime-sampler/v3"})


    def test_generic_generation_matches_existing_numeric_source_contract(self):
        release = compile_factory_release(self.c, self.historical_registry)
        expected = list(draw_numbers(self.graph, seed=47, maximum=10,
                                     capability="C.ADD", each=12))
        actual = draw_release_rows(SOURCE, self.graph, release, self.registry,
                                   seed=47, capability="C.ADD", each=12)
        self.assertEqual(actual, expected)


    def test_assessment_rubric_tracks_highest_grade_represented_in_scope(self):
        minimal = minimal_boolean_successor(self.a, SOURCE)
        a_scope = tuple(cap.id for cap in minimal.grades[0].capabilities)
        b_scope = tuple(cap.id for cap in minimal.grades[-1].capabilities)
        self.assertEqual(assessment_rubric_for_scope(minimal, a_scope),
                         minimal.grades[0].assessment_sha256)
        self.assertEqual(assessment_rubric_for_scope(minimal, a_scope + b_scope),
                         minimal.grades[-1].assessment_sha256)
