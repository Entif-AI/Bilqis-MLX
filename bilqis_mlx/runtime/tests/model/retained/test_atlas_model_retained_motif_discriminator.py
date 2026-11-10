"""Literal B08 same-frame hit/miss discriminator on both retained read sites."""
from dataclasses import replace
import hashlib
from unittest import TestCase, skipUnless
from unittest.mock import patch

import mlx.core as mx
import numpy as np

from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import begin_candidate
from bilqis_mlx.learning.atlas_engram import MotifManifest, MotifSlot
from bilqis_mlx.learning.atlas_engram_reads.source_owner import _B13_EXECUTION_SEAL
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, group_eligibility
from bilqis_mlx.learning.atlas_readout import ControlAction, DecisionOutput
from bilqis_mlx.learning.frame_embeddings import semantic_bank_views
from bilqis_mlx.learning.source_atoms.backbone import start_retained_source_backbone_producer
from bilqis_mlx.learning.source_atoms.backbone_receipts import QUALIFIED_MISS
from bilqis_mlx.runtime.atlas_artifact_owner import AtlasFeatureArtifactOwner
from bilqis_mlx.runtime.atlas_candidate_step import production_candidate_step
from bilqis_mlx.runtime.atlas_model import BamfCompiledBatch, bamf_value_and_grad
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle.execution_cache import _new_execution_cache
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents
from bilqis_mlx.runtime.tests.model.execution.active_semantic_rows_support import (
    snapshot_active_semantic_rows,
)
from bilqis_mlx.runtime.topology_v2.ledger import bamf_parameter_census
import bilqis_mlx.runtime.atlas_model_forward as forward_impl
import bilqis_mlx.runtime.tests.model.test_atlas_model_retained as retained_tests
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE


def _nonmatching_manifest(manifest):
    return MotifManifest(
        manifest.semantic_release,
        tuple(
            MotifSlot(slot.slot_id, replace(
                slot.key, relation_signature=hashlib.sha256(
                    f"b08-miss-{slot.slot_id}".encode()).hexdigest()))
            for slot in manifest.slots
        ),
        capacity=manifest.capacity,
    )


def _candidate_step(case, parameters, manifest, spec, extents, gradient):
    admitted = set(gradient.execution.visible_identity_rows)
    admitted.update(gradient.execution.semantic_denominator_identity_rows)
    ages = tuple(IdentityRowAge(bank, row, 0) for bank, row in sorted(admitted))
    eligibility = group_eligibility(
        "FULL", bamf_parameter_census(spec, extents), ages)
    parent = case._retained_parent(parameters, manifest, spec, extents, ages)
    transaction = production_candidate_step(
        begin_candidate(parent), loss_bearing_target=True, gradient_execution=gradient,
        group_eligible=eligibility, spec=spec, extents=extents,
        run_id="test-retained", generation=2, parent_manifest_sha256="8" * 64,
        parent_candidate_identity_sha256=candidate_identity_digest(parent),
        parent_optimizer_step=0, topology_digest=spec.digest, candidate_step_ordinal=1,
        teacher_hparams=AdamWHyperparameters(.001, (.9, .95), 1e-8, .01), max_norm=1.0)
    return parent, transaction


