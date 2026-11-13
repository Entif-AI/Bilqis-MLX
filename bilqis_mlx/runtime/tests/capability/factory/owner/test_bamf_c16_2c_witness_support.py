"""Cheap regressions for the C16.2c witness orchestration helpers."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint

from bilqis_mlx.factory.assessment import assessment_scope_contract
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.accepted_teacher_custody import derive_c03_successor_bundle
from bilqis_mlx.runtime.bamf_bundle import publish_bamf_generation
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance,
    accepted_state,
    publish_genesis,
    shape_patch,
)
from bilqis_mlx.runtime.tests.capability.factory.retention.factory_retention_live_support import (
    live_factory_context,
)

from .bamf_c16_2c_witness_support import (
    accepted_witness_receipt,
    bound_visit,
    finalize_witness_receipt,
)
from .c16_2c_resource_preflight import require_mlx_verification_resources


class C16_2CWitnessSupportTests(unittest.TestCase):
    @staticmethod
    def _resource_result(command, *, memory=81, swap_total=57344, swap_free=16384,
                         processes=None, **_kwargs):
        if command == ["memory_pressure", "-Q"]:
            return subprocess.CompletedProcess(
                command, 0,
                stdout=f"System-wide memory free percentage: {memory}%\n",
                stderr="")
        if command == ["sysctl", "vm.swapusage"]:
            used = swap_total - swap_free
            return subprocess.CompletedProcess(
                command, 0,
                stdout=(f"vm.swapusage: total = {swap_total:.2f}M  "
                        f"used = {used:.2f}M  free = {swap_free:.2f}M  (encrypted)\n"),
                stderr="")
        raise AssertionError(command)

    def test_resource_preflight_accepts_serial_healthy_studio(self):
        with patch.dict(os.environ, {"BILQIS_TEST_WORKERS": "1"}), patch(
            "bilqis_mlx.runtime.tests.capability.factory.owner."
            "c16_2c_resource_preflight.subprocess.run",
            side_effect=self._resource_result,
        ):
            receipt = require_mlx_verification_resources()

        self.assertEqual(receipt["test_workers"], 1)
        self.assertEqual(receipt["memory_free_percent"], 81)
        self.assertGreater(receipt["swap_free_fraction"], .1)

    def test_resource_preflight_rejects_parallel_workers(self):
        with patch.dict(os.environ, {"BILQIS_TEST_WORKERS": "4"}):
            with self.assertRaisesRegex(RuntimeError, "C16_2C_MLX_WORKERS_UNSAFE"):
                require_mlx_verification_resources()

    def test_resource_preflight_observes_near_saturated_swap_without_veto(self):
        def saturated(command, **kwargs):
            return self._resource_result(command, swap_free=512)

        with patch.dict(os.environ, {"BILQIS_TEST_WORKERS": "1"}), patch(
            "bilqis_mlx.runtime.tests.capability.factory.owner."
            "c16_2c_resource_preflight.subprocess.run",
            side_effect=saturated,
        ):
            receipt = require_mlx_verification_resources()
        self.assertLess(receipt["swap_free_fraction"], .01)

    def test_resource_preflight_rejects_low_free_memory(self):
        def pressured(command, **kwargs):
            return self._resource_result(command, memory=12)

        with patch.dict(os.environ, {"BILQIS_TEST_WORKERS": "1"}), patch(
            "bilqis_mlx.runtime.tests.capability.factory.owner."
            "c16_2c_resource_preflight.subprocess.run",
            side_effect=pressured,
        ):
            with self.assertRaisesRegex(RuntimeError, "C16_2C_MLX_MEMORY_PRESSURE"):
                require_mlx_verification_resources()

    def test_future_capability_is_blocked_before_model_execution(self):
        repo = Path.cwd()
        context, _ = live_factory_context(repo, (repo / "vendor/legacy-v16").resolve())

        with self.assertRaises(BilqisError) as caught:
            context.require_capabilities(("FUTURE.X",))

        self.assertIn(
            "FACTORY_EXECUTABLE_GENERATION_UNKNOWN_CAPABILITY",
            str(caught.exception),
        )

    def test_two_admitted_families_share_one_release_and_whole_school_scope(self):
        repo = Path.cwd()
        context, _ = live_factory_context(repo, (repo / "vendor/legacy-v16").resolve())
        requested = ("A.IDENTITY", "B.IDBOOLOPS")
        context.require_capabilities(requested)
        capabilities = tuple(
            item.capability_id for item in context.release.execution_plan.capabilities
        )
        contract = assessment_scope_contract(context.release, capabilities)

        self.assertTrue(set(requested) <= set(capabilities))
        self.assertEqual(tuple(contract.capabilities), capabilities)

    def test_launch_receipt_can_finalize_after_independent_cold_stage(self):
        parent = type("Parent", (), {
            "generation": 0,
            "retained_state": type("State", (), {"optimizer_step": 0})(),
        })()
        successor = type("Successor", (), {
            "generation": 1,
            "retained_state": type("State", (), {"optimizer_step": 1})(),
            "extents": type("Extents", (), {"factor_map_digest": "f" * 64})(),
        })()
        decision = type("Decision", (), {"to_record": lambda self: {"accepted": True}})()
        context = type("Context", (), {"release": type("Release", (), {
            "release_sha256": "r" * 64,
            "source_bindings": type("Bindings", (), {
                "source_attestation_sha256": "s" * 64,
                "digest": lambda self: "d" * 64,
            })(),
        })()})()
        bound = type("Bound", (), {"identity": type("Identity", (), {
            "selection_seed": 3,
            "to_record": lambda self: {"visit_id": "v" * 64},
        })()})()
        warm = {"optimizer_step": 2}

        with patch(
            "bilqis_mlx.runtime.tests.capability.factory.owner."
            "bamf_c16_2c_witness_support.retained_digest",
            side_effect=("p" * 64, "n" * 64),
        ):
            accepted = accepted_witness_receipt(
                parent,
                successor,
                {"manifest_sha256": "m" * 64},
                decision,
                context,
                bound,
                warm,
                ".",
                process_nonce="warm-process",
            )
        final = finalize_witness_receipt(accepted, dict(warm))

        self.assertEqual(accepted["schema"], "bilqis.mlx.c16.2c-accepted-stage/v1")
        self.assertEqual(final["schema"], "bilqis.mlx.c16.2c-launch-witness/v1")
        self.assertTrue(final["cold_next_update_equivalent"])

    def test_bound_visit_reuses_mature_c03_lineage_without_bootstrap(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "run"
            with patch.dict(
                os.environ, {"BILQIS_DATA_PLANE": str(root / "plane.sqlite3")}
            ):
                with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
                    publish_genesis(run, run_seed=71)
                with shape_patch():
                    parent = load_accepted_generation(run)
                    bound, _provenance, _policy = bound_visit(
                        parent, run, capability="C.ADD", lesson_grade="A"
                    )
                    retained = accepted_state(parent.retained_state, parent.extents)
                    successor = derive_c03_successor_bundle(
                        run,
                        retained,
                        bound,
                        next_seed=72,
                        cursor="lesson:1",
                        delivery_events=(
                            {"event": "C16_2C_TEST_VISIT", "optimizer_step": 1},
                        ),
                    )
                with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
                    publish_bamf_generation(
                        run,
                        successor,
                        acceptance=acceptance(
                            successor, parent=parent.retained_state
                        ),
                        reserve_gib=0.0,
                    )
                with shape_patch():
                    mature = load_accepted_generation(run)
                    rebound, _provenance, _policy = bound_visit(
                        mature, run, capability="C.ADD", lesson_grade="A"
                    )

        self.assertEqual(rebound.identity.generation, 1)
        self.assertEqual(rebound.identity.selection_seed, 72)
        self.assertEqual(rebound.identity.cursor, "lesson:1")


if __name__ == "__main__":
    unittest.main()
