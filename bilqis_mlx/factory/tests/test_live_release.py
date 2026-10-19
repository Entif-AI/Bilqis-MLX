import json
from pathlib import Path
import unittest

from bilqis_mlx.source_adapters.school import live_source_registry
from bilqis_mlx.factory.generation import draw_release_rows
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

    def test_generic_generation_matches_existing_a_and_b_source_contracts(self):
        release = compile_factory_release(self.b, self.registry)
        for capability, direct in (
            ("A.IDENTITY", draw_predicates),
            ("B.IMPLIES", draw_connectives),
        ):
            expected = list(direct(SOURCE, self.a_graph, seed=31,
                                   capability=capability, each=12))
            actual = draw_release_rows(SOURCE, self.a_graph, release, self.registry,
                                       seed=31, capability=capability, each=12)
            self.assertEqual(actual, expected)

    def test_generic_generation_matches_existing_numeric_source_contract(self):
        release = compile_factory_release(self.c, self.registry)
        expected = list(draw_numbers(self.graph, seed=47, maximum=10,
                                     capability="C.ADD", each=12))
        actual = draw_release_rows(SOURCE, self.graph, release, self.registry,
                                   seed=47, capability="C.ADD", each=12)
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
