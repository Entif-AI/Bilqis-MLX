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


class LiveReleaseSuccessionTests(LiveReleaseFixture, unittest.TestCase):
    @unittest.skipUnless(os.environ.get("BILQIS_FULL_GRADE_B_TESTS") == "1",
                         "legacy/full Grade B compatibility tests are opt-in")
    def test_same_grade_b_releases_preserve_history_and_precede_c(self):
        self.assertEqual(self.full_b.digest(),
                         "b6904a67849a8788f90b0c62cdbd4b3abeb3f24e686cf11e289895991bda470a")
        old_release = compile_factory_release(self.full_b, self.registry)
        sealed = json.loads(json.dumps(old_release.manifest()))
        self.assertEqual(type(old_release).from_manifest(sealed, old_release.release_sha256),
                         old_release)

        old_release.verify()
        self.assertEqual(old_release.course, self.full_b)
        plan = next_successor_plan(self.full_b, SOURCE)
        self.assertEqual(plan.transition, SAME_GRADE_TRANSITION)
        composite = plan.successor
        self.assertEqual(composite.version, BOOLEAN_COMPOSITE_RELEASE)
        self.assertEqual(composite, boolean_composite_successor(self.full_b, SOURCE))
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
        self.assertEqual(json.loads(json.dumps(old_release.manifest())), sealed)


    def test_a_defaults_to_minimal_boolean_release_and_full_b_is_explicit_opt_in(self):
        minimal = next_successor_plan(self.a, SOURCE)
        self.assertEqual(minimal.successor.version, MINIMAL_BOOLEAN_RELEASE)
        self.assertEqual(
            tuple(cap.id for cap in minimal.successor.grades[-1].capabilities),
            ("B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"))
        self.assertEqual(
            minimal.successor.grades[-1].teaching_stages,
            (("B.AND", "B.IFF"), ("B.COMPOSITE",), ("B.IDBOOLOPS",)))
        release = compile_factory_release(
            minimal.successor, self.historical_registry)
        rows = draw_release_rows(
            SOURCE, self.a_graph, release, self.historical_registry,
            seed=53, capability="B.IDBOOLOPS", each=12)
        self.assertEqual({row["gold"] for row in rows}, {"AND", "IFF"})
        self.assertEqual(
            {tuple(row["operator_options"]) for row in rows},
            {("AND", "IFF")})

        full = next_successor_plan(self.a, SOURCE, full_grade_b=True)
        self.assertEqual(full.successor.version, BOOLEAN_RELEASE)
        self.assertEqual(len(full.successor.grades[-1].capabilities), 6)

        with patch.dict(os.environ, {"BILQIS_INTEGER_MAX": "10"}):
            c_plan = next_successor_plan(minimal.successor, SOURCE)
        self.assertEqual(c_plan.transition, GRAPH_GROWTH_TRANSITION)
        self.assertEqual(
            tuple(cap.id for cap in c_plan.successor.grades[1].capabilities),
            ("B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"))
        prior_heads = minimal_boolean_answer_heads(self.a_graph)
        grown_heads = numeric_answer_heads(
            self.graph, 10, prior_heads=prior_heads)
        self.assertEqual(
            grown_heads["boolean_operator"]["values"], ["AND", "IFF"])


    def test_existing_full_b_defaults_to_neural_inert_minimal_replacement(self):
        composite = boolean_composite_successor(self.full_b, SOURCE)
        identified = boolean_identification_successor(composite, SOURCE)
        replacement = default_resume_replacement(
            identified, self.a, SOURCE, full_grade_b=False)
        self.assertIsNotNone(replacement)
        self.assertEqual(replacement.version, MINIMAL_BOOLEAN_RELEASE)
        self.assertEqual(
            tuple(cap.id for cap in replacement.grades[-1].capabilities),
            ("B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"))
        self.assertIsNone(default_resume_replacement(
            identified, self.a, SOURCE, full_grade_b=True))
