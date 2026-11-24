"""Pre-push must exercise the same repository predicates as hosted PR CI."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from scripts.quality.pre_push import CI_GROUPS, LocalChecks, PrePushError, source_updates

ROOT = Path(__file__).resolve().parents[3]
HOSTED_STEPS = frozenset({
    "Resolve verification ledger location",
    "Restore trusted main verification receipts",
    "Resolve truthful comparison base",
    "Require all expensive verification surfaces",
    "Install historical semantic integrity dependencies",
    "Install portable custody dependencies",
    "Refresh main code smell inventory incrementally",
    "Prepare isolated Python readiness source",
    "Install BAMF readiness dependencies",
    "Install semantic profile dependencies",
    "Reconcile portable verification result",
})


class RecordingChecks(LocalChecks):
    def __init__(self, *, head="feature", abi="false", semantic="SKIP", failure=""):
        super().__init__(ROOT, {"HEAD_REF": head, "BASE_REF": "main"})
        self.abi = abi
        self.semantic = semantic
        self.failure = failure
        self.calls = []

    def dependencies(self, *requirements):
        return None

    def run(self, group, **extra):
        self.calls.append((group, extra))
        if group == self.failure:
            raise subprocess.CalledProcessError(1, group)

    def outputs(self, group):
        self.run(group)
        return {"run": self.abi} if group == "abi-scope" else {"action": self.semantic}


class PrePushTests(unittest.TestCase):
    def test_every_pr_workflow_command_is_shared_or_hosted_setup(self):
        shared = set()
        for path in sorted((ROOT / ".github/workflows").glob("*.yml")):
            source = path.read_text()
            if not re.search(r"(?m)^  pull_request:", source):
                continue
            commands = 0
            for step in re.split(r"(?m)^      - name: ", source)[1:]:
                name = step.splitlines()[0]
                command = re.search(r"(?m)^        run: (.*)$", step)
                if not command:
                    continue
                commands += 1
                group = re.search(r"bash scripts/quality/ci_checks\.sh ([a-z-]+)$",
                                  command.group(1))
                if group:
                    shared.add(group.group(1))
                else:
                    self.assertIn(name, HOSTED_STEPS, f"{path.name}: {name}")
            self.assertEqual(commands, len(re.findall(r"(?m)^        run:", source)), path.name)
        self.assertEqual(shared, CI_GROUPS)

    def test_branch_and_semantic_plans_cover_all_ci_groups(self):
        ordinary = RecordingChecks(abi="true", semantic="DIFF")
        ordinary.verify()
        bamf = RecordingChecks(head="codex/bamf-fix", semantic="FULL")
        bamf.verify()
        seen = {group for group, _ in ordinary.calls + bamf.calls}
        self.assertEqual(seen, CI_GROUPS | {"local-governance"})
        self.assertEqual([extra["SKOS_SHARD_INDEX"] for group, extra in bamf.calls
                          if group == "semantic-shard"], [str(i) for i in range(8)])
        self.assertIn(("legacy-semantic", {}), ordinary.calls)
        self.assertIn(("bamf-contracts", {}), bamf.calls)
        self.assertNotIn(("legacy-semantic", {}), bamf.calls)
        self.assertEqual(ordinary.calls[-1], ("readiness", {}))

    def test_failure_stops_before_readiness_and_invalid_plan_blocks(self):
        failed = RecordingChecks(failure="portable-custody")
        with self.assertRaises(subprocess.CalledProcessError):
            failed.verify()
        self.assertNotIn(("readiness", {}), failed.calls)
        with self.assertRaises(PrePushError):
            RecordingChecks(semantic="ERROR").verify()

    def test_git_ref_records(self):
        head = "a" * 40
        zero = "0" * 40
        self.assertEqual(source_updates([
            f"refs/heads/main {head} refs/heads/main {zero}",
            f"(delete) {zero} refs/heads/old {head}",
            f"refs/heads/main {head} refs/heads/other {zero}",
        ]), (head,))
        self.assertEqual(source_updates([f"(delete) {zero} refs/heads/old {head}"]), ())
        with self.assertRaises(PrePushError):
            source_updates(["malformed"])

    def test_tracked_husky_hook_blocks_real_git_push_without_generated_shim(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            local = root / "local"
            remote = root / "remote.git"
            local.mkdir()
            env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}

            def git(*args, check=True):
                return subprocess.run(["git", *args], cwd=local, env=env,
                                      capture_output=True, text=True, check=check)

            git("init", "-q", "-b", "main")
            git("init", "--bare", "-q", str(remote))
            git("config", "user.email", "fixture@example.test")
            git("config", "user.name", "Fixture")
            git("config", "core.hooksPath", ".husky")
            hook = local / ".husky/pre-push"
            hook.parent.mkdir()
            hook.write_bytes((ROOT / ".husky/pre-push").read_bytes())
            hook.chmod(0o755)
            (local / "source").write_text("fixture")
            git("add", "source")
            git("commit", "-qm", "test: fixture")
            binaries = root / "bin"
            binaries.mkdir()
            python = binaries / "python3"
            python.write_text("#!/bin/sh\nexit 17\n")
            python.chmod(0o755)
            env["PATH"] = str(binaries) + os.pathsep + env["PATH"]
            blocked = git("push", str(remote), "main", check=False)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertEqual(git("--git-dir", str(remote), "for-each-ref").stdout, "")
            python.write_text("#!/bin/sh\nexit 0\n")
            git("push", str(remote), "main")
            self.assertIn("refs/heads/main", git("--git-dir", str(remote), "for-each-ref").stdout)


if __name__ == "__main__":
    unittest.main()
