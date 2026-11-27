import signal
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from bilqis_mlx.runtime.memory_safety import GIB, MIB, TrainerMemoryPolicy
from bilqis_mlx.runtime.trainer_resource_governor import (
    GovernorResult, run_governed_command, run_governed_train,
    supervise_running_process,
)


class DehGuhbohnayhituhTests(unittest.TestCase):
    def test_real_child_is_killed_when_physical_footprint_crosses_trip_boundary(self):
        policy = TrainerMemoryPolicy(
            ceiling_bytes=160 * MIB,
            warning_bytes=96 * MIB,
            trip_bytes=128 * MIB,
            sample_interval_seconds=0.01,
        )

        result = run_governed_command([
            sys.executable, "-B", "-c",
            "import time; payload=bytearray(192*1024*1024); time.sleep(5)",
        ], policy=policy)

        self.assertEqual(result.status, "RESOURCE_ENVELOPE_EXCEEDED")
        self.assertGreaterEqual(result.max_physical_footprint_bytes, policy.trip_bytes)
        self.assertNotEqual(result.returncode, 0)

    def test_custom_cli_ceiling_is_forwarded_to_child_mlx_policy(self):
        result = GovernorResult(
            "EXITED", 0, None, 0, 0, False,
            TrainerMemoryPolicy.from_gib(14).to_dict())
        with tempfile.TemporaryDirectory() as directory, patch(
                "bilqis_mlx.runtime.trainer_resource_governor.run_governed_command",
                return_value=result) as run:
            self.assertEqual(run_governed_train(
                ["train", "--human-run", "--memory-ceiling-gib", "14"],
                run_dir=Path(directory) / "aspirant", ceiling_gib=14), 0)

        environment = run.call_args.kwargs["env"]
        self.assertEqual(environment["BILQIS_TRAINER_MEMORY_CEILING_GIB"], "14")

    def test_kills_process_group_before_policy_ceiling(self):
        process = SimpleNamespace(pid=4321, returncode=None)
        process.poll = Mock(side_effect=[None, None, None])
        process.wait = Mock(return_value=-signal.SIGKILL)
        killpg = Mock()
        samples = iter((9 * GIB, 10 * GIB, 11 * GIB + 1))
        policy = TrainerMemoryPolicy.from_gib(12)

        result = supervise_running_process(
            process,
            policy=policy,
            footprint_bytes=lambda _pid: next(samples),
            sleep=lambda _seconds: None,
            kill_process_group=killpg,
        )

        self.assertEqual(result.status, "RESOURCE_ENVELOPE_EXCEEDED")
        self.assertEqual(result.guard_reason, "process physical footprint ceiling")
        self.assertGreaterEqual(result.max_physical_footprint_bytes, policy.trip_bytes)
        killpg.assert_called_once_with(process.pid, signal.SIGKILL)

    def test_normal_exit_does_not_kill(self):
        process = SimpleNamespace(pid=9876, returncode=0)
        process.poll = Mock(return_value=0)
        killpg = Mock()

        result = supervise_running_process(
            process,
            policy=TrainerMemoryPolicy.from_gib(12),
            footprint_bytes=lambda _pid: 2 * GIB,
            sleep=lambda _seconds: None,
            kill_process_group=killpg,
        )

        self.assertEqual(result.status, "EXITED")
        self.assertEqual(result.returncode, 0)
        killpg.assert_not_called()


if __name__ == "__main__":
    unittest.main()
