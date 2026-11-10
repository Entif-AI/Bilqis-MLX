"""Literal B13 custody proof for retained B08 reads."""
from dataclasses import replace
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.atlas_model_forward as forward_impl
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning._atlas_candidate.common import (
    RETAINED_STATE_ISSUER, STATE_SCHEMA,
)
from bilqis_mlx.learning.atlas_candidate import CandidateState
from bilqis_mlx.learning.atlas_engram_transaction import MotifAllocationSnapshot
from bilqis_mlx.learning.source_atoms.backbone import finalize_source_backbone_hidden
from bilqis_mlx.runtime.atlas_model import BamfCompiledBatch
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle import (
    admission, issue_initial_foundation_feature_authority,
    publish_bamf_generation, publish_initial_generation,
)
from bilqis_mlx.runtime.bamf_bundle.accepted_runtime import (
    bind_accepted_execution_cache,
)
from bilqis_mlx.runtime.bamf_bundle.admission import derive_successor_bundle
from bilqis_mlx.runtime.bamf_bundle.execution_cache import _new_execution_cache
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    acceptance, genesis_preparation, provision_source_authority_registry,
    with_source_authority_registry,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE


@unittest.skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class RetainedB13CustodyTests(unittest.TestCase):
    def _runtime_fixture(self):
        from bilqis_mlx.runtime.tests.model.test_atlas_model_retained import (
            AtlasModelRetainedMotifTests,
        )

        fixture = AtlasModelRetainedMotifTests(
            "test_retained_b08_hit_enters_the_same_loss_bearing_b09_trace")
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        return fixture._runtime_fixture()

    @staticmethod
    def _retained_state(parent, manifest):
        retained = object.__new__(CandidateState)
        for name, value in (
            ("optimizer", parent.retained_state.optimizer),
            ("policy", parent.retained_state.policy),
            ("allocations", MotifAllocationSnapshot(manifest)),
            ("optimizer_step", parent.retained_state.optimizer_step),
            ("custody", parent.retained_state.custody),
            ("step_proofs", ()),
            ("schema_version", STATE_SCHEMA),
            ("_issuance", RETAINED_STATE_ISSUER),
        ):
            object.__setattr__(retained, name, value)
        retained.__post_init__()
        return retained

    def _publish_retained_generation(
        self, run, source, compiled, manifest,
    ):
        feature_authority = issue_initial_foundation_feature_authority(
            source.selection)
        prepared = genesis_preparation(
            run_id="retained-proof", foundation_features=feature_authority)
        pointer = publish_initial_generation(run, prepared, reserve_gib=0.)
        parent = admission.load_accepted_generation(run)
        self.assertEqual(
            parent.extents.active_semantic_digest,
            compiled.extents.active_semantic_digest,
        )
        self.assertEqual(
            parent.extents.semantic_bank_count,
            compiled.extents.semantic_bank_count,
        )
        successor = derive_successor_bundle(
            parent,
            self._retained_state(parent, manifest),
            parent_manifest_sha256=pointer["manifest_sha256"],
            delivery_events=({"event": "RETAINED_MOTIF_PROOF"},),
        )
        successor = replace(
            successor,
            extents=compiled.extents,
            compiler_features={
                **successor.compiler_features,
                "factor_map_sha256": compiled.features.digest,
            },
            transition={
                "schema": "bilqis.mlx.bamf-generation-transition/v1",
                "kind": "PARAMETER_EXTENSION",
                "invalidate_derived_caches": True,
            },
        )
        provision_source_authority_registry(run, AUTHORITY)
        successor = with_source_authority_registry(successor, AUTHORITY)
        publish_bamf_generation(
            run, successor,
            acceptance=acceptance(successor, parent=parent.retained_state),
            reserve_gib=0.,
        )
        accepted = admission.load_accepted_generation(run)
        return bind_accepted_execution_cache(run), accepted.retained_state.optimizer.parameters

    def _assert_live_and_nonowned_paths(
        self, parameters, batch, cache, generation, slot_id,
    ):
        producer, accepted = forward_impl._source_producer(
            parameters, batch, generation, cache)
        finalize_source_backbone_hidden(producer)
        self.assertIs(accepted, cache)
        self.assertEqual(producer._motif_read.participating_slots, (slot_id,))
        self.assertEqual(producer._motif_read.dispositions[0][-1], "EXACT")

        unowned = _new_execution_cache(
            run_id=cache.run_id,
            generation=cache.generation,
            accepted_manifest_sha256=cache.accepted_manifest_sha256,
            generation_binding=cache.generation_binding,
            motif_manifest=cache.motif_manifest,
            source_authority_registry_sha256=cache.source_authority_registry_sha256,
        )
        with self.assertRaises(BilqisError) as error:
            forward_impl._source_producer(
                parameters, batch, generation, unowned)
        self.assertEqual(error.exception.context["reason"], "B13_EXECUTION_CACHE_REQUIRED")

    def _assert_absent_path(self, parameters, batch, generation):
        producer, accepted = forward_impl._source_producer(
            parameters, batch, generation, None)
        finalize_source_backbone_hidden(producer)
        self.assertIsNone(accepted)
        self.assertIsNone(producer._motif_read)

    def test_live_accepted_cache_owns_generation_bound_retained_hit(self):
        (compiled, _fixture_parameters, source, feature_schema, _plan, _fake_cache,
         spec, _extents, manifest, slot_id) = self._runtime_fixture()
        with TemporaryDirectory() as temporary, patch.dict(
            os.environ,
            {"BILQIS_DATA_PLANE": str(Path(temporary) / "plane.sqlite3")},
        ), patch.object(mlx_checkpoint, "assert_headroom"):
            run = Path(temporary) / "run"
            cache, parameters = self._publish_retained_generation(
                run, source, compiled, manifest)
            generation = execution_generation_digest(
                parameters, spec=spec, extents=compiled.extents)
            self.assertEqual(generation, cache.generation_binding)
            batch = BamfCompiledBatch(compiled, (source,), feature_schema)
            self._assert_live_and_nonowned_paths(
                parameters, batch, cache, generation, slot_id)
            self._assert_absent_path(parameters, batch, generation)
