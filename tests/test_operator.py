"""Human root commands must not accidentally begin optimization."""
from contextlib import redirect_stdout,redirect_stderr
import io
import json
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.cli import main,DEFAULT_RUN,ORIGINAL_CHECKPOINT
from bilqis_mlx.spiral_dashboard import TABLES


class OperatorTests(unittest.TestCase):
    def test_six_panel_renderer_still_has_same_names_and_rows(self):
        self.assertEqual([name for name,_ in TABLES],[
            "CANDIDATES","SENTINEL & RETENTION","SOUP & TEACHER",
            "BRIDGE FAMILIES","GRADES & MASTERY","SYSTEM & QUALIFICATION"])
        with tempfile.TemporaryDirectory() as tmp:
            out=io.StringIO()
            with redirect_stdout(out):
                result=main(["dashboard","--run-dir",tmp])
            self.assertEqual(result,0)
            for name,_ in TABLES:
                self.assertIn(name,out.getvalue())
            self.assertIn("READY_FOR_HUMAN_GRADE_A_START",out.getvalue())

    def test_explicit_resume_only_and_training_is_hard_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=io.StringIO()
            with redirect_stdout(output):
                code=main(["train","--dry-run","--run-dir",tmp])
            self.assertEqual(code,0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["start_behavior"], "GRADE_A_NEW_RUN")
            self.assertEqual(report["result"], "PREFLIGHT_ONLY_NO_NEURAL_UPDATES")
            self.assertFalse(report["human_live_grade_a_trainer_end_to_end_qualified"])
            self.assertEqual(report["disposable_full_student_optimizer_continuation"]["scope"],
                             "ONE_DETACHED_STEP_AND_COMPLETE_39_TENSOR_ADAMW_RESTART")
            self.assertEqual(report["blockers"], [])
            self.assertTrue(report["source_grounded_grade_a_admitted"])
            self.assertEqual(report["grade_a_release"],
                             "bilqis.mlx.grade-a-user-accepted/20261015")
            self.assertEqual(len(report["experimental_risks"]), 2)
            self.assertEqual(report["operator_constraint"], "HUMAN_ONLY_NEURAL_OPTIMIZER_UPDATES")
            self.assertNotIn("HUMAN_ONLY_NEURAL_OPTIMIZER_UPDATES", report["blockers"])
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["train","--dry-run","--resume","--run-dir",tmp]),2)
                self.assertEqual(main(["train","--run-dir",tmp]),2)
            self.assertEqual(list(Path(tmp).iterdir()),[])

    @unittest.skipUnless(ORIGINAL_CHECKPOINT.is_file(), "Pinned whole student not mounted")
    def test_verified_source_preflight_is_real_not_synthetic_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(["train", "--dry-run", "--verify-source", "--run-dir", tmp])
            self.assertEqual(code, 0)
            receipt = json.loads(output.getvalue())["source_manifest_preflight"]
            self.assertEqual(receipt["verified_items"], 216)
            self.assertEqual(receipt["exam_rubric_sha256"],
                             "7f351f93b81a1d08a45dd53d5f253ad34c238019015e84284d50ca40378a1370")
            self.assertFalse(receipt["original_candidate_manifest_release_flag"])
            self.assertTrue(receipt["grade_a_user_acceptance_is_separate"])
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__=="__main__":
    unittest.main()
