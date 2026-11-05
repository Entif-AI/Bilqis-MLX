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


class LiveReleaseFixture:
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.a = grade_a_course(accepted_grade_a(manifest))
        cls.full_b = grade_b_course(cls.a, SOURCE)
        cls.b = minimal_boolean_successor(cls.a, SOURCE)
        cls.graph = registry_graph()
        cls.c = grade_c_course(cls.b, cls.graph, maximum=10)
        _, _, cls.a_graph, _, _ = read_sources(SOURCE)
        cls.registry = live_source_registry()
        cls.historical_registry = historical_source_registry()
