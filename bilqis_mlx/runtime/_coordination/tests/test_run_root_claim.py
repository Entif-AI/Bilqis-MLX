"""Physical-parent run-root claim contracts."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime._coordination import run_root_claim


class RunRootClaimTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_claim_uses_parent_inode_and_creates_no_target_child(self):
        parent = self.root / "runs"
        parent.mkdir()
        target = parent / "legal-run-name"

        with run_root_claim(target, create_parent=False):
            self.assertFalse(target.exists())
            self.assertEqual(tuple(parent.iterdir()), ())

    def test_create_parent_creates_only_parent_chain_and_fsyncs_chain(self):
        target = self.root / "outer" / "inner" / "run"
        calls = []

        def record(path):
            calls.append(Path(path))

        with patch(
                "bilqis_mlx.runtime._coordination.run_root_claim._fsync_directory",
                side_effect=record):
            with run_root_claim(target, create_parent=True):
                self.assertTrue(target.parent.is_dir())
                self.assertFalse(target.exists())

        self.assertEqual(calls, [target.parent, target.parent.parent, self.root])

    def test_missing_parent_without_create_fails_without_mutation(self):
        target = self.root / "missing" / "run"

        with self.assertRaises(BilqisError) as failure:
            with run_root_claim(target, create_parent=False):
                self.fail("claim body must not run")

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_RUN_ROOT_CLAIM_UNAVAILABLE")
        self.assertFalse(target.parent.exists())

    def test_aliases_to_same_physical_parent_serialize(self):
        parent = self.root / "physical"
        parent.mkdir()
        alias = self.root / "alias"
        alias.symlink_to(parent, target_is_directory=True)
        entered = threading.Event()
        release = threading.Event()
        second_entered = threading.Event()

        def first():
            with run_root_claim(parent / "run-a", create_parent=False):
                entered.set()
                release.wait(5)

        def second():
            entered.wait(5)
            with run_root_claim(alias / "run-b", create_parent=False):
                second_entered.set()

        with ThreadPoolExecutor(max_workers=2) as pool:
            one = pool.submit(first)
            two = pool.submit(second)
            self.assertTrue(entered.wait(5))
            self.assertFalse(second_entered.wait(0.05))
            release.set()
            one.result(timeout=5)
            two.result(timeout=5)
        self.assertTrue(second_entered.is_set())

    def test_acquire_failure_maps_to_unavailable(self):
        parent = self.root / "runs"
        parent.mkdir()

        with patch(
                "bilqis_mlx.runtime._coordination.run_root_claim.fcntl.flock",
                side_effect=OSError("no lock")), self.assertRaises(BilqisError) as failure:
            with run_root_claim(parent / "run", create_parent=False):
                self.fail("claim body must not run")

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_RUN_ROOT_CLAIM_UNAVAILABLE")

    def test_release_failure_after_success_is_distinct(self):
        parent = self.root / "runs"
        parent.mkdir()
        owner = import_module("bilqis_mlx.runtime._coordination.run_root_claim")
        real = owner.fcntl.flock

        def fail_unlock(fd, operation):
            if operation == owner.fcntl.LOCK_UN:
                raise OSError("unlock failed")
            return real(fd, operation)

        with patch.object(owner.fcntl, "flock", side_effect=fail_unlock), \
                self.assertRaises(BilqisError) as failure:
            with run_root_claim(parent / "run", create_parent=False):
                pass

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_RUN_ROOT_CLAIM_RELEASE_FAILED")

    def test_body_error_wins_and_release_failure_is_note(self):
        parent = self.root / "runs"
        parent.mkdir()
        owner = import_module("bilqis_mlx.runtime._coordination.run_root_claim")
        real = owner.fcntl.flock

        def fail_unlock(fd, operation):
            if operation == owner.fcntl.LOCK_UN:
                raise OSError("unlock failed")
            return real(fd, operation)

        original = RuntimeError("body failed")
        with patch.object(owner.fcntl, "flock", side_effect=fail_unlock), \
                self.assertRaises(RuntimeError) as failure:
            with run_root_claim(parent / "run", create_parent=False):
                raise original

        self.assertIs(failure.exception, original)
        self.assertIn(
            "BAMF_RUN_ROOT_CLAIM_RELEASE_FAILED:unlock",
            getattr(original, "__notes__", ()))


if __name__ == "__main__":
    unittest.main()
