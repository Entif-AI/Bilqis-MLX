"""Post-C05 distributed telemetry belongs to the retention owner."""
from types import SimpleNamespace
import unittest

from bilqis_mlx.runtime.bamf_operator.session_parts.retention import (
    _distributed_retention_metrics,
)


class DistributedRetentionMetricsTests(unittest.TestCase):
    def _step(self):
        return SimpleNamespace(realized_cost={
            "c08_distributed_manifest_digest": "a" * 64,
            "c08_distributed_source_release": "b" * 64,
        })

    def test_accepted_visit_records_retained_gain_and_accepted_rate(self):
        evaluation = SimpleNamespace(decision=SimpleNamespace(
            outcome_scores=(("cap", 1, 2, 4),), policy_sha256="c" * 64))
        observer = SimpleNamespace(record={"retention_wall_seconds": 1.0})
        resource = {"wall_seconds": 2.0, "optimizer_steps": 1}
        _distributed_retention_metrics(
            (self._step(),), evaluation, SimpleNamespace(accepted=True),
            observer, resource)
        self.assertEqual(resource["c08_distributed_evaluation_seconds"], 1.0)
        self.assertEqual(
            resource["c08_distributed_accepted_steps_per_hour"], 1200.0)
        self.assertEqual(
            resource["c08_distributed_retained_capability_gain"], 0.25)
        self.assertEqual(
            resource["c08_distributed_source_contract_digest"], "b" * 64)
        self.assertEqual(
            resource["c08_distributed_evaluation_contract_digest"], "c" * 64)

    def test_rejected_visit_records_zero_retained_gain_and_accepted_rate(self):
        evaluation = SimpleNamespace(decision=SimpleNamespace(
            outcome_scores=(("cap", 2, 1, 4),), policy_sha256="c" * 64))
        observer = SimpleNamespace(record={"retention_wall_seconds": 1.0})
        resource = {"wall_seconds": 2.0, "optimizer_steps": 1}
        _distributed_retention_metrics(
            (self._step(),), evaluation, SimpleNamespace(accepted=False),
            observer, resource)
        self.assertEqual(resource["c08_distributed_accepted_steps_per_hour"], 0.0)
        self.assertEqual(
            resource["c08_distributed_retained_capability_gain"], 0.0)


if __name__ == "__main__":
    unittest.main()
