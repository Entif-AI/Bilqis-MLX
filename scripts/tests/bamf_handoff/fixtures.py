"""Local repositories and bare upstreams for handoff behavior tests."""
import subprocess
import tempfile
import unittest
from pathlib import Path


class WriterHandoffFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / "work"
        self.remote = Path(self.temp.name) / "remote.git"
        subprocess.run(["git", "init", "--bare", "-q", str(self.remote)], check=True)
        subprocess.run(["git", "init", "-q", "-b", "work", str(self.repo)], check=True)
        self.run_git("config", "user.email", "test@example.invalid")
        self.run_git("config", "user.name", "Test")
        (self.repo / "file.txt").write_text("initial\n")
        self.run_git("add", ".")
        self.run_git("commit", "-qm", "initial")
        self.run_git("remote", "add", "origin", str(self.remote))
        self.run_git("push", "-q", "-u", "origin", "work")

    def run_git(self, *args: str) -> None:
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)
