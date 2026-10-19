"""Neural-inert durable enrollment of B.IDBOOLOPS into the revised Grade-B release."""
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from bilqis_mlx.boolean_composite import build_course as build_composite
from bilqis_mlx.boolean_identification import CAPABILITY, RELEASE, build_course
from bilqis_mlx.curriculum import BOOLEAN_OPERATORS
from bilqis_mlx.curriculum.scheduler import start_new
from bilqis_mlx.factory.live_releases import initial_course, boolean_successor
from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.grade_a_release import accepted_grade_a
from bilqis_mlx.learning.champions import Checkpoint
from bilqis_mlx.runtime.state import _fingerprint
from bilqis_mlx.trainer import VERSION, _activate_revised_admitted_grade


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "vendor" / "legacy-v16"


@unittest.skipUnless(os.environ.get("BILQIS_FULL_GRADE_B_TESTS") == "1",
                     "legacy/full Grade B compatibility tests are opt-in")
class BooleanIdentificationMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        manifest = json.loads((
            ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json").read_text())
        cls.manifest = manifest
        cls.a = initial_course(accepted_grade_a(manifest))
        cls.b = boolean_successor(cls.a, SOURCE)
        cls.old = build_composite(cls.b, SOURCE)
        cls.new = build_course(cls.old, SOURCE)
        _, _, cls.graph, _, _ = read_sources(SOURCE)

    def test_durable_idboolops_revision_changes_curriculum_and_heads_not_neural_state(self):
        student = Checkpoint("a" * 64, "bundles/unchanged", 4321, True)
        base = start_new(self.old, student)
        b_caps = tuple(cap.id for cap in self.old.grades[-1].capabilities)
        school = replace(
            base, grade_index=1, queue=b_caps,
            champions={"A": student, "B": student},
        )
        receipt = {
            "schema": VERSION,
            "generation": 11,
            "run_id": "idboolops-migration-fixture",
            "school": asdict(school),
            "model_bundle": student.filename,
            "curriculum_mode": self.old.version,
            "result": "ACTIVE_GRADE_B",
            "semantic_graph_sha256": _fingerprint(self.graph),
            "parameter_shapes": {"embedding.weight": [len(self.graph["tokens"]), 8]},
            "source_manifest_sha256": self.manifest["manifest_sha256"],
            "teacher": {"events": 99, "strategies": {}},
            "config": {"precision": "fp32", "vocab_size": len(self.graph["tokens"])},
            "last_exam": {"cohort_sha256": "b" * 64},
            "qualification_cohort": {"cohort_sha256": "c" * 64},
            "capability_best": {},
            "mentor_epoch": None,
        }
        with TemporaryDirectory() as temp:
            root = Path(temp)
            revised = _activate_revised_admitted_grade(
                root, receipt, self.old, self.new, self.graph)
            self.assertEqual(json.loads((root / "state.json").read_text()), revised)
            self.assertTrue((root / "states" / "0000012.json").is_file())
            events = [json.loads(line) for line in (
                root / "events.jsonl").read_text().splitlines()]

        self.assertEqual(revised["curriculum_mode"], RELEASE)
        self.assertEqual(revised["model_bundle"], receipt["model_bundle"])
        self.assertEqual(revised["school"]["current_student"],
                         receipt["school"]["current_student"])
        self.assertEqual(revised["teacher"], receipt["teacher"])
        self.assertEqual(set(revised["school"]["champions"]), {"A"})
        self.assertEqual(len(revised["school"]["queue"]), 8)
        self.assertIn(CAPABILITY, revised["school"]["queue"])
        self.assertIsNone(revised["last_exam"])
        self.assertNotIn("qualification_cohort", revised)
        operator = revised["config"]["answer_heads"]["boolean_operator"]
        self.assertEqual(operator["values"], list(BOOLEAN_OPERATORS))
        self.assertEqual(operator["token_ids"], [
            self.graph["tokens"].index("cogal.operator." + op)
            for op in BOOLEAN_OPERATORS
        ])
        self.assertEqual(revised["config"]["vocab_size"], len(self.graph["tokens"]))
        self.assertEqual(events[-1]["event"], "SCHOOL_GRADE_RELEASE_REVISED")
        self.assertEqual(events[-1]["actual_neural_updates"], 0)
        self.assertEqual(events[-1]["optimizer_step"], 4321)


if __name__ == "__main__":
    unittest.main()
