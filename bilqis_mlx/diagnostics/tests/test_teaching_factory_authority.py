"""Regression proof for diagnostics after the runtime cut over to Factory v2."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from bilqis_mlx.diagnostics.teaching import inspect_lesson_step
from bilqis_mlx.factory.curriculum_definition import from_legacy_course
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.live_grade_a import live_course as grade_a_course
from bilqis_mlx.live_grade_b import draw_connectives, live_course as grade_b_course
from bilqis_mlx.source_adapters.structure import inspect_source_query


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "vendor" / "legacy-v16"


class TeachingFactoryAuthorityTests(unittest.TestCase):
    def test_v2_curriculum_definition_drives_same_lesson_evidence(self):
        manifest = json.loads(
            (ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        legacy = grade_b_course(grade_a_course(accepted_grade_a(manifest)), SOURCE)
        curriculum, _ = from_legacy_course(legacy)
        from bilqis_mlx.grade_a_probe import read_sources
        _, _, graph, _, _ = read_sources(SOURCE)
        rows = list(draw_connectives(
            SOURCE, graph, seed=29, each=12, capability="B.NOT"))
        row = min(rows, key=lambda item: (
            inspect_source_query(item["record"]["query"]).semantic_operations,
            len(item["tokens"])))

        self.assertEqual(
            inspect_lesson_step(curriculum, "B.NOT", rows, [row]),
            inspect_lesson_step(legacy, "B.NOT", rows, [row]),
        )


if __name__ == "__main__":
    unittest.main()
