"""C08.4 distributed execution is selectable at the human-started operator boundary."""
from pathlib import Path
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.bamf_operator import session
from bilqis_mlx.runtime.atlas_resources import DistributedRank
from bilqis_mlx.runtime.c08_distributed_executor import (
    DistributedExecutorBinding, configure_mlx_distributed_execution,
)


class DistributedResourceModeTests(unittest.TestCase):
    def test_executor_binding_is_owner_issued_worker_cohort(self):
        workers = (
            DistributedRank(0, "rank-0", "Apple M3 Ultra"),
            DistributedRank(1, "rank-1", "Apple M2 Ultra"))
        with self.assertRaises(Exception):
            DistributedExecutorBinding()
        with patch(
                "bilqis_mlx.runtime.c08_distributed_executor."
                "require_distributed_backend", return_value="ring"), patch(
                    "bilqis_mlx.runtime.c08_distributed_executor.version",
                    return_value="0.test"):
            binding = configure_mlx_distributed_execution(
                workers, hosts=("127.0.0.1",), partition_seed=17,
                backend="ring", python_executable="/python",
                working_directory="/repo")
        self.assertEqual(len(binding.profile.workers), 2)
        self.assertEqual(binding.profile.mlx_version, "0.test")
        command = binding._command(
            Path("/tmp/request"), Path("/tmp/response"), "a" * 64)
        self.assertIn("mlx.launch", command)
        self.assertIn("-n", command)
        self.assertIn("2", command)
        self.assertIn("c08_distributed_worker", " ".join(command))

    def test_operator_can_derive_profile_from_bound_executor(self):
        workers = (
            DistributedRank(0, "rank-0", "Apple M3 Ultra"),
            DistributedRank(1, "rank-1", "Apple M2 Ultra"))
        with patch(
                "bilqis_mlx.runtime.c08_distributed_executor."
                "require_distributed_backend", return_value="ring"), patch(
                    "bilqis_mlx.runtime.c08_distributed_executor.version",
                    return_value="0.test"):
            binding = configure_mlx_distributed_execution(
                workers, hosts=("127.0.0.1",), partition_seed=17,
                backend="ring")

        def operate_impl(*_args, visit_fn, **_kwargs):
            with patch.object(session, "_visit", return_value="VISIT") as visit:
                visit_fn(Path("/run"), 100.0)
            visit.assert_called_once_with(
                Path("/run"), 100.0, distributed_profile=binding.profile,
                distributed_executor=binding)
            return "RESULT"

        with patch.object(session, "_operate_impl", side_effect=operate_impl):
            self.assertEqual(session.operate_bamf(
                Path("/run"), minutes=1, source_prefetch_workers=0,
                distributed_executor=binding), "RESULT")

    def test_visit_threads_distributed_mode_into_prepared_visit(self):
        profile = object()
        executor = object()
        with patch.object(session, "_visit_impl", return_value="VISIT") as visit_impl, \
                patch.object(session, "prepare_bamf_visit", return_value="PREPARED") as prepare:
            self.assertEqual(
                session._visit(
                    Path("/run"), 100.0, steps_per_visit=1, progress=None,
                    source_prefetch_workers=0, distributed_profile=profile,
                    distributed_executor=executor),
                "VISIT")
            bound_prepare = visit_impl.call_args.kwargs["prepare_visit"]
            self.assertEqual(bound_prepare(Path("/run"), steps_per_visit=1), "PREPARED")
        prepare.assert_called_once_with(
            Path("/run"), steps_per_visit=1,
            distributed_profile=profile, distributed_executor=executor)

    def test_operator_public_mode_binds_visit_function(self):
        profile = object()
        executor = object()

        def operate_impl(*_args, visit_fn, **_kwargs):
            with patch.object(session, "_visit", return_value="VISIT") as visit:
                self.assertEqual(visit_fn(Path("/run"), 100.0), "VISIT")
            visit.assert_called_once_with(
                Path("/run"), 100.0,
                distributed_profile=profile, distributed_executor=executor)
            return "RESULT"

        with patch.object(session, "_operate_impl", side_effect=operate_impl):
            self.assertEqual(
                session.operate_bamf(
                    Path("/run"), minutes=1, source_prefetch_workers=0,
                    distributed_profile=profile, distributed_executor=executor),
                "RESULT")


if __name__ == "__main__":
    unittest.main()
