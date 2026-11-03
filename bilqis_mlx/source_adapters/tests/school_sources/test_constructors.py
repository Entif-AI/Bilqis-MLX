"""School enrichment remains a source-owned constructor over typed curricula."""
import unittest
from unittest.mock import patch
from bilqis_mlx.factory.tests.lifecycle.test_teaching import closed_source_fixture


class SchoolConstructorTests(unittest.TestCase):
    def test_enrichment_provider_accepts_the_typed_curriculum(self):
        from dataclasses import replace
        from bilqis_mlx.curriculum import AnswerFamily
        from bilqis_mlx.source_adapters.school import enrich_boolean, BOOLEAN_ASSOCIATION_OPTION
        _, _, _, _, release = closed_source_fixture()
        grade = release.curriculum.grades[0]
        numeric = replace(grade.capabilities[-1], answer_families=(
            AnswerFamily("numeric_active", ("0", "1", "2", "3")),))
        curriculum = replace(release.curriculum, grades=(replace(
            grade, capabilities=(*grade.capabilities[:-1], numeric)),))
        with patch("bilqis_mlx.source_adapters.school.draw_b_grade_bridges",
                   return_value=()) as draw:
            enrich_boolean(source_root=None, graph={}, course=curriculum,
                capability="Z.C0", seed=17, option_id=BOOLEAN_ASSOCIATION_OPTION)
        self.assertEqual(draw.call_args.kwargs["maximum"], 3)
