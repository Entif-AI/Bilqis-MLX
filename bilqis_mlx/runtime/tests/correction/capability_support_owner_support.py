"""Shared accepted capability-support fixtures for C09 tests."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import mlx.core as mx

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.factory.teaching import content_digest
from bilqis_mlx.learning.atlas_candidate import (
    begin_candidate, candidate_step, resolve_candidate,
)
from bilqis_mlx.learning._retention.tests.execution_fixtures import execution_provenance
from bilqis_mlx.learning.source_atoms import SourceAtomRow
from bilqis_mlx.runtime.atlas_capability_support_owner import load_capability_support_owner
from bilqis_mlx.runtime.atlas_training_authority import _issue as issue_training_authority
from bilqis_mlx.runtime.atlas_training_contracts import (
    BamfDeliveryProvenance, BamfTrainingRow, _issue_training_batch,
)
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents, ModelTopologySpecV2
from bilqis_mlx.runtime.source_execution import source_content_digest
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, bind_accepted_correction_authority,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    HP, NAME, candidate, parent_state, retention_decision, shape_patch,
)
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactSelection
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef


TARGET = "capability:target"
SOURCE_ROW = "source:capability-support:row"
SOURCE_ID = "fixture-source"
SOURCE_FAMILY = "source-family:capability-support"
EPISODE = "episode:capability-support"
SOURCE_RELEASE = "4" * 64
GENERATION = "5" * 64
def immediate_dependencies(source_row=SOURCE_ROW, source_id=SOURCE_ID):
    return tuple(sorted((
        DependencyRef(DependencyKind.SOURCE, source_row),
        DependencyRef(DependencyKind.SOURCE, source_id),
        DependencyRef(DependencyKind.OPERATOR, "operator:fixture-support"),
        DependencyRef(DependencyKind.RELEASE, "source-release:" + SOURCE_RELEASE),
        DependencyRef(DependencyKind.POLICY, "policy:fixture-support"),
        DependencyRef(DependencyKind.RIGHTS, "rights:fixture-support"),
        DependencyRef(DependencyKind.TIME, "time:asof:fixture-support"),
    )))


IMMEDIATE_DEPENDENCIES = immediate_dependencies()


def training_authority(
    *, capability=TARGET, source_row=SOURCE_ROW,
    source_id=SOURCE_ID,
    source_family=SOURCE_FAMILY, episode=EPISODE,
    generation_binding=GENERATION,
):
    row = {"id": source_row, "capability": capability}
    provenance = BamfDeliveryProvenance(
        source_row, source_content_digest((row,)), source_id, capability,
        None, (), 1, 1, None, 0,
        source_family, episode, immediate_dependencies(source_row, source_id))
    training_row = BamfTrainingRow(None, None, None, provenance)
    batch = _issue_training_batch(
        SOURCE_RELEASE, generation_binding, content_digest((row,)), capability,
        (training_row,))
    source = SourceAtomRow(
        AtlasArtifactSelection(
            "/fixture", "1" * 64, SOURCE_RELEASE, "2" * 64),
        row, {}, Path("."), 17, 1)
    return issue_training_authority(batch, source, provenance)


def source_qualified_state(parent=None, *, authority=None, **authority_kwargs):
    parent = parent_state() if parent is None else parent
    transaction = begin_candidate(parent)
    authority = training_authority(**authority_kwargs) if authority is None else authority
    spec = ModelTopologySpecV2()
    extents = GenerationExtents(
        1, 1, "a" * 64, parent.allocations.manifest.digest, "c" * 64)
    with shape_patch():
        transaction = candidate_step(
            transaction,
            {NAME: mx.array([[3., 4.], [0., 0.]], dtype=mx.float32)},
            execution_provenance(
                transaction.parent, rows=(0,),
                candidate_step=transaction.update_steps + 1),
            HP, spec=spec, extents=extents, loss_bearing=True, max_norm=1.,
            training_authority=authority)
    return parent, transaction, resolve_candidate(transaction, accepted=True), authority


class CapabilitySupportOwnerFixture(unittest.TestCase):
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

    def publish_support(self, *, authority=None, authority_registry=None):
        parent, transaction, retained, authority = source_qualified_state(
            authority=authority)
        bundle = candidate(retained)
        if authority_registry is not None:
            bundle = replace(bundle, correction_frontier={
                **bundle.correction_frontier,
                "source_authority_registry_sha256": authority_registry.digest,
            })
        decision = retention_decision(parent=parent, retained=retained)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            published = accept_and_publish(
                self.run, bundle, retained, decision=decision,
                feature_sha256=bundle.extents.factor_map_digest,
                training_authorities=transaction.training_authorities)
            if authority_registry is not None:
                bind_accepted_correction_authority(self.run, authority_registry)
        return published, authority

    def load_support(self, authority_registry=None):
        with shape_patch():
            return load_capability_support_owner(
                self.run, TARGET, authority_registry)