def _miss_gradient(parameters, compiled, source, feature_schema, plan, spec, extents, manifest):
    generation = execution_generation_digest(parameters, spec=spec, extents=extents)
    cache = _new_execution_cache(
        run_id="test-retained", generation=1, accepted_manifest_sha256="8" * 64,
        generation_binding=generation, motif_manifest=manifest)
    with patch.object(forward_impl, "require_accepted_execution_cache",
                      return_value=cache), patch(
        "bilqis_mlx.runtime.bamf_bundle.execution_cache.require_accepted_execution_cache",
        return_value=cache):
        return bamf_value_and_grad(
            parameters, BamfCompiledBatch(
                compiled, (source,), feature_schema,
                snapshot_active_semantic_rows(
                    compiled, plan.snapshot, run_id=cache.run_id,
                    generation=cache.generation)),
            replace(plan, generation_binding=generation),
            (DecisionOutput("finish", ControlAction.END_FRAME),),
            {"finish": True}, cache=cache)


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class RetainedMotifDiscriminatorTests(TestCase):
    def test_same_frame_exact_hit_vs_nonmatching_key_is_safe_at_both_sites(self):
        case = retained_tests.AtlasModelRetainedMotifTests(
            "test_retained_b08_hit_enters_the_same_loss_bearing_b09_trace")
        (compiled, parameters, source, feature_schema, plan, _cache,
         spec, extents, manifest, slot_id) = case._runtime_fixture()
        miss_manifest = _nonmatching_manifest(manifest)
        miss_extents = GenerationExtents(
            extents.semantic_bank_count, extents.motif_page_count,
            extents.active_semantic_digest, miss_manifest.digest,
            extents.factor_map_digest)
        miss_compiled = replace(compiled, extents=miss_extents)
        hit_active_rows = snapshot_active_semantic_rows(
            compiled, plan.snapshot, run_id="test-retained", generation=1)
        hit_banks = semantic_bank_views(
            parameters, extents, compiled.features.semantic_release,
            hit_active_rows.active_indices)
        miss_active_rows = snapshot_active_semantic_rows(
            miss_compiled, plan.snapshot, run_id="test-retained", generation=1)
        miss_banks = semantic_bank_views(
            parameters, miss_extents, miss_compiled.features.semantic_release,
            miss_active_rows.active_indices)
        hit = start_retained_source_backbone_producer(
            compiled, parameters, (source,), feature_schema, hit_banks, manifest,
            AtlasFeatureArtifactOwner(compiled.features, feature_schema),
            seal=_B13_EXECUTION_SEAL)
        hit_g1 = hit.advance()
        missed = start_retained_source_backbone_producer(
            miss_compiled, parameters, (source,), feature_schema, miss_banks,
            miss_manifest,
            AtlasFeatureArtifactOwner(miss_compiled.features, feature_schema),
            seal=_B13_EXECUTION_SEAL)
        missed_g1 = missed.advance()
        self.assertEqual(
            (hit._input_motif_read.participating_slots, hit._motif_read.participating_slots),
            ((slot_id,), (slot_id,)))
        expected = mx.zeros_like(hit._encoded.global_seeds).at[0, -1, 0].add(1.0)
        np.testing.assert_array_equal(
            np.asarray(hit._input_motif_read.hidden - hit._encoded.global_seeds),
            np.asarray(expected))
        np.testing.assert_array_equal(
            np.asarray(hit._motif_read.hidden - hit._session.results[0].hidden),
            np.asarray(expected))
        self.assertEqual(hit.receipts[0].motif_disposition, "SOURCE_QUALIFIED_HIT")
        self.assertEqual(hit_g1.motif_disposition, "SOURCE_QUALIFIED_HIT")
        self.assertEqual(missed._input_motif_read.participating_slots, ())
        self.assertEqual(missed._motif_read.participating_slots, ())
        np.testing.assert_array_equal(
            np.asarray(missed._input_motif_read.hidden), np.asarray(missed._encoded.global_seeds))
        np.testing.assert_array_equal(
            np.asarray(missed._motif_read.hidden), np.asarray(missed._session.results[0].hidden))
        self.assertEqual(missed.receipts[0].motif_disposition, QUALIFIED_MISS)
        self.assertEqual(missed_g1.motif_disposition, QUALIFIED_MISS)
        gradient = _miss_gradient(
            parameters, miss_compiled, source, feature_schema, plan, spec,
            miss_extents, miss_manifest)
        self.assertEqual(
            tuple(read.participating_slots for read in gradient.execution.motif_reads),
            ((), ()))
        self.assertFalse(any(name.startswith("motif.site.")
                             for name in gradient.execution.dense_parameter_names))
        parent, transaction = _candidate_step(
            case, parameters, miss_manifest, spec, miss_extents, gradient)
        for name in parent.optimizer.parameters:
            if name.startswith("motif."):
                for field in ("parameters", "m", "v", "update_counts"):
                    np.testing.assert_array_equal(
                        np.asarray(getattr(transaction.optimizer, field)[name]),
                        np.asarray(getattr(parent.optimizer, field)[name]))
