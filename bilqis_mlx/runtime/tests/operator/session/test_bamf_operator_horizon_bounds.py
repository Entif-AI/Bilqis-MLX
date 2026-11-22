"""BAMF operator candidate-horizon bounds stay aligned across CLI and runtime."""
from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.presentation.operator_cli.parser import parse_args
from bilqis_mlx.runtime.bamf_operator._session_execution import operate as operate_session
from bilqis_mlx.runtime.bamf_operator.session import operate_bamf
from bilqis_mlx.runtime.bamf_operator.session_limits import (
    DEFAULT_CANDIDATE_HORIZON,
    MAX_CANDIDATE_HORIZON,
)
from bilqis_mlx.runtime.bamf_operator.session_support import BamfOperatorResult


class _Observer:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def update(self, **_kwargs):
        return None

    def finish(self, _outcome):
        return None


class _Metrics:
    wait_seconds = 0.0
    overlap_seconds = 0.0
    prepared_steps = 0
    serial_steps = 0


class BamfOperatorHorizonBoundsTests(unittest.TestCase):
    def test_cli_default_stays_sixteen_and_explicit_twenty_four_is_admitted(self):
        self.assertEqual(DEFAULT_CANDIDATE_HORIZON, 16)
        self.assertEqual(MAX_CANDIDATE_HORIZON, 24)
        self.assertEqual(
            parse_args(["train", "--resume"]).steps_per_visit,
            DEFAULT_CANDIDATE_HORIZON,
        )
        self.assertEqual(
            parse_args([
                "train", "--resume", "--steps-per-visit",
                str(MAX_CANDIDATE_HORIZON),
            ]).steps_per_visit,
            MAX_CANDIDATE_HORIZON,
        )

    def test_runtime_accepts_twenty_four_and_rejects_twenty_five(self):
        with TemporaryDirectory() as temporary, patch(
                "bilqis_mlx.runtime.source_prefetch.source_prefetch_pool",
                side_effect=AssertionError("bounds passed")):
            with self.assertRaisesRegex(AssertionError, "bounds passed"):
                operate_bamf(
                    temporary, minutes=1,
                    steps_per_visit=MAX_CANDIDATE_HORIZON,
                )
        with self.assertRaises(BilqisError):
            operate_bamf(
                "/run", minutes=1,
                steps_per_visit=MAX_CANDIDATE_HORIZON + 1,
            )

    def test_stop_receipt_preserves_explicit_twenty_four_step_bound(self):
        record_stop = Mock(return_value="a" * 64)
        current = SimpleNamespace(
            generation=7,
            retained_state=SimpleNamespace(optimizer_step=138),
        )

        result = operate_session(
            Path("/run"),
            minutes=1,
            max_visits=1,
            steps_per_visit=MAX_CANDIDATE_HORIZON,
            reserve_gib=0.0,
            source_prefetch_workers=0,
            progress=None,
            max_horizon=MAX_CANDIDATE_HORIZON,
            worker_counts=(0, 1, 2),
            invalid=lambda reason: (_ for _ in ()).throw(ValueError(reason)),
            metrics_type=_Metrics,
            source_pool_factory=lambda _workers: nullcontext(None),
            null_context=nullcontext,
            operator_lock=lambda _run: nullcontext(),
            visit_fn=lambda *_args, **_kwargs: "REJECTED",
            observer_type=lambda *_args, **_kwargs: _Observer(),
            emit_progress=lambda *_args, **_kwargs: None,
            monotonic=lambda: 0.0,
            load_generation=lambda _run: current,
            result_type=BamfOperatorResult,
            resource_snapshot=None,
            record_stop=record_stop,
            elapsed_clock=None,
        )

        self.assertEqual(result.visits, 1)
        self.assertEqual(result.rejected, 1)
        self.assertEqual(
            record_stop.call_args.kwargs["steps_per_visit"],
            MAX_CANDIDATE_HORIZON,
        )


if __name__ == "__main__":
    unittest.main()
