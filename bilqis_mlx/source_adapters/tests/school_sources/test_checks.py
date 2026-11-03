"""Canonical predicate/connective source checks and semantic footprints."""
import unittest
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.source_adapters.tests.test_source_adapters_micro import SOURCE_ROOT


class SchoolSourceCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = read_sources(SOURCE_ROOT)[2]

    def test_registered_predicate_and_connective_own_checks_and_canonical_footprints(self):
        from bilqis_mlx.source_adapters.school import live_source_registry, A_ORACLE, B_ORACLE
        registry = live_source_registry()
        variants = (
            ("bilqis_mlx.grade_a_probe.make_record", A_ORACLE, "A.IDENTITY", "micro.compare.EQ"),
            ("bilqis_mlx.live_grade_b.draw_connectives", B_ORACLE, "B.AND", "cogal.operator.AND"),
        )
        for generator, oracle, capability, root in variants:
            with self.subTest(capability=capability):
                adapter = registry.require(generator, oracle)
                self.assertEqual(adapter.check.__module__, "bilqis_mlx.source_adapters.school")
                rows = adapter.draw(source_root=SOURCE_ROOT, graph=self.graph, course=None,
                                    capability=capability, seed=31, each=4)
                self.assertTrue(rows)
                for row in rows:
                    self.assertTrue(adapter.check(row, source_root=SOURCE_ROOT, graph=self.graph))
                    self.assertFalse(adapter.check({**row, "gold": "invalid"},
                                                   source_root=SOURCE_ROOT, graph=self.graph))
                    self.assertEqual(adapter.semantic_footprint(row), (root,))
