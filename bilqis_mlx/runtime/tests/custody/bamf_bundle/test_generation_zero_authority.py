"""B13.6 generation-zero custody is distinct from C05 retention acceptance."""
from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import (
    InitialGenerationBinding, PreparedInitialGeneration,
    load_bamf_generation, publish_bamf_generation, publish_initial_generation,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, candidate, genesis_preparation, parent_state, shape_patch,
)


class GenerationZeroAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish_genesis(self, *, run_seed=73):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            prepared = genesis_preparation(run_seed=run_seed)
            pointer = publish_initial_generation(
                self.run, prepared, reserve_gib=0.)
        return prepared, pointer

    def test_genesis_persists_run_seed_and_zero_foundation_optimizer(self):
        prepared, pointer = self.publish_genesis(run_seed=73)
        with shape_patch():
            student = load_bamf_generation(self.run / "bamf-state.json")

        self.assertEqual(student.generation, 0)
        self.assertEqual(student.run_identity.run_seed, 73)
        self.assertEqual(student.run_identity.digest,
                         prepared.candidate.run_identity.digest)
        self.assertEqual(student.retained_state.optimizer_step, 0)
        self.assertEqual(student.retained_state.policy.mode, "FOUNDATION")
        self.assertEqual(student.parent_manifest_sha256, None)
        self.assertEqual(pointer["acceptance_sha256"], prepared.binding.digest)
        for tree in (student.retained_state.optimizer.m,
                     student.retained_state.optimizer.v,
                     student.retained_state.optimizer.update_counts):
            for value in tree.values():
                self.assertFalse(bool(mx.any(value)))

    def test_generation_zero_refuses_c05_candidate_acceptance(self):
        legacy = candidate(parent_state())
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            with self.assertRaises(BilqisError) as failure:
                publish_bamf_generation(
                    self.run, legacy, acceptance=acceptance(legacy), reserve_gib=0.)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_BOOTSTRAP_REQUIRED")

    def test_persisted_bootstrap_record_never_regains_live_authority(self):
        prepared = None
        with shape_patch():
            prepared = genesis_preparation(run_seed=91)
        parsed = InitialGenerationBinding.from_record(prepared.binding.to_record())
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            with self.assertRaises(BilqisError):
                publish_initial_generation(
                    self.run,
                    PreparedInitialGeneration(prepared.candidate, parsed),
                    reserve_gib=0.)

    def test_exact_retry_converges_and_conflicting_seed_cannot_replace_genesis(self):
        prepared, first = self.publish_genesis(run_seed=101)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            second = publish_initial_generation(
                self.run, prepared, reserve_gib=0.)
            foreign = genesis_preparation(run_seed=102)
            with self.assertRaises(BilqisError):
                publish_initial_generation(self.run, foreign, reserve_gib=0.)
        self.assertEqual(first, second)
        self.assertEqual(
            json.loads((self.run / "bamf-state.json").read_text()), first)

    def test_bootstrap_binding_cannot_authorize_successor_publication(self):
        prepared, first = self.publish_genesis(run_seed=117)
        successor = replace(
            prepared.candidate, generation=1,
            parent_manifest_sha256=first["manifest_sha256"],
            transition={
                "schema": "bilqis.mlx.bamf-generation-transition/v1",
                "kind": "RETAINED_CANDIDATE",
                "invalidate_derived_caches": False,
            })
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            with self.assertRaises(BilqisError) as failure:
                publish_bamf_generation(
                    self.run, successor, acceptance=prepared.binding,
                    reserve_gib=0.)
        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_GENERATION_ACCEPTANCE_REQUIRED")


if __name__ == "__main__":
    unittest.main()
