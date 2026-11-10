"""B08 parent acceptance for both retained motif read sites in the real B11 path."""
from dataclasses import replace
import hashlib
from unittest import TestCase, skipUnless
from unittest.mock import patch
import mlx.core as mx
import numpy as np
from bilqis_mlx.learning.atlas_acceptance import candidate_identity_digest
from bilqis_mlx.learning.atlas_candidate import begin_candidate, resolve_candidate
from bilqis_mlx.learning.atlas_engram import MotifManifest, MotifSlot
from bilqis_mlx.learning.atlas_engram_reads.source_owner import _B13_EXECUTION_SEAL
from bilqis_mlx.learning.atlas_plasticity import IdentityRowAge, group_eligibility
from bilqis_mlx.learning.atlas_readout import (
    AnswerPlan, ControlAction, DecisionKind, DecisionOutput, DecisionSpec,
)
from bilqis_mlx.learning.source_atoms.backbone import (
    start_retained_source_backbone_producer, start_source_backbone_producer,
)
from bilqis_mlx.learning.source_atoms.backbone_receipts import QUALIFIED_MISS
from bilqis_mlx.runtime.atlas_artifact_owner import AtlasFeatureArtifactOwner
from bilqis_mlx.runtime.atlas_candidate_step import production_candidate_step
from bilqis_mlx.runtime.atlas_execution_binder import bind_execution_provenance
from bilqis_mlx.runtime.atlas_model import BamfCompiledBatch, bamf_value_and_grad
from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle.execution_cache import _new_execution_cache
from bilqis_mlx.runtime.model_topology_v2 import GenerationExtents
import bilqis_mlx.runtime.atlas_model_forward as forward_impl
import bilqis_mlx.runtime.tests.model.test_atlas_model_retained as retained_tests
from bilqis_mlx.runtime.topology_v2.ledger import bamf_parameter_census
import bilqis_mlx.semantics.frame_adapters.public_formal_schema_rights_registry as rights_registry
from bilqis_mlx.semantics.tests.context.test_public_formal_schema_rights_owner import (
    PublicFormalSchemaRightsOwnerTests,
)
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE
@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class RetainedMotifSiteIntegrationTests(TestCase):
    def _candidate_step(self, case, parameters, manifest, spec, extents, gradient):
        admitted = set(gradient.execution.visible_identity_rows)
        admitted.update(gradient.execution.semantic_denominator_identity_rows)
        ages = tuple(IdentityRowAge(bank, row, 0) for bank, row in sorted(admitted))
        eligibility = group_eligibility(
            "FULL", bamf_parameter_census(spec, extents), ages)
        parent = case._retained_parent(parameters, manifest, spec, extents, ages)
        kwargs = dict(
            group_eligible=eligibility, spec=spec, extents=extents,
            run_id="test-retained", generation=2,
            parent_manifest_sha256="8" * 64,
            parent_candidate_identity_sha256=candidate_identity_digest(parent),
            parent_optimizer_step=0, topology_digest=spec.digest,
            candidate_step_ordinal=1)
        transaction = production_candidate_step(
            begin_candidate(parent), loss_bearing_target=True,
            gradient_execution=gradient,
            teacher_hparams=AdamWHyperparameters(.001, (.9, .95), 1e-8, .01),
            max_norm=1.0, **kwargs)
        return parent, transaction, eligibility, kwargs
    def _nondegenerate_gradient(self):
        case = retained_tests.AtlasModelRetainedMotifTests(
            "test_retained_b08_hit_enters_the_same_loss_bearing_b09_trace")
        (compiled, parameters, source, feature_schema, plan, _cache,
         spec, extents, manifest, slot_id) = case._runtime_fixture()
        role = plan.allowed_output_schema.schema.roles[0]
        (first_identity, first), (second_identity, second) = (
            case._source_owned_unseen_concepts(compiled, source, plan))
        parameters = dict(parameters)
        parameters["readout.state_norm"] = mx.ones_like(
            parameters["readout.state_norm"])
        parameters["readout.output_norm"] = mx.ones_like(
            parameters["readout.output_norm"])
        for identity, sign in ((first_identity, 1.0), (second_identity, -1.0)):
            bank, row = identity
            name = f"identity.bank.{bank}"
            parameters[name] = parameters[name].at[row, 0].add(sign)
        generation = execution_generation_digest(
            parameters, spec=spec, extents=extents)
        value_plan = AnswerPlan(
            plan.modality_id, plan.input_prefix_end,
            (
                DecisionSpec(
                    "emit", role.role_id, 0, DecisionKind.CONTROL,
                    (ControlAction.EMIT_VALUE,)),
                DecisionSpec(
                    "value", role.role_id, 0, DecisionKind.VALUE,
                    (first, second), ("emit",)),
                DecisionSpec(
                    "finish", None, 0, DecisionKind.CONTROL,
                    (ControlAction.END_FRAME,), ("value",)),
            ),
            plan.allowed_output_schema, plan.snapshot, plan.source_span, generation,
        )
        cache = _new_execution_cache(
            run_id="test-retained", generation=1,
            accepted_manifest_sha256="8" * 64,
            generation_binding=generation, motif_manifest=manifest)
        with patch.object(
                forward_impl, "require_accepted_execution_cache",
                return_value=cache), patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache.require_accepted_execution_cache",
            return_value=cache,
        ):
            gradient = bamf_value_and_grad(
                parameters,
                BamfCompiledBatch(compiled, (source,), feature_schema),
                value_plan,
                (DecisionOutput("value", first),),
                {"value": True}, cache=cache)
        return case, parameters, manifest, spec, extents, slot_id, gradient
    def test_both_retained_sites_backpropagate_on_a_nondegenerate_loss(self):
        _case, _parameters, _manifest, _spec, _extents, slot_id, gradient = (
            self._nondegenerate_gradient())
        self.assertGreater(float(gradient.loss_total), 0.0)
        self.assertEqual(
            tuple(read.participating_slots for read in gradient.execution.motif_reads),
            ((slot_id,), (slot_id,)),
        )
        motif_gradients = {
            name: value for name, value in gradient.gradients.items()
            if name == "motif.page.0" or name.startswith("motif.site.")
        }
        self.assertTrue(all(
            bool(mx.all(mx.isfinite(value))) for value in motif_gradients.values()))
        for name in (
            "motif.page.0",
            "motif.site.0.projection", "motif.site.0.gate_feature",
            "motif.site.0.bias", "motif.site.1.projection",
            "motif.site.1.gate_hidden", "motif.site.1.gate_feature",
            "motif.site.1.bias",
        ):
            self.assertGreater(float(mx.abs(gradient.gradients[name]).sum()), 0.0)
    def test_two_site_update_rejects_back_to_the_exact_retained_parent(self):
        case, parameters, manifest, spec, extents, slot_id, gradient = (
            self._nondegenerate_gradient())
        parent, transaction, _eligibility, kwargs = self._candidate_step(
            case, parameters, manifest, spec, extents, gradient)
        self.assertEqual(int(transaction.optimizer.update_counts["motif.page.0"][slot_id]), 1)
        provenance = bind_execution_provenance(loss_bearing_target=True,
                                               loss_execution=gradient.execution, **kwargs)
        for site_index in (0, 1):
            for suffix in ("projection", "norm", "gate_hidden", "gate_feature", "bias"):
                name = f"motif.site.{site_index}.{suffix}"
                self.assertTrue(provenance.mask.parameter(name).whole_parameter)
                self.assertEqual(int(transaction.optimizer.update_counts[name]), 1)
        self.assertIs(resolve_candidate(transaction, accepted=False), parent)
    def test_empty_retained_manifest_executes_two_bitwise_safe_misses(self):
        case = retained_tests.AtlasModelRetainedMotifTests(
            "test_retained_b08_hit_enters_the_same_loss_bearing_b09_trace")
        (compiled, parameters, source, feature_schema, plan, _cache,
         spec, extents, manifest, _slot_id) = case._runtime_fixture()
        empty = MotifManifest(manifest.semantic_release)
        miss_extents = GenerationExtents(
            extents.semantic_bank_count, extents.motif_page_count,
            extents.active_semantic_digest, empty.digest, extents.factor_map_digest)
        miss_compiled = replace(compiled, extents=miss_extents)
        owner = AtlasFeatureArtifactOwner(miss_compiled.features, feature_schema)
        plain = start_source_backbone_producer(
            miss_compiled, parameters, (source,), feature_schema,
            owner)
        retained = start_retained_source_backbone_producer(
            miss_compiled, parameters, (source,), feature_schema, empty,
            owner, seal=_B13_EXECUTION_SEAL)
        plain_g1, retained_g1 = plain.advance(), retained.advance()
        np.testing.assert_array_equal(
            np.asarray(retained.receipts[0].hidden), np.asarray(plain.receipts[0].hidden))
        np.testing.assert_array_equal(
            np.asarray(retained_g1.hidden), np.asarray(plain_g1.hidden))
        self.assertEqual(retained._input_motif_read.participating_slots, ())
        self.assertEqual(retained._motif_read.participating_slots, ())
        self.assertEqual(retained.receipts[0].motif_disposition, QUALIFIED_MISS)
        self.assertEqual(retained_g1.motif_disposition, QUALIFIED_MISS)
        generation = execution_generation_digest(
            parameters, spec=spec, extents=miss_extents)
        miss_plan = replace(plan, generation_binding=generation)
        cache = _new_execution_cache(
            run_id="test-retained", generation=1,
            accepted_manifest_sha256="8" * 64,
            generation_binding=generation, motif_manifest=empty)
        with patch.object(
                forward_impl, "require_accepted_execution_cache",
                return_value=cache), patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache.require_accepted_execution_cache",
            return_value=cache,
        ):
            gradient = bamf_value_and_grad(
                parameters,
                BamfCompiledBatch(miss_compiled, (source,), feature_schema),
                miss_plan,
                (DecisionOutput("finish", ControlAction.END_FRAME),),
                {"finish": True}, cache=cache)
        self.assertEqual(len(gradient.execution.motif_reads), 2)
        self.assertTrue(all(read.participating_slots == ()
                            for read in gradient.execution.motif_reads))
        self.assertFalse(any(name.startswith("motif.site.")
                             for name in gradient.execution.dense_parameter_names))
        parent, transaction, eligibility, kwargs = self._candidate_step(
            case, parameters, empty, spec, miss_extents, gradient)
        provenance = bind_execution_provenance(loss_bearing_target=True,
                                               loss_execution=gradient.execution, **kwargs)
        for name in ("motif.page.0", "motif.site.0.projection",
                     "motif.site.1.projection"):
            mask = provenance.mask.parameter(name)
            self.assertFalse(mask.whole_parameter)
            self.assertEqual(mask.row_indices, ())
        self.assertEqual(int(mx.max(
            transaction.optimizer.update_counts["motif.page.0"])), 0)
        for site_index in (0, 1):
            self.assertEqual(int(transaction.optimizer.update_counts[
                f"motif.site.{site_index}.projection"]), 0)
        for name in parent.optimizer.parameters:
            if name.startswith("motif."):
                for field in ("parameters", "m", "v", "update_counts"):
                    np.testing.assert_array_equal(
                        np.asarray(getattr(transaction.optimizer, field)[name]),
                        np.asarray(getattr(parent.optimizer, field)[name]))
    def test_same_frame_exact_hit_vs_nonmatching_key_is_safe_at_both_sites(self):
        case = retained_tests.AtlasModelRetainedMotifTests(
            "test_retained_b08_hit_enters_the_same_loss_bearing_b09_trace")
        (compiled, parameters, source, feature_schema, plan, _cache,
         spec, extents, manifest, slot_id) = case._runtime_fixture()
        miss_manifest = MotifManifest(
            manifest.semantic_release,
            tuple(
                MotifSlot(
                    slot.slot_id,
                    replace(
                        slot.key,
                        relation_signature=hashlib.sha256(
                            f"b08-miss-{slot.slot_id}".encode()).hexdigest(),
                    ),
                )
                for slot in manifest.slots
            ),
            capacity=manifest.capacity,
        )
        miss_extents = GenerationExtents(
            extents.semantic_bank_count, extents.motif_page_count,
            extents.active_semantic_digest, miss_manifest.digest,
            extents.factor_map_digest)
        miss_compiled = replace(compiled, extents=miss_extents)

        hit_owner = AtlasFeatureArtifactOwner(compiled.features, feature_schema)
        hit = start_retained_source_backbone_producer(
            compiled, parameters, (source,), feature_schema, manifest,
            hit_owner, seal=_B13_EXECUTION_SEAL)
        hit_g1 = hit.advance()

        miss_owner = AtlasFeatureArtifactOwner(
            miss_compiled.features, feature_schema)
        missed = start_retained_source_backbone_producer(
            miss_compiled, parameters, (source,), feature_schema,
            miss_manifest, miss_owner, seal=_B13_EXECUTION_SEAL)
        missed_g1 = missed.advance()

        self.assertEqual(
            (hit._input_motif_read.participating_slots,
             hit._motif_read.participating_slots),
            ((slot_id,), (slot_id,)),
        )
        self.assertGreater(float(mx.abs(
            hit._input_motif_read.hidden - hit._encoded.global_seeds).sum()), 0.0)
        self.assertGreater(float(mx.abs(
            hit._motif_read.hidden - hit._session.results[0].hidden).sum()), 0.0)
        self.assertEqual(hit.receipts[0].motif_disposition, "SOURCE_QUALIFIED_HIT")
        self.assertEqual(hit_g1.motif_disposition, "SOURCE_QUALIFIED_HIT")

        self.assertEqual(missed._input_motif_read.participating_slots, ())
        self.assertEqual(missed._motif_read.participating_slots, ())
        np.testing.assert_array_equal(
            np.asarray(missed._input_motif_read.hidden),
            np.asarray(missed._encoded.global_seeds))
        np.testing.assert_array_equal(
            np.asarray(missed._motif_read.hidden),
            np.asarray(missed._session.results[0].hidden))
        self.assertEqual(missed.receipts[0].motif_disposition, QUALIFIED_MISS)
        self.assertEqual(missed_g1.motif_disposition, QUALIFIED_MISS)

        generation = execution_generation_digest(
            parameters, spec=spec, extents=miss_extents)
        miss_plan = replace(plan, generation_binding=generation)
        cache = _new_execution_cache(
            run_id="test-retained", generation=1,
            accepted_manifest_sha256="8" * 64,
            generation_binding=generation, motif_manifest=miss_manifest)
        with patch.object(
                forward_impl, "require_accepted_execution_cache",
                return_value=cache), patch(
            "bilqis_mlx.runtime.bamf_bundle.execution_cache.require_accepted_execution_cache",
            return_value=cache,
        ):
            gradient = bamf_value_and_grad(
                parameters,
                BamfCompiledBatch(miss_compiled, (source,), feature_schema),
                miss_plan,
                (DecisionOutput("finish", ControlAction.END_FRAME),),
                {"finish": True}, cache=cache)
        self.assertEqual(
            tuple(read.participating_slots for read in gradient.execution.motif_reads),
            ((), ()),
        )
        self.assertFalse(any(
            name.startswith("motif.site.")
            for name in gradient.execution.dense_parameter_names))
        parent, transaction, _eligibility, _kwargs = self._candidate_step(
            case, parameters, miss_manifest, spec, miss_extents, gradient)
        for name in parent.optimizer.parameters:
            if name.startswith("motif."):
                for field in ("parameters", "m", "v", "update_counts"):
                    np.testing.assert_array_equal(
                        np.asarray(getattr(transaction.optimizer, field)[name]),
                        np.asarray(getattr(parent.optimizer, field)[name]))
    def test_owner_revocation_is_a_safe_miss_at_both_sites(self):
        case = retained_tests.AtlasModelRetainedMotifTests(
            "test_retained_b08_hit_enters_the_same_loss_bearing_b09_trace")
        (compiled, parameters, source, feature_schema, _plan, _cache,
         _spec, _extents, manifest, _slot_id) = case._runtime_fixture()
        rights_case = PublicFormalSchemaRightsOwnerTests(
            "test_same_epoch_revocation_survives_fresh_and_cold_owner_reissue")
        rights_case.setUp()
        try:
            frame, _handle = rights_case._target()
            rights_case._revoke(rights_registry._REGISTRY_SHA256, frame)
            owner = AtlasFeatureArtifactOwner(compiled.features, feature_schema)
            producer = start_retained_source_backbone_producer(
                compiled, parameters, (source,), feature_schema, manifest, owner,
                seal=_B13_EXECUTION_SEAL)
            g1 = producer.advance()
            for read, before in (
                (producer._input_motif_read, producer._encoded.global_seeds),
                (producer._motif_read, producer._session.results[0].hidden),
            ):
                self.assertIn("HELD", {item for row in read.dispositions for item in row})
                self.assertEqual(read.participating_slots, ())
                np.testing.assert_array_equal(np.asarray(read.hidden), np.asarray(before))
            self.assertEqual(producer.receipts[0].motif_disposition, QUALIFIED_MISS)
            self.assertEqual(g1.motif_disposition, QUALIFIED_MISS)
        finally:
            rights_case.doCleanups()
