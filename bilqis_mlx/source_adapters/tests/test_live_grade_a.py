"""Live Grade A draws are reproducible, source-checked, and not embargoed."""
from pathlib import Path
import unittest

from bilqis_mlx.live_grade_a import draw_predicates, live_course
from bilqis_mlx.source_adapters.grade_a_presentation import (
    draw_a_generalization as draw_a_presentation,
)
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.generated_assessment import make_cohort
from bilqis_mlx.trainer import _persist_live_cohort, _verify_saved_cohort
from bilqis_mlx.curriculum.scheduler import Assessment, Score, assess, start_new, visit
from bilqis_mlx.learning.champions import Checkpoint
import json
import tempfile


ROOT = Path(__file__).resolve().parents[3] / "vendor" / "legacy-v16"
SOURCE = ROOT / "runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt"
MANIFEST = Path(__file__).resolve().parents[3] / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


@unittest.skipUnless(SOURCE.is_file(), "Pinned original source not available")
class LiveGradeAGenerationTests(unittest.TestCase):
    def test_all_six_families_regenerate_oracle_agreed_rows_per_seed(self):
        import torch
        graph = torch.load(SOURCE, map_location="cpu", weights_only=True)["graph"]
        one = draw_predicates(ROOT, graph, seed=833, each=12)
        same = draw_predicates(ROOT, graph, seed=833, each=12)
        another = draw_predicates(ROOT, graph, seed=834, each=12)
        self.assertEqual(one, same)
        self.assertNotEqual(one, another)
        self.assertEqual(len(one), 72)
        self.assertEqual(len({x["id"] for x in one}), 72)
        self.assertEqual({x["capability"] for x in one},
            {"A.IDENTITY", "A.PARENT", "A.LINK", "A.MEMBER", "A.EDGE", "A.MAPS"})
        for cap in {x["capability"] for x in one}:
            subset = [x for x in one if x["capability"] == cap]
            self.assertEqual(len(subset), 12)
            self.assertEqual([x["gold"] for x in subset].count("TRUE"), 6)
            self.assertTrue(all(x["oracle"] and x["source_id"] for x in subset))
        cohort = make_cohort(one, generator_version="grade-a-live/v1",
                             seed=833, rubric_version="A/live/v1")
        self.assertNotEqual(cohort.digest,
                            make_cohort(another, generator_version="grade-a-live/v1",
                                        seed=834, rubric_version="A/live/v1").digest)

    def test_contextual_provider_preserves_all_grade_a_source_oracles(self):
        import torch
        from bilqis_mlx.source_adapters.school import live_source_registry
        graph = torch.load(SOURCE, map_location="cpu", weights_only=True)["graph"]
        registry = live_source_registry()
        adapter = registry.require(
            "bilqis_mlx.grade_a_probe.make_record",
            "bilqis.mlx.grade-a-record-oracle/v2")
        for capability in (
                "A.IDENTITY", "A.PARENT", "A.LINK",
                "A.MEMBER", "A.EDGE", "A.MAPS"):
            base = draw_predicates(ROOT, graph, seed=377, each=12,
                                   capability=capability)
            rows = draw_a_presentation(
                source_root=ROOT, graph=graph, course=None,
                capability=capability, seed=377, each=12)
            self.assertEqual([row["gold"] for row in rows],
                             [row["gold"] for row in base])
            self.assertTrue(all(adapter.check(
                row, source_root=ROOT, graph=graph, course=None) for row in rows))
            self.assertTrue(any(
                row["id"] != original["id"] and row["tokens"] != original["tokens"]
                for row, original in zip(rows, base)))

    def test_live_provider_keeps_canonical_grade_a_for_non_generalization(self):
        import torch
        from bilqis_mlx.source_adapters.school import live_source_registry
        graph = torch.load(SOURCE, map_location="cpu", weights_only=True)["graph"]
        adapter = live_source_registry().require(
            "bilqis_mlx.grade_a_probe.make_record",
            "bilqis.mlx.grade-a-record-oracle/v2")
        expected = draw_predicates(
            ROOT, graph, seed=491, each=12, capability="A.IDENTITY")
        ordinary = adapter.draw(
            source_root=ROOT, graph=graph, course=None,
            capability="A.IDENTITY", seed=491, each=12)
        generalized = adapter.generalization_draw(
            source_root=ROOT, graph=graph, course=None,
            capability="A.IDENTITY", seed=491, each=12)
        self.assertEqual(tuple(expected), ordinary)
        self.assertNotEqual(ordinary, generalized)

    def test_member_context_expands_the_fresh_false_size3_source_space(self):
        import torch
        graph = torch.load(SOURCE, map_location="cpu", weights_only=True)["graph"]
        identities = set()
        for seed in range(12):
            rows = draw_a_presentation(
                source_root=ROOT, graph=graph, course=None,
                capability="A.MEMBER", seed=seed, each=12)
            for row in rows:
                if row["gold"] == "FALSE" and row["universe_size"] == 3:
                    identities.add(row["id"])
                    self.assertTrue(row["record"]["world"]["sets"]["K1"])
                    self.assertEqual(row["record"]["query"]["args"][1]["name"], "K0")
        # Historical A.MEMBER FALSE/size-3 had only C(5,3)*3 = 30 records.
        self.assertGreater(len(identities), 30)

    def test_rotating_cohorts_use_one_stable_school_rubric(self):
        source = accepted_grade_a(json.loads(MANIFEST.read_text()))
        course = live_course(source)
        self.assertNotEqual(course.digest(), source.digest())
        self.assertNotEqual(course.grades[0].assessment_sha256,
                            source.grades[0].assessment_sha256)
        student = Checkpoint("1"*64, "bundles/test", 42, True)
        school = start_new(course, student)
        for cap in [c.id for c in course.grades[0].capabilities]:
            school = visit(course, school, cap, student)
        for n in range(2):
            assessment = Assessment(student.sha256, student.optimizer_step,
                                    course.digest(), course.grades[0].assessment_sha256,
                                    {c.id: Score(0, 12) for c in course.grades[0].capabilities},
                                    "different-generated-cohort-" + str(n))
            school = assess(course, school, assessment)
            if n == 0:
                for cap in school.queue:
                    school = visit(course, school, cap, student)
        self.assertEqual(school.stage, "RECOVERY_2")

    def test_saved_cohort_replay_verifies_exact_content_and_source(self):
        import torch
        manifest = json.loads(MANIFEST.read_text())
        course = live_course(accepted_grade_a(manifest))
        graph = torch.load(SOURCE, map_location="cpu", weights_only=True)["graph"]
        rows = draw_predicates(ROOT, graph, seed=9002)
        cohort = make_cohort(rows,
            generator_version="bilqis.mlx.grade-a-live-constructor/v1",
            seed=9002, rubric_version="bilqis.mlx.grade-a-live/20261015")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            file = _persist_live_cohort(path, manifest, course, cohort)
            receipt = {"source_manifest_sha256": manifest["manifest_sha256"],
                       "last_exam": {"cohort_file": file,
                                     "cohort_seed": 9002,
                                     "cohort_sha256": cohort.digest}}
            _verify_saved_cohort(path, receipt, course)
            payload = json.loads((path/file).read_text())
            payload["rows"][0]["gold"] = "FALSE" if payload["rows"][0]["gold"] == "TRUE" else "TRUE"
            (path/file).write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError, "COHORT_CONTENT_DRIFT"):
                _verify_saved_cohort(path, receipt, course)
            with self.assertRaisesRegex(ValueError, "COHORT_CUSTODY_DRIFT"):
                _persist_live_cohort(path, manifest, course, cohort)


if __name__ == "__main__":
    unittest.main()
