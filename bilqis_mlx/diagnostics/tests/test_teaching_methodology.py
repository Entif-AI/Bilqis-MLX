"""Practical first-lesson and cross-grade warning checks, without item-ID gating."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from bilqis_mlx.diagnostics import (DiagnosticStatus, LearningSignal,
    diagnose_teaching_visit, inspect_lesson_step)
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.live_grade_a import live_course as grade_a_course
from bilqis_mlx.live_grade_b import draw_connectives, live_course as grade_b_course
from bilqis_mlx.source_adapters.structure import inspect_source_query


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "vendor" / "legacy-v16"


class TeachingMethodologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.course = grade_b_course(grade_a_course(accepted_grade_a(manifest)), SOURCE)
        _, _, cls.graph, _, _ = read_sources(SOURCE)
        cls.rows = list(draw_connectives(SOURCE, cls.graph, seed=29, each=12,
                                        capability="B.NOT"))

    @staticmethod
    def complexity(row):
        shape = inspect_source_query(row["record"]["query"])
        return shape.semantic_operations, len(row["tokens"])

    def test_real_grade_b_examples_link_source_semantics_to_grade_a(self):
        row = min(self.rows, key=self.complexity)
        step = inspect_lesson_step(self.course, "B.NOT", self.rows, [row])
        self.assertGreaterEqual(step.delivered_count, 1)
        self.assertEqual(step.simplest_delivered, step.simplest_offered)
        self.assertTrue(set(step.prerequisite_capabilities) <=
                        {"A.IDENTITY", "A.PARENT", "A.LINK"})
        self.assertTrue(step.prerequisite_capabilities)
        s4, s5 = diagnose_teaching_visit(self.course, "B.NOT", (step,),
                                        introductory=True)
        self.assertEqual(s4.signal, LearningSignal.DISCONNECTED_PREREQUISITES)
        self.assertEqual(s4.status, DiagnosticStatus.NOT_OBSERVED)
        self.assertEqual(s5.status, DiagnosticStatus.NOT_OBSERVED)

    def test_missing_earlier_semantic_construction_is_detected_without_question_ids(self):
        broken = deepcopy(self.rows[0])
        broken["record"]["query"]["args"] = [{"kind": "literal", "value": True}]
        # Deliberately malformed structural lesson: source admission would also
        # reject it. This unit verifies the independent S4 warning mechanism.
        step = inspect_lesson_step(self.course, "B.NOT", [broken], [broken])
        s4, _ = diagnose_teaching_visit(self.course, "B.NOT", (step,),
                                        introductory=True)
        self.assertEqual(s4.status, DiagnosticStatus.OBSERVED_IN_INSTRUCTION)
        self.assertEqual(step.prerequisite_capabilities, ())

    def test_first_instruction_skipping_a_simpler_offered_example_is_flagged(self):
        simplest = min(self.rows, key=self.complexity)
        complex_row = max(self.rows, key=self.complexity)
        self.assertLess(self.complexity(simplest), self.complexity(complex_row))
        step = inspect_lesson_step(self.course, "B.NOT", self.rows,
                                   [complex_row])
        _, s5 = diagnose_teaching_visit(self.course, "B.NOT", (step,),
                                        introductory=True)
        self.assertEqual(s5.status, DiagnosticStatus.OBSERVED_IN_INSTRUCTION)
        self.assertEqual(s5.evidence_count, 1)
        self.assertEqual(diagnose_teaching_visit(
            self.course, "B.NOT", (step,), introductory=None)[1].status,
            DiagnosticStatus.NOT_MEASURED)
        self.assertEqual(diagnose_teaching_visit(
            self.course, "B.NOT", (step,), introductory=False)[1].status,
            DiagnosticStatus.NOT_APPLICABLE)

    def test_unsupported_semantic_root_and_unoffered_example_fail_closed(self):
        row = deepcopy(self.rows[0])
        row["record"]["query"]["args"][0]["name"] = "UNADMITTED"
        with self.assertRaisesRegex(ValueError, "UNADMITTED_CONSTITUENT"):
            inspect_lesson_step(self.course, "B.NOT", [row], [row])
        unrelated = deepcopy(self.rows[0])
        unrelated["id"] = "unoffered"
        with self.assertRaisesRegex(ValueError, "DELIVERED_NOT_OFFERED"):
            inspect_lesson_step(self.course, "B.NOT", self.rows, [unrelated])
        altered = deepcopy(self.rows[0])
        altered["tokens"] = altered["tokens"] + [7]
        with self.assertRaisesRegex(ValueError, "DELIVERED_NOT_OFFERED"):
            inspect_lesson_step(self.course, "B.NOT", self.rows, [altered])


if __name__ == "__main__":
    unittest.main()
