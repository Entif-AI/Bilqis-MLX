"""Default reduced Grade-B active-v2 contract tests."""
import json
from pathlib import Path
import unittest

from bilqis_mlx.factory.autonomy import EvidenceKind, obligations_for_capability
from bilqis_mlx.factory.executable_release import (
    answer_heads_from_executable_release,
)
from bilqis_mlx.factory.evidence import draw_evidence_rows
from bilqis_mlx.factory.generation import draw_executable_release_rows
from bilqis_mlx.factory.live_releases import (
    MINIMAL_BOOLEAN_RELEASE,
    initial_course,
    minimal_boolean_successor,
)
from bilqis_mlx.compatibility.executable_projection import (
    compile_projected_executable_release,
)
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.minimal_grade_b import CAPABILITIES, OPERATORS
from bilqis_mlx.runtime.autonomy_live import build_live_autonomy_plan
from bilqis_mlx.source_adapters.school import live_source_registry


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "vendor" / "legacy-v16"
MANIFEST = ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


@unittest.skipUnless((SOURCE / "bilqis_micro/kernel.py").is_file(),
                     "Pinned predecessor source is not mounted")
class MinimalGradeBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        accepted = accepted_grade_a(json.loads(MANIFEST.read_text()))
        cls.a = initial_course(accepted)
        cls.course = minimal_boolean_successor(cls.a, SOURCE)
        _, _, cls.graph, _, _ = read_sources(SOURCE)
        cls.registry = live_source_registry()
        cls.release, cls.program, cls.canonical_course = (
            compile_projected_executable_release(
                cls.course, cls.a, SOURCE, cls.graph))

    def test_only_reduced_capabilities_are_admitted(self):
        self.assertEqual(self.course.version, MINIMAL_BOOLEAN_RELEASE)
        self.assertEqual(
            tuple(cap.id for cap in self.course.grades[-1].capabilities),
            CAPABILITIES)
        self.assertEqual(
            self.course.grades[-1].teaching_stages,
            (("B.AND", "B.IFF"), ("B.COMPOSITE",), ("B.IDBOOLOPS",)))

    def test_atomic_release_contains_only_and_and_iff(self):
        for capability in ("B.AND", "B.IFF"):
            rows = draw_executable_release_rows(
                SOURCE, self.graph, self.release, self.registry,
                seed=11, legacy_course=self.canonical_course,
                capability=capability, each=12)
            self.assertEqual({row["capability"] for row in rows}, {capability})
            self.assertEqual(len(rows), 12)

    def test_composite_never_uses_withheld_operators(self):
        rows = draw_executable_release_rows(
            SOURCE, self.graph, self.release, self.registry,
            seed=12, legacy_course=self.canonical_course,
            capability="B.COMPOSITE", each=12)
        self.assertTrue(rows)
        self.assertTrue(all(set(row["operators"]) <= set(OPERATORS) for row in rows))

    def test_idboolops_is_two_way_and_balanced(self):
        rows = draw_executable_release_rows(
            SOURCE, self.graph, self.release, self.registry,
            seed=13, legacy_course=self.canonical_course,
            capability="B.IDBOOLOPS", each=12)
        self.assertEqual([row["gold"] for row in rows].count("AND"), 6)
        self.assertEqual([row["gold"] for row in rows].count("IFF"), 6)
        self.assertEqual(
            {tuple(row["operator_options"]) for row in rows},
            {OPERATORS})
        self.assertEqual(
            answer_heads_from_executable_release(
                self.release, self.graph)["boolean_operator"]["values"],
            list(OPERATORS))

    def test_autonomy_can_witness_reduced_boolean_dependencies(self):
        plan = build_live_autonomy_plan(self.release, SOURCE)
        composite = obligations_for_capability(
            self.release, "B.COMPOSITE", plan=plan)
        self.assertFalse(any(
            item.kind is EvidenceKind.PREREQUISITE and item.key.startswith("A.")
            for item in composite))
        self.assertEqual(
            {item.key for item in composite if item.kind is EvidenceKind.COMPOSITION
             and "@" not in item.key},
            {"B.AND", "B.IFF"},
        )
        obligation = next(
            item for item in composite
            if item.kind is EvidenceKind.COMPOSITION and item.key == "B.AND")
        rows = draw_evidence_rows(
            SOURCE, self.graph, self.release, self.registry,
            obligation, seed=14)
        self.assertEqual(len(rows), obligation.minimum_specimens)


if __name__ == "__main__":
    unittest.main()
