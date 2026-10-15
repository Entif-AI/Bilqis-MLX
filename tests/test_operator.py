"""Human root commands must not accidentally begin optimization."""
from contextlib import redirect_stdout,redirect_stderr
import io
from pathlib import Path
import tempfile
import unittest
from bilqis_mlx.cli import main,DEFAULT_RUN
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
            self.assertIn("CURRICULUM HOLD",out.getvalue())

    def test_explicit_resume_only_and_training_is_hard_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=io.StringIO()
            with redirect_stdout(output):
                code=main(["train","--dry-run","--run-dir",tmp])
            self.assertEqual(code,0)
            self.assertIn("GRADE_A_NEW_RUN",output.getvalue())
            self.assertIn("NO_NEURAL_UPDATES",output.getvalue())
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["train","--dry-run","--resume","--run-dir",tmp]),2)
                self.assertEqual(main(["train","--run-dir",tmp]),2)
            self.assertEqual(list(Path(tmp).iterdir()),[])


if __name__=="__main__":
    unittest.main()
