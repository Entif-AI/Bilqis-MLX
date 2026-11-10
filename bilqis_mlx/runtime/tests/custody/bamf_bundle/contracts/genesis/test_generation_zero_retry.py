"""Generation-zero retries authenticate exact state and recover durable custody."""
from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.bamf_bundle.publication as publication
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_generation_authority, publish_initial_generation,
    recover_sealed_initial_generation,
)
from bilqis_mlx.runtime.bamf_bundle.genesis.records import (
    InitialGenerationBinding, optimizer_hyperparameters_digest,
)
from bilqis_mlx.runtime.bamf_bundle import source_authority_custody as custody
from bilqis_mlx.runtime.bamf_bundle.records import invalid
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    genesis_preparation, shape_patch,
)
from bilqis_mlx.runtime.atlas_source_authority import SourceAuthorityRegistry
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactIdentity
from bilqis_mlx.semantics.tests.core.test_atlas_export_clearance import REGISTRY
from bilqis_mlx.state_dag import persist, read_current


class GenerationZeroRetryTests(unittest.TestCase):
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

    def _prepare(self, *, run_seed):
        with shape_patch():
            return genesis_preparation(run_seed=run_seed)

    def _publish(self, prepared):
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            return publish_initial_generation(
                self.run, prepared, reserve_gib=0.)

    def _advance_factory_source(self, prepared):
        source = Path(prepared.factory_authority.source_run_dir)
        current = read_current(source)
        advanced = dict(current)
        advanced["generation"] = current["generation"] + 1
        school = dict(current["school"])
        checkpoint = dict(school["current_student"])
        checkpoint.update(
            optimizer_step=checkpoint["optimizer_step"] + 1,
            sha256="8" * 64, filename="bundles/advanced")
        school["current_student"] = checkpoint
        advanced["school"] = school
        persist(source, advanced)

    def _cold_recover(self, prepared, *, optimizer_digest=None):
        student = prepared.candidate
        feature_source = student.compiler_features["feature_source"]
        return recover_sealed_initial_generation(
            self.run,
            expected_run_id=student.run_id,
            expected_run_seed=student.run_identity.run_seed,
            expected_topology_digest=student.topology.digest,
            expected_atlas_artifact=AtlasArtifactIdentity(
                feature_source["atlas_bundle_id"],
                feature_source["release_sha256"],
                feature_source["source_bundle_id"],
            ),
            expected_optimizer_hyperparameters_sha256=(
                optimizer_digest
                or optimizer_hyperparameters_digest(student.optimizer_hyperparameters)),
        )

    def test_completed_retry_rejects_post_publication_numerical_mutation(self):
        prepared = self._prepare(run_seed=307)
        first = self._publish(prepared)
        before = json.loads((self.run / "bamf-state.json").read_text())
        parameter = next(iter(prepared.candidate.retained_state.optimizer.parameters.values()))
        parameter[0] += 1

        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                self.assertRaises(BilqisError) as failure:
            publish_initial_generation(self.run, prepared, reserve_gib=0.)

        self.assertEqual(
            failure.exception.context["reason"],
            "BAMF_INITIAL_GENERATION_BINDING_DRIFT")
        self.assertEqual(
            json.loads((self.run / "bamf-state.json").read_text()), before)
        self.assertEqual(before, first)

    def test_pre_pointer_crash_recovers_exact_genesis_after_factory_advances(self):
        prepared = self._prepare(run_seed=311)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                patch.object(
                    publication, "_atomic_pointer",
                    side_effect=RuntimeError("pointer crash")):
            with self.assertRaisesRegex(RuntimeError, "pointer crash"):
                publish_initial_generation(self.run, prepared, reserve_gib=0.)

        self.assertFalse((self.run / "bamf-state.json").exists())
        bundles = tuple((self.run / "bamf-bundles").iterdir())
        acceptances = tuple((self.run / "bamf-acceptance").iterdir())
        self.assertEqual(len(bundles), 1)
        self.assertEqual(len(acceptances), 1)
        durable_manifest = bundles[0].name

        self._advance_factory_source(prepared)
        with shape_patch():
            recovered = self._cold_recover(prepared)

        self.assertEqual(recovered["manifest_sha256"], durable_manifest)
        self.assertEqual(
            json.loads((self.run / "bamf-state.json").read_text()), recovered)
        with shape_patch():
            student, manifest = load_bamf_generation_authority(
                self.run / "bamf-state.json")
        self.assertEqual(manifest, durable_manifest)
        self.assertEqual(student.run_identity.run_seed, 311)

    def test_post_trust_seal_crash_recovers_after_factory_advances(self):
        prepared = self._prepare(run_seed=3111)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                patch.object(
                    publication, "_write_acceptance",
                    side_effect=RuntimeError("acceptance crash")):
            with self.assertRaisesRegex(RuntimeError, "acceptance crash"):
                publish_initial_generation(self.run, prepared, reserve_gib=0.)

        self.assertFalse((self.run / "bamf-state.json").exists())
        self.assertFalse((self.run / "bamf-acceptance").exists())
        bundles = tuple((self.run / "bamf-bundles").iterdir())
        self.assertEqual(len(bundles), 1)
        durable_manifest = bundles[0].name

        self._advance_factory_source(prepared)
        with shape_patch():
            recovered = self._cold_recover(prepared)

        self.assertEqual(recovered["manifest_sha256"], durable_manifest)
        self.assertEqual(len(tuple((self.run / "bamf-acceptance").iterdir())), 1)
        acceptance = json.loads(next((self.run / "bamf-acceptance").iterdir()).read_text())
        self.assertIn("binding_sha256", acceptance)
        parsed = InitialGenerationBinding.from_record(acceptance)
        self.assertEqual(parsed.digest, acceptance["binding_sha256"])
        with shape_patch():
            student, manifest = load_bamf_generation_authority(
                self.run / "bamf-state.json")
        self.assertEqual(manifest, durable_manifest)
        self.assertEqual(student.run_identity.run_seed, 3111)

    def test_sealed_genesis_retry_requires_exact_host_root_after_factory_advance(self):
        prepared = self._prepare(run_seed=3112)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                patch.object(
                    publication, "_write_acceptance",
                    side_effect=RuntimeError("acceptance crash")):
            with self.assertRaisesRegex(RuntimeError, "acceptance crash"):
                publish_initial_generation(self.run, prepared, reserve_gib=0.)

        self.assertFalse((self.run / "bamf-state.json").exists())
        durable_manifest = next((self.run / "bamf-bundles").iterdir()).name
        self._advance_factory_source(prepared)

        def missing_root():
            invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED")

        with shape_patch(), patch.object(
                custody, "read_host_system_source_authority_registry",
                side_effect=missing_root), patch.object(
                mlx_checkpoint, "assert_headroom"), \
                self.assertRaises(BilqisError) as missing:
            self._cold_recover(prepared)
        self.assertEqual(
            missing.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_REQUIRED")
        self.assertFalse((self.run / "bamf-state.json").exists())

        drift = SourceAuthorityRegistry((replace(
            REGISTRY.keys[0], owner_id="source:drifted-host-root"),))
        with shape_patch(), patch.object(
                custody, "read_host_system_source_authority_registry",
                return_value=drift), patch.object(
                mlx_checkpoint, "assert_headroom"), \
                self.assertRaises(BilqisError) as mismatch:
            self._cold_recover(prepared)
        self.assertEqual(
            mismatch.exception.context["reason"],
            "BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_MISMATCH")
        self.assertFalse((self.run / "bamf-state.json").exists())

        with shape_patch():
            recovered = self._cold_recover(prepared)
        self.assertEqual(recovered["manifest_sha256"], durable_manifest)
        self.assertEqual(
            json.loads((self.run / "bamf-state.json").read_text()), recovered)

    def test_post_pointer_crash_retry_reconciles_pending_delivery_before_success(self):
        prepared = self._prepare(run_seed=312)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                patch.object(
                    publication, "reconcile_bamf_outbox",
                    side_effect=RuntimeError("outbox crash")):
            with self.assertRaisesRegex(RuntimeError, "outbox crash"):
                publish_initial_generation(self.run, prepared, reserve_gib=0.)

        before = json.loads((self.run / "bamf-state.json").read_text())
        self.assertFalse((self.run / "events.jsonl").exists())

        retried = self._publish(prepared)

        self.assertEqual(retried, before)
        events = [
            json.loads(line)
            for line in (self.run / "events.jsonl").read_text().splitlines()
        ]
        self.assertEqual([event["event"] for event in events], ["FIXTURE_GENESIS"])
        self.assertEqual([event["optimizer_step"] for event in events], [0])

    def test_unpointed_conflicting_genesis_cannot_replace_durable_acceptance(self):
        prepared = self._prepare(run_seed=313)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                patch.object(
                    publication, "_atomic_pointer",
                    side_effect=RuntimeError("pointer crash")):
            with self.assertRaisesRegex(RuntimeError, "pointer crash"):
                publish_initial_generation(self.run, prepared, reserve_gib=0.)
        foreign = self._prepare(run_seed=317)

        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                self.assertRaises(BilqisError):
            publish_initial_generation(self.run, foreign, reserve_gib=0.)

        self.assertFalse((self.run / "bamf-state.json").exists())
        self.assertEqual(len(tuple((self.run / "bamf-bundles").iterdir())), 1)
        self.assertEqual(len(tuple((self.run / "bamf-acceptance").iterdir())), 1)

    def test_cold_recovery_optimizer_digest_mismatch_is_read_only(self):
        prepared = self._prepare(run_seed=319)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"), \
                patch.object(
                    publication, "_write_acceptance",
                    side_effect=RuntimeError("acceptance crash")):
            with self.assertRaisesRegex(RuntimeError, "acceptance crash"):
                publish_initial_generation(self.run, prepared, reserve_gib=0.)
        before = tuple(
            (str(path.relative_to(self.run)), path.is_dir(),
             None if path.is_dir() else path.read_bytes())
            for path in (self.run, *sorted(self.run.rglob("*")))
        )

        with shape_patch(), self.assertRaises(BilqisError):
            self._cold_recover(prepared, optimizer_digest="0" * 64)

        after = tuple(
            (str(path.relative_to(self.run)), path.is_dir(),
             None if path.is_dir() else path.read_bytes())
            for path in (self.run, *sorted(self.run.rglob("*")))
        )
        self.assertEqual(after, before)
        self.assertFalse((self.run / "bamf-state.json").exists())


if __name__ == "__main__":
    unittest.main()
