"""Shared A01-backed setup for Factory-to-B11 integration tests."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory

from bilqis_mlx.factory.teaching import describe_delivered_teaching
from bilqis_mlx.learning.source_atoms.tests.backbone_test_support import (
    SourceBackboneTestBase,
)
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle import authenticate_bamf_candidate_feature_context
from bilqis_mlx.runtime.factory_training_bridge import prepare_factory_training_batch
from bilqis_mlx.runtime.tests.capability.factory.retention.factory_retention_live_support import (
    genesis_bundle, live_factory_context,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY
from bilqis_mlx.semantics.atlas.feature_io import persist_feature_manifest


class FactoryTrainingBridgeFixture(SourceBackboneTestBase):
    def setUp(self):
        artifact = os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
        if not artifact or not Path(artifact).is_dir():
            self.skipTest("BILQIS_A01_ATLAS_BUNDLE fixture is not mounted")
        self.artifact = Path(artifact)
        super().setUp()
        self.root = Path.cwd()
        self.context, _ = live_factory_context(
            self.root, (self.root / "vendor/legacy-v16").resolve())
        self.candidate, _ = genesis_bundle(
            self, self.snapshot, self.schema, self.artifact)
        authenticated = authenticate_bamf_candidate_feature_context(
            self.candidate, str(self.artifact))
        self.feature_root = TemporaryDirectory()
        self.addCleanup(self.feature_root.cleanup)
        self.feature_receipt = persist_feature_manifest(
            authenticated.features, self.feature_root.name)
        self.generation = execution_generation_digest(
            self.candidate.retained_state.optimizer.parameters,
            spec=self.candidate.topology, extents=self.candidate.extents)
        self.feature_context = authenticated

    def prepare(self, capability, seed, each):
        rows = tuple(self.context.draw_rows(
            seed=seed, capability=capability, each=each))
        execution = self.context.release.execution_plan.capability_map[capability]
        delivery = describe_delivered_teaching(
            self.context.release, capability,
            execution.teaching_option_ids[0], rows)
        return rows, prepare_factory_training_batch(
            self.context, self.candidate, str(self.artifact),
            self.feature_receipt.path, rows, self.generation,
            capability=capability, delivery=delivery, requested_count=each + 2,
            source_seed=seed, source_each=each,
            optimizer_step_seed=7,
            teacher_strategy={"policy": "c02-parent-integration"})

    def accepted_source_context(self, run_dir: Path):
        from bilqis_mlx.runtime import admission as factory_admission

        release_file = factory_admission._persist_executable_factory_release(
            run_dir, self.context.release)
        receipt = {
            "factory_release_sha256": self.context.release.release_sha256,
            "factory_release_file": release_file,
        }
        return AcceptedRuntimeHost(run_dir).source_context(
            receipt, graph=self.context.graph,
            source_root=self.context.source_root)


__all__ = ("FactoryTrainingBridgeFixture",)
