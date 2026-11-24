"""Prove receipt reuse, invalidation and the main-workflow trust boundary."""
from contextlib import redirect_stdout
import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts.quality.restore_verification_ledger import main as restore_main, restore, trusted_run
from scripts.quality.run_verified import execute
from scripts.quality.verification_frontier import frontier_digest
from scripts.quality.verification_ledger import ledger_path


class VerificationReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "repo"
        self.root.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "fixture@example.test")
        self.git("config", "user.name", "Fixture")
        self.commit("scripts/check_bamf_flow_control.py", "# gate\n")
        self.marker = self.base / "calls"
        self.database = self.base / "ledger.sqlite3"
        self.enterContext(patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true",
            "RUNNER_ENVIRONMENT": "github-hosted",
            "ImageOS": "fixture",
            "ImageVersion": "1",
            "RUNNER_OS": "fixture",
            "RUNNER_ARCH": "ARM64",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_RUN_ID": "101",
            "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_REPOSITORY": "Entif-AI/Bilqis-MLX",
            "BILQIS_VERIFICATION_LEDGER": str(self.database),
            "BILQIS_VERIFICATION_FULL": "0",
            "BILQIS_VERIFICATION_TRUSTED_LEDGER": "",
            "BILQIS_VERIFICATION_TRUSTED_SHA256": "",
        }))

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, text=True).strip()

    def commit(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        self.git("add", path)
        self.git("commit", "-qm", "fixture")

    def run_check(self, status=0, *, full=False, check="bamf-readiness"):
        command = [sys.executable, "-B", "-c",
                   f"from pathlib import Path; p=Path({str(self.marker)!r}); "
                   f"p.open('a').write('x'); raise SystemExit({status})"]
        stream = io.StringIO()
        with redirect_stdout(stream):
            result = execute(self.root, check, command, full=full)
        return result, stream.getvalue()

    def pr_context(self):
        return patch.dict(os.environ, {"GITHUB_REF": "refs/pull/9/merge",
                                      "GITHUB_EVENT_NAME": "pull_request",
                                      "GITHUB_RUN_ID": "102"})

    def restore_producer(self):
        # Model the artifact handoff through the real restore entrypoint, with
        # only the remote provider response replaced by a fixture.
        dest = self.base / "trusted" / "ledger.sqlite3"
        github_env = self.base / "github_env"
        run = TrustedArtifactTests().run_metadata(id=101, run_attempt=1)
        with patch.dict(os.environ, {"GITHUB_ENV": str(github_env), "GITHUB_OUTPUT": ""}), patch(
            "scripts.quality.restore_verification_ledger._runs", return_value=[run]
        ), patch("scripts.quality.restore_verification_ledger.subprocess.run") as download:
            def provide(args, **_kwargs):
                target = Path(args[args.index("--dir") + 1]) / "ledger.sqlite3"
                target.write_bytes(self.database.read_bytes())
                return subprocess.CompletedProcess(args, 0)
            download.side_effect = provide
            self.assertEqual(restore_main(["--scope", "readiness", "--destination", str(dest)]), 0)
        values = dict(line.split("=", 1) for line in github_env.read_text().splitlines())
        self.assertEqual(values["BILQIS_VERIFICATION_TRUSTED_SHA256"],
                         hashlib.sha256(dest.read_bytes()).hexdigest())
        return values

    def test_main_pass_reuses_across_pr_and_full_override_executes(self):
        self.assertEqual(self.run_check()[0], 0)
        with self.pr_context():
            # A local database alone is not evidence in CI.
            self.assertNotIn("TEST_EVIDENCE_REUSED", self.run_check()[1])
            trusted = self.restore_producer()
            with patch.dict(os.environ, trusted):
                result, log = self.run_check()
                self.assertEqual(result, 0)
                self.assertIn("TEST_EVIDENCE_REUSED check=bamf-readiness", log)
                self.assertEqual(self.marker.read_text(), "xx")
                self.assertEqual(self.run_check(full=True)[0], 0)
            self.assertEqual(self.marker.read_text(), "xxx")

    def test_failure_and_pr_success_do_not_create_reusable_pass(self):
        self.assertEqual(self.run_check(7)[0], 7)
        self.assertEqual(self.run_check(7)[0], 7)
        with self.pr_context():
            self.assertEqual(self.run_check()[0], 0)
            self.assertEqual(self.run_check()[0], 0)
        self.assertEqual(self.marker.read_text(), "xxxx")

    def test_environment_dirty_source_and_committed_changes_invalidate(self):
        self.assertEqual(self.run_check()[0], 0)
        with self.pr_context():
            trusted = self.restore_producer()
            with patch.dict(os.environ, trusted):
                with patch.dict(os.environ, {"ImageVersion": "2"}):
                    self.assertNotIn("TEST_EVIDENCE_REUSED", self.run_check()[1])
                target = self.root / "scripts/check_bamf_flow_control.py"
                target.write_text("# changed\n", encoding="utf-8")
                self.assertIn("identity-unavailable", self.run_check()[1])
                self.git("add", ".")
                self.git("commit", "-qm", "change")
                self.assertNotIn("TEST_EVIDENCE_REUSED", self.run_check()[1])
        self.assertEqual(self.marker.read_text(), "xxxx")

    def test_complete_frontier_changes_for_application_and_runtime_source(self):
        readiness = frontier_digest(self.root, "bamf-readiness")
        self.commit("apps/mission-control/view.js", "const view = 1;\n")
        changed = frontier_digest(self.root, "bamf-readiness")
        self.assertNotEqual(changed, readiness)
        self.commit("bilqis_mlx/runtime.py", "value = 1\n")
        self.assertNotEqual(frontier_digest(self.root, "bamf-readiness"), changed)

    def test_tampered_trusted_input_is_not_reused(self):
        self.assertEqual(self.run_check()[0], 0)
        with self.pr_context():
            trusted = self.restore_producer()
            Path(trusted["BILQIS_VERIFICATION_TRUSTED_LEDGER"]).write_bytes(b"changed")
            with patch.dict(os.environ, trusted):
                self.assertNotIn("TEST_EVIDENCE_REUSED", self.run_check()[1])
        self.assertEqual(self.marker.read_text(), "xx")

    def test_ignored_source_and_npm_configuration_invalidate(self):
        self.commit(".gitignore", "*.pyc\n")
        self.assertEqual(self.run_check()[0], 0)
        with self.pr_context():
            trusted = self.restore_producer()
            with patch.dict(os.environ, trusted):
                with patch.dict(os.environ, {"NODE_OPTIONS": "--no-warnings"}):
                    self.assertNotIn("TEST_EVIDENCE_REUSED", self.run_check()[1])
                (self.root / "shadow.pyc").write_bytes(b"ignored")
                self.assertIn("identity-unavailable", self.run_check()[1])
        self.assertEqual(self.marker.read_text(), "xxx")

    def test_common_git_directory_shares_local_ledger(self):
        other = self.base / "worktree"
        self.git("worktree", "add", "-q", "-b", "other", str(other))
        with patch.dict(os.environ, {"BILQIS_VERIFICATION_LEDGER": "", "GITHUB_ACTIONS": "false"}):
            self.assertEqual(ledger_path(self.root), ledger_path(other))
            self.assertEqual(ledger_path(self.root), self.root / ".git/verification-ledger.sqlite3")


class TrustedArtifactTests(unittest.TestCase):
    def run_metadata(self, **changes):
        return dict(path=".github/workflows/quality.yml", head_branch="main",
                    event="push", status="completed", conclusion="success",
                    head_repository={"full_name": "Entif-AI/Bilqis-MLX"},
                    head_sha="a" * 40, id=123, run_attempt=2) | changes

    def test_only_successful_main_workflow_is_accepted(self):
        repo = "Entif-AI/Bilqis-MLX"
        with patch.dict(os.environ, {"GITHUB_RUN_ID": "999"}):
            self.assertTrue(trusted_run(self.run_metadata(), repo))
            for change in (
                {"event": "pull_request"}, {"head_branch": "feature"},
                {"conclusion": "failure"}, {"status": "in_progress"},
                {"path": ".github/workflows/other.yml"},
                {"head_repository": {"full_name": "fork/Bilqis-MLX"}},
                {"id": 999}, {"run_attempt": 0},
            ):
                with self.subTest(change=change):
                    self.assertFalse(trusted_run(self.run_metadata(**change), repo))

    def test_restore_uses_exact_successful_main_attempt(self):
        repo = "Entif-AI/Bilqis-MLX"
        with tempfile.TemporaryDirectory() as temporary:
            dest = Path(temporary) / "restored" / "ledger.sqlite3"
            with patch.dict(os.environ, {
                "GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                "GITHUB_REPOSITORY": repo, "GITHUB_RUN_ID": "999",
                "BILQIS_VERIFICATION_FULL": "0",
            }), patch("scripts.quality.restore_verification_ledger._runs",
                      return_value=[self.run_metadata(id=124, event="pull_request"),
                                    self.run_metadata()]), patch(
                      "scripts.quality.restore_verification_ledger.subprocess.run") as download:
                def write_download(args, **_kwargs):
                    self.assertEqual(args[3], "123")
                    self.assertEqual(args[args.index("--name") + 1],
                                     "verification-ledger-readiness-2")
                    folder = Path(args[args.index("--dir") + 1])
                    (folder / "ledger.sqlite3").write_bytes(b"fixture evidence")
                    return subprocess.CompletedProcess(args, 0)
                download.side_effect = write_download
                self.assertTrue(restore(dest, "readiness"))
                self.assertEqual(dest.read_bytes(), b"fixture evidence")
                self.assertEqual(download.call_count, 1)


if __name__ == "__main__":
    unittest.main()
